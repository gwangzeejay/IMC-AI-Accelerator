#!/bin/bash
# ============================================================================
# IMC-TinyML Verification Script
# ============================================================================
#
# Runs complete verification flow:
# 1. Python simulation
# 2. Test vector generation
# 3. RTL simulation with Verilator
# 4. Result comparison
#
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
RTL_DIR="$PROJECT_DIR/04_RTL"
SIM_DIR="$PROJECT_DIR/09_Simulation"
MODEL_DIR="$PROJECT_DIR/05_Model_Training"
TEST_VECTORS="$SIM_DIR/test_vectors"
OUTPUT_DIR="$SIM_DIR/output"

# ============================================================================
# Helper Functions
# ============================================================================

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

check_command() {
    if command -v "$1" &> /dev/null; then
        print_success "$1 found: $(command -v $1)"
        return 0
    else
        print_error "$1 not found"
        return 1
    fi
}

# ============================================================================
# Pre-flight Checks
# ============================================================================

print_header "Pre-flight Checks"

MISSING_DEPS=0

check_command verilator || MISSING_DEPS=1
check_command python3 || MISSING_DEPS=1
check_command gtkwave || print_warning "gtkwave not found (optional)"

if [ $MISSING_DEPS -eq 1 ]; then
    print_error "Missing dependencies"
    echo "Install with:"
    echo "  Ubuntu/Debian: apt install verilator gtkwave"
    echo "  macOS: brew install verilator gtkwave"
    exit 1
fi

# Create output directories
mkdir -p "$OUTPUT_DIR"
mkdir -p "$TEST_VECTORS"

print_success "Pre-flight checks passed"

# ============================================================================
# Step 1: Python Simulation
# ============================================================================

print_header "Step 1: Python Simulation"

cd "$SIM_DIR"

# Generate test vectors
print_warning "Generating test vectors..."
python3 test_vectors.py --output "$TEST_VECTORS" --generate-tb

if [ $? -eq 0 ]; then
    print_success "Test vectors generated"
else
    print_error "Test vector generation failed"
    exit 1
fi

# Run Python simulator
print_warning "Running Python simulator..."
python3 python_simulator.py --generate --output "$OUTPUT_DIR"

if [ $? -eq 0 ]; then
    print_success "Python simulation complete"
else
    print_error "Python simulation failed"
    exit 1
fi

# ============================================================================
# Step 2: RTL Compilation
# ============================================================================

print_header "Step 2: RTL Compilation with Verilator"

cd "$PROJECT_DIR"

# Source files
RTL_SOURCES="$RTL_DIR/tinyml_accelerator.v \
             $RTL_DIR/imc_array.v \
             $RTL_DIR/imc_activation.v \
             $RTL_DIR/imc_apb_if.v"

TB_SOURCE="$RTL_DIR/tb_imc_accelerator.v"

print_warning "Compiling RTL with Verilator..."

verilator -Wall --trace --cc \
    $RTL_SOURCES \
    $TB_SOURCE \
    -CFLAGS "-O2 -Wall" \
    -LDFLAGS "-lstdc++" \
    --exe \
    -o "$OUTPUT_DIR/Vtb_imc_accelerator" \
    -CFLAGS "-I$RTL_DIR"

if [ $? -eq 0 ]; then
    print_success "RTL compilation successful"
else
    print_error "RTL compilation failed"
    exit 1
fi

# ============================================================================
# Step 3: RTL Simulation
# ============================================================================

print_header "Step 3: RTL Simulation"

cd "$OUTPUT_DIR"

print_warning "Running RTL simulation..."

timeout 300 ./Vtb_imc_accelerator

if [ $? -eq 0 ]; then
    print_success "RTL simulation completed"
else
    print_warning "RTL simulation may have timed out or had errors"
fi

# Check for VCD file
if [ -f "tb_imc_accelerator.vcd" ]; then
    print_success "VCD waveform generated: tb_imc_accelerator.vcd"
    WAVEFORM_SIZE=$(du -h "tb_imc_accelerator.vcd" | cut -f1)
    echo "  Size: $WAVEFORM_SIZE"
else
    print_warning "No VCD file generated"
fi

# ============================================================================
# Step 4: Result Analysis
# ============================================================================

print_header "Step 4: Result Analysis"

# Check simulation log
if [ -f "sim.log" ]; then
    echo ""
    echo "Simulation Log (last 50 lines):"
    echo "----------------------------------------"
    tail -50 sim.log
    echo "----------------------------------------"
fi

# Check for errors
if grep -q "SOME TESTS FAILED" sim.log 2>/dev/null; then
    print_error "Some tests failed"
    FAILED_COUNT=$(grep "Failed:" sim.log | grep -oE '[0-9]+' | tail -1)
    echo "  Failed tests: $FAILED_COUNT"
elif grep -q "ALL TESTS PASSED" sim.log 2>/dev/null; then
    print_success "All tests passed!"
else
    print_warning "Could not determine test results"
fi

# ============================================================================
# Step 5: Waveform Analysis
# ============================================================================

print_header "Step 5: Waveform Analysis"

if [ -f "tb_imc_accelerator.vcd" ]; then
    echo "VCD file available for analysis with GTKWave"
    echo ""
    echo "To view waveforms:"
    echo "  gtkwave tb_imc_accelerator.vcd"
    echo ""
    echo "Or use the Makefile:"
    echo "  make wave"
else
    print_warning "No waveform file available"
fi

# ============================================================================
# Summary
# ============================================================================

print_header "Verification Summary"

echo ""
echo "Generated files:"
echo "  Test vectors: $TEST_VECTORS/"
echo "  Simulation output: $OUTPUT_DIR/"
echo ""

if [ -f "$OUTPUT_DIR/sim.log" ]; then
    PASSED=$(grep "Passed:" "$OUTPUT_DIR/sim.log" | grep -oE '[0-9]+' | tail -1 || echo "0")
    FAILED=$(grep "Failed:" "$OUTPUT_DIR/sim.log" | grep -oE '[0-9]+' | tail -1 || echo "0")
    TOTAL=$(grep "Total Tests:" "$OUTPUT_DIR/sim.log" | grep -oE '[0-9]+' | tail -1 || echo "0")

    echo "Test Results:"
    echo "  Total:  $TOTAL"
    echo "  Passed: $PASSED"
    echo "  Failed: $FAILED"
    echo ""
fi

echo "Next steps:"
echo "  1. View waveforms: gtkwave $OUTPUT_DIR/tb_imc_accelerator.vcd"
echo "  2. Run model training: python3 $MODEL_DIR/train_imc_model.py"
echo "  3. FPGA implementation: vivado -source $PROJECT_DIR/06_FPGA/synthesis/compile.tcl"

echo ""
print_success "Verification script complete!"
echo ""
