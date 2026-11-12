# G1: Kiểm tra deliverables và trạng thái nghiệm thu

**Phiên bản:** 1.3 — rà soát nguồn ngày 15/10/2026

**Trạng thái G1: PARTIAL / CHƯA ĐỦ ĐIỀU KIỆN ĐÓNG MỐC.**

Đối chiếu với plan v3.3 (giữ tiêu chí kỹ thuật từ v3.2): G1 yêu cầu khác biệt kỹ thuật có dẫn chứng, baseline gần nhất và cấu hình SRAM-CIM/NVM có dữ liệu hoặc miền giả định được giải thích. Việc có file hoặc tìm được abstract không đồng nghĩa đã xác minh nội dung hay qua G1.

## 1. Những gì đã thực hiện

| Deliverable | Có artifact | Kết quả rà soát | Trạng thái |
|---|---|---|---|
| Novelty matrix | Có | Có danh sách công trình và giả thuyết; các nhãn “xác nhận mới” cũ vượt bằng chứng | Đã sửa thành matrix có mức bằng chứng; chưa xác nhận novelty |
| Hardware shortlist | Có | Tìm được TDC-CiM/CIM-Tuner và các công trình khác; cần phân biệt backend, precision và phạm vi số liệu | Có shortlist; chưa chọn macro digital INT8 đáp ứng plan |
| NVM | Ban đầu mới có tên công nghệ | Số pJ/byte cũ thiếu part number/datasheet | Đã bổ sung ứng viên FM25V20A và mô hình transaction có nguồn; chưa phải cấu hình cuối |
| References | Có | Trùng citation keys, tác giả placeholder, metadata sai và lẫn danh tính công trình | Đã chuẩn hóa active bibliography; mục chưa xác minh chuyển sang danh sách loại trừ |
| Baselines | Có danh sách dự kiến | B1/B2/B3 cũ không cùng nghĩa với plan | Đã đồng bộ ID; B4 có hai ứng viên cần tái hiện, chưa tuyên bố nearest-SOTA đã chốt |
| Sensitivity | Có các khoảng đề xuất | Chưa có run log hoặc kết quả sensitivity | Là thiết kế thí nghiệm; chưa hoàn thành phân tích |

Các mục “đã sửa” là kết quả kiểm tra tài liệu và nguồn, không phải kết quả chạy phần cứng/simulator.

## 2. Sửa đổi quan trọng

- TDC-CiM/CIM-Tuner có bản arXiv năm **2026**, không phải 2024/2025 như một số tiêu đề cũ. Metadata chính xác nằm trong `references.bib`.
- TDC-CiM là mixed-signal/time-domain. Không mặc định INT8 input/weight đồng nghĩa bit-exact INT8 MAC hoặc backend digital phù hợp plan. Các cấu hình SRAM trong abstract và bảng performance phải tách riêng.
- Không suy ra việc dùng XNOR đồng nghĩa chỉ hỗ trợ mạng binary. FERMI-ML cần kiểm tra semantics/độ chính xác; không loại nó chỉ vì là digital trong khi plan chính ưu tiên digital.
- Chime có mô hình chi phí checkpoint và recomputation: bỏ kết luận “tách write/recovery là đóng góp mới”.
- Không kết luận “không công trình nào có” từ vài abstract. Khác biệt dự kiến vẫn là đồng tối ưu DW–PW mapping, trạng thái weight và lựa chọn lưu/tính lại dưới power loss, cần khảo sát rộng hơn.

## 3. Baselines thống nhất với plan

