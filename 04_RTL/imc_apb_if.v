// ============================================================================
// APB Interface and Control Module
// ============================================================================
//
// APB slave interface for configuration and control
// ============================================================================

`timescale 1ns / 1ps

module apb_controller #(
    parameter ADDR_WIDTH = 32,
    parameter DATA_WIDTH = 32
)(
    // Clock and Reset
    input  wire                 clk,
    input  wire                 rst_n,

    // APB Interface
    input  wire [ADDR_WIDTH-1:0] paddr,
    input  wire [DATA_WIDTH-1:0] pwdata,
    output reg  [DATA_WIDTH-1:0] prdata,
    input  wire                  psel,
    input  wire                  penable,
    input  wire                  pwrite,
    output reg                   pready,
    output reg                   pslverr,

    // Configuration Outputs
    output reg  [1:0]           layer_type,
    output reg  [7:0]          input_rows,
    output reg  [7:0]          input_cols,
    output reg  [7:0]          input_channels,
    output reg  [7:0]          output_channels,
    output reg  [7:0]          kernel_size,
    output reg  [7:0]          stride,
    output reg  [1:0]          activation_type,
    output reg  [1:0]          pooling_type,
    output reg  [15:0]         max_layers,
    output reg                  start,
    output reg                  reset,

    // Status Inputs
    input  wire                  idle,
    input  wire                  busy,
    input  wire                  done,
    input  wire                  error,

    // Interrupt
    output reg                   int_enable,
    input  wire                  int_pending
);

// ============================================================================
// Register Addresses
// ============================================================================

localparam ADDR_CTRL       = 5'h00;
localparam ADDR_STATUS     = 5'h01;
localparam ADDR_LAYER_TYPE = 5'h02;
localparam ADDR_IN_ROWS   = 5'h03;
localparam ADDR_IN_COLS   = 5'h04;
localparam ADDR_IN_CH     = 5'h05;
localparam ADDR_OUT_CH    = 5'h06;
localparam ADDR_KERNEL    = 5'h07;
localparam ADDR_STRIDE    = 5'h08;
localparam ADDR_ACT       = 5'h09;
localparam ADDR_POOL      = 5'h0A;
localparam ADDR_MAX_LAYER = 5'h0B;
localparam ADDR_RESULT    = 5'h0C;
localparam ADDR_INT_EN    = 5'h0D;
localparam ADDR_INT_STAT  = 5'h0E;
localparam ADDR_CYCLE_CNT = 5'h0F;
localparam ADDR_POWER     = 5'h10;

// Internal registers
reg [DATA_WIDTH-1:0] int_en_reg;
reg [DATA_WIDTH-1:0] int_stat_reg;
reg [31:0] cycle_count;
reg [DATA_WIDTH-1:0] result_reg;
reg [1:0] power_state;

// ============================================================================
// APB Protocol
// ============================================================================

// APB Write
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        layer_type      <= 2'h0;
        input_rows      <= 8'd0;
        input_cols      <= 8'd0;
        input_channels  <= 8'd0;
        output_channels <= 8'd0;
        kernel_size     <= 8'd3;
        stride          <= 8'd1;
        activation_type <= 2'h0;
        pooling_type    <= 2'h0;
        max_layers      <= 16'd12;
        start           <= 1'b0;
        reset           <= 1'b0;
        int_en_reg      <= 32'h0;
        power_state     <= 2'h0;
    end else begin
        start <= 1'b0;
        reset <= 1'b0;

        if (psel && penable && pwrite) begin
            case (paddr[6:2])
                ADDR_CTRL: begin
                    start <= pwdata[0];
                    reset <= pwdata[1];
                end

                ADDR_LAYER_TYPE: begin
                    layer_type <= pwdata[1:0];
                end

                ADDR_IN_ROWS: begin
                    input_rows <= pwdata[7:0];
                end

                ADDR_IN_COLS: begin
                    input_cols <= pwdata[7:0];
                end

                ADDR_IN_CH: begin
                    input_channels <= pwdata[7:0];
                end

                ADDR_OUT_CH: begin
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

                ADDR_POOL: begin
                    pooling_type <= pwdata[1:0];
                end

                ADDR_MAX_LAYER: begin
                    max_layers <= pwdata[15:0];
                end

                ADDR_INT_EN: begin
                    int_en_reg <= pwdata;
                end

                ADDR_POWER: begin
                    power_state <= pwdata[1:0];
                end
            endcase
        end
    end
end

// APB Read
always @(*) begin
    case (paddr[6:2])
        ADDR_CTRL:      prdata = {30'h0, layer_type};
        ADDR_STATUS:    prdata = {idle, busy, done, error, 28'h0};
        ADDR_LAYER_TYPE:prdata = {30'h0, layer_type};
        ADDR_IN_ROWS:   prdata = {24'h0, input_rows};
        ADDR_IN_COLS:   prdata = {24'h0, input_cols};
        ADDR_IN_CH:     prdata = {24'h0, input_channels};
        ADDR_OUT_CH:    prdata = {24'h0, output_channels};
        ADDR_KERNEL:    prdata = {24'h0, kernel_size};
        ADDR_STRIDE:    prdata = {24'h0, stride};
        ADDR_ACT:       prdata = {30'h0, activation_type};
        ADDR_POOL:      prdata = {30'h0, pooling_type};
        ADDR_MAX_LAYER: prdata = {16'h0, max_layers};
        ADDR_RESULT:    prdata = result_reg;
        ADDR_INT_EN:    prdata = int_en_reg;
        ADDR_INT_STAT:  prdata = {31'h0, int_pending};
        ADDR_CYCLE_CNT: prdata = cycle_count;
        ADDR_POWER:     prdata = {30'h0, power_state};
        default:        prdata = 32'h0;
    endcase
end

// Ready and Error
always @(*) begin
    pready = 1'b1;
    pslverr = 1'b0;
end

// Interrupt enable
always @(*) begin
    int_enable = int_en_reg[0];
end

// Cycle counter
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        cycle_count <= 32'h0;
    end else begin
        if (reset) begin
            cycle_count <= 32'h0;
        end else if (busy) begin
            cycle_count <= cycle_count + 1'b1;
        end
    end
end

// Result capture
always @(posedge clk) begin
    if (done) begin
        result_reg <= 32'hDEADBEEF;  // Placeholder result
    end
end

endmodule // apb_controller

// ============================================================================
// AXI-Stream Interface
// ============================================================================

module axi_stream_controller #(
    parameter DATA_WIDTH = 8,
    parameter ID_WIDTH = 4,
    parameter FIFO_DEPTH = 16
)(
    // Clock and Reset
    input  wire                 clk,
    input  wire                 rst_n,

    // Slave Interface (Input)
    input  wire [DATA_WIDTH-1:0] s_axis_tdata,
    input  wire                  s_axis_tvalid,
    output reg                   s_axis_tready,
    input  wire                  s_axis_tlast,
    input  wire [ID_WIDTH-1:0]  s_axis_tid,

    // Master Interface (Output)
    output reg  [DATA_WIDTH-1:0] m_axis_tdata,
    output reg                   m_axis_tvalid,
    input  wire                  m_axis_tready,
    output reg                   m_axis_tlast,
    output reg  [ID_WIDTH-1:0]  m_axis_tid,

    // Internal Interface
    output reg  [DATA_WIDTH-1:0] data_out,
    output reg                   data_valid,
    output reg                   data_last,
    input  wire                  read_enable,
    input  wire [DATA_WIDTH-1:0] data_in
);

// ============================================================================
// Input FIFO
// ============================================================================

reg [DATA_WIDTH-1:0] input_fifo [0:FIFO_DEPTH-1];
reg [$clog2(FIFO_DEPTH):0] input_fifo_count;
reg [$clog2(FIFO_DEPTH):0] input_fifo_wr_ptr;
reg [$clog2(FIFO_DEPTH):0] input_fifo_rd_ptr;
wire input_fifo_full;
wire input_fifo_empty;

// Input FIFO write
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        input_fifo_wr_ptr <= {$clog2(FIFO_DEPTH)+1{1'b0}};
    end else begin
        if (s_axis_tvalid && !input_fifo_full) begin
            input_fifo[input_fifo_wr_ptr[$clog2(FIFO_DEPTH)-1:0]] <= s_axis_tdata;
            input_fifo_wr_ptr <= input_fifo_wr_ptr + 1'b1;
        end
    end
end

// Input FIFO read
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        input_fifo_rd_ptr <= {$clog2(FIFO_DEPTH)+1{1'b0}};
        s_axis_tready <= 1'b0;
    end else begin
        if (read_enable && !input_fifo_empty) begin
            data_out <= input_fifo[input_fifo_rd_ptr[$clog2(FIFO_DEPTH)-1:0]];
            data_valid <= 1'b1;
            input_fifo_rd_ptr <= input_fifo_rd_ptr + 1'b1;
            s_axis_tready <= 1'b1;
        end else begin
            data_valid <= 1'b0;
        end
    end
end

// Input FIFO status
assign input_fifo_full = (input_fifo_count == FIFO_DEPTH);
assign input_fifo_empty = (input_fifo_count == 0);

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        input_fifo_count <= {$clog2(FIFO_DEPTH)+1{1'b0}};
    end else begin
        if (s_axis_tvalid && !input_fifo_full && !(read_enable && !input_fifo_empty)) begin
            input_fifo_count <= input_fifo_count + 1'b1;
        end else if (!(s_axis_tvalid && !input_fifo_full) && read_enable && !input_fifo_empty) begin
            input_fifo_count <= input_fifo_count - 1'b1;
        end
    end
end

// ============================================================================
// Output FIFO
// ============================================================================

reg [DATA_WIDTH-1:0] output_fifo [0:FIFO_DEPTH-1];
reg [$clog2(FIFO_DEPTH):0] output_fifo_count;
reg [$clog2(FIFO_DEPTH):0] output_fifo_wr_ptr;
reg [$clog2(FIFO_DEPTH):0] output_fifo_rd_ptr;
wire output_fifo_full;
wire output_fifo_empty;

// Output FIFO write
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        output_fifo_wr_ptr <= {$clog2(FIFO_DEPTH)+1{1'b0}};
        m_axis_tvalid <= 1'b0;
        m_axis_tdata <= {DATA_WIDTH{1'b0}};
        m_axis_tlast <= 1'b0;
        m_axis_tid <= {ID_WIDTH{1'b0}};
    end else begin
        if (data_valid && !output_fifo_full) begin
            output_fifo[output_fifo_wr_ptr[$clog2(FIFO_DEPTH)-1:0]] <= data_in;
            output_fifo_wr_ptr <= output_fifo_wr_ptr + 1'b1;
        end

        if (!output_fifo_empty && (m_axis_tready || !m_axis_tvalid)) begin
            m_axis_tdata <= output_fifo[output_fifo_rd_ptr[$clog2(FIFO_DEPTH)-1:0]];
            m_axis_tvalid <= 1'b1;
            m_axis_tlast <= data_last;
            m_axis_tid <= {ID_WIDTH{1'b0}};
            output_fifo_rd_ptr <= output_fifo_rd_ptr + 1'b1;
        end else begin
            m_axis_tvalid <= 1'b0;
        end
    end
end

// Output FIFO status
assign output_fifo_full = (output_fifo_count == FIFO_DEPTH);
assign output_fifo_empty = (output_fifo_count == 0);

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        output_fifo_count <= {$clog2(FIFO_DEPTH)+1{1'b0}};
    end else begin
        if (data_valid && !output_fifo_full && !(m_axis_tready || !m_axis_tvalid) && output_fifo_count > 0) begin
            output_fifo_count <= output_fifo_count + 1'b1;
        end else if (!(data_valid && !output_fifo_full) && (m_axis_tready || !m_axis_tvalid) && output_fifo_count > 0) begin
            output_fifo_count <= output_fifo_count - 1'b1;
        end
    end
end

endmodule // axi_stream_controller

// ============================================================================
// Power Management Unit
// ============================================================================

module power_manager #(
    parameter NUM_POWER_DOMAINS = 4
)(
    // Clock and Reset
    input  wire                 clk,
    input  wire                 rst_n,

    // Control
    input  wire [1:0]          power_state,     // 00=active, 01=idle, 10=sleep, 11=off
    input  wire [NUM_POWER_DOMAINS-1:0] domain_enable,

    // Power Domain Outputs
    output reg  [NUM_POWER_DOMAINS-1:0] pd_enable,
    output reg  [NUM_POWER_DOMAINS-1:0] pd_retention,
    output reg                          clk_gate,
    output reg                          isolation_enable,

    // Status
    output reg                          power_ready,
    output reg  [1:0]                  current_state
);

// Power state machine
localparam STATE_BITS = 3;
localparam PWR_IDLE  = 3'd0;
localparam PWR_ACTIVE = 3'd1;
localparam PWR_IDLE_PWR = 3'd2;
localparam PWR_SLEEP = 3'd3;
localparam PWR_WAKE = 3'd4;
localparam PWR_OFF = 3'd5;

reg [STATE_BITS-1:0] pwr_state;
reg [15:0] wake_counter;

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        pwr_state <= PWR_IDLE;
        pd_enable <= {NUM_POWER_DOMAINS{1'b0}};
        pd_retention <= {NUM_POWER_DOMAINS{1'b1}};
        clk_gate <= 1'b1;
        isolation_enable <= 1'b0;
        power_ready <= 1'b0;
        current_state <= 2'b00;
        wake_counter <= 16'h0;
    end else begin
        case (pwr_state)
            PWR_IDLE: begin
                current_state <= 2'b00;
                clk_gate <= 1'b1;
                pd_enable <= {NUM_POWER_DOMAINS{1'b0}};
                pd_retention <= {NUM_POWER_DOMAINS{1'b1}};
                power_ready <= 1'b0;

                if (power_state == 2'b00) begin
                    pwr_state <= PWR_ACTIVE;
                end else if (power_state == 2'b01) begin
                    pwr_state <= PWR_IDLE_PWR;
                end else if (power_state == 2'b10) begin
                    pwr_state <= PWR_SLEEP;
                end
            end

            PWR_ACTIVE: begin
                current_state <= 2'b00;
                clk_gate <= 1'b0;
                pd_enable <= domain_enable;
                pd_retention <= {NUM_POWER_DOMAINS{1'b0}};
                isolation_enable <= 1'b0;
                power_ready <= 1'b1;

                if (power_state != 2'b00) begin
                    pwr_state <= PWR_IDLE;
                end
            end

            PWR_IDLE_PWR: begin
                current_state <= 2'b01;
                clk_gate <= 1'b1;
                pd_enable <= {NUM_POWER_DOMAINS{1'b1}};
                pd_retention <= {NUM_POWER_DOMAINS{1'b0}};
                isolation_enable <= 1'b0;
                power_ready <= 1'b1;

                if (power_state == 2'b00) begin
                    pwr_state <= PWR_ACTIVE;
                end else if (power_state == 2'b10) begin
                    pwr_state <= PWR_SLEEP;
                end
            end

            PWR_SLEEP: begin
                current_state <= 2'b10;
                clk_gate <= 1'b1;
                pd_enable <= {NUM_POWER_DOMAINS{1'b0}};
                pd_retention <= {NUM_POWER_DOMAINS{1'b1}};
                isolation_enable <= 1'b1;
                power_ready <= 1'b0;

                if (power_state == 2'b00) begin
                    pwr_state <= PWR_WAKE;
                    wake_counter <= 16'h0;
                end
            end

            PWR_WAKE: begin
                current_state <= 2'b10;
                isolation_enable <= 1'b1;
                clk_gate <= 1'b1;

                if (wake_counter < 16'd100) begin
                    wake_counter <= wake_counter + 1'b1;
                end else begin
                    pwr_state <= PWR_ACTIVE;
                end
            end

            default: begin
                pwr_state <= PWR_IDLE;
            end
        endcase
    end
end

endmodule // power_manager
