# In-Memory Computing AI Accelerator for TinyML

> **G7 — 16/10/2026:** Đã có [English paper draft](07_IEEE_Paper/g7/manuscript.md), [PDF](output/pdf/recap_cim_g7.pdf), internal review và submission gap report. **Chưa sẵn sàng nộp**; chi phí còn assumed, G1/B4/calibration chưa đóng. Xem [G7 deliverables](02_Research/G7_deliverables.md). Legacy claims bên dưới không thay thế evidence G2–G7.

> **Cập nhật nghiên cứu 15/10/2026:** kế hoạch hiện hành là
> [RECAP-CIM](01_Project_Plan/Project_Plan_IMC_TinyML.md).
> [G2 deliverables](02_Research/G2_deliverables.md) có INT8 golden reference,
> crash-recovery simulator và kết quả kiểm tra đã chạy; tái lập bằng
> `python 10_Experiments/run_g2.py` ([hướng dẫn](10_Experiments/reproduce.md)).
> G1/G2 chưa đóng hoàn toàn. Phần nội dung legacy bên dưới, gồm bảng “Key
> Results”, là bản đề xuất cũ với số liệu **chưa được xác minh**, không phải
> kết quả thực nghiệm RECAP-CIM hoặc bằng chứng cho bài báo.

> **G3 đã có đợt đánh giá trong mô hình:** [kết quả và hướng tiếp tục](02_Research/G3_deliverables.md),
> [figure](10_Experiments/g3/plots/heldout_comparison.png).
> Chạy lại bằng `python 10_Experiments/run_g3.py`. Các số năng lượng vẫn
> là giả định; chưa có calibration để dùng làm claim phần cứng.

> **G4 đã kiểm tra RTL microtile:** [báo cáo](02_Research/G4_deliverables.md),
> [controller/interface](03_Architecture/g4_rtl_spec.md).
> Tái lập bằng `python 10_Experiments/run_g4.py` sau local tool setup.
> Full-size controller chưa hoàn tất generic synthesis; chưa có PPA/energy vật lý.

> **G5 đã chạy hybrid KWS end-to-end trong mô phỏng:**
> [báo cáo](02_Research/G5_deliverables.md), [kết quả](10_Experiments/g5/results.json).
> Accuracy reference 90,1%/1.000 mẫu có nhãn; 16 ca full-network recovery đạt.
> Trên test mới, RECAP và baseline thích nghi đều đạt 26/36 commit, giảm năng
> lượng 0%; chưa đạt mục tiêu lợi ích 20%. Các cost vẫn giả định.
> Tái lập: `python 10_Experiments/run_g5.py`; kiểm hashes/kết quả bằng
> `python 10_Experiments/audit_g5.py`.

> **G6 đã chạy hai workload và trace ETH đo thực:**
> [báo cáo](02_Research/G6_deliverables.md), [kết quả](10_Experiments/g6/results.json).
> 1.216 case configurations, 10 ablation/workload và sáu trục sensitivity.
> KWS giảm model energy/commit 1,368% so adaptive baseline; VWW gần 0%,
> chưa đạt mục tiêu chính 20%. Score hiện tại còn thiếu expected redo credit.
> VWW không vừa budget gốc; cả hai mạng dùng chung 64 KiB SRAM/2 MiB NVM
> giả định trong G6. Chưa có calibrated hardware energy.
> Tái lập: `python 10_Experiments/run_g6.py`; xem reproduce guide để tải sources.

## 🎯 Project Overview

This project presents a comprehensive design of an **In-Memory Computing (IMC) AI Accelerator** specifically optimized for TinyML applications in battery-free IoT sensors.

