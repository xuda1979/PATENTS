# Local Combined Projection Probe

Created: 2026-05-27

This local CPU probe combines the two promising projection-internal directions:
FFN gate/up/down residuals and attention `K+V` residuals. The synthetic block is
a dense single-head attention path plus a dense gated-FFN path. The student uses
low-rank bases for FFN and K/V, then applies generated residuals to FFN only,
K/V only, or both. Combined variants compare separate routers, one shared token
router, and a joint allocator over FFN-token and K/V-token patch slots.

Configuration: `d=48`, `m=144`, rank-12 low-rank base, rank-6 residuals, three
seeds, 60 base steps, 90 residual steps, 50 router-supervision steps, and
budgets 10%, 25%, and 50%.

Source results:

- `/tmp/mwg_combined_projection_main/mwg_combined_projection_probe_20260527T123512Z.json`
- `/tmp/mwg_combined_projection_main/mwg_combined_projection_probe_20260527T123521Z.json`
- `/tmp/mwg_combined_projection_main/mwg_combined_projection_probe_20260527T123529Z.json`

Joint-allocation follow-up:

- `/tmp/mwg_combined_projection_joint_main/mwg_combined_projection_probe_20260527T125542Z.json`
- `/tmp/mwg_combined_projection_joint_main/mwg_combined_projection_probe_20260527T125553Z.json`
- `/tmp/mwg_combined_projection_joint_main/mwg_combined_projection_probe_20260527T125605Z.json`

## Three-Seed Aggregate

| Method | Budget | FFN budget | K/V budget | Mean rel. MSE | Mean improvement vs base | Min improvement | Max improvement | Mean cosine |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| low_rank_block | 0.0000 | 0.0000 | 0.0000 | 0.799740 | 0.000% | 0.000% | 0.000% | 0.448723 |
| ffn_separate_always | 1.0000 | 1.0000 | 0.0000 | 0.799302 | 0.055% | 0.051% | 0.060% | 0.449234 |
| ffn_separate_oracle_b0.1 | 0.1000 | 0.1000 | 0.0000 | 0.799470 | 0.034% | 0.029% | 0.039% | 0.449038 |
| ffn_separate_supervised_b0.1 | 0.1000 | 0.1000 | 0.0000 | 0.799629 | 0.014% | 0.008% | 0.018% | 0.448851 |
| ffn_separate_oracle_b0.25 | 0.2500 | 0.2500 | 0.0000 | 0.799357 | 0.048% | 0.044% | 0.053% | 0.449169 |
| ffn_separate_supervised_b0.25 | 0.2500 | 0.2500 | 0.0000 | 0.799507 | 0.029% | 0.027% | 0.033% | 0.448993 |
| ffn_separate_oracle_b0.5 | 0.5000 | 0.5000 | 0.0000 | 0.799299 | 0.055% | 0.053% | 0.060% | 0.449236 |
| ffn_separate_supervised_b0.5 | 0.5000 | 0.5000 | 0.0000 | 0.799425 | 0.039% | 0.039% | 0.041% | 0.449087 |
| kv_separate_always | 1.0000 | 0.0000 | 1.0000 | 0.799363 | 0.047% | 0.037% | 0.064% | 0.449156 |
| kv_separate_oracle_b0.1 | 0.1000 | 0.0000 | 0.1000 | 0.799504 | 0.030% | 0.019% | 0.043% | 0.448993 |
| kv_separate_supervised_b0.1 | 0.1000 | 0.0000 | 0.1000 | 0.799706 | 0.004% | -0.000% | 0.009% | 0.448762 |
| kv_separate_oracle_b0.25 | 0.2500 | 0.0000 | 0.2500 | 0.799386 | 0.045% | 0.033% | 0.062% | 0.449130 |
| kv_separate_supervised_b0.25 | 0.2500 | 0.0000 | 0.2500 | 0.799647 | 0.012% | 0.005% | 0.022% | 0.448827 |
| kv_separate_oracle_b0.5 | 0.5000 | 0.0000 | 0.5000 | 0.799308 | 0.054% | 0.042% | 0.075% | 0.449218 |
| kv_separate_supervised_b0.5 | 0.5000 | 0.0000 | 0.5000 | 0.799570 | 0.021% | 0.017% | 0.024% | 0.448922 |
| combined_separate_always | 1.0000 | 1.0000 | 1.0000 | 0.798932 | 0.101% | 0.089% | 0.111% | 0.449660 |
| combined_separate_oracle_b0.1 | 0.1000 | 0.1000 | 0.1000 | 0.799221 | 0.065% | 0.054% | 0.071% | 0.449324 |
| combined_separate_supervised_b0.1 | 0.1000 | 0.1000 | 0.1000 | 0.799606 | 0.017% | 0.011% | 0.024% | 0.448876 |
| combined_separate_oracle_b0.25 | 0.2500 | 0.2500 | 0.2500 | 0.798994 | 0.094% | 0.084% | 0.100% | 0.449588 |
| combined_separate_supervised_b0.25 | 0.2500 | 0.2500 | 0.2500 | 0.799439 | 0.038% | 0.024% | 0.052% | 0.449071 |
| combined_separate_oracle_b0.5 | 0.5000 | 0.5000 | 0.5000 | 0.798868 | 0.109% | 0.100% | 0.117% | 0.449734 |
| combined_separate_supervised_b0.5 | 0.5000 | 0.5000 | 0.5000 | 0.799180 | 0.070% | 0.057% | 0.082% | 0.449370 |
| combined_shared_always | 1.0000 | 1.0000 | 1.0000 | 0.799028 | 0.089% | 0.080% | 0.104% | 0.449546 |
| combined_shared_oracle_b0.1 | 0.1000 | 0.1000 | 0.1000 | 0.799379 | 0.045% | 0.033% | 0.056% | 0.449140 |
| combined_shared_supervised_b0.1 | 0.1000 | 0.1000 | 0.1000 | 0.799631 | 0.014% | 0.011% | 0.019% | 0.448850 |
| combined_shared_oracle_b0.25 | 0.2500 | 0.2500 | 0.2500 | 0.799180 | 0.070% | 0.058% | 0.083% | 0.449371 |
| combined_shared_supervised_b0.25 | 0.2500 | 0.2500 | 0.2500 | 0.799488 | 0.032% | 0.023% | 0.039% | 0.449015 |
| combined_shared_oracle_b0.5 | 0.5000 | 0.5000 | 0.5000 | 0.799037 | 0.088% | 0.078% | 0.103% | 0.449535 |
| combined_shared_supervised_b0.5 | 0.5000 | 0.5000 | 0.5000 | 0.799382 | 0.045% | 0.036% | 0.051% | 0.449141 |

