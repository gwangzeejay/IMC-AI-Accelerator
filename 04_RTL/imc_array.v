// ============================================================================
// IMC Array Module
// Behavioral Model for In-Memory Computing Array
// ============================================================================
//
// This module implements a behavioral model of an SRAM-based In-Memory Computing
// array for matrix-vector multiplication operations.
//
// ============================================================================

`timescale 1ns / 1ps

module imc_array #(
    //=================================================================
    // Parameters
    //=================================================================
    parameter NUM_ROWS        = 256,            // Number of rows (input channels)
    parameter NUM_COLS        = 64,             // Number of columns (output)
    parameter BIT_PRECISION   = 8,              // Bits per weight
    parameter DATA_WIDTH      = 8,              // Input data width
    parameter ACCUM_WIDTH     = 32              // Accumulator width
)(
    //=================================================================
    // Clock and Reset
    //=================================================================
    input  wire                 clk,
    input  wire                 rst_n,

    //=================================================================
    // Control Signals
    //=================================================================
    input  wire                 enable,           // Array enable
    input  wire                 compute_start,    // Start computation
    input  wire                 reset_accum,      // Reset accumulator
    input  wire                 precharge,        // Precharge bitlines

    //=================================================================
    // Weight Memory Interface
    //=================================================================
    input  wire [$clog2(NUM_ROWS)-1:0] weight_row_addr,
    input  wire [$clog2(NUM_COLS)-1:0] weight_col_addr,
    input  wire [BIT_PRECISION-1:0]     weight_write_data,
    input  wire                         weight_write_enable,
    input  wire                         weight_read_enable,

    output wire [BIT_PRECISION-1:0]     weight_read_data,

    //=================================================================
    // Input Data Interface
    //=================================================================
    input  wire [DATA_WIDTH-1:0]        input_data,       // Input vector
    input  wire [$clog2(NUM_ROWS)-1:0] input_select,     // Select input row

    //=================================================================
    // Output Interface
    //=================================================================
    output wire [ACCUM_WIDTH-1:0]      result_out,        // Accumulated result
    output wire                         result_valid,     // Result ready
    output wire [NUM_COLS-1:0]        bitline_levels     // For debugging
);

// ============================================================================
// Local Parameters
// ============================================================================

localparam ADDR_ROW_WIDTH = $clog2(NUM_ROWS);
localparam ADDR_COL_WIDTH = $clog2(NUM_COLS);

// ============================================================================
// Weight Memory (SRAM Model)
// ============================================================================
//
// The weight memory stores the neural network weights.
// In a physical implementation, this would be actual SRAM cells.
// For simulation, we use a behavioral model.

// Weight Memory: NUM_ROWS × NUM_COLS × BIT_PRECISION bits
// Organized as: each row stores weights for one input channel
// Each column represents one output

(* ram_style = "block" *)
reg [BIT_PRECISION-1:0] weight_memory [0:NUM_ROWS*NUM_COLS-1];

// Memory address calculation
wire [ADDR_ROW_WIDTH + ADDR_COL_WIDTH - 1:0] weight_addr_calc;
assign weight_addr_calc = {weight_row_addr, weight_col_addr};

// Weight Write
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        // Initialize with small random values for simulation
        integer i;
        for (i = 0; i < NUM_ROWS * NUM_COLS; i = i + 1) begin
            weight_memory[i] <= $random % 256;  // Random 8-bit values
        end
    end else begin
        if (weight_write_enable) begin
            weight_memory[weight_addr_calc] <= weight_write_data;
        end
    end
end

// Weight Read
assign weight_read_data = weight_memory[weight_addr_calc];

// ============================================================================
// IMC Computation Logic
// ============================================================================
//
// The IMC computation is performed by:
// 1. Selecting the input row (wordline)
// 2. Reading weights from the selected row
// 3. Multiplying each weight by the input value
// 4. Summing across all columns
//
// In physical IMC, this is done analog in the memory array.
// Here we model it digitally for simulation.

// Input register
reg [DATA_WIDTH-1:0] input_reg;
reg [ADDR_ROW_WIDTH-1:0] input_select_reg;

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        input_reg <= {DATA_WIDTH{1'b0}};
        input_select_reg <= {ADDR_ROW_WIDTH{1'b0}};
    end else begin
        if (enable) begin
            input_reg <= input_data;
            input_select_reg <= input_select;
        end
    end
end

// ============================================================================
// Analog Simulation (Behavioral)
// ============================================================================
//
// We simulate the analog behavior of the IMC array:
// - Each weight cell has a "conductance" proportional to its stored value
// - The wordline voltage is proportional to the input
// - The bitline current is the sum of (input * weight) for all cells
//
// Digital approximation:
// result[col] = Σ(row) input[row] × weight[row][col]

// Partial sum storage
reg [ACCUM_WIDTH-1:0] accumulators [0:NUM_COLS-1];

// Computation state
reg computing;
reg [ADDR_ROW_WIDTH-1:0] compute_row_count;

// Result valid flag
reg result_valid_reg;

// Compute the matrix-vector multiplication
integer col_idx;
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        for (col_idx = 0; col_idx < NUM_COLS; col_idx = col_idx + 1) begin
            accumulators[col_idx] <= {ACCUM_WIDTH{1'b0}};
        end
        computing <= 1'b0;
        compute_row_count <= {ADDR_ROW_WIDTH{1'b0}};
        result_valid_reg <= 1'b0;
    end else begin
        result_valid_reg <= 1'b0;

        if (reset_accum) begin
            // Reset accumulators
            for (col_idx = 0; col_idx < NUM_COLS; col_idx = col_idx + 1) begin
                accumulators[col_idx] <= {ACCUM_WIDTH{1'b0}};
            end
            compute_row_count <= {ADDR_ROW_WIDTH{1'b0}};
            computing <= 1'b0;
        end else if (compute_start && !computing) begin
            // Start new computation
            for (col_idx = 0; col_idx < NUM_COLS; col_idx = col_idx + 1) begin
                accumulators[col_idx] <= {ACCUM_WIDTH{1'b0}};
            end
            compute_row_count <= {ADDR_ROW_WIDTH{1'b0}};
            computing <= 1'b1;
        end else if (computing) begin
            // Compute one row at a time (pipelined)
            if (compute_row_count < NUM_ROWS[ADDR_ROW_WIDTH-1:0]) begin
                // Compute contribution from this row
                for (col_idx = 0; col_idx < NUM_COLS; col_idx = col_idx + 1) begin
                    // IMC multiplication: input * weight
                    // In real analog, this would be: V_in * G_cell
                    // We approximate as signed multiplication
                    accumulators[col_idx] <= accumulators[col_idx] +
                        ({{24{input_reg[DATA_WIDTH-1]}}, input_reg} *
                         {{24{weight_memory[{input_select_reg, col_idx[ADDR_COL_WIDTH-1:0]}][BIT_PRECISION-1]}},
                          weight_memory[{input_select_reg, col_idx[ADDR_COL_WIDTH-1:0]}]});
                end
                compute_row_count <= compute_row_count + 1'b1;
            end else begin
                // Computation complete
                computing <= 1'b0;
                result_valid_reg <= 1'b1;
            end
        end
    end
end

// ============================================================================
// Output Assignment
// ============================================================================

// Result is the sum of all rows
// For a single input (one row), result is the row itself
assign result_out = accumulators[0];

// Result valid is combinatorial based on state
assign result_valid = result_valid_reg;

// Debug: bitline levels (simulated)
assign bitline_levels = {NUM_COLS{1'b0}};  // Placeholder

// ============================================================================
// Additional Read Ports (for weight verification)
// ============================================================================

// We maintain a copy of the weights for verification
reg [BIT_PRECISION-1:0] weight_copy [0:NUM_ROWS*NUM_COLS-1];

integer copy_idx;
always @(posedge clk) begin
    if (weight_write_enable) begin
        weight_copy[weight_addr_calc] <= weight_write_data;
    end
end

// Check that weights are correctly stored
wire weight_check;
assign weight_check = (weight_memory[weight_addr_calc] == weight_copy[weight_addr_calc]);

// ============================================================================
// Assertions
// ============================================================================

// synthesis translate_off
// synopsys translate_off

// Ensure NUM_ROWS is a power of 2
initial begin
    if (NUM_ROWS % 2 != 0) begin
        $display("Warning: NUM_ROWS should be power of 2 for optimal IMC performance");
    end
    if (NUM_COLS % 2 != 0) begin
        $display("Warning: NUM_COLS should be power of 2 for optimal IMC performance");
    end
end

// synthesis translate_on
// synopsys translate_on

endmodule // imc_array

// ============================================================================
// IMC Tile Wrapper
// ============================================================================
//
// Wraps multiple IMC arrays to form a larger compute tile
// ============================================================================

module imc_tile #(
    parameter NUM_ROWS        = 256,
    parameter NUM_COLS        = 64,
    parameter BIT_PRECISION   = 8,
    parameter DATA_WIDTH      = 8,
    parameter ACCUM_WIDTH     = 32,
    parameter NUM_TILES       = 4  // Number of parallel output tiles
)(
    input  wire                 clk,
    input  wire                 rst_n,

    // Control
    input  wire                 enable,
    input  wire                 compute_start,
    input  wire                 reset_accum,

    // Input broadcast
    input  wire [DATA_WIDTH-1:0] input_data,

    // Weight interface
    input  wire [$clog2(NUM_ROWS)-1:0] weight_row_addr,
    input  wire [BIT_PRECISION-1:0]     weight_write_data,
    input  wire                         weight_write_enable,

    // Outputs (parallel)
    output wire [NUM_TILES*ACCUM_WIDTH-1:0] results,
    output wire [NUM_TILES-1:0]             results_valid
);

genvar tile_idx;
generate
    for (tile_idx = 0; tile_idx < NUM_TILES; tile_idx = tile_idx + 1) begin : gen_tile

        wire [$clog2(NUM_COLS)-1:0] tile_col_offset;
        assign tile_col_offset = tile_idx * (NUM_COLS / NUM_TILES);

        imc_array #(
            .NUM_ROWS      (NUM_ROWS),
            .NUM_COLS      (NUM_COLS / NUM_TILES),
            .BIT_PRECISION (BIT_PRECISION),
            .DATA_WIDTH    (DATA_WIDTH),
            .ACCUM_WIDTH   (ACCUM_WIDTH)
        ) u_imc_array (
            .clk              (clk),
            .rst_n            (rst_n),
            .enable           (enable),
            .compute_start    (compute_start),
            .reset_accum      (reset_accum),
            .precharge        (1'b0),
            .weight_row_addr  (weight_row_addr),
            .weight_col_addr  (tile_col_offset),
            .weight_write_data(weight_write_data),
            .weight_write_enable(weight_write_enable),
            .weight_read_enable(1'b0),
            .weight_read_data (),
            .input_data       (input_data),
            .input_select     (weight_row_addr),
            .result_out       (results[tile_idx*ACCUM_WIDTH +: ACCUM_WIDTH]),
            .result_valid     (results_valid[tile_idx]),
            .bitline_levels   ()
        );

    end
endgenerate

endmodule // imc_tile

// ============================================================================
// Shift-Add Accumulator
// ============================================================================
//
// Converts bit-serial analog values to digital output
// ============================================================================

module shift_add_accumulator #(
    parameter NUM_BITS     = 8,
    parameter BIT_WIDTH   = 32,
    parameter NUM_CHANNELS = 16
)(
    input  wire                     clk,
    input  wire                     rst_n,

    // Input: bit-serial from each bit-slice
    input  wire [NUM_CHANNELS-1:0] bit_in,      // Current bit value
    input  wire [2:0]             bit_position, // 0-7 for INT8

    // Control
    input  wire                     accumulate,    // Add to accumulator
    input  wire                     reset,         // Reset accumulator

    // Output
    output wire [BIT_WIDTH-1:0]   result
);

// Internal accumulator
reg [BIT_WIDTH-1:0] accumulator [0:NUM_CHANNELS-1];

// Shift factor based on bit position
wire [BIT_WIDTH-1:0] shift_factor;
assign shift_factor = (bit_position == 3'd0) ? {{BIT_WIDTH-1{1'b0}}, 1'b1} :
                     (bit_position == 3'd1) ? {{BIT_WIDTH-2{1'b0}}, 1'b1, 1'b0} :
                     (bit_position == 3'd2) ? {{BIT_WIDTH-3{1'b0}}, 3'b100} :
                     (bit_position == 3'd3) ? {{BIT_WIDTH-4{1'b0}}, 4'b1000} :
                     (bit_position == 3'd4) ? {{BIT_WIDTH-5{1'b0}}, 5'b10000} :
                     (bit_position == 3'd5) ? {{BIT_WIDTH-6{1'b0}}, 6'b100000} :
                     (bit_position == 3'd6) ? {{BIT_WIDTH-7{1'b0}}, 7'b1000000} :
                                              {{BIT_WIDTH-8{1'b0}}, 8'b10000000};

integer ch;
always @(posedge clk or negedge rst_n) begin
    if (!rst_n || reset) begin
        for (ch = 0; ch < NUM_CHANNELS; ch = ch + 1) begin
            accumulator[ch] <= {BIT_WIDTH{1'b0}};
        end
    end else if (accumulate) begin
        for (ch = 0; ch < NUM_CHANNELS; ch = ch + 1) begin
            if (bit_in[ch]) begin
                accumulator[ch] <= accumulator[ch] + shift_factor;
            end
        end
    end
end

// Output: sum of all channels
genvar i;
generate
    if (NUM_CHANNELS == 1) begin : gen_single
        assign result = accumulator[0];
    end else begin : gen_multi
        wire [BIT_WIDTH-1:0] sum_tree [0:NUM_CHANNELS-1];
        for (i = 0; i < NUM_CHANNELS; i = i + 1) begin
            assign sum_tree[i] = accumulator[i];
        end
        // Simple adder tree
        wire [BIT_WIDTH-1:0] partial_sums [0:(NUM_CHANNELS+1)/2-1];
        genvar j;
        for (j = 0; j < (NUM_CHANNELS+1)/2; j = j + 1) begin
            if (2*j < NUM_CHANNELS && 2*j+1 < NUM_CHANNELS) begin
                assign partial_sums[j] = sum_tree[2*j] + sum_tree[2*j+1];
            end else if (2*j < NUM_CHANNELS) begin
                assign partial_sums[j] = sum_tree[2*j];
            end
        end
        assign result = partial_sums[0] + partial_sums[1];
    end
endgenerate

endmodule // shift_add_accumulator

// ============================================================================
// Current Mirror Sense Amplifier (Behavioral)
// ============================================================================
//
// Models the current mirror sensing used in SRAM-based IMC
// ============================================================================

module sense_amplifier #(
    parameter INPUT_WIDTH  = 8,
    parameter OUTPUT_WIDTH = 8,
    parameter GAIN        = 4
)(
    input  wire [INPUT_WIDTH-1:0]  current_in,    // Bitline current (encoded)
    input  wire                    enable,
    output wire [OUTPUT_WIDTH-1:0] voltage_out
);

// Simplified model: convert current to voltage
// In real design, this would be transistor-level

reg [OUTPUT_WIDTH-1:0] v_out;

always @(*) begin
    if (enable) begin
        // Simple linear approximation
        // In real circuit: V_out = I_in * R_load * Gain
        v_out = current_in[INPUT_WIDTH-1:INPUT_WIDTH-OUTPUT_WIDTH] * GAIN;
        if (v_out > {OUTPUT_WIDTH{1'b1}}) begin
            v_out = {OUTPUT_WIDTH{1'b1}};
        end
    end else begin
        v_out = {OUTPUT_WIDTH{1'b0}};
    end
end

assign voltage_out = v_out;

endmodule // sense_amplifier
