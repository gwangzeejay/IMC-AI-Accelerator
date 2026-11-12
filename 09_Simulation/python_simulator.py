#!/usr/bin/env python3
# ============================================================================
# IMC-TinyML Python Inference Simulator
# ============================================================================
#
# Behavioral simulation of the IMC accelerator for verification
# Models the analog computation inside IMC arrays
#
# ============================================================================

import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
import struct
import argparse
import os

# ============================================================================
# IMC Array Simulator
# ============================================================================

@dataclass
class IMCConfig:
    """IMC Array Configuration"""
    num_rows: int = 256
    num_cols: int = 64
    num_tiles: int = 4
    bit_precision: int = 8
    wordline_voltage_max: float = 1.0
    cell_conductance_min: float = 1e-6  # S
    cell_conductance_max: float = 100e-6  # S


class IMCArray:
    """
    Behavioral model of an SRAM-based IMC array

    Models:
    - Weight storage as cell conductance
    - Wordline voltage as input
    - Bitline current as output
    - Shift-add accumulation for multi-bit
    """

    def __init__(self, config: IMCConfig):
        self.config = config
        self.rows = config.num_rows
        self.cols = config.num_cols

        # Weight memory (stored as signed integers -128 to 127)
        # Maps to conductance range [G_min, G_max]
        self.weights = np.zeros((config.num_rows, config.num_cols), dtype=np.int8)

        # Statistics
        self.access_count = 0
        self.computation_energy = 0.0

    def load_weights(self, weight_matrix: np.ndarray):
        """
        Load weights into the IMC array

        Args:
            weight_matrix: Shape (rows, cols) with INT8 values
        """
        assert weight_matrix.shape == (self.rows, self.cols), \
            f"Weight shape {weight_matrix.shape} != ({self.rows}, {self.cols})"

        self.weights = weight_matrix.astype(np.int8)

    def compute(self, input_vector: np.ndarray, noise_std: float = 0.0) -> np.ndarray:
        """
        Perform matrix-vector multiplication in the IMC array

        Args:
            input_vector: Shape (rows,) with values 0-255 (8-bit)
            noise_std: Standard deviation of noise to add (modeling analog effects)

        Returns:
            Output vector: Shape (cols,)
        """
        assert len(input_vector) == self.rows, \
            f"Input length {len(input_vector)} != {self.rows}"

        # Convert input to voltages (0 to V_max)
        v_in = (input_vector.astype(np.float64) / 255.0) * self.config.wordline_voltage_max

        # Convert weights to conductances
        # G = G_min + (G_max - G_min) * (w / 255)
        G_min = self.config.cell_conductance_min
        G_max = self.config.cell_conductance_max
        G_range = G_max - G_min

        # Conductance matrix
        G = G_min + G_range * ((self.weights.astype(np.float64) + 128) / 255.0)

        # Compute bitline currents: I_BL = V_in @ G
        # Each row i contributes: v_in[i] * G[i, j]
        I_BL = np.dot(v_in, G)

        # Add noise (modeling analog non-idealities)
        if noise_std > 0:
            noise = np.random.normal(0, noise_std, self.cols)
            I_BL += noise

        return I_BL

    def shift_add_accumulate(self, input_vector: np.ndarray,
                            bit_position: int = 0) -> np.ndarray:
        """
        Shift-add accumulation for multi-bit computation

        Args:
            input_vector: Input values
            bit_position: Current bit (0-7)

        Returns:
            Partial sum for this bit
        """
        # Compute current contribution
        current = self.compute(input_vector)

        # Shift by bit position (equivalent to multiplying by 2^bit)
        shifted = current * (2 ** bit_position)

        return shifted

    def energy_per_access(self) -> float:
        """
        Estimate energy per array access (in fJ)

        Based on SRAM access energy model:
        - Read: ~100 fJ per bitline
        - Write: ~200 fJ per bitline
        """
        return 100.0 * self.cols  # fJ


