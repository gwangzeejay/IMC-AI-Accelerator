# Technical supplement to the G7 working draft

Status: supporting material for internal review, not a substitute for resolving the research gaps. All energy/time values refer to assumed models. No policies were fitted and no G6 held-out artifacts were overwritten during G7.

## Protocol and identity

G6 freeze ID: `3e55d8df18ac1044961f1fd693d82dd8e2afc2cbbc30e4965eb61659ec932df6`.
The source/input freeze is in `10_Experiments/g6/frozen_protocol.json`. It fixes source digests, model digests, reserve=0.30 and no G6 tuning. Repeated cache use does not imply additional independent executions.

| Workload | Model SHA-256 | Input contract |
|---|---|---|
| KWS | aeea436800704fce17b17292e4412630ad856e9d777c044c64ef748a880bd0ae | INT8 [1,49,10,1] precomputed MFCC |
| VWW | 597a384c8c2c8a1276f04702f25013b7838f2f814f1ca7c174d295b73e3d6b7b | INT8 [1,96,96,3], research-preprocessed COCO subset |

Acquisition/preprocessing/external queue are excluded. The same fully evaluated output contract is used for B1-B3/RECAP. A literature method using retraining, pruning or early exits needs either a separate accuracy/latency trade-off or an explicitly justified exact-output adaptation.

## Recovery and arithmetic boundary

The G4 binary codec has a 124-byte header, full 256-bit model/input/descriptor identities and CRC32. Copy-on-write order is inactive-slot invalidation, payload, header, publish marker, then output frontier. The fault model assumes old-or-new byte writes, persistence on ACK, no delayed writes after reset, and no reordering. CRC32 detects modeled corruption; it is not an adversarial authentication scheme or a mathematical guarantee against every possible collision.

G4 reports 1,882 controller cases, including expected fail-closed diagnostics. These are not 1,882 whole-network runs. The G3 JSON codec and G4 binary codec are not byte-equivalent; RTL validation did not revalidate G3 energy gains. G4 full-controller generic Yosys processing timed out at 180 s; reduced-controller and scalar processing/checks passed. There is no technology-mapped area, power, timing, or formal proof.

G6 adds graph logs/root publication in software. Arithmetic uses reference-compatible integer convolution, with an isolated reference CPU head. The pinned TF2.21 reference FC rounding contract differs from an all-integer requantization in a known regression input; therefore whole-network correctness must retain the documented reference-head semantics.

## Cost, adaptation, and causality

The runtime ranks feasible actions by nominal energy/output for RECAP and nominal time/output for B3. The same candidate set exposes geometry, input-channel chunk, saved DW output and saved partial sums. The current objective omits expected future redo benefit. Post-hoc state dominance is therefore structural to this objective and cost set, not empirical evidence that a complete recovery optimizer prefers replay globally.

Admission checks the energy of a bounded unit against current reservoir energy. No admitted-work depletions occurred under this model. Failures can still occur during retention waiting. Introducing an arbitrary per-unit failure probability would conflict with this admission guarantee; a future redo model must identify the remaining causal risk, such as retention loss, model error, or unmodeled overhead, and justify its distribution. Expected costs belong in the planner, while actual event consumption is counted once in the ledger.

The primary graph is always fused. Continuous-fusion and unfused interventions are fixed alternatives; they do not demonstrate a per-pair fusion optimizer. all_live copies redundant live state but retains the minimal-state objective; its losses do not prove that optimized full-state mapping is infeasible. The digital profile only multiplies PW compute energy by10 and time by4; it does not calibrate a non-CIM competitor.

## Source traces and statistics

Synthetic power is2mW when on, with different zero-power fractions in mild/severe families; mean power is therefore different. Independent stochastic units are40 trace seeds, not120 individual arrivals. Pairing and stratification keep arrivals in each trace together.

ETH source is `pos16_power_relative.h5` (SHA-256 e781fdff077a340495a88c7351f423bea21ebf7d12359cd996377d1591d44b89), from Zenodo3715472. The official sign convention gives input power as -I_in*V_in. Six equally spaced valid index windows were selected without performance screening. Both capacitors for each measured day stay in one bootstrap block. Sample noise may be clipped at zero for the rail model, with native windows and conversion assumptions retained. One location/six days do not establish environmental generality.

All method-consumed energy, including unfinished work, appears in the numerator of energy/commit. Bootstrap samples with no commits remain undefined. Measured unconditional energy intervals are null; reporting a conditional interval after excluding these samples would answer a different question. All primary stochastic and measured method p95 values are infinite; the separate steady KWS control has finite p95 and should not be conflated with those groups.

## Supplementary tables and figures

Generated from exact schemas by `build_assets.py`:

- Table1: `assets/table1_main.md` / CSV — all16 workload/domain/method cells.
- Table2: `assets/table2_ablations.md` / CSV — all20 intervention rows with completion denominators.
- Table3: `assets/table3_sensitivity.md` / CSV — all36 stress cells with both method completion counts.
- Table4: `assets/table4_validation.md` / CSV — validation levels and exclusions.
- Table5: `assets/table5_related_work.md` / CSV — qualitative positive facts, locators and open comparisons.

Figure1 shows the implementation boundary. Figure2 shows all main completion counts. Figure3 compares stage-scoped intervals without implying controlled cross-stage comparison. Figure4 shows ablation completions rather than ranking unequal-completion energy ratios. Figure5 shows stress-cell reduction percentages with RECAP/Adaptive commit counts out of24 arrivals each. Axis values are multipliers for energy/bandwidth, microwatts for active leakage/retention, and percent for admission margin (table3 also records exact numeric values). Figure6 decomposes steady KWS total energy for equal six-commit workloads. Scratch, layer log and weight-load components are disjoint in this diagnostic; other is the remainder.

Figures are vector PDF/SVG, 300-dpi PNG and grayscale PNG, at3.5-inch or7.16-inch source widths. The letter includes Figures1/3 and Table1; the supplement supplies the other assets. Paper figure numbers follow placement, so the file named fig3_intervals appears as Figure2 in the letter.

## Reproducibility limits

G7 hash/aggregate audit and fresh same-host diagnostics are separate from complete G2-G6 replay. Full clean-host replay, independent-host numerical checking, target timing calibration, and human independent code review remain open. The earlier G7 CV/replay reports were insufficient; their backups are historical evidence, not valid certificates. The current helpers fail on actual hash/data mismatches instead of filling missing fields with zero.

The source/review ZIP is a manuscript package with frozen summary/raw evidence needed to rebuild figures. It is not a self-contained full inference artifact: models, all datasets, tool binaries and the large ETH archive are not redistributed. The full workspace reproduction guide remains authoritative for those prerequisites. No public artifact DOI has been minted.
