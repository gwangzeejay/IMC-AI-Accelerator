`timescale 1ns/1ps
module tb_arithmetic;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,start=0,operand_valid=0;
    reg [8:0] terms=0;
    reg signed [31:0] bias=0;
    reg signed [7:0] activation=0,weight=0,zp=0;
    wire ready,done,mac_error;wire signed [31:0] accumulator;wire [8:0] count;
    recap_int8_mac mac(clk,rst_n,start,terms,bias,operand_valid,ready,activation,weight,zp,accumulator,done,mac_error,count);
    reg signed [31:0] qa,qm;reg signed [5:0] qs;reg signed [7:0] qz,qmin,qmax;
    wire signed [7:0] qr;wire qe;
    recap_requantize quant(qa,qm,qs,qz,qmin,qmax,qr,qe);
    integer fd,rc,n,b,z,expected,expected_error,a,w,i,cases=0,qcases=0,m,s,lo,hi;
    string macfile,qfile;
    initial begin
        if(!$value$plusargs("MAC=%s",macfile) || !$value$plusargs("QUANT=%s",qfile)) $fatal(1,"missing arithmetic vectors");
        fd=$fopen(macfile,"r");if(!fd) $fatal(1,"missing MAC file");
        while(!$feof(fd)) begin
            rc=$fscanf(fd,"%d %d %d %d %d\n",n,b,z,expected,expected_error);if(rc!=5) $fatal(1,"bad MAC row");
            @(negedge clk);rst_n=0;start=0;operand_valid=0;
            repeat(2) @(negedge clk);rst_n=1;terms=n;bias=b;zp=z;start=1;
            @(negedge clk);start=0;
            for(i=0;i<n;i=i+1) begin
                rc=$fscanf(fd,"%d %d\n",a,w);if(rc!=2) $fatal(1,"bad operand row");
                activation=a;weight=w;operand_valid=!mac_error;
                @(negedge clk);
                if(!expected_error && i<n-1 && done) $fatal(1,"MAC completed early");
            end
            operand_valid=0;
            if(mac_error!==expected_error[0]) $fatal(1,"MAC error flag mismatch case %0d",cases);
            if(!expected_error && (!done || accumulator!==expected || count!=n))
                $fatal(1,"MAC mismatch case %0d n %0d count %0d got %0d expected %0d",cases,n,count,accumulator,expected);
            cases=cases+1;
        end
        $fclose(fd);
        fd=$fopen(qfile,"r");if(!fd) $fatal(1,"missing requant file");
        while(!$feof(fd)) begin
            rc=$fscanf(fd,"%d %d %d %d %d %d %d %d\n",a,m,s,z,lo,hi,expected,expected_error);if(rc!=8) $fatal(1,"bad requant row");
            qa=a;qm=m;qs=s;qz=z;qmin=lo;qmax=hi;#1;
            if(qe!==expected_error[0] || (!expected_error && $signed(qr)!=expected))
                $fatal(1,"requant mismatch case %0d a %0d m %0d shift %0d got %0d err%0d expected %0d err%0d",qcases,a,m,s,$signed(qr),qe,expected,expected_error);
            qcases=qcases+1;
        end
        $fclose(fd);$display("PASS arithmetic mac_cases=%0d quant_cases=%0d",cases,qcases);$finish;
    end
endmodule
