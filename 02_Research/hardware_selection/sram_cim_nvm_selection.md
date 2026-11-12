# G1 hardware selection — SRAM-CIM và NVM

**Phiên bản:** 1.3; **ngày:** 15/10/2026; **trạng thái:** ứng viên đã rà soát, chưa chốt backend chính.

## 1. Quyết định hiện tại

Plan v3.2 ưu tiên digital SRAM-CIM, INT8 reference/INT32 accumulation và khôi phục bit-exact. Chưa có đủ dữ liệu để nghiệm thu một macro thỏa đầy đủ yêu cầu đó. TDC-CiM giữ ở danh sách tham khảo/mixed-signal extension; không tự đổi hướng nghiên cứu để khớp một con số TOPS/W.

### 1.1 TDC-CiM — số liệu có phạm vi

Nguồn: [S5, bản tác giả v1](https://arxiv.org/html/2601.00434v1), năm arXiv 2026. **Reported post-layout simulations**, không phải phép đo của dự án.

| Trường | Điều kiểm tra được | Vị trí |
|---|---|---|
| Cơ chế | Charge/time-domain với TDC; mixed-signal | §§II, III-A |
| Precision | Input/weight 8/8; hai chu kỳ phần 4-bit được mô tả | §IV-E |
| Geometry minh họa | 256×256 bitcells → 8 KiB vật lý | §III-A |
| Cấu hình performance | 512×256 bitcells → 16 KiB; 28 nm, 1 V, 0.5 GHz | §IV-E, Table III |
| Performance cấu hình trên | 320 GOPS; 38.46 TOPS/W, macro scope | Table III |
| Nạp weight | Có mapping/update path; chưa trích được energy/byte và update bandwidth đủ dùng | §III-E; còn thiếu |
| Exact arithmetic | Accuracy software/hardware không hoàn toàn giống ở các model | Table II; không phải bằng chứng bit-exact |

Không gắn geometry 1024×1304 hoặc “1 cycle/MAC” cũ vào paper. Không trộn cấu hình 8 KiB trong abstract với performance 16 KiB. Digital readout không biến cả datapath thành digital exact arithmetic.

### 1.2 Chuẩn hóa TOPS/W

Với efficiency `eta` TOPS/W và quy ước `k` operations/MAC:

\[
E_{op,pJ}=1/\eta,\qquad E_{MAC,pJ}=k/\eta.
\]

Nếu `eta = 38.46`, thì `E_op ≈ 0.026001 pJ`; **chỉ khi k=2**, `E_MAC ≈ 0.052002 pJ`. Con số 0.026 pJ/MAC cũ đã bỏ qua quy ước đếm. Giữ `operations_per_mac = null` cho tới khi kiểm tra được nguồn; không dùng phép đổi điều kiện này như calibration end-to-end. Peak efficiency cũng không thay thế utilization, update cost, controller và external NVM.

### 1.3 Các ứng viên khác

| Nguồn | Vai trò hợp lý | Điều kiện còn thiếu |
|---|---|---|
| CIM-Tuner 2026, S4 | Mapping model/implementation tham khảo; có AL/PC/SCR/ICW/WUW | Cần chọn macro digital cụ thể, đọc config và kiểm tra update energy; công cụ không phải một macro |
| FERMI-ML 2025, S7 | Digital multi-precision candidate | Kiểm tra approximation/exact INT8 và cost theo precision; không loại chỉ vì XNOR |
| PSCNN 2022, S8 | Prior art SRAM-CIM KWS | Binary workload; không dùng số efficiency như INT8 |
| Các mục “CIMAT/NeuEPU/Conv-SRAM” cũ | Chưa dùng trong active parameter set | Metadata và danh tính chưa đủ tin cậy; xem audit/quarantine |

**Acceptance macro chính:** có arithmetic semantics phù hợp, compute/update bandwidth, weight load path, capacity/layout, cost source và những trường chưa biết được chỉ rõ. Nếu chỉ dùng architecture model giả định, phải gắn nhãn assumed và giới hạn claim theo sensitivity.

## 2. NVM candidate cụ thể: Infineon FM25V20A

Nguồn: [S10, datasheet 001-90261 Rev. *J, 22/12/2023](https://www.infineon.com/dgdl/Infineon-FM25V20A_2-Mbit_(256_K_X_8)_Serial_(SPI)_F-RAM-DataSheet-v10_00-EN.pdf?fileId=8ac78c8c7d0d8da4017d0ec93a4341a5). Bản PDF gốc và SHA-256 có trong source manifest.

| Tham số | Giá trị/điều kiện | Vị trí |
|---|---|---|
| Capacity | 2 Mbit = 262144 bytes = 256 KiB | Datasheet tên/organization |
| SPI | Tối đa 40 MHz; 3-byte address | §5, timing tables |
| VDD | 2.0–3.6 V; typical point 3.3 V | Table 11, tr. 19 |
| Active current | 2.4 mA typ / 3 mA max tại 40 MHz, SO open | Table 11, tr. 19 |
| Standby/sleep | 100 µA / 3 µA typ, 25°C | Table 11 |
| Access | Byte-stream; WREN trước WRITE; không có page-program delay | §5.1, tr. 14 |
| Endurance | 10^14 read/write accesses, theo row accounting | §5.6, tr. 16 |
| Power state | Cold access delay ≥1 ms; sleep recovery ≤450 µs | Table 17, tr. 25 |

Đây là **reported datasheet parameters**, không phải phép đo board của dự án. Capacity không phải 8 MB. Byte-addressability không đồng nghĩa giao dịch 64 byte là nguyên tử khi brownout; G2 phải kiểm tra power sequencing, slot invalidation, atomic marker và ordering phù hợp datasheet.

### 2.1 Cost theo transaction, không gán tùy ý pJ/byte

Chọn điểm tính toán minh họa 3.3 V/40 MHz; B là payload bytes. READ opcode + address chiếm 4 byte; WRITE cộng WREN riêng nên 5 byte, chưa tính CS gaps, wake-up và master overhead:

\[
t_{read}=8(B+4)/f_{SPI},\quad t_{write}=8(B+5)/f_{SPI},\quad E_{chip}=V I_{active}t.
\]

Từ typical current, streaming asymptote là **1.584 nJ/payload byte**, không phải 10/30 pJ. Dùng 3 mA tại cùng điểm điện áp cho một upper-current scenario cho **1.98 nJ/byte**; không gọi typical là giới hạn dưới hoặc đây là full-system upper bound.

Với B=8192, mô hình chip-only ở trên cho READ khoảng **12.982464 µJ**, WRITE khoảng **12.984048 µJ**. Đây là **derived illustration**, chưa gồm controller/SPI IO, regulator, CS gaps hoặc wake-up. Không gán hai số read/write độc lập để giả định FRAM luôn rẻ ghi; so riêng current theo datasheet nếu có.

Standby ở typical point đã khoảng 330 µW, sleep khoảng 9.9 µW. Policy sleep/power-gating và chi phí wake-up phải nằm trong mô phỏng năng lượng. IO load trong hệ thống thật khác điều kiện SO-open có thể tăng tiêu thụ.

### 2.2 Kiểm tra dung lượng và checkpoint

- Chưa khóa model MLPerf Tiny/commit: không giữ các số weight=256 KiB, MAC=826000 hoặc checkpoint=8 KiB như đặc tính benchmark.
- Extract weight/bias/quantization tensors, input và live activation/PS footprint từ model thật.
- Bố trí model + input/anchor + hai checkpoint slots + metadata/output phải vừa 256 KiB; nếu không, chọn NVM khác có nguồn hoặc quy định streaming/storage bổ sung.
- Byte ghi xong và nguồn đáp ứng điều kiện datasheet là căn cứ cho thiết kế; không nhận toàn bộ payload atomically durable chỉ vì nó vừa được gửi qua SPI.

## 3. Tham số đã loại khỏi cấu hình dùng được

Các giá trị cũ 10 pJ/read-byte, 30 pJ/write-byte, 8 MB FRAM, 64-byte atomic write, load 100 ns, 1 cycle/MAC, 256 KiB model, boot 5 µJ và “10 µJ KWS” **không còn là nominal parameters**. Bản gốc được backup; chưa có data/calibration để thay các trường thiếu bằng một con số chính xác.

[research_parameters.json](research_parameters.json) dùng `null` và status cho dữ liệu thiếu. `ready_for_energy_results = false` là có chủ ý. Sensitivity axes phải lấy theo part/profile và từng energy domain; chưa có kết quả sweep trong lần rà soát này.

## 4. Những việc để hoàn tất hardware part của G1

- [ ] Chọn macro/backend chính đúng yêu cầu digital/bit-exact hoặc giới hạn mô hình kiến trúc giả định có căn cứ.
- [ ] Chốt update bandwidth và energy, loading granularity, sign/accumulator/overflow semantics.
- [ ] Chốt model/commit/hash và memory layout kiểm tra capacity.
- [ ] Chốt NVM voltage/frequency, sleep/boot/IO model, persistence protocol và transaction gaps.
- [ ] Chỉ sau đó mới tạo nominal executable simulator configuration; giữ assumed và reported tách riêng.
