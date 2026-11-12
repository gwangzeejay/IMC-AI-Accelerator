# =============================================================================
# PROJECT PLAN: In-Memory Computing AI Accelerator for TinyML
# "An Ultra-Low Power In-Memory Computing Architecture for 
#  Battery-Free Intelligent IoT Sensors"
# =============================================================================

---

## EXECUTIVE SUMMARY

This project proposes the design and implementation of an **In-Memory Computing (IMC) AI Accelerator** specifically optimized for TinyML applications in battery-free IoT sensors. Unlike traditional architectures that move data between memory and compute units, IMC performs matrix-vector multiplication directly within the memory array, eliminating the infamous "memory wall" bottleneck.

The proposed architecture achieves:
- **10x improvement in energy efficiency** compared to traditional accelerators
- **100x reduction in memory bandwidth requirements**
- **Truly batteryless operation** through ultra-low power design
- **On-chip learning capability** for adaptive intelligence

---

## 1. PROJECT OVERVIEW

### 1.1 Problem Statement

Current AI accelerators, including our previously developed TinyML accelerator, suffer from a fundamental limitation: **the memory wall problem**. Data movement between memory and compute units consumes 50-90% of total energy in neural network inference.

For battery-free IoT sensors operating at microwatt power budgets, this limitation is prohibitive. The proposed solution leverages **In-Memory Computing** to perform neural network operations directly within the memory array, eliminating data movement and achieving unprecedented energy efficiency.

### 1.2 Research Objectives

| Objective | Target | Metric |
|-----------|--------|--------|
| Energy Efficiency | >5 TOPS/W | TOPS/W |
| Memory Bandwidth | 0 GB/s external | Eliminated |
| Inference Energy | <10 μJ | Per operation |
| Battery-Free Support | Indoor light | 100 μW harvest |
| Accuracy | >94% | KWS accuracy |
| Area | <2 mm² | 65nm ASIC |

### 1.3 Research Questions

1. **RQ1**: How can we design an in-memory computing architecture that efficiently supports INT8 quantization for neural networks?

2. **RQ2**: What is the optimal organization of memory arrays for matrix-vector multiplication in depthwise separable CNNs?

3. **RQ3**: How do we handle non-ideal effects (noise, variation, sneak paths) while maintaining acceptable accuracy?

4. **RQ4**: Can in-memory computing enable truly batteryless operation for TinyML applications?

---

## 2. LITERATURE SURVEY

### 2.1 In-Memory Computing Fundamentals

In-Memory Computing represents a paradigm shift from traditional von Neumann architecture. Instead of moving data to compute units, IMC performs computation directly within the memory array.

**Key Principle**: For matrix-vector multiplication (y = Wx), each row of weight matrix W is stored in one memory row. The vector x controls wordline activations, and the resulting partial sums appear directly on the bitlines.

### 2.2 State-of-the-Art Review

| Work | Year | Technology | Precision | TOPS/W | Notes |
|------|------|------------|-----------|--------|-------|
| PRIME | 2014 | ReRAM | 2-bit | 0.2 | First IMC for NN |
| ISAAC | 2016 | ReRAM | 1-4 bit | 2.9 | Pipelined IMC |
| PipeLayer | 2017 | ReRAM | 16-bit | 3.9 | Layer pipelining |
| NeuEPU | 2019 | SRAM | 8-bit | 7.5 | SRAM-based |
| MCNN | 2020 | ReRAM | 1-2 bit | 16.5 | Mixed-precision |
| CIMAT | 2021 | SRAM | 8-bit | 34.0 | Current SOTA |
| **This Work** | **2025** | **SRAM/ReRAM** | **INT8** | **>5** | **TinyML focus** |

### 2.3 Technology Comparison

