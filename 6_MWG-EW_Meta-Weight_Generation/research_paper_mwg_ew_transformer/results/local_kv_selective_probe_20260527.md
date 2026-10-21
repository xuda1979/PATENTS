# Local K/V Selective Probe

Created: 2026-05-27

This local CPU probe returns to the original MWG idea of replacing or patching
attention `K`/`V` projection matrices. The experiment keeps `Q` and `O` dense,
uses trainable low-rank `K`/`V` factors as the base, and tests small generated
residuals for `K`, `V`, and `K+V` under token budgets.

Configuration: synthetic single-head attention teacher, `d=64`, rank-16
low-rank K/V base, rank-8 residuals, three seeds, 80 base steps, 160 residual
steps, 40 router-supervision steps, budgets 10%, 25%, and 50%.

Source results:

- `/tmp/mwg_kv_selective_main/mwg_kv_selective_probe_20260526T164024Z.json`
- `/tmp/mwg_kv_selective_main/mwg_kv_selective_probe_20260526T164028Z.json`
- `/tmp/mwg_kv_selective_main/mwg_kv_selective_probe_20260526T164033Z.json`

## Three-Seed Aggregate

| Method | Actual budget | Mean rel. MSE | Mean improvement vs base | Min improvement | Max improvement | Mean cosine |
|---|---:|---:|---:|---:|---:|---:|
| low_rank_kv | 0.0000 | 0.590547 | 0.000% | 0.000% | 0.000% | 0.642395 |
| k_always_residual | 1.0000 | 0.588886 | 0.281% | 0.206% | 0.377% | 0.643598 |
| v_always_residual | 1.0000 | 0.582084 | 1.431% | 1.090% | 1.819% | 0.648549 |
| kv_always_residual | 1.0000 | 0.581280 | 1.567% | 1.134% | 2.054% | 0.649118 |
| k_oracle_b0.10 | 0.1042 | 0.589169 | 0.233% | 0.156% | 0.323% | 0.643378 |
| v_oracle_b0.10 | 0.1042 | 0.584339 | 1.049% | 0.742% | 1.452% | 0.646911 |
| kv_oracle_b0.10 | 0.1042 | 0.584263 | 1.060% | 0.803% | 1.470% | 0.646956 |
| k_supervised_b0.10 | 0.1042 | 0.590309 | 0.040% | 0.026% | 0.051% | 0.642572 |
| v_supervised_b0.10 | 0.1042 | 0.589100 | 0.249% | 0.078% | 0.433% | 0.643437 |
| kv_supervised_b0.10 | 0.1042 | 0.588871 | 0.286% | 0.141% | 0.417% | 0.643603 |
| k_oracle_b0.25 | 0.2500 | 0.588835 | 0.290% | 0.209% | 0.381% | 0.643618 |
| v_oracle_b0.25 | 0.2500 | 0.582136 | 1.422% | 1.030% | 1.890% | 0.648521 |
| kv_oracle_b0.25 | 0.2500 | 0.581896 | 1.463% | 1.070% | 1.923% | 0.648664 |
| k_supervised_b0.25 | 0.2500 | 0.590104 | 0.074% | 0.040% | 0.109% | 0.642727 |
| v_supervised_b0.25 | 0.2500 | 0.586564 | 0.671% | 0.277% | 1.179% | 0.645316 |
| kv_supervised_b0.25 | 0.2500 | 0.586534 | 0.682% | 0.485% | 0.804% | 0.645313 |
| k_oracle_b0.50 | 0.5000 | 0.588663 | 0.319% | 0.236% | 0.414% | 0.643742 |
| v_oracle_b0.50 | 0.5000 | 0.580919 | 1.629% | 1.198% | 2.089% | 0.649399 |
| kv_oracle_b0.50 | 0.5000 | 0.580381 | 1.720% | 1.238% | 2.231% | 0.649767 |
| k_supervised_b0.50 | 0.5000 | 0.589412 | 0.191% | 0.119% | 0.287% | 0.643217 |
| v_supervised_b0.50 | 0.5000 | 0.586091 | 0.753% | 0.438% | 1.090% | 0.645625 |
| kv_supervised_b0.50 | 0.5000 | 0.585353 | 0.879% | 0.620% | 1.135% | 0.646179 |

## Interpretation

The original K/V direction has real but smaller local signal than the FFN
internal residual probe. K-only patching is weak. V-only patching carries most
of the benefit. K+V patching is best overall: always-on K+V improves 1.567%;
oracle K+V improves 1.060% at 10%, 1.463% at 25%, and 1.720% at 50%.

Benefit-supervised routing matters here too. Naive learned selective routing is
weak, while supervised K+V routing reaches 0.286% at 10%, 0.682% at 25%, and
0.879% at 50%.

Current usage rule:

1. Do not use MWG blindly.
2. Use MWG inside large projection paths, not merely as an output correction.
3. For attention, prioritize `V` or `K+V`; `K` alone has weak payoff in this
   synthetic probe.
4. Train the router from per-token benefit labels; budget penalties alone are
   not enough.

Next local test: combine FFN-internal and K+V selective residuals under a shared
token budget, then move from synthetic inputs to held-out LM activations.
