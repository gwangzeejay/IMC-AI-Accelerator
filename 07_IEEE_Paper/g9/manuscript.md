# When Does State-Saving Pay on Intermittent SRAM-CIM? A Pre-Registered Negative Result Under Assumed Costs

*Draft, 2026-11-11. Model energy only; `calibrated=false`. No hardware measurement, no novelty claim.*

## Abstract

Intermittently powered, volatile SRAM compute-in-memory (CIM) accelerators can survive power loss by saving intermediate state (depthwise outputs, partial sums) to non-volatile memory (NVM), or by recomputing. We ask in which region of NVM cost, outage rate and capacitor size state-saving beats strong controls, and where it does not. We pre-registered (an in-repository lock with file hashes, not an external registry) a 48-cell crossover grid (2 workloads, 4 NVM energy scales, 3 reset rates, 2 capacitor sizes, 6 paired replicates) with a locked protocol hash, a decision rule (at least 2% lower model energy per completed inference than all five strong controls, paired-bootstrap 95% lower bound above 0, non-inferior completion, at least 10% state-saving use), and an NVM scale range grounded in datasheets before any main result. The outcome is `NO_REGION`: no cell wins, no cell loses, and 48 of 48 are tie or inconclusive, both within the grounded range and over the whole grid. The recovery-aware policy never selected state-saving in any cell (0% of tile decisions), so it reproduced the time-oriented adaptive baseline; controls that do save state (fixed-interval saving, an iNAS-style search) used more energy, and a dynamic-programming control was within 1% of it. A post-hoc, read-only diagnosis shows that on VWW the ranking does select state-saving once the planning hazard reaches 100 Hz, but that on KWS it never does at any hazard because the expected-redo model charges no loss risk to single-chunk plans; a hand calculation with that gap corrected puts the break-even for a representative KWS tile at about 2 kHz (recovery cost omitted), against a grid maximum of 16 Hz. The result concerns an assumed-cost model, not silicon.

## 1. Introduction

Fusing depthwise (DW) and pointwise (PW) convolution avoids intermediate traffic during uninterrupted execution, but on volatile SRAM-CIM a power loss destroys resident weights and intermediate results. A runtime can (i) restart the tile, (ii) save DW output (`SAVE_DW`) or partial sums (`KEEP_PS`) to NVM, or (iii) shrink the tile so the unit of work fits the energy buffer. Which choice is cheapest depends on NVM write cost, outage rate and buffer size, so a single "best method" claim is fragile.

Earlier internal phases (G2–G8) built a byte-level recovery model and a recovery-aware policy (RECAP). In the final G8 evidence the policy matched a time-oriented adaptive baseline and selected `SAVE_DW=0`, `KEEP_PS=0`. Prior work on progress preservation and tile-boundary checkpointing (Section 2) also limits any claim that these mechanisms are new. We therefore reframed the study from "a new method" to a pre-registered question about the crossover, with the stopping rule fixed in advance: if no region of the grounded range shows a win over all strong controls, publish the negative result without adjusting costs, seeds or inputs.

Contributions, all under assumed costs:

1. A locked crossover protocol (hash of 166 files, decision rule, grounded cost range declared before results).
2. Literature-adapted controls on a shared backend, including an iNAS-style and a dynamic-programming checkpoint-placement control.
3. A negative result with every cell reported, plus a labelled post-hoc diagnosis of why the policy never saves state.

## 2. Related Work and Limits of This Study

Energy-adaptive checkpoint-free inference keeps loop-index progress and guards write-after-read hazards with atomic critical sections on FRAM microcontrollers [Islam et al., arXiv:2503.06663]. CHRYSALIS models checkpoints at tile boundaries with a checkpoint-count term and a fixed re-execution factor [Hou et al., ISCA 2024]. iNAS jointly designs execution and preservation (tile, loop order, batch preservation) [Mendis et al., ACM TECS 2021]; INTERCEPT places state-persistence operations on STT-MRAM [Barjami et al., SenSys 2024]. FreeML re-executes layers with separate working buffers [arXiv:2405.10426]. DIAC synthesises netlist-level backup structures for battery-free nodes and is not a DNN or CIM design. ReRAM and spintronic CIM designs (ResiRCA, MOUSE) use non-volatile compute substrates, so they sit outside the volatile-SRAM setting studied here; we know these two only from abstracts.

Evidence levels, stated plainly: the 2503.06663 paper was read in full; CHRYSALIS selectively; FreeML and DIAC from downloaded source text with keyword checks; iNAS only through its public code and a secondary description; INTERCEPT through its abstract only (the PDF was blocked and we did not circumvent this). The literature coverage is therefore partial (the internal coverage gate G1 remained `PARTIAL_NOT_PASSED`), and nothing here asserts that a technique is absent from the field.

## 3. Study Design

