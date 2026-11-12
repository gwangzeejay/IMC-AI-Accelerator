# Tái lập RECAP-CIM G2–G6 trên máy tính

## Môi trường đã chạy

Windows, CPython 3.12.9, NumPy 2.2.4, TensorFlow 2.21.0. Các thư viện này
đã có trên máy khi thực hiện G2; không thay đổi môi trường toàn cục.
Danh sách pin: `requirements-g2.txt`. Khi chuẩn bị máy khác, có thể cài
trong virtual environment riêng:

```powershell
python -m venv .venv-g2
.venv-g2\Scripts\python.exe -m pip install -r 10_Experiments/requirements-g2.txt
.venv-g2\Scripts\python.exe 10_Experiments/run_g2.py
```

TensorFlow/Lite resolver được pin để giữ semantics làm tròn; việc chuyển
sang LiteRT hoặc kernel optimized cần kiểm tra lại golden equivalence.
API interpreter hiện có cảnh báo deprecation; cảnh báo không phải test fail.
Model được nạp qua `model_content` để tránh vấn đề đường dẫn Unicode trong
native TFLite file loader trên Windows.

## Một lệnh thực hiện toàn bộ G2

Chạy tại thư mục gốc repository:

```powershell
python 10_Experiments/run_g2.py
```

Pipeline đọc source/model đã lưu cục bộ, kiểm tra source hashes, export
golden, chạy unit tests, bốn policy chức năng, coupled-source debug,
profile mapper và fault campaign. Không download dữ liệu, không huấn luyện,
không cần FPGA/EDA. Các kết quả sinh lại ghi đè **artifact G2 được tạo tự
động** tại `10_Experiments/g2/` và `manifests/g2_run.json`.

Nếu chỉ muốn giữ golden đã đối chiếu và chạy lại simulator/tests:

```powershell
python 10_Experiments/run_g2.py --skip-reference
```

Lệnh này vẫn kiểm tra SHA-256 các golden files, nhưng không đối chiếu lại
với interpreter trong lần đó. Manifest ghi rõ lựa chọn.

## Từng bước riêng

```powershell
python 05_Model_Training/export_reference_int8.py
python -m unittest discover -s 09_Simulation/tests -v
python 09_Simulation/recap_simulator.py
python 09_Simulation/recap_simulator.py --source-debug
python 09_Simulation/profile_g2_mapper.py
python 09_Simulation/fault_injection.py --seed 20261015 --random-cases 1000
```

## Đọc kết quả

| File | Ý nghĩa |
|---|---|
| `g2/reference/reference_report.json` | Model identity, weight/constant bytes, MACs, 16 checks trên 4 DW–PW pairs |
| `g2/reference/*.npz`, `microtile.json` | Golden và parameters số học; fixture stress không phải accuracy dataset |
| `g2/unit_tests.json`, `unit_tests.txt` | Số test và kết quả chạy thật |
| `g2/functional/summary.json` | Bốn policy đúng chức năng, energy chưa biết |
| `g2/functional/*.jsonl` | Breakdown bytes/MAC/actions/replay theo identity |
| `g2/source_debug/summary.json` | Source/ledger invariant, completed/incomplete và metrics của hệ số giả định |
| `g2/mapper_profile.json` | 16 cấu hình, 48 training evaluations, B1/B2 prototypes; chưa có held-out test |
| `g2/faults/summary.json`, `cases.jsonl` | 3.099 ca và từng vị trí loss đã thực thi |
| `manifests/g2_run.json` | Phiên bản, lệnh chạy, SHA-256 của code/config/result |

Kỳ vọng: 22 unit tests pass, 256.000 tensor elements không mismatch,
3.099 fault cases không mismatch. Source-debug chỉ hai trong bốn policy
hoàn tất trên trace ngắn đã chọn; `PASS_SOURCE_INVARIANTS` không có nghĩa
mọi policy đều hoàn tất. Không biến các số J giả định thành kết quả bài báo.

Thời gian/peak Python allocations thay đổi theo máy/lần chạy. Golden
hashes được sinh lại và ghi vào manifest; không yêu cầu toàn bộ JSON report
có hash cố định khi chứa thời gian profiling.

