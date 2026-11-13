# Complete-FFN five-arm v4 latency sweep — ASI3, 2026-11-12

## What this is

First validated **complete-FFN** latency sweep comparing five arms
(dense / persistent low-rank / materialized core / fused v1 single-core /
fused v4 multicore) on a realistic FFN geometry (d=4096, m=14336, rank=128,
fp16, Ascend 910B2), extending the kernel-only 2026-11-08 v1-vs-v4 record
(`results/v4_multicore_benchmark_asi3_v3_20261108.json`) to the full
FFN computation the manuscript's Table~\ref{tab:v1} timing boundary uses.

This closes the "v4 speedup is only demonstrated at the isolated-kernel
level, not on the complete FFN path" gap: at T>=1024 the v4 complete-FFN
arm is faster than the v1 fused arm (1.15x at T1024, 1.32x at T2048,
1.47x at T4096 median-of-repeats host wall-time), while all four
numerical validations pass at every geometry.

## Local files

- `sweep_summary.json` — per-geometry medians (ms) for the five arms and
  the four validation booleans. Byte-identical to the remote copy
  (md5/sha256 recorded in `provenance_digest.json`).
- `provenance_digest.json` — run configuration, arm semantics, backend
  contracts (binary sha256 for both op libraries), full remote-file
  sha256 digests, output-content sha256 per arm (T4096), timing protocol,
  claim boundary, and limitations.
- `README.md` — this file.

## Remote records (retained on ASI3, not in repo)

`/root/work/filestorage/mwg-ew-transformer-research/results/asi3_complete_ffn_v4_sweep_20261112/`:
- `five_arm_T{128,512,1024,2048,4096}.json` — full records (timing
  distributions with 5 repeats x 200 iters, per-validation max_abs /
  mean_abs / max_rel, arm-level backend contracts, output sha256,
  environment). sha256 digests in `provenance_digest.json`.
- `asi3_complete_ffn_v4_sweep_20261112.log` — sweep log.

## How it was collected

- Harness: `experiments/mwg_four_arm_lifetime_benchmark.py` (five-arm
  extension; the four-arm version is md5-recorded in earlier audits).
- First invocation failed **pre-timing** on a T-divisibility input
  validation at T=128 (batch/seq flatten); fixed by token-major layout
  and re-run clean. No timing numbers from the failed run are used.
- Timing: 30 warmup, 200 iters, 5 repeats, host wall-time with device
  synchronize; medians over repeats reported.
- Correctness gates at every geometry: dense-vs-persistent factorization,
  materialized-vs-fused, materialized-vs-fused_v4, fused-vs-fused_v4
  (rtol=atol=0.005; T4096 fused_vs_fused_v4 max_abs = 0.0 — exact fp16
  match between v1 and v4 kernels).

## Results (median ms, from `sweep_summary.json`)

| Geometry | dense | persistent | materialized | fused (v1) | fused_v4 |
|----------|-------|-----------|--------------|------------|----------|
| T128  (B1,S128)  | 0.460 | 0.290 | 0.908 | 0.914 | 0.998 |
| T512  (B2,S256)  | 1.014 | 0.286 | 0.936 | 1.053 | 1.042 |
| T1024 (B4,S256)  | 1.684 | 0.260 | 0.849 | 1.150 | 1.105 |
| T2048 (B8,S256)  | 3.317 | 0.438 | 0.950 | 1.596 | 1.210 |
| T4096 (B16,S256) | 6.127 | 0.879 | 1.414 | 2.680 | 1.826 |

## Claim boundary

- Synthetic factor-generated weights (amplitude 0.05, seed 1234) —
  representation/execution timing only, **not** a trained-model claim.
- Inference-only; no optimizer or gradient flow.
- `fused_v4` hardware counters for the complete FFN are not yet parsed
  (kernel-level HBM/L2 counters exist in
  `results/v4_device_counters_asi3_20261110/`); "no-store" attribution
  for the complete-FFN path remains unclaimed.
- Host wall-time with device synchronize; single NPU (NPU 0).
