# G9 analysis plan (pre-registered, locked with the protocol)

Date: 2026-11-11. The machine-readable rule is `09_Simulation/configs/g9_protocol.json`
(`decision_rule`); `10_Experiments/analyze_g9.py` implements it and is hashed in the lock.
This file states intent in prose; if the two ever differ, the JSON and code govern and the
discrepancy must be reported.

## Question
In which part of the (NVM energy scale x outage rate x capacitor) grid does state-saving
(`SAVE_DW`/`KEEP_PS`) reduce model energy per completed inference versus every strong control
(B3_adaptive, B4_ci16, B4_ci64, B5a_inas, B5b_chime_dp), and where does it not?

## What counts
A cell wins only if RECAP_redo beats ALL five strong controls by >= 2% with a paired-bootstrap
95% lower bound above 0, is noninferior in completion/on-time, AND actually used state-saving in
>= 10% of its tile decisions. A region needs two neighbouring winning cells in one workload.
Losses and ties are reported in full. No cell, seed, control, threshold or bound is changed after
the lock; B1_layer is reported but never in the verdict.

## Verdicts
REGION_BOTH_WORKLOADS / REGION_ONE_WORKLOAD / NO_REGION, computed for the full grid and, as the
primary verdict, for the cells inside the grounded NVM scale range declared in stage 3.

## Not claimed whatever the result
Hardware savings, calibration, novelty of any mechanism, accuracy beyond the inherited models.
All costs and the planning hazard are assumptions.