## Tái lập G3: mapper và microbenchmark

```powershell
python 10_Experiments/run_g3.py
```

G3 dùng cùng Python/NumPy/TensorFlow như G2 và Matplotlib để xuất PNG/SVG.
Lệnh kiểm tra golden/source hashes, export thêm quantization CO, sinh
descriptor, chạy 22 tests G2 + 17 tests G3, fit/freeze mapper, đánh giá
held-out và sensitivity, thử exploratory recovery episodes, fault campaign,
sinh figure và manifest. Không download hoặc huấn luyện lại.

Lệnh ghi đè các artifact G3 được sinh tự động; không ghi đè G2 results.
Các log diagnostic đã retire được giữ riêng trong `g3/_diagnostics/` và
không dùng làm test evidence chính.

| Artifact G3 | Nội dung |
|---|---|
| `g3/protocol_snapshot.json`, `scenarios.json` | Grid, cost assumptions, splits/seeds và source traces |
| `g3/descriptors/catalog.json` | 75 descriptor, 8 partitions, actual golden coverage |
| `g3/frozen_mapper.json` | Mapping chọn bằng train/validation, feasibility reference B3, hash và fit IDs |
| `g3/raw/train*.jsonl`, `validation*.jsonl` | Kết quả fit và adaptive baseline reference |
| `g3/raw/test.jsonl`, `sensitivity_*.jsonl` | Held-out và toàn bộ sensitivity, gồm incomplete cases |
| `g3/summary.json` | Metrics, paired bootstrap và quyết định model-only |
| `g3/recovery_episodes.json` | Post-hoc state-aligned diagnostic, không dùng tuning/test claim |
| `g3/faults/summary.json`, `cases.jsonl` | 4.112 ca, 6.022 loss thực thi; không mismatch |
| `g3/unit_tests.json`, `unit_tests.txt` | 39 tests đạt, không fail/error/skip |
| `g3/plots/` | Held-out comparison, undefined main sensitivity, exploratory episode heatmaps; PNG/SVG |
| `manifests/g3_run.json` | Source/result hashes, versions, command và retired diagnostic hashes |

Kết quả kỳ vọng: mapper 1×2/CO16/CI64, 9/18 completed so với B3 8/18,
model energy/completed giảm 22,09% với CI95 14,65–38,08%. Không xem đây là
phép đo hoặc là bảo đảm giảm ≥20%. Main SAVE/REPLAY CI16 có 0 completed,
energy/completed undefined; các ca này phải giữ nguyên trong báo cáo.

Các file [G3 deliverables](../02_Research/G3_deliverables.md) và
[G3 spec](../03_Architecture/g3_mapping_spec.md) giải thích định hướng và
giới hạn trước khi tiến tới RTL. Có thể chuẩn bị môi trường mới bằng
`requirements-g3.txt`; môi trường hiện tại không bị cài/thay đổi thư viện.

## Tái lập G4: RTL simulation và wire/cycle oracle

G4 dùng Windows/CPython 3.12.9, NumPy 2.2.4 và local Icarus/VVP/Yosys.
Không import TensorFlow khi golden tensors G2/G3 đã có. Dependencies Python
tại `requirements-g4.txt`; source/golden hashes G2/G3 được kiểm trước run.

Chuẩn bị tools một lần, cần mạng và khoảng 575 MiB archive:

```powershell
python 10_Experiments/setup_g4_tools.py
```

Script pin OSS CAD Suite release 2026-10-14, kiểm size/digest của archive
rồi chỉ extract runtimes vào `tmp/g4_tools`. DLL runtime được copy tới
Temp path ASCII để Windows native tools làm việc với workspace tiếng Việt.
Không sửa PATH/registry toàn hệ thống; PATH chỉ đặt cho subprocess.

Chạy kiểm chứng lại thật, offline sau setup:

```powershell
python 10_Experiments/run_g4.py
```

Default thực hiện 10 Python tests, real-model/seeded arithmetic RTL,
1.856 main CI16 protocol cases + 26 CI64 supplement, independent byte/cycle
oracle và generic Yosys passes cho scalar cores/reduced controller.
Fault traces lớn được gzip sau khi cross-check. Chạy mất vài phút tùy máy;
không cần FPGA, PDK hoặc EDA thương mại.