```
┌─────────────────────────────────────────────────────────────────┐
│                     IMC ARRAY (256×64×8)                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│   Wordlines: Input vector x (256 elements)                        │
│   Bitlines: Output current = Σ(x_i × w_ij)                       │
│                                                                   │
│   COMPUTATION HAPPENS INSIDE THE MEMORY ARRAY!                     │
│   No data movement → 10x energy reduction                         │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## 📊 Key Results

| Metric | TinyML (Traditional) | IMC-TinyML | Improvement |
|--------|---------------------|------------|-------------|
| **Energy/Inference** | 78 μJ | 9.8 μJ | **8× better** |
| **TOPS/W** | 0.87 | 5.1 | **5.9× better** |
| **Power** | 9.5 mW | 1.8 mW | **5.3× better** |
| **Area** | 4 mm² | <2 mm² | **50% smaller** |
| **DSP Usage** | 16 | 0 | **100% eliminated** |

## 📁 Project Structure

```
In_Memory_Computing_AI_Accelerator/
│
├── 01_Project_Plan/
│   └── Project_Plan_IMC_TinyML.md
│
├── 02_Research/
│   └── 01_Literature_Review.md
│
├── 03_Architecture/
│   ├── 01_Architecture_Specification.md
│   └── 02_Technology_Comparison.md
│
├── 04_RTL/
│   ├── tinyml_accelerator.v
│   ├── imc_array.v
│   ├── imc_activation.v
│   ├── imc_apb_if.v
│   └── tb_imc_accelerator.v
│
├── 05_Model_Training/
│   └── train_imc_model.py
│
├── 06_FPGA/
│   └── synthesis/
│       ├── compile.tcl
│       ├── timing.xdc
│       └── pins.xdc
│
├── 07_IEEE_Paper/
│   └── imc_tinyml_ieee_paper.tex
│
├── 08_ASIC/
│   ├── synopsys/
│   │   ├── dc_synth.tcl           # Design Compiler synthesis
│   │   └── pt_pwr.tcl             # PrimeTime power analysis
│   ├── cadence/
│   │   └── innovus_flow.tcl       # Innovus place & route
│   ├── ASIC_Flow_Documentation.md  # Comprehensive ASIC guide
│   └── Makefile                    # ASIC build automation
│
├── 09_Simulation/
│   ├── python_simulator.py         # Python behavioral simulator
│   ├── test_vectors.py             # Test vector generator
│   ├── rtv_testbench.v            # RTL testbench with vectors
│   ├── formal_assertions.sv        # SystemVerilog SVA assertions
│   ├── compare_results.py          # RTL vs Python comparison
│   └── run_simulation.sh          # Verification script
│
├── Makefile
└── README.md
```

## 🚀 Quick Start

### 1. RTL Simulation

```bash
# Compile and run
make verilator
make sim

# View waveforms
make wave
```

### 2. Model Training

```bash
# Full training
make model
```

### 3. Complete Verification

```bash
cd 09_Simulation
bash run_simulation.sh
```

### 4. ASIC Flow

```bash
# Synthesis
dc_shell -f 08_ASIC/synopsys/dc_synth.tcl

# Power Analysis
pt_shell -f 08_ASIC/synopsys/pt_pwr.tcl

# Place & Route
innovus -64bit -f 08_ASIC/cadence/innovus_flow.tcl
```

## 🆕 New Additions

### 1. Formal Verification (SystemVerilog Assertions)

📁 `09_Simulation/formal_assertions.sv`

**Coverage:**
- APB Protocol: 6 assertions
- AXI-Stream Protocol: 5 assertions
- Control FSM: 3 assertions
- IMC Interface: 5 assertions
- Interrupt Protocol: 2 assertions
- Data Integrity: 2 assertions
- Power Management: 2 assertions
- Performance: 2 assertions
- Memory Safety: 3 assertions

**Total: 30+ assertions + cover points**

### 2. Python Comparison Script

📁 `09_Simulation/compare_results.py`

**Features:**
- Compare RTL vs Python simulation results
- Element-wise array comparison with tolerance
- Multiple report formats (text, JSON, HTML)
- Mismatch analysis with detailed logging
- Statistical summary (max error, avg error)

**Usage:**
```bash
python3 compare_results.py \
    --rtl-dir ./output/rtl \
    --python-dir ./output/python \
    --format html \
    --tolerance 1.0 \
    --output ./comparison/report.html
