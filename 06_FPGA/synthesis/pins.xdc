# ============================================================================
# Pin Constraints for IMC-TinyML Accelerator
# Xilinx Artix-7 (xc7a35t-cpg236)
# ============================================================================

# ============================================================================
# Clock and Reset
# ============================================================================

# System Clock (100 MHz)
set_property PACKAGE_PIN E3 [get_ports clk]
set_property IOSTANDARD LVCMOS33 [get_ports clk]

# Reset (active low)
set_property PACKAGE_PIN C12 [get_ports rst_n]
set_property IOSTANDARD LVCMOS33 [get_ports rst_n]

# ============================================================================
# APB Interface (Configuration)
# ============================================================================

# Address Bus (32-bit, but we use lower 16 bits)
set_property PACKAGE_PIN J15 [get_ports paddr[0]]
set_property PACKAGE_PIN L16 [get_ports paddr[1]]
set_property PACKAGE_PIN M13 [get_ports paddr[2]]
set_property PACKAGE_PIN R15 [get_ports paddr[3]]
set_property PACKAGE_PIN R17 [get_ports paddr[4]]
set_property PACKAGE_PIN T18 [get_ports paddr[5]]
set_property PACKAGE_PIN U18 [get_ports paddr[6]]
set_property PACKAGE_PIN R13 [get_ports paddr[7]]

# Data Bus (32-bit write)
set_property PACKAGE_PIN T13 [get_ports pwdata[0]]
set_property PACKAGE_PIN H6 [get_ports pwdata[1]]
set_property PACKAGE_PIN U12 [get_ports pwdata[2]]
set_property PACKAGE_PIN U11 [get_ports pwdata[3]]
set_property PACKAGE_PIN V10 [get_ports pwdata[4]]
set_property PACKAGE_PIN T3 [get_ports pwdata[5]]
set_property PACKAGE_PIN R3 [get_ports pwdata[6]]
set_property PACKAGE_PIN T5 [get_ports pwdata[7]]

# Data Bus (32-bit read)
set_property PACKAGE_PIN T4 [get_ports prdata[0]]
set_property PACKAGE_PIN R5 [get_ports prdata[1]]
set_property PACKAGE_PIN T11 [get_ports prdata[2]]
set_property PACKAGE_PIN T10 [get_ports prdata[3]]
set_property PACKAGE_PIN V11 [get_ports prdata[4]]
set_property PACKAGE_PIN V12 [get_ports prdata[5]]
set_property PACKAGE_PIN V14 [get_ports prdata[6]]
set_property PACKAGE_PIN V15 [get_ports prdata[7]]

# APB Control Signals
set_property PACKAGE_PIN T14 [get_ports psel]
set_property PACKAGE_PIN T15 [get_ports penable]
set_property PACKAGE_PIN T16 [get_ports pwrite]
set_property PACKAGE_PIN U13 [get_ports pready]
set_property PACKAGE_PIN U14 [get_ports pslverr]

set_property IOSTANDARD LVCMOS33 [get_ports paddr[*]]
set_property IOSTANDARD LVCMOS33 [get_ports pwdata[*]]
set_property IOSTANDARD LVCMOS33 [get_ports prdata[*]]
set_property IOSTANDARD LVCMOS33 [get_ports psel]
set_property IOSTANDARD LVCMOS33 [get_ports penable]
set_property IOSTANDARD LVCMOS33 [get_ports pwrite]
set_property IOSTANDARD LVCMOS33 [get_ports pready]
set_property IOSTANDARD LVCMOS33 [get_ports pslverr]

# ============================================================================
# AXI-Stream Interface (Data I/O)
# ============================================================================

# Input AXI-Stream
# Valid signal
set_property PACKAGE_PIN U15 [get_ports s_axis_tvalid]
set_property IOSTANDARD LVCMOS33 [get_ports s_axis_tvalid]

# Data (8-bit)
set_property PACKAGE_PIN V17 [get_ports s_axis_tdata[0]]
set_property PACKAGE_PIN V16 [get_ports s_axis_tdata[1]]
set_property PACKAGE_PIN M17 [get_ports s_axis_tdata[2]]
set_property PACKAGE_PIN A18 [get_ports s_axis_tdata[3]]
set_property PACKAGE_PIN B18 [get_ports s_axis_tdata[4]]
set_property PACKAGE_PIN C17 [get_ports s_axis_tdata[5]]
set_property PACKAGE_PIN D18 [get_ports s_axis_tdata[6]]
set_property PACKAGE_PIN E18 [get_ports s_axis_tdata[7]]
set_property IOSTANDARD LVCMOS33 [get_ports s_axis_tdata[*]]

# Ready signal
set_property PACKAGE_PIN D17 [get_ports s_axis_tready]
set_property IOSTANDARD LVCMOS33 [get_ports s_axis_tready]

# Last signal
set_property PACKAGE_PIN E19 [get_ports s_axis_tlast]
set_property IOSTANDARD LVCMOS33 [get_ports s_axis_tlast]

# Output AXI-Stream
# Valid signal
set_property PACKAGE_PIN M18 [get_ports m_axis_tvalid]
set_property IOSTANDARD LVCMOS33 [get_ports m_axis_tvalid]