```powershell
python 10_Experiments/run_g4.py --full-controller
```

Flag trên thử thêm full-size generic controller với timeout 180 s; không
hứa synthesis sẽ đạt. Lần đã thực hiện bị timeout, chưa có tech mapping,
timing closure hoặc PPA. Reduced generic checks không chứng minh full
controller sẽ fit area hoặc timing target.

```powershell
python 10_Experiments/run_g4.py --collect-existing
```

Collect mode chỉ đóng gói/check source bindings và evidence/logs của các
RTL runs đã thực hiện, chạy Python codec tests; không rerun campaign hoặc
Yosys. Đợt phát triển này dùng chế độ đó sau khi suites đã chạy trực tiếp
bằng helper. Không mô tả collect mode như chạy lại toàn bộ RTL.

| Artifact G4 | Nội dung |
|---|---|
| `g4/summary.json` | Scope, tổng cases/traffic/cycle checks và limitations |
| `g4/rtl_summary.json`, `whole_unit_summary.json` | Main CI16 và CI64 output-only protocol suites |
| `g4/vectors/` | Model-backed input/weights/quantization, arithmetic vectors, binary identity configs |
| `g4/cases/` | Reproducible case lists và directed initial NVM images |
| `g4/raw/*.trace`, `*.trace.gz` | Byte ACK/restore/reset/commit events và cycle timestamps |
| `g4/*_report.json` | Independent oracle results, per-case stats và latency comparisons |
| `g4/logs/arithmetic.log` | 647 MAC / 5.468 requantization cases đạt |
| `g4/synthesis_summary.json`, `*_generic.json` | Actual Yosys passes; reduced/full scope và no-PPA fields |
| `g4/build/tb_checkpoint_ci64.sv` | Driver variant: chỉ đổi execution chunk 16→64, controller không đổi |
| `g4/rtl_source_hashes.json` | Source bindings của campaigns đã chạy |
| `manifests/g4_run.json` | Command/collect flag, tool versions/binary hashes và artifact hashes |

Kỳ vọng: 1.882 controller cases (6 intentional fail-closed cases), 1.830
fault cases, 2.844 loss thực thi, 6.415.721 NVM transactions và 8.317 commit
latencies không mismatch; 647 MAC, 5.468 requant và 10 Python tests đạt.
Phạm vi là finite simulation, không phải formal proof.

Header binary 124 B/CRC32 khác JSON/SHA-256 trong G3; G4 kiểm semantic
refinement, không byte/energy equivalence với G3. Chưa có full KWS,
physical macro/NVM validation hoặc area/power/fmax. Chi tiết tại
[G4 deliverables](../02_Research/G4_deliverables.md).

## G5 — Hybrid KWS, mapper/runtime và test độc lập

Môi trường: Python 3.12.9; NumPy 2.2.4, TensorFlow 2.21.0,
matplotlib 3.10.1 (`requirements-g5.txt`). Chạy từ workspace root:

```powershell
python 10_Experiments/setup_g5_data.py
python 10_Experiments/run_g5.py
python 10_Experiments/audit_g5.py
```

Setup lần đầu tải zip commit EEMBC đã ghim, chỉ lấy `datasets/kws01` cùng
metadata liên quan: 1.000 file MFCC 490 B + nhãn. Các lần sau kiểm hashes
local, không download lại. Model/checkpoints G2/G3/G4 có sẵn là prerequisites;
main G5 kiểm đủ prior manifests và không lặp lại Icarus/Yosys campaigns.

Main G5 ghi đè **generated** artifacts tại `g5/` và `manifests/g5_run.json`:
12 unit tests; reference accuracy 1.000 input; own full arithmetic trên 39
mẫu; 16 full-network diagnostic faults; 108 train/validation/test evaluations;
policy/source freeze trước test; paired bootstrap và PNG/SVG plots.
Đợt đã chạy khoảng 118 s trên máy hiện tại. Không thay policy theo kết quả
test khi rerun. Nếu thay thuật toán/cost phải tạo protocol/holdout mới.

