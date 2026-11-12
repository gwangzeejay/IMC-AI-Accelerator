// TFLite/gemmlowp two-rounding integer requantization. Combinational reference.
module recap_requantize(
    input wire signed [31:0] accumulator,input wire signed [31:0] multiplier,
    input wire signed [5:0] shift,input wire signed [7:0] zero_point,
    input wire signed [7:0] activation_min,input wire signed [7:0] activation_max,
    output reg signed [7:0] result,output reg error
);
    reg signed [63:0] left,product,nudge,high,value;
    reg [63:0] mask,remainder,threshold;
    integer exponent;
    always @* begin
        error=0;result=0;left=$signed(accumulator);product=0;nudge=0;high=0;value=0;mask=0;remainder=0;threshold=0;exponent=0;
        if(shift>0) left=left<<<shift;
        if(shift>30 || shift< -31 || activation_min>activation_max || left>64'sd2147483647 || left< -64'sd2147483648) error=1;
        else begin
            if(left== -64'sd2147483648 && multiplier==32'sh80000000) high=2147483647;
            else begin
                product=left*$signed(multiplier);
                nudge=product>=0?64'sd1073741824:-64'sd1073741823;
                high=(product+nudge)/64'sd2147483648;
            end
            exponent=shift<0?-shift:0;mask=(64'd1<<exponent)-1;
            remainder=high&mask;threshold=(mask>>1)+(high<0);
            // Keep the arithmetic shift signed: mixing an unsigned comparison
            // into the same expression can make >>> behave as a logical shift.
            value=high>>>exponent;
            if(remainder>threshold) value=value+64'sd1;
            value=value+$signed({{56{zero_point[7]}},zero_point});
            if(value<$signed(activation_min)) value=$signed(activation_min);
            if(value>$signed(activation_max)) value=$signed(activation_max);
            result=value[7:0];
        end
    end
endmodule
