// ============================================================================
// IMC-TinyML: In-Memory Computing AI Accelerator
// Top-level RTL Implementation
// ============================================================================
//
// This module implements the complete IMC-based AI accelerator for TinyML
// applications. It integrates IMC arrays with digital periphery for
// ultra-low power neural network inference.
//
// ============================================================================

`timescale 1ns / 1ps

module tinyml_accelerator #(
    //=================================================================
    // Parameters
    //=================================================================
    parameter NUM_TILES         = 4,              // Number of IMC tiles
    parameter ARRAY_ROWS        = 256,            // Rows per IMC array
    parameter ARRAY_COLS        = 64,             // Columns per IMC array
    parameter BIT_SLICE_DEPTH   = 8,              // INT8 precision
    parameter DATA_WIDTH        = 8,              // Input/output data width
    parameter ADDR_WIDTH        = 32,             // Address width
    parameter NUM_LAYERS        = 12,             // Maximum layers
    parameter ACCUM_WIDTH       = 32              // Accumulator width
)(
    //=================================================================
    // Clock and Reset
    //=================================================================
    input  wire                 clk,
    input  wire                 rst_n,

    //=================================================================
    // APB Interface (Configuration)
    //=================================================================
    input  wire [ADDR_WIDTH-1:0] paddr,
    input  wire [31:0]           pwdata,
    output wire [31:0]           prdata,
    input  wire                  psel,
    input  wire                  penable,
    input  wire                  pwrite,
    output wire                  pready,
    output wire                  pslverr,

    //=================================================================
    // AXI-Stream Interface (Data I/O)
    //=================================================================
    input  wire                  s_axis_tvalid,
    output wire                  s_axis_tready,
    input  wire [DATA_WIDTH-1:0] s_axis_tdata,
    input  wire                  s_axis_tlast,

    output wire                  m_axis_tvalid,
    input  wire                  m_axis_tready,
    output wire [DATA_WIDTH-1:0] m_axis_tdata,
    output wire                  m_axis_tlast,

    //=================================================================
    // Interrupt
    //=================================================================
    output wire                  interrupt,

    //=================================================================
    // IMC Array Interface (Simulation Model)
    //=================================================================
    output wire [NUM_TILES-1:0]     imc_wl_en,       // Wordline enable
    output wire [NUM_TILES-1:0]     imc_bl_prech,    // Bitline precharge
    output wire [NUM_TILES-1:0]     imc_sense_en,    // Sensing enable
    output wire [NUM_TILES-1:0]     imc_array_rst,   // Array reset
    output wire [NUM_TILES*8-1:0]   imc_input_data,   // Input data to IMC
    input  wire [NUM_TILES*ACCUM_WIDTH-1:0] imc_output_data, // IMC output

    //=================================================================
    // Debug Interface
    //=================================================================
    output wire [7:0]              dbg_state,
    output wire [31:0]            dbg_cycles,
    output wire [15:0]            dbg_layer_count
);

// ============================================================================
// Local Parameters
// ============================================================================

// FSM States
localparam FSM_BITS = 8;
localparam FSM_IDLE        = 8'd0;
localparam FSM_CONFIG      = 8'd1;
localparam FSM_LOAD_WEIGHTS = 8'd2;
localparam FSM_FETCH_INPUT = 8'd3;
localparam FSM_COMPUTE     = 8'd4;
localparam FSM_ACCUMULATE  = 8'd5;
localparam FSM_ACTIVATION  = 8'd6;
localparam FSM_STORE_OUTPUT = 8'd7;
localparam FSM_NEXT_LAYER  = 8'd8;
localparam FSM_DONE        = 8'd9;

// Layer Types
localparam LAYER_CONV      = 2'd0;
localparam LAYER_DENSE     = 2'd1;
localparam LAYER_POOL       = 2'd2;
localparam LAYER_ACT        = 2'd3;

// Activation Types
localparam ACT_NONE        = 2'd0;
localparam ACT_RELU        = 2'd1;
localparam ACT_RELU6       = 2'd2;
localparam ACT_SIGMOID     = 2'd3;

// ============================================================================
// Internal Signals
// ============================================================================

// Control FSM
reg [FSM_BITS-1:0]         fsm_state;
reg [FSM_BITS-1:0]         fsm_next;
reg [31:0]                 cycle_count;
reg                         start_computation;
reg                         computation_done;

// Configuration Registers
reg [1:0]                  layer_type;
reg [7:0]                  input_rows;
reg [7:0]                  input_cols;
reg [7:0]                  input_channels;
reg [7:0]                  output_channels;
reg [7:0]                  kernel_size;
reg [7:0]                  stride;
reg [1:0]                  activation_type;
reg [1:0]                  pooling_type;
reg [15:0]                 layer_count;
reg [15:0]                 max_layers;

// Data Path
reg [DATA_WIDTH-1:0]       input_buffer [0:255];
reg [$clog2(256)-1:0]     input_write_ptr;
reg [$clog2(256)-1:0]     input_read_ptr;
reg                         input_valid;
reg [DATA_WIDTH-1:0]       input_data;

reg [ACCUM_WIDTH-1:0]      output_buffer [0:255];
reg [$clog2(256)-1:0]      output_write_ptr;
reg [$clog2(256)-1:0]      output_read_ptr;
reg                         output_valid;

// IMC Control
reg [NUM_TILES-1:0]       imc_enable;
reg [NUM_TILES-1:0]       imc_start_compute;
reg [7:0]                  imc_tile_select;
reg [15:0]                 imc_row_count;
reg [15:0]                 imc_col_count;
reg [7:0]                  imc_bit_slice;
wire [NUM_TILES*ACCUM_WIDTH-1:0] imc_result;
reg [ACCUM_WIDTH-1:0]      partial_sum [0:NUM_TILES-1];

// Activation
reg [DATA_WIDTH-1:0]       activation_result;
reg [DATA_WIDTH-1:0]       activation_input;

// Pooling
reg [DATA_WIDTH-1:0]       pool_window [0:15];
reg [3:0]                  pool_counter;
reg [DATA_WIDTH-1:0]       pool_max;
reg [31:0]                  pool_sum;

// Address Generation
reg [15:0]                  weight_addr;
reg [7:0]                   input_addr;
reg [7:0]                   output_addr;

// Status
reg                          busy;
reg                          error;
wire                         idle;

// Interrupt
reg                          int_enable;
reg                          int_pending;
reg                          int_done;

// ============================================================================
// APB Controller
// ============================================================================

// Register Address Decode
localparam ADDR_CTRL       = 4'h0;
localparam ADDR_STATUS     = 4'h1;
localparam ADDR_LAYER_TYPE = 4'h2;
localparam ADDR_IN_DIM     = 4'h3;
localparam ADDR_OUT_DIM    = 4'h4;
localparam ADDR_KERNEL     = 4'h5;
localparam ADDR_STRIDE    = 4'h6;
localparam ADDR_ACT       = 4'h7;
localparam ADDR_MAX_LAYER = 4'h8;
localparam ADDR_RESULT     = 4'h9;
localparam ADDR_INT_EN    = 4'hA;
localparam ADDR_INT_STAT   = 4'hB;

reg [31:0]                  ctrl_reg;
reg [31:0]                  status_reg;
reg [31:0]                  result_reg;
reg [31:0]                  int_en_reg;
reg [31:0]                  int_stat_reg;

wire                        apb_write;
wire                        apb_read;
reg                         apb_ready;

// APB Write
assign apb_write = psel && penable && pwrite;
assign apb_read  = psel && !pwrite;

// APB Ready (always ready in this design)
assign pready = 1'b1;
assign pslverr = 1'b0;

// APB Write Logic
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        ctrl_reg       <= 32'h0;
        layer_type     <= 2'h0;
        input_rows     <= 8'd0;
        input_cols     <= 8'd0;
        input_channels <= 8'd0;
        output_channels<= 8'd0;
        kernel_size    <= 8'd0;
        stride         <= 8'd1;
        activation_type<= 2'h0;
        pooling_type   <= 2'h0;
        max_layers     <= 16'd12;
        int_en_reg     <= 32'h0;
    end else begin
        if (apb_write) begin
            case (paddr[5:2])
                ADDR_CTRL: begin
                    ctrl_reg <= pwdata;
                    if (pwdata[0]) start_computation <= 1'b1;
                    if (pwdata[2]) begin
                        fsm_state <= FSM_IDLE;
                        cycle_count <= 32'h0;
                    end
                end

                ADDR_LAYER_TYPE: begin
                    layer_type <= pwdata[1:0];
                end

                ADDR_IN_DIM: begin
                    input_rows     <= pwdata[31:24];
                    input_cols     <= pwdata[23:16];
                    input_channels <= pwdata[7:0];
                end

                ADDR_OUT_DIM: begin
                    output_channels <= pwdata[7:0];
                end

                ADDR_KERNEL: begin
                    kernel_size <= pwdata[7:0];
                end

                ADDR_STRIDE: begin
                    stride <= pwdata[7:0];
                end

                ADDR_ACT: begin
                    activation_type <= pwdata[1:0];
                end

                ADDR_MAX_LAYER: begin
                    max_layers <= pwdata[15:0];
                end

                ADDR_INT_EN: begin
                    int_en_reg <= pwdata;
                end
            endcase
        end else begin
            start_computation <= 1'b0;
        end
    end
end

// APB Read Logic
always @(*) begin
    case (paddr[5:2])
        ADDR_CTRL:       prdata = ctrl_reg;
        ADDR_STATUS:     prdata = {idle, busy, computation_done, error, 28'h0};
        ADDR_LAYER_TYPE: prdata = {30'h0, layer_type};
        ADDR_IN_DIM:     prdata = {input_rows, input_cols, 8'h0, input_channels};
        ADDR_OUT_DIM:    prdata = {24'h0, output_channels};
        ADDR_KERNEL:     prdata = {24'h0, kernel_size};
        ADDR_STRIDE:     prdata = {24'h0, stride};
        ADDR_ACT:        prdata = {30'h0, activation_type};
        ADDR_MAX_LAYER:  prdata = {16'h0, max_layers};
        ADDR_RESULT:     prdata = result_reg;
        ADDR_INT_EN:     prdata = int_en_reg;
        ADDR_INT_STAT:   prdata = {31'h0, int_pending};
        default:          prdata = 32'h0;
    endcase
end

// ============================================================================
// Control FSM
// ============================================================================

// FSM State Register
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        fsm_state <= FSM_IDLE;
        cycle_count <= 32'h0;
    end else begin
        fsm_state <= fsm_next;
        if (fsm_state != FSM_IDLE) begin
            cycle_count <= cycle_count + 1'b1;
        end else begin
            cycle_count <= 32'h0;
        end
    end
end

// FSM Next State Logic
always @(*) begin
    case (fsm_state)
        FSM_IDLE: begin
            if (start_computation)
                fsm_next = FSM_CONFIG;
            else
                fsm_next = FSM_IDLE;
        end

        FSM_CONFIG: begin
            fsm_next = FSM_LOAD_WEIGHTS;
        end

        FSM_LOAD_WEIGHTS: begin
            // Load weights into IMC arrays
            if (weight_addr >= (kernel_size * kernel_size * input_channels / NUM_TILES))
                fsm_next = FSM_FETCH_INPUT;
            else
                fsm_next = FSM_LOAD_WEIGHTS;
        end

        FSM_FETCH_INPUT: begin
            if (input_valid)
                fsm_next = FSM_COMPUTE;
            else
                fsm_next = FSM_FETCH_INPUT;
        end

        FSM_COMPUTE: begin
            // Wait for IMC computation
            fsm_next = FSM_ACCUMULATE;
        end

        FSM_ACCUMULATE: begin
            if (imc_row_count >= output_channels)
                fsm_next = FSM_ACTIVATION;
            else
                fsm_next = FSM_COMPUTE;
        end

        FSM_ACTIVATION: begin
            fsm_next = FSM_STORE_OUTPUT;
        end

        FSM_STORE_OUTPUT: begin
            if (layer_count >= max_layers)
                fsm_next = FSM_DONE;
            else
                fsm_next = FSM_NEXT_LAYER;
        end

        FSM_NEXT_LAYER: begin
            fsm_next = FSM_CONFIG;
        end

        FSM_DONE: begin
            fsm_next = FSM_IDLE;
        end

        default: fsm_next = FSM_IDLE;
    endcase
end

// FSM Control Outputs
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        imc_enable         <= {NUM_TILES{1'b0}};
        imc_start_compute  <= {NUM_TILES{1'b0}};
        imc_tile_select    <= 8'h0;
        imc_row_count      <= 16'h0;
        imc_col_count      <= 16'h0;
        imc_bit_slice      <= 8'h0;
        busy               <= 1'b0;
        error              <= 1'b0;
        computation_done   <= 1'b0;
        layer_count        <= 16'h0;
        int_pending        <= 1'b0;
    end else begin
        imc_enable         <= {NUM_TILES{1'b0}};
        imc_start_compute  <= {NUM_TILES{1'b0}};

        case (fsm_state)
            FSM_IDLE: begin
                busy             <= 1'b0;
                error            <= 1'b0;
                computation_done <= 1'b0;
                layer_count      <= 16'h0;
            end

            FSM_CONFIG: begin
                busy            <= 1'b1;
                layer_count     <= 16'h0;
                weight_addr     <= 16'h0;
                imc_row_count   <= 16'h0;
                imc_col_count   <= 16'h0;
            end

            FSM_LOAD_WEIGHTS: begin
                imc_enable     <= {NUM_TILES{1'b1}};
                imc_tile_select <= weight_addr[7:0];
                // Weight loading happens via separate memory interface
                weight_addr     <= weight_addr + 1'b1;
            end

            FSM_FETCH_INPUT: begin
                // Input data received from AXI-Stream
            end

            FSM_COMPUTE: begin
                imc_enable         <= {NUM_TILES{1'b1}};
                imc_start_compute  <= {NUM_TILES{1'b1}};
                imc_tile_select    <= imc_row_count[7:0];
                imc_bit_slice      <= 8'h0;
            end

            FSM_ACCUMULATE: begin
                // Accumulate partial results from IMC
                imc_row_count <= imc_row_count + 1'b1;
            end

            FSM_NEXT_LAYER: begin
                layer_count <= layer_count + 1'b1;
            end

            FSM_DONE: begin
                computation_done <= 1'b1;
                busy             <= 1'b0;
                int_pending      <= int_en_reg[0];
            end
        endcase
    end
end

// ============================================================================
// IMC Array Model (Behavioral)
// ============================================================================

// This models the behavior of the physical IMC array
// In real implementation, this would be replaced with transistor-level simulation

genvar tile_idx;
generate
    for (tile_idx = 0; tile_idx < NUM_TILES; tile_idx = tile_idx + 1) begin : gen_imc_tile

        // IMC Input Register
        reg [DATA_WIDTH-1:0] imc_input_reg;
        reg [ACCUM_WIDTH-1:0] imc_accum;

        always @(posedge clk or negedge rst_n) begin
            if (!rst_n) begin
                imc_input_reg <= {DATA_WIDTH{1'b0}};
                imc_accum     <= {ACCUM_WIDTH{1'b0}};
            end else begin
                if (imc_enable[tile_idx]) begin
                    imc_input_reg <= imc_input_data[tile_idx*DATA_WIDTH +: DATA_WIDTH];

                    // Simulate IMC multiplication and accumulation
                    if (imc_start_compute[tile_idx]) begin
                        // Multiply-accumulate simulation
                        imc_accum <= imc_accum +
                                    ({{24{imc_input_reg[7]}}, imc_input_reg} *
                                     {{24{1'b0}}, 8'h01});  // Simplified MAC
                    end

                    // Reset accumulator periodically
                    if (fsm_state == FSM_CONFIG) begin
                        imc_accum <= {ACCUM_WIDTH{1'b0}};
                    end
                end
            end
        end

        // IMC Output Assignment
        assign imc_output_data[tile_idx*ACCUM_WIDTH +: ACCUM_WIDTH] =
               imc_enable[tile_idx] ? imc_accum : {ACCUM_WIDTH{1'b0}};

    end
endgenerate

// ============================================================================
// Activation Unit
// ============================================================================

always @(*) begin
    case (activation_type)
        ACT_NONE: begin
            activation_result = activation_input;
        end

        ACT_RELU: begin
            // ReLU: max(0, x)
            activation_result = (activation_input[DATA_WIDTH-1]) ?
                               {DATA_WIDTH{1'b0}} : activation_input;
        end

        ACT_RELU6: begin
            // ReLU6: min(max(0, x), 6)
            if (activation_input[DATA_WIDTH-1]) begin
                activation_result = {DATA_WIDTH{1'b0}};
            end else if (|activation_input[DATA_WIDTH-1:3]) begin
                activation_result = 8'd6;
            end else begin
                activation_result = activation_input;
            end
        end

        ACT_SIGMOID: begin
            // Piecewise linear sigmoid approximation
            if (activation_input[DATA_WIDTH-1]) begin
                // Negative: small values
                activation_result = 8'd0;
            end else if (|activation_input[DATA_WIDTH-1:2]) begin
                // Large positive: near 1
                activation_result = 8'd255;
            end else begin
                // Linear region: approx x/4 + 128
                activation_result = {1'b0, activation_input[6:0]} + 8'd128;
            end
        end

        default: activation_result = activation_input;
    endcase
end

// ============================================================================
// Pooling Unit
// ============================================================================

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        pool_counter <= 4'h0;
        pool_max     <= {DATA_WIDTH{1'b0}};
        pool_sum     <= 32'h0;
    end else begin
        if (fsm_state == FSM_COMPUTE && pooling_type != 2'b00) begin
            pool_window[pool_counter] <= activation_input;
            pool_sum <= pool_sum + {{24{activation_input[7]}}, activation_input};

            // Update max
            if (activation_input > pool_max) begin
                pool_max <= activation_input;
            end

            pool_counter <= pool_counter + 1'b1;

            // Output pooling result when window is full
            if (pool_counter == 4'hF) begin
                pool_counter <= 4'h0;
            end
        end else begin
            pool_counter <= 4'h0;
            pool_max     <= {DATA_WIDTH{1'b0}};
            pool_sum     <= 32'h0;
        end
    end
end

// ============================================================================
// Input/Output Buffers
// ============================================================================

// Input Buffer Write
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        input_write_ptr <= {$clog2(256){1'b0}};
        input_valid     <= 1'b0;
    end else begin
        if (s_axis_tvalid && fsm_state == FSM_FETCH_INPUT) begin
            input_buffer[input_write_ptr] <= s_axis_tdata;
            input_write_ptr <= input_write_ptr + 1'b1;
            input_valid <= 1'b1;
        end else begin
            input_valid <= 1'b0;
        end
    end
end

// Input Buffer Read
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        input_read_ptr <= {$clog2(256){1'b0}};
        input_data     <= {DATA_WIDTH{1'b0}};
    end else begin
        if (fsm_state == FSM_COMPUTE) begin
            input_data <= input_buffer[input_read_ptr];
            input_read_ptr <= input_read_ptr + 1'b1;
        end else begin
            input_read_ptr <= {$clog2(256){1'b0}};
        end
    end
end

// IMC Input Assignment
genvar i;
generate
    for (i = 0; i < NUM_TILES; i = i + 1) begin : gen_imc_input
        assign imc_input_data[i*DATA_WIDTH +: DATA_WIDTH] = input_data;
    end
endgenerate

// Activation input selection
always @(*) begin
    case (pooling_type)
        2'b00: activation_input = imc_output_data[ACCUM_WIDTH-1:0];
        2'b01: activation_input = pool_max;      // Max pooling
        2'b10: activation_input = pool_sum[15:8]; // Average pooling
        default: activation_input = imc_output_data[ACCUM_WIDTH-1:0];
    endcase
end

// Output Buffer Write
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        output_write_ptr <= {$clog2(256){1'b0}};
        output_valid     <= 1'b0;
    end else begin
        if (fsm_state == FSM_STORE_OUTPUT) begin
            output_buffer[output_write_ptr] <= activation_result;
            output_write_ptr <= output_write_ptr + 1'b1;
            output_valid <= 1'b1;
        end else begin
            output_valid <= 1'b0;
        end
    end
end

// Output AXI-Stream
assign m_axis_tvalid = output_valid;
assign m_axis_tdata  = output_buffer[output_read_ptr];
assign m_axis_tlast  = (output_read_ptr == output_write_ptr - 1'b1);

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        output_read_ptr <= {$clog2(256){1'b0}};
    end else begin
        if (m_axis_tready && m_axis_tvalid) begin
            output_read_ptr <= output_read_ptr + 1'b1;
        end
        if (fsm_state == FSM_IDLE) begin
            output_read_ptr <= {$clog2(256){1'b0}};
        end
    end
end

// ============================================================================
// Input AXI-Stream
// ============================================================================

assign s_axis_tready = (fsm_state == FSM_FETCH_INPUT);

// ============================================================================
// IMC Array Physical Interface
// ============================================================================

assign imc_wl_en      = {NUM_TILES{1'b1}};
assign imc_bl_prech  = (fsm_state == FSM_CONFIG) ? {NUM_TILES{1'b1}} : {NUM_TILES{1'b0}};
assign imc_sense_en  = imc_enable;
assign imc_array_rst = (fsm_state == FSM_CONFIG) ? {NUM_TILES{1'b1}} : {NUM_TILES{1'b0}};

// ============================================================================
// Status Outputs
// ============================================================================

assign idle = (fsm_state == FSM_IDLE);
assign interrupt = int_pending;

assign dbg_state      = fsm_state;
assign dbg_cycles     = cycle_count;
assign dbg_layer_count = layer_count;

// ============================================================================
// Result Register
// ============================================================================

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        result_reg <= 32'h0;
    end else begin
        if (fsm_state == FSM_DONE) begin
            result_reg <= {16'h0, output_buffer[0]};
        end
    end
end

endmodule // tinyml_accelerator
