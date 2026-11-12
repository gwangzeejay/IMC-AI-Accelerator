# G9 — Pivot: bản đồ crossover của state-saving trên SRAM-CIM dễ mất

Ngày: **11/11/2026**. Trạng thái: **đã duyệt hướng đi (A+B); GĐ 0 hoàn tất; GĐ 1 đang làm.**
Các đợt G2–G8 và `Project_Plan_IMC_TinyML.md` giữ nguyên làm bằng chứng lịch sử
(bản sao lưu: `Project_Plan_IMC_TinyML.v3_2_backup_2026-11-11.md`).

## Vì sao pivot

Kết quả G8 (cost giả định): RECAP_redo bằng B3_adaptive ở miền chính (chênh 0% trên KWS,
~1e-13 trên VWW, là nhiễu số); main chọn `SAVE_DW=0`, `KEEP_PS=0`; mục tiêu giảm 20% chưa đạt.
Novelty matrix: G1 `PARTIAL_NOT_PASSED`. Phần tiến độ/commit đã có prior art (xem
[G9_literature_notes.md](../02_Research/G9_literature_notes.md)).

## Câu hỏi nghiên cứu mới

> Với suy luận INT8 bit-exact trên SRAM-CIM dễ mất, trong miền chi phí/nguồn nào việc lưu
> DW/PS (`SAVE_DW`, `KEEP_PS`) hoặc replay thắng một policy tile-thích-nghi đơn giản (B3)
> và các baseline mô phỏng prior art — và ngoài miền đó thì không?

Đóng góp mục tiêu: **bản đồ crossover có độ nhạy cost**, kèm các ca thua; không phải
"phương pháp mới", không claim "first", không claim giảm 20%.

## Quy tắc ngôn ngữ (áp dụng cho mọi tài liệu từ G9)

- Dùng "nghiên cứu chẩn đoán/crossover", "adaptation", "control". Không dùng
  "reproduction" khi chưa chạy lại mã gốc.
- Số liệu năng lượng luôn ghi "model" và `calibrated=false` cho đến khi có calibration.
- Không dùng B1 làm đối chứng chính; so với mọi control mạnh, giữ ca thua.

## Tiêu chí dừng (khóa trước khi chạy GĐ 2)

1. **Có vùng thắng:** tồn tại vùng trong không gian sweep mà RECAP (`SAVE_DW`/`KEEP_PS` ≠ 0)
   giảm model energy/commit so với **mọi** baseline mạnh (B3, B5a, B5b, B6) với CI95 (paired
   bootstrap) không chứa 0, trên holdout khóa mới, ở ít nhất hai workload → viết bản đồ crossover
   hai chiều (có vùng thắng và thua).
2. **Không có vùng thắng:** viết negative result đầy đủ (hướng A thuần): ngưỡng cost cần để state-saving
   có lợi nằm ngoài khoảng có căn cứ datasheet/paper.
3. Không chỉnh cost, seed hoặc tập holdout sau khi thấy kết quả để chuyển từ (2) sang (1).
   Mọi thay đổi protocol phải khóa lại và ghi vào log.

## Các giai đoạn

| GĐ | Nội dung | Phụ thuộc | Trạng thái |
|---|---|---|---|
| 0 | Ghi G9 vào kế hoạch, ngôn ngữ, tiêu chí dừng | — | **Xong 11/11/2026** |
| 1 | Đọc nguồn còn thiếu; coverage log; novelty matrix; spec baseline | — | **Đóng có điều kiện (xem giới hạn iNAS/INTERCEPT); chưa implement baseline** |
| 2 | Sweep crossover (NVM cost × outage × capacitor × workload), holdout mới | GĐ 1, 3 | **Đã chạy main 20261111-m2 (11/11/2026): `NO_REGION` (xem "Kết quả main")** |
| 3 | Cost có căn cứ: khoảng giá trị từ datasheet/paper | — | **Xong 11/11/2026: khoảng [0,627; 8,91]; lock rev 2** |
| 4 | Viết bài, review độc lập, chọn venue theo CFP thực tế | GĐ 2 | **Bản nháp negative result: [07_IEEE_Paper/g9/manuscript.md](../07_IEEE_Paper/g9/manuscript.md) (11/11/2026); chưa review độc lập, chưa chọn venue** |

