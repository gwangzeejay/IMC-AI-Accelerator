# ============================================================================
# IMC-TinyML ASIC Implementation - Synopsys Design Compiler
# ============================================================================
#
# RTL to Gate-level synthesis script for TSMC 65nm LP
#
# ============================================================================

# ============================================================================
# Setup
# ============================================================================

puts "\n========================================"
puts "  IMC-TinyML ASIC Synthesis"
puts "  Synopsys Design Compiler"
puts "========================================\n"

# Variables
set design "tinyml_accelerator"
set target_library "tsmc65lp.db"
set link_library "* $target_library"
set search_path "/tools/synopsys/libraries/syn \
                  /tools/synopsys/libraries/tcbn65lpwc \
                  ./rtl"

# Output directories
set synth_dir "./synth"
set reports_dir "./synth/reports"
set results_dir "./synth/results"

file delete -force $synth_dir
file delete -force $reports_dir
file delete -force $results_dir

file mkdir $synth_dir
file mkdir $reports_dir
file mkdir $results_dir

# ============================================================================
# Read Libraries
# ============================================================================

puts "Loading libraries..."
set target_library "tcbn65lpwc/tcbn65lpwc.db"
set link_library "* $target_library"

# Check if library exists
if {![file exists "/tools/synopsys/libraries/tcbn65lpwc/tcbn65lpwc.db"]} {
    puts "WARNING: Target library not found at expected path"
    puts "Using standard cells for estimation"
    set target_library "tsmc65lp.db"
}

# ============================================================================
# Read Design
# ============================================================================

puts "\nReading RTL sources..."

set rtl_files {
    "../../04_RTL/tinyml_accelerator.v"
    "../../04_RTL/imc_array.v"
    "../../04_RTL/imc_activation.v"
    "../../04_RTL/imc_apb_if.v"
}

foreach src $rtl_files {
    if {[file exists $src]} {
        read_verilog $src
        puts "  Read: $src"
    } else {
        puts "  ERROR: File not found: $src"
        exit 1
    }
}

# ============================================================================
# Define Clock
# ============================================================================

puts "\nDefining clock constraints..."

create_clock clk -name sys_clk -period 10.0 -waveform {0 5.0}

# ============================================================================
# SDC Constraints
# ============================================================================

puts "Writing SDC constraints..."

set clock_name sys_clk

# Input delays
set_input_delay 1.0 -clock $clock_name [remove_from_collection [all_inputs] clk]
set_input_delay 1.0 -clock $clock_name [remove_from_collection [all_inputs] rst_n]

# Output delays
set_output_delay 1.0 -clock $clock_name [all_outputs]

# Clock uncertainty (jitter)
set_clock_uncertainty 0.2 [get_clocks $clock_name]

# ============================================================================
# Design Constraints
# ============================================================================

puts "\nSetting design constraints..."

# Set design name
current_design $design
link

# ============================================================================
# Compile Strategy
# ============================================================================

puts "\nSetting compile strategies..."

# High effort for performance
set compile_ultra_options "-no_autoungroup"

# ============================================================================
# Initial Compilation
# ============================================================================

puts "\n========================================"
puts "  Phase 1: Initial Synthesis"
puts "========================================\n"

compile_ultra -gate_clock -exact_byte_delay

# ============================================================================
# Reports - Initial
# ============================================================================

puts "\nGenerating initial reports..."

# Timing Report
report_timing -max_paths 10 > $reports_dir/timing_initial.rpt
report_timing_summary > $reports_dir/timing_summary_initial.rpt

# Area Report
report_area > $reports_dir/area_initial.rpt

# Power Report
report_power > $reports_dir/power_initial.rpt

# Cell Statistics
report_cell > $reports_dir/cells_initial.rpt

# ============================================================================
# Optimization
# ============================================================================

puts "\n========================================"
puts "  Phase 2: Optimization"
puts "========================================\n"

# Ungroup small modules
ungroup -all -flatten

# Re-compile after ungrouping
compile_ultra

# ============================================================================
# Reports - Optimized
# ============================================================================

puts "\nGenerating optimized reports..."

# Timing Report
report_timing -max_paths 20 > $reports_dir/timing_optimized.rpt
report_timing_summary -verbose > $reports_dir/timing_summary_optimized.rpt

# Area Report
report_area -hierarchical > $reports_dir/area_optimized.rpt

# Power Report
report_power -hierarchical > $reports_dir/power_optimized.rpt

# Cell Statistics
report_cell -hier > $reports_dir/cells_optimized.rpt

# Critical Paths
report_criticality -num_paths 30 > $reports_dir/critical_paths.rpt

# ============================================================================
# QoR Summary
# ============================================================================

puts "\n========================================"
puts "  Quality of Results Summary"
puts "========================================\n"

puts "\n--- Timing ---"
set clock_period [get_attribute [get_clocks $clock_name] period]
set slack [get_attribute [get_timing_paths -max_paths 1] slack]
puts "  Clock Period: $clock_period ns"
puts "  Setup Slack:  $slack ns"
puts "  Frequency:    [expr 1000.0 / $clock_period] MHz"

puts "\n--- Area ---"
set total_area [get_attribute [current_design] total_area]
puts "  Total Area: $total_area um^2"
puts "  [expr $total_area / 1000000] mm^2"

puts "\n--- Power ---"
set leakage [get_attribute [current_design] leakage_power]
set dynamic [get_attribute [current_design] dynamic_power]
puts "  Leakage: [expr $leakage * 1000000] nW"
puts "  Dynamic: [expr $dynamic * 1000000] nW"

# ============================================================================
# Export Results
# ============================================================================

puts "\n========================================"
puts "  Exporting Results"
puts "========================================\n"

# Write synthesized netlist
write -format verilog -hierarchy -output $results_dir/${design}_synth.v
puts "  Netlist: $results_dir/${design}_synth.v"

# Write SDF for timing
write_sdf $results_dir/${design}_timing.sdf
puts "  SDF: $results_dir/${design}_timing.sdf"

# Write SDC constraints
write -format sdc -output $results_dir/${design}_const.sdc
puts "  SDC: $results_dir/${design}_const.sdc"

# Write design db
write -format db -hierarchy -output $results_dir/${design}.db
puts "  DB: $results_dir/${design}.db"

# ============================================================================
# Final Summary
# ============================================================================

puts "\n========================================"
puts "  Synthesis Complete!"
puts "========================================\n"

puts "Reports:"
puts "  $reports_dir/timing_*.rpt"
puts "  $reports_dir/area_*.rpt"
puts "  $reports_dir/power_*.rpt"
puts "  $reports_dir/cells_*.rpt"
puts "  $reports_dir/critical_paths.rpt"

puts "\nResults:"
puts "  $results_dir/${design}_synth.v"
puts "  $results_dir/${design}_timing.sdf"
puts "  $results_dir/${design}_const.sdc"
puts "  $results_dir/${design}.db"

exit
