// ============================================================================
// IMC-TinyML Formal Verification Package
// SystemVerilog Assertions for RTL Verification
// ============================================================================
//
// This file contains comprehensive SVA assertions for the IMC accelerator
// Can be used with formal verification tools (Jasper, VC Formal, etc.)
//
// ============================================================================

`timescale 1ns / 1ps
`ifdef NCVERILOG
`include "ncverilog_parser.h"
`endif

// ============================================================================
// Package: imc_tinyml_assertions
// ============================================================================

package imc_tinyml_assertions_pkg;

// ============================================================================
// Timing Constants
// ============================================================================

localparam time T_CLK = 10ns;       // 100 MHz clock
localparam time T_SETUP = 1ns;      // Setup time
localparam time T_HOLD = 0.5ns;     // Hold time
localparam time T_PROP = 2ns;       // Prop delay

// ============================================================================
// Property: Clock and Reset
// ============================================================================

// Clock must be stable and periodic
property clk_stable;
    @(posedge clk) disable iff (!rst_n)
    $stable(clk) && (clk !== 1'bx);
endproperty

// Reset must be stable when asserted
property rstn_stable;
    @(posedge clk)
    rst_n === 1'b0 |-> ##1 rst_n === 1'b0 until rst_n === 1'b1;
endproperty

// Reset must be asserted for minimum duration
property rstn_min_pulse;
    @(posedge clk)
    rst_n === 1'b0 |-> ##[3:$] rst_n === 1'b1;
endproperty

// ============================================================================
// Property: APB Protocol
// ============================================================================

// APB: psel must be stable during setup phase
property apb_psel_stable;
    @(posedge clk)
    psel && !penable |=> psel until (penable || !psel);
endproperty

// APB: paddr must be stable during access
property apb_paddr_stable;
    @(posedge clk)
    psel && !penable |-> ##1 $stable(paddr) throughout (penable[->1]);
endproperty

// APB: pwdata must be stable during write
property apb_pwdata_stable;
    @(posedge clk)
    psel && !penable && pwrite |-> ##1 $stable(pwdata) throughout (penable[->1]);
endproperty

// APB: pready must be high when penable is high
property apb_pready_when_enabled;
    @(posedge clk)
    psel && penable |-> pready;
endproperty

// APB: Write transaction sequence
sequence apb_write_seq;
    ##1 psel && !penable && pwrite
    ##1 psel && penable && pwrite && pready;
endsequence

// APB: Read transaction sequence
sequence apb_read_seq;
    ##1 psel && !penable && !pwrite
    ##1 psel && penable && !pwrite && pready;
endsequence

// APB: psel must not be de-asserted during transaction
property apb_psel_held;
    apb_write_seq |-> psel throughout (penable[->1]);
endproperty

// ============================================================================
// Property: AXI-Stream Protocol
// ============================================================================

// AXI-Stream: tvalid must not be de-asserted during transfer
property axis_tvalid_held;
    @(posedge clk)
    s_axis_tvalid && !s_axis_tready |=> s_axis_tvalid until s_axis_tready;
endproperty

// AXI-Stream: tdata must be stable when valid and not ready
property axis_tdata_stable;
    @(posedge clk)
    s_axis_tvalid && !s_axis_tready |=> $stable(s_axis_tdata);
endproperty

// AXI-Stream: tlast must be stable with tdata
property axis_tlast_stable;
    @(posedge clk)
    s_axis_tvalid && !s_axis_tready |=> $stable(s_axis_tlast);
endproperty

// AXI-Stream: tlast must be asserted with final word
sequence axis_transfer;
    s_axis_tvalid && s_axis_tready[*0:$] ##1 s_axis_tlast && s_axis_tvalid && s_axis_tready;
endsequence

// AXI-Stream: tready must not be de-asserted during transfer
property axis_tready_held;
    @(posedge clk)
    m_axis_tvalid && m_axis_tready |=> m_axis_tvalid until !m_axis_tvalid;
endproperty

// AXI-Stream: No valid after tlast
property axis_no_valid_after_last;
    @(posedge clk)
    s_axis_tlast && s_axis_tvalid && s_axis_tready |=> !s_axis_tvalid until !s_axis_tlast;
endproperty

// ============================================================================
// Property: Control FSM
// ============================================================================

// FSM: Valid state transitions
property valid_state_transition;
    @(posedge clk)
    disable iff (!rst_n)
    dbg_state inside {8'h00, 8'h01, 8'h02, 8'h03, 8'h04, 8'h05, 8'h10, 8'hFF};
endproperty

// FSM: No invalid states
property no_invalid_state;
    @(posedge clk)
    disable iff (!rst_n)
    !dbg_state inside {8'h06, 8'h07, 8'h08, 8'h09, 8'h0A, 8'h0F};
endproperty

// FSM: State transition timing
property state_change_timing;
    @(posedge clk)
    disable iff (!rst_n)
    dbg_state == 8'h01 |-> ##[1:100] dbg_state != 8'h01;
endproperty

// ============================================================================
// Property: IMC Array Interface
// ============================================================================

// IMC: Wordline enable timing
property imc_wl_timing;
    @(posedge clk)
    imc_wl_en |-> ##1 $stable(imc_wl_en) until !imc_wl_en;
endproperty

// IMC: Sense enable pulse width
property imc_sense_pulse;
    @(posedge clk)
    imc_sense_en |-> ##1 imc_sense_en[*1:5] ##1 !imc_sense_en;
endproperty

// IMC: Precharge before sense
property imc_precharge_before_sense;
    @(posedge clk)
    imc_sense_en |-> ##1 imc_bl_prech throughout (imc_sense_en[*0:$]);
endproperty

// IMC: Array reset clears state
property imc_array_rst_clears;
    @(posedge clk)
    imc_array_rst |-> ##[1:3] !imc_array_rst until (imc_wl_en || imc_bl_prech);
endproperty

// IMC: Input data valid with wordline
property imc_input_with_wl;
    @(posedge clk)
    imc_wl_en |-> $stable(imc_input_data) throughout (imc_wl_en[*0:$]);
endproperty

// ============================================================================
// Property: Interrupt Protocol
// ============================================================================

// Interrupt: Pulse width
property int_pulse_width;
    @(posedge clk)
    interrupt |-> ##1 interrupt[*3:$] ##1 !interrupt;
endproperty

// Interrupt: Not asserted during reset
property int_not_during_reset;
    @(posedge clk)
    !rst_n |-> !interrupt;
endproperty

// Interrupt: Cleared after read
sequence int_cleared_after_read;
    interrupt ##[1:10] $rose(prdata[2]);
endsequence

// ============================================================================
// Property: Data Integrity
// ============================================================================

// No X propagation on data outputs
property no_x_on_outputs;
    @(posedge clk)
    rst_n |-> !$isunknown({prdata, pready, m_axis_tdata, m_axis_tvalid});
endproperty

// No X on control signals
property no_x_on_control;
    @(posedge clk)
    rst_n |-> !$isunknown({pready, pslverr, s_axis_tready, interrupt});
endproperty

// ============================================================================
// Property: Power Management
// ============================================================================

// Power: No activity during reset
property no_activity_during_reset;
    @(posedge clk)
    !rst_n |-> !m_axis_tvalid && !interrupt && (dbg_state == 8'h00);
endproperty

// Power: Idle state after done
sequence idle_after_done;
    m_axis_tlast && m_axis_tvalid && m_axis_tready ##1
    (dbg_state == 8'h00);
endsequence

// ============================================================================
// Property: Performance
// ============================================================================

// Latency: Inference completion within expected time
property inference_latency;
    @(posedge clk)
    disable iff (!rst_n)
    (dbg_state == 8'h01) |-> ##[1:5000] (dbg_state == 8'h00);
endproperty

// Throughput: Minimum time between inferences
property inference_gap;
    @(posedge clk)
    (dbg_state == 8'h00) && $past(dbg_state == 8'h00) ##1 ##[1:$]
    (dbg_state == 8'h01) |-> ##[100:$] (dbg_state == 8'h00);
endproperty

// ============================================================================
// Property: Memory Safety
// ============================================================================

// Weight write: Valid address range
property weight_addr_valid;
    @(posedge clk)
    weight_write_enable |-> (weight_row_addr < 256) && (weight_col_addr < 64);
endproperty

// Weight write: Data in valid range
property weight_data_valid;
    @(posedge clk)
    weight_write_enable |-> (weight_write_data inside {[8'h00]:[8'hFF]});
endproperty

// No simultaneous read and write to same location
property no_rw_conflict;
    @(posedge clk)
    weight_write_enable && weight_read_enable |->
    (weight_row_addr != $past(weight_row_addr)) ||
    (weight_col_addr != $past(weight_col_addr));
endproperty

// ============================================================================
// Assertions
// ============================================================================

// Clock and Reset
assert property (clk_stable)
    else $error("Clock not stable");
assert property (rstn_stable)
    else $error("Reset not stable");
assert property (rstn_min_pulse)
    else $error("Reset pulse too short");

// APB Protocol
assert property (apb_psel_stable)
    else $error("APB psel not stable during setup");
assert property (apb_paddr_stable)
    else $error("APB paddr changed during access");
assert property (apb_pwdata_stable)
    else $error("APB pwdata changed during write");
assert property (apb_pready_when_enabled)
    else $error("APB pready not asserted when enabled");
assert property (apb_psel_held)
    else $error("APB psel de-asserted during transaction");

// AXI-Stream Protocol
assert property (axis_tvalid_held)
    else $error("AXI tvalid de-asserted during transfer");
assert property (axis_tdata_stable)
    else $error("AXI tdata changed while waiting");
assert property (axis_tlast_stable)
    else $error("AXI tlast changed while waiting");
assert property (axis_tready_held)
    else $error("AXI tready de-asserted during transfer");
assert property (axis_no_valid_after_last)
    else $error("AXI valid after tlast");

// Control FSM
assert property (valid_state_transition)
    else $error("Invalid state detected: %h", dbg_state);
assert property (no_invalid_state)
    else $error("FSM entered invalid state: %h", dbg_state);
assert property (state_change_timing)
    else $error("FSM stuck in same state too long");

// IMC Array Interface
assert property (imc_wl_timing)
    else $error("IMC wordline not stable");
assert property (imc_sense_pulse)
    else $error("IMC sense pulse width violation");
assert property (imc_precharge_before_sense)
    else $error("IMC precharge not before sense");
assert property (imc_array_rst_clears)
    else $error("IMC reset timing violation");
assert property (imc_input_with_wl)
    else $error("IMC input data not stable with wordline");

// Interrupt Protocol
assert property (int_pulse_width)
    else $error("Interrupt pulse width violation");
assert property (int_not_during_reset)
    else $error("Interrupt asserted during reset");

// Data Integrity
assert property (no_x_on_outputs)
    else $error("X detected on outputs");
assert property (no_x_on_control)
    else $error("X detected on control signals");

// Power Management
assert property (no_activity_during_reset)
    else $error("Activity detected during reset");

// Performance
assert property (inference_latency)
    else $error("Inference latency exceeded maximum");

// Memory Safety
assert property (weight_addr_valid)
    else $error("Invalid weight address");
assert property (weight_data_valid)
    else $error("Invalid weight data");
assert property (no_rw_conflict)
    else $error("Read/write conflict on weight memory");

// ============================================================================
// Cover Points
// ============================================================================

// APB Cover
cover property (apb_write_seq)
    $display("Cover: APB write transaction");
cover property (apb_read_seq)
    $display("Cover: APB read transaction");

// AXI Cover
cover property (axis_transfer)
    $display("Cover: AXI transfer with tlast");

// FSM Cover
cover sequence (dbg_state == 8'h00 ##[1:100] dbg_state == 8'h01)
    $display("Cover: FSM transition IDLE->BUSY");
cover sequence (dbg_state == 8'h01 ##[1:100] dbg_state == 8'h00)
    $display("Cover: FSM transition BUSY->IDLE");

// IMC Cover
cover sequence (imc_wl_en ##[1:10] imc_sense_en)
    $display("Cover: IMC compute cycle");

// Interrupt Cover
cover property ($rose(interrupt))
    $display("Cover: Interrupt detected");

endpackage : imc_tinyml_assertions_pkg

// ============================================================================
// Module: Assertion Bindings
// ============================================================================

module imc_tinyml_assertions (
    input clk,
    input rst_n,

    // APB
    input [31:0] paddr,
    input [31:0] pwdata,
    input [31:0] prdata,
    input psel,
    input penable,
    input pwrite,
    input pready,
    input pslverr,

    // AXI-Stream
    input [7:0] s_axis_tdata,
    input s_axis_tvalid,
    input s_axis_tready,
    input s_axis_tlast,
    input [7:0] m_axis_tdata,
    input m_axis_tvalid,
    input m_axis_tready,
    input m_axis_tlast,

    // IMC
    input [3:0] imc_wl_en,
    input [3:0] imc_bl_prech,
    input [3:0] imc_sense_en,
    input [3:0] imc_array_rst,
    input [31:0] imc_input_data,
    input [127:0] imc_output_data,

    // Control
    input interrupt,
    input [7:0] dbg_state,
    input [31:0] dbg_cycles,
    input [15:0] dbg_layer_count,

    // Weight interface
    input [7:0] weight_row_addr,
    input [7:0] weight_col_addr,
    input [7:0] weight_write_data,
    input weight_write_enable,
    input weight_read_enable
);

    import imc_tinyml_assertions_pkg::*;

    // Assertions are automatically bound via the package

endmodule : imc_tinyml_assertions

// ============================================================================
// Module: Property Checker Wrapper
// ============================================================================

module imc_tinyml_property_checker #(
    parameter CHECK_CLKGATE = 1,
    parameter CHECK_APB = 1,
    parameter CHECK_AXIS = 1,
    parameter CHECK_IMC = 1,
    parameter CHECK_POWER = 1
)(
    input clk,
    input rst_n,

    // DUT signals (bound internally in formal tools)
    // These parameters allow selective checking

    input [31:0] paddr,
    input [31:0] pwdata,
    input [31:0] prdata,
    input psel,
    input penable,
    input pwrite,
    input pready,

    input [7:0] s_axis_tdata,
    input s_axis_tvalid,
    input s_axis_tready,

    input [7:0] dbg_state,
    input interrupt
);

    // =========================================================================
    // APB Protocol Checks
    // =========================================================================
    generate if (CHECK_APB) begin : gen_apb_checks
        assert property (
            @(posedge clk)
            disable iff (!rst_n)
            psel && penable |-> pready
        ) else $error("APB: pready not asserted");

        assert property (
            @(posedge clk)
            disable iff (!rst_n)
            psel && !penable |=> psel until (penable || !psel)
        ) else $error("APB: psel de-asserted during setup");
    end endgenerate

    // =========================================================================
    // AXI-Stream Checks
    // =========================================================================
    generate if (CHECK_AXIS) begin : gen_axis_checks
        assert property (
            @(posedge clk)
            disable iff (!rst_n)
            s_axis_tvalid && !s_axis_tready |=> s_axis_tvalid
        ) else $error("AXIS: tvalid de-asserted");

        assert property (
            @(posedge clk)
            disable iff (!rst_n)
            s_axis_tlast && s_axis_tvalid && s_axis_tready |->
            ##[1:100] !s_axis_tvalid until !s_axis_tlast
        ) else $error("AXIS: valid after tlast");
    end endgenerate

    // =========================================================================
    // Control FSM Checks
    // =========================================================================
    generate if (CHECK_POWER) begin : gen_power_checks
        assert property (
            @(posedge clk)
            disable iff (!rst_n)
            !rst_n |-> !interrupt && (dbg_state == 8'h00)
        ) else $error("POWER: Activity during reset");
    end endgenerate

endmodule : imc_tinyml_property_checker