**Backend.** A bit-exact INT8 runtime for a keyword-spotting DS-CNN (KWS) and a visual-wake-words network (VWW), with an energy-reservoir simulator and externally scheduled resets that discard stored charge. All unit costs, including NVM read (1 nJ/B) and write (2 nJ/B) at scale 1, are assumptions.

**Grid.** NVM energy scale {0.25, 1, 4, 16} (relative to the assumed costs), reset rate {1, 4, 16} Hz, capacitor {25, 100} µJ, 6 paired replicates per cell, 24 s horizon, 3 arrivals. 2 workloads × 8 policies × 48/2 cells × 6 replicates gives 2,304 main rows (plus 896 secondary rows).

**Grounded range.** Chip-only datasheet energy per byte (3.3 V × current × 200 ns) was compared to the assumed costs for FM25V20A and MB85RS2MTA FRAM and MR25H10 MRAM, giving a scale range of [0.627, 8.91]; cells at 1× and 4× form the primary verdict. This is a lower bound on system cost (SPI I/O, level shifters and controller are excluded), a single scale cannot match both read and write ratios for all devices, and NOR flash was excluded. The range was declared and the protocol re-locked before any main result.

**Controls.** B3 (time-oriented adaptive tile policy), B4 with partial-sum saving every 16 or 64 input channels (two fixed intervals, no tuning), B5a (iNAS-style candidate search with atomicity constraint, from public code; the latency objective is replaced by nominal energy), and B5b (dynamic-programming checkpoint placement with an exponential-hazard planning model). B1 (layer-granular) is reported but not a strong control. A loop-index control (B6) is identical to B4 at interval 16 in this backend and is not counted twice. These are adaptations, not reproductions of the original systems.

**Policy under test.** RECAP_redo ranks candidate plans by expected redo cost under a fixed planning hazard of 2 Hz that policies do not know to equal the actual rate. A matched-hazard variant is reported as a secondary analysis.

**Decision rule (summarised from the locked protocol; confidence intervals use 2,000 paired bootstrap replicates).** A cell is a win if RECAP_redo is non-inferior in completion and on-time rate (0.05 absolute tolerance), reduces model energy per completed inference by at least 2% against every strong control, and the paired-bootstrap 95% CI lower bound is above 0; and it selected state-saving for at least 10% of its tile decisions. A region is two neighbouring winning cells of one workload. Verdicts: `REGION_BOTH_WORKLOADS`, `REGION_ONE_WORKLOAD`, `NO_REGION`.

**Inputs.** 72 KWS inputs (6 per class, disjoint from earlier use) and 20 VWW images. The VWW images are the same 20 used in G8 (no further images exist), with new reset seeds; this reuse is disclosed. Development inputs were used only for smoke and fault checks; no parameter was tuned on any split.

**Run integrity.** The first launch of the main run (`20261111-m1`) terminated abruptly during VWW without a traceback and was discarded unanalysed; the reported run is `20261111-m2` under the same lock.

## 4. Results

**Verdict.** `NO_REGION` for the grounded range and for the full grid. Labels over 48 cells: win 0, win without state-saving 0, loss to some control 0, tie or inconclusive 48.

**State-saving use.** RECAP_redo selected a state-saving plan in none of its tile decisions in any cell, including at 0.25× NVM cost and in the matched-hazard variant. The same was true in the earlier G8 run. Table 1 shows what the controls did.

**Table 1.** Completed inferences and state-saving share of tile decisions, pooled over the grid (432 arrivals per workload per policy).

| Workload | Policy | Completed / arrivals | State-saving share |
|---|---|---|---|
| KWS | B1_layer | 304 / 432 | 0.0% |
| KWS | B3_adaptive | 356 / 432 | 0.0% |
| KWS | B4_ci16 | 321 / 432 | 63.8% |
| KWS | B4_ci64 | 348 / 432 | 0.0% |
| KWS | B5a_inas | 332 / 432 | 16.1% |
| KWS | B5b_chime_dp | 348 / 432 | 65.1% |
| KWS | RECAP_nominal / RECAP_redo | 356 / 432 | 0.0% |
| VWW | B1_layer | 155 / 432 | 0.0% |
| VWW | B3_adaptive | 239 / 432 | 0.0% |
| VWW | B4_ci16 | 216 / 432 | 45.1% |
| VWW | B4_ci64 | 239 / 432 | 31.2% |
| VWW | B5a_inas | 234 / 432 | 31.3% |
| VWW | B5b_chime_dp | 239 / 432 | 45.7% |
| VWW | RECAP_nominal / RECAP_redo | 239 / 432 | 0.0% |

Note: on KWS (input-channel depth 64) B4 at interval 64 is a single chunk, so it saves no state; B3 and B4_ci64 are therefore non-saving controls there.

