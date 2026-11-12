# ============================================================================
# IMC-TinyML FPGA Implementation Script
# Vivado TCL Script for Xilinx Artix-7
# ============================================================================
#
# This script implements the IMC-TinyML accelerator on Xilinx Artix-7 FPGA
# For simulation and prototyping before ASIC tape-out
#
# ============================================================================

# ============================================================================
# TCL Script Configuration
# ============================================================================

# Design parameters
set project_name "imc_tinyml_accelerator"
set top_module "tinyml_accelerator"
set target_part "xc7a35t-cpg236-1"
set target_device "xc7a35t"

# Clock settings
set system_clock "clk"
set system_clock_period 10.0
set system_clock_frequency [expr 1000.0 / $system_clock_period]

# ============================================================================
# Project Setup
# ============================================================================

puts "\n========================================"
puts "  IMC-TinyML FPGA Implementation"
puts "  Xilinx Vivado TCL Script"
puts "========================================\n"

puts "Configuration:"
puts "  Project: $project_name"
puts "  Top Module: $top_module"
puts "  Target Part: $target_part"
puts "  Clock Period: $system_clock_period ns"
puts "  Clock Frequency: $system_clock_frequency MHz\n"

# Clean up previous runs
file delete -force .runs
file delete -force .cache
file delete -force .hw
file delete -force .ip_user_files

# Create project
puts "Creating Vivado project..."
create_project -force $project_name ./vivado_proj -part $target_part

# Set project properties
set_property target_language Verilog [current_project]
set_property simulator_language Mixed [current_project]
set_property default_lib work [current_project]

# ============================================================================
# Source Files
# ============================================================================

puts "\nAdding source files..."

# RTL sources
set source_files {
    "../../04_RTL/tinyml_accelerator.v"
    "../../04_RTL/imc_array.v"
    "../../04_RTL/imc_activation.v"
    "../../04_RTL/imc_apb_if.v"
}

foreach src $source_files {
    if {[file exists $src]} {
        add_files -norecurse $src
        puts "  Added: $src"
    } else {
        puts "  WARNING: File not found: $src"
    }
}

# Add include files if any
# set_property include_dirs {../../04_RTL} [current_fileset]

# ============================================================================
# Constraint Files
# ============================================================================

puts "\nAdding constraint files..."

# Timing constraints
set_property used_in_synthesis true ./constraints/timing.xdc
set_property used_in_implementation true ./constraints/timing.xdc

# Pin constraints
set_property used_in_synthesis false ./constraints/pins.xdc
set_property used_in_implementation true ./constraints/pins.xdc

puts "  Added: timing.xdc"
puts "  Added: pins.xdc"

# ============================================================================
# IP Cores
# ============================================================================

puts "\nConfiguring IP cores..."

# Clocking Wizard
puts "  Creating Clocking Wizard IP..."

# Create clocking wizard IP
create_ip -name clk_wiz -module_name clk_wiz_0 -dir ./

# Configure clocking wizard
set_property -dict [list \
    CONFIG.PRIM_IN_FREQ {100.000} \
    CONFIG.PRIM_SOURCE {Single_ended_clock_capable_pin} \
    CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {100.000} \
    CONFIG.CLKOUT2_REQUESTED_OUT_FREQ {200.000} \
    CONFIG.USE_RESET {true} \
    CONFIG.USE_LOCKED {true} \
] [get_ips clk_wiz_0]

# Generate clocking wizard
generate_target {all} [get_ips clk_wiz_0]
create_ip_run [get_ips clk_wiz_0]

# Block RAM
puts "  Creating Block RAM IP..."

# Create dist memory IP for weight storage
create_ip -name dist_mem_gen -module_name weight_dist_mem -dir ./

set_property -dict [list \
    CONFIG.Component_Name {weight_dist_mem} \
    CONFIG.Memory_Type {Single_Port_RAM} \
    CONFIG.Data_Width {8} \
    CONFIG.Address_Width {14} \
    CONFIG.Memory_Size {16384} \
    CONFIG.Output_Latency_1 {true} \
    CONFIG.Register_Outputs {true} \
] [get_ips weight_dist_mem]

generate_target {all} [get_ips weight_dist_mem]
create_ip_run [get_ips weight_dist_mem]

# ============================================================================
# Synthesis
# ============================================================================

puts "\n========================================"
puts "  Starting Synthesis"
puts "========================================\n"

# Set synthesis properties
set_property strategy Flow_PerfOptimized_high [get_runs synth_1]
set_property -dict [list \
    STEPS.SYNTH_DESIGN.ARGS.FANOUT_LIMIT {10} \
    STEPS.SYNTH_DESIGN.ARGS.RETIMING {true} \
] [get_runs synth_1]

