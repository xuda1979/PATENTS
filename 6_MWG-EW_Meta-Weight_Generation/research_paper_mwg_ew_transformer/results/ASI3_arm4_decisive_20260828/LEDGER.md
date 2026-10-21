# Decisive four-arm experiment — final ledger (2026-08-29)

## Status: COMPLETE. The review's minimum-package item 1 is measured end-to-end.

## Deployed artifact identity
- Kernel: custom_ops/ephemeral_core_apply/torch_ext/ephemeral_core_apply.asc
  md5 740e7411830b8756a04823d201f6d5fc (local == deployed on ASI3 host)
- Build: CANN 8.5, MAKE_RC=0, SMOKE PASS (functional NPU check + hash-bound
  contract manifest regeneration), final build log makeFINAL.log
- Contract: mwg::ephemeral_core_apply manifest (source+binary SHA-256),
  harness rtol=atol=5e-3

## Headline measured results (Ascend 910B2, fp16, seed 1234)
| Geometry | Validation | Dense | Persistent | Materialized | Fused (shipped) |
|---|---|---:|---:|---:|---:|
| B=1,S=128 (probe) | PASS (both) | 0.470 | 0.258 | 0.864 | **0.865 ms** |
| B=16,S=256 (T=4096) | PASS | – | – | 1.371 | 2.644 ms |

- Probe: fused == materialized at parity (medians within +/-2% across runs;
  the pre-optimization 1.45x deficit was host overhead, not device cost).
- Large-T: 1.93x, stable across five independent runs; cause isolated to
  the single-core epilogue by matched msprof passes (the ephemeral kernel's
  DRAM traffic is output-only — the no-store property is directly visible).

## Counter evidence
All four predeclared families (Memory, L2Cache, PipeUtilization,
ArithmeticUtilization) collected on matched arm-3/arm-4 passes at both
geometries. energy_joules/occupancy_percent are not exposed by these
msprof families on this CANN build — documented toolchain gap.

## What this proves
1. The no-escape/no-store mechanism is real and device-verifiable.
2. The fused ephemeral-core path has NO device-side penalty at
   L2-resident geometries once host work is amortized (parity measured,
   band-straddling 1.0x across repeated runs).
3. The scaling boundary (core > L2) is characterized, and its cause
   (single-core epilogue) is isolated with counter evidence; the v2 lever
   is identified (warp-tiled epilogue; the naive M-split and manual
   double-buffering attempts both failed with documented causes).

## Reproduction
bash scripts/run_arm4_asi2.sh  (builds, smoke-gates, runs harness)
Tests: tests/test_kernel_source_contract.py + 56 others (57/57 green).
Paper: tab:fourarmmeasured + Section "Four-arm protocol" discussion.
