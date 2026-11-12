# G9 — Ghi chú đọc nguồn (GĐ 1)

Ngày: **11/11/2026**. Phạm vi: bốn nguồn còn thiếu của G1. Đây **không** phải
systematic review và không chứng minh một kỹ thuật "vắng mặt" trong lĩnh vực.

## Mức bằng chứng thực sự đạt được

| Nguồn | Cách đọc | Mức |
|---|---|---|
| Islam et al. 2025, arXiv 2503.06663v1 | Trích text từ PDF 7 trang, đọc từ đầu đến hết phần tài liệu tham khảo | **Đọc toàn văn** |
| CHRYSALIS, Hou et al., ISCA 2024 (DOI 10.1109/ISCA59077.2024.00022) | Tải PDF 15 trang, trích text; đọc có chọn lọc §2 (Fig. 2), mô hình dataflow/Eq. 4–6, Table III–IV, phần thực nghiệm "Existing AuT setup" và Related Work | **Đọc có chọn lọc**; chưa đọc §6–§8 phần accelerator mới (MAESTRO/GAMMA) và chưa chạy artifact Zenodo |
| FreeML, arXiv 2405.10426v1 | Trích xuất qua công cụ WebFetch (mô hình tóm tắt) trên HTML, 100.000/103.827 ký tự; **không** đọc trực tiếp từng đoạn | **Tóm tắt trung gian**; con số và số section cần kiểm lại trên bản gốc trước khi trích dẫn |
| DIAC, arXiv 2311.16406v1 | Như FreeML, công cụ WebFetch trên HTML | **Tóm tắt trung gian**; như trên |

Quy tắc: chỉ dùng hai dòng "tóm tắt trung gian" để định hướng, không dùng để trích
số hoặc khẳng định absence. Trước khi đưa vào bản thảo phải đọc lại bản gốc.

## 1. Energy-Adaptive Checkpoint-Free Intermittent Inference (2503.06663)

**Cơ chế (Sec. II-A, II-B).** Tiến độ = `L` (layer đang chạy) + `C = (I, W, O)`
(chỉ số input/weight/output trong vòng lặp conv), lưu trong NVM. Không lưu
kết quả trung gian riêng; dữ liệu và activation nằm sẵn trong NVM (FRAM).
Hazard write-after-read (WAR) khi con trỏ chưa cập nhật mà output đã ghi; giải
bằng "critical section" chạy atomically trong cùng power cycle, chỉ vào khi
`E_av > E_req` (dựa dự đoán năng lượng). Low Energy Adaptation (LEA) dùng
pattern pruning + fine-tuning hai bước để bật một tập trọng số nhỏ khi năng
lượng thấp.

**Nền tảng thực nghiệm (Sec. III).** MSP430FR5994 (16 MHz, 8 KB SRAM, 256 KB
FRAM), tụ 100 µF, đo bằng EnergyTrace; MNIST/HAR/GTSRB; mô hình 14K–33K tham số.

**Baseline (Sec. III-B).** Chỉ BASE (không LEA, không CLI) và M1 (nhiều mô hình,
chỉ so bộ nhớ). **Không so với phương pháp checkpoint đã công bố nào**; BASE và
LEA "không hoàn thành" dưới nguồn gián đoạn.

**Điểm chạm với RECAP-CIM**
- Theo dõi tiến độ bằng chỉ số vòng lặp + commit atomic quanh vùng nguy hiểm
  tương đương *PS frontier + publish protocol* của RECAP. **Không được gọi các
  thành phần này là mới.**
- Khác biệt: (1) họ giữ dữ liệu trong NVM, không có trạng thái SRAM-CIM dễ mất,
  không có weight residency; (2) họ đổi mô hình (pruning), không bảo toàn output
  INT8 bit-exact; (3) bảo vệ WAR dựa dự đoán năng lượng, không có commit CRC/marker.
- Hàm ý baseline: cơ chế này chính là "ghi PS vào NVM tại chỗ + loop-index"
  — một họ đối chứng hợp lý (xem GĐ 1 mục 5).

## 2. CHRYSALIS (ISCA 2024)

**Cơ chế đã đọc (§ mô hình năng lượng, Eq. 4–6; Table III–IV).**
- Checkpoint ở **ranh giới tile**: khi không đủ năng lượng, "toàn bộ dữ liệu
  trong VM và phần cứng xử lý" được lưu vào NVM và khôi phục sau đó.
