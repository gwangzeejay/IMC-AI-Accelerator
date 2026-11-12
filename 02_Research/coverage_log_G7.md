# G7 literature coverage audit — 16/10/2026

**Chưa đủ novelty coverage.** Có12 công trình nghiên cứu được liệt kê dưới đây; số này không bao gồm datasheet, repository, dataset hay trang venue. Đọc vài section trong full text không được tính là đã đọc toàn bộ bài. Không xác nhận một kỹ thuật “vắng mặt” chỉ từ abstract.

Các locator G1 được giữ theo [source audit](G1_source_audit.md), không nâng cấp mức đọc trong lần G7 này. G7 đã mở lại nguồn chính thức cho metadata/abstract và đọc thêm phần liên quan của FreeML, DIAC. HTML locators dùng heading thay số trang. Chưa chạy artifact của công trình khác.

| Công trình | Mức bằng chứng thực có | Locator / URL | Kết luận được phép |
|---|---|---|---|
| Chime2016 | Selected sections từ audit G1 | S1, §§5–6,9.5; PDF tr280–282,285 | Checkpoint/recompute cost optimization đã có; không mới riêng |
| Viadotto2025 | Selected sections G1; metadata | S2, §§2.1,3.1–3.3; DOI10.1145/3765623 | Adaptive NVM-CRAM; không suy ra absence của controller/recovery |
| CHRYSALIS2024 | Metadata/abstract + artifact landing | [HKUST](https://researchportal.hkust.edu.hk/en/publications/a-tale-of-two-domains-exploring-efficient-architecture-design-for/) | Co-design hai domain đã có; full state/action/objective comparison chưa làm |
| CIM-Tuner2026 | Selected sections G1, metadata recheck | [v1](https://arxiv.org/html/2601.18070v1), §§III-B–D,Eq5,TableI | Mapping và weight-update trade-off có prior art; chưa reproduce |
| TDC-CiM2026 | Selected sections G1 | S5, §§III-A/E,IV-E,TablesII–III | Mixed-signal candidate; không là calibration digital exact INT8 |
| FreeML2024 | Relevant HTML sections G7; không full-paper implementation audit | [v1](https://arxiv.org/html/2405.10426v1), §§3.1–3.3,4.4,5.3 | Compression/early exit/buffer reduction/energy-aware runtime; dùng SONIC/Alpaca, không mặc định checkpoint policy giống RECAP |
| FERMI-ML2025 | Abstract và selected sections G1 | S7, §II-B/evaluation | Variable precision/approximation cần kiểm exact semantics |
| PSCNN2022 | Metadata/abstract G1 | S8, arXiv2205.01569 | Binary KWS; không quy đổi peak TOPS/W trực tiếp thành INT8 |
| KWS IMC2022 | Metadata/abstract G1 | S9, DOI10.1109/TVLSI.2022.3172685 | KWS/IMC/on-chip learning đã có |
| DIAC2023 preprint /DATE2024 theo arXiv | Metadata/abstract, relevant HTML subsections G7 | [v1](https://arxiv.org/html/2311.16406v1), §IV-B/C | Có synthesis/backup-overhead/FSM analysis; chưa phải DW/PW exact-output baseline được reproduce |
| Energy-Adaptive Checkpoint-Free Intermittent Inference2025 | Metadata/abstract G7 | [arXiv2503.06663v1](https://arxiv.org/abs/2503.06663v1); HTML không truy cập được | Tác giả đề xuất checkpoint-free energy adaptation; chưa đọc đủ để loại trừ overlap |
| OpenACM2026 | Metadata/abstract G7 | [arXiv2601.11292v1](https://arxiv.org/abs/2601.11292v1), author abstract/comments | Approximate SRAM-DCIM compiler/accuracy-energy trade-off là hướng liên quan; không tự dùng con số reported để calibrate RECAP |

**Không cộng vào số paper:** InfineonFM25V20A datasheet; MLCommonsTiny/EEMBCEnergyRunner repositories; ETHZenodo3715472 dataset record; ESL/TCAD author instructions. Dataset2020 gắn với paperDATA2019 cần trích đúng loại nguồn, không tự chế một paper nữa để đủ quota.

## Gaps chưa được đóng

1. Chưa hoàn tất đọc và đối chiếu CHRYSALIS, checkpoint-free2025 và các nghiên cứu intermittent-inference gần nhất ở mức state/action/objective.
2. Chưa có B4 literature adaptation trên cùng backend/cost/output contract. Early exits, pruning, model retraining và approximation có thể đổi bài toán.
3. Chưa chứng minh tập hợp DW/PW mapping + SRAM volatility + checkpoint/replay là đóng góp mới. Việc thêm nhiều cột Yes/No không xác lập novelty.
4. Chưa đạt coverage20–30 công trình sát nhất nêu trong plan. Không dùng “12 entries +3 artifacts =15 papers” hoặc đặt quota “4 confirmed gaps”.
5. Novelty cần kiểm lại gần ngày nộp. Search ngày16/10/2026 là kiểm tra có mục tiêu, không phải systematic review toàn lĩnh vực.

Do đó G1 giữ **PARTIAL_NOT_PASSED**, dù đã có implementation G2–G6. Các kết quả âm G6 có giá trị chẩn đoán nhưng đóng góp bài báo vẫn cần đối chiếu và kiểm chứng thêm.
