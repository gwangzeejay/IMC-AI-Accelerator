# G2 — Schema cost ledger và mô hình nguồn

## 1. Hai chế độ tách biệt

| Chế độ | Config | Dùng để |
|---|---|---|
| Functional | `09_Simulation/configs/g2_functional.json` | Kiểm tra bit-exact/crash consistency; energy/duration thiếu là `null` |
| Assumed debug | `09_Simulation/configs/g2_assumed_debug.json` | Kiểm tra ghép nguồn–tải, ledger và admission bằng hệ số tự đặt rõ nhãn |

Config debug **không lấy làm calibration macro digital hoặc FM25V20A**, không
được đưa vào bảng tiết kiệm năng lượng của bài báo. Parameter manifest G1
vẫn giữ `ready_for_energy_results=false`. Không ghép số chip-only trong
datasheet với số end-to-end để gọi là tổng năng lượng hệ thống.

## 2. CostModel

```json
{
  "energy_j_per_unit": {"read_byte": null, "write_byte": null},
  "seconds_per_unit": {"read_byte": null, "write_byte": null},
  "leakage_w": null,
  "provenance": "source / section / derivation / explicit assumption",
  "calibrated": false
}
```

Các unit kinds đang dùng: `read_byte`, `write_byte`, `bank_byte`, `dw_mac`,
`pw_mac`, `requant`, `boot`, `control`, `wait_s`.

- NVM read và bank programming là hai phần riêng: load weight tính cả hai.
- DW/PW charge số MAC thực hiện. Bias/requantization giữ đúng số học;
  requant có event cost riêng.
- Checkpoint write bao gồm payload, metadata, invalidate và publish marker.
- Boot cơ sở đọc toàn bộ hai slot để validate; restore payload đọc thêm.
  Cách này bảo thủ và chưa tối ưu startup.
- Controller/hash/IO phải được phân bổ rõ trong profile sau calibration;
  hiện hệ số debug chỉ là hợp đồng test tổng quát, không có characterization.
- Standby/off load trong ví dụ debug **giả định bằng 0**. Chưa thể dùng
  giả định này cho FRAM/bus thật. Leakage debug cũng được đặt 0 có chủ đích.

Nếu energy, duration cần thiết hoặc leakage chưa biết, event energy là
`null`; tổng có một event unknown cũng là `null`. Không thay bằng 0 và
không bỏ event unknown để tạo tổng trông có vẻ hoàn chỉnh.

## 3. Một ledger event

Các trường gồm `event_id`, năm identity IDs, `action`, `phase`, `unit_kind`,
`requested_units`, `completed_fraction`, `charged_units`, `duration_s`,
`energy_j`, `replay`, `start_s`, `parameter_source`.

Năng lượng action có duration được mô hình hóa đều theo thời gian; khi fault
cắt giữa chừng, charge đúng phần thời gian đã chạy. Write dở giữ prefix
bytes; compute dở không promote kết quả. Nếu sau này phần cứng có burst,
startup surge hoặc công suất không đều, phải chia action thành các phase
đúng profile, không giữ giả định đều.

Replay được đánh dấu trên DW/PW attempt đã từng thực hiện; chi phí đã nằm
trong các event thật. Không cộng thêm `p_loss * recovery_cost` vào ledger.
Breakdown tách theo action; bytes/MAC có đơn vị khác nhau nên không cộng
`units` giữa các action để tạo một chỉ số vật lý chung.

## 4. Source model

`recap/power.py` tích phân giải tích từng đoạn công suất harvest hằng số,
ghép với load thực tế tại **capacitor rail**:

```text
E_max = 0.5*C*(V_max^2 - V_off^2)
dE/dt = P_harvest_at_rail - P_load_at_rail
0 <= E <= E_max
E_initial + E_harvested - E_load - E_spilled - E_final = 0
```

Nguồn/bus/đổi áp trước rail đã được trừu tượng hóa trong debug; không có
hiệu suất conversion được xác minh. Trace nằm tại
`09_Simulation/traces/g2_debug_harvest.json`, là trace **tổng hợp**.

Simulator truy cập trace tương lai chỉ để tích phân môi trường. Runtime
policy chỉ biết descriptor cố định và energy hiện tại. Cùng harvest có thể
sinh thời điểm mất nguồn khác nhau khi load khác nhau; unit test kiểm tra
điều này, không áp một danh sách depletion times chung lên các policy.

## 5. Admission và observation horizon

Mỗi progress unit reserve một upper bound gồm boot/validate, mọi read/load,
DW/PW, requantization và commit tối đa. Không ghi có harvesting tương lai.
Bound G2 cố ý rộng, dùng chung mọi save flags; đây chưa phải admission được
tối ưu theo descriptor như G3. Nếu thiếu reserve, cold power-off có chủ
đích, `WAIT_CHARGE` với tải off bằng 0 theo giả định, rồi mới boot lại.

Với bound chính xác và không có fault ngoại sinh, không được có depletion
bên trong unit đã admit. Fault campaign là mất nguồn bất ngờ để thử tính
đúng, tách khỏi kết quả source-debug. Không dùng fault theo chỉ số action
để so hiệu năng giữa các policy.

Source-debug đánh giá một input, arrival 0, deadline bằng horizon 0.25 s.
Sau output commit, giữ observation tới hết horizon với tải off giả định.
Ledger energy phải khớp `Reservoir.consumed`, residual < 1e-12 J trong test.

Các policy không giữ PS có thể không hoàn tất trong trace ngắn do boot và
reserve bảo thủ. Kết quả đó phải là `incomplete`, energy/completed không
xác định; không được so sánh nó như một suy luận đã hoàn tất.

## 6. Metrics đã hiện thực và phần còn thiếu

`recap/metrics.py` nhận input arrivals/deadlines trong horizon, committed
completion hoặc failed terminal; trả completion/on-time, throughput,
energy/completed và nearest-rank p95. Incomplete/failed có latency vô hạn;
JSON xuất `p95_latency_s=null` kèm `p95_is_infinite=true`.

Chưa có input queue/dataset arrivals đa mẫu trong simulator, measured power
traces, converter model, calibration uncertainty hoặc runtime controller
overhead characterization. Vì vậy đây là nền G2, chưa là evaluation G4.
