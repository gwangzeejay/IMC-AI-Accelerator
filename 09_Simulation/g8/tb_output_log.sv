`timescale 1ns/1ps
module tb_output_log;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,cmd_valid=0,ready=0;
    reg [31:0] base=32;
    reg [15:0] payload_length=16;
    wire cmd_ready,valid,write,done,error;
    wire [16:0] source_addr;wire [31:0] addr;wire [7:0] data;
    reg [7:0] source[0:139];reg [7:0] memory[0:255];
    integer i,cut,acks,cycles,seed=731,stall_mode;
    reg [31:0] held_addr;reg [7:0] held_data;reg pending;
    reg [1023:0] source_file;
    recap_output_log_commit dut(clk,rst_n,cmd_valid,cmd_ready,base,payload_length,
        source_addr,source[source_addr],valid,write,addr,data,ready,done,error);
    always @(negedge clk) begin
        if(!rst_n) ready=0;
        else if(stall_mode==0) ready=1;
        else ready=($random(seed)&3)!=0;
    end
    always @(posedge clk) begin
        if(!rst_n) begin pending=0;end
        else begin
            if(pending && (!valid || addr!==held_addr || data!==held_data)) $fatal(1,"unstable stalled request");
            pending=valid && !ready;held_addr=addr;held_data=data;
            if(valid && ready) begin
                if(!write || addr<32 || addr>=172) $fatal(1,"invalid write address");
                memory[addr]=data;acks=acks+1;
            end
        end
    end
    task reset_dut;
        begin @(negedge clk);rst_n=0;cmd_valid=0;repeat(2) @(negedge clk);rst_n=1;end
    endtask
    task start_command;
        begin @(negedge clk);cmd_valid=1;@(negedge clk);cmd_valid=0;end
    endtask
    task finish_command;
        begin
            cycles=0;
            while(!done && cycles<2000) begin @(negedge clk);cycles=cycles+1;end
            if(!done || error) $fatal(1,"commit timeout/error");
            for(i=0;i<140;i=i+1) if(memory[32+i]!==source[i]) $fatal(1,"final byte mismatch");
        end
    endtask
    initial begin
        if(!$value$plusargs("SOURCE=%s",source_file)) $fatal(1,"SOURCE required");
        $readmemh(source_file,source);
        for(stall_mode=0;stall_mode<2;stall_mode=stall_mode+1) begin
            for(cut=0;cut<=141;cut=cut+1) begin
                for(i=0;i<256;i=i+1) memory[i]=0;
                reset_dut();acks=0;start_command();
                cycles=0;
                while(acks<cut && cycles<2000) begin @(negedge clk);cycles=cycles+1;end
                if(acks!=cut) $fatal(1,"bad cut count");
                // Capture durable bytes at the reset boundary for Python CRC/scan.
                $write("CUT %0d %0d ",stall_mode,cut);
                for(i=0;i<256;i=i+1) $write("%02x",memory[i]);
                $write("\n");
                reset_dut();acks=0;start_command();finish_command();
            end
        end
        // Empty/overflow commands must emit no writes.
        reset_dut();payload_length=0;acks=0;start_command();
        if(!error || acks!=0) $fatal(1,"zero-length command accepted");
        payload_length=16;base=32'hfffffff0;start_command();
        if(!error || acks!=0) $fatal(1,"overflow command accepted");
        $display("PASS_OUTPUT_LOG cuts=284 invalid=2 stalls=2");$finish;
    end
endmodule
