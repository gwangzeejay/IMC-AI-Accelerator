# G2 — Hiện thực và nghiệm thu bước đầu

Ngày: **15/10/2026**. Trạng thái: **PARTIAL_CORE_VALIDATED — nền chức năng đã
kiểm tra, chưa đủ điều kiện đóng toàn bộ G2**. G1 vẫn PARTIAL; không đổi
`ready_for_energy_results=false`.

## 1. Những gì đã thực hiện và chạy thật

| Deliverable G2 | Artifact và bằng chứng | Trạng thái |
|---|---|---|
| INT8 reference thật | MLPerf Tiny DS-CNN chính thức; pin commit và model SHA-256 | Đã có |
| Golden tensors DW–PW | 4 cặp trên 4 fixtures, so 256.000 phần tử với TFLite BUILTIN_REF | Không mismatch |
| State/action/commit spec | [recovery_spec](../03_Architecture/recovery_spec.md), slot bytes và checksum thật | Đã có bản microtile thực thi |
| Bốn save/replay policy | `(save_z, keep_ps)` đủ 4 tổ hợp, prefix CI 16 | Chạy đúng khi không lỗi và trong fault campaign |
| Cold recovery | Xóa SRAM/banks; restore chỉ từ record publish; PS đi cùng offset | Có tests trước/sau publish và restore bị ngắt |
| Cost ledger | Byte/MAC/action/replay breakdown; missing energy là `null` | Đã có schema và kiểm tra |
| Source cơ sở | Capacitor + harvest trace ghép actual load; conservative admission | Đã kiểm tra bằng hệ số giả định |
| Baseline breakdown | B1/B2 **microtile prototypes**, không phải full-network baselines | Có trong mapper profile |
| Chọn phương pháp mapper | Enumeration 16 cấu hình / 3 train scenarios = 48 evaluations | Đã profile; G3 mới mở rộng DP/beam |
| Backend macro được hiệu chuẩn | Chưa có digital macro đáp ứng đủ arithmetic/update/load parameters | Chưa đạt |

## 2. Model và phạm vi golden reference

