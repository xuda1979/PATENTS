# ASI2 ref-corruption root cause + diag9 v2 all-pass (2026-10-08)

## Executive summary

The 2026-10-08 ~06:00 diag9 failure on ASI2 (S1/S5 err = 0.0810542106628418,
both ops, deterministic) was **not a kernel defect**. The NPU-computed fp32
reference tensor itself was corrupted. Two independent kernels (v1
single-core, v4 multicore) cannot produce bit-identical wrong output; the
shared artifact between them was the `ref` computed once in the CANN
lazy-init window. After hardening the reference computation with a
two-phase integrity gate, all five diag9 sections pass on the same device,
same binaries, ~1 hour later.

The 05:25 decisive benchmark abort (`v1_nan_device_wedged` at large_T512)
was the same class of transient: a mid-run NPU bad window hit either the
v1 output or the `algebraic_reference` matmul at large_T512. probe_T128
results from that run are valid (v1 0.1281 ms, v4 0.1182 ms, 1.083x
speedup, v1-vs-v4 bit-identical, max_err 0.001953 <= fp16 noise).

## Evidence chain

1. **asi2_pair_probe** (`results/asi2_pair_probe_20261008.json`):
   reproduced diag9's exact S1 sequence (load V1 then V4, seed-1234
   probe, ref, v1, v4, repeats) in both load orders. Result:
   NOT_REPRODUCED — v1_err = v4_err = 0.001079, v1_vs_v4 = 0.0, both
   pass. Rules out a two-lib interaction or persistent kernel defect.

2. **asi2_fresh_discriminator** (`results/asi2_fresh_discriminator_20261008.json`):
   CPU ground truth computed before any NPU work; NPU ref snapshots
   compared against it per sequence:
   - seqA (diag9 order, immediately after load): all pass, v1 = v4 =
     CPU truth within fp16 noise (0.00108), NPU ref = CPU truth (2.4e-07).
   - seqB (fresh tensors after 10 op calls): NPU ref2 still = CPU truth
     (2.4e-07) but BOTH ops wrong vs CPU truth (v1 0.1529, v4 0.1513)
     AND diverging from each other (0.193) — a live mid-run bad window
     (the ops' internal fp16 casts are separate NPU ops).
   - seqC (after 5 more calls): v1 NaN vs CPU truth, v4 recovered.
   This catches the transient red-handed: inputs and ref provably
   correct on device, kernel outputs wrong, self-healing.

3. **diag9v2** (`results/diag9v2_asi2_20261008.json`, remote md5
   54cc272bbd83a512dc0767f872387969): diag9 with a two-phase ref
   integrity gate (compute ref twice, require bit-identical, retry to
   8x). All refs converged at attempt 1 with delta 0.0; S1-S5 all pass;
   every v1-vs-v4 delta 0.0 (bit-identical) including the T sweep
   {64,128,192,256,512,2048} and v4 multicore T=1024. Overall PASS at
   07:06Z.

## Root-cause model (updated)

The verified-warmup fix (2026-10-02) absorbs the first-call-per-thread
bad-launch streak. But ASI2 exhibits **recurrent, runtime-global NPU bad
windows** where arbitrary NPU ops (matmul, dtype casts, custom kernels)
transiently return wrong-finite or NaN results, self-healing after 1-3
launches. These windows can occur mid-run (seqB/seqC above; the 05:25
large_T512 NaN). Reference tensors and op outputs are equally exposed.

Mitigations now in place:
- diag9v2's two-phase ref gate (ref recomputed until bit-stable).
- The 05:25 aborted decisive artifacts are preserved
  (`*_aborted0525.*`) and probe_T128 from that run remains valid
  evidence.
- A detached watcher (`/tmp/asi2_decisive_watcher.sh`, PID 6679 on
  ASI2, started 07:23Z) polls the device-free gates every 30 s and will
  auto-run `scripts/asi2_v4_decisive_worker.sh` when the user's
  holdout/rubric-eval workloads finish (8 tenant processes were running
  at 07:15; watcher max wait 12 h).

## Binary provenance (unchanged from 2026-10-02 ledger)

- v1 `libcustom_ops.so` md5 `e7c377c6f4f6f8202fc983e9d732c72d`
- v4 `libcustom_ops_v4.so` md5 `1659bbe61f85e10d88f240a89843f036`
- Both binaries contain the verified-warmup string; sources verified by
  the decisive worker's Gate 2 (v4 source 701e9be0..., v1 source
  59cf1751...).

## Files

- `results/diag9v2_asi2_20261008.json` — hardened diag9, ALL PASS
- `results/asi2_pair_probe_20261008.json` — S1 non-reproduction probe
- `results/asi2_fresh_discriminator_20261008.json` — transient caught live
- `results/diag9_asi2_20261008_refcorrupt.json` — original failing diag9
- `results/v4_asi2_decisive_20261008_aborted0525.log` — 05:25 abort log
- `results/v4_multicore_benchmark_asi2_20261008_aborted0525.json` — 05:25 partial results
- Remote only: `/tmp/diag9_v2_asi2.py` (hardened script, md5
  5505774a97ec7f5433ad0684cf28030d), `/tmp/asi2_fresh_disc.py`
  (md5 c05c8594a38e218b8b43f387ed9e2d3e), `/tmp/asi2_pair_probe.py`
  (md5 070d798e5f9f5c196561b492635a7313)

## Addendum (08:54Z): second decisive abort + T512 NaN isolation

The first watcher fired at 07:43Z when the device freed; the worker
rebuilt v4 and the test **aborted identically** — `large_T512 v1
max_err = nan` at 07:45:40 (3rd occurrence: ASI3 2026-09-29, ASI2
05:25, ASI2 07:45). Artifacts: `*_aborted0745.*`. probe_T128 again
valid (v1 0.1305 ms, v4 0.1220 ms, 1.070x, v1-vs-v4 bit-identical).

Isolation (4 probes, all archived in `diag10_ref_corruption/`):

1. `nan_attribution_probe.py` — full T128 benchmark then T512 with
   per-tensor NaN attribution vs CPU truth: 5/5 reps clean (v1 err
   0.0039). (An initial version had a truthiness bug in the
   inputs-NaN check; fixed and rerun.)
2. `exact_data_probe.py` — the test's exact seed-1234 data and
   generation order (ctrl, w, b, act), synced calls: 3/3 reps clean
   (v1 err 0.00195).
3. `async_pileup_probe.py` — exact `benchmark_op` (30 warmup + 200
   unsynced iters x 5 reps, host perf_counter) then T512: clean.
4. Timing: every failing test started < 60 s after a heavy v4
   rebuild (make -j); every passing probe ran hours after the last
   build. Host memory/page-cache pressure from the build is the
   remaining common factor.

Conclusion: the T512 v1-NaN is an environment-level transient in the
same family as the diag9 ref corruption — not deterministic in
sequence, data, or call pattern, and never reproduced in isolation.

Hardened rerun path (deployed, waiting on device):
- `test_v4_multicore_v2.py` (md5 582470c5452ccdf7680370d628b29961):
  identical methodology/configs/tolerances, plus H1 gated-ref
  (recompute-until-bit-stable), H2 NaN attribution vs CPU truth
  before any abort, H3 per-config 3x retry; aborts only on persistent
  op-attributed failure.
- `scripts/asi2_v4_decisive_worker_v2.sh` (md5
  002550def2bd737e8283d64f74f9c3b3): same gates/rebuild + 60 s
  post-build settle.
- v2 watcher started 08:54:07Z (remote
  `/tmp/asi2_v2_watcher.log`), auto-runs when the device frees.
