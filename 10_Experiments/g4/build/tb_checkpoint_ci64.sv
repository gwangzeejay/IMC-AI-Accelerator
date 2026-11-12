`timescale 1ns/1ps
module tb_checkpoint;
    `include "params.vh"
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,cmd_valid=0,cmd_save_z=0,cmd_keep_ps=0,cmd_output=0;
    reg [31:0] cmd_offset=0;
    wire cmd_ready,mem_valid,mem_write,boot_done,commit_done,protocol_error,active_valid,active_slot;
    wire [15:0] payload_addr,mem_addr,restore_addr;
    wire [7:0] mem_wdata,restore_data;
    reg [7:0] payload_rdata;
    wire [31:0] committed_offset,active_generation;
    wire [2:0] active_flags;wire [3:0] phase;
    reg restore_ready=1;
    reg [7:0] nvm[0:2*SLOT];
    reg pending=0;integer delay_count=0;
    wire mem_ready=rst_n && pending && delay_count==0;
    wire [7:0] mem_rdata=nvm[mem_addr];
    recap_checkpoint_ctrl #(.Z_BYTES(ZB),.PS_BYTES(PB),.OUT_BYTES(OB),.SLOT_BYTES(SLOT)) dut(
        .clk(clk),.rst_n(rst_n),.model_id(MODEL_ID),.input_id(INPUT_ID),.descriptor_id(DESCRIPTOR_ID),
        .cmd_valid(cmd_valid),.cmd_ready(cmd_ready),.cmd_save_z(cmd_save_z),.cmd_keep_ps(cmd_keep_ps),.cmd_output(cmd_output),.cmd_offset(cmd_offset),
        .payload_addr(payload_addr),.payload_rdata(payload_rdata),.mem_valid(mem_valid),.mem_write(mem_write),.mem_addr(mem_addr),.mem_wdata(mem_wdata),
        .mem_ready(mem_ready),.mem_rdata(mem_rdata),.restore_valid(restore_valid),.restore_ready(restore_ready),.restore_addr(restore_addr),.restore_data(restore_data),
        .boot_done(boot_done),.commit_done(commit_done),.protocol_error(protocol_error),.active_valid(active_valid),.active_slot(active_slot),
        .active_generation(active_generation),.committed_offset(committed_offset),.active_flags(active_flags),.dbg_phase(phase));
    reg [7:0] x[0:IH*IW*CI-1],wd[0:9*CI-1],wp[0:CI*CO-1],gold[0:OB-1];
    reg signed [31:0] bd[0:CI-1],bp[0:CO-1],dm[0:CI-1],ds[0:CI-1],pm[0:CO-1],pshift[0:CO-1];
    reg [7:0] z[0:ZB-1],out_data[0:OB-1];reg signed [31:0] sums[0:PIXELS*CO-1];
    reg z_valid=0,ps_valid=0,backend_initialized=0;
    integer volatile_offset=0;
    integer cycle=0,ack_count=0,case_id=-1,logfd,casefd,scan_status;
    integer save_flag,keep_flag,cut1,cut2,cut_mode,persist_pending,seed,stall_mode,switch_policy,expect_error;
    integer fault_index,loss_count,current_cut,reset_ticks,i,p,c,k,ky,kx,acc,stop_channel;
    integer last_offset=0,last_generation=0,last_phase=0;
    integer blocked_cycles=0;
    reg waiting=0,last_boot=0;reg [24:0] held_request;
    reg [31:0] rng;
    string casepath,tracepath,initpath;

    function automatic integer requant(input integer value,input integer multiplier,input integer shift,
                                      input integer zero_point,input integer amin,input integer amax);
        reg signed [63:0] left,product,nudge,high;
        integer exponent,mask,remainder,threshold,result;
        begin
            left=$signed(value);
            if(shift>0) left=left<<<shift;
            if(left>64'sd2147483647 || left< -64'sd2147483648) $fatal(1,"requant shift overflow");
            if(left== -64'sd2147483648 && multiplier==32'sh80000000) high=2147483647;
            else begin
                product=left*$signed(multiplier);
                nudge=product>=0?64'sd1073741824:-64'sd1073741823;
                high=(product+nudge)/64'sd2147483648;
            end
            exponent=shift<0?-shift:0;mask=(64'd1<<exponent)-1;
            remainder=$signed(high)&mask;threshold=(mask>>1)+(high<0);
            result=$signed(high)>>>exponent;
            if(remainder>threshold) result=result+1;
            result=result+zero_point;
            if(result<amin) result=amin;if(result>amax) result=amax;
            requant=result;
        end
    endfunction
    task automatic compute_dw;
        integer pixel,ch,yy,xx,a;
        begin
            for(pixel=0;pixel<PIXELS;pixel=pixel+1)
                for(ch=0;ch<CI;ch=ch+1) begin
                    a=bd[ch];
                    for(yy=0;yy<3;yy=yy+1) for(xx=0;xx<3;xx=xx+1)
                        a=a+($signed(x[((pixel/OW+yy)*IW+pixel%OW+xx)*CI+ch])-DW_INPUT_ZERO_POINT)*$signed(wd[(yy*3+xx)*CI+ch]);
                    z[pixel*CI+ch]=requant(a,dm[ch],ds[ch],DW_OUTPUT_ZERO_POINT,DW_ACTIVATION_MIN,DW_ACTIVATION_MAX);
                end
            z_valid=1;
        end
    endtask
    task automatic compute_pw(input integer first,input integer last);
        integer pixel,ch,ic,a;
        begin
            if(!ps_valid) begin
                for(pixel=0;pixel<PIXELS;pixel=pixel+1) for(ch=0;ch<CO;ch=ch+1) sums[pixel*CO+ch]=bp[ch];
                ps_valid=1;
            end
            for(pixel=0;pixel<PIXELS;pixel=pixel+1) for(ch=0;ch<CO;ch=ch+1) begin
                a=sums[pixel*CO+ch];
                for(ic=first;ic<last;ic=ic+1) a=a+($signed(z[pixel*CI+ic])-PW_INPUT_ZERO_POINT)*$signed(wp[ic*CO+ch]);
                sums[pixel*CO+ch]=a;
                if(last==64) out_data[pixel*CO+ch]=requant(a,pm[ch],pshift[ch],PW_OUTPUT_ZERO_POINT,PW_ACTIVATION_MIN,PW_ACTIVATION_MAX);
            end
        end
    endtask
    always @* begin
        payload_rdata=0;
        if(payload_addr<ZB) payload_rdata=z[payload_addr];
        else if(payload_addr<ZB+PB) payload_rdata=sums[(payload_addr-ZB)/4] >> (8*((payload_addr-ZB)%4));
        else if(payload_addr<ZB+PB+OB) payload_rdata=out_data[payload_addr-ZB-PB];
    end
    always @(negedge rst_n) begin
        pending=0;waiting=0;last_boot=0;last_offset=0;last_generation=0;blocked_cycles=0;
        z_valid=0;ps_valid=0;backend_initialized=0;volatile_offset=0;cmd_valid=0;
        for(i=0;i<ZB;i=i+1) z[i]=0;
        for(i=0;i<PIXELS*CO;i=i+1) sums[i]=0;
        for(i=0;i<OB;i=i+1) out_data[i]=0;
    end
    always @(negedge clk) begin
        if(!rst_n) pending=0;
        else if(!pending && mem_valid) begin
            pending=1;rng=rng*32'd1664525+32'd1013904223;
            delay_count=stall_mode?1+(rng%3):0;
        end else if(pending && delay_count>0) delay_count=delay_count-1;
        restore_ready=!stall_mode || cycle%3!=0;
    end
    always @(posedge clk) begin
        cycle=cycle+1;
        if(rst_n) begin
            if(waiting && (!mem_valid || {mem_write,mem_addr,mem_wdata}!==held_request)) $fatal(1,"unstable memory request");
            waiting=mem_valid&&!mem_ready;held_request={mem_write,mem_addr,mem_wdata};
            if(mem_valid && !mem_ready) blocked_cycles=blocked_cycles+1;
            if(mem_valid && mem_addr>2*SLOT) $fatal(1,"memory address out of bounds");
            if(cmd_ready && !boot_done) $fatal(1,"command before boot completion");
            if(mem_valid && mem_ready) begin
                $fdisplay(logfd,"T %0d %0d %0d %0d %0d %0d %0d",case_id,cycle,mem_write,mem_addr,mem_write?mem_wdata:mem_rdata,phase,blocked_cycles);
                blocked_cycles=0;
                if(mem_write) begin
                    if(phase==9 && active_valid && mem_addr==active_slot*SLOT) $fatal(1,"overwriting active slot");
                    if(phase==13 && !active_flags[2]) $fatal(1,"frontier before output publication");
                    nvm[mem_addr]=mem_wdata;
                end
                ack_count=ack_count+1;pending=0;
            end
            if(restore_valid && restore_ready) begin
                $fdisplay(logfd,"R %0d %0d %0d %0d",case_id,cycle,restore_addr,restore_data);
                if(active_flags[2]) out_data[restore_addr]<=restore_data;
                else if(active_flags[0] && restore_addr<ZB) z[restore_addr]<=restore_data;
                else sums[(restore_addr-(active_flags[0]?ZB:0))/4][8*((restore_addr-(active_flags[0]?ZB:0))%4)+:8]<=restore_data;
            end
            if(cmd_valid && cmd_ready) $fdisplay(logfd,"C %0d %0d %0d %0d %0d %0d",case_id,cycle,cmd_save_z,cmd_keep_ps,cmd_output,cmd_offset);
        end
        last_phase=phase;
        #1;
        if(rst_n) begin
            if((committed_offset!=last_offset || active_generation!=last_generation) && last_phase!=4 && last_phase!=12)
                $fatal(1,"durable state promoted before publish");
            last_offset=committed_offset;last_generation=active_generation;
            if(boot_done && !last_boot) $fdisplay(logfd,"B %0d %0d %0d %0d %0d",case_id,cycle,committed_offset,active_flags,active_generation);
            last_boot=boot_done;
            if(commit_done) $fdisplay(logfd,"D %0d %0d %0d %0d %0d",case_id,cycle,committed_offset,active_flags,active_generation);
        end
    end
    task automatic cold_loss;
        begin
            if(cut_mode==1 && pending && mem_valid && mem_write && persist_pending) begin
                nvm[mem_addr]=mem_wdata;
                $fdisplay(logfd,"U %0d %0d %0d %0d",case_id,cycle,mem_addr,mem_wdata);
            end
            $fdisplay(logfd,"X %0d %0d %0d",case_id,cycle,phase);
            rst_n=0;loss_count=loss_count+1;fault_index=fault_index+1;
            repeat(3) @(negedge clk);#1;rst_n=1;
        end
    endtask
    reg fire,finished;
    initial begin
        $readmemh({VECTOR_DIR,"x.hex"},x);$readmemh({VECTOR_DIR,"wd.hex"},wd);$readmemh({VECTOR_DIR,"wp.hex"},wp);$readmemh({VECTOR_DIR,"y.hex"},gold);
        $readmemh({VECTOR_DIR,"bd.hex"},bd);$readmemh({VECTOR_DIR,"bp.hex"},bp);
        $readmemh({VECTOR_DIR,"dw_multipliers.hex"},dm);$readmemh({VECTOR_DIR,"dw_shifts.hex"},ds);
        $readmemh({VECTOR_DIR,"pw_multipliers.hex"},pm);$readmemh({VECTOR_DIR,"pw_shifts.hex"},pshift);
        if(!$value$plusargs("CASES=%s",casepath) || !$value$plusargs("TRACE=%s",tracepath)) $fatal(1,"missing arguments");
        if(!$value$plusargs("INIT=%s",initpath)) initpath="";
        casefd=$fopen(casepath,"r");logfd=$fopen(tracepath,"w");
        if(!casefd || !logfd) $fatal(1,"cannot open files");
        while(!$feof(casefd)) begin
            scan_status=$fscanf(casefd,"%d %d %d %d %d %d %d %d %d %d %d\n",case_id,save_flag,keep_flag,cut1,cut2,cut_mode,persist_pending,seed,stall_mode,switch_policy,expect_error);
            if(scan_status!=11) $fatal(1,"invalid case row");
            @(negedge clk);#1;rst_n=0;cmd_valid=0;cycle=0;ack_count=0;fault_index=0;loss_count=0;rng=seed;finished=0;
            for(k=0;k<=2*SLOT;k=k+1) nvm[k]=0;
            if(initpath!="") $readmemh(initpath,nvm);
            $fdisplay(logfd,"S %0d",case_id);
            repeat(3) @(negedge clk);#1;rst_n=1;
            while(!finished) begin
                @(negedge clk);#1;
                if(cycle>200000) $fatal(1,"timeout case %0d",case_id);
                current_cut=fault_index==0?cut1:cut2;fire=0;
                if(fault_index<2 && current_cut>=0) begin
                    if(current_cut>=100000) fire=phase==current_cut/100000 && dut.cursor==current_cut%100000;
                    else if(cut_mode==0) fire=ack_count==current_cut+1;
                    else fire=ack_count==current_cut && pending && mem_valid && !mem_ready;
                end
                if(fire) cold_loss();
                else if(protocol_error) begin
                    if(!expect_error) $fatal(1,"protocol error case %0d",case_id);
                    $fdisplay(logfd,"E %0d %0d",case_id,cycle);finished=1;
                end else if(boot_done && active_flags[2] && nvm[2*SLOT]==1) begin
                    if(expect_error) $fatal(1,"expected error absent");
                    for(k=0;k<OB;k=k+1) if(out_data[k]!==gold[k]) $fatal(1,"output mismatch case %0d index %0d got %0d expected %0d",case_id,k,out_data[k],gold[k]);
                    $fdisplay(logfd,"P %0d %0d %0d %0d",case_id,cycle,loss_count,ack_count);finished=1;
                end else if(boot_done && cmd_ready && !cmd_valid) begin
                    if(!backend_initialized) begin
                        z_valid=active_flags[0];ps_valid=active_flags[1];volatile_offset=ps_valid?committed_offset:0;backend_initialized=1;
                    end
                    if(!z_valid) compute_dw();
                    stop_channel=volatile_offset+64;if(stop_channel>64) stop_channel=64;
                    compute_pw(volatile_offset,stop_channel);volatile_offset=stop_channel;
                    cmd_save_z=save_flag;cmd_keep_ps=keep_flag;
                    if(switch_policy) cmd_keep_ps=volatile_offset!=32;
                    cmd_output=volatile_offset==64;cmd_offset=expect_error==2?65:volatile_offset;cmd_valid=1;
                end else if(cmd_valid && !cmd_ready) cmd_valid=0;
            end
        end
        $fclose(casefd);$fclose(logfd);$display("PASS checkpoint testbench");$finish;
    end
endmodule
