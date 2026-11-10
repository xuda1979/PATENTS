# v4 device-counter evidence — ASI3, 2026-11-10

## What this is

Parsed HBM/main-memory and L2-cache device counters for the v1
(single-core) versus v4 (multicore) `ephemeral_core_apply` kernels,
closing the "no parsed v4 device-counter evidence" blocking gap from
`results/journal_revision_20261022/evidence_audit.json`.

## How it was collected

- Host: ASI3 (Ascend 910B2 x8), NPU 0, CANN 8.5.0, torch 2.9.0 + torch_npu.
- Harness: `profile_v4_device_counters.py` (in this directory), companion to
  the hardened `test_v4_multicore_v3.py` (md5 526839744b6c2916822b3a1a9387609f).
  Identical geometries (probe_T128, large_T512..T4096), identical input
  construction (ctrl fp32 [T,H]; head_w fp32 [H,R]; head_b fp32 [R];
  act fp16 [T,R]; amp 0.05; seed 1234).
- Profiling: `torch_npu.profiler.profile` with
  `_ExperimentalConfig(aic_metrics=AiCMetrics.Memory, l2_cache=True)`;
  30 warmup + 50 profiled iterations per arm per geometry.
- Parsing: `extract_v4_counters.py` (in this directory) joins
  `ge_summary` (kernel names), `metric_summary` (aic main-memory = HBM
  read/write bandwidth, cycles), and `l2cache` (per-task hit rate) from
  the CANN profiler sqlite exports.

## Key numbers (see `v4_device_counters_parsed.json` for full record)

Host timing (medians, synchronized) reproduces the archived 2026-11-08
record within noise: T4096 speedup 2.972x here vs 2.97x archived;
T2048 2.200x vs 2.22x archived; T128 1.103x vs 1.35x (small-T noise).

Parsed device counters (50 profiled iterations per arm, per kernel):

| Geometry | Kernel | aic HBM read BW (GB/s) | aic HBM write BW (GB/s) | L2 hit rate |
|---|---|---|---|---|
| T2048 | v1 | 0.138 | 0.589 | 0.99997 |
| T2048 | v4 | 0.113 | 0.384 | 0.99994 |
| T4096 | v1 | 0.137 | 0.594 | 0.99998 |
| T4096 | v4 | 0.114 | 0.426 | 0.99997 |

Interpretation boundaries (kept consistent with the manuscript):

1. Both kernels are effectively L2-resident at these geometries
   (hit rates ~0.9999), so the speedup is not explained by a change in
   L2 residency class at these probe sizes.
2. The v4 kernel issues measurably lower HBM write bandwidth per task
   (0.38-0.43 vs 0.59 GB/s at T>=2048), consistent with its multicore
   epilogue restructuring; the counters support the traffic-attribution
   story but do not by themselves establish whole-model gains.
3. The bandwidth columns are per-task rates under the profiler's
   sampling; they are attribution evidence, not a full traffic budget.

## Known artifacts and claim boundaries

- The one-shot v1-vs-v4 equivalence check in the profiling harness
  observed the documented 910B2 v1 transient corruption at T512/T4096
  (`max_abs_diff: nan` in `v4_profiling_host_record.json`): v1 produced
  non-deterministic NaN outputs on 2 of 3 repeat trials with `randn`
  inputs (fp16 overflow windows in the unmodulated reference path),
  while v4 stayed finite. This v1 transient is exactly the failure
  family the hardened v3 harness gates (H1) and is documented in
  `results/v1_v4_ref_corruption_diag9v2_20261008.md`. The canonical
  v4 numerical evidence remains the 2026-11-08 hardened record
  (1000/1000 calls, final max error 0.00390625 vs CPU truth,
  v1-vs-v4 bit-identical on clean gates).
- Device counters were collected with the kernel executing normally;
  the counter rows themselves are unaffected by the output corruption
  (traffic still moves). Counter evidence supports traffic attribution
  only.
- No trained-model or whole-FFN claim is made from this record.

## Provenance

- Run: 2026-11-10T17:16Z, ASI3, pid 150797 (`/tmp/v4_profile.log`).
- Libraries: v1 `/root/work/mwg_torch_ext/build/libcustom_ops.so`
  (Oct 2 build, md5-recorded in earlier audits); v4
  `/root/work/mwg_v4_torch_ext/build/libcustom_ops_v4.so` (Nov 8 build,
  the binary verified by the 2026-11-08 hardened sweep).
- Raw CANN exports retained on ASI3 under
  `/root/work/export_only_prof_dir/*_150797_*_ascend_pt` (10 trees).
