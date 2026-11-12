# G4 — RTL controller, fault tests và transaction refinement

Ngày: **15/10/2026**. Trạng thái: **G4_RTL_SIMULATION_VALIDATED** trong phạm
vi microtile. Đã hiện thực protocol bằng RTL và kiểm tra correctness/fault
invariants. Chưa là accelerator đầy đủ, chưa có PPA hoặc calibration năng
lượng phần cứng. Các điều kiện còn thiếu của G1/G2 giữ nguyên.

## 1. Kết quả thực thi

| Hạng mục | Kết quả đã chạy |
|---|---|
| Controller RTL | Hai slots, full identity, CRC, PS+offset recovery, atomic publish và output frontier |
| Model-backed fixtures | G2 2×2/CO4 và G3 spatial tile 1×2/CO16; giữ số học của golden MLPerf Tiny |
| Main protocol suite CI16 | 1.856 ca: 20 baseline/invalid-command, 1.820 fault, 16 directed integrity/recovery cases |
| CI64/output-only supplement | 26 ca, gồm 10 fault cases; đúng execution chunk của mapping đã chọn ở G3 |
| **Tổng controller RTL cases** | **1.882**, trong đó **1.830 fault cases**, **2.844 lần mất nguồn thực thi** |
| Byte-level cross-check | **6.415.721 acknowledged NVM byte transactions** khớp Python wire simulator, không mismatch; pending writes cũng được kiểm riêng |
| Cycle-level cross-check | **8.317 commits** khớp công thức latency gồm stall, không mismatch |
| Scalar arithmetic RTL | **647 MAC cases + 5.468 requant cases** đạt, gồm dữ liệu model thật và overflow/rounding edges |
| Python codec checks | **10 tests** đạt |
| Generic Yosys check | MAC, requant và reduced controller qua `proc/opt/memory_collect/check -assert` |

Sáu ca trong controller suite cố ý yêu cầu fail closed: invalid prefix,
generation wrap hoặc orphan frontier. Chúng đạt khi RTL từ chối đúng;
không coi là sáu inference đã hoàn tất. Mọi ca output thành công so đủ
tensor INT8, không chỉ label. Fault coverage hữu hạn, không phải chứng minh
mọi byte/chuỗi power failures.

## 2. Những gì mới được hiện thực

- `recap_checkpoint_ctrl.sv`: chỉ promote generation/offset sau marker đã
  persistence ACK; copy-on-write vào inactive slot; phục hồi từ bytes NVM
  thật; giữ PS cũ offset 16 khi volatile đã tới 32 nhưng không giữ PS mới.
- `recap_int8_mac.sv`: signed zero-point adjustment, accumulator overflow
  detection, counter chứa được giá trị 256. Không nhận đây là macro CIM.
- `recap_requantize.sv`: integer two-rounding, saturation/activation và
  shift guard; đối chiếu với real-model tensors và seeded vectors.
- Testbench có arbitrary bounded memory stalls, restore backpressure,
  cold loss trước/sau ACK, pending write persistent hoặc không persistent,
  boot/restore bị ngắt lần nữa và output/frontier publication boundaries.
- Python oracle tự tạo binary metadata/transaction từ command và golden;
  kiểm tra read/write/restore bytes và durable output sau từng execution.

Chi tiết interface, assumptions và FSM tại
[g4_rtl_spec.md](../03_Architecture/g4_rtl_spec.md).

## 3. Lỗi đã phát hiện và sửa

Trong RTL requantization mới, trộn kết quả comparison unsigned vào biểu
thức có `>>>` làm số âm bị dịch logical trong ngữ cảnh 64 bit. Real-model
vector đầu tiên đã bắt lỗi: output bị saturate dương thay vì âm.

Đã tách arithmetic shift khỏi comparison/increment và sign-extend zero
point rõ ràng; chạy lại toàn bộ arithmetic vectors đạt. Bộ vectors giữ
ca âm/half-rounding/left-shift overflow để chống tái diễn.

RTL legacy không được dùng để nhận kết quả G4. MAC mới có test 255/256
terms; không dùng bộ đếm địa chỉ 8 bit để so trực tiếp với 256 bị cắt về 0.

## 4. Ý nghĩa và ranh giới của đối chiếu simulator

G2/G3 lưu JSON metadata và SHA-256; G4 dùng header binary-v1 **124 B**,
CRC32 và ba full 256-bit identities. Thay representation để RTL có định
dạng hữu hạn, kiểm tra **cùng durable prefix/payload và ordering**.

Vì header/bus/granularity đã khác, G4 **không xác nhận lại tỷ lệ giảm
22,09% năng lượng G3**. Trước khi đo overhead trong G5 phải đưa codec/
traffic/controller cycles mới vào simulator và fit cost có nguồn.

Cycle equation đã đối chiếu:

```text
commit_cycles = 2*payload_bytes + 246 + is_output + bus_stall_cycles
```

Đây chỉ là protocol commit latency. Zero-stall output commit: 279 cycles
cho output 16 B, 311 cycles cho output 32 B. Chưa gồm DW/PW/weight/input
traffic hay charging; không chuyển thành throughput chip hoặc joule.