| Technology | Density | Speed | Variation | Maturity | Suitable for TinyML |
|------------|---------|-------|-----------|----------|---------------------|
| SRAM | Low (6T) | Fast | Low | High | Yes (our choice) |
| ReRAM | High | Medium | High | Medium | Future extension |
| MRAM | Medium | Fast | Medium | Medium | Emerging |
| PCM | High | Slow | High | Low | No |

**Decision**: Use SRAM-based IMC for Phase 1 (mature, predictable), ReRAM for Phase 2 (higher density).

---

## 3. SYSTEM ARCHITECTURE

### 3.1 Overall Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   IN-MEMORY COMPUTING AI ACCELERATOR                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                     INPUT BUFFER (1KB)                       │ │
│  │                  (Stores input vector x)                    │ │
│  └──────────────────────────┬──────────────────────────────────┘ │
│                             │                                      │
│                             ▼                                      │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                  IMC COMPUTE ARRAY                             │ │
│  │                                                               │ │
│  │   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐     │ │
│  │   │ 8x256   │  │ 8x256   │  │ 8x256   │  │ 8x256   │     │ │
│  │   │  SRAM   │  │  SRAM   │  │  SRAM   │  │  SRAM   │     │ │
│  │   │ Array   │  │ Array   │  │ Array   │  │ Array   │     │ │
│  │   └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘     │ │
│  │        │            │            │            │            │ │
│  │        └────────────┴────────────┴────────────┘            │ │
│  │                         │                                  │ │
│  │              Bitline Summing Network                       │ │
│  │                         │                                  │ │
│  │                         ▼                                  │ │
│  │   ┌───────────────────────────────────────────────────┐   │ │
│  │   │           SHIFT-ADD ACCUMULATOR                    │   │ │
│  │   │     (Converts analog currents to digital)          │   │ │
│  │   └───────────────────────────────────────────────────┘   │ │
│  │                                                               │ │
│  └───────────────────────────────────────────────────────────┘ │
│                             │                                      │
│                             ▼                                      │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                  DIGITAL ACTIVATION UNIT                      │ │
│  │                   (ReLU, ReLU6, etc.)                        │ │
│  └───────────────────────────────────────────────────────────┘ │
│                             │                                      │
│                             ▼                                      │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                  OUTPUT BUFFER (1KB)                        │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                     CONTROL FSM                               │ │
│  │                  (RISC-V Compatible)                         │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 IMC Array Organization

Each IMC array tile performs one row of matrix-vector multiplication:

```
┌─────────────────────────────────────────────────────────────────┐
│                    IMC ARRAY TILE (8 rows × 256 columns)            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Wordlines (Input x):                                            │
│  ─────────────────────────────────────────────────────────────   │
│  WL[0] ──────┬───────────────────────────────────────────┐       │
│  WL[1] ──────┼───────────────────────────────────────────┤       │
│  WL[2] ──────┼───────────────────────────────────────────┤       │
│  ...  ───────┼───────────────────────────────────────────┤       │
│  WL[7] ──────┴───────────────────────────────────────────┘       │
│                                                                 │
│  Weight Storage (in each cell):                                  │
│  - Each column stores one weight bit                              │
│  - Multiple arrays for multi-bit weights                          │
│                                                                 │
│  Bitlines (Output current):                                      │
│  ─────────────────────────────────────────────────────────────   │
│  BL[0] ──────┐                                                   │
│  BL[1] ──────┼─────► I_out = Σ(x_i × W_i)                       │
│  BL[2] ──────┤     (Current summation happens physically)        │
│  ...  ───────┤                                                    │
│  BL[255] ────┘                                                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 Shift-Add Accumulation

Since bitline currents are analog, we need conversion to digital:

```
┌─────────────────────────────────────────────────────────────────┐
│                    SHIFT-ADD ACCUMULATION                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  For INT8 weights (8 bits):                                      │
│                                                                 │
│  Result = Σ(bitline_current × 2^bit_position)                  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                                                             │ │
│  │   Bit[7] current ──┐                                       │ │
│  │                    ├───► × 128 ──┐                        │ │
│  │   Bit[6] current ──┤             │                        │ │
│  │                    ├───► ×  64 ──┼──► Digital Sum        │ │
│  │   Bit[5] current ──┤             │                        │ │
│  │                    ├───► ×  32 ──┘                        │ │
│  │   ...             │                                        │ │
│  │   Bit[0] current ──┴─────► ×   1 ──► Output               │ │
│  │                                                             │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  Implementation: Current mirrors + SAR ADC + Shift-Add          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. HARDWARE DESIGN

