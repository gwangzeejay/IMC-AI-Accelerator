# G8: redo-aware ranking and direct durable output publication

Date: 2026-10-23. Baseline implementation/evidence G2-G6 stays byte-for-byte
unchanged. G8 extends the Python runtime in `g8_runtime.py`; it is not a
replacement for the historical G6 claim set.

## Execution and output contract

- Pretrained KWS and VWW INT8 models and the isolated reference CPU head are
  unchanged. Every completed inference is compared against whole-model output.
- All five G8 policies share `Store.log_ops`: invalidate record, write payload,
  write header bytes 1..123, then persist the atomic 0xA5 marker. Scan accepts
  only the longest correctly identified and CRC-validated output prefix.
- The default path omits the separate scratch-output record. Partial DW/PS
  checkpoint slots remain available. A crash before log publication replays
  the unfinished tile; a crash after publication resumes from the durable log.
- Layer-log publication of L output bytes writes L+125 bytes; there is no
  extra scratch frontier byte. Graph-root publication remains copy-on-write.
- This still assumes byte atomicity, persistent acknowledgments and no
  delayed writes crossing reset. A physical FRAM adapter is not implemented.

## Approximate expected-redo ranking

For a candidate tile, separate DW execution, optional saved-DW prologue, PW
segments, intermediate saved-PS records and final durable output publication.
At intermediate boundary i, use `q_i = 1-exp(-lambda * t_i)`, with lambda
fixed in the protocol. Let c_i be segment compute plus checkpoint energy and
r_i approximate boot, restore-read and missing-DW replay energy.

For the final segment: `E_last = c_last`. For an intermediate segment:

`E_i = c_i + (1-q_i) E_(i+1) + q_i (r_i + E_restart)`.

After an acknowledged PS checkpoint, `restart=i+1`; otherwise `restart=0`.
The implementation solves the resulting affine renewal equation. Initial DW
and optional DW checkpoint are added once outside that equation. Saved DW
removes its recomputation term from r_i but still pays restore reads.

Only the ranking uses this expectation. The load ledger charges actual
executed read/write/compute/boot/replay work; expected energy is never added
to measured-in-the-model execution totals. Unit tests compare the recurrence
against an independent linear-system oracle and verify a save/replay crossover.

Limitations: losses are approximated at segment boundaries; final publication
can tear in the actual simulator but has no final renewal-loss window in the
ranking. Cold reload/residency and boot-scan costs are simplified. The fixed
hazard is not a calibrated predictor, a probability learned from test traces,
or proof of a globally optimal mapper. The code never inspects future reset
times or future harvested power when choosing a candidate.

## Common-backend controls

| Method | Mapping/ranking | Intermediate state |
|---|---|---|
| B1_layer | Fixed legal geometry and CI64, nominal time | No DW/PS state; layer progress replayed on reboot |
| B3_adaptive | Feasible tile/chunk candidates, nominal time | Same candidate space, naturally pays checkpoint cost |
| B4_periodic | Nominal-energy mapping with development-selected CI16/64 interval | Saves PS at every nonfinal interval; no saved DW |
| RECAP_nominal | Same common candidates, nominal energy | Save/replay candidates included without redo benefit |
| RECAP_redo | Same common candidates, expected energy above | Selects DW/PS state using the declared approximation |

B4 is a local periodic-checkpoint control, not a reproduction of the Chime
optimization algorithm or of CIM-Tuner. Its interval is chosen using only
development runs; no G8 test result selects it. A nearest-literature optimized
baseline remains open.

## Reset model and conservation

G8 adds predetermined absolute-time rail disconnects, identical for all methods
on a given scenario. They can interrupt admitted work or tear a byte transaction.
The source integrator handles these events; the mapper cannot access them.
Discarded capacitor charge is recorded in reservoir `spilled`, separately
reported as `discarded_capacitor_energy_j`, and excluded from inference-load
energy. Natural retention brownouts remain enabled. An admitted unit depleting
without an exogenous reset still raises an error.

## Fresh experiment boundary

Protocol G8_1.1 uses 24 s horizons and arrivals 0/8/16 s, common 64 KiB SRAM
and 2 MiB NVM budgets, new source/reset seeds and a feature pool disjoint from
prior G5/G6 runtime use. VWW adds 24 source images: four development and twenty
reserved holdout. These images are a small research-preprocessed subset.

The aborted G8_1.0 integration run exposed a fixed-B1 NHWC geometry bug. It is
marked invalid; G8_1.1 uses new source/reset seeds after a regression fix, with
no policy tuning. Its reserved image/feature pool was reused after that failed
integration, so it is not described as never previously executed.

The declared matrix contains 28 scenarios/workload/method: 16 stochastic,
four steady/zero controls and eight exogenous-reset cases. Five methods and two
workloads yield 280 main rows. Five preset interventions on six scenarios,
two workloads and two methods add 120 secondary rows. Main and secondary
results stay separate. G6 and G8 percentages must not be mixed because the
protocol and publication primitives changed.

## RTL boundary

`04_RTL/g8/recap_output_log_commit.sv` implements only the direct publisher,
with a 32-bit destination address and host-provided encoded header/payload.
It holds a write request stable under backpressure. It does not generate CRC,
execute a graph, drive SPI, measure energy or implement a physical CIM macro.
The RTL campaign tests every ACK cut of a 16-byte output at two stall modes,
plus zero-length and address-overflow rejection. Python independently decodes
durable images. Generic synthesis is reported separately from technology PPA.
