# G9 protocol lock history

| Rev | Date | Change | Verified |
|---|---|---|---|
| 1 | 2026-11-11 | Initial lock, `grounded_nvm_scale_range = null` (166 files). Copy: `protocol_lock.rev1.json`. | Main refused to run. |
| 2 | 2026-11-11 | Filled `grounded_nvm_scale_range = [0.627, 8.91]` and `grounded_range_derivation` in `g9_protocol.json` (the only protocol edit; undoing these two lines reproduces the rev-1 hash). Test `test_protocol_is_internally_consistent` changed from "range is null" to "range is a positive increasing pair" (one line, mechanical consequence). Derivation: `02_Research/hardware_selection/nvm_scale_range.json`, script `10_Experiments/g9/derive_nvm_scale_range.py`. | Every other hashed file unchanged since rev 1; 19 G9 tests pass. Declared before any main result. |

The derivation script and JSON are referenced by hash inside the protocol; they are not themselves in the lock file list.