- Repository: [MLCommons Tiny](https://github.com/mlcommons/tiny).
- Commit: `4addd0fa08d216e20637637874e084895f289da4`.
- Model SHA-256: `aeea436800704fce17b17292e4412630ad856e9d777c044c64ef748a880bd0ae`.
- TFLite file **53.936 B**; INT8 weights **22.016 B**; tất cả constant
  tensors **24.376 B**; input `[1,49,10,1]`; **2.656.768 MAC/inference**.
  MACs dùng quy ước dense nominal, tính cả vị trí kernel padding; đây
  không phải số cycle hay số phép toán sau zero-skipping. File bytes,
  weight bytes và constant bytes là ba đại lượng khác nhau.
- 1 sample INT8 có sẵn trong reference submission chính thức + 3 fixtures
  min/max/random seed `20261015` để stress số học. Không có nhãn/dataset
  test đầy đủ nên **chưa đo accuracy**, không công bố tỷ lệ nhận dạng.
- TFLite chạy toàn model để lấy intermediate/output tensors; NumPy reference
  độc lập kiểm tra **4 cặp DW–PW**, không nhận đã tự hiện thực và kiểm chứng
  first convolution, pooling, dense và softmax.
- Quantization/rounding được đối chiếu với implementation và
  [nguồn TensorFlow quantization](https://github.com/tensorflow/tensorflow/blob/v2.21.0/tensorflow/lite/kernels/internal/quantization_util.cc).
  Giữ requantization giữa DW và PW; giới hạn accumulator được xuất theo kênh.

Source, README và license được giữ tại
[reference_mlperf](../05_Model_Training/reference_mlperf/source_manifest.json).
Golden report: [reference_report.json](../10_Experiments/g2/reference/reference_report.json).

## 3. Kiểm tra phục hồi

Microtile dùng tensor của cặp đầu tiên: anchor 4×4×64, DW output 2×2×64,
PW output 2×2×4. NVM có hai slot 4096 B. Commit marker atomic một byte là
**giả định của simulator**, chưa được datasheet/brownout test xác nhận.

- **22 unit tests**, gồm signedness, zero-point padding/stride, saturation,
  INT32 overflow, atomic publish, metadata/payload corruption, sai identity,
  capacity, PS cũ offset 16 khi volatile đã tới 32, restore lại mất nguồn,
  source/ledger balance, admission và incomplete horizon.
- Fault campaign: **3.099 ca**, gồm 1.712 single-boundary cuts,
  384 interior-write cuts, 3 targeted restore-interruption cases và
  1.000 seeded multi-fault cases.
- **5.035 lần mất nguồn thực thi, không mismatch** trong các ca đã chạy. Coverage từng
  pha và seed nằm trong [fault summary](../10_Experiments/g2/faults/summary.json);
  từng ca có log `cases.jsonl`.
- Đây là tập kiểm tra hữu hạn trên một descriptor. Không xem là chứng minh
  đúng cho mọi byte/chuỗi fault, mọi tile hoặc toàn mạng.

Đã phát hiện và sửa lỗi số học của source simulator: sai số tích phân thời
gian khiến packet/marker hoàn tất bị hiểu là còn thiếu một phần rất nhỏ,
dẫn tới ghi thiếu byte. Có regression test riêng cho lỗi này.

## 4. Source, cost và mapper

[Cost schema](../03_Architecture/cost_model_schema.md) phân biệt functional
unknown energy với **ASSUMED_DEBUG_ONLY**. Functional summary giữ total
energy `null`; không dùng giá trị legacy không có nguồn.

Debug trace cố định horizon 0,25 s, một input. Hai policy giữ PS hoàn tất;
hai policy không giữ PS còn incomplete do reserve/boot bảo thủ. Incomplete
vẫn bị tính năng lượng đã dùng, energy/completed không xác định, p95 vô hạn.
Đây là kiểm tra semantics, **không phải bằng chứng chính sách mới tiết kiệm
năng lượng trên phần cứng**.

[Mapper profile](../10_Experiments/g2/mapper_profile.json) chọn
`z0_ps0_ci64` trong tập nhỏ: microtile vừa một unit nên layer checkpoint
thắng các cấu hình checkpoint trung gian dưới hệ số debug. Không loại
baseline này và không coi kết quả là đã chứng minh RECAP có lợi.
Chưa có held-out test hoặc tối ưu spatial/CO/bank residency.

Source residual, ledger energy so với load energy, metric và full horizon
được kiểm tra bằng pipeline. Thời gian mapper/peak allocations ghi trong
report là số trên PC, không phải runtime cycles/peak RSS/SRAM phần cứng.

## 5. Điều kiện còn thiếu để đóng G2

- [ ] Chọn/đặc tả macro digital INT8 có nguồn cho compute, update bandwidth,
  load energy/latency; hoặc miền giả định kiến trúc có justification đủ rõ.
- [ ] Hoàn tất NVM/bus/converter/boot/controller cost và giả định marker
  atomic thực tế. Không đánh dấu complete chỉ vì config debug chạy được.
- [ ] Liveness/arena/scratch và durable anchor layout cho **toàn mạng**;
  `activation_peak_bytes`, `checkpoint_payload_bytes` và
  `all_live_memory_fits_nvm` vẫn chưa biết. Capacity microtile không chứng
  minh capacity full inference.
- [ ] Golden/reference và profiling được mở rộng theo descriptor generator
  trước khi nhận mapper full-network hoạt động; baseline B0–B5 phải được
  hiện thực công bằng ở các mốc tiếp theo.
- [ ] Speech Commands test inputs/labels và protocol đo accuracy thật trước
  báo cáo benchmark end-to-end; không dùng stress fixtures để tính accuracy.

Nền G2 đủ để tiếp tục phát triển simulator/descriptor, nhưng chưa đủ căn cứ
chạy nghiên cứu so năng lượng chính thức hoặc nhận G2 PASS hoàn toàn.

## 6. Tái lập và kiểm tra artifact

Chạy từ thư mục gốc:

```powershell
python 10_Experiments/run_g2.py
```

Xem [hướng dẫn](../10_Experiments/reproduce.md),
[run manifest](../10_Experiments/manifests/g2_run.json),
[unit test log](../10_Experiments/g2/unit_tests.txt),
[functional summary](../10_Experiments/g2/functional/summary.json) và
[source-debug summary](../10_Experiments/g2/source_debug/summary.json).
Manifest pin phiên bản Python/NumPy/TensorFlow và SHA-256 code/config/results.

Các file có sẵn bị cập nhật được sao lưu tại
[`before_G2_2026-10-15`](./_backups/before_G2_2026-10-15/manifest.json).
Legacy RTL, training bằng dữ liệu ngẫu nhiên và paper số liệu cũ không được
dùng làm bằng chứng của lần G2 này.