## GĐ 1 — Kết quả và việc còn mở

**Đã làm** (chi tiết và mức bằng chứng ở [G9_literature_notes.md](../02_Research/G9_literature_notes.md)):
- Lượt 1 (11/11/2026): đọc toàn văn 2503.06663; đọc có chọn lọc CHRYSALIS.
- Lượt 2 (11/11/2026): đối chiếu trực tiếp FreeML, DIAC trên HTML gốc; đọc thêm CHRYSALIS Table V và
  README Zenodo; đọc 2407.14514; ghi abstract/metadata iNAS, INTERCEPT, MOUSE, ResiRCA.
- **Phát hiện chính:** iNAS và INTERCEPT là prior art gần nhất cho "joint tile + persistence" (MCU+NVM).
  Hướng pivot sang bản đồ crossover là phù hợp hơn; không dùng claim "joint mapping + recovery" làm novelty.

**Còn mở trước khi đóng G1 (không được coi là đã đạt):**
- [x] Đọc lại FreeML và DIAC trên bản gốc (đối chiếu từ khóa; chưa đọc tuần tự toàn văn).
- [x] Đọc CHRYSALIS phần accelerator và README artifact (chưa chạy artifact).
- [~] **Bản gốc iNAS và INTERCEPT toàn văn: không truy cập được** (người thực hiện xác nhận 11/11/2026).
  Thay bằng đọc **mã nguồn iNAS công khai** (lượt 3; không phải đọc bài). INTERCEPT chỉ abstract; liên hệ
  với ghi STT-MRAM xấp xỉ (arXiv 2403.07517) là suy đoán chưa xác nhận. **Rủi ro chấp nhận được:** bài không
  claim novelty phương pháp; Related Work ghi rõ mức đối chiếu; nhờ reviewer độc lập kiểm lại hai nguồn này.
- [ ] HAWAII (Kang 2020), Stateful NN (Yen 2022), AutoTile (GLSVLSI 2024; chưa tìm thấy), MaxTracker, ESWEEK 2025.
- [ ] Đọc ResiRCA và MOUSE ở mức phương pháp (hiện chỉ abstract).
- [ ] Tìm thêm công trình tới coverage 20–30 (hiện 17 nguồn nhận diện, đa số mức abstract).
- [x] Spec B5a, B5b, B6 đã duyệt (11/11/2026) và implement; xem mục "Implement baseline".

**Spec sơ bộ baseline** (chờ duyệt; không implement trước):
| ID | Nguồn cảm hứng | State/action | Ghi chú |
|---|---|---|---|
| B5a | iNAS code (`IEExplorer`, `CostModel`) + CHRYSALIS Eq. 5 | Duyệt `(tile, loop order, S)` với ràng buộc C0 (VM) và C1 (`E_pc ≤ E_av`); lưu PS sau mỗi `S` lần lặp tile; chọn min model energy/commit | Adaptation từ code công khai (không từ bài); iNAS gốc tối thiểu hóa latency, ghi rõ khác biệt; B4 hiện chỉ là họ `S` không tìm tile |
| B5b | Chime 2016 §5–6 | Vị trí checkpoint tối ưu theo liveness (DP) | Nếu không map sạch lên đồ thị layer/tile thì ghi lý do và loại |
| B6 | 2503.06663 | PS ghi tại chỗ vào NVM, loop-index + commit atomic | Không giữ trạng thái SRAM sau mất nguồn |

## Implement baseline (11/11/2026)

Mã: [g9_runtime.py](../09_Simulation/g9_runtime.py); test: [tests_g9](../09_Simulation/tests_g9/test_g9.py)
(10 test đạt; chạy bằng Python 3.12 có TensorFlow, như môi trường G6). Không sửa file G2–G8; `check_project.py`
vẫn PASS (audit G8 độc lập, RTL) và 14 test G8 vẫn đạt. **Chưa chạy bất kỳ so sánh năng lượng nào** giữa
các policy mới và B3/RECAP: so sánh chỉ được làm ở GĐ 2 sau khi khóa protocol/holdout.