class IMCTile:
    """
    IMC Tile: Multiple arrays for larger computations

    Supports tiling for weights that don't fit in one array
    """

    def __init__(self, config: IMCConfig):
        self.config = config
        self.arrays = [IMCArray(config) for _ in range(config.num_tiles)]

        # Tiling state
        self.tile_size = config.num_rows
        self.current_tile = 0

    def load_weights_tiled(self, weight_matrix: np.ndarray):
        """
        Load weights with tiling for large matrices

        Args:
            weight_matrix: Shape (rows, cols), can be larger than single array
        """
        total_rows, total_cols = weight_matrix.shape
        rows_per_tile = self.config.num_rows
        cols_per_tile = self.config.num_cols // len(self.arrays)

        assert total_rows <= rows_per_tile * 4, "Too many rows for tiling"
        assert total_cols <= cols_per_tile * len(self.arrays), "Too many cols for tiling"

        # Distribute columns across tiles
        for tile_idx, array in enumerate(self.arrays):
            col_start = tile_idx * cols_per_tile
            col_end = min(col_start + cols_per_tile, total_cols)
            if col_start < total_cols:
                tile_weights = weight_matrix[:, col_start:col_end]
                # Pad if necessary
                if tile_weights.shape[1] < cols_per_tile:
                    tile_weights = np.pad(tile_weights,
                                        ((0, 0), (0, cols_per_tile - tile_weights.shape[1])),
                                        mode='constant')
                array.load_weights(tile_weights[:rows_per_tile, :])

    def compute(self, input_vector: np.ndarray, noise_std: float = 0.0) -> np.ndarray:
        """
        Compute with tiling support

        Args:
            input_vector: Input vector
            noise_std: Noise level

        Returns:
            Result vector
        """
        results = []
        for array in self.arrays:
            results.append(array.compute(input_vector, noise_std))

        return np.concatenate(results)


# ============================================================================
# Activation Functions
# ============================================================================

class ActivationUnit:
    """Digital activation functions"""

    @staticmethod
    def relu(x: np.ndarray) -> np.ndarray:
        """ReLU: max(0, x)"""
        return np.maximum(0, x)

    @staticmethod
    def relu6(x: np.ndarray) -> np.ndarray:
        """ReLU6: min(max(0, x), 6)"""
        return np.clip(x, 0, 6)

    @staticmethod
    def sigmoid(x: np.ndarray) -> np.ndarray:
        """Sigmoid (piecewise linear approximation)"""
        result = np.zeros_like(x)
        result[x < -4] = 0
        result[(x >= -4) & (x < 4)] = (x[(x >= -4) & (x < 4)] + 4) / 8
        result[x >= 4] = 1
        return result

    @staticmethod
    def tanh(x: np.ndarray) -> np.ndarray:
        """Tanh (piecewise linear approximation)"""
        result = np.zeros_like(x)
        result[x < -2] = -1
        result[(x >= -2) & (x < 2)] = x[(x >= -2) & (x < 2)] / 2
        result[x >= 2] = 1
        return result

    @staticmethod
    def apply(x: np.ndarray, act_type: str) -> np.ndarray:
        """Apply activation by name"""
        activations = {
            'none': lambda x: x,
            'relu': ActivationUnit.relu,
            'relu6': ActivationUnit.relu6,
            'sigmoid': ActivationUnit.sigmoid,
            'tanh': ActivationUnit.tanh
        }
        return activations.get(act_type, ActivationUnit.relu)(x)


# ============================================================================
# Pooling
# ============================================================================

class PoolingUnit:
    """Pooling operations"""

    @staticmethod
    def max_pool2d(x: np.ndarray, pool_size: int = 2) -> np.ndarray:
        """2D Max pooling"""
        h, w = x.shape
        out_h = h // pool_size
        out_w = w // pool_size

        result = np.zeros((out_h, out_w))
        for i in range(out_h):
            for j in range(out_w):
                h_start = i * pool_size
                w_start = j * pool_size
                window = x[h_start:h_start+pool_size, w_start:w_start+pool_size]
                result[i, j] = np.max(window)

        return result

    @staticmethod
    def avg_pool2d(x: np.ndarray, pool_size: int = 2) -> np.ndarray:
        """2D Average pooling"""
        h, w = x.shape
        out_h = h // pool_size
        out_w = w // pool_size

        result = np.zeros((out_h, out_w))
        for i in range(out_h):
            for j in range(out_w):
                h_start = i * pool_size
                w_start = j * pool_size
                window = x[h_start:h_start+pool_size, w_start:w_start+pool_size]
                result[i, j] = np.mean(window)

        return result

    @staticmethod
    def global_avg_pool(x: np.ndarray) -> np.ndarray:
        """Global average pooling"""
        return np.mean(x, axis=(0, 1)) if x.ndim == 3 else np.mean(x)


# ============================================================================
# Accelerator Simulator
# ============================================================================

