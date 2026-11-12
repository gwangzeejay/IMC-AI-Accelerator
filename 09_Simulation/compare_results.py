#!/usr/bin/env python3
# ============================================================================
# IMC-TinyML RTL vs Python Comparison Script
# ============================================================================
#
# Compares RTL simulation results with Python behavioral simulation
# Generates detailed report with mismatch analysis
#
# ============================================================================

import os
import sys
import argparse
import numpy as np
import json
import struct
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any
from datetime import datetime
import hashlib

# ============================================================================
# Configuration
# ============================================================================

@dataclass
class CompareConfig:
    """Configuration for comparison"""
    tolerance_percent: float = 1.0      # Percentage tolerance for floating point
    tolerance_absolute: float = 1e-6   # Absolute tolerance for fixed point
    verbose: bool = False
    generate_report: bool = True
    report_format: str = "text"         # "text", "html", "json"
    output_dir: str = "./comparison"
    log_failures: bool = True
    max_mismatches_shown: int = 20


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class TestResult:
    """Result from one test"""
    name: str
    passed: bool
    input_data: np.ndarray = None
    expected_data: np.ndarray = None
    actual_data: np.ndarray = None
    mismatches: List[Dict] = field(default_factory=list)
    error_message: str = ""
    execution_time: float = 0.0
    metadata: Dict = field(default_factory=dict)


