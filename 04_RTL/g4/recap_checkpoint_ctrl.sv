// Binary-v1 refinement of the G2/G3 copy-on-write semantics. One outstanding
// byte request; mem_ready means read completion / write persistence ACK.
// A byte commit marker is assumed atomic old-or-new across power failure.
module recap_checkpoint_ctrl #(
    parameter integer Z_BYTES=128, PS_BYTES=32, OUT_BYTES=8,
    parameter integer CHANNELS=64, SLOT_BYTES=512,
    parameter integer HEADER_BYTES=124,
    parameter integer MAX_PAYLOAD=Z_BYTES+PS_BYTES+OUT_BYTES
)(
    input wire clk, input wire rst_n,
    input wire [255:0] model_id, input wire [255:0] input_id, input wire [255:0] descriptor_id,
    input wire cmd_valid, output wire cmd_ready,
    input wire cmd_save_z, input wire cmd_keep_ps, input wire cmd_output,
    input wire [31:0] cmd_offset,
    output reg [15:0] payload_addr, input wire [7:0] payload_rdata,
    output reg mem_valid, output reg mem_write, output reg [15:0] mem_addr,
    output reg [7:0] mem_wdata, input wire mem_ready, input wire [7:0] mem_rdata,
    output reg restore_valid, input wire restore_ready,
    output reg [15:0] restore_addr, output reg [7:0] restore_data,
    output reg boot_done, output reg commit_done, output reg protocol_error,
    output reg active_valid, output reg active_slot, output reg [31:0] active_generation,
    output reg [31:0] committed_offset, output reg [2:0] active_flags,
    output wire [3:0] dbg_phase
);
    localparam [3:0] BOOT_READ=0, VALIDATE_START=1, META_CHECK=2, PAYLOAD_CHECK=3,
        SELECT_SLOT=4, RESTORE=5, IDLE=6, STAGE=7, BUILD_HEADER=8,
        INVALIDATE=9, WRITE_PAYLOAD=10, WRITE_HEADER=11, PUBLISH=12, FRONTIER=13, ERROR=14;
    reg [3:0] state;
    assign dbg_phase=state;
    assign cmd_ready=state==IDLE && !protocol_error && !active_flags[2];
    reg [7:0] scan [0:2*SLOT_BYTES];
    reg [7:0] durable [0:MAX_PAYLOAD-1];
    reg [7:0] staged [0:MAX_PAYLOAD-1];
    reg [7:0] header [0:HEADER_BYTES-1];
    reg [1:0] valid_slots;
    reg [31:0] gen0,gen1;
    reg candidate_slot, target_slot;
    reg [2:0] next_flags;
    reg [31:0] next_offset,next_generation;
    reg use_new_z,use_new_ps;
    integer cursor,payload_length,active_length,candidate_length;
    reg [31:0] crc;
    reg [31:0] payload_crc;
    integer base;

    function automatic [31:0] crc_byte(input [31:0] previous,input [7:0] value);
        reg [31:0] v; integer b;
        begin
            v=previous ^ {24'b0,value};
            for(b=0;b<8;b=b+1) v=v[0] ? ((v>>1)^32'hedb88320) : (v>>1);
            crc_byte=v;
        end
    endfunction
    function automatic [31:0] word_at(input integer addr);
        begin word_at={scan[addr+3],scan[addr+2],scan[addr+1],scan[addr]}; end
    endfunction
    function automatic [15:0] half_at(input integer addr);
        begin half_at={scan[addr+1],scan[addr]}; end
    endfunction
    function automatic [255:0] id_at(input integer addr);
        integer b;
        begin for(b=0;b<32;b=b+1) id_at[8*b+:8]=scan[addr+b]; end
    endfunction
    function automatic header_legal(input integer b);
        reg [2:0] flags; integer length;
        begin
            flags=scan[b+2][2:0];
            length=half_at(b+108)+half_at(b+110)+half_at(b+112);
            header_legal=scan[b]==8'ha5 && scan[b+1]==1 && scan[b+2][7:3]==0 && scan[b+3]==0 &&
                word_at(b+4)!=0 && id_at(b+8)==model_id && id_at(b+40)==input_id && id_at(b+72)==descriptor_id &&
                half_at(b+108)==(flags[0]?Z_BYTES:0) && half_at(b+110)==(flags[1]?PS_BYTES:0) &&
                half_at(b+112)==(flags[2]?OUT_BYTES:0) && half_at(b+114)==0 &&
                length<=MAX_PAYLOAD && HEADER_BYTES+length<=SLOT_BYTES && word_at(b+104)<=CHANNELS &&
                (flags[1] || flags[2] || word_at(b+104)==0) &&
                (!flags[2] || (flags==4 && word_at(b+104)==CHANNELS));
        end
    endfunction
    function automatic [7:0] header_byte(input integer pos);
        integer zlen,plen,olen;
        begin
            zlen=next_flags[0]?Z_BYTES:0; plen=next_flags[1]?PS_BYTES:0; olen=next_flags[2]?OUT_BYTES:0;
            header_byte=0;
            if(pos==1) header_byte=1;
            else if(pos==2) header_byte={5'b0,next_flags};
            else if(pos>=4 && pos<8) header_byte=next_generation >> (8*(pos-4));
            else if(pos>=8 && pos<40) header_byte=model_id >> (8*(pos-8));
            else if(pos>=40 && pos<72) header_byte=input_id >> (8*(pos-40));
            else if(pos>=72 && pos<104) header_byte=descriptor_id >> (8*(pos-72));
            else if(pos>=104 && pos<108) header_byte=next_offset >> (8*(pos-104));
            else if(pos>=108 && pos<110) header_byte=zlen >> (8*(pos-108));
            else if(pos>=110 && pos<112) header_byte=plen >> (8*(pos-110));
            else if(pos>=112 && pos<114) header_byte=olen >> (8*(pos-112));
            else if(pos>=116 && pos<120) header_byte=payload_crc >> (8*(pos-116));
        end
    endfunction

    always @* begin
        mem_valid=0;mem_write=0;mem_addr=0;mem_wdata=0;
        restore_valid=0;restore_addr=cursor;restore_data=0;payload_addr=0;
        if(state==BOOT_READ) begin mem_valid=1;mem_addr=cursor;end
        if(state==INVALIDATE || state==WRITE_PAYLOAD || state==WRITE_HEADER || state==PUBLISH || state==FRONTIER) begin
            mem_valid=1;mem_write=1;
            case(state)
                INVALIDATE:begin mem_addr=target_slot*SLOT_BYTES;mem_wdata=0;end
                WRITE_PAYLOAD:begin mem_addr=target_slot*SLOT_BYTES+HEADER_BYTES+cursor;mem_wdata=staged[cursor];end
                WRITE_HEADER:begin mem_addr=target_slot*SLOT_BYTES+cursor;mem_wdata=header[cursor];end
                PUBLISH:begin mem_addr=target_slot*SLOT_BYTES;mem_wdata=8'ha5;end
                FRONTIER:begin mem_addr=2*SLOT_BYTES;mem_wdata=1;end
                default:begin end
            endcase
        end
        if(state==RESTORE) begin
            restore_valid=cursor<active_length;restore_data=scan[active_slot*SLOT_BYTES+HEADER_BYTES+cursor];
        end
        if(state==STAGE) begin
            if(next_flags[2]) payload_addr=Z_BYTES+PS_BYTES+cursor;
            else if(next_flags[0] && cursor<Z_BYTES) payload_addr=cursor;
            else payload_addr=Z_BYTES+cursor-(next_flags[0]?Z_BYTES:0);
        end
        if(!rst_n) begin mem_valid=0;restore_valid=0;end
    end

    reg [7:0] byte_value;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state<=BOOT_READ;cursor<=0;boot_done<=0;commit_done<=0;protocol_error<=0;
            active_valid<=0;active_slot<=0;active_generation<=0;committed_offset<=0;active_flags<=0;
            valid_slots<=0;candidate_slot<=0;target_slot<=0;gen0<=0;gen1<=0;
            crc<=32'hffffffff;payload_crc<=0;payload_length<=0;active_length<=0;candidate_length<=0;
            next_flags<=0;next_offset<=0;next_generation<=0;use_new_z<=0;use_new_ps<=0;
        end else begin
            commit_done<=0;
            case(state)
                BOOT_READ:if(mem_ready) begin
                    scan[cursor]<=mem_rdata;
                    if(cursor==2*SLOT_BYTES) begin candidate_slot<=0;state<=VALIDATE_START;end
                    else cursor<=cursor+1;
                end
                VALIDATE_START:begin
                    if(header_legal(candidate_slot*SLOT_BYTES)) begin
                        candidate_length<=half_at(candidate_slot*SLOT_BYTES+108)+half_at(candidate_slot*SLOT_BYTES+110)+half_at(candidate_slot*SLOT_BYTES+112);
                        cursor<=1;crc<=32'hffffffff;state<=META_CHECK;
                    end else if(!candidate_slot) begin candidate_slot<=1;end
                    else state<=SELECT_SLOT;
                end
                META_CHECK:begin
                    if(cursor==120) begin
                        if((~crc)==word_at(candidate_slot*SLOT_BYTES+120)) begin
                            crc<=32'hffffffff;cursor<=0;state<=PAYLOAD_CHECK;
                        end else if(!candidate_slot) begin candidate_slot<=1;state<=VALIDATE_START;end
                        else state<=SELECT_SLOT;
                    end else begin crc<=crc_byte(crc,scan[candidate_slot*SLOT_BYTES+cursor]);cursor<=cursor+1;end
                end
                PAYLOAD_CHECK:begin
                    if(cursor==candidate_length) begin
                        if((~crc)==word_at(candidate_slot*SLOT_BYTES+116)) begin
                            valid_slots[candidate_slot]<=1;
                            if(candidate_slot) gen1<=word_at(SLOT_BYTES+4);else gen0<=word_at(4);
                        end
                        if(!candidate_slot) begin candidate_slot<=1;state<=VALIDATE_START;end
                        else state<=SELECT_SLOT;
                    end else begin crc<=crc_byte(crc,scan[candidate_slot*SLOT_BYTES+HEADER_BYTES+cursor]);cursor<=cursor+1;end
                end
                SELECT_SLOT:begin
                    if(valid_slots!=0) begin
                        if(valid_slots[1] && (!valid_slots[0] || gen1>gen0)) begin active_slot<=1;base=SLOT_BYTES;end
                        else begin active_slot<=0;base=0;end
                        active_valid<=1;active_generation<=word_at(base+4);committed_offset<=word_at(base+104);
                        active_flags<=scan[base+2][2:0];
                        active_length<=half_at(base+108)+half_at(base+110)+half_at(base+112);
                        cursor<=0;state<=RESTORE;
                        if(scan[2*SLOT_BYTES]!=0 && scan[base+2][2]==0) begin protocol_error<=1;state<=ERROR;end
                    end else if(scan[2*SLOT_BYTES]!=0) begin protocol_error<=1;state<=ERROR;end
                    else begin boot_done<=1;state<=IDLE;end
                end
                RESTORE:begin
                    if(cursor==active_length) begin
                        if(active_flags[2] && scan[2*SLOT_BYTES]==0) state<=FRONTIER;
                        else begin boot_done<=1;state<=IDLE;end
                    end else if(restore_ready) begin durable[cursor]<=restore_data;cursor<=cursor+1;end
                end
                IDLE:if(cmd_valid && cmd_ready) begin
                    if(active_generation==32'hffffffff || cmd_offset>CHANNELS ||
                        (cmd_output && cmd_offset!=CHANNELS) || (cmd_keep_ps && cmd_offset<committed_offset)) begin
                        protocol_error<=1;state<=ERROR;
                    end else begin
                        next_flags<=cmd_output?4:{1'b0,(cmd_keep_ps || active_flags[1]),(cmd_save_z || active_flags[0])};
                        next_offset<=cmd_output?CHANNELS:(cmd_keep_ps?cmd_offset:committed_offset);
                        next_generation<=active_generation+1;target_slot<=active_valid?!active_slot:0;
                        payload_length<=cmd_output?OUT_BYTES:((cmd_save_z || active_flags[0]?Z_BYTES:0)+(cmd_keep_ps || active_flags[1]?PS_BYTES:0));
                        use_new_z<=cmd_save_z;use_new_ps<=cmd_keep_ps;cursor<=0;crc<=32'hffffffff;state<=STAGE;
                    end
                end
                STAGE:begin
                    if(cursor==payload_length) begin payload_crc<=~crc;cursor<=1;crc<=32'hffffffff;state<=BUILD_HEADER;end
                    else begin
                        byte_value=payload_rdata;
                        if(!next_flags[2]) begin
                            if(next_flags[0] && cursor<Z_BYTES && !use_new_z) byte_value=durable[cursor];
                            if((!next_flags[0] || cursor>=Z_BYTES) && !use_new_ps)
                                byte_value=durable[(active_flags[0]?Z_BYTES:0)+cursor-(next_flags[0]?Z_BYTES:0)];
                        end
                        staged[cursor]<=byte_value;crc<=crc_byte(crc,byte_value);cursor<=cursor+1;
                    end
                end
                BUILD_HEADER:begin
                    if(cursor<120) begin header[cursor]<=header_byte(cursor);crc<=crc_byte(crc,header_byte(cursor));cursor<=cursor+1;end
                    else begin
                        header[120]<=~crc;header[121]<=(~crc)>>8;header[122]<=(~crc)>>16;header[123]<=(~crc)>>24;
                        cursor<=0;state<=INVALIDATE;
                    end
                end
                INVALIDATE:if(mem_ready) begin cursor<=0;state<=payload_length==0?WRITE_HEADER:WRITE_PAYLOAD;if(payload_length==0) cursor<=1;end
                WRITE_PAYLOAD:if(mem_ready) begin
                    if(cursor+1==payload_length) begin cursor<=1;state<=WRITE_HEADER;end else cursor<=cursor+1;
                end
                WRITE_HEADER:if(mem_ready) begin
                    if(cursor==HEADER_BYTES-1) begin cursor<=0;state<=PUBLISH;end else cursor<=cursor+1;
                end
                PUBLISH:if(mem_ready) begin
                    active_valid<=1;active_slot<=target_slot;active_generation<=next_generation;
                    active_flags<=next_flags;committed_offset<=next_offset;active_length<=payload_length;
                    // Cache is volatile. Promote only after persistence ACK.
                    for(base=0;base<MAX_PAYLOAD;base=base+1) durable[base]<=staged[base];
                    if(next_flags[2]) state<=FRONTIER;
                    else begin commit_done<=1;state<=IDLE;end
                end
                FRONTIER:if(mem_ready) begin boot_done<=1;commit_done<=1;state<=IDLE;end
                ERROR:begin protocol_error<=1;end
                default:begin protocol_error<=1;state<=ERROR;end
            endcase
        end
    end
endmodule
