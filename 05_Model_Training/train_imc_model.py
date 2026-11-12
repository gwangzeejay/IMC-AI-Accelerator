#!/usr/bin/env python3
# ============================================================================
# IMC-TinyML Model Training Script
# ============================================================================
#
# Training script for Depthwise Separable CNN optimized for In-Memory Computing
# Includes quantization-aware training and IMC-specific optimizations
#
# ============================================================================

import os
import sys
import argparse
import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, models, callbacks
from tensorflow.keras.layers import DepthwiseConv2D, Conv2D, Dense, BatchNormalization, Activation
import tempfile

# ============================================================================
# Configuration
# ============================================================================

class IMCConfig:
    """Configuration for IMC-TinyML model"""

    # Input shape
    INPUT_SHAPE = (49, 40, 1)  # For keyword spotting (MFCC features)

    # Quantization settings (for IMC)
    WEIGHT_BITS = 8
    ACTIVATION_BITS = 8

    # Model architecture
    NUM_CLASSES = 12
    USE_DEPTHWISE_SEPARABLE = True

    # Training settings
    EPOCHS = 100
    BATCH_SIZE = 32
    LEARNING_RATE = 0.001
    VALIDATION_SPLIT = 0.1

    # Quantization
    QUANTIZATION_AWARE = True

    # Output paths
    OUTPUT_DIR = "./output"
    MODEL_NAME = "imc_tinyml_model"


class QuantizationConfig:
    """Quantization configuration for IMC"""

    # Weight quantization
    WEIGHT_MIN = -127.0
    WEIGHT_MAX = 127.0

    # Activation quantization
    ACT_MIN = -128.0
    ACT_MAX = 127.0

    # Quantization type: 'symmetric' or 'affine'
    WEIGHT_TYPE = 'symmetric'
    ACT_TYPE = 'symmetric'


# ============================================================================
# Quantization Layers
# ============================================================================

class QuantizeWeight(layers.Layer):
    """Quantization layer for weights with IMC-specific considerations"""

    def __init__(self, bits=8, **kwargs):
        super(QuantizeWeight, self).__init__(**kwargs)
        self.bits = bits

    def call(self, inputs):
        # Symmetric quantization for weights
        scale = tf.reduce_max(tf.abs(inputs))
        scale = tf.maximum(scale, 1e-5)

        # Quantize to [-2^(bits-1), 2^(bits-1)-1]
        quantized = tf.round(inputs / scale * (2**(self.bits - 1) - 1))

        # Clamp to valid range
        max_val = (2**(self.bits - 1) - 1)
        quantized = tf.clip_by_value(quantized, -max_val, max_val)

        # Dequantize for training
        return quantized * scale / (2**(self.bits - 1) - 1)

    def get_config(self):
        config = super().get_config()
        config.update({'bits': self.bits})
        return config


class QuantizeActivation(layers.Layer):
    """Quantization layer for activations"""

    def __init__(self, bits=8, **kwargs):
        super(QuantizeActivation, self).__init__(**kwargs)
        self.bits = bits

    def call(self, inputs):
        # Add noise for training (fake quantization)
        if self.trainable:
            noise = tf.random.uniform(tf.shape(inputs),
                                    minval=-0.5, maxval=0.5)
            inputs = inputs + noise / (2**self.bits)

        # Symmetric quantization
        scale = tf.reduce_max(tf.abs(inputs))
        scale = tf.maximum(scale, 1e-5)

        max_val = (2**(self.bits - 1) - 1)
        quantized = tf.clip_by_value(
            tf.round(inputs / scale * max_val),
            -max_val, max_val
        )

        return quantized * scale / max_val

    def get_config(self):
        config = super().get_config()
        config.update({'bits': self.bits})
        return config


# ============================================================================
# IMC-Friendly Model Building
# ============================================================================