- `E_all = N_tile·E_tile`, trong đó phần checkpoint là
  `N_tile (1 + r_exc) N_ckpt (e_r + e_w)`; `r_exc` là **hệ số cố định theo kịch bản**.
- Ràng buộc `E_tile ≤ E_available`; tile nhỏ hơn thì checkpoint nhiều hơn.
- Không gian thiết kế: kích thước solar panel, tụ (1 µF–10 mF), tile size;
  chiến lược "Tile Partition, ckpt. iNAS-like" (Table III); accelerator mô phỏng
  dựa trên MAESTRO (data-centric, thêm directive `InterTempMap`) và GAMMA.
- Bộ workload: conv cơ bản, CIFAR-10, HAR, KWS (§ thực nghiệm).

**Trong phạm vi các phần đã đọc, không thấy:** chọn từng tile "lưu gì / tính lại
gì" (save-vs-recompute) ngoài checkpoint toàn bộ VM; weight residency của SRAM-CIM;
fusion DW–PW. Đây là *không thấy trong phần đã đọc*, không phải *không tồn tại*.

**Hàm ý.** Eq. 5 là mô hình tile/checkpoint có công bố, đủ cụ thể để làm baseline
adaptation. Cũng cho thấy `r_exc` tĩnh là xấp xỉ; mô hình nguồn/reset tuyệt đối của
G8 chi tiết hơn, nhưng đó là khác biệt kỹ thuật, không tự là novelty.

**Leads chưa đọc** (từ Related Work/refs): iNAS (Mendis 2021), HAWAII (Kang 2020),
Stateful NN (Yen 2022), JAPARI, ResiRCA (Qiu, ReRAM crossbar energy-harvesting
accelerator — **gần nhất với CIM**).

## 3. FreeML (2405.10426) — *tóm tắt trung gian*

Chạy theo layer; buffer NVM riêng cho input/output từng layer để tránh WAR, nên
re-execute layer bị cắt cho kết quả giống nhau (Sec. 2, 3.1.2); chạy trên SONIC/Alpaca;
MSP430FR5994 + Powercast, tụ 1 mF; early exit (gNet) và nén (Tucker/SVD) đổi
output/accuracy. **Hàm ý:** B1_layer của project tương ứng *kiểu re-execute layer*
của họ; đây là control có dẫn nguồn, không phải strawman. Early exit/nén là bài toán khác
(không bit-exact) — không đưa vào baseline cùng contract.

## 4. DIAC (2311.16406) — *tóm tắt trung gian*

Tổng hợp mạch cấp netlist cho node IoT không pin: chèn NVM theo cây, ngưỡng backup và
dải "Safe_Zone" để tránh ghi NVM thừa. Không phải DNN/CIM. Ý tưởng duy nhất đáng
chú ý: **hysteresis (Safe_Zone)** quanh ngưỡng backup — có thể xét như biến thể
của policy thích nghi, không phải đối thủ trực tiếp.

## 4b. Cập nhật lượt 2 (11/11/2026) — đọc trực tiếp và nguồn mới

**Nâng mức đọc.** FreeML và DIAC nay đã được tải HTML gốc, chuyển thành text và đối chiếu
từng đoạn liên quan bằng tìm kiếm từ khóa (không còn chỉ qua tóm tắt công cụ). Chưa đọc tuần tự
toàn văn từng bài. Các điểm ở §3 và §4 được xác nhận: FreeML dùng *working buffer* NVM tách
input/output từng layer để chống WAR, chạy trên lớp ML của SONIC/Alpaca theo từng layer, có
phần early exit/nén (đổi output); DIAC là synthesis cấp netlist với Safe_Zone, mô phỏng với
nguồn "virtual energy source", MRAM, 45 nm.
Trong FreeML có số liệu **không nhất quán trong chính bài** (10,84–16,19% ở phần mở đầu so với
2,41–3,17% ở §5; "19,65%" và "19,65×" cho cùng đại lượng; kết luận nêu 65%). **Không trích các
con số này** cho đến khi xác minh từng bảng.

