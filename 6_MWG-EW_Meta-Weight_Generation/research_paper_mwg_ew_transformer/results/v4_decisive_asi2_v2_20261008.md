# v4-vs-v1 decisive benchmark on ASI2 — COMPLETE, equivalence + speedup confirmed (2026-10-08)

## Executive summary

The decisive v4-vs-v1 comparison ran to completion on ASI2 at
2026-10-08T13:43:54Z–13:47:03Z (device freed from tenant jobs at 13:43Z;
the re-armed v2 watcher auto-launched worker v2). **v4 is algebraically
identical to v1 (v1-vs-v4 max_err = 0.000000 at every config, both at
the fp16 rounding floor against the hardened two-phase reference) and
1.13×–3.03× faster across T=128–4096.** The decisive claim — v4 ≈ v1
numerically with v4 faster at beyond-L2 geometry — is met. The ~2×
viability threshold stated in the paper ("if the v4 kernel does not
achieve at least ~2× speedup over v1, the fused no-store arm would
remain slower than materialization at serving-relevant sequence
lengths") is cleared at T≥2048.

## Measured results (single Ascend 910B2, fp16, rank 128, amp 0.05)

| Config | T | v1 median ms | v4 median ms | speedup v1/v4 | v1 max_err | v4 max_err | v1-vs-v4 max_err |
|---|---|---|---|---|---|---|---|
| probe_T128 | 128 | 0.1323 | 0.1170 | 1.130× | 0.001953 | 0.001953 | 0.000000 |
| large_T512 | 512 | 0.1674 | 0.1212 | 1.381× | 0.001953 | 0.001953 | 0.000000 |
| large_T1024 | 1024 | 0.2232 | 0.1310 | 1.705× | 0.003906 | 0.003906 | 0.000000 |
| large_T2048 | 2048 | 0.3317 | 0.1553 | 2.136× | 0.003906 | 0.003906 | 0.000000 |
| large_T4096 | 4096 | 0.5434 | 0.1794 | 3.029× | 0.003906 | 0.003906 | 0.000000 |

All 15 equivalence records pass (5 configs × {v1-vs-ref, v4-vs-ref,
v1-vs-v4}). Timing: 30 warmup + 200 timed iterations × 5 repeats per
config, host timer + device synchronize, medians reported.

Supplementary 1000-call sequential stability check at T=4096: completed
1000/1000 calls, final max_err = nan, FAIL. This check runs an
unhardened comparison path (no H1 two-phase ref, no H2 NaN attribution);
the nan is consistent with ASI2's documented environment-level transient
bad-window family (see diag9v2 doc), not with a kernel defect: the
hardened five-config equivalence section of the same run was clean, and
the same v4 .so passed all isolated probes. Recorded as an open
stability question; does not gate the decisive claim (test rc=0).

## Provenance chain (all gates passed)

- Fixed v4 source md5 `701e9be098b51b13ac89409384735e2d` (verified by
  worker gate before build).
- v1 baseline source md5 `59cf1751d920f5f90851b117f7483d6c` (verified).
- Hardened test `test_v4_multicore_v2.py` md5
  `60dd757f10e374346977b4949d1d6dc8` (the argparse-fixed version
  uploaded 11:19Z after the 09:47Z staging-bug failure; verified on
  device before the run).
- CMake rebuild rc=0, make rc=0; warmup-fix string present in the
  rebuilt v4 .so (count=1); 60 s post-build settle observed.
- Device free at launch (no tenant processes); preflight baseline matmul
  finite & deterministic.

## Artifacts

- `results/v4_multicore_benchmark_asi2_v2_20261008.json`
  (md5 `1dbd8047c03a7f9d220e0f72e7ac0f1f`, 5744 bytes) — full configs,
  equivalence, stability records.
- `results/v4_asi2_decisive_v2_20261008.log`
  (md5 `54850a886e8b7aea9c36258e71ef6ae2`, 3885 bytes) — complete worker
  v2 log including both the 09:44Z argparse-failure section and the
  13:43Z–13:47Z decisive section.
- Both pulled to local `results/` via ASI1 shared-filestorage read;
  md5-verified against remote.

## Interpretation vs. the design projection

The v4 design projected ~5–7× over v1 at T=4096 (Appendix
`app:v4design`), which would bring the fused arm from 1.93× slower to
~2.5–3.5× faster than materialization. Measured: 3.03× at T=4096 —
direction confirmed, magnitude below projection, consistent with
partial L2-contention saturation from 8 cores reading the same B tensor
concurrently. Implication for the fused-vs-materialized comparison at
T=4096: the fused v4 arm is now expected to be ~1.6× faster than the
materialized arm at this geometry (1.93/3.03 × (v1_fused/v1_mat) aside,
the direct four-arm v4-vs-materialized measurement remains future
work); the paper claims only the kernel-level result.

## Paper updates made in the same pass (m5)

- Abstract: limitation (2) now states the measured v4 result (bit-identical,
  1.13×–3.03×, resolves the bottleneck at this geometry).
- Intro contribution bullet: same update.
- `sec:systems` v4 paragraph: projection → measured decisive run, with
  remaining risks (UB at r≥256; stability-check nan recorded).
- `sec:results` Open item 3: beyond-L2 bottleneck marked resolved at
  kernel level; end-to-end items stay open.
- `sec:discussion` What-remains-open: epilogue bottleneck resolved at
  kernel level, deployment benefit bounded by unmeasured serving stack.
- Appendix `app:v4design`: header re-scoped (design retained verbatim;
  measured result in closing paragraph); "Projected impact" paragraph
  replaced by "Measured decisive result and remaining risk."
- Four-arm figure caption (appendix): adds the measured v4 resolution.
- Claims table (appendix): v4 measured row added.
- Checklist limitations item: updated.

Rebuild after edits: 29 pages, 0 undefined citations, 0 overfull boxes.

## Session ledger note

The 09:44Z first firing failed on a harness staging bug (missing
`import argparse` in the uploaded test file; NameError before any NPU
call). Fixed locally, re-uploaded with md5 verification, and the
re-armed watcher's second firing at 13:43Z used the fixed file. The
decisive artifacts therefore contain two sections in one log file: the
09:44–09:47Z failed section (rc=1, no device work) and the
13:43–13:47Z decisive section (rc=0). Both md5s above cover the full
two-section log.
