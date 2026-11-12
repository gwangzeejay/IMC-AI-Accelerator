# G1 novelty matrix — RECAP-CIM

**Phiên bản:** 1.3; **kiểm tra:** 15/10/2026; **trạng thái:** giả thuyết khác biệt chưa qua G1.

## 1. Quy ước bằng chứng

- **Metadata/abstract:** xác nhận danh tính và phát biểu tác giả; không chứng minh một kỹ thuật vắng mặt.
- **Mục liên quan đã đọc:** có section/page locators; kết luận chỉ trong phạm vi đó.
- **Artifact:** đã xem repository không đồng nghĩa đã chạy/reproduce.
- **Chưa xác minh:** cần bổ sung tài liệu. “Không thấy trong phần đã đọc” không đồng nghĩa “không tồn tại”.

Bảng G1 mô tả giả thuyết thiết kế. Đến G7 đã có implementation G2–G6 trong phạm vi mô phỏng/RTL hữu hạn; điều này không tự xác nhận novelty của từng kỹ thuật. Bank tags/vùng weight là trạng thái chi tiết; không quay lại mô hình chỉ có ALL/PARTIAL/NONE.

## 2. So sánh có dẫn chứng

| Công trình | Nguồn và vị trí đã kiểm tra | Điều có thể kết luận | Điều chưa được phép kết luận |
|---|---|---|---|
| Chime 2016 | S1: PDF tr. 4–6, in tr. 280–282, §§5–6; tr. 9, §9.5 | Tối ưu checkpoint, chi phí lưu trạng thái và recomputation đã có | Không gọi cost decomposition/save-vs-recompute nói chung là mới; chưa chứng minh toàn lĩnh vực thiếu weight-aware recovery |
| Viadotto 2025 | S2: §§2.1, 3.1–3.3 | Backend NVM-CRAM, allocation/dataflow/controller và thích nghi song song | Không suy ra “không cần tracking/controller/recovery” chỉ vì NVM không mất dữ liệu |
| CHRYSALIS 2024 | S3: metadata/abstract và artifact landing page | Energy/inference co-design đã được đề xuất | Chưa đọc đủ phương pháp để loại trừ mọi quyết định RECAP; là việc còn thiếu của G1 |
| CIM-Tuner 2026 | S4: §§III-B–III-D, Eq. (5), Table I; §IV-A; README | Có weight-update bandwidth/cost characterization, mapping nhiều cấp và partial-sum trade-off | Weight loading/mapping cost riêng lẻ chưa phải điểm mới; scope được đọc không phải bằng chứng mọi phương pháp intermittent còn thiếu |
| TDC-CiM 2026 | S5: §§III-A, III-E, IV-E; Tables II–III | Có SRAM-CIM INT8, weight-stationary và macro/mapping selection | Không xem là digital exact-INT8 backend hoặc khẳng định intermittent extension là mới toàn lĩnh vực |
| FreeML 2024 | S6: abstract và cấu trúc §3.3 | Memory/energy-adaptive intermittent inference là prior art quan trọng | Không đưa early exit vào baseline bit-exact mà bỏ qua khác biệt output/accuracy |
| FERMI-ML 2025 | S7: abstract, §II-B và evaluation | Digital multi-precision; cần kiểm tra approximation và định nghĩa phép toán | Không đồng nhất XNOR/Posit-4 với binary-only; chưa xác nhận phù hợp exact INT8 |
| PSCNN 2022 | S8: abstract | SRAM-CIM KWS nhị phân đã có | Không chuẩn hóa trực tiếp binary TOPS/W thành INT8; không tự gán ternary nếu chưa có nguồn |
| KWS IMC/on-chip learning 2022 | S9: metadata/abstract | KWS + SRAM-IMC + model adaptation đã có | Không gọi tổ hợp KWS/IMC/QAT là mới |

Các source IDs và URL nằm trong [G1_source_audit.md](G1_source_audit.md). Bảng này không thay thế full-text coverage log của 20–30 công trình sát nhất trong plan.

## 3. Kiểm tra từng đóng góp dự kiến

| Thành phần RECAP | Trạng thái | Phép kiểm tra cần có |
|---|---|---|
| Weight reload cost | Yếu tố chi phí cần mô hình hóa; không mới độc lập | Đối chiếu update bandwidth/dataflow của CIM-Tuner; tách reload do remapping khỏi reload do cold reboot |
| DW–PW mapping + `(save_z, keep_ps)` + weight-bank state | Ứng viên đóng góp kết hợp | Đối chiếu state/action/cost của phương pháp gần nhất, gồm fusion và intermittent mapping; chưa xác nhận mới |
| Checkpoint copy-on-write/atomic publish | Yêu cầu correctness dùng kỹ thuật đã biết | Fault injection, PS/offset consistency và durable anchor |
| Cost write/read/replay riêng | Đã có tiền lệ ở checkpointing | Dùng để mô hình đúng, không tách thành novelty claim |
| INT8 | Lựa chọn arithmetic, không mới | Golden tensor và quy tắc rounding/saturation của model cụ thể |

