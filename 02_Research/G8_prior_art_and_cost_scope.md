# G8: comparison and remaining scientific gaps

Checked: 2026-10-23. This note narrows implementation claims; it does not close
the systematic literature review or certify originality.

## Source comparison

| Source | Checked locator | Supported mechanism | G8 relation / gap |
|---|---|---|---|
| Chime, Mirhoseini et al., 2016 | Local `source_materials/chime2016.pdf`, PDF pp. 5-6 / printed pp. 281-282, sections 5.2 and 6.1-6.3; PDF p. 9 / printed p. 285, sections 9.4-9.5 | Register liveness determines checkpoint cost; optimization places checkpoints under execution-distance constraints; periodic checkpointing is a comparison control | G8 B4 implements a restricted periodic PS-interval control, not Chime's DP or register-liveness analysis. Do not label it “Chime reproduced.” |
| [CIM-Tuner v1](https://arxiv.org/html/2601.18070v1) | Sections III-B through III-D, especially III-C; IV-A | Two-level spatial scheduling/tiling and compute/storage exploration with compiled instruction flows | G8 uses a small fixed architecture/tile space, not CIM-Tuner's hardware search or compiler. A common-backend optimized adaptation remains unimplemented. |

The Chime source explains checkpoint and recomputation overhead together.
Its periodic control is distinct from its optimized method. G8 therefore
improves comparison coverage but does not claim to beat the nearest published
optimized method. Neither checkpointing, expected-loss accounting nor DW/PW
fusion alone is asserted to be a new research contribution.

## What is improved

The new code removes duplicated output staging from all compared G8 policies,
separates nominal and expected-redo rankings, checks causality and compares
them under common absolute-time reset schedules. These are concrete engineering
changes; their performance is whatever the frozen G8 artifacts report.

## Cost evidence boundary

- G8 inherits G6 debug rail coefficients, including DW energy scaled by 30.
  They are assumptions. A 0.25x/4x NVM sweep does not turn them into calibration.
- The SRAM-CIM macro and complete NVM/processor implementation remain unselected.
- [Infineon FM25V20A-G](https://www.infineon.com/part/FM25V20A-G) is a 256-KiB
  example device, smaller than the common 2-MiB G8 NVM budget. One such chip
  cannot be described as the complete VWW backing store.
- Device current/timing specifications are not complete transaction or board
  energy. SPI command/address clocks, I/O, controller, converter, startup and
  rail conditions must be included or separately excluded with justification.
- Unknown physical quantities remain null in `10_Experiments/calibration_template.json`.
  The runtime continues to declare `calibrated=false`.

## Still required for a method-superiority paper

1. Identify the nearest optimized method at state/action/objective level;
   implement and validate a faithful or explicitly bounded common-backend adaptation.
2. Establish a source-supported cost domain or physical calibration. Keep
   arithmetic, technology, voltage, capacity and operation counts compatible.
3. Evaluate a newly locked policy against all strong controls using additional
   independent source seeds/datasets; retain losses, undefined ratios and
   infinite unconditional latency.
4. Show the mechanism generalizes beyond this codebase and obtain independent
   human review. Laptop simulation is a legitimate scope, but does not itself
   establish these scientific conditions.
