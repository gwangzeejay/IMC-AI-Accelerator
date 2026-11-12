# G2 — Đặc tả phục hồi của microtile DW–PW

Ngày: 15/10/2026. Artifact thực thi: `09_Simulation/recap/simulator.py`,
`recap/storage.py`. Phạm vi hiện tại là **một microtile**, chưa phải mạng
intermittent hoàn chỉnh hoặc firmware trên FRAM thật.

## 1. Số học và descriptor

- NHWC, batch 1; DW multiplier 1, dilation 1; PW 1×1.
- Activation/weight signed INT8; weight zero point bằng 0; bias/PS INT32.
- Giữ requantization và activation sau DW, trước PW. Dùng gemmlowp hai lần
  làm tròn; không thay bằng `round(float)`.
- Descriptor G2 là cặp DW–PW đầu tiên: output DW tại y=1:3, x=1:3,
  toàn bộ 64 input channels; 4 output channels PW. Input anchor 4×4×64
  có halo; DW VALID tạo output 2×2×64.
- `model_hash`, `input_id`, `descriptor_id`, `arithmetic_id`, `layout_id`
  gắn với checkpoint. Descriptor không thay đổi giữa lần chạy/phục hồi.
- Thứ tự PW là prefix kênh liên tiếp; bias chỉ được thêm khi khởi tạo PS.
  Offset `k` nghĩa là PS chứa đúng đóng góp `[0,k)`.

Golden tensors và bound accumulator nằm trong
`10_Experiments/g2/reference/`. Bound bảo thủ:

```text
max_abs_input = max(abs(-128 - input_zp), abs(127 - input_zp))
bound[co] = abs(bias[co]) + max_abs_input * sum(abs(weights[..., co]))
```

Từ chối nếu bound vượt INT32; phép dịch trái trong requantization cũng có
guard riêng. Không mô phỏng wraparound như kết quả hợp lệ.

## 2. State và dữ liệu thật

| State | Biểu diễn hiện thực |
|---|---|
| Immutable NVM | Bản sao input anchor, DW/PW weights và bias; NumPy read-only |
| Durable checkpoints | Hai `bytearray`, mỗi slot 4096 B; chứa bytes payload, metadata và marker |
| SRAM | Input, Z, PS, output; chỉ được đánh dấu có dữ liệu sau khi action hoàn tất |
| Weight banks | Hai bank riêng DW/PW; có tensor thật, bias, tile ID, layout, valid region, capacity |
| `offset` / `progress_d` | Prefix volatile / prefix từ record đã publish và đã đọc khi boot |
| `pending_txn` | Generation, target slot và pha đang ghi; mất khi cold reset |
| Attempt history | Chỉ dùng để đánh dấu replay trong ledger; không cho runtime khôi phục dữ liệu |

Cold loss xóa mọi SRAM, bank tags, offset volatile và pending runtime state.
Checkpoint bytes đã ghi vẫn giữ. `progress_d` trong runtime được nạp lại
khi boot; không suy diễn prefix từ payload chưa publish.

## 3. Slot layout và commit

```text
byte 0        : atomic marker (0xA5 = published)
bytes 1..4    : metadata length, uint32 little-endian
bytes 5..36   : SHA-256(metadata)
bytes 37..1060: metadata area, tối đa 1024 B
bytes 1061..  : Z / PS / output payloads, C order, INT32 little-endian
```

Metadata gồm generation, identity, PS offset, tensor shapes/dtypes/ranges,
payload length/SHA-256 và output-committed flag.

1. Chọn slot khác slot mới nhất hợp lệ; invalidate marker trước khi ghi.
2. Ghi payload theo từng packet tối đa 32 B. Fault giữa packet chỉ giữ prefix
   bytes đã ghi; chưa làm payload trở thành checkpoint.
3. Ghi length, metadata checksum và metadata. Slot cũ vẫn có hiệu lực.
4. Publish marker một byte; sau đó mới cập nhật runtime durable record.
5. Boot đọc/kiểm tra cả hai slot, chọn generation hợp lệ lớn nhất. Checksum
   hỏng hoặc identity khác bị loại; output chỉ hoàn tất khi record output
   đã publish và payload đúng.

**Giả định mô phỏng:** ghi marker một byte là atomic old-or-new; các write
đã hoàn tất là persistent, có thứ tự; checksum phát hiện corruption được
thử. Đây chưa phải bảo đảm brownout của FM25V20A. Cần xác minh power/bus
protocol trước khi chuyển sang firmware hoặc nhận tính đúng phần cứng.
Simulator chưa mô hình write reorder, cache chưa flush, generation wrap,
checksum collision hoặc hỏng đồng thời cả hai slot.

## 4. Bốn policy và prefix cũ

| `save_z` | `keep_ps` | Record checkpoint mới |
|---|---|---|
| false | false | Không thêm Z/PS mới; giữ prefix durable cũ nếu có |
| false | true | PS + offset mới; sau loss cần replay DW |
| true | false | Z mới; prefix PW durable vẫn là prefix cũ |
| true | true | Z + PS + offset mới |

Nếu checkpoint cũ có PS offset 16, runtime đã tính tới 32 nhưng policy mới
không giữ PS, record tiếp theo vẫn phải giữ **PS cũ và offset 16**. Không
ghép PS mới với offset cũ hoặc ngược lại. Bản G2 copy payload cũ sang slot
mới, tính cả read/write; không tạo reference chéo slot dễ bị ghi đè.

Sau reboot, restore Z/PS chỉ làm SRAM-valid sau read hoàn tất. Nếu restore
lại mất nguồn, boot tiếp tục đọc record cũ. Weight bank luôn phải nạp lại.

## 5. Capacity và giới hạn

Microtile: anchor 1024 B, DW weight+bias 832 B, PW weight+bias 272 B,
Z 256 B, PS 64 B, output 16 B. NVM reservation gồm immutable microtile
2128 B + hai slot 8192 B = **10320 B**; không bao gồm toàn bộ model blob.

Logical SRAM reservation là **6512 B** trong budget 8192 B: hai bank
1024 B, anchor/Z/PS/output, scratch INT32 bảo thủ `max(4*Z_bytes, PS_bytes)`,
2048 B cho metadata/controller và 32 B I/O scratch. Đây là layout giả định
của backend logic, không phải peak RSS của Python hoặc kết quả SRAM sizing
RTL. NumPy dùng temporaries trên PC; mạng đầy đủ/arena/scratch cần liveness
analysis riêng. Simulator từ chối cấu hình vượt các budget khai báo.

## 6. Bằng chứng hiện tại

Xem `10_Experiments/g2/unit_tests.txt` và `faults/summary.json`: kiểm tra
trước/sau publish, giữa payload/metadata, boot/restore bị ngắt, identity,
corruption, cold banks, replay và prefix cũ khác 0. Campaign bao phủ hữu hạn
các boundary của execution không lỗi và một số write interior; không chứng
minh mọi vị trí byte, mọi chuỗi fault, mọi descriptor hoặc toàn mạng.