**Phát biểu tạm thời:** RECAP-CIM khảo sát liệu việc đồng chọn tile DW–PW, trạng thái weight và dữ liệu cần lưu/tính lại khi SRAM bị mất có giảm chi phí hoàn thành suy luận hơn các đối chứng trên cùng backend hay không. Đây là câu hỏi nghiên cứu, chưa phải kết quả hoặc bằng chứng “first”.

## 4. Baseline và ví dụ cần xây dựng

Giữ ID B0–B5/O1 như plan; mapping prior art ứng viên là CIM-Tuner-inspired, recovery prior art ứng viên là Chime-inspired. Xem [G1_deliverables.md](G1_deliverables.md) để tránh nhầm macro TDC-CiM với checkpoint policy.

Ví dụ dự kiến: hai phương án có cùng input/tile đích, một giữ Z/PS trong NVM, một replay DW với cùng PS frontier. Tính cả weight miss sau reboot và transaction overhead; so với từng policy cố định. Đây mới là specification cho microbenchmark, chưa có kết quả chứng minh policy kết hợp thắng.

## 5. G1 còn mở

- [ ] CHRYSALIS và các công trình fusion/intermittent inference sát nhất được đọc ở mức state/action/objective.
- [ ] Xác định và ghi locators cho nguồn gần nhất có thể phủ định novelty.
- [ ] Chọn B4 và mô tả adaptation; chưa gọi implementation lấy cảm hứng là reproduction gốc.
- [ ] Kiểm tra cập nhật literature gần ngày nộp. Không dùng matrix này để tuyên bố “không công trình nào có”.

## 6. G7 cập nhật — 16/10/2026

G1 vẫn **PARTIAL_NOT_PASSED**. [Coverage audit đã sửa](coverage_log.md) ghi12 research papers, không đếm datasheet/repo/dataset thành papers và không gọi selected-section access là full-paper review. Ba nguồn bổ sung có danh tính xác minh: DIAC (arXiv2311.16406), checkpoint-free intermittent inference (2503.06663), OpenACM (2601.11292). Mức đọc khác nhau được ghi rõ; không suy ra absence từ abstract.

Implementation G6 chưa có expected-redo credit trong objective, không chọn SAVE_DW/KEEP_PS ở main tests và chưa có per-pair fusion graph optimizer. Vì vậy dòng ứng viên “joint mapping + recovery” chưa thể đổi thành novelty claim đã chứng minh. B4 và đối chiếu đầy đủ CHRYSALIS/nearby methods còn mở. Bản thảo G7 chuyển sang diagnostic simulation study, không nhận là phương pháp recovery tối ưu mới.

## 7. G9 cập nhật — 11/11/2026

Định hướng đổi sang nghiên cứu crossover ([G9_Pivot_Plan.md](../01_Project_Plan/G9_Pivot_Plan.md));
bảng §3 không còn là danh sách đóng góp. Cập nhật theo [G9_literature_notes.md](G9_literature_notes.md):

| Thành phần | Kết luận mới (phạm vi phần đã đọc) |
|---|---|
| Progress tracking (layer + loop index/PS frontier), atomic commit/WAR | **Prior art**: 2503.06663 (đọc toàn văn), FreeML (tóm tắt trung gian). Không claim. |
| Checkpoint ở ranh giới tile với `N_ckpt`, `r_exc` | **Prior art**: CHRYSALIS Eq. 5 (đọc có chọn lọc), iNAS-like. Không claim. |
| Tái thực thi theo layer (B1) | Tương ứng cách FreeML/SONIC re-execute layer; là control có nguồn. |
| Chọn đồng thời tile DW–PW + weight state + save-vs-recompute trên SRAM-CIM dễ mất | Không thấy trong phần đã đọc; **chưa kiểm** (ResiRCA, iNAS, HAWAII chưa đọc). Không dùng làm claim. |

Baseline GĐ 2 (đề xuất, chưa implement): B5a CHRYSALIS/iNAS-style, B5b Chime-style DP, B6 loop-index/NVM-direct.
G1 vẫn `PARTIAL_NOT_PASSED`.

### G9 lượt 2 — 11/11/2026

| Thành phần | Cập nhật |
|---|---|
| "Joint tile/execution + preservation design" | **Prior art ở MCU+NVM:** iNAS (execution + preservation design, batch preservation) và INTERCEPT (tối ưu vị trí/cấu hình persistence). Cả hai mới ở mức README/abstract; cần bản gốc để phân định chính xác. |
| CIM + energy harvesting | ResiRCA (ReRAM crossbar), MOUSE (spintronic CRAM): backend **NVM**, không có bài toán SRAM mất dữ liệu. |
| Phần còn lại có thể khác biệt | Áp dụng lên SRAM-CIM dễ mất với weight residency và đầu ra INT8 bit-exact. Chưa kiểm; không dùng làm claim. |

### G9 lượt 3 — 11/11/2026

iNAS đối chiếu từ **code**: duyệt `(tile, loop order, S)` dưới ràng buộc VM và năng lượng mỗi power cycle,
mục tiêu latency, power cycle kế hoạch hóa (không mất nguồn ngẫu nhiên, không save-vs-recompute, không
weight residency). INTERCEPT chưa phân định (chỉ abstract). Không dùng để khẳng định khoảng trống.
