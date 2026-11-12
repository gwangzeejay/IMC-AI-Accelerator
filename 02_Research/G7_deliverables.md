# G7 — Bản thảo, review và chuẩn bị submission

**Ngày:**16/10/2026. **Mốc theo kế hoạch chính:** tuần29–32. Không nhận đã làm đủ bốn tuần công việc chỉ vì tạo được deliverables trong lần thực thi này.

**Trạng thái:** `G7_DRAFT_REVIEW_AND_GAP_REPORT_COMPLETED`.
**Submission:** `NOT_READY`; `submission_ready=false`.

Đã thực hiện nhánh **“bản thảo và báo cáo rõ phần còn thiếu”** của G7. G1 vẫn `PARTIAL_NOT_PASSED`; kết quả G2–G6 giữ phạm vi mô phỏng/RTL hữu hạn. Việc viết bài không chứng minh novelty hoặc thay thế baseline/calibration.

## Bản thảo và review

- [English manuscript](../07_IEEE_Paper/g7/manuscript.md), [references](../07_IEEE_Paper/g7/references.md), [IEEEtran source](../07_IEEE_Paper/g7/manuscript.tex), [PDF](../output/pdf/recap_cim_g7.pdf).
- [Internal review/revision record](../07_IEEE_Paper/g7/internal_review.md):18 findings, phân biệt điểm đã sửa trong bài và scientific blockers còn mở. Đây là Codex-assisted self-review, **chưa phải phản biện độc lập**.
- [Readiness](../07_IEEE_Paper/g7/submission_readiness.md), [claim-to-evidence map](../07_IEEE_Paper/g7/claim_evidence.md), [technical supplement](../07_IEEE_Paper/g7/supplement.md).
- [Venue decision](venue_decision.md), [venue checklist](venue_checklist.md), cover-letter draft và metadata chưa có tác giả thật trong `07_IEEE_Paper/g7/`.

Bài định hướng **Checkpoint Costs in Intermittent SRAM-CIM TinyML: A Simulation Study**. Hướng chẩn đoán bám kết quả hiện có; chưa nhận đóng góp phương pháp tối ưu mới hoặc lợi thế CIM đã đo. Abstract/phương pháp/kết luận giữ giả định chi phí, các ca thua và kết quả undefined.

## Bằng chứng được giữ nguyên

G6 stochastic: KWS99/120 ở RECAP,98/120 ở B3,100/120 ở B1. Model energy/commit giảm1,368% so B3, CI95[0,126%;3,504%], nhưng cao hơn B1 khoảng10,56%. VWW20/120 ở RECAP/B3, gần0% gain; CI có cả giá trị âm. Không đạt mục tiêu20% và không claim finite-latency nonregression từ p95 vô hạn.

ETH-derived: KWS24/36 và VWW4/36 ở RECAP/B3. Giữ energy CI null vì3/2000 và178/2000 bootstrap replicates có zero denominator. Trace đo chỉ cung cấp đầu vào môi trường; rail transfer70% và hệ số backend vẫn assumed.

Hai chẩn đoán: objective không có expected-redo credit nên saved-state bị nominal-cost dominated trong174 pairs; trên steady KWS, scratch publication giải thích mô tả97,76% chênh energy với B1. Direct durable publication và objective sửa đổi là **đề xuất cần kiểm**, chưa phải improvement đã chạy.

## Kiểm tra thực hiện trong G7