### 4.1 IMC Cell Design

```
┌─────────────────────────────────────────────────────────────────┐
│                      IMC SRAM CELL DESIGN                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Standard 6T SRAM Cell (read mode for IMC):                     │
│                                                                 │
│        WWL                  RWL                                  │
│          │                   │                                    │
│          ▼                   ▼                                    │
│    ┌──────────┐        ┌──────────┐                             │
│    │    Q     │◄──BLB──│          │                             │
│    │          │  BL    │          │                             │
│    └────┬─────┘        └────┬─────┘                             │
│         │                   │                                    │
│         ▼                   ▼                                    │
│    ┌──────────────────────────────┐                             │
│    │      Standard 6T Cell        │                             │
│    │  (WL: wordline, BL/BLB: bitlines)   │                      │
│    └──────────────────────────────┘                             │
│                                                                 │
│  IMC Operation:                                                  │
│  1. Precharge BL and BLB to VDD                                  │
│  2. Assert RWL (read wordline)                                   │
│  3. Cell content and input voltage determine discharge            │
│  4. Multiple cells' currents sum on BL                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Array Organization

```
┌─────────────────────────────────────────────────────────────────┐
│                   ARRAY HIERARCHY                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Level 1: IMC Cell                                                │
│    - 6T SRAM cell                                               │
│    - Stores 1-bit weight                                         │
│                                                                 │
│  Level 2: IMC Bit Slice                                          │
│    - 256 cells in a row                                         │
│    - 8 wordlines (for input bits)                              │
│    - 1 bitline (output)                                        │
│    - Computes: I_bl = Σ(x_j × w_ij)                            │
│                                                                 │
│  Level 3: IMC Tile                                               │
│    - 8 bit slices (for INT8)                                    │
│    - Shares wordlines                                           │
│    - Produces 8-bit partial sum                                 │
│                                                                 │
│  Level 4: IMC Array Block                                        │
│    - Multiple tiles                                              │
│    - Different weight rows                                       │
│    - Pipelined computation                                       │
│                                                                 │
│  Level 5: Full Accelerator                                       │
│    - 4 array blocks                                             │
│    - Digital periphery                                           │
│    - Control logic                                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 Peripheral Circuit Design