class IMCAcceleratorSim:
    """
    Complete IMC-TinyML Accelerator Simulator

    Integrates:
    - IMC arrays
    - Activation units
    - Pooling
    - Control flow
    """

    def __init__(self, config: Optional[IMCConfig] = None):
        self.config = config or IMCConfig()
        self.tile = IMCTile(self.config)
        self.activation = ActivationUnit()
        self.pooling = PoolingUnit()

        # Layer state
        self.weights = {}
        self.biases = {}
        self.current_layer = 0

        # Statistics
        self.total_cycles = 0
        self.total_energy = 0.0

    def load_layer_weights(self, layer_idx: int, weights: np.ndarray,
                          bias: Optional[np.ndarray] = None):
        """Load weights for a specific layer"""
        self.weights[layer_idx] = weights.astype(np.int8)
        if bias is not None:
            self.biases[layer_idx] = bias

    def forward_layer(self, input_data: np.ndarray, layer_config: Dict) -> np.ndarray:
        """
        Forward pass through one layer

        Args:
            input_data: Input activations
            layer_config: Layer configuration dict

        Returns:
            Output activations
        """
        layer_type = layer_config.get('type', 'dense')

        if layer_type == 'dense':
            # Dense/FC layer
            output = self._dense_layer(input_data, layer_config)

        elif layer_type == 'conv2d':
            # 2D Convolution
            output = self._conv2d_layer(input_data, layer_config)

        elif layer_type == 'depthwise':
            # Depthwise convolution
            output = self._depthwise_layer(input_data, layer_config)

        elif layer_type == 'pointwise':
            # Pointwise convolution
            output = self._pointwise_layer(input_data, layer_config)

        elif layer_type == 'pool':
            # Pooling
            output = self._pool_layer(input_data, layer_config)

        elif layer_type == 'act':
            # Activation only
            output = self._act_layer(input_data, layer_config)

        else:
            raise ValueError(f"Unknown layer type: {layer_type}")

        # Apply activation if specified
        act_type = layer_config.get('activation', 'none')
        if act_type != 'none':
            output = self.activation.apply(output, act_type)

        self.total_cycles += layer_config.get('cycles', 100)

        return output

    def _dense_layer(self, input_data: np.ndarray, config: Dict) -> np.ndarray:
        """Dense layer computation"""
        weights = config['weights']
        bias = config.get('bias', np.zeros(weights.shape[0]))

        # IMC computation
        # input_data: (in_features,)
        # weights: (out_features, in_features)
        output = np.dot(weights, input_data) + bias

        return output

    def _conv2d_layer(self, input_data: np.ndarray, config: Dict) -> np.ndarray:
        """2D Convolution"""
        weights = config['weights']  # (out_ch, in_ch, kh, kw)
        stride = config.get('stride', 1)
        padding = config.get('padding', 0)

        in_ch, in_h, in_w = input_data.shape
        out_ch = weights.shape[0]
        kh, kw = weights.shape[2], weights.shape[3]

        # Calculate output dimensions
        out_h = (in_h + 2*padding - kh) // stride + 1
        out_w = (in_w + 2*padding - kw) // stride + 1

        output = np.zeros((out_ch, out_h, out_w))

        # Im2col + GEMM would be faster, but simple convolution for clarity
        for oc in range(out_ch):
            for oh in range(out_h):
                for ow in range(out_w):
                    for ic in range(in_ch):
                        for kh_idx in range(kh):
                            for kw_idx in range(kw):
                                ih = oh * stride + kh_idx - padding
                                iw = ow * stride + kw_idx - padding
                                if 0 <= ih < in_h and 0 <= iw < in_w:
                                    output[oc, oh, ow] += (
                                        weights[oc, ic, kh_idx, kw_idx] *
                                        input_data[ic, ih, iw]
                                    )

        return output

    def _depthwise_layer(self, input_data: np.ndarray, config: Dict) -> np.ndarray:
        """Depthwise convolution"""
        weights = config['weights']  # (ch, kh, kw)
        stride = config.get('stride', 1)
        padding = config.get('padding', 0)

        ch, in_h, in_w = input_data.shape
        kh, kw = weights.shape[1], weights.shape[2]

        out_h = (in_h + 2*padding - kh) // stride + 1
        out_w = (in_w + 2*padding - kw) // stride + 1

        output = np.zeros((ch, out_h, out_w))

        for c in range(ch):
            for oh in range(out_h):
                for ow in range(out_w):
                    for kh_idx in range(kh):
                        for kw_idx in range(kw):
                            ih = oh * stride + kh_idx - padding
                            iw = ow * stride + kw_idx - padding
                            if 0 <= ih < in_h and 0 <= iw < in_w:
                                output[c, oh, ow] += (
                                    weights[c, kh_idx, kw_idx] *
                                    input_data[c, ih, iw]
                                )

        return output

    def _pointwise_layer(self, input_data: np.ndarray, config: Dict) -> np.ndarray:
        """Pointwise convolution (1x1)"""
        weights = config['weights']  # (out_ch, in_ch)

        if input_data.ndim == 3:
            ch, h, w = input_data.shape
            # Reshape to (h*w, ch) for matrix multiply
            x_flat = input_data.reshape(ch, -1).T  # (h*w, ch)
            output = np.dot(x_flat, weights.T).T   # (out_ch, h*w)
            output = output.reshape(-1, h, w)
        else:
            output = np.dot(weights, input_data)

        return output

    def _pool_layer(self, input_data: np.ndarray, config: Dict) -> np.ndarray:
        """Pooling layer"""
        pool_type = config.get('pool_type', 'avg')
        pool_size = config.get('pool_size', 2)

        if pool_type == 'avg':
            if input_data.ndim == 3:
                ch, h, w = input_data.shape
                out_h, out_w = h // pool_size, w // pool_size
                output = np.zeros((ch, out_h, out_w))
                for c in range(ch):
                    output[c] = self.pooling.avg_pool2d(input_data[c], pool_size)
            else:
                output = self.pooling.avg_pool2d(input_data, pool_size)

        elif pool_type == 'max':
            if input_data.ndim == 3:
                ch, h, w = input_data.shape
                out_h, out_w = h // pool_size, w // pool_size
                output = np.zeros((ch, out_h, out_w))
                for c in range(ch):
                    output[c] = self.pooling.max_pool2d(input_data[c], pool_size)
            else:
                output = self.pooling.max_pool2d(input_data, pool_size)

        elif pool_type == 'global_avg':
            output = self.pooling.global_avg_pool(input_data)

        return output

    def _act_layer(self, input_data: np.ndarray, config: Dict) -> np.ndarray:
        """Activation layer"""
        return input_data

    def infer(self, input_data: np.ndarray, layers: List[Dict]) -> Tuple[np.ndarray, Dict]:
        """
        Run full inference

        Args:
            input_data: Input tensor
            layers: List of layer configurations

        Returns:
            Tuple of (output, stats)
        """
        x = input_data.copy()
        stats = {
            'layers_executed': 0,
            'total_cycles': 0,
            'total_energy': 0.0
        }

        for layer_config in layers:
            x = self.forward_layer(x, layer_config)
            stats['layers_executed'] += 1

        stats['total_cycles'] = self.total_cycles
        stats['total_energy'] = self.total_energy

        return x, stats

    def compute_energy(self) -> float:
        """Compute total energy consumption"""
        # IMC array energy: ~0.1 fJ per bit per cell access
        array_energy = (self.config.num_rows * self.config.num_cols *
                       self.config.bit_precision * 0.1e-15)  # J

        # ADC energy: ~100 pJ per conversion
        adc_energy = self.config.num_cols * 100e-12  # J

        # Digital energy: ~10 pJ per MAC
        digital_energy = 10e-12 * self.total_cycles  # J

        return array_energy + adc_energy + digital_energy


