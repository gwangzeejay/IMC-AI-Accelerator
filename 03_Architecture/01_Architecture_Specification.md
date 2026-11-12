# =============================================================================
# ARCHITECTURE SPECIFICATION: In-Memory Computing AI Accelerator for TinyML
# =============================================================================

---

## TABLE OF CONTENTS

1. [Overview](#1-overview)
2. [System Architecture](#2-system-architecture)
3. [IMC Array Design](#3-imc-array-design)
4. [Peripheral Circuits](#4-peripheral-circuits)
5. [Control Architecture](#5-control-architecture)
6. [Memory Architecture](#6-memory-architecture)
7. [AI Model Mapping](#7-ai-model-mapping)
8. [Power Management](#8-power-management)
9. [Interface Specification](#9-interface-specification)
10. [Performance Specifications](#10-performance-specifications)

---

## 1. OVERVIEW

### 1.1 Architecture Name

**IMC-TinyML**: In-Memory Computing Accelerator for Tiny Machine Learning

### 1.2 Design Goals

| Goal | Target | Rationale |
|------|--------|-----------|
| Energy Efficiency | >5 TOPS/W | 10x improvement over TinyML |
| Inference Energy | <10 μJ | Enable battery-free operation |
| Peak Throughput | 2 GOPS | Sufficient for TinyML models |
| Precision | INT8 | Balance accuracy and efficiency |
| Area | <2 mm² | Suitable for IoT integration |
| Power | <2 mW peak | Support energy harvesting |

### 1.3 Target Applications

| Application | Model | MACs/Inference | Target Energy |
|-------------|-------|----------------|---------------|
| Keyword Spotting | DS-CNN | 826K | 8 μJ |
| Activity Recognition | CNN-LSTM | 450K | 5 μJ |
| Anomaly Detection | Autoencoder | 200K | 3 μJ |
| Gesture Recognition | Depthwise CNN | 600K | 6 μJ |

### 1.4 Technology Node

| Parameter | Value | Notes |
|-----------|-------|-------|
| Process | TSMC 65nm LP | Mature, low leakage |
| Library | Standard cell | For digital periphery |
| Memory | Custom SRAM | For IMC arrays |
| Metal | 6 metal layers | Sufficient for routing |

---

## 2. SYSTEM ARCHITECTURE

### 2.1 Top-Level Block Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        IMC-TinyML ACCELERATOR                               │
│                        (Top-Level System)                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│    ┌─────────────────────────────────────────────────────────────────┐  │
│    │                      SYSTEM INTERFACE                               │  │
│    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │  │
│    │  │   APB      │  │  AXI-Stream │  │   RISC-V    │            │  │
│    │  │  Config    │  │    I/F      │  │   Custom    │            │  │
│    │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘            │  │
│    │         └────────────────┼────────────────┘                    │  │
│    └───────────────────────────┼──────────────────────────────────────┘  │
│                                │                                           │
│                                ▼                                           │
│    ┌─────────────────────────────────────────────────────────────────┐  │
│    │                      CONTROL FSM                                     │  │
│    │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │  │
│    │  │  Config  │ │  Layer   │ │  Compute │ │  Status  │            │  │
│    │  │ Decoder  │ │ Decoder  │ │ Scheduler│ │ Monitor  │            │  │
│    │  └──────────┘ └──────────┘ └──────────┘ └──────────┘            │  │
│    └───────────────────────────┬──────────────────────────────────────┘  │
│                                │                                           │
│    ┌───────────────────────────┼──────────────────────────────────────┐  │
│    │                           ▼                                        │  │
│    │  ┌───────────────────────────────────────────────────────────┐  │  │
│    │  │              IMC COMPUTE CORE                              │  │  │
│    │  │                                                           │  │  │
│    │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │  │  │
│    │  │  │ IMC     │ │ IMC     │ │ IMC     │ │ IMC     │        │  │  │
│    │  │  │ Tile 0  │ │ Tile 1  │ │ Tile 2  │ │ Tile 3  │        │  │  │
│    │  │  │ 256×64  │ │ 256×64  │ │ 256×64  │ │ 256×64  │        │  │  │
│    │  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘        │  │  │
│    │  │       └───────────┼───────────┼───────────┘              │  │  │
│    │  │                   │           │                          │  │  │
│    │  │           ┌───────┴───────────┴───────┐                   │  │  │
│    │  │           │  Bitline Summing Network  │                   │  │  │
│    │  │           └───────┬───────────┬───────┘                   │  │  │
│    │  │                   │           │                           │  │  │
│    │  │           ┌───────┴───────────┴───────┐                   │  │  │
│    │  │           │  Shift-Add Accumulator   │                   │  │  │
│    │  │           └───────┬───────────┬───────┘                   │  │  │
│    │  │                   │           │                           │  │  │
│    │  └───────────────────┼───────────┼───────────────────────────┘  │  │
│    │                      │           │                              │  │
│    └──────────────────────┼───────────┼──────────────────────────────┘  │
│                           │           │                                 │
│                           ▼           ▼                                 │
│    ┌─────────────────────────────────────────────────────────────────┐  │
│    │                   DIGITAL ACTIVATION UNIT                            │  │
│    │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐               │  │
│    │  │  ReLU   │ │  ReLU6  │ │ Sigmoid │ │ Tanh    │               │  │
│    │  └─────────┘ └─────────┘ └─────────┘ └─────────┘               │  │
│    └─────────────────────────────────────────────────────────────────┘  │
│                                │                                           │
│                                ▼                                           │
│    ┌─────────────────────────────────────────────────────────────────┐  │
│    │                      OUTPUT BUFFER                                   │  │
│    │  ┌───────────────────────────────────────────────────────────┐  │  │
│    │  │              256 × 32-bit Register File                     │  │  │
│    │  └───────────────────────────────────────────────────────────┘  │  │
│    └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│    ┌─────────────────────────────────────────────────────────────────┐  │
│    │                     POWER MANAGEMENT UNIT                           │  │
│    │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │  │
│    │  │  Level   │ │  Sleep   │ │  Clock   │ │  Power   │            │  │
│    │  │  Shifter  │ │ Controller│ │ Gating   │ │ Gating   │            │  │
│    │  └──────────┘ └──────────┘ └──────────┘ └──────────┘            │  │
│    └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Signal Description

| Signal | Width | Direction | Description |
|--------|-------|-----------|-------------|
| clk | 1 | Input | System clock (100 MHz) |
| rst_n | 1 | Input | Active low reset |
| paddr | 32 | Input | APB address |
| pwdata | 32 | Input | APB write data |
| prdata | 32 | Output | APB read data |
| psel | 1 | Input | APB select |
| penable | 1 | Input | APB enable |
| pwrite | 1 | Input | APB write enable |
| pready | 1 | Output | APB ready |
| s_axis_tvalid | 1 | Input | Input valid |
| s_axis_tready | 1 | Output | Input ready |
| s_axis_tdata | 32 | Input | Input data |
| m_axis_tvalid | 1 | Output | Output valid |
| m_axis_tready | 1 | Input | Output ready |
| m_axis_tdata | 32 | Output | Output data |
| interrupt | 1 | Output | Computation done |

### 2.3 Clock Domains

| Domain | Frequency | Source | Purpose |
|--------|-----------|--------|---------|
| sys_clk | 100 MHz | External | System control, APB |
| imc_clk | 200 MHz | PLL | IMC sensing, ADC |
| digital_clk | 100 MHz | Gated sys | Digital compute |

---

## 3. IMC ARRAY DESIGN

### 3.1 IMC Tile Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          IMC TILE (256 rows × 64 columns)                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  WORDLINE DRIVERS (256 rows)                                          │
│  ───────────────────────────────────────────────────────────────────── │
│                                                                         │
│      WL[0]   ──┬─────────────────────────────────────────────────┐   │
│      WL[1]   ──┼─────────────────────────────────────────────────┤   │
│      WL[2]   ──┼─────────────────────────────────────────────────┤   │
│        │      │                                                      │
│        │      │   ┌───────────────────────────────────────────┐   │
│        │      │   │                                           │   │
│        │      │   │   6T SRAM CELL MATRIX                   │   │
│        │      │   │   (256 rows × 64 columns)                  │   │
│        │      │   │                                           │   │
│        │      │   │   Each cell stores 1 weight bit           │   │
│        │      │   │   Multiple cells for multi-bit            │   │
│        │      │   │                                           │   │
│        │      │   └───────────────────────────────────────────┘   │
│        │      │                                                      │
│      WL[255] ──┴─────────────────────────────────────────────────┘   │
│                                                                         │
│  ───────────────────────────────────────────────────────────────────── │
│  BITLINE SENSING (64 columns)                                          │
│                                                                         │
│      BL[0]   ──┐                                                      │
│      BL[1]   ──┼──► Current Mirror ──► Sense Amp ──► ADC Input       │
│      BL[2]   ──┤                                                      │
│       │      │                                                         │
│      BL[63] ──┘                                                       │
│                                                                         │
│  ───────────────────────────────────────────────────────────────────── │
│  CONTROL SIGNALS                                                       │
│  ───────────────────────────────────────────────────────────────────── │
│                                                                         │
│      WL_EN[7:0]     - Wordline enable (8 groups)                     │
│      BL_PRECH       - Bitline precharge                               │
│      SENSE_EN       - Sensing enable                                  │
│      ADC_START      - ADC conversion start                            │
│      ARRAY_RST     - Array reset                                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 IMC Cell Design

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     6T SRAM CELL (IMC Mode)                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Schematic:                                                            │
│                                                                         │
│         WWL                RWL                                          │
│          │                  │                                            │
│          │                  │                                            │
│          ▼                  ▼                                            │
│      ┌──────┐          ┌──────┐                                         │
│      │  M5  │          │  M6  │                                        │
│      └──┬───┘          └──┬───┘                                        │
│         │                 │                                             │
│    BLB──┼─────────────┬───┼───BL                                         │
│          │             │   │                                             │
│       ┌──┴──┐       │ ┌──┴──┐                                         │
│       │  M1  │◄────┐ │ │  M3  │                                        │
│       └──┬───┘    │ │ └──┬───┘                                        │
│          │       │ │    │                                             │
│          └───────┼─┴─┘  │                                             │
│                  │       │                                             │
│               ┌──┴───┐ │ ┌┴───┐                                        │
│               │   M2   │ │ │   M4   │                                   │
│               └───────┘ │ └─────┘                                     │
│                         │                                              │
│                      ┌───┴───┐                                          │
│                      │   Q   │◄── STORAGE NODE                         │
│                      └───────┘                                          │
│                                                                         │
│  Standard 6T SRAM Cell:                                                │
│  - M1-M2: Pull-down (NL)                                              │
│  - M3-M4: Pull-up (PL)                                                │
│  - M5-M6: Access transistors                                          │
│                                                                         │
│  IMC Operation:                                                        │
│  1. Precharge BL, BLB to VDD                                         │
│  2. Set RWL = V_ref (analog input)                                    │
│  3. Cell pulls down BL proportional to stored value                    │
│  4. Multiple cells' currents sum on BL                                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Array Organization Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| Rows per tile | 256 | Number of input channels |
| Columns per tile | 64 | Output resolution |
| Tiles total | 4 | Parallel output channels |
| Bit-slice depth | 8 | For INT8 weights |
| Total cells | 4 × 256 × 64 × 8 = 524,288 | |

### 3.4 Bit-Slice Organization

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       BIT-SLICE ORGANIZATION (INT8)                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  For INT8 weights (8 bits per weight):                                 │
│                                                                         │
│      Weight[7]    Weight[6]    Weight[5]    ...    Weight[0]         │
│         │             │             │                  │               │
│         ▼             ▼             ▼                  ▼               │
│   ┌───────────┐ ┌───────────┐ ┌───────────┐      ┌───────────┐        │
│   │ Bit-Slice │ │ Bit-Slice │ │ Bit-Slice │      │ Bit-Slice │        │
│   │     7     │ │     6     │ │     5     │  ... │     0     │        │
│   │           │ │           │ │           │      │           │        │
│   │  256×64   │ │  256×64   │ │  256×64   │      │  256×64   │        │
│   │   cells   │ │   cells   │ │   cells   │      │   cells   │        │
│   └─────┬─────┘ └─────┬─────┘ └─────┬─────┘      └─────┬─────┘        │
│         │             │             │                  │               │
│         │             │             │                  │               │
│         ▼             ▼             ▼                  ▼               │
│      I_bit7        I_bit6        I_bit5            I_bit0           │
│         │             │             │                  │               │
│         └─────────────┴─────────────┴──────────────────┘               │
│                              │                                          │
│                              ▼                                          │
│                    ┌───────────────────┐                                │
│                    │   Shift-Add      │                                │
│                    │   Accumulator    │                                │
│                    │                   │                                │
│                    │  = I7×2^7 + I6×2^6 + ... + I0×2^0              │
│                    └────────┬──────────┘                                │
│                             │                                           │
│                             ▼                                           │
│                      Digital Output                                     │
│                      (8-bit result)                                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. PERIPHERAL CIRCUITS

### 4.1 Wordline Driver

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         WORDLINE DRIVER                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Function: Convert digital input to analog wordline voltage             │
│                                                                         │
│  Input:   V_in[7:0]   - 8-bit digital input                           │
│  Output:  V_wl        - 0-1.0V wordline voltage                       │
│                                                                         │
│  Circuit:                                                               │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                                                                 │  │
│  │   V_in[7:0]  ──►  DAC  ──►  Level Shifter  ──►  V_wl       │  │
│  │                     │           │                                │  │
│  │                     │           │                                │  │
│  │              8-bit DAC      Voltage translation               │  │
│  │            (8 levels)         (0.8V → 1.0V)                   │  │
│  │                                                                 │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  Specifications:                                                        │
│  - Voltage range: 0 - 1.0V                                             │
│  - Resolution: 8 levels (3-bit effective)                             │
│  - Drive strength: 256 cells                                          │
│  - settling time: < 500 ps                                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Current Mirror Sensing

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      CURRENT MIRROR SENSOR                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Function: Convert bitline current to voltage for ADC                    │
│                                                                         │
│  Circuit:                                                               │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                                                                 │  │
│  │                        VDD                                       │  │
│  │                          │                                       │  │
│  │                   ┌──────┴──────┐                                │  │
│  │                   │             │                                │  │
│  │              ┌────┴────┐   ┌────┴────┐                           │  │
│  │              │   M1    │   │   M2    │   Current Mirror        │  │
│  │              │ (N×W)   │───│  (1×W)  │                           │  │
│  │              └────┬────┘   └────┬────┘                           │  │
│  │                   │             │                                 │  │
│  │                   │        ┌────┴────┐                            │  │
│  │                   │        │          │                            │  │
│  │                   │    BL  │          │    BL_out                 │  │
│  │                   └────┬────┘          │─────┬────                 │  │
│  │                        │               │     │                    │  │
│  │                    ┌───┴───┐            │     │                    │  │
│  │                    │ Cell  │           │     │                    │  │
│  │                    │ Array │           │     │                    │  │
│  │                    └───┬───┘           │     │                    │  │
│  │                        │               │     │                    │  │
│  │                   I_BL (sum)        I_sense                      │  │
│  │                                                                 │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  Operation:                                                           │
│  1. Current mirror copies I_BL to I_sense                            │
│  2. I_sense creates voltage drop across load resistor               │
│  3. Differential sensing for better SNR                             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Shift-Add Accumulator

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      SHIFT-ADD ACCUMULATOR                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Function: Convert bit-serial analog to digital output                  │
│                                                                         │
│  Architecture:                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                                                                 │  │
│  │   Bit[7] current  ──┐                                            │  │
│  │                     ├───► ×128 ──┐                              │  │
│  │   Bit[6] current  ──┤               │                          │  │
│  │                     ├───►  ×64 ────┼────► Digital Sum         │  │
│  │   Bit[5] current  ──┤               │                          │  │
│  │                     ├───►  ×32 ────┘                          │  │
│  │        ...         │                                            │  │
│  │   Bit[0] current  ──┴────►  ×1  ────► Output                   │  │
│  │                                                                 │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  Implementation:                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                                                                 │  │
│  │   8:1 MUX  ──►  Sample/Hold  ──►  SAR ADC  ──►  Shift-Add   │  │
│  │                                                                 │  │
│  │   - 8:1 MUX selects which bit-slice to sample                 │  │
│  │   - Sample/Hold captures the current                          │  │
│  │   - SAR ADC converts to digital (8-bit)                       │  │
│  │   - Shift-Add weights by position                              │  │
│  │                                                                 │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  Timing:                                                               │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  Cycle 1-8:  Sample each bit-slice (1 cycle each)             │  │
│  │  Cycle 9:     ADC conversion                                   │  │
│  │  Cycle 10:    Shift-add accumulation                           │  │
│  │                                                                 │  │
│  │  Total: 10 cycles per output                                   │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.4 ADC Specification

| Parameter | Value | Description |
|-----------|-------|-------------|
| Type | SAR | Successive Approximation |
| Resolution | 8-bit | Matches weight precision |
| Sampling Rate | 200 MS/s | Per channel |
| ENOB | >7.5 bits | Effective number of bits |
| Power | <100 μW | Per ADC |
| Area | <0.01 mm² | Per ADC |

---

## 5. CONTROL ARCHITECTURE

### 5.1 FSM State Machine

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CONTROL FSM                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│    ┌─────────┐                                                        │
│    │  IDLE   │◄───────────────────────────────────────┐              │
│    └────┬────┘                                                │              │
│         │ Start                                               │              │
│         ▼                                                     │              │
│    ┌─────────┐     ┌─────────────┐      ┌─────────────┐      │              │
│    │  LOAD   │────►│   FETCH    │─────►│  COMPUTE    │──────┘              │
│    │  CONFIG │     │  WEIGHTS   │      │   LAYER     │                      │
│    └────┬────┘     └──────┬──────┘      └──────┬──────┘                      │
│         │                 │                     │                              │
│         │                 │                     │ More tiles                    │
│         │                 │                     ▼                              │
│         │                 │              ┌─────────────┐                     │
│         │                 │              │    ACCUM    │                     │
│         │                 │              │   PARTIAL   │                     │
│         │                 │              └──────┬──────┘                     │
│         │                 │                     │                              │
│         │                 │                     │ Done                        │
│         │                 │                     ▼                              │
│         │                 │              ┌─────────────┐                     │
│         │                 │              │  ACTIVATION│                     │
│         │                 │              └──────┬──────┘                     │
│         │                 │                     │                              │
│         │                 │                     │ Done                        │
│         │                 │                     ▼                              │
│         │                 │              ┌─────────────┐                     │
│         │                 │              │    STORE    │                     │
│         │                 │              │   OUTPUT   │                     │
│         │                 │              └──────┬──────┘                     │
│         │                 │                     │                              │
│         │                 │                     │ More layers                 │
│         │                 │                     ▼                              │
│         │                 │              ┌─────────────┐                     │
│         │                 │              │    NEXT    │─────────────────────►│
│         │                 │              │    LAYER   │                     │
│         │                 │              └─────────────┘                     │
│         │                 │                     │                              │
│         │                 │                     │ Done                        │
│         │                 │                     ▼                              │
│         │                 │              ┌─────────────┐                     │
│         │                 │              │   DONE     │─────────────────────►│
│         │                 │              └─────────────┘                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Layer Configuration

| Parameter | Bits | Description |
|-----------|------|-------------|
| layer_type | 2 | 00=Conv, 01=Dense, 10=Pool, 11=Act |
| input_rows | 8 | Input height |
| input_cols | 8 | Input width |
| input_channels | 8 | Input feature maps |
| output_channels | 8 | Output feature maps |
| kernel_size | 3 | Conv kernel (3x3) |
| stride | 2 | Stride (1 or 2) |
| activation | 2 | 00=None, 01=ReLU, 10=ReLU6 |
| pooling | 2 | 00=None, 01=Max, 10=Avg |

### 5.3 Address Generation

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       ADDRESS GENERATOR                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Generates addresses for:                                                │
│  1. Weight tiles in IMC arrays                                        │
│  2. Input activation buffer                                           │
│  3. Output partial sum buffer                                         │
│                                                                         │
│  Architecture:                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                                                                 │  │
│  │   Layer Config  ──►  Loop Counter  ──►  Address Generator    │  │
│  │                                                                 │  │
│  │   ┌──────────┐    ┌──────────┐    ┌──────────────────┐         │  │
│  │   │  Row     │    │  Row     │    │                  │         │  │
│  │   │  Count   │───►│  Addr    │───►│  Wordline Addr  │         │  │
│  │   │  (N)     │    │  (log2N) │    │  (WL[7:0])      │         │  │
│  │   └──────────┘    └──────────┘    └──────────────────┘         │  │
│  │                                                                 │  │
│  │   ┌──────────┐    ┌──────────┐    ┌──────────────────┐         │  │
│  │   │  Col     │    │  Col     │    │  Bitline Addr   │         │  │
│  │   │  Count   │───►│  Addr    │───►│  (BL[5:0])     │         │  │
│  │   │  (M)     │    │  (log2M) │    │                  │         │  │
│  │   └──────────┘    └──────────┘    └──────────────────┘         │  │
│  │                                                                 │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  Supports:                                                             │
│  - Direct mapping (weights fit in array)                              │
│  - Tiling (large weights)                                             │
│  - Striding (for convolution)                                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 6. MEMORY ARCHITECTURE

### 6.1 Memory Hierarchy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        MEMORY HIERARCHY                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Level 0: IMC Arrays                                                   │
│  ───────────────────────────────────────────────────────────────────── │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  Capacity: 64 KB (4 tiles × 256×64×8 bits)                     │  │
│  │  Purpose: Weight storage + computation                          │  │
│  │  Latency: 1 cycle (analog)                                    │  │
│  │  Energy: 0.1 fJ/bit (computation)                             │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  Level 1: Activation Buffer                                             │
│  ───────────────────────────────────────────────────────────────────── │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  Capacity: 8 KB                                                 │  │
│  │  Organization: 2048 × 32-bit                                    │  │
│  │  Purpose: Input/output activation storage                       │  │
│  │  Latency: 1 cycle                                             │  │
│  │  Energy: 0.5 pJ/read                                           │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  Level 2: Configuration Registers                                       │
│  ───────────────────────────────────────────────────────────────────── │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  Capacity: 256 bytes                                            │  │
│  │  Organization: 64 × 32-bit                                     │  │
│  │  Purpose: Layer configuration, control                          │  │
│  │  Latency: 1 cycle                                             │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Activation Buffer Specification

| Parameter | Value | Description |
|-----------|-------|-------------|
| Capacity | 8 KB | 2048 × 32-bit |
| Ports | 2R+1W | Dual read, single write |
| Latency | 1 cycle | Pipelined access |
| Organization | 64 banks × 32 words | Banked for parallelism |
| ECC | Optional | Single-bit error correction |

---

## 7. AI MODEL MAPPING

### 7.1 DS-CNN Mapping

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     DS-CNN LAYER MAPPING                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Layer 1: Conv2D (1→16 channels, 49×40 input)                         │
│  ───────────────────────────────────────────────────────────────────── │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  Kernel: 5×5×1×16 = 400 weights                                │  │
│  │  IMC Mapping: Direct (fits in 256×64 array)                     │  │
│  │  Computation: 49×40×16×25 = 784,000 MACs                      │  │
│  │  Tiling: Not required                                         │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  Layers 2-11: Depthwise Separable Conv (64→64 channels)                │
│  ───────────────────────────────────────────────────────────────────── │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  Depthwise: 3×3×64 = 576 weights                              │  │
│  │  Pointwise: 64×64 = 4,096 weights                             │  │
│  │  IMC Mapping: Tiling for pointwise (4096 > 256)                │  │
│  │  Depthwise: Direct mapping (576 < 256)                         │  │
│  │  Tiling strategy: 4 tiles × 256 weights                        │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  Layer 12: Dense (576→12 classes)                                       │
│  ───────────────────────────────────────────────────────────────────── │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  Weights: 576×12 = 6,912                                      │  │
│  │  IMC Mapping: Direct (6912/4 tiles = 1728 per tile)            │  │
│  │  Computation: 576×12 = 6,912 MACs                              │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Tiling Strategy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          WEIGHT TILING                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  For pointwise layer (64 inputs → 64 outputs):                         │
│                                                                         │
│  Weight Matrix W (64×64):                                               │
│  ┌────┬────┬────┬────┐                                                  │
│  │W00 │W01 │... │W0n │  Row tile 0 (256 cols)                         │
│  ├────┼────┼────┼────┤                                                  │
│  │W10 │W11 │... │W1n │  Row tile 1 (256 cols)                         │
│  ├────┼────┼────┼────┤                                                  │
│  │... │... │... │... │  Row tile 2 (256 cols)                         │
│  ├────┼────┼────┼────┤                                                  │
│  │Wm0 │Wm1 │... │Wmn │  Row tile 3 (256 cols)                         │
│  └────┴────┴────┴────┘                                                  │
│                                                                         │
│  Computation Flow:                                                      │
│  1. Load Tile 0 → IMC arrays                                          │
│  2. Apply input vector x[0:255]                                       │
│  3. Read partial sum P0                                               │
│  4. Load Tile 1 → IMC arrays                                          │
│  5. Apply input vector x[256:511]                                     │
│  6. Read partial sum P1                                               │
│  7. Accumulate: y = P0 + P1                                           │
│  8. Repeat for all tiles                                              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 8. POWER MANAGEMENT

### 8.1 Power Domains

| Domain | Voltage | Purpose | Power Gating |
|--------|---------|---------|--------------|
| IMC Arrays | 1.0V | SRAM arrays | Yes (per tile) |
| Digital | 1.0V | Control, activation | Yes |
| ADC | 1.2V | Sensing circuits | Yes (per ADC) |
| SRAM buffers | 1.0V | Activation storage | Partial |
| IO | 3.3V | External interface | No |

### 8.2 Power States

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          POWER STATES                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────┐                                                         │
│  │  ACTIVE  │  Full power, all circuits active                       │
│  │  100%    │  Target: 2 mW @ 100 MHz                               │
│  └────┬─────┘                                                         │
│       │                                                                │
│       │ Compute idle                                                   │
│       ▼                                                                │
│  ┌──────────┐                                                         │
│  │  IDLE    │  IMC arrays active, digital reduced                     │
│  │   50%    │  Target: 1 mW                                          │
│  └────┬─────┘                                                         │
│       │                                                                │
│       │ No inference                                                   │
│       ▼                                                                │
│  ┌──────────┐                                                         │
│  │  LIGHT   │  IMC in retention, critical logic on                   │
│  │   10%    │  Target: 200 μW                                        │
│  └────┬─────┘                                                         │
│       │                                                                │
│       │ Standby                                                        │
│       ▼                                                                │
│  ┌──────────┐                                                         │
│  │  SLEEP   │  Only retention SRAM on                                │
│  │   1%     │  Target: 20 μW                                          │
│  └────┬─────┘                                                         │
│       │                                                                │
│       │ Wake event                                                     │
│       ▼                                                                │
│  ┌──────────┐                                                         │
│  │  OFF     │  Everything off, wake timer active                     │
│  │   0.1%   │  Target: 2 μW                                          │
│  └──────────┘                                                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 8.3 Clock Gating

| Module | Clock Gating | Savings |
|--------|--------------|---------|
| IMC Tiles | Per-tile | 75% |
| ADC | Per-channel | 50% |
| Activation Unit | Full | 30% |
| Control FSM | When idle | 20% |
| Address Gen | When idle | 15% |

---

## 9. INTERFACE SPECIFICATION

### 9.1 APB Register Map

| Address | Name | Access | Description |
|---------|------|--------|-------------|
| 0x00 | CTRL | RW | Control register |
| 0x04 | STATUS | RO | Status register |
| 0x08 | INT_EN | RW | Interrupt enable |
| 0x0C | INT_STAT | RW1C | Interrupt status |
| 0x10 | LAYER_TYPE | RW | Layer configuration |
| 0x14 | IN_DIM | RW | Input dimensions |
| 0x18 | OUT_DIM | RW | Output dimensions |
| 0x1C | KERNEL_SIZE | RW | Kernel dimensions |
| 0x20 | STRIDE | RW | Stride value |
| 0x24 | ACT_FUNC | RW | Activation function |
| 0x28 | TILE_COUNT | RW | Number of tiles |
| 0x2C | RESULT | RO | Computation result |
| 0x30 | POWER_STATE | RW | Power management |
| 0x34 | VERSION | RO | Hardware version |

### 9.2 Control Register

| Bit | Name | Access | Description |
|-----|------|--------|-------------|
| [0] | START | WO | Start computation |
| [1] | STOP | WO | Abort computation |
| [2] | RESET | WO | Reset accelerator |
| [3] | ENABLE | RW | Global enable |
| [31:4] | Reserved | - | - |

### 9.3 Status Register

| Bit | Name | Access | Description |
|-----|------|--------|-------------|
| [0] | IDLE | RO | Accelerator idle |
| [1] | BUSY | RO | Computation in progress |
| [2] | DONE | RO | Computation complete |
| [3] | ERROR | RO | Error occurred |
| [7:4] | STATE | RO | Current FSM state |
| [31:8] | Reserved | - | - |

---

## 10. PERFORMANCE SPECIFICATIONS

### 10.1 Performance Summary

| Parameter | Value | Unit |
|-----------|-------|------|
| Peak Throughput | 2.0 | GOPS |
| Sustained Throughput | 1.5 | GOPS |
| Energy Efficiency | >5 | TOPS/W |
| Inference Energy (KWS) | <10 | μJ |
| Clock Frequency | 100 | MHz |
| Latency (KWS) | <5 | ms |

### 10.2 Resource Utilization

| Resource | Value | Unit |
|-----------|-------|------|
| Total Area | <2 | mm² |
| IMC SRAM | 0.8 | mm² |
| Digital Logic | 0.6 | mm² |
| ADC Periphery | 0.3 | mm² |
| IO/Interface | 0.3 | mm² |

### 10.3 Power Breakdown

| Component | Active | Idle | Sleep |
|-----------|--------|------|-------|
| IMC Arrays | 800 μW | 200 μW | 10 μW |
| Digital Logic | 600 μW | 100 μW | 5 μW |
| ADC | 400 μW | 50 μW | 1 μW |
| Activation Unit | 100 μW | 50 μW | 1 μW |
| Clock/PLL | 100 μW | 50 μW | 1 μW |
| **Total** | **2.0 mW** | **450 μW** | **18 μW** |

### 10.4 Technology Summary

| Parameter | Value | Notes |
|-----------|-------|-------|
| Process | TSMC 65nm LP | Low power variant |
| Voltage | 0.8-1.2V | Adaptive |
| Temperature | -40 to 125°C | Industrial |
| Package | TBD | BGA or QFN |
| IO | 3.3V compatible | Level shifters |

---

## APPENDIX A: TIMING DIAGRAMS

### A.1 Inference Timing

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         INFERENCE TIMING                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  clk    ─┐   ┌─┐   ┌─┐   ┌─┐   ┌─┐   ┌─┐   ┌─┐   ┌─┐   ┌─┐   ┌─┐  │
│          └───┘ └───┘ └───┘ └───┘ └───┘ └───┘ └───┘ └───┘ └───┘  │
│                                                                         │
│  start  ──┐                                                             │
│           └────────────────────────┐                                      │
│                                    │                                     │
│  config ──────────────────────────┼────────────────────────────       │
│  load     │                         │                                     │
│           └─────────────────────────┘                                     │
│                                                                         │
│  compute ─────────────────────────────────────────────────────────────  │
│  (layers)│                                                                   │
│          └────────────────────────────────────────────────────────────  │
│                                                                         │
│  done    ────────────────────────────────────────────────────────┐    │
│                                                              └────┘    │
│                                                                         │
│  interrupt ───────────────────────────────────────────────────────┐    │
│                                                              └────┘    │
│                                                                         │
│  Time:                                                              │    │
│  - Config: 10 cycles                                                │    │
│  - Conv1: 100 cycles                                                │    │
│  - Sep1-10: 800 cycles                                              │    │
│  - FC: 50 cycles                                                    │    │
│  - Total: ~1000 cycles = 10 ms @ 100 MHz                            │    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

*Document Version: 1.0*
*Architecture Specification - IMC TinyML Accelerator*
*Created: [Current Date]*
