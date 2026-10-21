# ASI1 World-1 Benchmark Sweep (2026-08-21)

- Platform: Huanxin AI1, single Ascend 910B2 NPU, **torch 2.7.1/torch_npu
  2.7.1** (vs 2.9.0 on the ASI2/ASI3 systems families).
- Protocol: identical ASI3_sweep preset, ranks 64/128/256, three launches,
  world size 1.
- Purpose: fourth-environment + cross-torch-version confirmation of the
  training-speedup family.

## Results (mean +- std over 3 launches)

| rank | train speedup | train ms |
|------|---------------|----------|
| 64   | 1.445+-0.123  | 3.424    |
| 128  | 1.468+-0.101  | 3.363    |
| 256  | 1.473+-0.097  | 3.352    |

## Comparison

- ASI3 reliability world-1 (torch 2.9.0): r64 1.475, r128 1.531, r256
  1.514. AI1 mean 1.46 vs ASI3 mean 1.51 — within run-to-run noise
  (per-launch std 0.10-0.12); direction and magnitude reproduce across
  software stacks.
- Paper updated: systems section now notes the AI1 world-1 confirmation;
  compiles clean.
- Raw JSONs on AI1: results/*2026082*_AI1.json x3 (env_label AI1);
  run log logs/ai1_world1_20260821T*.log.