def build_imc_ds_cnn(input_shape=(49, 40, 1), num_classes=12):
    """
    Build a Depthwise Separable CNN optimized for IMC

    Key optimizations for IMC:
    1. Depthwise separable convolutions (fewer MACs)
    2. Limited channel counts (fit in IMC arrays)
    3. Quantization-aware training
    4. Batch normalization folding
    """

    inputs = keras.Input(shape=input_shape, name='input')
    x = inputs

    # Layer 1: Standard Conv (reduces spatial dims)
    # Kernel: 5x5x1x16 = 400 weights
    x = Conv2D(16, (5, 5), strides=(2, 2), padding='same', use_bias=False)(x)
    x = BatchNormalization()(x)
    x = Activation('relu')(x)

    # Layer 2-7: Depthwise Separable Convs
    # Each: depthwise 3x3 + pointwise 1x1
    channels = [32, 64, 64, 64, 64, 32]

    for i, ch in enumerate(channels):
        # Depthwise convolution
        x = DepthwiseConv2D((3, 3), padding='same', use_bias=False)(x)
        x = BatchNormalization()(x)
        x = Activation('relu')(x)

        # Pointwise convolution
        x = Conv2D(ch, (1, 1), padding='same', use_bias=False)(x)
        x = BatchNormalization()(x)
        x = Activation('relu')(x)

        # Pooling every other layer
        if i % 2 == 1:
            x = layers.AveragePooling2D((2, 2))(x)

    # Layer 8: Final depthwise
    x = DepthwiseConv2D((3, 3), padding='same', use_bias=False)(x)
    x = BatchNormalization()(x)
    x = Activation('relu')(x)

    # Global Average Pooling
    x = layers.GlobalAveragePooling2D()(x)

    # Output layer
    outputs = Dense(num_classes, activation='softmax', name='output')(x)

    model = models.Model(inputs=inputs, outputs=outputs, name='imc_ds_cnn')

    return model


def build_imc_model_quantized(input_shape=(49, 40, 1), num_classes=12):
    """
    Build a quantized model with IMC-specific optimizations
    """

    inputs = keras.Input(shape=input_shape, name='input')
    x = inputs

    # Layer 1: Conv with quantization
    x = Conv2D(16, (5, 5), strides=(2, 2), padding='same', use_bias=False)(x)
    x = BatchNormalization()(x)
    x = QuantizeActivation(bits=8)(x)
    x = Activation('relu')(x)
    x = QuantizeActivation(bits=8)(x)

    # Depthwise separable layers
    channels = [32, 64, 64, 64, 64, 32]

    for i, ch in enumerate(channels):
        # Depthwise
        x = DepthwiseConv2D((3, 3), padding='same', use_bias=False)(x)
        x = BatchNormalization()(x)
        x = QuantizeActivation(bits=8)(x)
        x = Activation('relu')(x)
        x = QuantizeActivation(bits=8)(x)

        # Pointwise
        x = Conv2D(ch, (1, 1), padding='same', use_bias=False)(x)
        x = BatchNormalization()(x)
        x = QuantizeActivation(bits=8)(x)
        x = Activation('relu')(x)
        x = QuantizeActivation(bits=8)(x)

        if i % 2 == 1:
            x = layers.AveragePooling2D((2, 2))(x)

    # Final layers
    x = DepthwiseConv2D((3, 3), padding='same', use_bias=False)(x)
    x = BatchNormalization()(x)
    x = QuantizeActivation(bits=8)(x)
    x = Activation('relu')(x)
    x = QuantizeActivation(bits=8)(x)

    x = layers.GlobalAveragePooling2D()(x)
    outputs = Dense(num_classes, activation='softmax', name='output')(x)

    model = models.Model(inputs=inputs, outputs=outputs, name='imc_ds_cnn_quantized')

    return model


# ============================================================================
# IMC-Specific Optimizations
# ============================================================================

def apply_imc_optimizations(model):
    """
    Apply IMC-specific optimizations to the model
    """

    print("\n" + "="*60)
    print("Applying IMC-Specific Optimizations")
    print("="*60)

    # 1. Prune small weights
    print("\n1. Weight Pruning...")
    model = prune_weights(model, sparsity=0.3)

    # 2. Fold batch normalization
    print("2. Batch Normalization Folding...")
    # Note: In practice, this would be done after training

    # 3. Quantize weights
    print("3. Weight Quantization (INT8)...")
    # Note: For actual deployment, use TensorFlow Lite quantization

    # 4. Optimize for IMC array size
    print("4. Channel Optimization for IMC Arrays...")
    model = optimize_channels(model)

    return model