# Data (8-bit)
set_property PACKAGE_PIN M19 [get_ports m_axis_tdata[0]]
set_property PACKAGE_PIN N17 [get_ports m_axis_tdata[1]]
set_property PACKAGE_PIN N18 [get_ports m_axis_tdata[2]]
set_property PACKAGE_PIN P17 [get_ports m_axis_tdata[3]]
set_property PACKAGE_PIN P18 [get_ports m_axis_tdata[4]]
set_property PACKAGE_PIN R18 [get_ports m_axis_tdata[5]]
set_property PACKAGE_PIN N19 [get_ports m_axis_tdata[6]]
set_property PACKAGE_PIN N20 [get_ports m_axis_tdata[7]]
set_property IOSTANDARD LVCMOS33 [get_ports m_axis_tdata[*]]

# Ready signal
set_property PACKAGE_PIN P19 [get_ports m_axis_tready]
set_property IOSTANDARD LVCMOS33 [get_ports m_axis_tready]

# Last signal
set_property PACKAGE_PIN P20 [get_ports m_axis_tlast]
set_property IOSTANDARD LVCMOS33 [get_ports m_axis_tlast]

# ============================================================================
# Interrupt
# ============================================================================

set_property PACKAGE_PIN H17 [get_ports interrupt]
set_property IOSTANDARD LVCMOS33 [get_ports interrupt]

# ============================================================================
# Debug Interface
# ============================================================================

# State (8-bit LED output for debugging)
set_property PACKAGE_PIN H15 [get_ports dbg_state[0]]
set_property PACKAGE_PIN U15 [get_ports dbg_state[1]]
set_property PACKAGE_PIN L18 [get_ports dbg_state[2]]
set_property PACKAGE_PIN T15 [get_ports dbg_state[3]]
set_property PACKAGE_PIN U8 [get_ports dbg_state[4]]
set_property PACKAGE_PIN R8 [get_ports dbg_state[5]]
set_property PACKAGE_PIN T8 [get_ports dbg_state[6]]
set_property PACKAGE_PIN T10 [get_ports dbg_state[7]]
set_property IOSTANDARD LVCMOS33 [get_ports dbg_state[*]]

# Cycle counter (16-bit, displayed on 7-segment or LED bank)
set_property PACKAGE_PIN J17 [get_ports dbg_cycles[0]]
set_property PACKAGE_PIN H17 [get_ports dbg_cycles[1]]
set_property PACKAGE_PIN K15 [get_ports dbg_cycles[2]]
set_property PACKAGE_PIN J13 [get_ports dbg_cycles[3]]
set_property PACKAGE_PIN N14 [get_ports dbg_cycles[4]]
set_property PACKAGE_PIN R18 [get_ports dbg_cycles[5]]
set_property PACKAGE_PIN V17 [get_ports dbg_cycles[6]]
set_property PACKAGE_PIN U17 [get_ports dbg_cycles[7]]
set_property IOSTANDARD LVCMOS33 [get_ports dbg_cycles[*]]

# Layer counter
set_property PACKAGE_PIN U18 [get_ports dbg_layer_count[0]]
set_property PACKAGE_PIN R13 [get_ports dbg_layer_count[1]]
set_property PACKAGE_PIN T13 [get_ports dbg_layer_count[2]]
set_property PACKAGE_PIN T3 [get_ports dbg_layer_count[3]]
set_property PACKAGE_PIN R3 [get_ports dbg_layer_count[4]]
set_property PACKAGE_PIN T5 [get_ports dbg_layer_count[5]]
set_property PACKAGE_PIN T4 [get_ports dbg_layer_count[6]]
set_property PACKAGE_PIN R5 [get_ports dbg_layer_count[7]]
set_property IOSTANDARD LVCMOS33 [get_ports dbg_layer_count[*]]

# ============================================================================
# IMC Interface (Internal, for monitoring)
# ============================================================================

# Wordline enable (4 bits)
set_property PACKAGE_PIN U11 [get_ports imc_wl_en[0]]
set_property PACKAGE_PIN U12 [get_ports imc_wl_en[1]]
set_property PACKAGE_PIN V10 [get_ports imc_wl_en[2]]
set_property PACKAGE_PIN T3 [get_ports imc_wl_en[3]]
set_property IOSTANDARD LVCMOS33 [get_ports imc_wl_en[*]]

# Bitline precharge (4 bits)
set_property PACKAGE_PIN R3 [get_ports imc_bl_prech[0]]
set_property PACKAGE_PIN T5 [get_ports imc_bl_prech[1]]
set_property PACKAGE_PIN T4 [get_ports imc_bl_prech[2]]
set_property PACKAGE_PIN R5 [get_ports imc_bl_prech[3]]
set_property IOSTANDARD LVCMOS33 [get_ports imc_bl_prech[*]]

# Sense enable (4 bits)
set_property PACKAGE_PIN T11 [get_ports imc_sense_en[0]]
set_property PACKAGE_PIN T10 [get_ports imc_sense_en[1]]
set_property PACKAGE_PIN V11 [get_ports imc_sense_en[2]]
set_property PACKAGE_PIN V12 [get_ports imc_sense_en[3]]
set_property IOSTANDARD LVCMOS33 [get_ports imc_sense_en[*]]

# ============================================================================
# Configuration
# ============================================================================

# Drive strength
set_property DRIVE 8 [get_ports clk]
set_property DRIVE 4 [get_ports interrupt]
set_property DRIVE 4 [get_ports dbg_state[*]]
set_property DRIVE 4 [get_ports imc_wl_en[*]]
set_property DRIVE 4 [get_ports imc_bl_prech[*]]
set_property DRIVE 4 [get_ports imc_sense_en[*]]

# Pull-up/Pull-down
set_property PULLUP true [get_ports rst_n]
set_property PULLDOWN true [get_ports imc_wl_en[*]]

# Slew rate
set_property SLEW FAST [get_ports clk]
set_property SLEW SLOW [get_ports dbg_state[*]]