## Joint Allocation Follow-Up

The first combined run used either independent per-family budgets or the same
token mask on both paths. A follow-up added `combined_joint_*`, where FFN-token
and K/V-token patch opportunities compete in one top-k pool. This tests whether
the allocator can move budget between projection families.

| Method | Budget | FFN budget | K/V budget | Mean rel. MSE | Mean improvement vs base | Min improvement | Max improvement | Mean cosine |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| low_rank_block | 0.0000 | 0.0000 | 0.0000 | 0.799740 | 0.000% | 0.000% | 0.000% | 0.448723 |
| combined_separate_oracle_b0.25 | 0.2500 | 0.2500 | 0.2500 | 0.798994 | 0.094% | 0.084% | 0.100% | 0.449588 |
| combined_separate_supervised_b0.25 | 0.2500 | 0.2500 | 0.2500 | 0.799439 | 0.038% | 0.024% | 0.052% | 0.449071 |
| combined_shared_oracle_b0.25 | 0.2500 | 0.2500 | 0.2500 | 0.799180 | 0.070% | 0.058% | 0.083% | 0.449371 |
| combined_shared_supervised_b0.25 | 0.2500 | 0.2500 | 0.2500 | 0.799488 | 0.032% | 0.023% | 0.039% | 0.449015 |
| combined_joint_oracle_b0.10 | 0.1000 | 0.1021 | 0.0979 | 0.799288 | 0.057% | 0.045% | 0.065% | 0.449247 |
| combined_joint_supervised_b0.10 | 0.1000 | 0.1500 | 0.0500 | 0.799605 | 0.017% | 0.015% | 0.019% | 0.448880 |
| combined_joint_oracle_b0.25 | 0.2500 | 0.2417 | 0.2583 | 0.799076 | 0.083% | 0.071% | 0.092% | 0.449494 |
| combined_joint_supervised_b0.25 | 0.2500 | 0.2854 | 0.2146 | 0.799483 | 0.032% | 0.026% | 0.039% | 0.449021 |
| combined_joint_oracle_b0.50 | 0.5000 | 0.4937 | 0.5062 | 0.798969 | 0.097% | 0.085% | 0.107% | 0.449618 |
| combined_joint_supervised_b0.50 | 0.5000 | 0.4417 | 0.5583 | 0.799300 | 0.055% | 0.050% | 0.062% | 0.449235 |

## Interpretation

The combined direction is directionally positive but currently weak. Combining
FFN-internal and K/V residuals beats either family alone under oracle routing:
at 25% budget, separate combined routing improves 0.094% versus 0.048% for
FFN-only and 0.045% for K/V-only. At 50%, separate combined routing improves
0.109% and supervised routing improves 0.070%.

The shared-router variant is consistently weaker than separate routers in this
setup. At 25%, shared oracle improves 0.070% versus 0.094% for separate oracle;
shared supervised improves 0.032% versus 0.038%.

The true joint allocator is also not better than separate per-family routing in
this synthetic block. At 25%, joint oracle improves 0.083%, below separate
oracle at 0.094%; joint supervised improves 0.032%, below separate supervised
at 0.038%. The joint router does learn uneven allocations, such as 28.54% FFN
and 21.46% K/V at the 25% supervised setting, but this reallocation does not
translate into stronger quality. In this local setting, the best conservative
policy remains separate benefit labels and separate token budgets.

This is not an ASI3 launch candidate yet. The signal is far smaller than the
isolated internal-FFN probe, and supervised routing leaves most of the oracle
benefit on the table. The next useful local step is to make the combined block
closer to real LM activations or to train the router against richer labels that
rank FFN and K/V benefits jointly instead of sharing the same per-token budget
across both paths.