```
┌─────────────────────────────────────────────────────────────────┐
│                    PERIPHERAL CIRCUITS                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. WORDLINE DRIVER                                               │
│     - Level shifter (digital to analog)                          │
│     - Voltage: 0-0.8V input to 0-1.0V wordline                  │
│     - Drives 256 cells                                           │
│                                                                 │
│  2. BITLINE SENSING                                              │
│     - Current mirror for current-to-voltage conversion           │
│     - Sense amplifier for small signals                          │
│     - Offset cancellation                                        │
│                                                                 │
│  3. SHIFT-ADD ACCUMULATOR                                        │
│     - 8:1 analog MUX                                            │
│     - Sample and hold                                             │
│     - Successive approximation ADC (8-bit)                       │
│     - Digital adder tree                                         │
│                                                                 │
│  4. OUTPUT REGISTERS                                             │
│     - Pipeline registers between stages                           │
│     - Result latching                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. AI MODEL OPTIMIZATION

### 5.1 IMC-Aware Model Design

Standard neural networks assume arbitrary precision in memory access. IMC imposes constraints:

| Constraint | Impact | Mitigation |
|------------|--------|------------|
| Weight precision | Limited by cell stability | Multi-cell per bit |
| Input precision | Limited by wordline voltage | Analog input encoding |
| MAC precision | Limited by ADC resolution | Quantization-aware training |
| Array size | Limited by sneak paths | Tiling and streaming |

### 5.2 Model Architecture: IMC-DS-CNN

```
┌─────────────────────────────────────────────────────────────────┐
│                   IMC-OPTIMIZED DS-CNN                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Layer      │ Type        │ Weights │ IMC Fit  │ Adaptation        │
│  ─────────────────────────────────────────────────────────────  │
│  Conv1     │ Conv2D      │ 288     │ Perfect  │ Standard          │
│  Separable1│ Depthwise   │ 576     │ Perfect  │ 8-bit weights     │
│  Separable2│ Depthwise   │ 1.15K   │ Perfect  │ 8-bit weights     │
│  ...       │ ...         │ ...     │ Perfect  │ Tiling for large  │
│  FC        │ Dense       │ 7K      │ Perfect  │ Direct mapping    │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  Key Adaptation:                                                  │
│  - All layers fit in IMC arrays (tiling for large layers)         │
│  - Weights quantized to 8-bit (matches ADC)                       │
│  - Activations use analog encoding                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.3 Tiling Strategy

For layers larger than IMC array capacity:

```
┌─────────────────────────────────────────────────────────────────┐
│                        LAYER TILING                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Large Weight Matrix:                                            │
│  ┌─────────────────────────────────┐                            │
│  │                                 │                            │
│  │   W (Rows × Cols)               │                            │
│  │                                 │                            │
│  └─────────────────────────────────┘                            │
│           │                                                        │
│           ▼                                                        │
│  ┌───┬───┬───┬───┐                                              │
│  │W00│W01│...│W0n│  Row tiles                                    │
│  ├───┼───┼───┼───┤                                              │
│  │W10│W11│...│W1n│                                              │
│  ├───┼───┼───┼───┤                                              │
│  │...│...│...│...│                                              │
│  ├───┼───┼───┼───┤                                              │
│  │Wm0│Wm1│...│Wmn│                                              │
│  └───┴───┴───┴───┘                                              │
│                                                                 │
│  Computation:                                                    │
│  1. Load tile W_ij into IMC array                                │
│  2. Apply input x_j                                               │
│  3. Read partial sum p_ij                                          │
│  4. Accumulate: y_i = Σ(p_ij)                                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. IMPLEMENTATION PLAN

### 6.1 Project Phases

| Phase | Duration | Tasks | Deliverables |
|-------|----------|-------|--------------|
| **Phase 1: Design** | 8 weeks | Architecture, circuit design, model optimization | Specification, RTL design |
| **Phase 2: Simulation** | 6 weeks | Circuit simulation, model training, accuracy analysis | Verified design |
| **Phase 3: Implementation** | 8 weeks | RTL to GDS, place and route, sign-off | ASIC layout |
| **Phase 4: Validation** | 6 weeks | Chip test, benchmark, comparison | Test results |
| **Phase 5: Documentation** | 4 weeks | Paper writing, thesis | Publication |

**Total: 32 weeks (2 semesters)**

### 6.2 Detailed Timeline

```
Semester 1:
──────────
Week 1-2:   Literature review, technology selection
Week 3-4:   Architecture design, cell design
Week 5-6:   Array organization, peripheral circuits
Week 7-8:   AI model design, quantization
Week 9-10:  RTL implementation (Phase 1)
Week 11-12: RTL verification, simulation
Week 13-14: Circuit-level simulation
Week 15-16: Model accuracy validation
Week 17-18: Mid-term review, corrections
Week 19-20: Architecture refinement

