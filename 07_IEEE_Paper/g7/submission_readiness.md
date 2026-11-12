# G7 submission readiness

**2026-10-16 — NOT READY TO SUBMIT.** Draft/review/preparation completed within available evidence; scientific and author approvals remain open. No manuscript has been uploaded, emailed, or submitted.

| Gate | Status | Concrete evidence / next action |
|---|---|---|
| English manuscript | Draft prepared | `manuscript.md`, generated IEEEtran `manuscript.tex`, active entry point in parent directory |
| Evidence traceability | Audited | `claim_evidence.md`, `assets/sources.json`, `evidence_audit.json`; script verifies actual hashes and raw aggregate metrics |
| Model execution sanity | Same-host diagnostic only | `10_Experiments/g7/cv_report.json`; two fresh arithmetic inputs and two matching KWS runtime repeats |
| Whole-pipeline clean-host replay | NOT RUN | Original G7 run report covers G2/G3 only and did not prove preservation; no claim of <30-minute all-stage replay |
| Novel contribution / nearest-work semantics | OPEN, blocking | G1 partial; compare Chime, CHRYSALIS, Viadotto, FreeML and current intermittent-inference work at action/objective level |
| Quantitative closest baseline B4 | OPEN, blocking | Fair same-cost/output-contract adaptation and runnable comparison required for method-superiority claims |
| Backend/cost evidence | OPEN, blocking current hardware claims | Calibrated macro/NVM/control model absent; accept abstract-cost scope only if contribution and robustness justify it |
| Recovery-aware algorithm | OPEN | Nominal objective lacks redo benefit; candidate space is not demonstrated joint optimization |
| Statistical interpretation | Scope corrected | Paired trace/day blocks; zero-denominator and infinite-p95 results retained; no latency nonregression or robust 20% claim |
| Physical implementation | NOT AVAILABLE | No chip/FPGA, full-network RTL, technology-mapped PPA, measured energy, formal proof, or compiled CPU arena |
| Human internal scientific review | NOT RUN, blocking | Codex-assisted self-review is not independent review |
| Author metadata / approval | REQUIRED, blocking | Names/order, affiliations, email, corresponding author, ORCIDs, funding/conflicts, prior work, permissions, all-author approval |
| AI disclosure | Draft included | Acknowledgments identify Codex and its text/code/artifact-assistance scope; human authors must check completeness |
| Data/code public release | NOT RELEASED | Local evidence is not a public DOI. Review source/model/dataset licenses, attribution and redistribution before depositing |
| Exclusivity / prior publication | UNCONFIRMED | Human authors must disclose earlier submissions/publications and confirm applicable policies |

The choice to delay submission is an evidence-based recommendation, not a claim that IEEE requires silicon or a fixed percentage improvement. No universal IEEE acceptance threshold exists. A four-page compliant PDF is necessary for ESL but cannot establish research originality or soundness.

See [venue decision](../../02_Research/venue_decision.md) and [review findings](internal_review.md). Human metadata fields are collected in `submission_metadata.json`; their null values are intentional.