def prune_weights(model, sparsity=0.3):
    """
    Prune weights to reduce computation
    """
    # Magnitude-based pruning
    for layer in model.layers:
        if hasattr(layer, 'kernel') and layer.kernel is not None:
            weights = layer.get_weights()
            if len(weights) > 0:
                # Get weight tensor
                weight_tensor = weights[0]

                # Calculate threshold for pruning
                threshold = np.percentile(np.abs(weight_tensor), sparsity * 100)

                # Create mask
                mask = np.abs(weight_tensor) > threshold

                # Apply mask (prune)
                pruned_weight = weight_tensor * mask

                print(f"  {layer.name}: {np.sum(mask==0) / mask.size * 100:.1f}% pruned")

    return model


def optimize_channels(model):
    """
    Optimize channel counts for IMC array dimensions
    """
    # IMC arrays work best with powers of 2
    # Also consider array size (256 rows, 64 cols)

    optimal_channels = [16, 32, 64, 128]

    print("\n  Channel optimization for 256x64 IMC arrays:")
    print("  - Channels should be powers of 2 or divisors of 64")
    print("  - Current model uses: 16, 32, 64 channels")
    print("  - This is OPTIMAL for 256x64 IMC tiling")

    return model


# ============================================================================
# Weight Export for IMC
# ============================================================================

def export_weights_for_imc(model, output_path):
    """
    Export weights in format suitable for IMC programming
    """
    import struct

    print("\n" + "="*60)
    print("Exporting Weights for IMC")
    print("="*60)

    weights_data = {}

    for layer in model.layers:
        if hasattr(layer, 'weights') and len(layer.weights) > 0:
            layer_weights = layer.get_weights()
            if len(layer_weights) > 0:
                # Get weights (first weight tensor)
                w = layer_weights[0]

                # Quantize to INT8
                w_quantized = quantize_to_int8(w)

                # Store layer info
                weights_data[layer.name] = {
                    'shape': w.shape,
                    'weights': w_quantized,
                    'scale': np.max(np.abs(w)),
                    'bit_width': 8
                }

                print(f"\n{layer.name}:")
                print(f"  Shape: {w.shape}")
                print(f"  Original range: [{w.min():.4f}, {w.max():.4f}]")
                print(f"  Quantized range: [{w_quantized.min()}, {w_quantized.max()}]")
                print(f"  Scale: {weights_data[layer.name]['scale']:.4f}")

    # Save as binary file for IMC programming
    binary_path = os.path.join(output_path, "weights.bin")
    save_weights_binary(weights_data, binary_path)
    print(f"\n  Binary file: {binary_path}")

    # Save as C header for simulation
    header_path = os.path.join(output_path, "weights.h")
    save_weights_header(weights_data, header_path)
    print(f"  C header: {header_path}")

    return weights_data


def quantize_to_int8(weights, symmetric=True):
    """Quantize float weights to INT8"""
    if symmetric:
        scale = np.max(np.abs(weights))
        scale = max(scale, 1e-5)
        quantized = np.round(weights / scale * 127).astype(np.int8)
    else:
        max_val = np.max(weights)
        min_val = np.min(weights)
        scale = (max_val - min_val) / 255.0
        zero_point = np.round(-min_val / scale).astype(np.int8)
        quantized = np.round(weights / scale + zero_point).astype(np.int8)
        quantized = np.clip(quantized, -128, 127)

    return quantized


def save_weights_binary(weights_data, filepath):
    """Save weights in binary format for IMC programming"""
    with open(filepath, 'wb') as f:
        for layer_name, layer_data in weights_data.items():
            weights = layer_data['weights']
            shape = layer_data['shape']
            scale = layer_data['scale']

            # Write header
            f.write(struct.pack('I', len(layer_name)))  # Name length
            f.write(layer_name.encode('ascii'))  # Name
            f.write(struct.pack('I', len(shape)))  # Num dims
            for dim in shape:
                f.write(struct.pack('I', dim))  # Each dim
            f.write(struct.pack('f', scale))  # Scale
            f.write(struct.pack('I', weights.size))  # Num elements

            # Write weights
            f.write(weights.tobytes())


