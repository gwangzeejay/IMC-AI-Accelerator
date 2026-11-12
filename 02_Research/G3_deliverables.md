# G3 — Microbenchmark, mapper v1 và quyết định tiếp tục

Ngày: **15/10/2026**. Trạng thái: **MODEL_ONLY_G3_COMPLETED** — đã hoàn thành
đợt microbenchmark G3 trong mô hình giả định, có lợi ích và giới hạn tái lập.
Chưa đóng các thiếu sót calibration G1/G2, chưa nhận lợi ích năng lượng
phần cứng hoặc tính mới đủ cho bài báo IEEE.

## 1. Kết luận để quyết định

**Tiếp tục có điều kiện ở hướng mapping và kiểm chứng mô hình; thu hẹp
claim về đồng tối ưu SAVE/REPLAY và lợi ích đặc thù CIM. Chưa đầu tư lớn
vào RTL dựa trên số năng lượng hiện tại.**

Trên 18 trace test mới, mapper hoàn tất **9/18** workload so với **8/18**
của baseline thích nghi B3 prototype. `E_completed` của mô hình giảm
**22,09%**, CI95 bootstrap **14,65–38,08%**. Point estimate vượt mục tiêu
20% và không giảm completion/on-time; CI vẫn bao gồm mức dưới 20% nên
không tuyên bố đã bảo đảm giảm ít nhất 20%.

Mapper chọn **spatial 1×2, CO16, CI64, không lưu Z/PS trung gian**. Cải
thiện hiện tại gắn với mapping/tần suất checkpoint. Nó không chứng minh
joint SAVE/REPLAY là nguồn cải thiện: CI64 chỉ có output commit nên hai
save flags không có tác dụng. Ablation tắt weight reuse cho cùng kết quả
trên tập test này; chưa có bằng chứng lợi ích riêng của weight residency.

## 2. Công việc đã thực hiện

| Hạng mục | Kết quả có artifact |
|---|---|
| Fixed workload | 8 spatial pixels × 16 output channels, 128 INT8 values từ golden MLPerf Tiny |
| Descriptor generator | 75 descriptor duy nhất; coverage không thiếu/trùng output, halo và quantization giữ đúng |
| Mapper bản đầu | 64 cấu hình (40 hành vi phân biệt), enumeration train/validation, freeze trước test |

> **Note về 64 cấu hình vs 40 hành vi phân biệt:** 64 = 4 spatial (1×1, 1×2,
> 2×2, 4×2) × 2 CO (4, 16) × 2 CI (16, 64) × 4 save flags = 64 cấu hình
> hình thức. 24 cấu hình bị loại trùng vì CI=64 chỉ có output commit nên
> cả bốn save flags `(save_z, keep_ps)` đều tương đương về durable prefix,
> còn 2 spatial-CO kết hợp không tạo descriptor mới do anchor/dim trùng.
> Do đó enumerator chỉ khảo sát 40 hành vi runtime khác nhau trong tập
> 64. Không phải lỗi enumeration; là kết quả của domain reduction trong
> G3 microtile workload.
| Recovery/memory | Dedicated two-slot jobs, durable output frontier, content-based weight tags, bank/input/Z reuse có dependency checks |
| Source/admission | Bound theo descriptor/live state, boot có actual header/payload reads, source–ledger balance |
| Experiments | 901 evaluations main/sensitivity/witness; 6 train, 6 validation, 18 test |
| Kiểm tra | 39 unit/regression tests; 4.112 fault cases, 6.022 loss thực thi, không mismatch |
| SAVE/REPLAY episodes | 36 evaluated episodes + 18 probes, cùng PS prefix; không mismatch |
| Tái lập | Một lệnh, config/split/frozen policy, raw JSONL, manifests SHA-256, PNG/SVG |

Chi tiết kỹ thuật: [g3_mapping_spec](../03_Architecture/g3_mapping_spec.md).

## 3. Kết quả held-out trong mô hình

Các số uJ dưới đây là **ASSUMED MODEL ENERGY**, không phải đo phần cứng.
Energy numerator bao gồm mọi công việc incomplete trong horizon.

| Phương án | Completed / 18 | Completion/on-time | Model uJ / completed |
|---|---:|---:|---:|
| B1: whole tile, output-only checkpoint | 6 | 33,33% | 9,478 |
| B2: fixed mapping/tile, Z+PS | 0 | 0% | Không xác định |
| B3: fixed mapping, energy-adaptive CI | 8 | 44,44% | 40,362 |
| Mapper v1 | 9 | 50,00% | 31,448 |
| Fixed mapping, fit recovery flags | 0 | 0% | Không xác định |
| Mapper, tắt weight reuse | 9 | 50,00% | 31,448 |
| Matched SAVE, CI16, keep PS | 0 | 0% | Không xác định |
| Matched REPLAY, CI16, keep PS | 0 | 0% | Không xác định |

B1 có model energy/completed thấp hơn mapper nhưng hoàn tất ít hơn 3/18
workload; không gọi đây là lợi ích với mức hoàn thành tương đương.
Fixed-mapping recovery search không có policy thỏa feasibility B3;
ablation được giữ để thể hiện giới hạn, không ghi là một optimum khả thi.

Tất cả completed outputs khớp golden. Không có unexpected depletion trong
source runs đã admission; power-off giữa units là scheduled. p95 của các
phương án là vô hạn vì còn incomplete; không nhận latency non-regression
bằng cách so vô hạn với vô hạn.

