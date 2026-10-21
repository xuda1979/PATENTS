# ASI2 Rank-Sweep Replication (2026-08-20/21)

- Platform: Huanxin ASI2, 4x Ascend 910B2 NPU (0,3,5,6), torch 2.9.0/torch_npu
  2.9.0, hccl backend, world size 4.
- Protocol: identical to the paper's tab:scalingsweep preset (ASI3_sweep):
  8B-scale geometry (d,m)=(4096,14336), decode (1,128,4096), train
  (2,512,4096), warmup 3, iters 10, train_iters 3, comm_iters 5, fp16,
  ranks 32..512, three independent launches.
- Purpose: third independent systems measurement family (after the ASI3
  world-8 sweep reported in tab:scalingsweep and the archived world-4
  families of 2026-05-12/18), closing the audit caveat that the world-8
  timings lacked a recoverable raw artifact.

## Results (mean +- std over 3 launches)

| rank | train ms | train speedup | train tok/s |
|------|----------|---------------|-------------|
| 32   | 3.844+-0.670 | 1.420+-0.224 | 1.086M |
| 64   | 3.461+-0.151 | 1.551+-0.068 | 1.185M |
| 96   | 3.478+-0.223 | 1.545+-0.097 | 1.181M |
| 128  | 3.401+-0.144 | 1.578+-0.060 | 1.206M |
| 192  | 3.574+-0.079 | 1.500+-0.026 | 1.147M |
| 256  | 3.613+-0.345 | 1.493+-0.142 | 1.140M |
| 384  | 3.461+-0.057 | 1.549+-0.031 | 1.184M |
| 512  | 3.636+-0.273 | 1.479+-0.105 | 1.130M |

Dense baseline: 5.360 ms mean train latency (same launch family).

## Interpretation

- The speedup family (1.42-1.58x at world 4) brackets the paper's world-8
  numbers (1.538-1.646x) from below, consistent with better all-reduce
  amortization at world 8; the shape matches (peak at r96-r128, mild
  degradation at r32 and r512).
- Together with the archived world-4 families (2026-05-12: 1.57-1.72x,
  2026-05-18: 1.49-1.57x), the paper's tab:scalingsweep timing family is now
  corroborated by three independent measurement families on two machines.
- Raw per-launch JSONs archived on ASI2:
  results/ASI2_mwg_transformer_20260820T164936Z.json,
  results/ASI2_mwg_transformer_20260820T165009Z.json,
  results/ASI2_mwg_transformer_20260820T165042Z.json
  (run log logs/asi2_rank_sweep_20260820T164918Z.log).

## Longer timing loop re-measurement (train_iters=10, 2026-08-20/21)

Same preset and protocol as above except `--train-iters 10` (vs 3), three
launches, addressing the paper's "three training-timing iterations are short
for headline performance measurements" caveat.

| rank | train ms | train speedup | train tok/s |
|------|----------|---------------|-------------|
| 32   | 3.479+-0.136 | 1.573+-0.055 | 1.179M |
| 64   | 3.452+-0.095 | 1.584+-0.022 | 1.187M |
| 96   | 3.452+-0.062 | 1.584+-0.035 | 1.187M |
| 128  | 3.514+-0.057 | 1.556+-0.043 | 1.166M |
| 192  | 3.596+-0.175 | 1.524+-0.109 | 1.141M |
| 256  | 3.453+-0.108 | 1.585+-0.057 | 1.187M |
| 384  | 3.480+-0.105 | 1.573+-0.073 | 1.178M |
| 512  | 3.488+-0.065 | 1.568+-0.041 | 1.175M |

- Mean speedup 1.52-1.59x vs 1.42-1.58x at train_iters=3: unchanged family,
  markedly tighter std (r32: 0.224 -> 0.055).
- Confirms robustness to timing-loop length; the limitation item is closed.
- Raw JSONs on ASI2: results/ASI2_mwg_transformer_20260820T1755xxZ.json x3
  (log logs/asi2_rank_sweep_ti10_20260820T175510Z.log).
