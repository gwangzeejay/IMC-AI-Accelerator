# Tái lập toàn bộ G2-G6 từ một lệnh

## Mục đích

Script `10_Experiments/run_all.py` chạy lại toàn bộ pipeline từ G2 đến G6
mà **không cần network, không modify frozen manifests**. Mỗi stage chạy
tuần tự và verify trạng thái trước khi sang stage tiếp theo.

## Chuẩn bị một lần

Trước lần đầu chạy, cần setup:

```powershell
# 1. Tạo virtual environment
python -m venv .venv-recap
.venv-recap\Scripts\python.exe -m pip install -r 10_Experiments/requirements-g2.txt

# 2. Tải model, dataset, ETH source (chỉ cần làm một lần)
.venv-recap\Scripts\python.exe 10_Experiments/setup_g5_data.py
.venv-recap\Scripts\python.exe 10_Experiments/setup_g6_sources.py
```

G4 cần iverilog + yosys (OSS CAD Suite), setup riêng:

```powershell
.venv-recap\Scripts\python.exe 10_Experiments/setup_g4_tools.py
```

## Chạy toàn bộ

```powershell
.venv-recap\Scripts\python.exe 10_Experiments/run_all.py
```

Script sẽ in manifest status, chạy G2 → G3 → G4 → G5 → G6 tuần tự, và ghi
tổng kết vào `10_Experiments/g7_reproduce/reproduce_summary.json`.

## Tuỳ chọn

| Flag | Tác dụng |
|------|----------|
| `--skip-reference` | G2 dùng golden đã export, không chạy TFLite interpreter |
| `--skip-g3` | Bỏ qua G3 |
| `--skip-g4` | Bỏ qua G4 (khi không có iverilog/yosys) |
| `--skip-g5` | Bỏ qua G5 (khi chưa có EEMBC) |
| `--skip-g6` | Bỏ qua G6 (khi chưa có ETH source) |
| `--output-dir PATH` | Thay đổi nơi ghi summary |

Ví dụ chạy nhanh chỉ G2+G3:

```powershell
.venv-recap\Scripts\python.exe 10_Experiments/run_all.py --skip-g4 --skip-g5 --skip-g6
```

## Kết quả mong đợi

| Stage | Thời gian (PC thường) | Status |
|-------|------------------------|--------|
| G2 | ~30-60 s | `PASS_DEBUG_PROFILE`, 3099 fault cases |
| G3 | ~80-120 s | `MODEL_ONLY_G3_COMPLETED`, 4112 fault cases |
| G4 | ~10-30 phút (nếu có tools) | 1882 cases pass |
| G5 | ~2-5 phút | 901/1000 accuracy, 108 runs |
| G6 | ~25-40 phút | 1216 case artifacts |

Tổng (G2+G3+G5+G6, không G4): ~30-50 phút. Với G4: ~45-90 phút.

## Kiểm tra sau khi chạy

1. `10_Experiments/g7_reproduce/reproduce_summary.json` phải có:
   - `all_passed: true`
   - `frozen_protocol_preserved: true`
   - Mỗi stage có `duration_s`
2. `10_Experiments/manifests/g{2,3,4,5,6}_run.json` phải parse được
3. So sánh số liệu với deliverables:
   - G2: 3099 fault cases, 0 mismatch
   - G3: 4112 fault cases, 0 mismatch, 22.09% reduction point estimate
   - G5: 901/1000 accuracy, RECAP = B3 (0% reduction)
   - G6: 1216 case files, 1.368% KWS reduction

## Không chạy lại những gì

- **Không rerun training** (model đã pin, không fine-tune)
- **Không refit policy** trên test data
- **Không đổi frozen source/manifest** ở bất kỳ stage nào
- **Không tune cost coefficients** để làm số đẹp hơn

## Số liệu cố định (snapshot)

| Metric | Giá trị đã chạy | File |
|--------|------------------|------|
| G2 fault cases | 3.099 | g2/faults/summary.json |
| G2 mismatches | 0 | g2/faults/summary.json |
| G3 reduction | 22,09% | g3/summary.json |
| G3 fault cases | 4.112 | g3/faults/summary.json |
| G4 RTL cases | 1.882 | g4/rtl_summary.json |
| G4 NVM byte transactions | 6.415.721 | g4/rtl_summary.json |
| G5 KWS accuracy | 90,1% (901/1000) | g5/accuracy.json |
| G5 RECAP-B3 reduction | 0% (CI [0%; 0%]) | g5/results.json |
| G6 case artifacts | 1.216 | g6/summary.json |
| G6 KWS reduction | 1,368% (CI [0,126%; 3,504%]) | g6/results.json |
| G6 VWW reduction | ≈0% | g6/results.json |

## Troubleshooting

**`UnicodeEncodeError` trên Windows console:**

```powershell
$env:PYTHONIOENCODING = "utf-8"
python 10_Experiments/run_all.py
```

**G4 bị skip vì thiếu iverilog:**

```text
[G7] G4: tool iverilog not found, skipping
```

Chạy `python 10_Experiments/setup_g4_tools.py` để tải OSS CAD Suite.

**G5/G6 fail vì thiếu dataset:**

```text
FileNotFoundError: ... source_manifest.json ...
```

Chạy `python 10_Experiments/setup_g5_data.py` và `setup_g6_sources.py`.

**Verification mismatch:**

Nếu số liệu sau khi rerun khác snapshot trên, **không tự động cập nhật**;
kiểm tra lại frozen protocol, host timing, NumPy version, rồi báo cáo.