Backend DW–PW functional trong testbench tự tính từ input/weights/quant
parameters, nhưng chưa là datapath pipeline tích hợp với scalar cores.
Input/weight ROM reads của backend chưa đi qua NVM controller này. Do đó
G4 xác minh checkpoint/recovery traffic, không phải mọi event ledger G3.

## 5. Synthesis: bằng chứng đạt và phần chưa đạt

Tools được lấy từ [OSS CAD Suite snapshot 2026-10-14](https://github.com/YosysHQ/oss-cad-suite-build/releases/tag/2026-10-14),
có archive digest và local executable hashes trong manifest. Thực thi
Icarus/VVP 14.0 development snapshot và Yosys 0.70+16 theo version logs;
không chỉ lint hoặc mô phỏng lại bằng Python.

Yosys generic process/memory checks đạt:

| Module | Cấu hình | Generic cells sau passes đã chạy |
|---|---|---:|
| MAC | MAX_TERMS=256 | 51 |
| Requantization | Mặc định | 45 |
| Controller | Reduced Z4/PS4/OUT1/C4/SLOT160 | 49.593 |

Generic cells là các toán tử/mux/register/memory representation của Yosys,
không phải số standard cells công nghệ. Controller reduced vẫn tạo nhiều
decode/equality logic; đây là dấu hiệu cần tối ưu memory/parser, không
phải bằng chứng area tốt.

**Full-size controller generic check timeout ở 180 s, chưa đạt.** Chưa có
technology mapping, standard-cell library, P&R, timing closure, FPGA run,
power characterization hoặc formal proof. `area_mm2`, `power_w`,
`frequency_hz` tiếp tục `null`.

## 6. Giả định còn phải kiểm chứng

- Marker/frontier byte atomic old-or-new; persistence ACK đúng hợp đồng;
  không reordered/late writes sau reset. Chưa xác nhận trên FM25V20A thật.
- IDs/config ổn định trong một invocation. Generation wrap bị từ chối;
  chưa có migration/reclamation production protocol.
- CRC collision, mọi bit corruption và mọi sequence vô hạn không được
  bao phủ bởi campaign; bounded faults không chứng minh liveness vô điều kiện.
- SRAM payload port combinational, NVM byte port một outstanding request;
  driver SPI, burst timings, DMA, admission hardware và multi-input runtime
  chưa nằm trong controller đã kiểm tra.

**G4 đạt ở mức RTL microtile correctness/transaction refinement.** G5 cần
tích hợp runtime/descriptor addressing, input+weight transfers và scalar
backend, đồng bộ binary codec vào simulator, bổ sung baseline mạnh và
đánh giá lại overhead. Không mở claim PPA/energy từ các số debug hiện tại.

## 7. Tái lập và artifacts

Sau khi có local tools:

```powershell
python 10_Experiments/run_g4.py
```

Lệnh chạy lại thật các RTL simulations, arithmetic/unit tests, independent
oracle và reduced generic Yosys checks. Có thể mất vài phút. Môi trường
Windows, Python 3.12.9, NumPy 2.2.4; không cần FPGA/EDA thương mại.

Nếu máy chưa có tools, setup một lần có mạng:

```powershell
python 10_Experiments/setup_g4_tools.py
```

Gói nguồn khoảng 575 MiB, chỉ extract runtime cần dùng trong `tmp/g4_tools`.
DLL runtime có bản sao ở thư mục Temp tên ASCII để xử lý đường dẫn Unicode
Windows; không sửa registry hoặc global PATH. `PATH` chỉ đặt cho subprocess.

Đợt này đã chạy suites trực tiếp bằng các helper và lưu logs; sau đó
`run_g4.py --collect-existing` kiểm source bindings/recorded execution
evidence và đóng manifest, tránh lặp lại campaign đã đạt. Collect mode
không có nghĩa rerun RTL; manifest ghi rõ điều này. Default command ở trên
luôn thực hiện lại suites. `--full-controller` yêu cầu thêm full-size
generic attempt có timeout, không hứa synthesis/PPA sẽ đạt.

- [Summary](../10_Experiments/g4/summary.json), [main RTL report](../10_Experiments/g4/rtl_summary.json), [CI64 supplement](../10_Experiments/g4/whole_unit_summary.json).
- [Arithmetic log](../10_Experiments/g4/logs/arithmetic.log), [unit log](../10_Experiments/g4/unit_tests.txt), [synthesis summary](../10_Experiments/g4/synthesis_summary.json).
- [Run manifest](../10_Experiments/manifests/g4_run.json), raw traces và per-suite reports tại `10_Experiments/g4/`.
- Trace fault lớn được losslessly gzip sau khi cross-check; plain baseline/
  directed traces giữ lại để review. Generated CI64 driver variant được lưu
  cùng build sources; controller giống bản CI16.
- [Backup các tài liệu trước G4](./_backups/before_G4_2026-10-15/manifest.json).