Semester 2:
──────────
Week 1-4:   ASIC implementation (synthesis, PnR)
Week 5-8:   Timing closure, power optimization
Week 9-12:  Layout verification, DRC/LVS
Week 13-16: Chip fabrication (tape-out)
Week 17-20: Chip testing, benchmark
Week 21-24: Paper writing, thesis
Week 25-28: Final defense preparation
```

### 6.3 Milestones

| Milestone | Week | Description |
|-----------|------|-------------|
| M1 | 8 | Complete architecture specification |
| M2 | 12 | RTL implementation complete |
| M3 | 16 | Model accuracy >94% verified |
| M4 | 24 | ASIC layout complete |
| M5 | 28 | Tape-out ready |
| M6 | 36 | Testing complete |
| M7 | 40 | Paper submitted |

---

## 7. RESOURCES REQUIRED

### 7.1 EDA Tools

| Tool | Purpose | Access |
|------|---------|--------|
| Cadence Virtuoso | Circuit design, layout | University license |
| Synopsys DC | Synthesis | University license |
| Cadence Innovus | Place and route | University license |
| Mentor Calibre | DRC/LVS | University license |
| MATLAB/Python | Model training | Open source |
| Verilator | RTL simulation | Open source |

### 7.2 Hardware

| Item | Purpose | Cost |
|------|---------|------|
| HPC Cluster | Simulation | University |
| ASIC fabrication (65nm) | Chip test | $50K |
| FPGA board | Prototype | $5K |
| Test equipment | Chip testing | $10K |

### 7.3 Team

| Role | Responsibility | Time |
|------|---------------|------|
| Lead researcher | Architecture, circuits | 100% |
| ML researcher | Model design, training | 50% |
| RTL engineer | Digital design, verification | 50% |
| Layout engineer | Physical design | 30% |

---

## 8. EXPECTED OUTCOMES

### 8.1 Technical Contributions

1. **Novel IMC Architecture**: First SRAM-based IMC accelerator optimized for TinyML
2. **IMC-Aware Training**: Quantization method preserving accuracy with IMC constraints
3. **Circuit Techniques**: Novel sensing and accumulation circuits for IMC
4. **System Integration**: Complete batteryless TinyML system design

### 8.2 Publications

| Venue | Target | Timeline |
|-------|--------|----------|
| IEEE ISCAS | Main paper | Month 10 |
| ACM/IEEE Embedded Systems | Application | Month 12 |
| IEEE JSSC | Full paper | Month 18 |
| VLSID | Architecture | Month 8 |

### 8.3 Performance Targets

| Metric | This Work | IMC SOTA | TinyML SOTA |
|--------|-----------|----------|-------------|
| TOPS/W | >5 | 34 (CIMAT) | 0.87 |
| Energy/inference | <10 μJ | N/A | 78 μJ |
| Area | <2 mm² | 6.6 mm² | 4 mm² |
| Batteryless | Yes | No | Partial |

**Note**: Our focus on TinyML (vs full DNN) enables different optimization trade-offs.

---

## 9. RISK ANALYSIS

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Sensing margin insufficient | Medium | High | Redundant sensing, error correction |
| Variation effects worse than expected | Medium | Medium | Monte Carlo simulation, margining |
| Model accuracy loss | High | Medium | Extensive QAT, mixed precision |
| Tape-out delay | Low | High | Early engagement with fab |
| Test setup issues | Medium | Medium | FPGA prototype first |

---

## 10. CONCLUSION

This project proposes a comprehensive investigation into In-Memory Computing AI accelerators for TinyML applications. By eliminating the memory wall bottleneck, we aim to achieve 10x improvement in energy efficiency, enabling truly batteryless intelligent IoT sensors.

The multi-disciplinary nature of this project combines:
- Circuit design (IMC cells, sensing)
- Architecture (array organization, dataflow)
- Machine learning (model optimization, quantization)
- Systems (battery-free operation)

This positions it as a significant contribution to the field of ultra-low power AI hardware.

---

*Document Version: 1.0*
*In-Memory Computing AI Accelerator Project Plan*
*Created: [Current Date]*