| ID | Định nghĩa | Nguồn/phạm vi |
|---|---|---|
| B0 | Digital non-CIM, chạy cả baseline policy và RECAP | Nhóm đối chứng backend × policy 2×2; chưa có backend calibrated |
| B1 | CIM, mapping cho nguồn liên tục, checkpoint theo layer | Baseline do dự án hiện thực |
| B2 | CIM, checkpoint theo tile cố định | Cùng commit protocol và arithmetic với RECAP |
| B3 | CIM, energy-adaptive tile, chưa đồng tối ưu save/replay và reload | Phải mô tả thuật toán, không dùng nhãn thay implementation |
| B4a | CIM-Tuner-inspired mapping + recovery policy được công bố rõ | Ứng viên baseline mapping mạnh; không gọi bản thêm recovery là nguyên bản tác giả |
| B4b | Chime-inspired checkpoint optimization trên cùng backend | Ứng viên baseline recovery; cần đối chiếu objective và semantics |
| B5 | RECAP-CIM | Chưa hiện thực |
| O1 | Oracle/optimum trong không gian nhỏ có mô tả | Chỉ làm upper bound/kiểm tra chất lượng mapper |

TDC-CiM là ứng viên macro/backend, không phải một checkpoint policy. Chưa chạy hoặc reproduce CIM-Tuner/Chime trong lần rà soát này.

## 4. Điều kiện còn thiếu để qua G1

- [ ] Có coverage log cho các công trình sát nhất, bao gồm CHRYSALIS và các nghiên cứu intermittent inference mới hơn; không nhận đủ 20–30 bài chỉ từ số dòng bibliography.
- [ ] Matrix dẫn tới mục/trang/công thức cụ thể cho mọi phát biểu phủ định quan trọng; không đánh dấu novelty toàn lĩnh vực đã được chứng minh.
- [ ] Chốt macro digital INT8 hoặc ghi một mô hình kiến trúc giả định có miền tham số đủ căn cứ; không tự chuyển plan sang mixed-signal để khớp một số TOPS/W.
- [ ] Có compute/update bandwidth, arithmetic semantics, reload energy/latency và phạm vi khối đủ để xây cost model; giá trị thiếu phải để chưa biết và giải thích sensitivity.
- [ ] Chọn NVM/bus/power-state/atomic-write assumptions; kiểm tra model + input + hai checkpoint slots + metadata có vừa capacity.
- [ ] Chọn B4 gần nhất sau khi đọc và kiểm tra artifact; lập kế hoạch adaptation công bằng với cùng workload/source/accuracy.
- [ ] Viết một ví dụ quyết định RECAP khác baseline và một thí nghiệm có thể bác bỏ lợi ích; việc chạy microbenchmark đúng thuộc G2/G3.

## 5. Việc có thể làm ngay

1. Tiếp tục G1: hoàn thành coverage log, macro selection và baseline adaptation spec.
2. G2 ở mức độc lập: INT8 golden tensors, schema simulator và ledger transactions; các trường chưa có nguồn phải giữ `null`, không dùng số cũ như số đo.
3. Chưa đóng băng energy results, chưa nhận đạt mục tiêu tiết kiệm và chưa ghi G1 PASS.

## 6. Artifact sau rà soát

- [Novelty matrix](novelty_matrix.md)
- [Hardware/NVM selection](hardware_selection/sram_cim_nvm_selection.md)
- [Parameter manifest](hardware_selection/research_parameters.json)
- [Source audit và danh sách dữ liệu bị loại](G1_source_audit.md)
- [Bibliography đã chuẩn hóa](references.bib)
- [Bản sao trước chỉnh sửa](./_backups/G1_before_audit_2026-10-15/manifest.json)

Ngày nghiệm thu chỉ được cập nhật thành PASS khi các điều kiện trên có artifact kiểm tra được. Đây là trạng thái công việc theo bằng chứng hiện có, không phải đánh giá khả năng nhận bài.

## 7. Kiểm tra kỹ thuật của lần audit

- BibTeX: 15 entries, không trùng khóa, không có failed parse blocks. Đây không phải số bài đã đọc full text.
- UTF-8, bảng Markdown, khối công thức/code và link nội bộ của bộ tài liệu G1 đã kiểm tra.
- Đơn vị/capacity và phép tính transaction minh họa được đối chiếu với parameter manifest; chưa phải validation năng lượng phần cứng.
- Hai PDF nguồn và sáu file backup trước chỉnh sửa được xác minh bằng SHA-256.
- Không chạy training, sensitivity sweep, reproduction baseline hoặc thí nghiệm RECAP trong lần audit này.