@dataclass
class ComparisonResult:
    """Result of comparison"""
    test_name: str
    passed: bool
    num_tests: int = 0
    num_passed: int = 0
    num_failed: int = 0
    max_error: float = 0.0
    avg_error: float = 0.0
    total_cycles: int = 0
    mismatches: List[Dict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    test_results: List[TestResult] = field(default_factory=list)


# ============================================================================
# Data Loader Classes
# ============================================================================

class RTLResultLoader:
    """Load results from RTL simulation"""

    @staticmethod
    def load_vcd_summary(filepath: str) -> Optional[Dict]:
        """Load summary from VCD analysis (placeholder)"""
        if not os.path.exists(filepath):
            return None

        # In practice, would parse VCD file
        # For now, return simulated results
        return {
            'file': filepath,
            'timestamp': datetime.now().isoformat(),
            'status': 'completed'
        }

    @staticmethod
    def load_sim_log(filepath: str) -> Dict:
        """Parse simulation log file"""
        results = {
            'tests': [],
            'passed': 0,
            'failed': 0,
            'total_cycles': 0
        }

        if not os.path.exists(filepath):
            return results

        with open(filepath, 'r') as f:
            content = f.read()

            # Parse test results
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if '[TEST' in line:
                    # Extract test info
                    test_name = line.strip()

                    # Look for result
                    for j in range(i+1, min(i+10, len(lines))):
                        if 'PASSED' in lines[j]:
                            results['tests'].append({
                                'name': test_name,
                                'passed': True
                            })
                            results['passed'] += 1
                            break
                        elif 'FAILED' in lines[j]:
                            results['tests'].append({
                                'name': test_name,
                                'passed': False,
                                'reason': lines[j]
                            })
                            results['failed'] += 1
                            break

        return results

    @staticmethod
    def load_binary_output(filepath: str) -> Optional[np.ndarray]:
        """Load binary output data from RTL"""
        if not os.path.exists(filepath):
            return None

        try:
            data = np.fromfile(filepath, dtype=np.int32)
            return data
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
            return None

    @staticmethod
    def load_json_output(filepath: str) -> Optional[Dict]:
        """Load JSON output from RTL"""
        if not os.path.exists(filepath):
            return None

        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
            return None


class PythonResultLoader:
    """Load results from Python simulation"""

    @staticmethod
    def load_simulation_output(filepath: str) -> Dict:
        """Load Python simulation output"""
        if not os.path.exists(filepath):
            return {}

        with open(filepath, 'r') as f:
            content = f.read()

        # Parse simulation output
        results = {
            'layers': [],
            'output': None,
            'stats': {},
            'errors': []
        }

        lines = content.split('\n')
        for line in lines:
            if 'Output shape:' in line:
                # Extract shape
                pass
            elif 'Output range:' in line:
                # Extract range
                pass

        return results

    @staticmethod
    def load_numpy_output(filepath: str) -> Optional[np.ndarray]:
        """Load numpy output file"""
        if not os.path.exists(filepath):
            return None

        try:
            return np.load(filepath)
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
            return None

    @staticmethod
    def load_test_vector(filepath: str) -> Optional[Dict]:
        """Load test vector metadata"""
        if not os.path.exists(filepath):
            return None

        with open(filepath, 'r') as f:
            return json.load(f)


# ============================================================================
# Comparison Engine
# ============================================================================

class ComparisonEngine:
    """Compare RTL and Python simulation results"""

    def __init__(self, config: CompareConfig = None):
        self.config = config or CompareConfig()
        self.results = []

    def compare_arrays(self, expected: np.ndarray, actual: np.ndarray,
                     name: str = "comparison") -> Tuple[bool, List[Dict]]:
        """
        Compare two numpy arrays element-wise

        Returns:
            Tuple of (passed, mismatches)
        """
        mismatches = []

        # Handle shape mismatch
        if expected.shape != actual.shape:
            mismatches.append({
                'index': 'N/A',
                'expected': 'N/A',
                'actual': 'N/A',
                'error': 'Shape mismatch',
                'expected_shape': str(expected.shape),
                'actual_shape': str(actual.shape)
            })
            return False, mismatches

        # Element-wise comparison
        if np.issubdtype(expected.dtype, np.integer):
            # Integer comparison
            diff = np.abs(expected.astype(np.int64) - actual.astype(np.int64))
            max_diff = np.max(diff)

            # Find mismatches
            mismatch_mask = diff > 0
            mismatch_indices = np.where(mismatch_mask)[0]

            for idx in mismatch_indices[:self.config.max_mismatches_shown]:
                mismatches.append({
                    'index': int(idx),
                    'expected': int(expected.flat[idx]),
                    'actual': int(actual.flat[idx]),
                    'error': int(diff.flat[idx]),
                    'error_percent': float(diff.flat[idx] / max(abs(expected.flat[idx]), 1) * 100)
                    if expected.flat[idx] != 0 else 0
                })

            passed = max_diff == 0

        else:
            # Floating point comparison
            abs_diff = np.abs(expected - actual)
            rel_diff = np.where(expected != 0,
                               abs_diff / np.abs(expected),
                               abs_diff)

            max_rel_error = np.max(rel_diff) * 100

            # Find mismatches
            tolerance = max(self.config.tolerance_percent,
                          self.config.tolerance_absolute)

            mismatch_mask = rel_diff * 100 > tolerance
            mismatch_indices = np.where(mismatch_mask)[0]

            for idx in mismatch_indices[:self.config.max_mismatches_shown]:
                mismatches.append({
                    'index': int(idx),
                    'expected': float(expected.flat[idx]),
                    'actual': float(actual.flat[idx]),
                    'error': float(abs_diff.flat[idx]),
                    'error_percent': float(rel_diff.flat[idx] * 100)
                })

            passed = max_rel_error <= self.config.tolerance_percent

        return passed, mismatches

    def compare_files(self, rtl_file: str, python_file: str,
                     test_name: str = "test") -> TestResult:
        """Compare RTL output with Python output"""
        result = TestResult(name=test_name, passed=False)

        # Load RTL output
        rtl_data = RTLResultLoader.load_binary_output(rtl_file)
        if rtl_data is None:
            result.error_message = f"RTL file not found: {rtl_file}"
            return result

        # Load Python output
        python_data = PythonResultLoader.load_numpy_output(python_file)
        if python_data is None:
            result.error_message = f"Python file not found: {python_file}"
            return result

        result.input_data = python_data
        result.expected_data = python_data
        result.actual_data = rtl_data

        # Compare
        passed, mismatches = self.compare_arrays(
            python_data.flatten(),
            rtl_data.flatten(),
            test_name
        )

        result.passed = passed
        result.mismatches = mismatches

        if not passed and len(mismatches) > 0:
            result.error_message = f"{len(mismatches)} mismatches found"

        return result

    def run_comparison(self, rtl_dir: str, python_dir: str,
                      test_list: List[str] = None) -> ComparisonResult:
        """Run comparison on a set of tests"""

        result = ComparisonResult(
            test_name="RTL vs Python Comparison",
            passed=True
        )

        # Find test files
        if test_list is None:
            test_list = []

            # Scan directories for matching files
            if os.path.exists(rtl_dir):
                for f in os.listdir(rtl_dir):
                    if f.endswith('_output.bin'):
                        test_name = f.replace('_output.bin', '')
                        test_list.append(test_name)

        # Compare each test
        for test_name in test_list:
            rtl_file = os.path.join(rtl_dir, f"{test_name}_output.bin")
            python_file = os.path.join(python_dir, f"{test_name}_output.npy")

            test_result = self.compare_files(rtl_file, python_file, test_name)
            result.test_results.append(test_result)

            if test_result.passed:
                result.num_passed += 1
            else:
                result.num_failed += 1
                result.mismatches.extend(test_result.mismatches)
                if test_result.error_message:
                    result.errors.append(test_result.error_message)

            result.num_tests += 1

        result.passed = result.num_failed == 0

        # Calculate statistics
        if result.mismatches:
            errors = [m['error'] for m in result.mismatches
                     if isinstance(m['error'], (int, float))]
            if errors:
                result.max_error = max(errors)
                result.avg_error = sum(errors) / len(errors)

        return result


# ============================================================================
# Report Generator
# ============================================================================

class ReportGenerator:
    """Generate comparison reports"""

    def __init__(self, config: CompareConfig = None):
        self.config = config or CompareConfig()

    def generate_text_report(self, result: ComparisonResult) -> str:
        """Generate text format report"""

        lines = []
        lines.append("=" * 70)
        lines.append("IMC-TinyML RTL vs Python Comparison Report")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # Summary
        lines.append("-" * 70)
        lines.append("SUMMARY")
        lines.append("-" * 70)
        lines.append(f"  Total Tests:  {result.num_tests}")
        lines.append(f"  Passed:       {result.num_passed}")
        lines.append(f"  Failed:       {result.num_failed}")
        lines.append(f"  Pass Rate:    {result.num_passed / max(result.num_tests, 1) * 100:.1f}%")
        lines.append("")

        if result.mismatches:
            lines.append(f"  Max Error:    {result.max_error}")
            lines.append(f"  Avg Error:    {result.avg_error:.6f}")
        lines.append("")

        # Test Details
        lines.append("-" * 70)
        lines.append("TEST DETAILS")
        lines.append("-" * 70)

        for test in result.test_results:
            status = "PASS" if test.passed else "FAIL"
            lines.append(f"  [{status}] {test.name}")

            if not test.passed and test.mismatches:
                lines.append(f"    Mismatches: {len(test.mismatches)}")
                for m in test.mismatches[:5]:
                    lines.append(
                        f"      Index {m['index']}: "
                        f"expected={m['expected']}, "
                        f"actual={m['actual']}, "
                        f"error={m['error']}"
                    )
                    if 'error_percent' in m:
                        lines.append(f"        ({m['error_percent']:.2f}%)")

            if test.error_message:
                lines.append(f"    Error: {test.error_message}")

        lines.append("")

        # Errors
        if result.errors:
            lines.append("-" * 70)
            lines.append("ERRORS")
            lines.append("-" * 70)
            for i, err in enumerate(result.errors[:10], 1):
                lines.append(f"  {i}. {err}")
            lines.append("")

        # Conclusion
        lines.append("=" * 70)
        if result.passed:
            lines.append("RESULT: ALL TESTS PASSED")
        else:
            lines.append(f"RESULT: {result.num_failed} TEST(S) FAILED")
        lines.append("=" * 70)

        return "\n".join(lines)

    def generate_json_report(self, result: ComparisonResult) -> str:
        """Generate JSON format report"""

        report = {
            'metadata': {
                'generated': datetime.now().isoformat(),
                'tool': 'IMC-TinyML Comparison Tool',
                'version': '1.0'
            },
            'summary': {
                'total_tests': result.num_tests,
                'passed': result.num_passed,
                'failed': result.num_failed,
                'pass_rate': result.num_passed / max(result.num_tests, 1),
                'max_error': result.max_error,
                'avg_error': result.avg_error,
                'passed': result.passed
            },
            'tests': []
        }

        for test in result.test_results:
            test_data = {
                'name': test.name,
                'passed': test.passed,
                'error_message': test.error_message,
                'num_mismatches': len(test.mismatches)
            }

            if test.mismatches:
                test_data['sample_mismatches'] = test.mismatches[:10]

            report['tests'].append(test_data)

        return json.dumps(report, indent=2)

    def generate_html_report(self, result: ComparisonResult) -> str:
        """Generate HTML format report"""

        html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>IMC-TinyML Comparison Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { color: #333; }
        .summary { background: #f5f5f5; padding: 20px; border-radius: 5px; }
        .pass { color: green; }
        .fail { color: red; }
        table { border-collapse: collapse; width: 100%; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #4CAF50; color: white; }
        tr:nth-child(even) { background-color: #f2f2f2; }
        .mismatch { font-family: monospace; font-size: 0.9em; }
    </style>
</head>
<body>
    <h1>IMC-TinyML RTL vs Python Comparison Report</h1>
    <p>Generated: {timestamp}</p>

    <div class="summary">
        <h2>Summary</h2>
        <p>Total Tests: {total}</p>
        <p class="pass">Passed: {passed}</p>
        <p class="fail">Failed: {failed}</p>
        <p>Pass Rate: {rate:.1f}%</p>
        {error_stats}
    </div>

    <h2>Test Details</h2>
    <table>
        <tr>
            <th>Test Name</th>
            <th>Status</th>
            <th>Mismatches</th>
            <th>Details</th>
        </tr>
        {test_rows}
    </table>

    {conclusion}

</body>
</html>
""".format(
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            total=result.num_tests,
            passed=result.num_passed,
            failed=result.num_failed,
            rate=result.num_passed / max(result.num_tests, 1) * 100,
            error_stats=f"<p>Max Error: {result.max_error}<br>Avg Error: {result.avg_error:.6f}</p>"
                       if result.mismatches else "",
            test_rows=self._generate_test_rows(result),
            conclusion=self._generate_conclusion(result)
        )

        return html

    def _generate_test_rows(self, result: ComparisonResult) -> str:
        """Generate HTML table rows for tests"""
        rows = []
        for test in result.test_results:
            status_class = "pass" if test.passed else "fail"
            status_text = "PASS" if test.passed else "FAIL"

            details = ""
            if test.mismatches:
                details = f"<div class='mismatch'>"
                for m in test.mismatches[:3]:
                    details += f"Index {m['index']}: {m['expected']} vs {m['actual']}<br>"
                details += "</div>"

            rows.append(f"""
                <tr>
                    <td>{test.name}</td>
                    <td class="{status_class}">{status_text}</td>
                    <td>{len(test.mismatches)}</td>
                    <td>{details}{test.error_message or ''}</td>
                </tr>
            """)

        return "".join(rows)

    def _generate_conclusion(self, result: ComparisonResult) -> str:
        """Generate HTML conclusion"""
        if result.passed:
            return """
    <div class="summary" style="background: #d4edda;">
        <h2 class="pass">RESULT: ALL TESTS PASSED</h2>
        <p>RTL and Python simulation results match within tolerance.</p>
    </div>
"""
        else:
            return f"""
    <div class="summary" style="background: #f8d7da;">
        <h2 class="fail">RESULT: {result.num_failed} TEST(S) FAILED</h2>
        <p>RTL and Python simulation results do not match.</p>
    </div>
"""

    def save_report(self, result: ComparisonResult, output_path: str):
        """Save report to file"""

        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

        if self.config.report_format == 'json':
            content = self.generate_json_report(result)
        elif self.config.report_format == 'html':
            content = self.generate_html_report(result)
        else:
            content = self.generate_text_report(result)

        with open(output_path, 'w') as f:
            f.write(content)

        print(f"Report saved: {output_path}")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='IMC-TinyML RTL vs Python Comparison'
    )
    parser.add_argument('--rtl-dir', '-r', type=str,
                       default='./output/rtl',
                       help='RTL simulation output directory')
    parser.add_argument('--python-dir', '-p', type=str,
                       default='./output/python',
                       help='Python simulation output directory')
    parser.add_argument('--output', '-o', type=str,
                       default='./comparison/report.txt',
                       help='Output report path')
    parser.add_argument('--format', '-f', type=str,
                       choices=['text', 'json', 'html'],
                       default='text',
                       help='Report format')
    parser.add_argument('--tolerance', '-t', type=float,
                       default=1.0,
                       help='Tolerance percentage for comparison')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    parser.add_argument('--tests', nargs='+',
                       help='Specific tests to compare')
    args = parser.parse_args()

    print("=" * 70)
    print("IMC-TinyML RTL vs Python Comparison")
    print("=" * 70)
    print()

    # Configure
    config = CompareConfig(
        tolerance_percent=args.tolerance,
        verbose=args.verbose,
        report_format=args.format,
        output_dir=os.path.dirname(args.output) or '.'
    )

    # Run comparison
    engine = ComparisonEngine(config)
    result = engine.run_comparison(
        args.rtl_dir,
        args.python_dir,
        args.tests
    )

    # Generate report
    generator = ReportGenerator(config)
    generator.save_report(result, args.output)

    # Print summary
    print()
    print(result)

    # Exit code
    sys.exit(0 if result.passed else 1)


if __name__ == '__main__':
    main()
