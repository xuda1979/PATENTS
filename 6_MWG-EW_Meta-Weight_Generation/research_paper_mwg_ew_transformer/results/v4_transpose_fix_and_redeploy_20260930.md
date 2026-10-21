# v4 Transpose Fix and ASI3 Redeploy — 2026-09-30

## Summary

Pre-deploy audit of the pending ASI3 v4 multi-core benchmark found and
fixed a host-wrapper weight-transpose bug that would have failed the
decisive v4-vs-v1 equivalence check and wasted the next scarce device
window. The fixed kernel and test are deployed to the ASI3 mirror and a
fresh 48-hour watcher is running.

## State at session start

- 2026-09-29 18:10 UTC: the deployed watcher fired on ASI3; the v4 kernel
  **built successfully** (`libcustom_ops_v4.so`, CMake + ASC flow clean).
- 2026-09-29 18:12 UTC: `test_v4_multicore.py` aborted rc=3 with a false
  "shipped v1 returned NaN" alarm at probe_T128. The qwen SFT trainer
  held the NPU at that moment; the test's own `head_weight` convention
  mismatch ([R,H] reference vs the shipped [H,R] kernel contract) was
  identified in commit d48b243 and fixed locally — but never redeployed.
- The watcher had already fired once and exited (fires-once design), so
  nothing was scheduled to rerun with the fixed test.
- ASI3's HTTP egress proxy 403-blocks the S3 relay (confirmed again in
  the 09-28 run log: `CMakeLists_v4 pull rc=1`, "Forbidden"), so
  launcher-time rclone pulls fail; the working deploy path is the local
  chunked uploader (`scripts/asi3_chunked_upload.sh`).

## Bugs found this session

1. **v4 host-wrapper transpose (critical, would invalidate the rerun).**
   `ephemeral_core_apply_v4_multicore.asc` line ~398:
   `b_f16 = head_weight.t().contiguous().to(at::kHalf)` while the
   matmul tiling declares `isTrans=false` and both the shipped v1
   kernel and the [H,R] reference use `head_weight` directly. v4 would
   have computed `ctrl @ W^T` — proven in pure PyTorch to yield
   max_err 0.4762 at the probe geometry, 95x the 5e-3 equivalence
   threshold. Root cause: the stale v1 header comment ("head_weight is
   transposed by the host to [R, H]") contradicts v1's own
   implementation and was evidently carried into v4 as an actual
   `.t()`. Fix: use `head_weight.contiguous().to(at::kHalf)` directly.

2. **Test caller shape (latent).** `test_v4_multicore.py` created
   `head_w = torch.randn(R, H)` at two call sites while the reference
   docstring and kernels expect `[H, R]`. Latent only because all five
   probe configs are square (H=R=128); fixed to `torch.randn(H, R)`.
   Same trap class as the 09-29 false-NaN abort.

## Numerical validation (pure PyTorch, local)

- Buggy v4 path vs v1: max abs output err **0.4762** (FAIL at 5e-3).
- Fixed v4 path vs v1: **bit-identical** logits (`ctrl @ W + b`).

## Deployment state (verified)

| Artifact | md5 | Where |
|---|---|---|
| `ephemeral_core_apply_v4_multicore.asc` | `5d97876118e41ee20a5bcf2bc4dcd311` | local, S3 relay, ASI3 mirror (chunk-upload VERIFIED) |
| `test_v4_multicore.py` | `299479483b28341477ce46c1e1e2296d` | local, S3 relay, ASI3 mirror (chunk-upload VERIFIED) |
| `watch_asi3_v4_when_free.sh` | `021a470bfa8c29bad9a0bd24a91b8f88` | local, S3 relay, ASI3 mirror |
| `launch_asi3_v4_build_benchmark_detached.sh` | `1d296e54d4282d40e9c0d44a15d410d6` | local, S3 relay, ASI3 mirror |

- Stale pre-fix watcher (pid 107087) killed; fresh watcher started
  (pid 107977, 2026-09-30 ~11:00 UTC), 48h deadline, 300s poll.
- Watch log confirms: "trainer still running; sleeping 300s" — qwen
  SFT holds the NPU; watcher will fire the build+benchmark when free.
- The launcher rebuilds the `.so` from the mirror's fixed `.asc` at
  fire time, so no stale binary can be reused.

## What to check next session

1. `results/v4_watch.log` + `results/v4_asi3_run.log` on the ASI3 mirror
   for the fire event and the five-probe benchmark JSON.
2. `results/v4_multicore_benchmark.json` for v1/v4 medians, speedup, and
   the 1000-call stability check at T=4096.
3. If passed: propagate measured v4 numbers into the paper's v4 sections
   (`iclr_parts/systems.tex` summary + `appendix_b.tex` full design),
   flipping "unmeasured design analysis" to measured claims, and
   rebuild all three PDFs.
4. If the v4 equivalence fails for a real reason (e.g. fp16 rounding
   at non-square geometry), capture per-config max_err before changing
   anything.

## Commit

- `20d29b4` Fix v4 host-wrapper weight transpose that would have failed
  the decisive rerun (kernel + test, with the numerical proof above).