**CHRYSALIS (đọc thêm).** Phần accelerator mới (Table V) là TPU/Eyeriss kiểu MAESTRO với
workload BERT/AlexNet/VGG16/ResNet18 và mục tiêu latency × diện tích solar panel; **không phải
SRAM-CIM và không có weight residency**. Zenodo (v4, 4/2024; có `iNASModel.py`, `GammaModel.py`):
README không mô tả xử lý checkpoint; chưa chạy artifact.

**Nguồn mới (mức bằng chứng ghi rõ):**

| Nguồn | Mức đọc | Nội dung đã kiểm | Hàm ý |
|---|---|---|---|
| iNAS, Mendis–Kang–Hsiu, ACM TECS 2021 | Chỉ README GitHub + mô tả lại trong 2407.14514 (thứ cấp); **chưa đọc bài gốc** | Cùng khám phá kiến trúc, *execution design* và *preservation design*; mô hình `iNAS-PMod` tính chi phí progress preservation/recovery; batch preservation giữ `S` output trong VM rồi lưu cùng lúc | **Gần nhất với "joint mapping + recovery"** ở MCU+FRAM. Chặn claim novelty ở mức ý tưởng. |
| Accelerate Intermittent Deep Inference, Zhang, arXiv 2407.14514v2 | Đọc HTML đã tải (text, grep + các đoạn chính); preprint một tác giả, chưa có venue | Scheduling/hyper-tile trên iNAS; MSP430; mô tả lại iNAS và batch preservation | Nguồn thứ cấp tốt để spec B5a; không dùng làm bằng chứng cho phương pháp. |
| INTERCEPT, Barjami–Miele–Mottola, SenSys 2024 (DOI 10.1145/3666025.3699364) | **Chỉ abstract** (PDF bị chặn bởi trang kiểm tra bot; không vượt chặn) | Toolchain compile-time chỉnh vị trí/cấu hình thao tác *state persistence* sang STT-MRAM; báo cáo 40% energy gain, tối đa 1% accuracy loss | **Rất gần "chọn lưu cái gì/ở đâu".** Có giảm accuracy ⇒ khác contract bit-exact, nhưng cần đọc toàn văn trước khi phân định. |
| MOUSE, Resch et al., MICRO 2020 | Chỉ abstract/metadata | Spintronic CRAM; MTJ idempotent nên tiến độ lưu sau mỗi phép tính | Backend NVM-CIM không cần save/recompute — cùng nhóm với Viadotto/ResiRCA. |
| ResiRCA, Qiu et al., HPCA 2020 | Chỉ abstract/metadata | ReRAM crossbar energy-harvesting, ResiSchedule cấu hình lại theo mức nguồn; báo cáo tăng tốc 8×/14× so với RCA không biết intermittency | CIM + energy harvesting đã có; nhưng ReRAM (NVM), không phải SRAM dễ mất. |

Còn lại **chưa tiếp cận được**: bản gốc iNAS, INTERCEPT toàn văn, HAWAII, Stateful NN, AutoTile
(không tìm thấy trong lượt tìm), MaxTracker, ESWEEK 2025 (CIM resilient) — ghi vào danh sách mở.

## 4c. Lượt 3 (11/11/2026) — không có bản gốc; dùng mã nguồn iNAS công khai

Người thực hiện không lấy được bài iNAS (TECS 2021) và INTERCEPT. Thay vào đó mình đọc **mã nguồn iNAS
công khai** (`EMCLab-Sinica/Intermittent-aware-NAS`): `IEExplorer/explore_intpow.py`,
`CostModel/cnn.py`, `common.py`, `conv_tiled.py`. Đây là **đọc code, không phải đọc bài**: nó cho biết
repo hiện thực gì, không cho biết bài *claim* gì hay các giả định được lập luận ra sao.

**iNAS-Exp (đọc từ code).** Duyệt vét cạn trên: kích thước tile `(Tr, Tc, Tm, Tn)`, thứ tự vòng lặp
liên-tile (`inter_lo`), và *backup batch size* `S` (số lần lặp tile gộp trong một power cycle trước khi
lưu). Ràng buộc: **C0** (buffer VM `B_in+B_w+B_out` ≤ `VM_CAPACITY`), **C1/atomicity**
(`Epc_max ≤ Eav`, với `Eav` = năng lượng tụ giữa `VON`–`VOFF` nhân hệ số an toàn). Mục tiêu: **tối thiểu
end-to-end latency** `Σ npc·(L_pc + t_recharge)`; mức hòa vốn theo `npc`, số power cycle.