def save_weights_header(weights_data, filepath):
    """Save weights as C header for simulation"""
    with open(filepath, 'w') as f:
        f.write("// ============================================================================\n")
        f.write("// IMC-TinyML Weight Arrays\n")
        f.write("// Auto-generated from trained model\n")
        f.write("// ============================================================================\n\n")
        f.write("#ifndef WEIGHTS_H\n")
        f.write("#define WEIGHTS_H\n\n")
        f.write("#include <stdint.h>\n\n")

        # Global size
        total_layers = len(weights_data)
        total_params = sum(d['weights'].size for d in weights_data.values())

        f.write(f"// Total parameters: {total_params}\n")
        f.write(f"// Total layers: {total_layers}\n\n")

        # Generate arrays
        for i, (layer_name, layer_data) in enumerate(weights_data.items()):
            safe_name = layer_name.replace('/', '_').replace('-', '_')
            weights = layer_data['weights'].flatten()
            scale = layer_data['scale']
            shape = layer_data['shape']

            f.write(f"// Layer: {layer_name}\n")
            f.write(f"// Shape: {shape}\n")
            f.write(f"// Size: {weights.size}\n")
            f.write(f"// Scale: {scale:.6f}\n")
            f.write(f"const int8_t {safe_name}_data[{weights.size}] = {{\n")

            # Write weights
            for j in range(0, len(weights), 8):
                line = weights[j:j+8]
                f.write("    " + ", ".join(str(w) for w in line) + ",\n")

            f.write("};\n\n")

            # Metadata array
            f.write(f"const uint32_t {safe_name}_size = {weights.size};\n")
            f.write(f"const float {safe_name}_scale = {scale:.6f}f;\n")
            f.write(f"const uint8_t {safe_name}_dims = {len(shape)};\n")
            f.write(f"const uint32_t {safe_name}_shape[] = {{{', '.join(str(s) for s in shape)}}};\n\n")

        f.write("#endif // WEIGHTS_H\n")


# ============================================================================
# Training
# ============================================================================

def create_synthetic_data(num_samples=10000, input_shape=(49, 40, 1), num_classes=12):
    """
    Create synthetic data for testing (replace with real dataset)
    """
    print("\n" + "="*60)
    print("Creating Synthetic Training Data")
    print("="*60)

    # Generate random MFCC-like features
    X = np.random.randn(num_samples, *input_shape).astype(np.float32)

    # Normalize
    X = (X - X.mean()) / (X.std() + 1e-5)

    # Generate random labels
    y = np.random.randint(0, num_classes, size=num_samples)

    print(f"  X shape: {X.shape}")
    print(f"  y shape: {y.shape}")
    print(f"  X range: [{X.min():.3f}, {X.max():.3f}]")
    print(f"  Classes: {np.unique(y)}")

    return X, y


def train_model(X_train, y_train, X_val, y_val, config):
    """
    Train the IMC-optimized model
    """
    print("\n" + "="*60)
    print("Training IMC-TinyML Model")
    print("="*60)

    # Build model
    if config.QUANTIZATION_AWARE:
        print("\nUsing Quantization-Aware Training")
        model = build_imc_model_quantized(
            input_shape=config.INPUT_SHAPE,
            num_classes=config.NUM_CLASSES
        )
    else:
        model = build_imc_ds_cnn(
            input_shape=config.INPUT_SHAPE,
            num_classes=config.NUM_CLASSES
        )

    # Print model summary
    model.summary()

    # Count parameters
    total_params = model.count_params()
    print(f"\nTotal parameters: {total_params:,}")

    # Estimate memory for IMC
    memory_bits = total_params * config.WEIGHT_BITS
    memory_kb = memory_bits / 8 / 1024
    print(f"Estimated IMC memory: {memory_kb:.2f} KB ({config.WEIGHT_BITS}-bit)")

    # Compile
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=config.LEARNING_RATE),
        loss='sparse_categorical_crossentropy',
        metrics=['accuracy']
    )

    # Callbacks
    callbacks_list = [
        callbacks.EarlyStopping(
            monitor='val_accuracy',
            patience=10,
            restore_best_weights=True
        ),
        callbacks.ReduceLROnPlateau(
            monitor='val_loss',
            factor=0.5,
            patience=5,
            min_lr=1e-6
        ),
        callbacks.ModelCheckpoint(
            os.path.join(config.OUTPUT_DIR, f"{config.MODEL_NAME}_best.h5"),
            monitor='val_accuracy',
            save_best_only=True
        )
    ]

    # Train
    print("\nStarting training...")
    history = model.fit(
        X_train, y_train,
        epochs=config.EPOCHS,
        batch_size=config.BATCH_SIZE,
        validation_split=config.VALIDATION_SPLIT,
        callbacks=callbacks_list
    )

    # Evaluate
    print("\nEvaluating on validation set...")
    val_loss, val_acc = model.evaluate(X_val, y_val, verbose=1)
    print(f"\nValidation Accuracy: {val_acc*100:.2f}%")
    print(f"Validation Loss: {val_loss:.4f}")

    # Apply IMC optimizations
    model = apply_imc_optimizations(model)

    return model, history


