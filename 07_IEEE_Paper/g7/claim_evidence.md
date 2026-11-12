# Claim-to-evidence map

All paths below are relative to repository root. Exact input hashes are in `assets/sources.json`; experiment-file hashes remain in the G2-G6 run manifests. Claims are conditional on the stated model and observed cases.

| Paper statement | Artifact / JSON locator | Allowed scope |
|---|---|---|
| KWS 99/120 vs 98/120; 1.368%, CI [0.126%,3.504%] | `10_Experiments/g6/results.json`: workloads.kws.synthetic_stochastic.{methods,comparison_vs_adaptive,paired_bootstrap} | Assumed energy; held-out G6 synthetic traces, not physical improvement |
| KWS Layer 100/120; RECAP 10.56% more expensive | Same file: workloads.kws.synthetic_stochastic.{methods.B1_layer,comparison_vs_layer} | Energy/commit with counts retained |
| VWW 20/120; near-zero improvement and signed CI | Same file: workloads.vww.synthetic_stochastic | Do not clip negative CI bound or assert equivalence from a null effect |
| ETH KWS 24/36, VWW 4/36; undefined energy CIs | Same file: workloads.*.eth_measured_derived_rail; `eth_windows.json` | Six day blocks from one location, assumed rail conversion |
| Primary p95 infinity | Same file: workloads.*.synthetic_stochastic.methods.*.p95_is_infinite | Unfinished arrivals included; not finite-latency nonregression |
| 448/240/576/96 matrix rows | Same file: raw_rows; `10_Experiments/g6/raw/*.jsonl` | Matrices reuse common cases; distinct case count is 1216, not 1360 independent trials |
| Save state cost-dominated in 174 pairs | `10_Experiments/g6_analysis/analysis.json`: state_objective_dominance; `09_Simulation/g6_runtime.py`: choose/score_energy | Post-hoc implementation diagnosis; no expected-redo term, not a theorem about saving |
| 97.76% of steady KWS gap from scratch publication | Same analysis: steady_checkpoint_ledger.kws | Descriptive ledger attribution, six equal commits; direct-publication benefit not evaluated |
| Supply ceiling approximately 99.96% for VWW | Same analysis: source_budget | Assumed rail supply plus initial capacitor; never substitute harvested for consumed energy metric |
| Ten interventions and six stress axes | G6 results: ablations/sensitivity; protocol_snapshot.json | Preset subsets; not independent full holdouts or calibrated parameter intervals |
| Memory 64 KiB / 2 MiB; maxima 41216 /1158122 B | G6 protocol_snapshot.json, results.json, memory_feasibility.json | Logical buffers, not CPU compiler arena |
| 1882 RTL cases /6415721 byte ACKs /8317 timing checks | `10_Experiments/g4/summary.json`: total_* | Two microtiles/controller; finite checks only |
| 647 MAC and 5468 requantization RTL cases | Same file: arithmetic | Scalar arithmetic cores only |
| Header 124 B; writes L+125+o; cycles 2L+246+o | `04_RTL/g4/recap_checkpoint_ctrl.sv`; `03_Architecture/g4_rtl_spec.md`; G4 logs | Assumed atomic byte and persistence ACK; zero-stall commit only |
| G6 1794096 elements and481 committed outputs | `10_Experiments/g6/accuracy.json`; results.json completed_outputs_in_main | Hybrid reference head; finite inputs; no full-hardware implication |
| 8 full-network fault cases +1000 tile schedules | `10_Experiments/g6/faults.json` | Distinct test scopes; no formal proof |
| KWS reference 901/1000; VWW33/40 | `10_Experiments/g5/summary.json`: accuracy; G6 accuracy.json | Pretrained reference, small research VWW subset; not newly achieved model accuracy |
| G3 gain22.09% does not persist at network scope | `10_Experiments/g3/summary.json`: primary_comparison; G5/G6 summaries | Different scopes/protocols; not a matched longitudinal experiment |
| Chime/Viadotto/CIM-Tuner/FreeML/CHRYSALIS context | `02_Research/G1_source_audit.md`, corrected coverage_log.md, references.json | Positive sourced facts; no categorical absence/first claim |

G7-specific checks: `evidence_audit.json` independently recomputes all 32 main aggregate cells from 448 raw rows and checks every G2-G6 manifest entry. `10_Experiments/g7/cv_report.json` records fresh same-host checks separately; it does not establish clean-host or physical reproducibility.
