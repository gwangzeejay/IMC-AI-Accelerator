# G7 fresh execution diagnostics

Status: PASS_SAME_HOST_DIAGNOSTICS. These are same-host checks, not full cross-validation or hardware calibration.

- Two fresh inputs: KWS 72,152 elements and VWW 232,068 elements; 304,220 total, zero mismatches against the pinned reference.
- Two fresh runtime executions of frozen case `g6_331000`: each 3 commits and 0.0027310116857093567 assumed J; both full result dictionaries exactly match the stored case.
- Modeled energy spread between repeats: 0.0 J. This only demonstrates same-code determinism for one case.
- Host execution times differ due to memoization/warmup and are not modeled target timings. No arbitrary <20% host-time variance or <5% energy-CV threshold is certified.
- No policy fit, no cost calibration, no new-holdout claim, and no G2-G6 result writes. Cross-host validation, full clean-host pipeline replay and physical timing validation remain NOT RUN.

Exact input IDs, timings and scope are recorded in `cv_report.json`. The previous cached-read PASS report is superseded and backed up.
