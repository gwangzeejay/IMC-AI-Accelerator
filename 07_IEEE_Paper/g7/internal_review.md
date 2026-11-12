# G7 internal review and revision record

Review date: 2026-10-16. Scope: author-side evidence and manuscript review assisted by Codex. **This is not independent peer review.**

Decision: **NO-GO for submission; usable English diagnostic-study draft and explicit missing-evidence report.** A small or negative result can be publishable, but this draft still needs a defensible research contribution, a nearest-work comparison, and evidence supporting the chosen cost scope. No acceptance probability is assigned.

| ID | Severity | Finding | Revision made / remaining acceptance criterion |
|---|---|---|---|
| R01 | Blocking scientific | G1 is partial; no proof of a new joint mapping/recovery method | Removed first/novel/optimal claims. Related work acknowledges Chime, Viadotto, CIM-Tuner, FreeML and CHRYSALIS. Full state/action/objective comparison remains open. |
| R02 | Blocking scientific | Main objective has no expected-redo credit; SAVE_DW/KEEP_PS are never selected | Disclosed the implemented objective and 174/174 diagnostic dominance. Do not infer that saving is useless. A revised algorithm requires frozen design and fresh holdouts. |
| R03 | Blocking claim scope | Primary macro is unselected; loading, compute, NVM/control costs lack calibration | Abstract, methods, figures, and tables explicitly say assumed model costs. No silicon energy, TOPS/W, PPA, or CIM-specific superiority. Either calibrate or substantiate a clearly bounded abstract-model contribution. |
| R04 | Blocking comparison | B4 nearest-literature baseline absent | Named controls B1-B3 as project implementations, not reproductions of Chime/Viadotto. Specify fair adaptation and run it before a competitive-method claim. |
| R05 | Major, corrected in draft | G3 22.09% could be misrepresented as an end-to-end gain | Main result is G6 KWS 1.368% CI [0.126%,3.504%], VWW approximately zero; G3 is only stage-scoped context. Neither confirms the 20% goal. |
| R06 | Major, corrected | RECAP loses to Layer on KWS energy/commit | Kept 100/120 vs 99/120 completion and 10.56% higher RECAP energy. Proposed direct publication is not labeled a measured improvement. |
| R07 | Major, corrected | Undefined bootstrap samples and unfinished arrivals could be dropped | ETH energy CIs stay undefined (3/2000 and 178/2000 replicates). Infinite p95 retained; no finite-latency nonregression claim. |
| R08 | Major, corrected | A sparse VWW sensitivity cell can appear to meet the main goal | Disclosed 3 vs 2 completions/24 arrivals and separated it from primary tests. |
| R09 | Major, corrected | VWW exceeds original memory; source trace is not physical system measurement | Common 64-KiB/2-MiB budgets stated, with logical arena scope; 70% solar transfer remains assumed. No subsecond/harvester-I-V validation claim. |
| R10 | Major, corrected | Accuracy and equivalence could imply a new trained model/full hardware INT8 system | Labeled pretrained reference checks and small VWW subset. Described isolated reference CPU head and preprocessing exclusions. |
| R11 | Major, corrected | RTL scope could be inflated to full accelerator or formal proof | Confined evidence to two microtiles/scalar units; reported timeout/generic-processing limits in supplement. |
| R12 | Major tooling, corrected | Old run_all checks manifest existence, reruns in place, then reports preserved=true | Replaced default with actual hash audit plus independent aggregate checks. Preserved old scripts/report in backup and marked old report superseded. Full pipeline replay on a clean machine remains NOT RUN. |
| R13 | Major tooling, corrected | Old CV reports PASS for reading cached JSON/positive energy and hardcoded transfer numbers | Fresh two-input arithmetic checks and repeated one-case runtime now execute. Same-host only; cross-host and target timing calibration explicitly NOT RUN. |
| R14 | Major tooling, corrected | Old figures/tables use wrong result schema, fallback zeros and incorrect CIs | New generator reads exact schemas, asserts missing data, retains undefined values, and records source hashes. Previous assets are superseded, not evidence. |
| R15 | Major literature, corrected | Coverage log counts artifacts as papers and calls selected-section access full-text coverage | Rewrote counts/access levels; no manufactured 15-paper quota or confirmed absence. Added three accurately bounded literature leads. |
| R16 | Major format, corrected | Old G7 plan labels ESL as 6-8 pages and invents a 2027 journal deadline | ESL limit is four pages including references; regular journal instructions have no annual conference deadline. Current official rules linked. |
| R17 | Submission blocker | Author identities, affiliations, ORCIDs, funding/conflicts, prior-publication declarations and all-author approval unknown | No invented identities or certifications. Working draft banner remains. Human authors must supply and approve metadata. |
| R18 | Submission blocker | Independent human scientific review not performed | This report is a self-review checklist. Obtain a reviewer who checks implementation, statistics, and nearest literature. |

Revisions R05-R16 improve accuracy and reviewability; they do not cure the open scientific blockers R01-R04. The intended G7 outcome is the plan's explicit alternative: a manuscript with a clear report of remaining evidence.

## Next research decision

Two routes are possible. For a method paper, implement a causally justified redo term and shared direct-publication primitive, calibrate the intended model, add the nearest baseline, and use new holdouts. For a diagnostic paper, establish that the objective/publication-path issue is broader than this implementation using a controlled comparison with corrected policies and literature methods. Editing alone cannot supply either route's missing evidence.
