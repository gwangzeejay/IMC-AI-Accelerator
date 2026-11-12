# ============================================================================
# IMC-TinyML Power Analysis - Synopsys PrimeTime PX
# ============================================================================
#
# Power analysis for gate-level netlist
#
# ============================================================================

puts "\n========================================"
puts "  IMC-TinyML Power Analysis"
puts "  PrimeTime PX"
puts "========================================\n"

# ============================================================================
# Setup
# ============================================================================

# Libraries
set target_library "/tools/synopsys/libraries/tcbn65lpwc/tcbn65lpwc.db"
set link_library "* $target_library"

# Output directories
set pwr_dir "./power"
file delete -force $pwr_dir
file mkdir $pwr_dir

# ============================================================================
# Read Design
# ============================================================================

puts "Reading synthesized netlist..."

set netlist "./synth/results/tinyml_accelerator_synth.v"
if {![file exists $netlist]} {
    puts "ERROR: Netlist not found: $netlist"
    puts "Run dc_synth.tcl first"
    exit 1
}

read_verilog $netlist
current_design tinyml_accelerator
link

# ============================================================================
# Read SDF
# ============================================================================

puts "Reading SDF..."
read_sdf "./synth/results/tinyml_accelerator_timing.sdf"

# ============================================================================
# Read SAIF (Activity)
# ============================================================================

# SAIF file from simulation
set saif_file "./sim/tinyml_activity.saif"
if {[file exists $saif_file]} {
    puts "Reading SAIF file..."
    read_saif -input $saif_file -design tinyml_accelerator
} else {
    puts "WARNING: SAIF file not found, using default toggle rates"
}

# ============================================================================
# Power Modes
# ============================================================================

puts "\n========================================"
puts "  Power Analysis - Multiple Modes"
puts "========================================\n"

# Mode 1: Active Inference
puts "\n--- Mode 1: Active Inference ---"

# Set activity factors for inference
set_switching_activity -static_probability 0.0 -toggle_rate 0 [find net -hier -filter "name =~ rst*"]
set_switching_activity -static_probability 0.5 -toggle_rate 100 [all_inputs]
set_switching_activity -static_probability 0.0 -toggle_rate 10 [all_outputs]

# Analyze power
update_power
report_power -format_summary > ./power/mode1_active.txt

puts "  Active Power: [get_attribute [current_design] total_power] mW"

# Mode 2: Idle
puts "\n--- Mode 2: Idle ---"

# Reduced activity
set_switching_activity -toggle_rate 10 [all_inputs]
set_switching_activity -toggle_rate 1 [all_registers]

update_power
report_power -format_summary > ./power/mode2_idle.txt

# Mode 3: Sleep
puts "\n--- Mode 3: Sleep ---"

# Minimal activity
set_switching_activity -toggle_rate 1 [all_inputs]

update_power
report_power -format_summary > ./power/mode3_sleep.txt

# ============================================================================
# Detailed Power Report
# ============================================================================

puts "\n========================================"
puts "  Detailed Power Breakdown"
puts "========================================\n"

# By module
report_power -hierarchy -format verilog > ./power/power_by_module.txt

# By net
report_power -net -max_nets 50 > ./power/power_by_net.txt

# Cell power breakdown
report_power -cell -max_cells 50 > ./power/power_by_cell.txt

# ============================================================================
# Power Summary
# ============================================================================

puts "\n========================================"
puts "  Power Summary"
puts "========================================\n"

report_power

# ============================================================================
# Energy Analysis
# ============================================================================

puts "\n========================================"
puts "  Energy Analysis"
puts "========================================\n"

# Get power values
set total_pwr [get_attribute [current_design] total_power]
set leakage_pwr [get_attribute [current_design] leakage_power]
set internal_pwr [get_attribute [current_design] cell_internal_power]
set switching_pwr [get_attribute [current_design] net_switching_power]

puts "\nPower Components:"
puts "  Total:    [format %.3f [expr $total_pwr * 1000]] mW"
puts "  Leakage:  [format %.3f [expr $leakage_pwr * 1000]] mW"
puts "  Internal: [format %.3f [expr $internal_pwr * 1000]] mW"
puts "  Switching:[format %.3f [expr $switching_pwr * 1000]] mW"

# Inference energy calculation
set inference_time 0.005  ;# 5ms for full inference
set inference_energy [expr $total_pwr * $inference_time * 1000000]

puts "\nInference Energy:"
puts "  Time:     [expr $inference_time * 1000] ms"
puts "  Energy:   [format %.2f $inference_energy] μJ"

# Battery-free analysis
puts "\nBattery-Free Analysis:"
puts "  Available power (indoor light): 10-100 μW"
puts "  IMC power: [format %.3f [expr $total_pwr * 1000000]] μW"
puts "  Status: POSSIBLE (if duty cycle < 0.1%)"

# ============================================================================
# Report Summary
# ============================================================================

report_power -format summary > ./power/power_summary.txt

puts "\n========================================"
puts "  Power Analysis Complete!"
puts "========================================\n"

puts "Reports saved to ./power/"

exit