# ============================================================================
# Weight File Loader
# ============================================================================

def load_weights_binary(filepath: str) -> Dict[str, np.ndarray]:
    """Load weights from binary file"""
    weights = {}

    with open(filepath, 'rb') as f:
        while True:
            # Read header
            header = f.read(4)
            if not header:
                break

            name_len = struct.unpack('I', header)[0]
            name = f.read(name_len).decode('ascii')

            # Read shape
            num_dims = struct.unpack('I', f.read(4))[0]
            shape = tuple(struct.unpack('I' * num_dims, f.read(4 * num_dims)))

            # Read scale
            scale = struct.unpack('f', f.read(4))[0]

            # Read weights
            num_elements = struct.unpack('I', f.read(4))[0]
            data = np.frombuffer(f.read(num_elements), dtype=np.int8)

            weights[name] = data.reshape(shape)

    return weights


def load_weights_header(filepath: str) -> Dict[str, np.ndarray]:
    """Parse C header file to extract weights"""
    weights = {}

    with open(filepath, 'r') as f:
        lines = f.readlines()

    current_name = None
    current_data = []
    in_array = False

    for line in lines:
        line = line.strip()

        if line.startswith('const int8_t') and '_data[' in line:
            # Start of array
            current_name = line.split()[2].replace('_data[', '')
            current_data = []
            in_array = True

        elif in_array and line == '};':
            # End of array
            weights[current_name] = np.array(current_data, dtype=np.int8)
            in_array = False

        elif in_array:
            # Data line
            data_str = line.rstrip(',')
            values = [int(x) for x in data_str.split(',') if x]
            current_data.extend(values)

    return weights


# ============================================================================
# Test Vector Generator
# ============================================================================

