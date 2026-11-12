# IMC-TinyML ASIC Implementation Guide

## Overview

This document describes the complete ASIC implementation flow for the IMC-TinyML accelerator, from RTL to GDSII. The flow uses industry-standard EDA tools from Synopsys and Cadence.

---

## Table of Contents

1. [Tool Requirements](#tool-requirements)
2. [Design Specifications](#design-specifications)
3. [RTL Verification](#rtl-verification)
4. [Synthesis (Design Compiler)](#synthesis-design-compiler)
5. [Power Analysis (PrimeTime)](#power-analysis-primetime)
6. [Place and Route (Innovus)](#place-and-route-innovus)
7. [Timing Closure](#timing-closure)
8. [Sign-off Checks](#sign-off-checks)
9. [GDSII Export](#gdsii-export)
10. [Tape-out Checklist](#tape-out-checklist)

---

## Tool Requirements

### Required Tools

| Tool | Vendor | Version | Purpose |
|------|--------|---------|---------|
| Design Compiler | Synopsys | >=Q-2020.09 | RTL to gate synthesis |
| PrimeTime | Synopsys | >=Q-2020.09 | Static timing analysis |
| PrimeTime PX | Synopsys | >=Q-2020.09 | Power analysis |
| Innovus | Cadence | >=20.1 | Place and route |
| Calibre | Siemens | >=2020.4 | DRC/LVS verification |
| OpenROAD | Acceleware | >=2.0 | Open-source alternative |

### Optional Tools

| Tool | Vendor | Purpose |
|------|--------|---------|
| Formality | Synopsys | Formal verification |
| IC Validator | Synopsys | Physical verification |
| Voltus | Cadence | Power integrity |

### Environment Setup

```bash
# Synopsys tools
export SYNOPSYS=/tools/synopsys
export PATH=$SYNOPSYS/bin:$PATH
export LM_LICENSE_FILE=27020@license-server

# Cadence tools
export CADENCE=/tools/cadence
export PATH=$CADENCE/tools/bin:$PATH
export PATH=$CADENCE/Innovus/bin:$PATH

# Mentor tools
export MGC_HOME=/tools/mentor
export PATH=$MGC_HOME/calibre/aoi/bin:$PATH
```

---

## Design Specifications

### Target Technology

| Parameter | Value |
|-----------|-------|
| Foundry | TSMC |
| Process Node | 65nm LP (Low Power) |
| Library | tcbn65lpwc |
| Voltage | 1.2V (typ), 1.08V-1.32V (range) |
| Temperature | -40°C to 125°C |

### Cell Library Requirements

- Standard cells: NAND, NOR, INV, DFF, etc.
- Clock cells: CLKBUF, CKINV
- Memory: SRAM compiler
- Analog: Sense amplifiers, charge pumps

### Clock Specification

| Parameter | Value |
|-----------|-------|
| Frequency | 100 MHz |
| Period | 10.0 ns |
| Jitter | < 100 ps |
| Duty Cycle | 45% - 55% |

### Power Specification

| Mode | Voltage | Frequency | Power Target |
|------|---------|-----------|--------------|
| Active | 1.2V | 100 MHz | < 2 mW |
| Idle | 1.2V | 0 MHz | < 100 μW |
| Sleep | 0.6V | 0 MHz | < 10 μW |

### Area Target

| Component | Area |
|-----------|------|
| Core | < 2 mm² |
| I/O | < 0.5 mm² |
| Total Die | < 4 mm² |

---

## RTL Verification

Before synthesis, verify the RTL thoroughly.

### Simulation Steps

```bash
# 1. Run unit tests
cd 09_Simulation
python3 test_vectors.py --output ./test_vectors
python3 python_simulator.py --generate --output ./output

# 2. Run RTL simulation
make verilator
make sim

# 3. Compare results
python3 compare_results.py --rtl-dir ./output/rtl --python-dir ./output/python
```

### Coverage Requirements

| Metric | Target |
|--------|--------|
| Line Coverage | > 95% |
| Branch Coverage | > 90% |
| FSM Coverage | 100% |
| Toggle Coverage | > 80% |

### Formal Verification (Optional)

```bash
# Run formality
formality -f formality.tcl
```

---

## Synthesis (Design Compiler)

### Flow Overview

```
RTL → Read → Compile → Optimize → Output
```

### Running Synthesis

```bash
# Create output directories
mkdir -p 08_ASIC/synopsys/synth/reports
mkdir -p 08_ASIC/synopsys/synth/results

# Run synthesis
dc_shell -f 08_ASIC/synopsys/dc_synth.tcl
```

### Synthesis Script (dc_synth.tcl)

The synthesis script performs:

1. **Library Loading**
   - Target library: tcbn65lpwc
   - Link library: * (all available)

2. **Design Reading**
   - Verilog RTL files
   - Include files

3. **Constraint Setting**
   - Clock: 100 MHz (10 ns period)
   - Input delays: 1 ns
   - Output delays: 1 ns
   - Clock uncertainty: 200 ps

4. **Compilation**
   - `compile_ultra` for high effort
   - Gate clock insertion
   - Retiming (if beneficial)

5. **Output Generation**
   - Synthesized netlist (.v)
   - SDF for timing (.sdf)
   - SDC constraints (.sdc)
   - Design database (.db)

### Key Synthesis Options

```tcl
# Clock gating
set compile_ultra_options "-gate_clock"

# Ungrouping for better optimization
ungroup -all -flatten

# Clock gate insertion
insert_clock_gating -exclusive
```

### Expected Results

| Metric | Target | Minimum |
|--------|--------|---------|
| Gate Count | < 80K | < 100K |
| Negative Slack | 0 ns | > -0.05 ns |
| Max Fanout | < 32 | < 64 |
| Area | < 1.8 mm² | < 2.2 mm² |

---

## Power Analysis (PrimeTime)

### Flow Overview

```
Netlist + SAIF → Power Analysis → Report
```

### Running Power Analysis

```bash
# Run with SAIF from simulation
pt_shell -f 08_ASIC/synopsys/pt_pwr.tcl
```

### Power Modes

| Mode | Activity | Power Target |
|------|----------|--------------|
| Active | 100% | < 2 mW |
| Idle | 10% | < 100 μW |
| Sleep | 1% | < 10 μW |

### Power Components

```tcl
# Breakdown by type
report_power -hierarchy -format verilog

# Breakdown by module
report_power -module
```

### Energy Per Inference

```
Energy = Power_active × t_active + Power_idle × t_idle + Power_sleep × t_sleep

Example:
  Active: 2 mW × 5 ms = 10 μJ
  Idle:   100 μW × 95 ms = 9.5 μJ
  Sleep:  10 μW × 900 ms = 9 μJ
  Total:  28.5 μJ per inference
```

### Power Optimization Techniques

1. **Clock Gating**: Insert CG cells on unused clock trees
2. **Multi-Vt**: Use HVT for low-leakage, SVT for speed
3. **Input Vector Control**: Reduce leakage in sleep mode
4. **Power Gating**: Shut off unused blocks

---

## Place and Route (Innovus)

### Flow Overview

```
Netlist → Floorplan → Power → Place → CTS → Route → Final
```

### Running PNR

```bash
# Create directories
mkdir -p 08_ASIC/cadence/innovus/reports

# Run place and route
innovus -64bit -f 08_ASIC/cadence/innovus_flow.tcl
```

### Floorplan

#### Die Dimensions

```
Pad Ring:     50 μm × 4 sides
Core Margin:  10 μm
Die Size:     2100 μm × 2100 μm (4.41 mm²)
Core Size:    1400 μm × 1400 μm (1.96 mm²)
```

#### Pin Assignment

| Signal | Side | Location |
|--------|------|----------|
| clk | Top | Center |
| rst_n | Top | Right |
| paddr | Left | Top to Bottom |
| pwdata/prdata | Right | Top to Bottom |
| s_axis_* | Bottom | Left |
| m_axis_* | Bottom | Right |

### Power Planning

```tcl
# Power rings
add_ring -type core_ring -follow true -layer {metal5 metal6} -width 2.0

# Power stripes
addStripe -layer metal4 -width 2.0 -spacing 20.0
addStripe -layer metal5 -width 2.0 -spacing 20.0
```

### Standard Cell Placement

```tcl
# Trial placement
trialplace

# Auto placement
place_design -effort high
```

### Clock Tree Synthesis

```tcl
# Create clock tree specification
create_ccopt_spec

# Build clock tree
build_clock_tree

# Verify CTS
report_ccopt
```

### Routing

```tcl
# Global route
globalRoute -space 2.0

# Detail route
routeDesign -globalDetail -viaOpt
```

### Timing Closure

```tcl
# Pre-CTS optimization
optDesign -preCTS

# Post-CTS optimization
optDesign -postCTS

# Post-route optimization
optDesign -postRoute
```

### Expected PNR Results

| Metric | Target | Achieved |
|--------|--------|----------|
| Core Utilization | 60-70% | __ |
| Wirelength | < 5000 μm | __ |
| Total Negative Slack | 0 ns | __ |
| DRC Violations | 0 | __ |
| Routing Overflow | 0% | __ |

---

## Timing Closure

### Timing Paths

| Path Type | Delay Target | Critical |
|-----------|--------------|----------|
| FF to FF (reg) | < 8 ns | Medium |
| Input to FF | < 6 ns | Low |
| FF to Output | < 6 ns | Low |
| Critical Path | < 10 ns | High |

### Optimization Strategies

1. **Buffer Insertion**: For high fanout nets
2. **Gate Sizing**: Upsize critical cells
3. **Register Duplication**: For high fanout
4. **Logic Restructuring**: Reduce logic depth
5. **Physical Optimization**: Improve placement

### Timing Report Analysis

```tcl
# Critical paths
report_timing -max_paths 20

# Path groups
report_timing -group clk

# Slack analysis
report_timing_summary
```

---

## Sign-off Checks

### Timing Sign-off

| Check | Condition | Tool |
|-------|-----------|------|
| Setup | slack > 0 | PrimeTime |
| Hold | slack > 0 | PrimeTime |
| Noise | derate < 10% | PrimeTime |
| OCV | included | PrimeTime |

### Power Sign-off

| Check | Target | Tool |
|-------|--------|------|
| IR Drop | < 5% | Voltus |
| EM | < 50% margin | Voltus |
| Power Grid | clean | Innovus |

### Physical Verification

| Check | Tool | Requirement |
|-------|------|-------------|
| DRC | Calibre | 0 violations |
| LVS | Calibre | 0 errors |
| Antenna | Calibre | 0 violations |

### Running Calibre DRC/LVS

```bash
# DRC
calibre -drc 08_ASIC/cadence/innovus/${design}_drc.rul

# LVS
calibre -lvs 08_ASIC/cadence/innovus/${design}_lvs.rul
```

---

## GDSII Export

### Export from Innovus

```tcl
# Stream out GDSII
setStreamOut \
    -library TSMC65nm \
    -output ./innovus/${design}.gds

# Include all layers
setStreamOut \
    -mapFile tsmc65nm.map \
    -output ./innovus/${design}.gds
```

### GDS Layer Map

| Layer | Purpose |
|-------|---------|
| 1-10 | Polysilicon |
| 11-20 | Metal 1-2 |
| 21-30 | Metal 3-5 |
| 31-40 | Via layers |
| 41-50 | Contact layers |

### Final Output Files

| File | Description |
|------|-------------|
| `{design}.gds` | GDSII for mask making |
| `{design}.v` | Netlist for verification |
| `{design}.sdf` | SDF for timing simulation |
| `{design}.libs` | Liberty files for power/timing |

---

## Tape-out Checklist

### Pre-Tapeout

- [ ] Timing: All paths meet setup and hold
- [ ] Power: IR drop < 5%, EM < 50%
- [ ] DRC: 0 violations
- [ ] LVS: 0 errors
- [ ] ERC: 0 violations
- [ ] Antenna: 0 violations
- [ ] Test Patterns: > 95% coverage
- [ ] Fuses: All set correctly
- [ ] Memory BIST: All pass
- [ ] DFT: ATPG complete

### Documentation

- [ ] Chip summary
- [ ] Pinout
- [ ] Timing specifications
- [ ] Power specifications
- [ ] Test procedures
- [ ] Reliability data

### Files to Deliver

```
tapeout/
├── gds/
│   └── {design}.gds
├── netlist/
│   ├── {design}_final.v
│   └── {design}_sdf.v
├── reports/
│   ├── timing_signoff.rpt
│   ├── power_analysis.rpt
│   ├── drc.rpt
│   └── lvs.rpt
├── lib/
│   ├── {design}_fast.lib
│   ├── {design}_slow.lib
│   └── {design}_typ.lib
└── doc/
    ├── chip_summary.pdf
    ├── timing_spec.pdf
    └── test_plan.pdf
```

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Setup violation | Long combinational path | Insert pipeline, optimize logic |
| Hold violation | Short path, clock skew | Add delay buffers, fix CTS |
| DRC violation | Routing congestion | Increase spacing, spread cells |
| IR drop | Insufficient power grid | Add straps, widen metals |
| Antenna violation | Large nets | Add antenna diodes |

### Debug Commands

```tcl
# Innovus
report_timing -debug
report_fanout
report_congestion
report_qor

# PrimeTime
report_timing -delay_type max
report_noise
report_power
```

---

## References

1. TSMC 65nm Library Documentation
2. Synopsys Design Compiler User Guide
3. Cadence Innovus User Guide
4. Synopsys PrimeTime User Guide
5. Calibre DRC/LVS User Manual

---

*Document Version: 1.0*
*Last Updated: 2026*