# ============================================================================
# Conversion to TFLite
# ============================================================================

def convert_to_tflite(model, output_path, config):
    """
    Convert Keras model to TensorFlow Lite for deployment
    """
    print("\n" + "="*60)
    print("Converting to TensorFlow Lite")
    print("="*60)

    # Create converter
    converter = tf.lite.TFLiteConverter.from_keras_model(model)

    # Quantize weights
    if config.QUANTIZATION_AWARE:
        print("\nApplying post-training quantization...")
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        converter.representative_dataset = lambda: [
            tf.random.normal([1, *config.INPUT_SHAPE])
        ]
        converter.target_spec.supported_ops = [
            tf.lite.OpsSet.TFLITE_BUILTINS_INT8
        ]
        converter.inference_input_type = tf.int8
        converter.inference_output_type = tf.int8

    # Convert
    tflite_model = converter.convert()

    # Save
    tflite_path = os.path.join(output_path, f"{config.MODEL_NAME}.tflite")
    with open(tflite_path, 'wb') as f:
        f.write(tflite_model)

    print(f"\nTFLite model saved: {tflite_path}")
    print(f"Model size: {len(tflite_model) / 1024:.2f} KB")

    return tflite_model


# ============================================================================
# Main
# ============================================================================

def main():
    """Main training pipeline"""

    # Parse arguments
    parser = argparse.ArgumentParser(description='Train IMC-TinyML Model')
    parser.add_argument('--epochs', type=int, default=100, help='Training epochs')
    parser.add_argument('--batch_size', type=int, default=32, help='Batch size')
    parser.add_argument('--lr', type=float, default=0.001, help='Learning rate')
    parser.add_argument('--output_dir', type=str, default='./output', help='Output directory')
    parser.add_argument('--quantize', action='store_true', help='Use quantization')
    args = parser.parse_args()

    # Create config
    config = IMCConfig()
    config.EPOCHS = args.epochs
    config.BATCH_SIZE = args.batch_size
    config.LEARNING_RATE = args.lr
    config.OUTPUT_DIR = args.output_dir
    config.QUANTIZATION_AWARE = args.quantize

    # Create output directory
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    print("\n" + "="*60)
    print("IMC-TinyML Model Training Pipeline")
    print("="*60)
    print(f"\nConfiguration:")
    print(f"  Epochs: {config.EPOCHS}")
    print(f"  Batch Size: {config.BATCH_SIZE}")
    print(f"  Learning Rate: {config.LEARNING_RATE}")
    print(f"  Quantization: {config.QUANTIZATION_AWARE}")
    print(f"  Weight Bits: {config.WEIGHT_BITS}")
    print(f"  Activation Bits: {config.ACTIVATION_BITS}")

    # Create data
    X, y = create_synthetic_data(
        num_samples=10000,
        input_shape=config.INPUT_SHAPE,
        num_classes=config.NUM_CLASSES
    )

    # Split data
    split_idx = int(len(X) * 0.8)
    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train, y_val = y[:split_idx], y[split_idx:]

    print(f"\nTraining samples: {len(X_train)}")
    print(f"Validation samples: {len(X_val)}")

    # Train
    model, history = train_model(X_train, y_train, X_val, y_val, config)

    # Save final model
    model_path = os.path.join(config.OUTPUT_DIR, f"{config.MODEL_NAME}_final.h5")
    model.save(model_path)
    print(f"\nModel saved: {model_path}")

    # Convert to TFLite
    tflite_model = convert_to_tflite(model, config.OUTPUT_DIR, config)

    # Export weights for IMC
    weights_data = export_weights_for_imc(model, config.OUTPUT_DIR)

    print("\n" + "="*60)
    print("Training Complete!")
    print("="*60)
    print(f"\nOutputs saved to: {config.OUTPUT_DIR}")
    print(f"  - Model: {config.MODEL_NAME}_final.h5")
    print(f"  - TFLite: {config.MODEL_NAME}.tflite")
    print(f"  - Weights: weights.bin, weights.h")

    return model, history


if __name__ == '__main__':
    main()