**Against the strong controls.** Over the full grid, RECAP_redo is identical to B3 in energy in 21 of the 37 cells where the ratio is defined (|difference| below 1e-9 in 26; the remainder is numerical noise of about 1e-13). The statements below refer to the grounded range. Against B4 at interval 16 it is 51.5–65.6% lower in energy in KWS cells within the grounded range and 0.2–48.0% lower in VWW; against B5a it is 0 or 67.6–71.5% lower in KWS and 4.8% to −0.02% in VWW (a negative value means RECAP uses more). The tightest comparison is B5b, which is up to 0.97% cheaper than RECAP_redo (VWW, 4× NVM, 4 Hz, 100 µJ), below the 2% threshold. These large reductions against B4 and B5a do not create a win because B3 and B5b match RECAP; the rule requires a win over all five.

**Table 2.** Grounded-range cells (NVM 1x and 4x). Columns: relative energy reduction of RECAP_redo versus each control, %, paired by scenario; positive means RECAP uses less. The full 48-cell table with confidence intervals is `assets/g9_cells.csv`.

| Workload | NVM x | Reset Hz | Cap uJ | State-saving share | vs B3 | vs B4-16 | vs B4-64 | vs B5a | vs B5b | Label |
|---|---|---|---|---|---|---|---|---|---|---|
| KWS | 1 | 1 | 25 | 0% | +0.00 | +52.99 | +0.00 | +0.00 | +0.00 | tie_or_inconclusive |
| KWS | 1 | 1 | 100 | 0% | +0.00 | +53.41 | +0.00 | +0.00 | +0.00 | tie_or_inconclusive |
| KWS | 1 | 4 | 25 | 0% | +0.00 | +53.87 | +0.00 | +0.00 | +0.00 | tie_or_inconclusive |
| KWS | 1 | 4 | 100 | 0% | +0.00 | +53.56 | +0.00 | +0.00 | +0.00 | tie_or_inconclusive |
| KWS | 1 | 16 | 25 | 0% | +0.00 | +51.52 | +0.00 | +0.00 | +0.00 | tie_or_inconclusive |
| KWS | 1 | 16 | 100 | 0% | +0.00 | +53.40 | +0.00 | +0.00 | +0.00 | tie_or_inconclusive |
| KWS | 4 | 1 | 25 | 0% | +0.00 | +58.37 | +0.00 | +67.62 | +0.00 | tie_or_inconclusive |
| KWS | 4 | 1 | 100 | 0% | +0.00 | +57.53 | +0.00 | +0.00 | +0.00 | tie_or_inconclusive |
| KWS | 4 | 4 | 25 | 0% | +0.00 | +57.83 | +0.00 | +68.00 | +0.00 | tie_or_inconclusive |
| KWS | 4 | 4 | 100 | 0% | +0.00 | +57.29 | +0.00 | +0.00 | +0.00 | tie_or_inconclusive |
| KWS | 4 | 16 | 25 | 0% | +0.00 | +65.55 | +0.00 | +71.47 | +0.00 | tie_or_inconclusive |
| KWS | 4 | 16 | 100 | 0% | +0.00 | +63.25 | +0.00 | +0.00 | +0.00 | tie_or_inconclusive |
| VWW | 1 | 1 | 25 | 0% | -0.00 | +29.05 | +4.78 | +4.78 | -0.03 | tie_or_inconclusive |
| VWW | 1 | 1 | 100 | 0% | -0.00 | +29.25 | +4.78 | +4.78 | -0.07 | tie_or_inconclusive |
| VWW | 1 | 4 | 25 | 0% | +0.00 | +28.86 | +4.57 | +4.57 | -0.19 | tie_or_inconclusive |
| VWW | 1 | 4 | 100 | 0% | -0.00 | +28.65 | +4.45 | +4.45 | -0.16 | tie_or_inconclusive |
| VWW | 1 | 16 | 25 | 0% | +0.00 | +47.72 | +3.26 | +3.26 | -0.07 | tie_or_inconclusive |
| VWW | 1 | 16 | 100 | 0% | +0.00 | +47.95 | +2.92 | +2.92 | -0.40 | tie_or_inconclusive |
| VWW | 4 | 1 | 25 | 0% | -0.00 | +0.18 | +0.01 | +0.18 | +0.02 | tie_or_inconclusive |
| VWW | 4 | 1 | 100 | 0% | +0.00 | +0.23 | +0.02 | +0.02 | -0.46 | tie_or_inconclusive |
| VWW | 4 | 4 | 25 | 0% | +0.00 | undef. | -0.06 | undef. | -0.04 | tie_or_inconclusive |
| VWW | 4 | 4 | 100 | 0% | +0.00 | undef. | -0.02 | -0.02 | -0.97 | tie_or_inconclusive |
| VWW | 4 | 16 | 25 | 0% | undef. | undef. | undef. | undef. | undef. | tie_or_inconclusive |
| VWW | 4 | 16 | 100 | 0% | undef. | undef. | undef. | undef. | undef. | tie_or_inconclusive |