1. `audit_g6.py`: PASS,1360 matrix rows,1216 cached cases,481 main commits; kiểm provenance, split, ledger và coverage. Không rerun/tune main inference.
2. [G7 evidence audit](../07_IEEE_Paper/g7/evidence_audit.json): kiểm **2769 manifest entries** G2–G6, source/input freeze và tính độc lập lại **32 aggregate cells** từ448 raw main rows. Đây là integrity/statistical-aggregation audit, không phải fresh full pipeline replay.
3. [Fresh execution diagnostics](../10_Experiments/g7/cv_report.md): KWS72152 + VWW232068 = **304220 tensor elements**, zero mismatch; hai lần chạy một steady KWS case có toàn bộ result dictionary trùng artifact frozen, mỗi lần3 commits, model energy0.0027310116857093567J. Chỉ cùng host, không gọi là cross-host validation.
4. PDF biên dịch bằng Tectonic0.17.0/IEEEtran: **3 trang**, hai cột10pt, Times-compatible fonts; mọi trang567×774pt (7.875×10.75inch). Kiểm không overfull/undefined references/font substitution; render từng trang để rà layout. Khi thêm tác giả phải build và kiểm lại giới hạn4 trang ESL.
5. Sáu hình PDF/SVG/PNG300dpi/BW và năm bảng CSV/Markdown từ schema thật, kèm hashes tại `07_IEEE_Paper/g7/assets/`. Hình1/3 và bảng1 được đưa vào letter; phần còn lại trong supplement. Không tạo điểmCI giả cho undefined.

## Các lỗi G7 có sẵn đã sửa

- `G7_plan.md` lệch tuần/mốc, gọi ESL6–8 trang, coi G1–G6 đều passed: sửa theo kế hoạch chính và nguồn IEEE hiện tại.
- `run_all.py` trước đây chạy stages tại chỗ rồi chỉ kiểm manifest tồn tại để báo preserved=true. Đổi mặc định thành audit đọc-only, kiểm hash thật; report cũ được gắn `SUPERSEDED_UNVERIFIED_REPLAY_REPORT` và sao lưu.
- CV cũ đọc cached JSON, kiểm positive energy và điền tay kết quả vẫn báo PASS. Thay bằng các lần thực thi thực nêu trên, ghi rõ NOT RUN cho cross-host/hardware timing/full clean-host replay.
- Figure/table helpers cũ dùng sai schema, fallback0 hoặc CI điền sẵn sai. Đổi entry points sang generator đã sửa; outputs cũ có cảnh báo superseded và không được dùng trong paper.
- Coverage log đếm dataset/repo/datasheet như paper và nâng selected sections thành full-text coverage. Sửa còn12 research entries với mức đọc/locators đúng; thêm DIAC, checkpoint-free2025, OpenACM2026 dưới mức bằng chứng tương ứng. Không coi đủ20–30 nearest papers hoặc đã có4 confirmed gaps.
- Bản LaTeX legacy có claim unsupported được giữ trong `_backups/G7_before_review_2026-10-16/`; active path nay trỏ tới G7 scoped draft.

## Những phần còn thiếu trước nộp

**P0 khoa học:** nearest-work state/action/objective comparison và B4; calibration hoặc một contribution mô hình trừu tượng được giới hạn và biện minh; sửa objective nếu theo method paper; kiểm direct publication bằng primitive công bằng; freeze mới và fresh test traces sau thay đổi. Cũng có thể phát triển diagnostic paper, nhưng phải chứng minh phát hiện không chỉ là lỗi riêng implementation này.

**P0 tác giả/review:** independent human scientific review, tên/thứ tự/affiliation/email/ORCID, funding/conflicts, prior submissions/publications, all-author approval, licenses/data-release decision và kiểm AI disclosure. Không có thông tin nào được tự điền hoặc certified thay tác giả.

**Chưa làm:** full clean-host G2–G6 replay, cross-host numerical check, physical timing/energy, full-network RTL/PPA/formal proof, compiled CPU arena, public artifact DOI hoặc upload submission. Không cần nhận tất cả phần cứng này cho mọi venue; phạm vi contribution phải phù hợp với bằng chứng thật.

Tái tạo và đóng gói local: [G7 README](../07_IEEE_Paper/g7/README.md). `output/g7/recap_cim_g7_review_package.zip` là source/review package kèm selected evidence, không phải full inference artifact hay submission đã được duyệt.
