// ============================================================================
// Activation Unit and Pooling Module
// ============================================================================
//
// Digital activation functions and pooling operations for IMC-TinyML
// ============================================================================

`timescale 1ns / 1ps

// ============================================================================
// Activation Functions
// ============================================================================

module activation_unit #(
    parameter DATA_WIDTH = 8
)(
    input  wire [DATA_WIDTH-1:0] data_in,
    input  wire [1:0]           act_type,     // 00=none, 01=relu, 10=relu6, 11=sigmoid
    output reg  [DATA_WIDTH-1:0] data_out
);

always @(*) begin
    case (act_type)
        2'b00: begin // None
            data_out = data_in;
        end

        2'b01: begin // ReLU
            data_out = (data_in[DATA_WIDTH-1]) ? {DATA_WIDTH{1'b0}} : data_in;
        end

        2'b10: begin // ReLU6
            if (data_in[DATA_WIDTH-1]) begin
                data_out = {DATA_WIDTH{1'b0}};
            end else if (data_in > 8'd6) begin
                data_out = 8'd6;
            end else begin
                data_out = data_in;
            end
        end

        2'b11: begin // Sigmoid (piecewise linear)
            if (data_in[DATA_WIDTH-1]) begin
                // Negative: output near 0
                if (data_in > 8'd192) begin  // x < -64
                    data_out = 8'd0;
                end else begin
                    // Linear: ~x/4 + 32
                    data_out = 8'd32 - {1'b0, data_in[6:0]};
                    if (data_out[DATA_WIDTH-1]) data_out = 8'd0;
                end
            end else begin
                // Positive: output near 255
                if (data_in > 8'd64) begin  // x > 64
                    data_out = 8'd255;
                end else begin
                    // Linear: ~x/4 + 224
                    data_out = 8'd224 + {1'b0, data_in[6:0]};
                    if (data_out > 8'd255) data_out = 8'd255;
                end
            end
        end

        default: data_out = data_in;
    endcase
end

endmodule // activation_unit

// ============================================================================
// Batch Normalization
// ============================================================================

module batch_norm #(
    parameter DATA_WIDTH = 8,
    parameter CHANNELS = 16
)(
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         enable,

    // Data
    input  wire [DATA_WIDTH-1:0]      data_in,
    input  wire                         valid_in,
    output reg  [DATA_WIDTH-1:0]      data_out,
    output reg                          valid_out,

    // Parameters (loaded from memory)
    input  wire signed [15:0]         scale      [0:CHANNELS-1],
    input  wire signed [15:0]         offset     [0:CHANNELS-1],
    input  wire signed [31:0]         mean       [0:CHANNELS-1],
    input  wire signed [31:0]         variance   [0:CHANNELS-1]
);

reg [3:0] channel_counter;
reg [DATA_WIDTH-1:0] data_delayed [0:3];
reg valid_delayed [0:3];

// Pipeline delay for parameters
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        channel_counter <= 4'h0;
        data_delayed[0] <= {DATA_WIDTH{1'b0}};
        data_delayed[1] <= {DATA_WIDTH{1'b0}};
        data_delayed[2] <= {DATA_WIDTH{1'b0}};
        data_delayed[3] <= {DATA_WIDTH{1'b0}};
        valid_delayed[0] <= 1'b0;
        valid_delayed[1] <= 1'b0;
        valid_delayed[2] <= 1'b0;
        valid_delayed[3] <= 1'b0;
    end else begin
        if (enable && valid_in) begin
            // Shift register
            data_delayed[3] <= data_delayed[2];
            data_delayed[2] <= data_delayed[1];
            data_delayed[1] <= data_delayed[0];
            data_delayed[0] <= data_in;

            valid_delayed[3] <= valid_delayed[2];
            valid_delayed[2] <= valid_delayed[1];
            valid_delayed[1] <= valid_delayed[0];
            valid_delayed[0] <= valid_in;

            // Channel counter
            if (channel_counter == CHANNELS - 1) begin
                channel_counter <= 4'h0;
            end else begin
                channel_counter <= channel_counter + 1'b1;
            end
        end

        if (!enable) begin
            channel_counter <= 4'h0;
            valid_delayed[0] <= 1'b0;
            valid_delayed[1] <= 1'b0;
            valid_delayed[2] <= 1'b0;
            valid_delayed[3] <= 1'b0;
        end
    end
end

// Batch norm computation
reg [31:0] normalized;
reg [31:0] scaled;
reg [31:0] shifted;

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        data_out <= {DATA_WIDTH{1'b0}};
        valid_out <= 1'b0;
    end else begin
        valid_out <= valid_delayed[3];

        if (valid_delayed[3]) begin
            // Simplified batch norm: (x - mean) * scale / sqrt(variance + eps) + offset
            // For simulation, use simplified version
            normalized <= {{24{data_in[DATA_WIDTH-1]}}, data_in};
            scaled <= normalized * scale[channel_counter];
            shifted <= scaled + offset[channel_counter];

            // Saturate to DATA_WIDTH bits
            if (shifted[31] && shifted[30:24] != 6'h3F) begin
                data_out <= {DATA_WIDTH{1'b1}};
            end else if (!shifted[31] && shifted[30:24] != 6'h00) begin
                data_out <= {DATA_WIDTH{1'b0}};
            end else begin
                data_out <= shifted[DATA_WIDTH+6-1:6];
            end
        end else begin
            data_out <= {DATA_WIDTH{1'b0}};
        end
    end
end

endmodule // batch_norm

// ============================================================================
// Pooling Unit
// ============================================================================

module pooling_unit #(
    parameter DATA_WIDTH = 8,
    parameter POOL_SIZE = 2
)(
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         enable,

    // Data
    input  wire [DATA_WIDTH-1:0]       data_in,
    input  wire                         valid_in,

    // Configuration
    input  wire [1:0]                  pool_type,     // 00=none, 01=max, 10=avg, 11=min
    input  wire [$clog2(POOL_SIZE)-1:0] pool_dim,     // Pool window size

    // Output
    output reg  [DATA_WIDTH-1:0]       data_out,
    output reg                          valid_out
);

localparam WINDOW_SIZE = POOL_SIZE * POOL_SIZE;

reg [DATA_WIDTH-1:0] window [0:WINDOW_SIZE-1];
reg [2*$clog2(WINDOW_SIZE):0] pool_accum;
reg [$clog2(WINDOW_SIZE)-1:0] window_count;
reg [DATA_WIDTH-1:0] pool_max;
reg [DATA_WIDTH-1:0] pool_min;
reg [2*$clog2(WINDOW_SIZE):0] pool_sum;
reg computing;

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        integer i;
        for (i = 0; i < WINDOW_SIZE; i = i + 1) begin
            window[i] <= {DATA_WIDTH{1'b0}};
        end
        window_count <= {$clog2(WINDOW_SIZE){1'b0}};
        pool_max <= {DATA_WIDTH{1'b0}};
        pool_min <= {DATA_WIDTH{1'b1}};
        pool_sum <= {(2*$clog2(WINDOW_SIZE)){1'b0}};
        data_out <= {DATA_WIDTH{1'b0}};
        valid_out <= 1'b0;
        computing <= 1'b0;
    end else begin
        valid_out <= 1'b0;

        if (enable && valid_in) begin
            // Store in window
            window[window_count] <= data_in;

            // Update accumulators
            if (data_in > pool_max) pool_max <= data_in;
            if (data_in < pool_min) pool_min <= data_in;
            pool_sum <= pool_sum + {{(($clog2(WINDOW_SIZE))){data_in[DATA_WIDTH-1]}}, data_in};

            // Increment counter
            window_count <= window_count + 1'b1;

            // Check if window is full
            if (window_count == WINDOW_SIZE - 1) begin
                computing <= 1'b1;
            end

            // Output result
            if (computing) begin
                case (pool_type)
                    2'b00: data_out <= data_in;      // No pooling
                    2'b01: data_out <= pool_max;    // Max pooling
                    2'b10: begin                     // Average pooling
                        data_out <= pool_sum[$clog2(WINDOW_SIZE)+DATA_WIDTH-1:$clog2(WINDOW_SIZE)];
                    end
                    2'b11: data_out <= pool_min;    // Min pooling
                    default: data_out <= data_in;
                endcase
                valid_out <= 1'b1;

                // Reset for next window
                window_count <= {$clog2(WINDOW_SIZE){1'b0}};
                pool_max <= {DATA_WIDTH{1'b0}};
                pool_min <= {DATA_WIDTH{1'b1}};
                pool_sum <= {(2*$clog2(WINDOW_SIZE)){1'b0}};
                computing <= 1'b0;
            end
        end
    end
end

endmodule // pooling_unit

// ============================================================================
// Softmax Unit
// ============================================================================

module softmax_unit #(
    parameter DATA_WIDTH = 8,
    parameter NUM_CLASSES = 12
)(
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         enable,

    // Data
    input  wire [DATA_WIDTH-1:0]       logits [0:NUM_CLASSES-1],
    input  wire                         valid_in,

    // Output
    output reg  [15:0]                  probabilities [0:NUM_CLASSES-1],
    output reg                          valid_out
);

reg [DATA_WIDTH-1:0] max_logit;
reg [2*DATA_WIDTH:0] exp_values [0:NUM_CLASSES-1];
reg [2*DATA_WIDTH+7:0] exp_sum;
reg [31:0] inverse_sum;

// Find maximum logit
integer i;
always @(*) begin
    max_logit = logits[0];
    for (i = 1; i < NUM_CLASSES; i = i + 1) begin
        if (logits[i] > max_logit) begin
            max_logit = logits[i];
        end
    end
end

// Compute exponentials (simplified)
reg [2*DATA_WIDTH:0] exp_val;
always @(*) begin
    for (i = 0; i < NUM_CLASSES; i = i + 1) begin
        // exp(x - max) to prevent overflow
        if (max_logit - logits[i] > 8'd10) begin
            exp_values[i] = 0;
        end else begin
            // Simplified exponential approximation
            exp_values[i] = 16'h1000 >> (max_logit - logits[i]);
        end
    end
end

// Compute sum of exponentials
reg [2*DATA_WIDTH+7:0] sum_accum;
always @(*) begin
    sum_accum = 0;
    for (i = 0; i < NUM_CLASSES; i = i + 1) begin
        sum_accum = sum_accum + exp_values[i];
    end
end

// Output probabilities
integer j;
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        valid_out <= 1'b0;
        for (j = 0; j < NUM_CLASSES; j = j + 1) begin
            probabilities[j] <= 16'h0;
        end
    end else begin
        valid_out <= 1'b0;

        if (enable && valid_in) begin
            // Compute probabilities
            for (j = 0; j < NUM_CLASSES; j = j + 1) begin
                if (sum_accum > 0) begin
                    probabilities[j] <= (exp_values[j] * 16'd1000) / sum_accum[2*DATA_WIDTH+7:2];
                end else begin
                    probabilities[j] <= 16'd0;
                end
            end
            valid_out <= 1'b1;
        end
    end
end

endmodule // softmax_unit

// ============================================================================
// Global Average Pooling
// ============================================================================

module global_avg_pool #(
    parameter DATA_WIDTH = 8,
    parameter INPUT_SIZE = 49
)(
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         enable,

    // Data
    input  wire [DATA_WIDTH-1:0]       data_in,
    input  wire                         valid_in,

    // Output
    output reg  [DATA_WIDTH+7:0]       avg_out,
    output reg                          valid_out
);

reg [31:0] sum;
reg [$clog2(INPUT_SIZE)-1:0] count;

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        sum <= 32'h0;
        count <= {$clog2(INPUT_SIZE){1'b0}};
        avg_out <= {DATA_WIDTH+8{1'b0}};
        valid_out <= 1'b0;
    end else begin
        valid_out <= 1'b0;

        if (enable && valid_in) begin
            sum <= sum + {{24{data_in[DATA_WIDTH-1]}}, data_in};
            count <= count + 1'b1;

            if (count == INPUT_SIZE - 1) begin
                avg_out <= sum[$clog2(INPUT_SIZE)+DATA_WIDTH-1:$clog2(INPUT_SIZE)];
                sum <= 32'h0;
                count <= {$clog2(INPUT_SIZE){1'b0}};
                valid_out <= 1'b1;
            end
        end
    end
end

endmodule // global_avg_pool
