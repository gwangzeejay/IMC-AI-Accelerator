# Tái lập và audit RECAP-CIM — G8, 23/10/2026

## Hai thao tác khác nhau

- **Audit**: đọc artifact có sẵn, kiểm SHA-256, pairing, energy ledger, memory
  bounds và tính lại aggregate. Không gọi inference/RTL lại.
- **Fresh execution**: chạy Python model/runtime hoặc Icarus/Yosys thật, ghi
  evidence vào run-id mới. Không thay thế bằng việc chỉ đọc JSON.

`run_all.py` hiện là audit G7 cho G2–G6. Nó không nhận các flag `--skip-g3`,
`--skip-g4`... và không chạy lại pipeline. Hướng dẫn cũ đã chuyển sang
`docs/legacy/reproduce_full_pre_G8.md`, không dùng như lệnh hiện hành.

## 1. Workspace hiện tại: kiểm nhanh

```powershell
python 10_Experiments/run_tests.py
python 10_Experiments/check_project.py
```

Tests bao gồm G2, G3, G4 Python codec, G5, G6 và G8. Đây không phải toàn bộ
fault campaign G2–G6 hay Icarus campaign G4. `check_project.py` audit nguyên
bằng chứng G2–G6 và G8 hiện hành; mặc định không ghi lại report cũ.

Có thể chỉ kiểm G8 unit tests hoặc chỉ hash legacy:

```powershell
python 10_Experiments/run_tests.py --g8-only
python 10_Experiments/check_project.py --legacy-only
```

## 2. Chuẩn bị môi trường mới

Python hiện dùng 3.12.9. Tạo venv riêng và dùng dependency pins:

```powershell
python -m venv .venv-recap
.venv-recap\Scripts\python.exe -m pip install -r 10_Experiments/requirements-g8.txt
```

Cần model/reference/G2–G6 artifacts theo [hướng dẫn từng mốc](reproduce.md).
Đây là prerequisite đã có sẵn trong workspace; chưa có bootstrap một lệnh từ
một checkout rỗng. Không gọi thiết lập mới đó là clean-host replay đã đạt.
Không cần train lại model, FPGA, PDK hay EDA thương mại.

Lần đầu chuẩn bị phần bổ sung G8:

```powershell
python 10_Experiments/setup_g8_data.py
python 10_Experiments/setup_g4_tools.py
```

Lệnh dữ liệu tải 24 JPEG VWW mới theo label file đã pin, giữ ảnh và tensor
trong thư mục G8 riêng. Lệnh tools G4 tải toolchain khá lớn nếu chưa có.
Sau setup có thể chạy offline. Tôn trọng quyền tái phân phối ảnh COCO.

## 3. Chạy lại G8 toàn mạng

```powershell
python 10_Experiments/run_g8.py --run-id my-g8-rerun
```

Run gồm: kiểm legacy hashes; unit tests; development/operator equivalence;
sáu full-network directed faults; chọn interval B4 từ development; freeze
source/model/input/protocol; chạy 280 main rows và 120 secondary rows; ghi
manifest cuối cùng. Chính sách và dữ liệu không được sửa sau freeze.

Run-id đã tồn tại sẽ bị từ chối, kể cả đợt bị lỗi. Giữ lại log lỗi và dùng ID
mới. Không sửa JSON để ép PASS; lỗi kỹ thuật cần sửa mã, thêm regression và
công khai nếu đã nhìn thấy một phần kết quả. Chạy lại cùng protocol chỉ là
replay, không phải một holdout nghiên cứu độc lập mới.

## 4. Chạy RTL publisher

```powershell
python 10_Experiments/verify_g8_rtl.py --run-id my-rtl-rerun
```

Thực thi Icarus/VVP: 284 ACK-cut/stall cases, hai invalid commands; Python
độc lập decode CRC/output visibility. Yosys kiểm proc/opt/check và lưu netlist
JSON. Generic cell count không phải diện tích chip, LUT count hoặc fmax.

## 5. Audit run mới

```powershell
python 10_Experiments/check_project.py --run-id my-g8-rerun --rtl-run-id my-rtl-rerun
```

Kỳ vọng: legacy 2.769 hash entries khớp, G8 main đủ 280 hàng, 40 aggregate
cells khớp; nguồn/dữ liệu đúng freeze; không có output scratch writes ở main;
energy conservation và memory bounds đạt. Case không hoàn thành giữ nguyên;
energy/commit có thể null và unconditional p95 có thể vô hạn.

Artifact chính: `protocol.json`, `development.json`, `faults.json`,
`equivalence.json`, `input_splits.json`, `scenarios.json`, `freeze.json`,
`main.jsonl`, `secondary.jsonl`, `results.json`, `manifest.json`.

## 6. G2–G6 và giới hạn tái lập

Giữ nguyên runners và bằng chứng các mốc trong [reproduce.md](reproduce.md).
Nếu muốn fresh replay G2–G6, dùng một bản sao workspace riêng để các runner
legacy không ghi đè bằng chứng gốc. Manifest mới có thể khác timestamp và host
profiling; cần so scientific metrics và phân biệt thay đổi hợp lệ với lỗi.
G8 chưa chứng minh toàn pipeline chạy được trên một máy sạch khác.