| ID | Hiện thực trong backend | Khác biệt so với nguồn (phải ghi trong bài) |
|---|---|---|
| B5a_inas | Ứng viên `(n, co, chunk=S)` với `z=False`, `ps` iff `chunk<CI`; ràng buộc C0 (SRAM, sẵn có) + **C1**: workload lớn nhất của một power cycle (kể cả DW prologue và output write) × (1+margin) ≤ dung lượng tụ; chọn min năng lượng danh định/output | Từ **code công khai** iNAS, không từ bài. iNAS tối thiểu latency; ở đây dùng năng lượng như đại diện cho vùng recharge chiếm ưu thế (giả định, cần ghi rõ). Không loop-order (backend không có). Hazard-blind: không checkpoint nếu không cần. |
| B5b_chime_dp | DP trên ranh giới CI (đơn vị chunk nhỏ nhất, 16): chọn tập checkpoint **không nhất thiết đều** tối thiểu hóa chi phí kỳ vọng; đoạn = `cost·expm1(x)/x + expm1(x)·recovery`, `x=λT`, restart-về-checkpoint-gần-nhất, tính cả công bị bỏ; cùng hazard cố định `planning_outage_rate_hz` như G8 | Chime gốc dùng liveness thanh ghi/ràng buộc khoảng cách thực thi; ở đây liveness là PS (`4·n·co` byte) và `z` luôn replay. Mô hình hazard mũ là giả định. Bank cold khi lập kế hoạch để tập kết quả xác định sau reboot. |
| B6_loopindex | Chunk mịn nhất (16), PS lưu mỗi chunk, `z=False` | **Trùng B4_periodic ở interval 16** (test `test_b6_is_periodic_limit`). Cơ chế gốc (ghi tại chỗ vào NVM, atomic bằng dự đoán năng lượng) không biểu diễn được. Báo cáo như "giới hạn mịn nhất của họ periodic", không như một baseline độc lập, và không tính hai lần trong thống kê. |

Chưa làm: đăng ký ba method vào protocol/runner (cần khóa ở GĐ 2), so sánh với B3, calibrate hazard cho DP.

## Khóa protocol GĐ 2 (11/11/2026)

Tệp: [g9_protocol.json](../09_Simulation/configs/g9_protocol.json) (máy đọc, là nguồn quy tắc),
[analysis_plan.md](../10_Experiments/g9/analysis_plan.md) (diễn giải), [run_g9.py](../10_Experiments/run_g9.py),
[analyze_g9.py](../10_Experiments/analyze_g9.py), khóa băm [protocol_lock.json](../10_Experiments/g9/protocol_lock.json)
(166 tệp: mã, cấu hình, mô hình, input, scenario, split).

- **Lưới (cố định):** `nvm_energy_scale` ∈ {0,25; 1; 4; 16} (tương đối so với hệ số G6 giả định) ×
  tốc độ reset thực {1, 4, 16} Hz × dung lượng tụ {25 µJ, 100 µJ} × 6 replicate/ô × 2 workload = 48 ô.
- **Policy (8 chạy):** B1_layer (chỉ báo cáo), B3_adaptive, B4_ci16, B4_ci64, B5a_inas, B5b_chime_dp,
  RECAP_nominal, RECAP_redo. B6 không chạy (≡ B4_ci16). Không chọn interval ⇒ không tuning.
  Hazard lập kế hoạch cố định 2 Hz, không biết tốc độ thực.
- **Quy tắc ô thắng:** RECAP_redo giảm ≥ 2% so với **cả 5 control mạnh**, CI95 paired bootstrap > 0, không
  kém về completion/on-time, **và** thực sự dùng state-saving ở ≥ 10% quyết định tile. **Vùng** = hai ô kề nhau
  cùng thắng trong một workload. Phán quyết: `REGION_BOTH_WORKLOADS` / `REGION_ONE_WORKLOAD` / `NO_REGION`.
- **Input:** KWS holdout mới 72 (chỉ số 4–9 mỗi lớp, G8 dùng 0–3); **VWW dùng lại 20 ảnh holdout G8 (công khai vì
  không còn ảnh mới)**; seed reset/trace mới, kiểm không trùng G6/G8.
