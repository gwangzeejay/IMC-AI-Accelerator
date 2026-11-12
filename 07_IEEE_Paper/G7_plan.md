# G7 — Tuần29–32: viết bài, review và chuẩn bị submission

**Cập nhật16/10/2026.** Kế hoạch chính tại `01_Project_Plan/Project_Plan_IMC_TinyML.md` là nguồn đánh số mốc. Bản G7_plan trước đây ghi tuần25–28, đặt viết bài sang G8, gọi ESL6–8 trang và coi G1–G6 đều đã hoàn thành; các diễn giải đó đã được sửa. Bản trước giữ trong `_backups/G7_before_review_2026-10-16/07_IEEE_Paper/`.

## Kết quả thực hiện

- English diagnostic-study draft: [manuscript](g7/manuscript.md), IEEEtran source và PDF kiểm layout.
- Review và sửa các tuyên bố vượt bằng chứng: [internal review](g7/internal_review.md).
- Sáu hình/năm bảng từ JSON frozen, source hashes và claim map; không dùng fallback zero hay điền sẵn CI.
- Audit thực2769 manifest entries và32 aggregate cells; fresh execution diagnostics trên cùng host. Không nhận full clean-host replay hoặc physical timing validation.
- [Readiness](g7/submission_readiness.md), candidate venue có điều kiện, cover-letter draft, metadata cần tác giả thật hoàn tất, local source/review ZIP.

**Trạng thái:** `G7_DRAFT_REVIEW_AND_GAP_REPORT_COMPLETED`; `submission_ready=false`. Đây là nhánh “báo cáo rõ phần còn thiếu” của tiêu chí G7. Không chuyển G1 thành passed và không coi việc viết bài là đã chứng minh novelty.

## Những việc phải có trước nộp

Novelty/nearest-work comparison và B4; cost calibration hoặc contribution mô hình trừu tượng được biện minh; expected-redo objective nếu nhận là method paper; fresh holdouts sau thay đổi; review độc lập; danh tính/ORCID và đồng thuận tác giả; license/public artifact review. Xem [G7 deliverables](../02_Research/G7_deliverables.md) và [build/review guide](g7/README.md).

Không ép đạt quota15papers,4gaps hay<30phút bằng cách đếm repo/datasheet, đọc lại JSON hoặc bỏ qua stage. Không có kiểm chứng nào được phép báo PASS khi chưa chạy thao tác tương ứng.
