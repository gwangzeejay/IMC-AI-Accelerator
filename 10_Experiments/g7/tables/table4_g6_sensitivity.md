# Table 4: G6 sensitivity sweep

| Workload | Knob | Value | B3 mean (uJ) | RECAP mean (uJ) | Reduction | Status |
| --- | --- | --- | --- | --- | --- | --- |
| KWS | active_leakage_w | 0.0 | 1005.3 | 998.7 | +0.66% | < 5% |
| KWS | active_leakage_w | 1e-06 | 1003.8 | 1003.8 | +0.00% | < 5% |
| KWS | active_leakage_w | 1e-05 | 1006.9 | 1006.9 | +0.00% | < 5% |
| KWS | admission_margin_fraction | 0.0 | 1005.3 | 998.7 | +0.66% | < 5% |
| KWS | admission_margin_fraction | 0.05 | 1003.7 | 998.6 | +0.50% | < 5% |
| KWS | admission_margin_fraction | 0.2 | 1002.5 | 999.1 | +0.33% | < 5% |
| KWS | bandwidth_scale | 0.25 | 1176.4 | 1176.4 | -0.00% | < 5% |
| KWS | bandwidth_scale | 1.0 | 1005.3 | 998.7 | +0.66% | < 5% |
| KWS | bandwidth_scale | 4.0 | 992.0 | 992.0 | +0.00% | < 5% |
| KWS | compute_energy_scale | 0.25 | 937.8 | 934.0 | +0.41% | < 5% |
| KWS | compute_energy_scale | 1.0 | 1005.3 | 998.7 | +0.66% | < 5% |
| KWS | compute_energy_scale | 4.0 | 1383.2 | 1383.2 | +0.00% | < 5% |
| KWS | nvm_energy_scale | 0.25 | 523.3 | 523.3 | -0.00% | < 5% |
| KWS | nvm_energy_scale | 1.0 | 1005.3 | 998.7 | +0.66% | < 5% |
| KWS | nvm_energy_scale | 4.0 | 2989.5 | 2989.5 | +0.00% | < 5% |
| KWS | retention_w | 0.0 | 996.0 | 996.0 | -0.00% | < 5% |
| KWS | retention_w | 1e-06 | 1005.3 | 998.7 | +0.66% | < 5% |
| KWS | retention_w | 1e-05 | 1030.5 | 1019.7 | +1.05% | < 5% |
| VWW | active_leakage_w | 0.0 | 12196.7 | 12196.7 | +0.00% | < 5% |
| VWW | active_leakage_w | 1e-06 | 12196.5 | 12196.5 | +0.00% | < 5% |
| VWW | active_leakage_w | 1e-05 | 12194.6 | 12194.6 | +0.00% | < 5% |
| VWW | admission_margin_fraction | 0.0 | 12196.7 | 12196.7 | +0.00% | < 5% |
| VWW | admission_margin_fraction | 0.05 | 12196.2 | 12196.2 | +0.00% | < 5% |
| VWW | admission_margin_fraction | 0.2 | 12194.3 | 12194.3 | -0.00% | < 5% |
| VWW | bandwidth_scale | 0.25 | 10178.0 | 9846.6 | +3.26% | < 5% |
| VWW | bandwidth_scale | 1.0 | 12196.7 | 12196.7 | +0.00% | < 5% |
| VWW | bandwidth_scale | 4.0 | 12197.1 | 12194.6 | +0.02% | < 5% |
| VWW | compute_energy_scale | 0.25 | 12194.8 | 12195.1 | -0.00% | < 5% |
| VWW | compute_energy_scale | 1.0 | 12196.7 | 12196.7 | +0.00% | < 5% |
| VWW | compute_energy_scale | 4.0 | 12195.8 | 12195.8 | +0.00% | < 5% |
| VWW | nvm_energy_scale | 0.25 | 4481.1 | 4469.9 | +0.25% | < 5% |
| VWW | nvm_energy_scale | 1.0 | 12196.7 | 12196.7 | +0.00% | < 5% |
| VWW | nvm_energy_scale | 4.0 | 0.0 | 0.0 | +0.00% | < 5% |
| VWW | retention_w | 0.0 | 12193.2 | 12193.2 | +0.00% | < 5% |
| VWW | retention_w | 1e-06 | 12196.7 | 12196.7 | +0.00% | < 5% |
| VWW | retention_w | 1e-05 | 12196.5 | 12196.5 | +0.00% | < 5% |

- Knobs là engineering stress ranges, không phải datasheet
- Reduction âm = RECAP đắt hơn B3 trong cấu hình đó
- Cùng value có thể thấy RECAP bằng B3 trong nhiều cấu hình