- **Phân tích phụ (không vào phán quyết):** hazard khớp tốc độ thực; nguồn ngẫu nhiên kiểu G8 ở scale 1; so với B1.
- **Test:** 19 test G9 đạt (10 runtime + 9 quy tắc quyết định trên dữ liệu tổng hợp). Smoke trên input development
  (20 hàng) đạt: output khớp reference, ledger cân. Kết quả smoke chỉ là kiểm hoạt động, **không dùng chỉnh gì**.
- **Chốt chặn:** `--stage main` từ chối chạy khi `grounded_nvm_scale_range` còn `null` hoặc bất kỳ tệp đã băm bị đổi.
  Quy tắc bổ sung: được phép điền duy nhất trường này (cùng nguồn trích) rồi khóa lại *trước* khi chạy main; đổi bất kỳ
  thứ gì khác là phiên bản protocol mới. Phạm vi đó chỉ chọn ô nào mang phán quyết chính, không đổi lưới hay quy tắc.

**(Đã xong ở GĐ 3, xem mục dưới.)** Việc cũ: xác định khoảng `nvm_energy_scale` có căn cứ (datasheet FM25V20A, paper), ghi nguồn, điền
protocol, khóa lại, rồi mới chạy main (ước tính vài chục phút: VWW ≈ 3 s/hàng × ~1.150 hàng).

## GĐ 3 — khoảng NVM scale có căn cứ (11/11/2026)

Tệp: [nvm_scale_range.json](../02_Research/hardware_selection/nvm_scale_range.json),
[derive_nvm_scale_range.py](../10_Experiments/g9/derive_nvm_scale_range.py),
[protocol_lock_history.md](../10_Experiments/g9/protocol_lock_history.md).

Cách tính: năng lượng chip-only mỗi byte `E = 3,3 V × I × 200 ns` (8 xung SPI ở 40 MHz) so với hệ số G6 giả định
(đọc 1 nJ/B, ghi 2 nJ/B), tách riêng đọc và ghi, cả điều kiện typ và max.

| Thiết bị (nguồn) | Đọc / G6 | Ghi / G6 |
|---|---|---|
| FM25V20A FRAM (datasheet local, Table 11) | 1,58–1,98× | 0,79–0,99× |
| MB85RS2MTA FRAM (RAMXEED, IDD @40 MHz 1,9 typ/2,3 max) | 1,25–1,52× | 0,63–0,76× |
| MR25H10 MRAM (Everspin Rev 9.5; đọc 6/10 mA, ghi 23/27 mA) | 3,96–6,60× | 7,59–8,91× |

**Khoảng đã khai báo: [0,627; 8,91].** Ô nằm trong: NVM scale 1× và 4×; ngoài: 0,25× và 16×.

Giới hạn bắt buộc phải nêu trong bài:
- Chỉ chip-only (cận dưới); I/O của SPI master, level shifter, controller, bộ chuyển đổi, startup **chưa tính** nên năng lượng thật cao hơn một hệ số chưa định lượng.
- Một hệ số nhân chung cho đọc và ghi; G6 có ghi/đọc = 2 trong khi FRAM ≈ 1 và MRAM ≈ 3,8, không scale đơn nào khớp mọi thiết bị.
- MR25H10 lấy từ bản sao của nhà phân phối; MB85RS2MTA giả định cùng IDD cho đọc và ghi.
- NOR flash (W25Q64PW) bị loại: cần erase và ghi theo trang; chỉ ghi chương trình ≈ 3,4×, có khấu hao erase ≈ 53× (ngoài lưới). Embedded NVM trên chip (thấp hơn nhiều) cũng ngoài khoảng. Phán quyết chính chỉ nói về lớp NVM nối tiếp ngoài, byte-addressable, không erase.

Khóa lại rev 2: chỉ đổi trường `grounded_nvm_scale_range` (+ khối dẫn nguồn) và một dòng test; mọi tệp đã băm khác không đổi
so với rev 1. Khai báo **trước** bất kỳ kết quả main nào.

## Kết quả main (11/11/2026)

