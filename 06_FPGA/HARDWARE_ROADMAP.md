# Lộ trình phần cứng và phương án khi chỉ có máy tính

Ngày 23/10/2026: người thực hiện xác nhận **không có board và không có quyền
tiếp cận lab/EDA**. Phạm vi nghiệm thu hiện tại là nghiên cứu mô phỏng và RTL
trên máy tính. Không cần mua phần cứng để chạy hoặc kiểm tra G8.

## Bạn có thể làm ngay, không cần board

1. Chạy `python 10_Experiments/run_tests.py` và
   `python 10_Experiments/check_project.py`; đọc rõ khác biệt tests và audit.
2. Chạy lại Icarus/Yosys cho publisher bằng `verify_g8_rtl.py` với run-id mới.
   Đây là thực thi RTL trên máy, không phải triển khai trên FPGA.
3. Đọc waveform nếu cần, kiểm các trạng thái invalidate/payload/header/publish,
   giải thích vì sao reset trước marker không tạo output hợp lệ.
4. Tiếp tục benchmark thuật toán, baseline và khảo sát paper. Có thể viết một
   đồ án/nghiên cứu giới hạn ở mô phỏng, với các giả định công khai.

## Khi sau này có thể hợp tác với một phòng lab

| Bước | Việc cần làm | Bằng chứng cần giữ |
|---|---|---|
| 1. Chốt cấu hình | Xác định board/chip, điện áp, clock, SRAM/NVM, công cụ có quyền sử dụng | Mã linh kiện, tài liệu, version tool, sơ đồ rail |
| 2. Kiểm tài nguyên | Ánh xạ controller và datapath, xem RAM có suy luận đúng, đo arena của runtime thực | Netlist, utilization, timing, linker map/arena peak |
| 3. NVM adapter | Thêm SPI/controller; chỉ ACK khi đáp ứng hợp đồng persistence; xử lý CS/reset/power-up | RTL/firmware adapter, trace SPI, test transaction |
| 4. Kiểm mất nguồn | Ngắt nguồn tại nhiều thời điểm ghi, đọc lại output/checkpoint và so golden INT8 | Seed/timestamp reset, raw NVM dump, mismatch count |
| 5. Đo năng lượng | Đo V(t), I(t) cùng GPIO đánh dấu boot/load/compute/write; tích phân trong cùng ranh giới | Raw CSV, sample rate, shunt/gain calibration, uncertainty |
| 6. Calibrate | Điền template cost theo đúng điện áp/clock, gồm boot, controller, standby và converter | Profile có nguồn và phép suy ra, validation trên trace khác |
| 7. So sánh lại | Cùng input, arrival/deadline, nguồn, memory budget và đường publish cho mọi policy | Completion, on-time, energy/commit, CI và ca thất bại |

Không cần triển khai toàn mạng ngay: bắt đầu bằng một tile DW/PW thật và
publisher, kiểm output đúng và phục hồi đúng trước khi mở rộng.

## Những giới hạn phải hiểu trước khi chọn thiết bị

- FPGA dùng RAM/DSP/logic thông thường có thể kiểm controller và dataflow;
  kết quả đó không đo năng lượng của một macro SRAM-CIM vật lý.
- G8 giả định 64 KiB SRAM và 2 MiB NVM. Một FM25V20A-G chỉ có 256 KiB theo
  [trang nhà sản xuất](https://www.infineon.com/part/FM25V20A-G). Cần tính lại
  layout nếu dùng cấu hình khác; không mặc định VWW sẽ vừa.
- File pin XDC legacy chưa phải sơ đồ chân của một board được chọn. Không
  dùng nó làm bản nối dây; chỉ lập pin constraints khi đã có board cụ thể.
- Ngắt riêng FPGA core trong khi giữ NVM và power-cycle toàn hệ thống là hai
  phép kiểm khác nhau. Cần mô tả rail nào bị ngắt và NVM nằm ở rail nào.
- Tham số RAM và cách đọc/ghi ảnh hưởng suy luận bộ nhớ trong synthesis;
  đối chiếu [AMD UG901](https://docs.amd.com/r/en-US/ug901-vivado-synthesis/RAM-HDL-Coding-Techniques)
  khi có Vivado. Script `g8/synth_publisher.tcl` chỉ là flow OOC tùy chọn,
  **chưa chạy** và chưa có kết quả timing/utilization của FPGA.
- `report_power` là ước lượng công cụ. Nếu dùng, cần hoạt động chuyển mạch
  phù hợp như SAIF theo [AMD UG907](https://docs.amd.com/r/en-US/ug907-vivado-power-analysis-optimization/Switching-Tab);
  vẫn ghi tách biệt với số đo dòng điện trên thiết bị.

## ASIC / chip SRAM-CIM thật

Đây là nhánh nghiên cứu về sau, không phải yêu cầu để hoàn thành đồ án trên máy.
Cần quyền dùng PDK, macro SRAM-CIM phù hợp INT8, thư viện chuẩn, NVM/IO,
synthesis/STA/power, physical design và sign-off. Các script legacy ở `08_ASIC`
là tài liệu tham khảo chưa nghiệm thu; không có GDS, DRC/LVS, PPA hay tape-out
đã xác minh. Nếu không có lab, giữ nhánh này là giới hạn công khai và tìm
hợp tác khi có điều kiện, không tự ghi các số mô phỏng thành số đo chip.

## Phần bạn cần trực tiếp thực hiện

Hiện tại: chạy lại một run-id riêng, hiểu state machine và ledger, tự giải
thích một ca lỗi/ca thua, bổ sung baseline/literature và nhờ giảng viên hoặc
người có kinh nghiệm review. Nếu sau này có lab, các phép nối mạch, đo rail,
power-cycle và kiểm điều kiện datasheet phải được thực hiện trên thiết bị;
những việc đó chưa thể thay bằng thao tác trong workspace.
