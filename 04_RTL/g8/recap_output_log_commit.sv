// Append one pre-encoded binary-v1 output record directly to a durable log.
// Host supplies HEADER(124 bytes)+payload with CRC/identity already encoded.
// source_data must be stable for source_addr while mem_valid is stalled.
// mem_ready acknowledges persistence; one atomic byte marker publishes record.
// This primitive does not implement FRAM SPI, CRC generation, or graph control.
module recap_output_log_commit #(
    parameter integer ADDR_WIDTH=32,
    parameter integer HEADER_BYTES=124
)(
    input wire clk, input wire rst_n,
    input wire cmd_valid, output wire cmd_ready,
    input wire [ADDR_WIDTH-1:0] cmd_base,
    input wire [15:0] cmd_payload_length,
    output reg [16:0] source_addr, input wire [7:0] source_data,
    output reg mem_valid, output wire mem_write,
    output reg [ADDR_WIDTH-1:0] mem_addr, output reg [7:0] mem_wdata,
    input wire mem_ready,
    output reg done, output reg error
);
    localparam IDLE=0, INVALIDATE=1, PAYLOAD=2, META=3, PUBLISH=4;
    reg [2:0] state;
    reg [ADDR_WIDTH-1:0] base;
    reg [15:0] length;
    reg [16:0] cursor;
    wire [ADDR_WIDTH:0] end_addr={1'b0,cmd_base}+HEADER_BYTES+cmd_payload_length-1;
    assign cmd_ready=state==IDLE;
    assign mem_write=mem_valid;
    always @* begin
        mem_valid=state!=IDLE;mem_addr=base;mem_wdata=0;source_addr=0;
        case(state)
            PAYLOAD:begin
                source_addr=HEADER_BYTES+cursor;mem_addr=base+HEADER_BYTES+cursor;mem_wdata=source_data;
            end
            META:begin source_addr=cursor;mem_addr=base+cursor;mem_wdata=source_data;end
            PUBLISH:mem_wdata=8'ha5;
            default:begin end
        endcase
    end
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin state<=IDLE;base<=0;length<=0;cursor<=0;done<=0;error<=0;end
        else begin
            done<=0;error<=0;
            case(state)
                IDLE:if(cmd_valid) begin
                    if(cmd_payload_length==0 || end_addr[ADDR_WIDTH]) error<=1;
                    else begin base<=cmd_base;length<=cmd_payload_length;cursor<=0;state<=INVALIDATE;end
                end
                INVALIDATE:if(mem_ready) begin cursor<=0;state<=PAYLOAD;end
                PAYLOAD:if(mem_ready) begin
                    if(cursor==length-1) begin cursor<=1;state<=META;end
                    else cursor<=cursor+1;
                end
                META:if(mem_ready) begin
                    if(cursor==HEADER_BYTES-1) state<=PUBLISH;
                    else cursor<=cursor+1;
                end
                PUBLISH:if(mem_ready) begin done<=1;state<=IDLE;end
                default:begin state<=IDLE;error<=1;end
            endcase
        end
    end
endmodule
