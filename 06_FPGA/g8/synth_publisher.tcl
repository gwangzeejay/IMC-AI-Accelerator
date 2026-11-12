# Optional Vivado out-of-context synthesis; NOT executed without a local tool.
# vivado -mode batch -source 06_FPGA/g8/synth_publisher.tcl -tclargs PART OUTDIR
# PART must be supplied from a real chosen target; there are no invented pins.
if {$argc != 2} { error "Usage: -tclargs PART OUTDIR" }
set target_part [lindex $argv 0]
set output_dir [file normalize [lindex $argv 1]]
set project_root [file normalize [file join [file dirname [info script]] ../..]]
if {[file exists $output_dir]} { error "Output exists; choose a fresh directory" }
file mkdir $output_dir
read_verilog -sv [file join $project_root 04_RTL g8 recap_output_log_commit.sv]
synth_design -top recap_output_log_commit -part $target_part -mode out_of_context
# 100 MHz is an explicit exploratory constraint, not an achieved frequency.
create_clock -name clk -period 10.0 [get_ports clk]
report_utilization -file [file join $output_dir utilization.rpt]
report_timing_summary -file [file join $output_dir timing_post_synth.rpt]
write_checkpoint [file join $output_dir publisher_post_synth.dcp]
puts "Post-synthesis only. No placement/routing, board test, or measured power."
