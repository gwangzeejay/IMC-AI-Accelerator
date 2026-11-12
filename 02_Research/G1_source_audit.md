# G1 source audit và dữ liệu cách ly

**Ngày kiểm tra:** 15/10/2026. Phạm vi: tài liệu G1 hiện có; chưa phải systematic review toàn bộ lĩnh vực.

## 1. Nguồn đã kiểm tra và mức truy cập

| ID / BibTeX key | Nguồn | Vị trí/mức bằng chứng |
|---|---|---|
| S1 / chime2016 | [Chime PDF từ nhóm tác giả](https://raw.githubusercontent.com/ACESLabUCSD/website-bib/refs/heads/main/Papers/2016/Chime_Checkpointing_Long_Computations_on_Interm_ittently_Energized_IoT_Devices.pdf) | PDF local 14 trang; §§5.1–5.2 tr. 280–281; §6 tr. 282; §9.5 tr. 285. Có tách checkpoint/read-write/recomputation; kết luận cũ ngược nguồn |
| S2 / viadotto2025 | [Viadotto full text](https://imec-publications.be/server/api/core/bitstreams/d647c609-d6f6-4f7f-b851-f19a1cc1a2ff/content) | §§2.1, 3.1–3.3 về CRAM, allocation/dataflow/controller; không chỉ abstract |
| S3 / chrysalis2024 | [HKUST publication record](https://researchportal.hkust.edu.hk/en/publications/a-tale-of-two-domains-exploring-efficient-architecture-design-for/) | Metadata/abstract; [artifact landing page](https://zenodo.org/records/10982940) đã tìm được, chưa chạy hay đọc đủ thuật toán |
| S4 / cimtuner2026 | [CIM-Tuner v1](https://arxiv.org/html/2601.18070v1), [repository](https://github.com/champloo2878/CIM-Tuner) | §§III-B–III-D và IV-A; Table I/Eq. (5); README đã xem, chưa reproduce hoặc audit code/config |
| S5 / tdccim2026 | [TDC-CiM v1](https://arxiv.org/html/2601.00434v1) | §§III-A, III-E, IV-E, Tables II/III; mixed-signal và scope/config phải tách |
| S6 / freeml2024 | [FreeML](https://arxiv.org/abs/2405.10426), [HTML](https://arxiv.org/html/2405.10426v1) | Metadata/abstract và cấu trúc §3.3; chưa audit đầy đủ recovery implementation |
| S7 / fermiml2025 | [FERMI-ML v1](https://arxiv.org/html/2511.12544v1) | Abstract, §II-B và evaluation; cần phân biệt variable precision, approximation và exact INT8 |
| S8 / pscnn2022 | [PSCNN](https://arxiv.org/abs/2205.01569) | Metadata/abstract: binary 1-D CNN KWS; không xác nhận ternary |
| S9 / kws2022 | [KWS IMC](https://arxiv.org/abs/2205.04665) | Metadata/abstract và DOI/year/volume/pages |
| S10 / fm25v20a2023 | [Infineon datasheet](https://www.infineon.com/dgdl/Infineon-FM25V20A_2-Mbit_(256_K_X_8)_Serial_(SPI)_F-RAM-DataSheet-v10_00-EN.pdf?fileId=8ac78c8c7d0d8da4017d0ec93a4341a5) | Local PDF 33 trang, Rev. *J; đã xem bảng/render tr. 14 và 19, đọc §§5.6/14. Tham số chip không phải board measurements |

PDF local nằm trong `source_materials/`; provenance/hashes trong [manifest](source_materials/manifest.json). Mục đọc qua HTML chưa được giả vờ có local snapshot/hash. Tất cả kết luận “đã đọc” giới hạn ở phần ghi trong bảng.

## 2. Những lỗi đã sửa

| Nội dung trước rà soát | Cách xử lý |
|---|---|
| Khẳng định novelty toàn lĩnh vực từ abstract | Bỏ nhãn “xác nhận mới”; thêm mức bằng chứng và việc cần đối chiếu |
| Chime không phân biệt chi phí checkpoint/recompute | Sửa theo full text §§5–6, 9.5 |
| “Không cần tracking/recovery” ở Viadotto | NVM giữ dữ liệu không loại bỏ allocation/controller/protocol; giới hạn khác biệt ở volatile loss |
| TDC-CiM là digital INT8 chính xác theo bit | Giữ là mixed-signal candidate, cần semantics/validation trước khi dùng |
| TOPS/W gắn vào geometry/capacity khác cấu hình | Tách các cấu hình và ghi scope |
| 0.026 pJ/MAC | Đây là energy/operation suy ra; energy/MAC phụ thuộc operations/MAC |
| XNOR/Posit-4 = binary-only | Bỏ suy luận; yêu cầu kiểm tra variable precision và approximation |
| FRAM pJ/byte, capacity/atomicity không có part | Thay bằng datasheet candidate và transaction-derived illustration; trường thiếu giữ null |
| Citation keys trùng, author placeholder, năm sai | Chuẩn hóa active bibliography; chưa xác minh không tự điền |
| Baseline IDs lệch plan | B0–B5 được giữ theo plan; macro không được đặt thành policy |
| “Sensitivity đã hoàn thành” | Chưa có run results; giữ là planned analysis |

## 3. Metadata/nguồn cũ chưa được phép dùng

- Mục `cimat2019` cũ gắn tên CIMAT với một title/author/DOI khác. Không mang thông số “34 TOPS/W” sang mô hình mới. Cần xác minh danh tính và paper gốc trước khi đưa lại vào active bibliography.
- `neuepu2019` và `convsram2020` cũ chưa có đối chiếu title–author–DOI–precision đáng tin trong lần audit này; không dùng các số hình học/năng lượng đó.
- `01_Literature_Review.md` là bản nền cũ với các tuyên bố chưa kiểm tra, được gắn nhãn legacy. Không cộng nó vào số bài full-text đã đọc.
- BibTeX trước audit có key trùng và tác giả giả định dạng “... authors”. Bản nguyên trạng giữ tại `_backups/G1_before_audit_2026-10-15/`.

## 4. Phạm vi còn thiếu

G1 vẫn cần coverage log rộng hơn, CHRYSALIS và các công trình fusion/intermittent gần nhất, macro digital exact INT8, cost loading có căn cứ, config model/hash và baseline adaptation spec. Không có kết quả training/simulator/reproduction mới trong audit này.