B3 ở đây chỉ thích nghi CI trên spatial/CO cố định, chưa là baseline mạnh
nhất trong prior art. Vì vậy 22,09% chưa chứng minh vượt nearest SOTA,
chưa đủ tách lợi ích thuật toán khỏi độ yếu của mapping baseline.

## 4. SAVE_DW / REPLAY_DW: kết quả và giới hạn

Trong main held-out sensitivity 3×3, cả SAVE/REPLAY CI16 đều không hoàn
tất workload. Giữ đầy đủ chín cells là **undefined**, không biến chúng
thành 0% cải thiện, không bỏ trace thiếu output.

Để tách nguyên nhân, đã thêm phép thử **exploratory, sau main analysis**
trên một descriptor của mapping đã freeze, `keep_ps=true` cho cả hai:

- Không outage: lưu Z gây chi phí thừa; tại hệ số main DW×30/write×1,
  SAVE dùng nhiều năng lượng mô hình hơn REPLAY khoảng **9,8%**.
- Một cold loss ngay sau cùng committed prefix CI=16: tại cùng hệ số,
  SAVE giảm khoảng **3,86%** so với REPLAY.
- Trên chín hệ số, reduction của SAVE trong case một cold loss từ
  **−8,96% đến +20,28%**. Xu hướng phụ thuộc compute/write cost và sự
  kiện mất SRAM; không có policy thắng ở mọi điều kiện.

Đây là state-aligned intervention cho một descriptor, không phải cùng
wall-clock outage, không phải whole-workload performance hay dữ liệu
held-out để nhận claim chính. Hệ số DW×300 chưa có căn cứ macro; không
chọn riêng cell thuận lợi đó để khẳng định mục tiêu năng lượng đã đạt.

## 5. Hướng nghiên cứu sau G3

1. **Ưu tiên capacity-aware spatial/CO mapping và kích thước durable unit.**
   So thêm baseline cũng thích nghi spatial/CO, không chỉ CI như B3 v1.
2. Giữ SAVE/REPLAY là lựa chọn có điều kiện. Viết được cost/feasibility
   boundary có xét prefix, boot, weight reload, metadata và lần dùng Z tiếp
   theo; chỉ nhận joint optimization contribution khi ablation chứng minh.
3. Chốt macro/NVM/bus/atomicity và uncertainty từ G1/G2 trước khi chuyển
   hệ số giả định thành claim. Đối chứng non-CIM và nearest-prior-art B4
   vẫn thiếu; chưa thể gọi lợi ích là riêng cho SRAM-CIM.
4. Mở rộng descriptor/workload và liveness toàn mạng, input/dataset thật,
   input queue và traces đo được. Sau đó mới freeze một test set mới cho
   nghiên cứu tiếp theo; không tune tiếp trên 18 traces đã báo cáo này.
5. RTL G4 có thể bắt đầu bằng kiểm tra traffic/control/arithmetic nhỏ;
   chưa cần mở rộng triển khai chỉ để minh họa một số phần trăm giả định.

Nếu baseline spatial-adaptive mạnh xóa lợi ích hoặc calibrated costs làm
joint policy không có lợi, chuyển problem statement sang miền lựa chọn
recovery policy/feasibility. Chưa có cơ sở gọi miền đó là đóng góp mới
toàn lĩnh vực nếu coverage G1 chưa hoàn tất.

## 6. Protocol correction và provenance

Harness thử đầu dùng nhầm B2 làm feasibility reference. Đã sửa theo plan
sang B3, giữ nguyên grid/costs/ngưỡng. Bộ test đã xem có seed base 51000
được retire và lưu trong [`_diagnostics`](../10_Experiments/g3/_diagnostics/initial_B2_feasibility_reference/README.txt).
Final protocol 1.1 dùng test seed base **71000**. Không gộp kết quả hai đợt
và không dùng kết quả diagnostic để nhận held-out improvement.

Artifacts chính:

- [Protocol](../09_Simulation/configs/g3_protocol.json), [frozen mapper](../10_Experiments/g3/frozen_mapper.json).
- [Experiment summary](../10_Experiments/g3/summary.json), [fault summary](../10_Experiments/g3/faults/summary.json).
- [Recovery episodes](../10_Experiments/g3/recovery_episodes.json), [unit log](../10_Experiments/g3/unit_tests.txt).
- [Held-out figure](../10_Experiments/g3/plots/heldout_comparison.png), [source sensitivity](../10_Experiments/g3/plots/save_replay_sensitivity.png), [episode heatmaps](../10_Experiments/g3/plots/recovery_episodes.png).
- [Run manifest](../10_Experiments/manifests/g3_run.json), raw records tại `10_Experiments/g3/raw/`.

Tái lập từ thư mục gốc:

```powershell
python 10_Experiments/run_g3.py
```

Model/golden đã lưu cục bộ; không cần download hoặc huấn luyện lại.

## 7. Cập nhật sau G3

Đã có [G4 RTL deliverables](G4_deliverables.md): kiểm chứng controller,
binary metadata, transaction/cycle và fault recovery trên microtiles.
Định dạng/bus khác mô hình G3, nên các kết quả đó không xác nhận lại số
22,09% ở trên. Kết quả G3 giữ nguyên; G5 cần đồng bộ codec/traffic/cost
trước khi sử dụng số năng lượng như một kết luận về triển khai.