Audit không refit hoặc chạy lại test inference: kiểm tất cả manifests G2–G5,
split/seed independence, raw aggregate, energy balance và logical memory
bounds; profile candidate enumeration trên host. Audit có manifest riêng tại
`g5_audit/`, không thay hashes của đợt main run đã khóa.

| Artifact | Nội dung |
|---|---|
| `g5/protocol_snapshot.json`, `input_splits.json`, `scenarios.json` | Cost/protocol, feature hash groups và source traces |
| `g5/frozen_policy.json` | Mapper/B3 reserve đã fit, source/model/data/split hashes trước test |
| `g5/raw/{train,validation,test}.jsonl` | Từng trace, arrival/deadline, exact outputs, energy ledger và lựa chọn mapping |
| `g5/accuracy.json`, `reference_predictions.json` | Accuracy reference + confusion matrix + own tensor checks |
| `g5/faults.json`, `unit_tests.txt` | Full-network loss cases và finite boundary tests |
| `g5/results.json`, `summary.json` | Held-out metrics, CIs, overhead, no-calibration flags |
| `g5/heldout.png`, `heldout.svg` | Figure có nhãn assumed costs |
| `manifests/g5_run.json` | Code/data/artifact hashes của đợt thực thi |
| `g5_audit/audit.json`, `manifest.json` | Post-run integrity checks và host-only profile |

Kết quả kỳ vọng của protocol G5_1.0: RECAP = B3 26/36 commit,
0,9623 model mJ/commit, giảm 0%; **mục tiêu 20% chưa đạt**. B1_layer 28/36
commit, 0,7923 model mJ/commit. p95 của mọi method vô hạn. Reference accuracy
90,1% không phải contribution accuracy do RECAP. CPU FC requantization và
softmax là classification head reference; audio/MFCC preprocessing bị loại
khỏi phạm vi. Không nhận full-network RTL/PPA/physical energy.

Chi tiết giới hạn và hướng nghiên cứu tiếp theo tại
[G5 deliverables](../02_Research/G5_deliverables.md) và
[runtime spec](../03_Architecture/g5_runtime_spec.md).

## G6 — Hai workload, ETH source, sensitivity và ablation

Giữ nguyên môi trường G5, thêm h5py 3.14.0 và Pillow 11.2.1;
dependency pins trong `requirements-g6.txt`. Chạy tại workspace root:

```powershell
python 10_Experiments/setup_g6_sources.py
python 10_Experiments/run_g6.py
python 10_Experiments/audit_g6.py
python 10_Experiments/analyze_g6.py
```

Setup tải model VWW cùng source ở commit MLCommons đã ghim; 40 JPEG COCO
theo nhãn chính thức; riêng ETH HDF5 pos16 khoảng **172 MiB** bằng HTTP Range,
kiểm SHA-256 toàn member. Không tải archive 32 GB. Trace member nằm tại
`tmp/g6_sources/pos16_power_relative.h5`; giữ file này để audit offline hoặc
chạy setup để tải lại. Các lần setup sau kiểm hashes local; khác checksum
phải dừng, không tự thay source để khớp một kết quả mới.

Main run kiểm manifests G2–G5; chạy 14 tests, model equivalence, 8 full-graph
faults và 1.000 random large-slot schedules; diagnostic preflight tất cả
variant trước khi khóa source/policy/data/scenario hashes và chạy main.
Không cần chạy lại Icarus/Yosys hoặc cài thêm EDA tools cho G6.

Pipeline chạy tuần tự độc lập. Để tận dụng CPU khi còn đủ RAM, sau khi log
báo `FROZEN before main evaluation`, có thể chạy hai lệnh ở terminal khác:

```powershell
python 10_Experiments/prefill_g6_cases.py --workload kws
python 10_Experiments/prefill_g6_cases.py --workload vww
```

Workers chỉ gọi đúng frozen runtime cho các sensitivity/digital cases độc
lập, kiểm source hashes và publish JSON nguyên tử. Provenance riêng ở
`g6_parallel/`; audit kiểm cả driver và các case hashes. Không dùng workers
để thay policy hoặc tham số theo test. Đợt này khoảng 25 phút, 688 cases
chạy trong main + 528 trong workers = 1.216 distinct case files. Thời gian
máy khác khác nhau. `unique_executions` trong summary chỉ đếm case mới của
main process; số case files và worker provenance cho biết tổng distinct cases.

