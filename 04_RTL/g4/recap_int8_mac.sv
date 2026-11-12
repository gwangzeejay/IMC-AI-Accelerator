// Scalar reference backend, NOT a physical SRAM-CIM macro. No wrapping math.
module recap_int8_mac #(parameter integer MAX_TERMS=256,
    parameter integer CW=$clog2(MAX_TERMS+1))(
    input wire clk,input wire rst_n,input wire start,input wire [CW-1:0] terms,
    input wire signed [31:0] bias,input wire operand_valid,output wire operand_ready,
    input wire signed [7:0] activation,input wire signed [7:0] weight,
    input wire signed [7:0] zero_point,
    output reg signed [31:0] accumulator,output reg done,output reg error,
    output reg [CW-1:0] count
);
    reg busy;reg [CW-1:0] limit;
    wire signed [8:0] adjusted=$signed({activation[7],activation})-$signed({zero_point[7],zero_point});
    wire signed [16:0] product=adjusted*weight;
    wire signed [32:0] sum=$signed({accumulator[31],accumulator})+$signed({{16{product[16]}},product});
    assign operand_ready=busy && !error;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin accumulator<=0;done<=0;error<=0;count<=0;busy<=0;limit<=0;end
        else begin
            done<=0;
            if(start && !busy) begin
                if(terms==0 || terms>MAX_TERMS) error<=1;
                else begin accumulator<=bias;count<=0;limit<=terms;busy<=1;error<=0;end
            end else if(operand_valid && operand_ready) begin
                if(sum[32]!=sum[31]) begin error<=1;busy<=0;end
                else begin
                    accumulator<=sum[31:0];count<=count+1;
                    if(count+1==limit) begin done<=1;busy<=0;end
                end
            end
        end
    end
endmodule