class TestVectorGenerator:
    """Generate test vectors for verification"""

    @staticmethod
    def generate_random_input(shape: Tuple, seed: int = 42) -> np.ndarray:
        """Generate random input"""
        np.random.seed(seed)
        return np.random.randint(0, 256, shape).astype(np.float32)

    @staticmethod
    def generate_weight_matrix(rows: int, cols: int,
                             seed: int = 42) -> np.ndarray:
        """Generate random weight matrix"""
        np.random.seed(seed)
        return np.random.randint(-128, 128, (rows, cols)).astype(np.int8)

    @staticmethod
    def generate_layer_configs() -> List[Dict]:
        """Generate typical DS-CNN layer configurations"""
        layers = [
            # Layer 1: Conv
            {
                'type': 'conv2d',
                'name': 'conv1',
                'weights': TestVectorGenerator.generate_weight_matrix(16, 1*5*5),
                'stride': 2,
                'activation': 'relu',
                'cycles': 1000
            },
            # Depthwise separable layers
            {
                'type': 'depthwise',
                'name': 'dw1',
                'weights': TestVectorGenerator.generate_weight_matrix(32, 3*3),
                'stride': 1,
                'activation': 'relu',
                'cycles': 500
            },
            {
                'type': 'pointwise',
                'name': 'pw1',
                'weights': TestVectorGenerator.generate_weight_matrix(64, 32),
                'activation': 'relu',
                'cycles': 600
            },
            {
                'type': 'pool',
                'name': 'pool1',
                'pool_type': 'avg',
                'pool_size': 2,
                'cycles': 100
            },
            # Final layers
            {
                'type': 'depthwise',
                'name': 'dw2',
                'weights': TestVectorGenerator.generate_weight_matrix(64, 3*3),
                'stride': 1,
                'activation': 'relu',
                'cycles': 500
            },
            {
                'type': 'pointwise',
                'name': 'pw2',
                'weights': TestVectorGenerator.generate_weight_matrix(32, 64),
                'activation': 'relu',
                'cycles': 400
            },
            {
                'type': 'pool',
                'name': 'pool2',
                'pool_type': 'global_avg',
                'cycles': 50
            },
            # Dense
            {
                'type': 'dense',
                'name': 'fc',
                'weights': TestVectorGenerator.generate_weight_matrix(12, 32),
                'activation': 'softmax',
                'cycles': 200
            }
        ]
        return layers

    @staticmethod
    def save_test_vectors(output_dir: str):
        """Save test vectors to files"""
        os.makedirs(output_dir, exist_ok=True)

        # Generate input test vector
        input_data = TestVectorGenerator.generate_random_input((1, 49, 40))
        input_path = os.path.join(output_dir, 'input.bin')
        input_data.astype(np.float32).tofile(input_path)
        print(f"Saved input: {input_path}")

        # Generate layer configs
        layers = TestVectorGenerator.generate_layer_configs()
        import json
        config_path = os.path.join(output_dir, 'layer_configs.json')
        with open(config_path, 'w') as f:
            # Convert numpy arrays to lists for JSON
            json_layers = []
            for layer in layers:
                layer_copy = layer.copy()
                if 'weights' in layer_copy:
                    layer_copy['weights'] = layer_copy['weights'].tolist()
                json_layers.append(layer_copy)
            json.dump(json_layers, f, indent=2)
        print(f"Saved configs: {config_path}")

        return input_data, layers


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='IMC-TinyML Simulator')
    parser.add_argument('--weights', type=str, help='Weight file (.bin or .h)')
    parser.add_argument('--input', type=str, help='Input file (.bin)')
    parser.add_argument('--output', type=str, default='./output',
                       help='Output directory')
    parser.add_argument('--noise', type=float, default=0.0,
                       help='Noise standard deviation')
    parser.add_argument('--generate', action='store_true',
                       help='Generate test vectors')
    args = parser.parse_args()

    if args.generate:
        print("Generating test vectors...")
        input_data, layers = TestVectorGenerator.save_test_vectors(args.output)
        print("Done!")

        # Run simulation with generated vectors
        print("\nRunning simulation...")
        sim = IMCAcceleratorSim()

        output, stats = sim.infer(input_data, layers)

        print(f"\nResults:")
        print(f"  Layers: {stats['layers_executed']}")
        print(f"  Cycles: {stats['total_cycles']}")
        print(f"  Energy: {sim.compute_energy() * 1e9:.3f} nJ")
        print(f"  Output shape: {output.shape}")
        print(f"  Output range: [{output.min():.3f}, {output.max():.3f}]")

    else:
        print("IMC-TinyML Simulator")
        print("Use --generate to create test vectors")
        print("Use --weights and --input for custom inference")


if __name__ == '__main__':
    main()
