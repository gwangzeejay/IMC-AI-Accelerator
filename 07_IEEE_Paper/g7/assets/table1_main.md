| Workload | Domain | Method | Commits | On-time (%) | Assumed energy (mJ/commit) | p95 (s) |
| --- | --- | --- | --- | --- | --- | --- |
| KWS | synthetic_stochastic | B1_layer | 100/120 | 75.83 | 0.878171 | infinity |
| KWS | synthetic_stochastic | B2_fixed | 12/120 | 0.00 | 25.152871 | infinity |
| KWS | synthetic_stochastic | B3_adaptive | 98/120 | 72.50 | 0.984372 | infinity |
| KWS | synthetic_stochastic | RECAP | 99/120 | 73.33 | 0.970909 | infinity |
| KWS | eth_measured_derived_rail | B1_layer | 24/36 | 66.67 | 0.840995 | infinity |
| KWS | eth_measured_derived_rail | B2_fixed | 2/36 | 0.00 | 33.787436 | infinity |
| KWS | eth_measured_derived_rail | B3_adaptive | 24/36 | 66.67 | 0.957298 | infinity |
| KWS | eth_measured_derived_rail | RECAP | 24/36 | 66.67 | 0.956891 | infinity |
| VWW | synthetic_stochastic | B1_layer | 20/120 | 0.00 | 15.086817 | infinity |
| VWW | synthetic_stochastic | B2_fixed | 0/120 | 0.00 | undefined | infinity |
| VWW | synthetic_stochastic | B3_adaptive | 20/120 | 0.00 | 15.087774 | infinity |
| VWW | synthetic_stochastic | RECAP | 20/120 | 0.00 | 15.087771 | infinity |
| VWW | eth_measured_derived_rail | B1_layer | 4/36 | 0.00 | 16.888406 | infinity |
| VWW | eth_measured_derived_rail | B2_fixed | 0/36 | 0.00 | undefined | infinity |
| VWW | eth_measured_derived_rail | B3_adaptive | 4/36 | 0.00 | 16.888352 | infinity |
| VWW | eth_measured_derived_rail | RECAP | 4/36 | 0.00 | 16.888352 | infinity |

All consumed model energy, including unfinished work, is in the numerator. Costs are assumed. Synthetic: 40 traces/120 arrivals; ETH-derived: six day blocks, two capacitors/day and 36 arrivals. Infinite p95 includes unfinished arrivals.
