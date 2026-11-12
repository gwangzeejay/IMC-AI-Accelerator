# G2 — Lựa chọn phương pháp mapper

**Quyết định:** dùng enumeration hữu hạn các **policy nhân quả cố định** để
làm mốc kiểm tra ban đầu. Chưa triển khai DP/beam search quy mô mạng ở G2;
không nhận tối ưu toàn cục cho bài toán RECAP-CIM.

## 1. Không gian và objective

`09_Simulation/mapper.py` sinh `(chunk_ci, save_z, keep_ps)`. Profile G2 dùng
chunk 8/16/32/64 trên một descriptor, tổng **16 cấu hình**. Bốn save flags
tại chunk 64 tương đương vì chỉ commit output; có 13 hành vi phân biệt.
Spatial/channel-output mapping và thứ tự descriptor vẫn cố định.

Runtime không đọc tương lai trace. Ngoại tuyến chạy từng policy trên ba
training scenarios: cùng trace tổng hợp nhân công suất với 0.8/1.0/1.2,
giữ horizon/arrivals/deadlines và trọng số scenario bằng nhau.

```text
score(policy) = sum_h(weight_h * energy_h) /
                sum_h(weight_h * completed_h)
```

Energy gồm cả công việc incomplete trong horizon. Mẫu số 0 không khả thi.
Không lấy trung bình các energy/completed riêng từng scenario. Profile yêu
cầu completion/on-time đạt 100% trên ba scenarios; đây là điều kiện debug,
không thay tolerance của main experiment. Hàm từ chối energy `null`.

## 2. Kết quả và cách hiểu

`10_Experiments/g2/mapper_profile.json` ghi 48 evaluations, thời gian PC và
peak allocations do Python `tracemalloc` quan sát. **Không phải peak RSS**,
không phải bộ nhớ/latency/energy runtime trên target.

Với hệ số debug hiện tại, policy được chọn là `z0_ps0_ci64`: toàn microtile
vừa một unit nên không cần intermediate checkpoint. Đây là kết quả hợp lý
và không chứng minh lợi ích RECAP. Không loại cấu hình này để làm save/replay
trông có lợi. Cần workload/energy windows có căn cứ mà full tile không vừa,
và kiểm tra trường hợp phương pháp đề xuất không cải thiện.

Chưa có held-out evaluation. Các giá trị J trong profile là **ASSUMED_DEBUG_ONLY**,
không phải kết quả công bố. Tối ưu chỉ đúng trong tập cấu hình đã liệt kê,
cùng simulator và các giả định đang dùng.

## 3. Baseline prototypes

Profile lưu breakdown chức năng hai prototype cùng arithmetic/commit:

- `B1_microtile_prototype`: toàn bộ prefix 64 kênh, chỉ commit output;
  tương ứng layer-checkpoint khi xem microtile như toàn workload.
- `B2_microtile_prototype`: prefix cố định 16, lưu Z+PS mỗi boundary.

Đây chưa phải B1/B2 mạng đầy đủ. B0 hai backend, B3 energy-adaptive tile,
B4 CIM-Tuner/Chime-inspired và B5 joint mapper vẫn chưa được reproduce.
Không dùng scalar NumPy arithmetic để nhận đã triển khai macro digital
hoặc đo lợi ích CIM so với non-CIM.

## 4. Khi chuyển sang G3

1. Hoàn tất macro/cost/source calibration và memory liveness.
2. Mở descriptor generator cho spatial/CI/CO tiles, halo và bank residency;
   mỗi descriptor cần arithmetic/dependency/recovery checks tương đương.
3. Liệt kê tập nhỏ để làm optimum trong tập policy; dùng DP/beam để sinh
   ứng viên khi số descriptor tăng, đo gap và chi phí search.
4. Freeze policy bằng training/validation; chạy test traces độc lập cùng
   arrivals/horizon. Không chọn lại trên test hoặc dùng future state.
5. Ratio objective không được thay bằng Bellman chỉ có additive energy;
   nếu dùng fractional optimization, công bố cách xử lý completion và
   feasibility, chẳng hạn search lambda cho `E-lambda*N_completed`.

Chi phí enumeration hiện tại là O(P*H*simulation_cost), với P là số policy,
H là số scenarios; không nhận complexity cubic hoặc guaranteed-optimal DP
khi chưa có transition model và state abstraction được kiểm chứng.

## 5. Cập nhật G3

Đã hiện thực enumeration spatial/CO/CI/save flags, descriptor-specific
admission và train/validation/test protocol tại
[g3_mapping_spec.md](g3_mapping_spec.md). Đây là phát triển tiếp theo của
bản G2, không thay đổi các kết quả G2 đã lưu. Kết luận G3 và giới hạn ở
[G3 deliverables](../02_Research/G3_deliverables.md); chưa có DP/beam search,
full-network mapper hoặc cost calibration.
