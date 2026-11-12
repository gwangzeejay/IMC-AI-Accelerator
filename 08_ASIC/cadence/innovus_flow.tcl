# ============================================================================
# IMC-TinyML ASIC Implementation - Cadence Innovus
# ============================================================================
#
# RTL to GDS implementation script for TSMC 65nm LP
#
# ============================================================================

# ============================================================================
# Initialization
# ============================================================================

puts "\n========================================"
puts "  IMC-TinyML ASIC Implementation"
puts "  Cadence Innovus"
puts "========================================\n"

# Configuration
set design_name "tinyml_accelerator"
set工艺 "TSMC_65nm_LP"
set target_dir "./innovus"
set synth_dir "./synth/results"

# Create directories
file delete -force $target_dir
file mkdir $target_dir

# ============================================================================
# Initialize Design
# ============================================================================

puts "\nInitializing design..."

# Import synthesized netlist
import_design \
    -format verilog \
    -top $design_name \
    ${synth_dir}/${design_name}_synth.v

# Read constraints
read_sdc ${synth_dir}/${design_name}_const.sdc

# Load timing library
set_global _allow_incomplete_timing_model true

# ============================================================================
# Floorplan
# ============================================================================

puts "\n========================================"
puts "  Floorplan"
puts "========================================\n"

# Die area (for 2mm x 2mm core)
set die_width 2000
set die_height 2000
set core_margin 50

# Create floorplan
floorplan -die_box "{$core_margin $core_margin [expr $die_width-$core_margin] [expr $die_height-$core_margin]}"

# Set aspect ratio
# floorplan -r 0.7 1.4

# Place pins
set_pin_placement_strategy -auto_generate_pins

# ============================================================================
# Power Planning
# ============================================================================

puts "\n========================================"
puts "  Power Planning"
puts "========================================\n"

# Create power/ground rings
add_ring \
    -type core_ring \
    -follow true \
    -layer {metal5 metal6} \
    -width 2.0 \
    -spacing 2.0 \
    -offset 2.0 \
    -core \
    -nets {VDD VSS}

# Add straps
addStripe \
    -layer metal4 \
    -width 2.0 \
    -spacing 2.0 \
    -offset 10.0 \
    -nets {VDD VSS}

addStripe \
    -layer metal5 \
    -width 2.0 \
    -spacing 2.0 \
    -offset 10.0 \
    -nets {VDD VSS}

# Connect straps to rings
sroute -connect pad_ring

# ============================================================================
# Place Standard Cells
# ============================================================================

puts "\n========================================"
puts "  Placement"
puts "========================================\n"

# Enable trial place for initial evaluation
trialplace

# Auto place
place_design

# ============================================================================
# CTS (Clock Tree Synthesis)
# ============================================================================

puts "\n========================================"
puts "  Clock Tree Synthesis"
puts "========================================\n"

# Set CTS options
set_ccopt_property -target_skew 0.1

# Create clock tree
create_clock_tree \
    -spec_file {} \
    -buffer_cells {CLKBUFx2 CLKBUFx4} \
    -leaf_cells {CKLNQx2 CKNDx2} \
    -max_fanout 16

# Build clock tree
build_clock_tree

# ============================================================================
# Routing
# ============================================================================

puts "\n========================================"
puts "  Routing"
puts "========================================\n"

# Set route options
setRouteMode -cancel true
setRouteMode -auto true
setRouteMode -detail true

# Global route
globalRoute -space 2.0

# Detail route
routeDesign -globalDetail

# ============================================================================
# Optimization
# ============================================================================

puts "\n========================================"
puts "  Optimization"
puts "========================================\n"

# Optimize setup
optDesign -preCTS
optDesign -postCTS
optDesign -postRoute

# ============================================================================
# Reports
# ============================================================================

puts "\n========================================"
puts "  Generating Reports"
puts "========================================\n"

set rpt_dir "./innovus/reports"
file mkdir $rpt_dir

# Timing reports
report_timing -max_paths 20 > $rpt_dir/timing.rpt
report_timing_summary > $rpt_dir/timing_summary.rpt

# Area report
report_area > $rpt_dir/area.rpt

# Power report
report_power > $rpt_dir/power.rpt

# Cell count
report_cells > $rpt_dir/cells.rpt

# Utilization
report_qor > $rpt_dir/qor.rpt

# ============================================================================
# Fillers
# ============================================================================

puts "\nAdding fillers..."

addFiller -cell {FILL1 FILL2 FILL4 FILL8 FILL16 FILL32} -prefix FIL_

# ============================================================================
# Output
# ============================================================================

puts "\n========================================"
puts "  Exporting Data"
puts "========================================\n"

# Export Netlist (Verilog)
write_netlist ./innovus/${design_name}_layout.v

# Export SDC
write_sdc ./innovus/${design_name}_layout.sdc

# Export SPEF
write_parasitics -format spef ./innovus/${design_name}.spef

# ============================================================================
# GDS Export
# ============================================================================

puts "\nExporting GDS..."

setStreamOut \
    -library "TSMC65nm" \
    -output ./innovus/${design_name}.gds

# ============================================================================
# Final Summary
# ============================================================================

puts "\n========================================"
puts "  Implementation Complete!"
puts "========================================\n"

puts "Reports: ./innovus/reports/"
puts "Netlist: ./innovus/${design_name}_layout.v"
puts "GDS:     ./innovus/${design_name}.gds"

saveDesign ./innovus/${design_name}.enc

exit