# Launch synthesis
launch_runs synth_1 -jobs 4
wait_on_run synth_1

# Check synthesis status
if {[get_property PROGRESS [get_runs synth_1]] != "100%"} {
    puts "\nERROR: Synthesis failed!"
    exit 1
}

if {[get_property STATUS [get_runs synth_1]] != "synth_design Complete!"} {
    puts "\nERROR: Synthesis status not complete!"
    exit 1
}

# Open synthesized design for reports
open_run synth_1

# ============================================================================
# Synthesis Reports
# ============================================================================

puts "\n========================================"
puts "  Synthesis Reports"
puts "========================================\n"

# Resource utilization
puts "\n--- Resource Utilization ---\n"
report_utilization -file ./reports/synthesis_utilization.rpt

# Timing summary
puts "\n--- Timing Summary ---\n"
report_timing_summary -file ./reports/synthesis_timing.rpt

# Clock domain crossings
puts "\n--- Clock Domain Crossings ---\n"
report_cdc -file ./reports/synthesis_cdc.rpt

# ============================================================================
# Implementation
# ============================================================================

puts "\n========================================"
puts "  Starting Implementation"
puts "========================================\n"

# Set implementation properties
set_property strategy Performance_ExplorePostRoutePhysOpt [get_runs impl_1]

# Launch implementation
launch_runs impl_1 -jobs 4
wait_on_run impl_1

# Check implementation status
if {[get_property PROGRESS [get_runs impl_1]] != "100%"} {
    puts "\nERROR: Implementation failed!"
    exit 1
}

# Open implemented design
open_run impl_1

# ============================================================================
# Implementation Reports
# ============================================================================

puts "\n========================================"
puts "  Implementation Reports"
puts "========================================\n"

# Resource utilization (post-implementation)
puts "\n--- Post-Implementation Resource Utilization ---\n"
report_utilization -file ./reports/impl_utilization.rpt
report_utilization -pb ./reports/impl_utilization.pb

# Timing summary (post-implementation)
puts "\n--- Post-Implementation Timing Summary ---\n"
report_timing_summary -file ./reports/impl_timing.rpt
report_timing_summary -pb ./reports/impl_timing.pb

# Power analysis
puts "\n--- Power Analysis ---\n"
report_power -file ./reports/power_analysis.rpt
report_power -pb ./reports/power_analysis.pb

# Critical paths
puts "\n--- Critical Paths ---\n"
report_timing -max_paths 10 -file ./reports/critical_paths.rpt

# Clock skew
puts "\n--- Clock Skew ---\n"
report_clock_networks -file ./reports/clock_networks.rpt

# ============================================================================
# Bitstream Generation
# ============================================================================

puts "\n========================================"
puts "  Generating Bitstream"
puts "========================================\n"

# Launch bitstream generation
launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1

# Check bitstream status
if {[get_property PROGRESS [get_runs impl_1]] != "100%"} {
    puts "\nERROR: Bitstream generation failed!"
    exit 1
}

puts "\nBitstream generated successfully!"
puts "  Location: ./vivado_proj/$project_name.runs/impl_1/$top_module.bit"

# ============================================================================
# Final Summary
# ============================================================================

puts "\n========================================"
puts "  Implementation Complete!"
puts "========================================\n"

puts "Reports generated:"
puts "  ./reports/synthesis_utilization.rpt"
puts "  ./reports/synthesis_timing.rpt"
puts "  ./reports/impl_utilization.rpt"
puts "  ./reports/impl_timing.rpt"
puts "  ./reports/power_analysis.rpt"
puts "  ./reports/critical_paths.rpt"
puts "  ./reports/clock_networks.rpt"

puts "\nBitstream:"
puts "  ./vivado_proj/$project_name.runs/impl_1/$top_module.bit"

# ============================================================================
# Hardware Export
# ============================================================================

puts "\n========================================"
puts "  Exporting to Hardware Manager"
puts "========================================\n"

# Open hardware manager
open_hw
connect_hw_server -url local:3121
current_hw_target [get_hw_targets */xilinx_tcf/Digilent/*/*]

# Open hardware device
open_hw_target
current_hw_device [get_hw_devices $target_device]
set_property PROGRAM.FILE {./vivado_proj/$project_name.runs/impl_1/$top_module.bit} [get_hw_devices $target_device]

puts "\nHardware ready for programming:"
puts "  Device: $target_device"
puts "  Bitstream: $top_module.bit"

# Close project
close_project

puts "\n========================================"
puts "  TCL Script Complete"
puts "========================================\n"

exit 0
