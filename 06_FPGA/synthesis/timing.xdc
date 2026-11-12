# ============================================================================
# Timing Constraints for IMC-TinyML Accelerator
# Xilinx XDC Format
# ============================================================================

# ============================================================================
# Clock Constraints
# ============================================================================

# System clock: 100 MHz
create_clock -period 10.000 -name sys_clk [get_ports clk]
set_input_delay -clock sys_clk -min 0.500 [get_ports rst_n]
set_input_delay -clock sys_clk -max 2.000 [get_ports rst_n]

# ============================================================================
# APB Interface Timing
# ============================================================================

# APB signals
set_input_delay -clock sys_clk -min 0.500 -max 3.000 [get_ports paddr[*]]
set_input_delay -clock sys_clk -min 0.500 -max 3.000 [get_ports pwdata[*]]
set_input_delay -clock sys_clk -min 0.500 -max 3.000 [get_ports psel]
set_input_delay -clock sys_clk -min 0.500 -max 3.000 [get_ports penable]
set_input_delay -clock sys_clk -min 0.500 -max 3.000 [get_ports pwrite]

set_output_delay -clock sys_clk -min 0.500 -max 3.000 [get_ports prdata[*]]
set_output_delay -clock sys_clk -min 0.500 -max 3.000 [get_ports pready]
set_output_delay -clock sys_clk -min 0.500 -max 3.000 [get_ports pslverr]

# ============================================================================
# AXI-Stream Interface Timing
# ============================================================================

# Input (slave) AXI-Stream
set_input_delay -clock sys_clk -min 0.200 -max 2.000 [get_ports s_axis_tvalid]
set_input_delay -clock sys_clk -min 0.200 -max 2.000 [get_ports s_axis_tdata[*]]
set_input_delay -clock sys_clk -min 0.200 -max 2.000 [get_ports s_axis_tlast]
set_output_delay -clock sys_clk -min 0.200 -max 2.000 [get_ports s_axis_tready]

# Output (master) AXI-Stream
set_output_delay -clock sys_clk -min 0.200 -max 2.000 [get_ports m_axis_tvalid]
set_output_delay -clock sys_clk -min 0.200 -max 2.000 [get_ports m_axis_tdata[*]]
set_output_delay -clock sys_clk -min 0.200 -max 2.000 [get_ports m_axis_tlast]
set_input_delay -clock sys_clk -min 0.200 -max 2.000 [get_ports m_axis_tready]

# ============================================================================
# Interrupt Signal
# ============================================================================

set_output_delay -clock sys_clk -min 0.100 -max 1.500 [get_ports interrupt]

# ============================================================================
# IMC Interface Timing (Internal)
# ============================================================================

# These are internal timing constraints for the IMC interface
set_false_path -from [get_ports imc_wl_en[*]]
set_false_path -from [get_ports imc_bl_prech[*]]
set_false_path -from [get_ports imc_sense_en[*]]
set_false_path -from [get_ports imc_array_rst[*]]
set_false_path -from [get_ports imc_input_data[*]]

# ============================================================================
# Debug Interface Timing
# ============================================================================

set_false_path -from [get_ports dbg_state[*]]
set_false_path -from [get_ports dbg_cycles[*]]
set_false_path -from [get_ports dbg_layer_count[*]]

# ============================================================================
# Clock Uncertainty (Jitter)
# ============================================================================

set_clock_uncertainty -setup 0.200 [get_clocks sys_clk]
set_clock_uncertainty -hold 0.100 [get_clocks sys_clk]

# ============================================================================
# Input/Output Constraints
# ============================================================================

# Maximum delay for inputs
set_max_delay -from [all_inputs] -to [all_outputs] 15.000

# ============================================================================
# False Paths
# ============================================================================

# Asynchronous reset
set_false_path -from [get_ports rst_n]

# ============================================================================
# Multicycle Paths
# ============================================================================

# Allow extra cycles for AXI-Stream handshaking
set_multicycle_path -setup 2 -from [get_pins s_axis_tvalid_reg/C] -to [get_pins s_axis_tready_reg/D]
set_multicycle_path -hold 1 -from [get_pins s_axis_tvalid_reg/C] -to [get_pins s_axis_tready_reg/D]

set_multicycle_path -setup 2 -from [get_pins m_axis_tvalid_reg/C] -to [get_pins m_axis_tready_reg/D]
set_multicycle_path -hold 1 -from [get_pins m_axis_tvalid_reg/C] -to [get_pins m_axis_tready_reg/D]

# ============================================================================
# Performance Constraints
# ============================================================================

# Target clock frequency: 100 MHz (period: 10 ns)
create_clock -period 10.000 -name imc_clk [get_pins imc_sense_en_reg/C]
set_clock_uncertainty -setup 0.100 [get_clocks imc_clk]
set_clock_uncertainty -hold 0.050 [get_clocks imc_clk]

# ============================================================================
# Area Constraints (Optimization)
# ============================================================================

# No specific area constraints for initial synthesis
# Vivado will optimize automatically based on strategy

# ============================================================================
# Power Optimization
# ============================================================================

# Enable clock gating where applicable
set_property STEPS.OPT_DESIGN.ARGS.ADDER_THRESHOLD_WIDTH 12 [get_runs impl_1]
set_property STEPS.PHYS_OPT_DESIGN.ARGS.INSERT_ASYM_REGULATORS true [get_runs impl_1]