`g6/cases/` là cache có khóa từ frozen source/data và toàn config. Main
run sau có thể dùng lại cases nếu khóa khớp; pipeline vẫn chạy preflight,
ghi lại freeze timestamp, summaries và manifests. Không sửa case JSON bằng
tay. Khi thay thuật toán/cost sau khi đã xem test, cần protocol/holdout mới;
cache key khác không tự biến tập test cũ thành holdout mới.

| Artifact | Nội dung |
|---|---|
| `g6/protocol_snapshot.json`, `frozen_protocol.json` | Grid/costs/methods và source/data binding trước test |
| `g6/input_pools.json`, `scenarios.json` | G5-disjoint input hashes, fresh seeds, native measured windows |
| `g6/eth_window_*.npz`, `eth_windows.json` | Raw measurements, timestamps, signed panel power và assumed rail transfer |
| `g6/memory_feasibility.json` | VWW infeasible trên budget gốc; cùng extended budget cho hai workload |
| `g6/accuracy.json`, `faults.json`, `unit_tests.txt`, `preflight.json` | Correctness scope riêng cho từng nhóm kiểm tra |
| `g6/cases/*.json` | Actual source-bound runtime results, gồm incomplete/undefined |
| `g6/raw/main.jsonl` | 448 main rows: 2 workloads × 4 methods × 56 source cases |
| `g6/raw/ablations.jsonl` | 240 rows, 10 interventions/workload |
| `g6/raw/sensitivity.jsonl` | 576 rows, 6 axes × 3 levels × 2 workloads × 2 methods × 8 traces |
| `g6/raw/backend_factorial.jsonl` | 96 rows: assumed CIM/digital × B3/RECAP × 2 workloads |
| `g6/results.json`, `summary.json`, `*.png`, `*.svg` | Metrics, paired CIs, losing cases và figures |
| `manifests/g6_run.json` | Code/source/case/artifact hashes; library versions; no-calibration flags |
| `g6_parallel/*.json` | Optional workers, frozen-content ID và published case hashes |
| `g6_audit/` | Provenance, pairing, grid completeness, memory/energy/statistic checks |
| `g6_analysis/` | Post-hoc mechanism diagnosis, numerical-loss filter, no refitting |

Kỳ vọng G6_1.0: stochastic KWS RECAP 99/120 vs B3 98/120, model energy
reduction 1,368% (CI95 0,126–3,504%); VWW cùng 20/120 và gần 0% reduction.
Measured-derived KWS 24/36, VWW 4/36; unconditional energy CIs undefined.
Chưa đạt mục tiêu chính 20%. Mẫu VWW 40 ảnh có research preprocessing;
82,5% là subset accuracy. Shared memory budget là 64 KiB/2 MiB; VWW không
vừa budget gốc 16 KiB/256 KiB. Các cost/rail transfer vẫn giả định.

Chi tiết ablation limitations, score thiếu redo credit và việc giữ mọi ca
thua tại [G6 deliverables](../02_Research/G6_deliverables.md) và
[evaluation spec](../03_Architecture/g6_evaluation_spec.md).

## G7 — Audit, diagnostic executions và manuscript build

`python 10_Experiments/run_all.py` hiện là audit đọc-only: kiểm SHA-256 thật của G2–G6 và tính lại main aggregates; không gọi stage runners hay ghi đè frozen outputs. Nó không chứng nhận fresh toàn pipeline replay. `python 10_Experiments/g7/cross_validation.py` chạy hai input và hai repeats của một KWS case trên cùng host; không là cross-host/hardware calibration. Báo cáo G7 cũ được giữ trong backup và đánh dấu superseded.

Build bản thảo và đóng gói local theo `07_IEEE_Paper/g7/README.md`. Để fresh replay toàn G2–G6, dùng workspace snapshot dùng một lần, chuẩn bị đủ model/data/tools theo hướng dẫn từng mốc ở trên, giữ riêng manifests gốc/lần chạy mới và so scientific metrics thay vì timestamps/host-profiling fields. Chưa thực hiện clean-host replay trong G7.
