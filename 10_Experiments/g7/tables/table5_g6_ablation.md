# Table 5: G6 ablation summary

| Workload | Intervention | Mean energy (uJ/commit) | Δ vs full RECAP | Status |
| --- | --- | --- | --- | --- |
| KWS | adaptive_mapping_fixed_recovery | 980.4 | +0.00% | 0.0% less |
| KWS | all_live | 3079.2 | +0.00% | 0.0% less |
| KWS | always_replay_dw | 980.4 | +0.00% | 0.0% less |
| KWS | always_save_dw | 1064.9 | +0.00% | 0.0% less |
| KWS | continuous_fusion | 978.4 | +0.00% | 0.0% less |
| KWS | fixed_mapping_recovery | 10807.7 | +0.00% | 0.0% less |
| KWS | ignore_reload_decision | 980.4 | +0.00% | 0.0% less |
| KWS | no_control | 960.9 | +0.00% | 0.0% less |
| KWS | no_weight_reuse | 980.4 | +0.00% | 0.0% less |
| KWS | unfused | 1179.8 | +0.00% | 0.0% less |
| VWW | adaptive_mapping_fixed_recovery | 13483.4 | +0.00% | 0.0% less |
| VWW | always_replay_dw | 13483.4 | +0.00% | 0.0% less |
| VWW | always_save_dw | 13484.0 | +0.00% | 0.0% less |
| VWW | continuous_fusion | 13483.4 | +0.00% | 0.0% less |
| VWW | ignore_reload_decision | 13483.4 | +0.00% | 0.0% less |
| VWW | no_control | 13482.2 | +0.00% | 0.0% less |
| VWW | no_weight_reuse | 13482.5 | +0.00% | 0.0% less |
| VWW | unfused | 13483.9 | +0.00% | 0.0% less |

- Δ > 0 nghĩa ablation tốn hơn full RECAP
- Các intervention chỉ thay đổi cost accounting, không thay đổi thuật toán
- Nhiều intervention cho Δ ≈ 0 vì cost overhead đã bị chia sẻ với work khác
