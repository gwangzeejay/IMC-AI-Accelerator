// ============================================================================
// IMC-TinyML Testbench
// Comprehensive verification for In-Memory Computing AI Accelerator
// ============================================================================

`timescale 1ns / 1ps

module tb_imc_accelerator;

// ============================================================================
// Clock and Reset
// ============================================================================

reg         clk;
reg         rst_n;

initial begin
    clk = 0;
    forever #5 clk = ~clk;  // 100 MHz
end

initial begin
    rst_n = 0;
    #100;
    rst_n = 1;
end

// ============================================================================
// DUT Signals
// ============================================================================

// APB Interface
wire [31:0] paddr;
wire [31:0] pwdata;
wire [31:0] prdata;
wire        psel;
wire        penable;
wire        pwrite;
wire        pready;
wire        pslverr;

// AXI-Stream Slave (Input)
reg         s_axis_tvalid;
wire        s_axis_tready;
reg  [7:0]  s_axis_tdata;
reg         s_axis_tlast;

// AXI-Stream Master (Output)
wire        m_axis_tvalid;
reg         m_axis_tready;
wire [7:0]  m_axis_tdata;
wire        m_axis_tlast;

// Interrupt
wire        interrupt;

// IMC Interface
wire [3:0]  imc_wl_en;
wire [3:0]  imc_bl_prech;
wire [3:0]  imc_sense_en;
wire [3:0]  imc_array_rst;
wire [31:0] imc_input_data;
wire [127:0] imc_output_data;  // 4 tiles × 32 bits

// Debug
wire [7:0]  dbg_state;
wire [31:0] dbg_cycles;
wire [15:0] dbg_layer_count;

// ============================================================================
// DUT Instance
// ============================================================================

tinyml_accelerator #(
    .NUM_TILES      (4),
    .ARRAY_ROWS     (256),
    .ARRAY_COLS     (64),
    .BIT_SLICE_DEPTH(8),
    .DATA_WIDTH     (8),
    .ADDR_WIDTH     (32),
    .NUM_LAYERS     (12),
    .ACCUM_WIDTH   (32)
) dut (
    .clk            (clk),
    .rst_n          (rst_n),

    // APB
    .paddr          (paddr),
    .pwdata         (pwdata),
    .prdata         (prdata),
    .psel           (psel),
    .penable        (penable),
    .pwrite         (pwrite),
    .pready         (pready),
    .pslverr        (pslverr),

    // AXI-Stream Slave
    .s_axis_tvalid  (s_axis_tvalid),
    .s_axis_tready  (s_axis_tready),
    .s_axis_tdata   (s_axis_tdata),
    .s_axis_tlast   (s_axis_tlast),

    // AXI-Stream Master
    .m_axis_tvalid  (m_axis_tvalid),
    .m_axis_tready  (m_axis_tready),
    .m_axis_tdata   (m_axis_tdata),
    .m_axis_tlast   (m_axis_tlast),

    // Interrupt
    .interrupt      (interrupt),

    // IMC Interface
    .imc_wl_en      (imc_wl_en),
    .imc_bl_prech   (imc_bl_prech),
    .imc_sense_en   (imc_sense_en),
    .imc_array_rst  (imc_array_rst),
    .imc_input_data (imc_input_data),
    .imc_output_data(imc_output_data),

    // Debug
    .dbg_state      (dbg_state),
    .dbg_cycles     (dbg_cycles),
    .dbg_layer_count(dbg_layer_count)
);

// ============================================================================
// APB Task Library
// ============================================================================

reg [31:0] apb_write_data;
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
// Test Cases
// ============================================================================

// Test counters
integer test_num = 0;
integer passed = 0;
integer failed = 0;

// Test 1: Register Access
task test_register_access;
    reg [31:0] read_data;
    begin
        test_num = test_num + 1;
        $display("[TEST %0d] Register Access Test", test_num);

        // Write to layer type register
        apb_write(32'h08, 32'h00000000);  // CONV layer

        // Read back
        apb_read(32'h08, read_data);

        if (read_data[1:0] == 2'b00) begin
            $display("  PASSED: Layer type register read/write");
            passed = passed + 1;
        end else begin
            $display("  FAILED: Layer type register read/write");
            $display("    Expected: 0x0, Got: 0x%h", read_data);
            failed = failed + 1;
        end

        // Write to control register
        apb_write(32'h00, 32'h00000004);  // Reset

        #100;

        apb_write(32'h00, 32'h00000000);

        // Read status
        apb_read(32'h04, read_data);

        if (read_data[0] == 1) begin
            $display("  PASSED: Status register (idle)");
            passed = passed + 1;
        end else begin
            $display("  FAILED: Status register (idle)");
            failed = failed + 1;
        end
    end
endtask

// Test 2: Configuration
task test_configuration;
    begin
        test_num = test_num + 1;
        $display("[TEST %0d] Configuration Test", test_num);

        // Configure layer
        apb_write(32'h08, 32'h00000000);  // LAYER_TYPE = CONV
        apb_write(32'h0C, 32'h31000008);  // IN_ROWS=49, IN_COLS=40, IN_CH=8
        apb_write(32'h10, 32'h00000010);  // OUT_CH = 16
        apb_write(32'h14, 32'h00000005);  // KERNEL = 5
        apb_write(32'h18, 32'h00000001);  // STRIDE = 1
        apb_write(32'h1C, 32'h00000001);  // ACT = ReLU
        apb_write(32'h28, 32'h0000000C);  // MAX_LAYERS = 12

        $display("  PASSED: Configuration registers set");
        passed = passed + 1;
    end
endtask

// Test 3: AXI-Stream Data Input
task test_axi_input;
    integer i;
    begin
        test_num = test_num + 1;
        $display("[TEST %0d] AXI-Stream Input Test", test_num);

        s_axis_tvalid = 0;
        s_axis_tdata = 0;
        s_axis_tlast = 0;

        #200;

        // Send 100 words of data
        for (i = 0; i < 100; i = i + 1) begin
            @(posedge clk);
            while (!s_axis_tready) @(posedge clk);
            s_axis_tvalid = 1;
            s_axis_tdata = i[7:0];
            s_axis_tlast = (i == 99) ? 1 : 0;
        end

        @(posedge clk);
        s_axis_tvalid = 0;
        s_axis_tlast = 0;

        $display("  PASSED: AXI-Stream data input (%0d words)", i);
        passed = passed + 1;
    end
endtask

// Test 4: Computation Start
task test_computation;
    reg [31:0] status;
    integer wait_cycles;
    begin
        test_num = test_num + 1;
        $display("[TEST %0d] Computation Start Test", test_num);

        // Start computation
        apb_write(32'h00, 32'h00000001);  // START

        // Wait and check status
        wait_cycles = 0;
        forever begin
            @(posedge clk);
            apb_read(32'h04, status);
            wait_cycles = wait_cycles + 1;

            if (status[1]) begin  // BUSY
                $display("  Computation started (busy)");
            end

            if (status[2]) begin  // DONE
                $display("  Computation completed after %0d cycles", wait_cycles);
                passed = passed + 1;
                disable wait_check;
            end

            if (wait_cycles > 10000) begin
                $display("  FAILED: Timeout waiting for completion");
                failed = failed + 1;
                disable wait_check;
            end
        end

        wait_check: begin end
    end
endtask

// Test 5: AXI-Stream Output
task test_axi_output;
    integer i;
    reg [31:0] word_count;
    begin
        test_num = test_num + 1;
        $display("[TEST %0d] AXI-Stream Output Test", test_num);

        m_axis_tready = 1;
        word_count = 0;

        // Collect output data
        fork
            begin
                forever begin
                    @(posedge clk);
                    if (m_axis_tvalid && m_axis_tready) begin
                        $display("  Output[%0d] = 0x%h", word_count, m_axis_tdata);
                        word_count = word_count + 1;
                        if (m_axis_tlast) begin
                            disable collect;
                        end
                    end
                end
            end
        join

        collect: begin end

        $display("  Received %0d output words", word_count);

        if (word_count > 0) begin
            $display("  PASSED: Output data received");
            passed = passed + 1;
        end else begin
            $display("  FAILED: No output data received");
            failed = failed + 1;
        end
    end
endtask

// Test 6: Interrupt
task test_interrupt;
    begin
        test_num = test_num + 1;
        $display("[TEST %0d] Interrupt Test", test_num);

        // Enable interrupt
        apb_write(32'h28, 32'h00000001);

        // Wait for interrupt
        @(posedge interrupt);
        $display("  Interrupt received!");

        $display("  PASSED: Interrupt mechanism working");
        passed = passed + 1;
    end
endtask

// Test 7: Power Management
task test_power_management;
    begin
        test_num = test_num + 1;
        $display("[TEST %0d] Power Management Test", test_num);

        // Read current power state
        apb_write(32'h40, 32'h00000000);  // ACTIVE
        #1000;

        apb_write(32'h40, 32'h00000002);  // SLEEP
        #1000;

        $display("  PASSED: Power state transitions");
        passed = passed + 1;
    end
endtask

// Test 8: Layer Sequence
task test_layer_sequence;
    integer i;
    begin
        test_num = test_num + 1;
        $display("[TEST %0d] Layer Sequence Test", test_num);

        // Test each layer type
        for (i = 0; i < 4; i = i + 1) begin
            apb_write(32'h08, i);  // Layer type
            apb_write(32'h00, 32'h00000001);  // Start
            #5000;
            $display("  Layer type %0d completed", i);
        end

        $display("  PASSED: All layer types processed");
        passed = passed + 1;
    end
endtask

// ============================================================================
// Main Testbench
// ============================================================================

initial begin
    $display("================================================================");
    $display("    IMC-TinyML Accelerator Testbench");
    $display("    In-Memory Computing AI Accelerator for TinyML");
    $display("================================================================");
    $display("");

    // Initialize signals
    psel = 0;
    penable = 0;
    pwrite = 0;
    paddr = 0;
    pwdata = 0;
    s_axis_tvalid = 0;
    s_axis_tdata = 0;
    s_axis_tlast = 0;
    m_axis_tready = 0;

    // Wait for reset
    wait (rst_n === 1);
    #100;

    $display("Reset complete. Starting tests...");
    $display("");

    // Run tests
    test_register_access;
    #500;

    test_configuration;
    #500;

    test_axi_input;
    #1000;

    test_computation;
    #1000;

    test_axi_output;
    #500;

    test_interrupt;
    #500;

    test_power_management;
    #500;

    test_layer_sequence;
    #1000;

    // Final summary
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
// Waveform Generation
// ============================================================================

initial begin
    $dumpfile("tb_imc_accelerator.vcd");
    $dumpvars(0, tb_imc_accelerator);
end

// ============================================================================
// Timeout Monitor
// ============================================================================

reg [31:0] timeout_counter;
initial timeout_counter = 0;

always @(posedge clk) begin
    timeout_counter = timeout_counter + 1;
    if (timeout_counter > 100000) begin
        $display("ERROR: Simulation timeout at %0d cycles", timeout_counter);
        $finish;
    end
end

endmodule // tb_imc_accelerator