**Undefined cells.** In 11 of 48 cells all five paired estimates are undefined (NVM 16×, plus VWW at 4× and 16 Hz); in the two cells we inspected, no policy completed any arrival. Two of these lie inside the grounded range. We keep them rather than excluding them.

## 5. Post-Hoc Diagnosis (read-only; does not alter the verdict)

*The analyses below were run after seeing the results and are exploratory.*

1. **The ranking responds to hazard on VWW but not on KWS.** Raising the planning hazard of RECAP_redo from 2 Hz to 100–100,000 Hz, and ranking the first tile of each stage, makes it choose state-saving on VWW at NVM 0.25× and 1× (1 of 15 stages at 100 Hz; 7 of 15 at 1 kHz and above; at 16× only 1 of 8 stages, at 1 kHz with the 25 µJ capacitor). On KWS it chooses state-saving for none of 6 stages even at 100,000 Hz; item 3 explains why. At the hazards of the grid (at most 16 Hz) it never does on either workload.
2. **Economics.** For a representative KWS fused tile (8 pixels × 64 channels) the unchunked plan costs about 10.1 µJ over 1.36 ms; saving partial sums raises this to about 24.5 µJ (+143%) and saving DW output as well to about 29.3 µJ (+190%). At 16 Hz the probability of a reset inside the tile is about 2%. With a full-exposure restart model, partial-sum saving breaks even at roughly 2 kHz, about two orders of magnitude above the grid. This is a hand calculation from printed plan costs, not a rerun of the full model; it ignores recovery cost (boot, reload, DW recompute), so the figure is an order-of-magnitude estimate, not a measured threshold.
3. **A modelling gap in the G8 ranking.** The expected-redo model charges loss risk only at boundaries between chunks, so a single-chunk plan has zero modelled risk at any hazard and the model favours fewer boundaries. Correcting this moves the break-even from "never" to about 2 kHz for the tile above, so it does not change the conclusion on this grid, but it is a directional bias that should be disclosed.
4. **Why RECAP_redo equals B3.** For the tiles we examined, at 2 Hz the expected-cost differences between plans are about 0.1%, and the time-oriented and expected-redo objectives choose the same unchunked plan. We did not examine every tile.
5. **Endpoint.** Model energy per completed inference does not charge the stored energy discarded at a reset, so a reset costs only the torn tile. This disfavours state-saving relative to latency or completion endpoints, which we did not test.

Unexplained: B5b and B4 at interval 16 use state-saving for 46–77% of decisions yet B5b is within 1% of RECAP in energy. We did not inspect the tile shapes B5b chose.

## 6. Limitations

All costs and the 2 Hz planning hazard are assumptions; results are model energy, not measurements, and `calibrated=false`. The grounded range uses chip-only datasheet energy and one shared scale for reads and writes. Two workloads and a single resets-plus-constant-source family constitute a narrow test; stochastic-source results are secondary and unanalysed here. Controls are adaptations (B5a from public code only; iNAS and INTERCEPT papers were not read in full). VWW images are reused from G8. Literature coverage is partial. Pre-registration is an in-repository lock, not an external registry, and was made by the same author who ran the study. Because RECAP_redo never saves state, the verdict tests this policy's ranking rather than state-saving as such; as a descriptive check with a different estimator (pooled energy per completed inference, not the pre-registered paired one), the largest advantage of any state-saving control over B3 in any cell is 0.97% (B5b, VWW, 4× NVM, 4 Hz, 100 µJ), which points the same way. The result does not show that state-saving is useless on real hardware, only that under this cost model and grid it never pays.

## 7. Conclusion and Next Study

Within a grounded NVM cost range and reset rates up to 16 Hz, state-saving did not beat strong controls on assumed-cost SRAM-CIM; the recovery-aware policy converged to the plain adaptive policy. Under the assumed costs, writing partial state costs far more than the redo it avoids at these reset rates; on KWS the ranking model's missing loss risk for single-chunk plans reinforces this. A region where state-saving can win is expected only where tiles are long relative to 1/λ (reset rates of hundreds of hertz or more), where NVM writes are about two orders of magnitude cheaper than assumed, or where tiles are forced into small chunks. Any test of those regions is a new protocol (G9.1) with a new lock; the present result is not to be adjusted toward it.

## Reproducibility

Run `10_Experiments/g9/20261111-m2/` (protocol G9_1.0 rev 2, lock `10_Experiments/g9/protocol_lock.json`); tables via `07_IEEE_Paper/g9/build_tables.py`; diagnosis scripts in `10_Experiments/g9/diagnostics_20261111/`.
