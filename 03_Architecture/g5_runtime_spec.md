# G5 — Hybrid KWS mapper/runtime specification

Implementation: `09_Simulation/g5_{model,storage,runtime,experiments}.py`.
This is an executable software simulation. It does not extend the G4 RTL
validation claim to a whole accelerator.

## Arithmetic and input boundary

The pinned MLPerf Tiny model consumes 490 precomputed signed INT8 MFCC values.
Audio capture, windowing and MFCC generation are outside this experiment.
First convolution and four fused DW/PW pairs execute from actual input/weights
using INT32-bounded accumulation and the G2 two-rounding integer arithmetic.
Pooling uses signed integer nearest rounding; reshape preserves bytes.

The CPU classification head deliberately follows the pinned TensorFlow 2.21
`BUILTIN_REF` semantics: FC accumulates integer products, then applies the
reference float64 scale and ties-away rounding. SOFTMAX is an isolated one-op
TFLite subgraph fed those computed logits. It cannot invoke the original graph
or obtain earlier activations. The independent whole-model interpreter is
consulted only for validation, after a runtime completion.

The reason for the CPU FC treatment is reproducible: `tst_000012_Go_1.bin`
produced FC class-8 logit −46 with gemmlowp requantization versus −45 with this
reference resolver. The final predicted class happened to match; comparing
only labels would have missed the semantic difference. Official implementation:
[FC dispatch](https://github.com/tensorflow/tensorflow/blob/v2.21.0/tensorflow/lite/kernels/fully_connected.cc),
[FC reference overloads](https://github.com/tensorflow/tensorflow/blob/v2.21.0/tensorflow/lite/kernels/internal/reference/integer_ops/fully_connected.h).
This head must not be described as an all-integer accelerator implementation.

## Graph persistence and bounded liveness

There are six durable stages: first conv; four fused DW/PW pairs; CPU head.
Stages 0–4 contain 8,000 INT8 output bytes; stage 5 contains 12 output bytes.
Jobs advance an NHWC linear frontier. Allowed geometries are 1 pixel × CO16,
1 × CO64, 4 × CO64 and 8 × CO64, with truncated spatial tails. CI chunks are
16 or 64; intermediate DW and INT32 PS can be saved independently.

Persistent allocation is bounded rather than growing with completed jobs:

| Reservation | Bytes |
|---|---:|
| Two alternating immutable layer logs | 140,000 |
| Two scratch slots and scratch frontier byte | 8,193 |
| Two graph-root slots and root frontier byte | 513 |
| Pinned model blob | 53,936 |
| Current immutable feature input | 490 |
| Descriptor/runtime reservation | 4,096 |
| Total | 207,228 |

Each log holds at most 500 records of 124-byte header + 16-byte output, exactly
70,000 bytes in the smallest geometry. A larger tile uses fewer records.
Only the currently served feature is in this target NVM reservation. The
benchmark arrival queue is external; acquisition, buffering of queued sensor
samples and delivery into immutable feature storage are excluded. Do not
interpret this as a complete embedded sensor acquisition pipeline.

Scratch slots reuse the G4 binary-v1 format and ordering: invalidate inactive
marker → payload → header → publish marker → output frontier ACK. Full model,
feature/invocation and descriptor identities are checked; CRC32 covers metadata
and payload. Each arrival has a separate invocation identity even when feature
bytes repeat. PS and channel prefix are restored together from real NVM bytes.

After scratch output becomes durable, an immutable output record is appended to
the destination log. A root record publishes a complete stage plus its SHA-256
digest. Only after this root is durable may the next stage overwrite the log
of the stage before the current source. A torn newer root preserves the old
source log. A published scratch output with an interrupted log copy is copied
again after recovery. These graph log/root operations are a **new simulated
software protocol**, not an already verified G4 RTL controller.

Recovery validates the root, checks/reconstructs its full source log, scans the
next destination prefix and restores any matching scratch job. Invalid or torn
unpublished suffixes are unfinished. A valid root with corrupt source fails
closed. Fault assumptions remain atomic old-or-new bytes, persistence ACK,
ordered operations, and no delayed post-reset writes; physical FRAM behavior
and CRC collision resistance are not established.

The algorithm buffer bound includes one resident source anchor, streamed 2 KiB
bank, tile DW/PS/output, header and control reservations. The previous anchor
dies before the next anchor is loaded. NumPy arrays used to inspect NVM are host
semantic views, not a second embedded output arena. This is a logical buffer
bound only: no compiled CPU stack, TFLite Micro arena or RTL memory mapping has
been measured. Host-only DW memoization is keyed by actual source bytes and
never removes a simulated load, computation, replay cost or elapsed time.

## Policy and fairness

- `B1_layer`: first conv/DW-PW stage checkpointing. It writes output records,
  but ignores an unfinished stage prefix after a loss and restarts the stage.
  It does not pay per-tile scratch publication.
- `B2_fixed`: 1 pixel/CO16, CI64, no intermediate save.
- `B3_adaptive`: causal minimum estimated time per output, adapting spatial
  extent, CO, CI and intermediate flags over the same candidate set as RECAP.
- `RECAP`: causal minimum estimated energy per output over that candidate set.
  A present-energy reserve fraction influences selection; it is fitted only
  on train/validation. B3 receives the same reserve candidates and fitting
  opportunity. A matching durable partial job resumes before selecting a new
  geometry. Neither policy reads the future source trace.

All methods share input sequence, source/capacitor, traffic coefficients,
arithmetic, persistence primitive and queue/deadline treatment. Their loads
can cause different capacitor trajectories and loss times. B1 has its intended
coarser durability, and B2 its intended fixed geometry; they are not substitutes
for the stronger B3 comparison.

Admission uses current reservoir energy plus a numerical reserve, without
crediting future harvest. Source integration is piecewise constant and couples
to actual load. Each admitted work/commit unit must finish without depletion;
depletion is an assertion failure. Waiting with volatile state uses an assumed
1 µW retention load and can deplete, triggering cold recovery. Cold charging
and inactive periods use the explicitly assumed zero off-state load. Main
results do not inject arbitrary failures. Diagnostic faults separately
discharge the reservoir and include that energy in their ledger.

## Overhead and metric boundary

All joules and seconds are **assumed**, inherited from the G2 debug model with
G3 DW energy ×30, plus preregistered CPU/controller/decision/retention costs.
There is no calibrated CIM macro, PPA or board measurement. Weight-load read
cost is an aggregate assumed transfer cost; analog programming and separately
characterized CIM bank-write energy are not available. No weight-residency
benefit is claimed.

Every tile/log/root pays actual byte counts. G4 commit cycles contribute
`2L + 246 + is_output`; modeled byte service replaces the bus-transfer cycles,
and only nonbus controller cycles extend elapsed time. Controller energy also
accrues through assumed bus waits, separately reported. Root/log integration,
parser budget, identity hashes, CPU head and decisions have assumed budgets,
not measured software instruction traces. Boot reads both root/scratch slots,
source restoration and destination scan; next anchors and weights are charged.
Full-network wall time is an event model, not cycle-accurate CPU/accelerator RTL.

`RECAP_no_control` retains frozen policy parameters, all metadata and NVM traffic,
but removes assumed controller and decision time/energy. Its causal schedule
can therefore change. It is a system ablation, not a hardware measurement or
an isolated subtraction of byte energy. The reported `checkpoint_path`
fraction includes checkpoint/log/root, destination scanning and root/scratch
reads. It excludes general boot, `restore_source` and next-anchor loads;
it is not the total recovery overhead. It overlaps the control-energy group.

Each 4 s source trace contains three arrivals. Completion requires the exact
12-byte output and a committed final root. Energy per completed inference uses
**all** consumed energy, including partial/replayed/unfinished work. A zero
completion denominator stays null. Incomplete/failed latency is infinity and
participates in nearest-rank p95. Completion and on-time constraints use 5
absolute percentage points; the preregistered energy target is 20%.

Input splits are grouped by identical feature SHA-256 so duplicate features
cannot cross tuning/test. Power seeds are fresh relative to G3. Baseline and
mapper are fitted on train/validation, then parameters, code, model, scenarios
and split hashes are saved before test begins. The paired stratified bootstrap
resamples independent trace seeds, keeping all three arrivals together;
undefined bootstrap denominators suppress the unconditional energy CI.