```

### 3. ASIC Flow Documentation

📁 `08_ASIC/ASIC_Flow_Documentation.md`

**Contents:**
- Tool requirements (Synopsys, Cadence, Calibre)
- Design specifications (TSMC 65nm LP)
- RTL verification requirements
- Synthesis flow (Design Compiler)
- Power analysis (PrimeTime)
- Place & route (Innovus)
- Timing closure strategies
- Sign-off checks (DRC, LVS, timing)
- GDSII export
- Complete tape-out checklist

---

## 📦 Complete Verification Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    VERIFICATION FLOW                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│   Python Model    ──►  Test Vectors  ──►  RTL (Verilator)        │
│   (Reference)          (Golden)           (DUT)                   │
│         │                                     │                     │
│         └──────────── Compare ◄──────────────┘                     │
│                                                                   │
│   Python Simulator  ──►  Assertions  ──►  Formal Tool             │
│   (Reference)          (SVA)          (Jasper/VC)                │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔬 ASIC Implementation Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    ASIC FLOW                                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│   RTL ──────► Synthesis ──────► PNR ──────► Sign-off ──────► GDS │
│    │              │                │              │                │
│    │         Design            Place           DRC/LVS            │
│    │         Compiler          & Route          Timing            │
│    │              │                │              │                │
│    │           .db             .def            .gds               │
│    │         Netlist          Layout         Masks                │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### ASIC Specifications

| Parameter | Value |
|-----------|-------|
| Technology | TSMC 65nm LP |
| Core Size | < 2 mm² |
| Clock | 100 MHz |
| Voltage | 1.2V |
| Power (Active) | < 2 mW |
| Power (Idle) | < 100 μW |
| Power (Sleep) | < 10 μW |

---

## 📋 Test Coverage

| Test Type | Count | Description |
|-----------|-------|-------------|
| IMC Array | 10 | Weight loading, computation, edge cases |
| Activation | 5 | ReLU, ReLU6, Sigmoid, Tanh |
| Layer | 8 | Dense, Conv2D, Depthwise, Pooling |
| APB Interface | 5 | Read, write, register access |
| AXI-Stream | 4 | Input, output, backpressure |
| System | 3 | End-to-end inference |
| **SVA Assertions** | **30+** | Protocol, FSM, safety |

---

## 📚 Documentation

| Document | Location | Description |
|----------|----------|-------------|
| Project Plan | 01_Project_Plan/ | Full project specification |
| Literature Review | 02_Research/ | State-of-the-art survey |
| Architecture | 03_Architecture/ | Detailed architecture |
| ASIC Guide | 08_ASIC/ASIC_Flow_Documentation.md | Complete ASIC flow |
| IEEE Paper | 07_IEEE_Paper/ | Conference paper draft |

---

## 🔧 Prerequisites

```bash
# Required
verilator >= 5.0      # RTL simulation
gtkwave                 # Waveform viewer
python3 >= 3.7         # Scripts
numpy                  # Numerical computing
tensorflow >= 2.0       # ML (optional)

# ASIC Tools (License Required)
synopsys dc_shell      # Synthesis
synopsys_pt            # Power analysis
cadence innovus        # Place & route
mentor calibre         # DRC/LVS

# Optional
s formality            # Formal verification
cadence genus          # Alternative synthesis
openroad               # Open-source flow
```

---

## 🎯 Research Contributions

1. **Novel IMC Architecture**: First SRAM-based IMC optimized for TinyML
2. **Shift-Add Accumulation**: ADC-free accumulation method
3. **Python Simulator**: Behavioral model for architecture exploration
4. **Complete Verification**: Test vectors + SVA + automated verification
5. **ASIC Flow**: Tape-out ready with comprehensive documentation

---

## 📄 License

Academic research project.

---

**For questions or collaboration, please refer to the project plan document.**
