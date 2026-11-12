# Table 2: G5 KWS main test — 12 traces × 3 arrivals

| Method | Commits / 36 | Completion (%) | On-time (%) | Model energy (uJ/commit) | Note |
| --- | --- | --- | --- | --- | --- |
| B1 (layer) | 28/36 | 77.8 | 52.8 | 792.3269 | Strongest completion; check tolerance 5pp |
| B2 (fixed) | 2/36 | 5.6 | 0.0 | 24085.3337 | Fixed geometry weak for 4-source window |
| B3 (adaptive) | 26/36 | 72.2 | 50.0 | 962.2725 | Same as RECAP; energy- and time-equal |
| RECAP | 26/36 | 72.2 | 50.0 | 962.2725 | Equal to B3 in 12/12 traces |
| RECAP no-control | 27/36 | 75.0 | 52.8 | 910.9569 | Ablation: drop assumed control overhead |

- Tất cả model energy là assumed coefficients, không phải silicon
- B3 = RECAP point estimate; CI95 energy reduction = [0%; 0%]
- B1 layer completion tốt hơn RECAP +5.56pp; nằm ngoài tolerance 5pp
- RECAP_no_control là ablation bỏ assumed control overhead