Run bất biến `10_Experiments/g9/20261111-m2/` (protocol G9_1.0 rev 2, lock nguyên vẹn; 2.304 hàng chính + 896 hàng phụ;
`results.json` sha256 `fbebbd01…22d0`). Lần `20261111-m1` bị dừng đột ngột giữa VWW (không traceback), **bị hủy và không
phân tích**; không dùng cho bất kỳ con số nào.

**Phán quyết theo luật đã khóa: `NO_REGION`** — cả ô trong khoảng có căn cứ (NVM 1× và 4×) lẫn toàn lưới.
Nhãn 48 ô: win 0, win_without_state_saving 0, loss 0, tie_or_inconclusive 48. → áp dụng tiêu chí dừng 2 (negative result).

Quan sát đọc từ dữ liệu (không đổi luật, không đổi ô):
- `RECAP_redo` **không chọn state-saving ở bất kỳ ô nào** (`state_saving_fraction` = 0 ở 48/48 ô, cả 0,25× lẫn 16×; cả biến thể `@matched` hazard ở phần phụ). Kế hoạch được chọn đều `z0ps0`. `RECAP_nominal` và `RECAP_redo` chọn y hệt nhau. Đối chiếu G8 `20261023-v2`: RECAP cũng có tỉ lệ 0 ở G8, nên không phải hồi quy của G9.
- Vì vậy RECAP_redo trùng kết quả `B3_adaptive` (|giảm| < 1e-9 ở 26/37 ô có định nghĩa, trong đó 21 ô bằng đúng 0; 5 ô còn lại là nhiễu số cỡ 1e-13 như ở G8) và gần như trùng `B5b_chime_dp`/`B4_ci64` (|chênh| ≤ 1% ở đa số ô). Không ô nào thắng mọi control mạnh với ngưỡng ≥ 2% và CI95 > 0.
- RECAP_redo giảm so với `B4_ci16` 0,2–76% (B4_ci16 dùng state-saving ~64% quyết định ở KWS) và so với B5a tới 72%, nhưng đó không đủ để thắng B3.
- 11/48 ô có mọi tỉ lệ giảm không xác định (không hoàn thành suy luận nào; NVM 16× và VWW 4× ở 16 Hz). Giữ nguyên, không loại. Trong khoảng có căn cứ, 2 ô (VWW 4× 16 Hz, hai dung lượng) thuộc loại này.
- Một số ô có control thắng RECAP chút ít (đến −1,0%) nhưng dưới ngưỡng 2%, nên không phải "loss".

Giải thích đúng phạm vi: trong mô hình chi phí giả định (G6) và hazard lập kế hoạch cố định 2 Hz, xếp hạng
expected-redo không bao giờ ưu tiên SAVE_DW/KEEP_PS trên lưới này; control có state-saving (B4_ci16, B5b) không rẻ
hơn. Đây là **kết quả về mô hình giả định, không phải đo đạc**, và chưa chứng minh state-saving vô ích trên phần cứng thật.
Chưa chẩn đoán vì sao xếp hạng không chọn state-saving (lỗi cài đặt hay ràng buộc cấu trúc của mô hình); chẩn đoán sau
này phải đi như phân tích mới, không sửa kết quả này.

Giới hạn: chi phí và hazard là giả định; B5a (từ code công khai) và B5b/B6 là adaptation; bài iNAS/INTERCEPT không đọc
được; ảnh VWW dùng lại từ G8 (đã khai báo); GĐ 1 vẫn còn mở (HAWAII, Stateful NN, AutoTile…).

## Chẩn đoán: vì sao RECAP không chọn state-saving (11/11/2026)

Phân tích **sau kết quả**, chỉ đọc; không đổi protocol, run hay phán quyết `NO_REGION`. Tệp:
[diagnostics_20261111/](../10_Experiments/g9/diagnostics_20261111/) (dùng ảnh phát triển, import code đã khóa, không ghi vào dự án).

