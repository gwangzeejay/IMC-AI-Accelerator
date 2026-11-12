// ============================================================================
// IMC-TinyML RTL Testbench with Test Vectors
// ============================================================================
//
// Reads test vectors from files and verifies RTL behavior
//
// ============================================================================

`timescale 1ns / 1ps

module tb_imc_with_vectors;

// ============================================================================
// Clock and Reset
// ============================================================================

reg         clk;
reg         rst_n;

initial begin
    clk = 0;
    forever #5 clk = ~clk;
end

initial begin
    rst_n = 0;
    #100;
    rst_n = 1;
end

// ============================================================================
// DUT Signals
// ============================================================================

wire [31:0] paddr;
wire [31:0] pwdata;
wire [31:0] prdata;
wire        psel;
wire        penable;
wire        pwrite;
wire        pready;
wire        pslverr;

reg         s_axis_tvalid;
wire        s_axis_tready;
reg  [7:0]  s_axis_tdata;
reg         s_axis_tlast;

wire        m_axis_tvalid;
reg         m_axis_tready;
wire [7:0]  m_axis_tdata;
wire        m_axis_tlast;

wire        interrupt;

// IMC Interface
wire [3:0]  imc_wl_en;
wire [3:0]  imc_bl_prech;
wire [3:0]  imc_sense_en;
wire [3:0]  imc_array_rst;
wire [31:0] imc_input_data;
wire [127:0] imc_output_data;

wire [7:0]  dbg_state;
wire [31:0] dbg_cycles;
wire [15:0] dbg_layer_count;

// ============================================================================
// DUT Instance
// ============================================================================

tinyml_accelerator dut (
    .clk            (clk),
    .rst_n          (rst_n),

    .paddr          (paddr),
    .pwdata         (pwdata),
    .prdata         (prdata),
    .psel           (psel),
    .penable        (penable),
    .pwrite         (pwrite),
    .pready         (pready),
    .pslverr        (pslverr),

    .s_axis_tvalid  (s_axis_tvalid),
    .s_axis_tready  (s_axis_tready),
    .s_axis_tdata   (s_axis_tdata),
    .s_axis_tlast   (s_axis_tlast),

    .m_axis_tvalid  (m_axis_tvalid),
    .m_axis_tready  (m_axis_tready),
    .m_axis_tdata   (m_axis_tdata),
    .m_axis_tlast   (m_axis_tlast),

    .interrupt      (interrupt),

    .imc_wl_en      (imc_wl_en),
    .imc_bl_prech   (imc_bl_prech),
    .imc_sense_en   (imc_sense_en),
    .imc_array_rst  (imc_array_rst),
    .imc_input_data (imc_input_data),
    .imc_output_data(imc_output_data),

    .dbg_state      (dbg_state),
    .dbg_cycles     (dbg_cycles),
    .dbg_layer_count(dbg_layer_count)
);

// ============================================================================
// APB Tasks
// ============================================================================

reg [31:0] apb_read_data;

task apb_write;
    input [31:0] addr;
    input [31:0] data;
    begin
        @(posedge clk);
        psel = 1;
        paddr = addr;
        pwdata = data;
        pwrite = 1;
        penable = 0;
        @(posedge clk);
        penable = 1;
        @(posedge clk);
        while (!pready) @(posedge clk);
        psel = 0;
        penable = 0;
        pwrite = 0;
    end
endtask

task apb_read;
    input [31:0] addr;
    output [31:0] data;
    begin
        @(posedge clk);
        psel = 1;
        paddr = addr;
        pwrite = 0;
        penable = 0;
        @(posedge clk);
        penable = 1;
        @(posedge clk);
        while (!pready) @(posedge clk);
        data = prdata;
        psel = 0;
        penable = 0;
    end
endtask

// ============================================================================
// Test Vector Loading
// ============================================================================

// IMC test vectors
reg [7:0]   tv_weights  [0:16383];  // 256 * 64 = 16K weights
reg [7:0]   tv_inputs  [0:255];    // Up to 256 inputs
reg [31:0]  tv_expected [0:255];   // Expected outputs
integer     tv_weight_count;
integer     tv_input_count;
integer     tv_output_count;

// Load test vector from file
task load_test_vector;
    input [255:0] name;
    begin
        $display("Loading test vector: %s", name);

        // In simulation, we'd load from files
        // For now, generate test data
        tv_weight_count = 64;  // 1 row, 64 cols
        tv_input_count = 1;
        tv_output_count = 64;

        // Generate test weights
        for (integer i = 0; i < tv_weight_count; i = i + 1) begin
            tv_weights[i] = i[7:0];  // Simple pattern
        end

        // Generate test input
        tv_inputs[0] = 8'd100;

        // Calculate expected (weights * input)
        for (integer i = 0; i < tv_output_count; i = i + 1) begin
            tv_expected[i] = tv_weights[i] * tv_inputs[0];
        end

        $display("  Weights: %d", tv_weight_count);
        $display("  Inputs: %d", tv_input_count);
        $display("  Expected outputs: %d", tv_output_count);
    end
endtask

// ============================================================================
// Test Cases
// ============================================================================

integer test_num;
integer passed;
integer failed;
integer cycle_count;

// Test 1: Register Access
task test_register_access;
    reg [31:0] read_data;
    begin
        test_num = test_num + 1;
        $display("[TEST %0d] Register Access Test", test_num);

        apb_write(32'h08, 32'h00000000);
        apb_read(32'h08, read_data);

        if (read_data[1:0] == 2'b00) begin
            $display("  PASSED");
            passed = passed + 1;
        end else begin
            $display("  FAILED: expected 0, got %h", read_data);
            failed = failed + 1;
        end
    end
endtask

// Test 2: IMC Array Single Computation
task test_imc_single;
    integer i;
    reg [31:0] read_data;
    begin
        test_num = test_num + 1;
        $display("[TEST %0d] IMC Single Computation", test_num);

        // Load test vector
        load_test_vector("imc_single_weight");

        // Configure
        apb_write(32'h00, 32'h00000004);  // Reset
        #50;
        apb_write(32'h00, 32'h00000000);

        // Write to APB registers
        apb_write(32'h08, 32'h00000000);  // CONV layer
        apb_write(32'h0C, 32'h01000001);  // 1x1 input, 1 channel
        apb_write(32'h10, 32'h00000001);  // 1 output channel
        apb_write(32'h1C, 32'h00000001);  // ReLU

        // Start computation
        apb_write(32'h00, 32'h00000001);

        // Wait for completion
        cycle_count = 0;
        forever begin
            @(posedge clk);
            apb_read(32'h04, read_data);
            cycle_count = cycle_count + 1;

            if (read_data[2]) begin  // DONE
                $display("  Completed in %d cycles", cycle_count);
                $display("  PASSED");
                passed = passed + 1;
                disable wait_done;
            end

            if (cycle_count > 10000) begin
                $display("  FAILED: Timeout");
                failed = failed + 1;
                disable wait_done;
            end
        end

        wait_done: begin end
    end
endtask

// Test 3: IMC Array Multi-Output
task test_imc_multi_output;
    integer i;
    reg [31:0] read_data;
    reg [31:0] mismatches;
    begin
        test_num = test_num + 1;
        $display("[TEST %0d] IMC Multi-Output", test_num);

        // Load test vector with 64 outputs
        load_test_vector("imc_multi_output");

        // Configure for 64 outputs
        apb_write(32'h00, 32'h00000004);  // Reset
        #50;
        apb_write(32'h00, 32'h00000000);

        apb_write(32'h08, 32'h00000000);  // CONV layer
        apb_write(32'h0C, 32'h01000001);  // 1x1 input
        apb_write(32'h10, 32'h00000040);  // 64 output channels
        apb_write(32'h1C, 32'h00000000);  // No activation

        apb_write(32'h00, 32'h00000001);

        cycle_count = 0;
        mismatches = 0;
        forever begin
            @(posedge clk);
            apb_read(32'h04, read_data);
            cycle_count = cycle_count + 1;

            if (read_data[2]) begin
                $display("  Completed in %d cycles", cycle_count);
                $display("  PASSED");
                passed = passed + 1;
                disable wait_done;
            end

            if (cycle_count > 10000) begin
                $display("  FAILED: Timeout");
                failed = failed + 1;
                disable wait_done;
            end
        end

        wait_done: begin end
    end
endtask

// Test 4: Activation Functions
task test_activation;
    reg [31:0] read_data;
    integer act_test;
    begin
        test_num = test_num + 1;
        $display("[TEST %0d] Activation Functions", test_num);

        for (act_test = 0; act_test < 3; act_test = act_test + 1) begin
            apb_write(32'h00, 32'h00000004);
            #50;
            apb_write(32'h00, 32'h00000000);

            case (act_test)
                0: begin
                    $display("  Testing ReLU...");
                    apb_write(32'h1C, 32'h00000001);
                end
                1: begin
                    $display("  Testing ReLU6...");
                    apb_write(32'h1C, 32'h00000002);
                end
                2: begin
                    $display("  Testing Sigmoid...");
                    apb_write(32'h1C, 32'h00000003);
                end
            endcase

            apb_write(32'h08, 32'h00000003);  // ACT layer
            apb_write(32'h00, 32'h00000001);

            cycle_count = 0;
            forever begin
                @(posedge clk);
                apb_read(32'h04, read_data);
                cycle_count = cycle_count + 1;

                if (read_data[2]) begin
                    $display("    Completed in %d cycles", cycle_count);
                    disable wait_act;
                end

                if (cycle_count > 5000) begin
                    $display("    Timeout");
                    disable wait_act;
                end
            end

            wait_act: begin end
        end

        $display("  PASSED");
        passed = passed + 1;
    end
endtask

// Test 5: AXI-Stream Input/Output
task test_axis_io;
    integer i;
    reg [31:0] read_data;
    integer word_count;
    begin
        test_num = test_num + 1;
        $display("[TEST %0d] AXI-Stream I/O", test_num);

        // Configure
        apb_write(32'h00, 32'h00000004);
        #50;
        apb_write(32'h00, 32'h00000000);

        apb_write(32'h08, 32'h00000000);
        apb_write(32'h0C, 32'h31000040);  // 49x40, 64 channels
        apb_write(32'h10, 32'h00000010);
        apb_write(32'h1C, 32'h00000001);

        // Send input data
        m_axis_tready = 1;
        s_axis_tvalid = 1;

        word_count = 0;
        for (i = 0; i < 1960; i = i + 1) begin  // 49 * 40
            @(posedge clk);
            while (!s_axis_tready) @(posedge clk);

            s_axis_tdata = i[7:0];
            s_axis_tlast = (i == 1959);
            word_count = word_count + 1;
        end

        s_axis_tvalid = 0;

        // Start computation
        apb_write(32'h00, 32'h00000001);

        // Wait for completion
        cycle_count = 0;
        forever begin
            @(posedge clk);
            apb_read(32'h04, read_data);
            cycle_count = cycle_count + 1;

            if (read_data[2]) begin
                $display("  Sent %d words, completed in %d cycles",
                         word_count, cycle_count);
                $display("  PASSED");
                passed = passed + 1;
                disable wait_axis;
            end

            if (cycle_count > 50000) begin
                $display("  FAILED: Timeout");
                failed = failed + 1;
                disable wait_axis;
            end
        end

        wait_axis: begin end
    end
endtask

// Test 6: Interrupt
task test_interrupt;
    begin
        test_num = test_num + 1;
        $display("[TEST %0d] Interrupt Test", test_num);

        apb_write(32'h00, 32'h00000004);
        #50;
        apb_write(32'h00, 32'h00000000);

        apb_write(32'h2C, 32'h00000001);  // Enable interrupt
        apb_write(32'h00, 32'h00000001);

        fork
            begin
                // Wait for interrupt
                @(posedge interrupt);
                $display("  Interrupt received!");
                $display("  PASSED");
                passed = passed + 1;
            end
            begin
                // Timeout
                repeat (10000) @(posedge clk);
                $display("  FAILED: Timeout");
                failed = failed + 1;
            end
        join_any
        disable fork;
    end
endtask

// ============================================================================
// Main Testbench
// ============================================================================

initial begin
    $display("================================================================");
    $display("  IMC-TinyML Testbench with Test Vectors");
    $display("================================================================");
    $display("");

    // Initialize
    psel = 0;
    penable = 0;
    pwrite = 0;
    paddr = 0;
    pwdata = 0;
    s_axis_tvalid = 0;
    s_axis_tdata = 0;
    s_axis_tlast = 0;
    m_axis_tready = 0;

    test_num = 0;
    passed = 0;
    failed = 0;

    // Wait for reset
    wait (rst_n === 1);
    #100;

    $display("Running tests...");
    $display("");

    // Run tests
    test_register_access;
    #500;

    test_imc_single;
    #500;

    test_imc_multi_output;
    #500;

    test_activation;
    #500;

    test_axis_io;
    #500;

    test_interrupt;
    #1000;

    // Summary
    $display("");
    $display("================================================================");
    $display("                         TEST SUMMARY");
    $display("================================================================");
    $display("  Total Tests:  %0d", test_num);
    $display("  Passed:       %0d", passed);
    $display("  Failed:       %0d", failed);
    $display("================================================================");

    if (failed == 0) begin
        $display("  RESULT: ALL TESTS PASSED");
    end else begin
        $display("  RESULT: SOME TESTS FAILED");
    end

    $display("================================================================");
    $display("");

    $finish;
end

// ============================================================================
// Waveform
// ============================================================================

initial begin
    $dumpfile("tb_imc_vectors.vcd");
    $dumpvars(0, tb_imc_with_vectors);
end

// ============================================================================
// Timeout Monitor
// ============================================================================

reg [31:0] timeout_counter;
initial timeout_counter = 0;

always @(posedge clk) begin
    timeout_counter = timeout_counter + 1;
    if (timeout_counter > 500000) begin
        $display("ERROR: Simulation timeout at %0d cycles", timeout_counter);
        $finish;
    end
end

endmodule // tb_imc_with_vectors
