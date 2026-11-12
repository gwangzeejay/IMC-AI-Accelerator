# G6 evaluation specification

G6 extends G5 to the pinned MLPerf Tiny KWS DS-CNN and VWW MobileNet models.
It preserves G2–G5 source/artifact hashes. New code lives in `g6_*.py`; this
is a new software event-model implementation, not a full-network RTL proof.

## Model, arithmetic and memory boundary

Both graphs execute their first convolution and each DW/PW operation from
actual computed input tensors with the established INT8/INT32 two-rounding
arithmetic. The isolated CPU head contains pool, reshape, FC and softmax from
the pinned reference model and accepts only the computed final convolution
tensor. Whole-model golden invocation happens after a committed completion
or in explicitly separate correctness tests. Host memoization never removes
modeled compute, load, time, energy or replay.

The adapter supports per-stage spatial shapes, asymmetric SAME padding,
stride 1/2, variable CI/CO and per-channel scales. VWW has 13 DW/PW pairs,
including CI256, compared with four CI64 pairs for KWS. Fused and unfused
graphs use the same arithmetic; unfused DW outputs become durable graph
anchors. No network training, pruning or width-multiplier change is performed.

VWW's 333,288-byte model alone exceeds the original 256 KiB NVM, and its
36,864-byte anchor exceeds 16 KiB SRAM. The original configuration is reported
as infeasible. G6 therefore uses a **common assumed 64 KiB SRAM / 2 MiB NVM
configuration for both workloads and every method**. This is an extended
capacity study, not evidence that VWW fits the original platform.

Two layer logs alternate, retaining the committed source until a newer graph
root is durable. Log reservation is computed from the largest stage and the
smallest allowed output geometry; scratch/root slots use the G4 binary-v1
header, identity/CRC and publish ordering. IDs include invocation and graph
layout; identical input arrivals cannot reuse an earlier completion. Logical
buffer highwater includes the resident anchor, streamed 2 KiB weight bank,
DW/INT32 PS/output tile and control/header allowance. Compiled CPU stack,
TFLite arena, target descriptor-engine memory and physical macro layout remain
unverified. The external input arrival queue and capture/preprocessing are
outside this inference-only boundary.

## Source model and preregistration

The same source/capacitor/input schedule is used for every method. Workload
load controls capacitor evolution, so failure times need not match. The
piecewise-constant source is integrated analytically. Retention waits end at
an energy threshold or source boundary; the policy sees present energy only.
Source-boundary knowledge belongs to the environment integrator and is not
an oracle for mapping. Cold charging and inactive periods assume zero load;
retention assumes its configured power. Each compute/commit unit requires
its full current-energy bound plus admission margin, without future harvest.
Depletion within an admitted unit is an assertion failure, distinct from
retention brownout or diagnostic external power loss.

Synthetic evaluation has 10 independent seeds for each mild/severe × capacitor
family, plus deterministic steady and zero-source cases. Seeds are independent
of G5. Reserve fraction 0.30 is transferred from G5 train/validation to both
RECAP and adaptive baseline, including VWW; no G6 policy tuning is performed.
Data pools, source windows, code, cost protocol and model hashes are frozen
before main execution. Diagnostic arithmetic/variant/fault preflights use
separate constant sources and reserved inputs. Viewed G6 tests cannot serve
as untouched holdout for a later algorithm change.

### Measured source