1. **Bộ xếp hạng phản ứng với hazard trên VWW nhưng không trên KWS (sửa lại sau review 12/11/2026; bản trước ghi "không phải bug" quá rộng).**
   Tăng hazard lập kế hoạch lên 100–100.000 Hz (tile đầu mỗi stage): VWW ở NVM 0,25×–1× chọn state-saving (1/15 stage ở 100 Hz, 7/15 ở ≥1.000 Hz; ở 16× chỉ 1/8);
   KWS **không chọn ở stage nào (0/6) kể cả 100.000 Hz** — do khiếm khuyết ở mục 3. Ở hazard của lưới (≤16 Hz) cả hai đều không chọn.
2. **Nguyên nhân kinh tế (chính).** Tile KWS fused 8 px × CO64: không chia chunk ≈ 10,1 µJ, 1,36 ms; có z1+ps1 ≈ 29,3 µJ (+190%),
   chỉ ps1 ≈ 24,5 µJ (+143%). Xác suất reset trong một tile ở 16 Hz chỉ ≈ 2%. Với mô hình phơi nhiễm đầy đủ, điểm hòa vốn
   ps1 so với không chia chunk ≈ **2 kHz** (hand-calc, bỏ qua chi phí recovery nên chỉ là ước lượng cỡ độ lớn), cao hơn lưới (≤16 Hz) khoảng 100 lần. Tức là chi phí ghi NVM (giả định G6) lớn hơn
   năng lượng làm lại vì tile ngắn và tiêu năng lượng thấp so với chu kỳ reset. KWS (ci = 64) có kế hoạch một chunk nên không cần chia; VWW (ci 128/256, chunk ≤ 64) bị ép chia nên mới có state-saving khi hazard cao.
3. **Khiếm khuyết mô hình trong `expected_remaining` (G8, đã đóng băng).** Rủi ro chỉ tính tại các biên giữa chunk (`times[:-1]`); kế hoạch một chunk
   có xác suất mất = 0 ở mọi hazard, và chunk cuối của kế hoạch nhiều chunk cũng không bị tính rủi ro. Ở λ = 10⁵ Hz, kế hoạch chia chunk không lưu ps cho giá trị kỳ vọng `inf`
   còn kế hoạch một chunk vẫn giữ nguyên chi phí danh nghĩa. Mô hình thiên về kế hoạch ít biên. Sửa lỗi này chỉ dời điểm hòa vốn từ "không bao giờ" xuống ≈ 2 kHz cho tile KWS, nên không đổi kết luận trên lưới G9, nhưng
   là sai lệch có hướng cần nêu trong bài.
4. **Vì sao B3 ≡ RECAP_redo:** với hazard lập kế hoạch 2 Hz mọi chênh lệch kỳ vọng chỉ cỡ 0,1%, và `score_time` (B3) với `score_expected` (RECAP) chọn cùng kế hoạch không chia chunk.
5. **Endpoint:** năng lượng mô hình mỗi suy luận hoàn thành không tính điện tích tụ bị xả khi reset, nên reset chỉ tốn phần làm lại tile bị ngắt. Điều này làm state-saving khó có lợi hơn so với điểm cuối theo độ trễ/hoàn thành; chưa thử endpoint đó.

Chưa giải thích được: `B5b_chime_dp` và `B4_ci16` dùng state-saving 46–77% quyết định nhưng B5b chỉ kém RECAP ≤ 1%; tôi chưa kiểm hình dạng tile mà B5b chọn.

Ý nghĩa cho hướng đi: kết quả âm là **cấu trúc**, không phải do tinh chỉnh. State-saving chỉ có thể thắng khi tile dài so với 1/λ
(tile nhiều ms, reset ≳ 0,5 kHz), hoặc NVM ghi rẻ hơn khoảng hai bậc, hoặc khi ép phải chia chunk (ci lớn/dung lượng nhỏ). Mọi thử nghiệm
tiếp theo cho các vùng đó phải là protocol mới (G9.1) với khóa mới.

## Rủi ro

- Baseline mạnh (B5a/B5b) có thể thu hẹp hoặc xóa vùng thắng → vẫn báo cáo được (tiêu chí 2).
- Cost chỉ lấy từ datasheet là chi phí thiết bị, chưa phải giao dịch/bo mạch; giữ khoảng và `calibrated=false`.
- Các con số FreeML/DIAC chưa kiểm trên bản gốc; không trích vào bản thảo.
