#!/usr/bin/env python3
# ============================================================================
# IMC-TinyML Test Vector Generator
# ============================================================================
#
# Generates comprehensive test vectors for RTL verification
#
# ============================================================================

import numpy as np
import struct
import os
import json
import argparse
from typing import List, Dict, Tuple

# ============================================================================
# Constants
# ============================================================================

DATA_WIDTH = 8
ACCUM_WIDTH = 32
NUM_TILES = 4
ARRAY_ROWS = 256
ARRAY_COLS = 64

# ============================================================================
# Test Vector Classes
# ============================================================================

class TestVectorGenerator:
    """Generate test vectors for IMC accelerator"""

    def __init__(self, output_dir: str = "./test_vectors"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_all(self):
        """Generate all test vectors"""
        print("Generating test vectors...")

        self.generate_imc_array_tests()
        self.generate_activation_tests()
        self.generate_layer_tests()
        self.generate_apb_tests()
        self.generate_axi_stream_tests()
        self.generate_system_tests()

        print(f"\nTest vectors saved to: {self.output_dir}")

    # =========================================================================
    # IMC Array Tests
    # =========================================================================

    def generate_imc_array_tests(self):
        """Test vectors for IMC array"""
        print("  IMC Array tests...")

        # Test 1: Single weight, single input
        self._write_imc_test(
            "imc_single_weight",
            weights=np.array([[42]], dtype=np.int8),
            inputs=np.array([100], dtype=np.uint8),
            expected=4200  # 42 * 100
        )

        # Test 2: Multiple weights, single input
        self._write_imc_test(
            "imc_multi_weight",
            weights=np.array([[10, 20, 30, 40]], dtype=np.int8),
            inputs=np.array([100], dtype=np.uint8),
            expected=np.array([1000, 2000, 3000, 4000])  # [10*100, 20*100, ...]
        )

        # Test 3: Multiple inputs, multiple weights (matrix multiply)
        weights = np.array([
            [1, 2, 3],
            [4, 5, 6]
        ], dtype=np.int8)
        inputs = np.array([1, 2, 3], dtype=np.uint8)
        # Output: [1*1+2*2+3*3, 4*1+5*2+6*3] = [14, 32]
        expected = np.array([14, 32])

        self._write_imc_test("imc_matrix_mul", weights, inputs, expected)

        # Test 4: Edge cases
        self._write_imc_test(
            "imc_zero_weight",
            weights=np.array([[0]], dtype=np.int8),
            inputs=np.array([255], dtype=np.uint8),
            expected=np.array([0])
        )

        self._write_imc_test(
            "imc_zero_input",
            weights=np.array([[127]], dtype=np.int8),
            inputs=np.array([0], dtype=np.uint8),
            expected=np.array([0])
        )

        self._write_imc_test(
            "imc_max_values",
            weights=np.array([[127]], dtype=np.int8),
            inputs=np.array([255], dtype=np.uint8),
            expected=np.array([32385])  # 127 * 255 = 32385
        )

        # Test 5: Negative weights (signed)
        self._write_imc_test(
            "imc_negative_weight",
            weights=np.array([[-50]], dtype=np.int8),
            inputs=np.array([100], dtype=np.uint8),
            expected=np.array([-5000])
        )

    def _write_imc_test(self, name: str, weights: np.ndarray,
                       inputs: np.ndarray, expected: np.ndarray):
        """Write IMC test vector"""
        base_path = os.path.join(self.output_dir, name)

        # Write weights
        with open(f"{base_path}_weights.bin", 'wb') as f:
            weights.tofile(f)

        # Write inputs
        with open(f"{base_path}_input.bin", 'wb') as f:
            inputs.tofile(f)

        # Write expected output
        with open(f"{base_path}_expected.bin", 'wb') as f:
            expected.tofile(f)

        # Write metadata
        metadata = {
            'name': name,
            'weight_shape': list(weights.shape),
            'input_shape': list(inputs.shape),
            'expected_shape': list(expected.shape),
            'test_type': 'imc_array'
        }
        with open(f"{base_path}_meta.json", 'w') as f:
            json.dump(metadata, f, indent=2)

    # =========================================================================
    # Activation Tests
    # =========================================================================

    def generate_activation_tests(self):
        """Test vectors for activation functions"""
        print("  Activation tests...")

        # ReLU tests
        self._write_activation_test(
            "relu_basic",
            data=np.array([0, 1, 5, 10, -1, -5, -10], dtype=np.int8),
            act_type='relu',
            expected=np.array([0, 1, 5, 10, 0, 0, 0], dtype=np.int8)
        )

        # ReLU6 tests
        self._write_activation_test(
            "relu6_basic",
            data=np.array([0, 1, 5, 6, 7, -1, -5], dtype=np.int8),
            act_type='relu6',
            expected=np.array([0, 1, 5, 6, 6, 0, 0], dtype=np.int8)
        )

        # Sigmoid tests (piecewise linear)
        self._write_activation_test(
            "sigmoid_basic",
            data=np.array([-64, -32, 0, 32, 64], dtype=np.int8),
            act_type='sigmoid',
            expected=np.array([0, 32, 128, 224, 255], dtype=np.uint8)
        )

    def _write_activation_test(self, name: str, data: np.ndarray,
                              act_type: str, expected: np.ndarray):
        """Write activation test vector"""
        base_path = os.path.join(self.output_dir, name)

        with open(f"{base_path}_input.bin", 'wb') as f:
            data.tofile(f)

        with open(f"{base_path}_expected.bin", 'wb') as f:
            expected.tofile(f)

        metadata = {
            'name': name,
            'act_type': act_type,
            'data_shape': list(data.shape),
            'test_type': 'activation'
        }
        with open(f"{base_path}_meta.json", 'w') as f:
            json.dump(metadata, f, indent=2)

    # =========================================================================
    # Layer Tests
    # =========================================================================

    def generate_layer_tests(self):
        """Test vectors for complete layers"""
        print("  Layer tests...")

        # Dense layer test
        self._write_layer_test(
            "dense_layer",
            layer_type='dense',
            input_data=np.random.randint(-128, 128, 32).astype(np.int8),
            weights=np.random.randint(-128, 128, (16, 32)).astype(np.int8),
            bias=np.random.randint(-1000, 1000, 16).astype(np.int32)
        )

        # Depthwise separable convolution
        self._write_ds_cnn_test(
            "depthwise_sep_conv",
            input_shape=(1, 49, 40),
            kernel_size=3,
            in_channels=16,
            out_channels=32
        )

        # Pooling test
        self._write_pool_test(
            "max_pool",
            pool_type='max',
            input_data=np.random.randint(0, 256, (1, 8, 8)).astype(np.uint8),
            pool_size=2
        )

    def _write_layer_test(self, name: str, layer_type: str,
                         input_data: np.ndarray, weights: np.ndarray,
                         bias: np.ndarray):
        """Write layer test vector"""
        base_path = os.path.join(self.output_dir, name)

        input_data.tofile(f"{base_path}_input.bin")
        weights.tofile(f"{base_path}_weights.bin")
        bias.tofile(f"{base_path}_bias.bin")

        # Compute expected output
        output = np.dot(weights.astype(np.int32), input_data.astype(np.int32)) + bias

        output.tofile(f"{base_path}_expected.bin")

        metadata = {
            'name': name,
            'layer_type': layer_type,
            'input_shape': list(input_data.shape),
            'weight_shape': list(weights.shape),
            'bias_shape': list(bias.shape),
            'output_shape': list(output.shape),
            'test_type': 'layer'
        }
        with open(f"{base_path}_meta.json", 'w') as f:
            json.dump(metadata, f, indent=2)

    def _write_ds_cnn_test(self, name: str, input_shape: Tuple,
                          kernel_size: int, in_channels: int,
                          out_channels: int):
        """Write depthwise separable CNN test"""
        base_path = os.path.join(self.output_dir, name)

        # Generate input
        input_data = np.random.randint(0, 256, input_shape).astype(np.uint8)
        input_data.tofile(f"{base_path}_input.bin")

        # Generate depthwise weights (ch, kh, kw)
        dw_weights = np.random.randint(-128, 128,
            (in_channels, kernel_size, kernel_size)).astype(np.int8)
        dw_weights.tofile(f"{base_path}_dw_weights.bin")

        # Generate pointwise weights (out_ch, in_ch)
        pw_weights = np.random.randint(-128, 128,
            (out_channels, in_channels)).astype(np.int8)
        pw_weights.tofile(f"{base_path}_pw_weights.bin")

        metadata = {
            'name': name,
            'input_shape': list(input_shape),
            'kernel_size': kernel_size,
            'in_channels': in_channels,
            'out_channels': out_channels,
            'test_type': 'ds_cnn'
        }
        with open(f"{base_path}_meta.json", 'w') as f:
            json.dump(metadata, f, indent=2)

    def _write_pool_test(self, name: str, pool_type: str,
                        input_data: np.ndarray, pool_size: int):
        """Write pooling test"""
        base_path = os.path.join(self.output_dir, name)

        input_data.tofile(f"{base_path}_input.bin")

        # Compute expected output
        if pool_type == 'max':
            h, w = input_data.shape
            out_h, out_w = h // pool_size, w // pool_size
            expected = np.zeros((out_h, out_w), dtype=input_data.dtype)
            for i in range(out_h):
                for j in range(out_w):
                    window = input_data[i*pool_size:(i+1)*pool_size,
                                      j*pool_size:(j+1)*pool_size]
                    expected[i, j] = np.max(window)
        else:
            expected = input_data

        expected.tofile(f"{base_path}_expected.bin")

        metadata = {
            'name': name,
            'pool_type': pool_type,
            'pool_size': pool_size,
            'input_shape': list(input_data.shape),
            'output_shape': list(expected.shape),
            'test_type': 'pooling'
        }
        with open(f"{base_path}_meta.json", 'w') as f:
            json.dump(metadata, f, indent=2)

    # =========================================================================
    # APB Interface Tests
    # =========================================================================

    def generate_apb_tests(self):
        """Test vectors for APB interface"""
        print("  APB interface tests...")

        # APB Write test
        self._write_apb_test(
            "apb_write",
            transactions=[
                {'addr': 0x00, 'data': 0x00000001, 'type': 'write'},  # Start
                {'addr': 0x08, 'data': 0x00000000, 'type': 'write'},  # Layer type
                {'addr': 0x0C, 'data': 0x31000008, 'type': 'write'},  # Input dims
                {'addr': 0x10, 'data': 0x00000010, 'type': 'write'},  # Output channels
            ]
        )

        # APB Read test
        self._write_apb_test(
            "apb_read",
            transactions=[
                {'addr': 0x04, 'data': 0x00000001, 'type': 'read'},   # Status
                {'addr': 0x04, 'data': 0x00000006, 'type': 'read'},   # Status (busy)
            ]
        )

        # APB Write-Read test
        self._write_apb_test(
            "apb_write_read",
            transactions=[
                {'addr': 0x08, 'data': 0x00000001, 'type': 'write'},  # Write layer type
                {'addr': 0x08, 'data': 0x00000001, 'type': 'read'},   # Read back
            ]
        )

    def _write_apb_test(self, name: str, transactions: List[Dict]):
        """Write APB test vector"""
        base_path = os.path.join(self.output_dir, name)

        # Write transactions
        with open(f"{base_path}_transactions.bin", 'wb') as f:
            for t in transactions:
                # Pack as: addr(32) | data(32) | type(8) | valid(8)
                valid = 1 if t['type'] in ['write', 'read'] else 0
                t_byte = 1 if t['type'] == 'write' else 0
                f.write(struct.pack('<I', t['addr']))
                f.write(struct.pack('<I', t['data']))
                f.write(struct.pack('<B', t_byte))
                f.write(struct.pack('<B', valid))

        metadata = {
            'name': name,
            'num_transactions': len(transactions),
            'test_type': 'apb'
        }
        with open(f"{base_path}_meta.json", 'w') as f:
            json.dump(metadata, f, indent=2)

    # =========================================================================
    # AXI-Stream Tests
    # =========================================================================

    def generate_axi_stream_tests(self):
        """Test vectors for AXI-Stream interface"""
        print("  AXI-Stream tests...")

        # Input stream test
        self._write_axis_test(
            "axis_input",
            data=np.random.randint(0, 256, 100).astype(np.uint8),
            tlast_positions=[99]  # Last at position 99
        )

        # Multi-packet test
        self._write_axis_test(
            "axis_multi_packet",
            data=np.random.randint(0, 256, 300).astype(np.uint8),
            tlast_positions=[99, 199, 299]
        )

        # Single word test
        self._write_axis_test(
            "axis_single",
            data=np.array([42], dtype=np.uint8),
            tlast_positions=[0]
        )

    def _write_axis_test(self, name: str, data: np.ndarray,
                        tlast_positions: List[int]):
        """Write AXI-Stream test"""
        base_path = os.path.join(self.output_dir, name)

        # Write data
        data.tofile(f"{base_path}_data.bin")

        # Write tlast positions
        with open(f"{base_path}_tlast.bin", 'wb') as f:
            for i in range(len(data)):
                tlast = 1 if i in tlast_positions else 0
                f.write(struct.pack('<B', tlast))

        metadata = {
            'name': name,
            'num_words': len(data),
            'tlast_positions': tlast_positions,
            'test_type': 'axi_stream'
        }
        with open(f"{base_path}_meta.json", 'w') as f:
            json.dump(metadata, f, indent=2)

    # =========================================================================
    # System Tests
    # =========================================================================

    def generate_system_tests(self):
        """End-to-end system tests"""
        print("  System tests...")

        # End-to-end inference test
        self._write_system_test(
            "system_inference",
            input_data=np.random.randint(0, 256, (1, 49, 40)).astype(np.uint8),
            expected_output_class=5
        )

        # Complete layer sequence test
        self._write_layer_sequence_test(
            "system_layer_sequence",
            num_layers=3
        )

    def _write_system_test(self, name: str, input_data: np.ndarray,
                          expected_output_class: int):
        """Write system test vector"""
        base_path = os.path.join(self.output_dir, name)

        input_data.tofile(f"{base_path}_input.bin")

        metadata = {
            'name': name,
            'input_shape': list(input_data.shape),
            'expected_output_class': expected_output_class,
            'test_type': 'system'
        }
        with open(f"{base_path}_meta.json", 'w') as f:
            json.dump(metadata, f, indent=2)

    def _write_layer_sequence_test(self, name: str, num_layers: int):
        """Write layer sequence test"""
        base_path = os.path.join(self.output_dir, name)

        # Generate layer configurations
        layers = []
        for i in range(num_layers):
            layer = {
                'index': i,
                'type': ['conv', 'dense', 'pool', 'act'][i % 4],
                'config': {
                    'channels': [16, 32, 64, 32][i % 4],
                    'activation': 'relu' if i % 4 != 3 else 'none'
                }
            }
            layers.append(layer)

        with open(f"{base_path}_layers.json", 'w') as f:
            json.dump(layers, f, indent=2)

        metadata = {
            'name': name,
            'num_layers': num_layers,
            'test_type': 'layer_sequence'
        }
        with open(f"{base_path}_meta.json", 'w') as f:
            json.dump(metadata, f, indent=2)


# ============================================================================
# Test Vector Reader for RTL
# ============================================================================

class TestVectorReader:
    """Read test vectors for RTL simulation"""

    @staticmethod
    def read_imc_test(name: str, test_dir: str = "./test_vectors") -> Dict:
        """Read IMC test vector"""
        base = os.path.join(test_dir, name)

        weights = np.fromfile(f"{base}_weights.bin", dtype=np.int8)
        inputs = np.fromfile(f"{base}_input.bin", dtype=np.uint8)
        expected = np.fromfile(f"{base}_expected.bin", dtype=np.int32)

        with open(f"{base}_meta.json", 'r') as f:
            metadata = json.load(f)

        return {
            'weights': weights,
            'inputs': inputs,
            'expected': expected,
            'metadata': metadata
        }

    @staticmethod
    def read_all_tests(test_dir: str = "./test_vectors") -> List[Dict]:
        """Read all test vectors"""
        tests = []
        for name in os.listdir(test_dir):
            if name.endswith('_meta.json'):
                test_name = name.replace('_meta.json', '')
                meta_path = os.path.join(test_dir, name)
                with open(meta_path, 'r') as f:
                    metadata = json.load(f)
                tests.append({
                    'name': test_name,
                    'metadata': metadata
                })
        return tests


# ============================================================================
# Verilog Testbench Generator
# ============================================================================

class VerilogTBGenerator:
    """Generate Verilog testbench from test vectors"""

    @staticmethod
    def generate_tb(test_dir: str = "./test_vectors",
                   output_file: str = "tv_stimulus.v"):
        """Generate Verilog test stimulus module"""

        tests = TestVectorReader.read_all_tests(test_dir)

        verilog = """
// ============================================================================
// Test Vector Stimulus for IMC-TinyML
// Auto-generated from Python test vectors
// ============================================================================

module tv_stimulus;

// ============================================================================
// Test Count
// ============================================================================
localparam NUM_TESTS = {num_tests};

// ============================================================================
// Test Data (loaded from memory)
// ============================================================================
""".format(num_tests=len(tests))

        # Generate test data arrays for each test
        for i, test in enumerate(tests):
            meta = test['metadata']
            test_type = meta.get('test_type', 'unknown')

            verilog += f"""
// Test {i}: {test['name']} ({test_type})
// Shape: {meta.get('weight_shape', meta.get('input_shape', 'N/A'))}
reg [7:0] test_{i}_data [0:255];
"""

        verilog += """

// ============================================================================
// Test Selection
// ============================================================================
reg [7:0] test_sel;

// ============================================================================
// Main
// ============================================================================
initial begin
    $display("Loading test vectors...");

"""

        for i, test in enumerate(tests):
            verilog += f"""
    // Load test {i}: {test['name']}
    $display("  Loading {test['name']}...");
"""

        verilog += """
    $display("Test vectors loaded.");
end

endmodule // tv_stimulus
"""

        with open(os.path.join(test_dir, output_file), 'w') as f:
            f.write(verilog)

        print(f"Verilog testbench generated: {output_file}")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='IMC-TinyML Test Vector Generator')
    parser.add_argument('--output', '-o', type=str, default='./test_vectors',
                       help='Output directory')
    parser.add_argument('--generate-tb', action='store_true',
                       help='Generate Verilog testbench')
    args = parser.parse_args()

    print("=" * 60)
    print("IMC-TinyML Test Vector Generator")
    print("=" * 60)
    print()

    # Generate test vectors
    generator = TestVectorGenerator(args.output)
    generator.generate_all()

    # Generate Verilog testbench
    if args.generate_tb:
        VerilogTBGenerator.generate_tb(args.output)

    # List generated files
    print("\nGenerated files:")
    for f in sorted(os.listdir(args.output)):
        size = os.path.getsize(os.path.join(args.output, f))
        print(f"  {f}: {size:,} bytes")

    print("\n" + "=" * 60)
    print("Generation complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