**Khác RECAP ở các điểm có thể kiểm chứng trong code**
- Power cycle được **kế hoạch hóa theo ngân sách năng lượng** (mỗi chu kỳ chạy tối đa `S` tile rồi lưu);
  không mô hình hóa mất nguồn ngẫu nhiên/ngoài kế hoạch ngay giữa phép tính hay expected-redo.
- Mục tiêu là latency, không phải energy/commit; một lớp mỗi lần (per-layer).
- Không có trạng thái weight dễ mất hay quyết định save-vs-recompute: preservation chỉ có `S`.
- Nền tảng MSP430FR5994 (tile-based, vector LEA), không phải SRAM-CIM.

**Hệ quả cho baseline.** `S` của iNAS chính là họ *periodic checkpoint*: **B4_periodic của project là
phiên bản gần iNAS-preservation nhất** (cùng ý "lưu PS theo khoảng cố định"), nhưng B4 chưa tìm tile
dưới ràng buộc C1. B5a (tile + `S` + C1, mục tiêu min energy/commit) là một *adaptation* hợp lệ, gọi
đúng là "iNAS-style adaptation từ code công khai".

**INTERCEPT — vẫn chỉ abstract.** Cùng nhóm tác giả có arXiv 2403.07517 ("Energy versus Output Quality
of Non-volatile Writes in Intermittent Computing": cố ý giảm năng lượng ghi STT-MRAM, chấp nhận lỗi
ghi). Việc INTERCEPT dùng cơ chế này là **suy đoán chưa xác nhận** (trang 2403.07517 không nhắc
INTERCEPT). Nếu đúng, bài toán khác contract bit-exact. Ghi là rủi ro chưa giải quyết, không phân
định bằng suy đoán.

**Kết luận.** G1 **không thể đóng thật sự** với các nguồn có thể truy cập. Hệ quả được chấp nhận:
bài không dựa vào claim novelty của phương pháp; phần Related Work phải ghi rõ iNAS/INTERCEPT chỉ được
đối chiếu ở mức code/abstract; nhờ reviewer độc lập kiểm lại hai nguồn này.

## 5. Kết luận cho G9

1. **Progress tracking + commit atomic** (loop index, WAR, critical section) là prior
   art (2503.06663, FreeML, họ SONIC). RECAP không claim phần này.
2. **Tile-boundary checkpoint với `N_ckpt`, `r_exc`** là prior art (CHRYSALIS/iNAS).
3. Ứng viên còn lại cho phần "mới" vẫn là: *chọn đồng thời* tile DW–PW, weight state
   và save-vs-recompute trên SRAM-CIM dễ mất. Sau lượt 2 **mức tin cậy giảm**: iNAS (cùng
   khám phá execution + preservation design) và INTERCEPT (tối ưu vị trí/cấu hình persistence)
   đã chiếm phần "joint tile + persistence" ở MCU+NVM; phần còn lại chỉ là *áp lên SRAM-CIM dễ
   mất, có weight residency, exact INT8*, và chưa được kiểm vì chưa đọc bản gốc hai bài này.
   Do pivot, bài không dựa vào claim này.
4. Baseline đề xuất cho GĐ 2 (chưa implement, chờ duyệt, xem
   [G9_Pivot_Plan.md](../01_Project_Plan/G9_Pivot_Plan.md) §GĐ 1):
   - **B5a CHRYSALIS/iNAS-style:** checkpoint ở ranh giới tile, `N_ckpt` = toàn bộ trạng
     thái VM sống, tile chọn theo Eq. 5 với `r_exc` hiệu chỉnh từ chính nguồn mô phỏng;
     **thêm tham số batch preservation `S`** (giữ `S` output trong VM rồi lưu cùng lúc, theo
     mô tả iNAS trong 2407.14514) — đây là *execution/preservation design* của iNAS.
   - **B5b Chime-style DP:** chọn điểm checkpoint theo liveness trên đồ thị layer/tile.
   - **B6 loop-index/NVM-direct (2503.06663-style):** ghi PS tại chỗ vào NVM, atomic
     commit, không giữ trạng thái SRAM.
   Đều là *adaptation trên cùng backend/output contract*, gọi đúng như vậy.