The public [ETH indoor solar dataset, record 3715472](https://zenodo.org/records/3715472)
provides timestamped power measurements from a solar panel and bq25505
harvester. Attribution: Lukas Sigrist, Andres Gomez and Lothar Thiele,
*Dataset: Tracing Indoor Solar Harvesting*, DATA 2019; CC BY 4.0.

Only `processed/pos16_power_relative.h5` is extracted by HTTP Range from the
32 GB archive. The entire 179,789,688-byte member is checked against its
published SHA-256, not merely a downloaded excerpt. Six equally spaced index
starts are selected without looking at workload performance; invalid/gapped
blocks are skipped using a fixed validity rule. Native approximately 1.00352 s
timestamps and 120 s horizon are preserved; there is no time compression or
amplitude normalization.

The authors' processing notebook defines panel power as `P_in = -I_in*V_in`.
The simulated rail receives `max(0, P_in) * 0.70`; sign, negative-sample count,
raw measurements and transfer assumption are recorded per window. The 70%
efficiency is **assumed**. This is measured-source-derived rail input, not
measured target-rail power. The original fixed-MPPT/virtual-battery operating
point does not validate harvester behavior against a varying target capacitor.
One location and six measurement days do not constitute multi-site validation.

### VWW images

Forty COCO 2014 images are selected as the first 20 IDs per class in the pinned
MLCommons VWW label file. JPEGs come from the COCO S3 bucket through valid HTTPS.
Research preprocessing is full-image RGB bilinear resize to 96×96 and signed
quantization `uint8-128`; it is not presented as official MLPerf performance
inputs. Two images per class are reserved for diagnostic checks; the remaining
36 form the source-trace pool. Accuracy on 40 images is a small-subset result,
not full COCO/VWW accuracy or MLPerf compliance. KWS power-test inputs exclude
feature hashes used in G5 runtime/correctness examples. No labels tune mapping.

## Baselines and ablation coverage

All methods share the new graph protocol, actual load ledger, source,
memory budgets and arithmetic. B1 commits at stage boundaries, restarting
the unfinished stage after loss. B2 uses fixed 1-pixel/CO16/CI16 geometry,
conservatively saving DW and available PS. This explicit state-saving B2
differs from G5's fixed output-only B2; G5 and G6 energy tables are not a
controlled before/after comparison. B3 adapts spatial/CO/CI/state over the
same candidate set as RECAP but ranks predicted time/output. RECAP ranks
predicted energy/output. These remain the tested cost heuristics; G6 does
not claim a new optimal or globally recovery-aware graph selector.

| Plan axis | Implemented intervention | Boundary |
|---|---|---|
| Ignore weight reload in decisions | Set only objective weight-read/bank-load terms to zero | Execution and admission still charge actual loads |
| SAVE vs REPLAY vs cost choice | `always_save_dw`, `always_replay_dw`, full | Save actually publishes DW, even before whole-chunk PW; PS decisions kept separate |
| Mapping/recovery separation | `fixed_mapping_recovery`, `adaptive_mapping_fixed_recovery`, full | Explicit fixed/adaptive decision axes |
| Fusion behavior | `continuous_fusion`, `unfused`, full | Fixed continuous mapping and global fuse/split comparison; not an optimized per-pair fusion graph search |
| Full vs minimal live checkpoint | `all_live` plus full | Redundant COW copy of live algorithm buffers/bank in extra reserved slots, in addition to minimal recovery records; no CPU register/stack snapshot claim |
| Source regimes | steady, mild, severe, zero, measured-derived source | Undefined completion denominators retained |
| Backend × policy | CIM/digital cost profiles × B3/RECAP | Assumed coefficient perturbation only; not calibrated backend validation |

Additional `no_weight_reuse` and `no_control` interventions check whether
bank residency and assumed controller/decision budgets change outcomes.
The bank contains actual loaded bytes, is limited to 2 KiB and is discarded
on cold boot. Larger weights stream and cannot receive a whole-weight
residency hit. Counterfactuals can change causal schedules; results are not
simple subtraction of a component's measured power.

`all_live` intentionally copies algorithm buffers that already have durable
ancestors, modeling conservative overcheckpointing. The auxiliary copy is
not required by minimal recovery and is not a reproduction of a prior system.
Its large admitted copy can exceed a small capacitor; such configurations are
reported infeasible/incomplete instead of silently shrinking the snapshot.
This intervention retains the minimal-state mapper objective and adds the
conservative copies to actual execution; it does not reoptimize mapping for
the larger snapshots. A blocked chosen snapshot is therefore **not proof**
that every possible full-state mapping is infeasible. This scope must remain
visible when interpreting the full-state ablation.
Literature baseline B4 remains unresolved at G1 and is explicitly missing;
these interventions must not be renamed exact Chime/Viadotto reproductions.

## Costs, metrics and uncertainty

Costs remain G2/G3/G5 **assumed architectural coefficients**, with explicit
weight-bank transfers and controller byte-wait overlap in G6. G4 commit
cycle equation is reused for aggregate protocol service; the complete G6
runtime is not cycle-accurate CPU/accelerator RTL. Controller/parser/head
budgets, hash execution, leakage and converter transfer lack physical
calibration. The digital profile changes PW energy/time by preregistered
factors; it does not measure a non-CIM chip. Bandwidth/compute/NVM scaling
ranges are stress ranges, not datasheet-derived confidence bounds.

One-factor-at-a-time sweeps cover NVM read/write energy, load bandwidth,
compute energy, active leakage, admission margin and retention power. They
use fixed first-two mild/severe seeds per capacitor for both workloads and
policies, without refitting. Source-trace uncertainty is distinct from unknown
cost-model uncertainty. Engineering sensitivity cannot establish calibration.

Every fixed horizon includes all arrivals and all consumed energy, including
partial, repeated and unfinished work. A committed output must match every
INT8 byte. Zero completion makes energy/commit undefined; failed/incomplete
latency is infinity in nearest-rank p95. Conditional classifier accuracy is
reported separately from correct committed arrivals. The 5 percentage-point
completion/on-time tolerances and 20% energy goal remain unchanged.

Paired bootstrap for stochastic sources resamples independent seeds within
source/capacitor families. Deterministic steady/zero cases have no artificial
replicate CI. Measured windows resample whole measurement-day blocks, keeping
both capacitances and all arrivals together. Undefined resamples suppress
the unconditional energy CI instead of being dropped. Per-trace losing
comparisons retain energy ledgers and failure counts for both policies.

Correctness evidence contains full-graph loss tests and a separate 1,000
random large-slot campaign using actual model-derived DW/PW anchors, including
CI256. The latter does **not** mean 1,000 full-network runs. These are finite
checks under atomic-byte/ordered-persistence assumptions; no formal proof,
physical NVM atomicity or full VWW RTL implementation is claimed.
