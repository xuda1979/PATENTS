# ASI1 Lifetime Ablation (2026-08-13)

Reviewer-required systems control: dense vs persistent low-rank vs
generated+materialized at identical rank and compute.

- Hardware: Huanxin ASI1, Ascend 910B2, single NPU (device 0), torch 2.7.1,
  torch_npu 2.7.1, HCCL, world size 1.
- Protocol: preset `ASI3_sweep` (d=4096, m=14336, ranks 32–512, decode
  (1,128,4096), train (2,512,4096), warmup 3 / fwd 10 / train 3 / ar 5, fp16),
  identical to the paper's scaling sweep; three independent launches per arm.
- Arms:
  - `cond`: benchmark arm (trainable base factors + per-call rank-channel
    scale head, i.e., generated + ordinary materialization).
  - `nocond`: `--no-conditioning` — identical factors without the generator
    (persistent low-rank FFN).
  - dense baseline measured inside each launch (≈4.92 ms train).
- Results (train speedup vs dense, mean ± std over 3 launches):

| rank | cond (gen+mat.) | nocond (persistent) |
|---:|---:|---:|
| 32   | 1.402±0.046 | 3.416±0.116 |
| 64   | 1.528±0.052 | 3.314±0.380 |
| 96   | 1.504±0.041 | 3.271±0.351 |
| 128  | 1.497±0.034 | 3.270±0.448 |
| 192  | 1.517±0.059 | 3.153±0.288 |
| 256  | 1.522±0.072 | 3.341±0.381 |
| 384  | 1.562±0.049 | 3.039±0.272 |
| 512  | 1.526±0.112 | 2.950±0.212 |
| mean | 1.507 | 3.219 |

- Interpretation: at identical rank and compute the persistent low-rank arm
  trains 2.1× faster than the generated+materialized arm. The training
  speedups reported in the paper are ordinary low-rank effects; the unfused
  generator (per-call factor re-materialization/rescaling) costs more than it
  saves. Ephemerality/no-write-back remains untested until the fused arm (iv)
  with HBM counters exists.
- Remote artifacts (raw per-launch JSON+MD): `/root/work/mwg-ew-persistent-control/results/`
  on ASI1 (env dl-9a5a098accce31c28cf4c6ca23391341); local aggregate:
  `ASI1_lifetime_ablation_20260813_aggregate.json`.
