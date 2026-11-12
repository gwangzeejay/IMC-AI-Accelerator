This G8_1.0 run was interrupted and is NOT valid evidence. It exposed a fixed
B1 geometry-contract bug: a CO64 tile of a CO128/256 VWW stage must use n=1,
not n=8, under the contiguous-NHWC layout. G8_1.1 fixes this correctness bug
and adds an all-stage VWW geometry regression. No method parameters were tuned
to these preliminary results. The replacement run uses fresh source/reset
seeds. The reserved input pool is reused after this integration failure; it
must not be described as never previously executed. G2-G6 are unaffected.
