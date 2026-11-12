# RECAP-CIM: phục hồi suy luận TinyML trên SRAM-CIM dễ mất dữ liệu

**Trạng thái hiện hành: G8 — 23/10/2026.** Project nghiên cứu trên máy tính,
bao gồm mô phỏng KWS/VWW INT8 và kiểm chứng các khối RTL. Người thực hiện chưa
có board, lab hoặc EDA thương mại. Năng lượng vẫn dùng hệ số giả định; chưa có
số đo chip, full-network accelerator RTL hay kết luận đạt mục tiêu giảm 20%.

Bản README cũ với các con số 8×, TOPS/W và tape-out chưa xác minh đã chuyển
sang [tài liệu lịch sử](docs/legacy/README_pre_G8.md). Những số đó không phải
kết quả của project hiện hành.

## Đọc trước

- [Những gì đã cải thiện, kết quả và việc còn lại](02_Research/G8_deliverables.md).
- [Đặc tả thuật toán, durability và phạm vi RTL](03_Architecture/g8_recovery_spec.md).
- [Tính mới, baseline và giới hạn cost model](02_Research/G8_prior_art_and_cost_scope.md).
- [Bạn cần làm gì khi chưa có phần cứng](06_FPGA/HARDWARE_ROADMAP.md).
- [Hướng dẫn tái lập](10_Experiments/reproduce_full.md).

## Các thay đổi G8

1. Thêm ranking có expected redo; expectation chỉ dùng để chọn phương án,
   ledger vẫn tính công việc thực thi. Có kiểm tra độc lập bằng hệ tuyến tính.
2. Bỏ bước scratch-output trung gian; mọi policy G8 dùng cùng đường publish
   output vào durable log. Các slot lưu DW/partial sum vẫn giữ cơ chế COW.
3. Thêm reset tại thời điểm tuyệt đối giống nhau cho mọi policy, đồng thời
   kiểm mapper không xem trước nguồn hoặc lịch reset.
4. So năm policy: B1_layer, B3_adaptive, B4_periodic, RECAP_nominal,
   RECAP_redo. B4 là control periodic nội bộ, chưa phải tái hiện thuật toán
   tối ưu Chime/CIM-Tuner.
5. Dùng source/reset seeds mới và pool input tách khỏi runtime G5/G6; VWW
   thêm 24 ảnh. Có tách development/holdout và source freeze trước main run.
6. Thêm publisher RTL độc lập, kiểm byte-cut/stall và generic synthesis.

## Chạy nhanh trong workspace đã có dữ liệu

```powershell
python 10_Experiments/run_tests.py
python 10_Experiments/check_project.py
```

Lệnh đầu thực thi các unit test. Lệnh sau chỉ kiểm hash và tính lại tổng hợp
của bằng chứng đã lưu; không chạy lại toàn bộ inference hay RTL.

Chạy thí nghiệm hoặc RTL mới, bắt buộc dùng run-id chưa tồn tại:

```powershell
python 10_Experiments/run_g8.py --run-id my-g8-rerun
python 10_Experiments/verify_g8_rtl.py --run-id my-rtl-rerun
python 10_Experiments/check_project.py --run-id my-g8-rerun --rtl-run-id my-rtl-rerun
```

Python dependencies: [requirements-g8.txt](10_Experiments/requirements-g8.txt).
Icarus/Yosys đã được pin trong tool setup G4; không cần FPGA/PDK để kiểm RTL.
Đừng cài đè môi trường đang dùng để tái lập; tạo venv riêng nếu cần.

## Bằng chứng và giới hạn

[CURRENT.json](10_Experiments/g8/CURRENT.json) chỉ tới đợt hiện hành.
G2–G6 và manifest gốc được giữ nguyên. Các đợt lỗi/superseded được gắn nhãn,
không được cộng vào số thí nghiệm thành công.

G6 ghi nhận KWS giảm model energy/commit 1,368% so baseline thích nghi và VWW
xấp xỉ 0%; chưa đạt 20%. G8 có protocol và đường publish mới nên phải dùng kết
quả G8 riêng, không lấy hai bảng khác protocol để tính phần trăm before/after.

Bộ nhớ 64 KiB SRAM / 2 MiB NVM là budget mô hình. Chưa chứng minh CPU runtime
thực vừa budget này. CPU head reference và sensing/preprocessing exclusions
được giữ nguyên. Kiểm chứng RTL hiện chỉ cho các khối được nêu trong báo cáo,
không phải toàn mạng hoặc formal proof.

## Cấu trúc hiện hành

| Thư mục | Nội dung |
|---|---|
| `02_Research` | Deliverables, prior-art gaps, phạm vi bằng chứng |
| `03_Architecture` | Đặc tả G2–G8 và hợp đồng lưu/khôi phục |
| `04_RTL/g4`, `04_RTL/g8` | Controller/số học đã kiểm và publisher mới |
| `09_Simulation` | Integer kernels, models, runtime, tests |
| `10_Experiments` | Protocol, runner, dữ liệu thô, freeze và audit |
| `06_FPGA` | Lộ trình phần cứng; flow OOC tùy chọn chưa chạy |
| `07_IEEE_Paper/g7` | Bản thảo lịch sử G7; chưa đủ điều kiện nộp |
| `docs/legacy`, `08_ASIC` | Tài liệu/flow tham khảo, không là bằng chứng triển khai vật lý |

Hoàn thiện phần mềm không đồng nghĩa chứng minh tính mới hoặc hiệu quả phần
cứng. Mọi claim công bố phải theo đúng kết quả, phạm vi và nguồn hỗ trợ.
