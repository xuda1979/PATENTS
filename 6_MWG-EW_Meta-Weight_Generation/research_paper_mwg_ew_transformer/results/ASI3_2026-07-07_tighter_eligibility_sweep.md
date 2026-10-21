# ASI3 2026-07-07 — Tighter-Eligibility Five-Suite Risk-Policy Sweep

Hardware: Huanxin ASI3, Ascend 910B2, single NPU (device 0).
Model: Qwen2.5-1.5B-Instruct, layer-16 FFN MWG-EW patch, rank r=384,
expert_residual student, LM-CE calibrated 1200 steps.
Checkpoint: `results/asi3_layer16_recovery_20260624T110725Z/layer16/checkpoints/mwg_expert_residual_r384_belle_lmce_cal_1200.pt`.

## Motivation

The 2026-07-06 risk-policy sweep (`RISK_MAX_PREDICTED_DELTA=0.0`) found no net
five-suite selective win: the best mean PPL ratio was 1.0032x at 5.6% actual
patching (`suite_min`, target 0.05). The write-up of that sweep identified that
a tighter eligibility policy than threshold quantiles is required to recover a
net five-suite win. This sweep tests that hypothesis by sweeping
`risk_max_predicted_delta` (`max_delta`) over {-0.50, -0.20, -0.10, -0.05, 0.0}
across four threshold policies (`global`, `suite_mean`, `suite_median`,
`suite_min`), three risk budgets {0.05, 0.10, 0.25}, and three seeds {0, 1, 2}.

## Sweep Configuration

- `--risk-budgets 0.05,0.10,0.25`
- `--risk-max-predicted-delta` swept over {-0.50, -0.20, -0.10, -0.05, 0.0}
- `--threshold-policy` swept over {global, suite_mean, suite_median, suite_min}
- `--seed` swept over {0, 1, 2}
- `--suite-balanced-sampling --suite-balanced-ridge --fail-on-suite-overlap --require-texts`
- `--seq 256 --ridge-l2 1.0 --dtype fp32`
- 60 cells total (5 max_delta × 4 policies × 3 seeds); each cell emits three
  router rows (one per risk budget).

## Headline Result

The tighter eligibility policy recovers a **net five-suite selective win**:
18 of 60 cells have `mean_ppl_ratio < 1.0`, all at `max_delta ∈ {-0.20, -0.10}`.
The always-patched five-suite baseline is 1.4086x (i.e., always patching hurts
by 40.86%); the best router operating point is **0.9923x at 2.01% actual
patching** (`max_delta=-0.20`, `suite_median` or `global`, target 0.05),
a 0.77% PPL reduction relative to dense.

### Best operating points (sorted by mean PPL ratio)

| max_delta | policy        | target | actual patch | mean PPL ratio |
|----------:|---------------|-------:|-------------:|---------------:|
| -0.20     | suite_median  | 0.05   | 0.0201       | 0.9923         |
| -0.20     | global        | 0.05   | 0.0201       | 0.9923         |
| -0.20     | suite_mean    | 0.10   | 0.0185       | 0.9926         |
| -0.10     | suite_min     | 0.05   | 0.0237       | 0.9928         |
| -0.10     | suite_mean    | 0.05   | 0.0462       | 0.9981         |

### Net-win counts

- By `max_delta`: `{-0.20: 12, -0.10: 6}` (out of 12 cells per `max_delta`)
- By policy: `{suite_min: 6, suite_mean: 6, global: 3, suite_median: 3}`
- `max_delta ∈ {-0.50, -0.05, 0.0}` produces no net wins (best 1.0014x–1.0032x).

### Per-suite always-patched reference (seed 0, max_delta=-0.20, suite_median)

| Suite                              | Tokens  | dense_loss | patched_loss | patched_ppl_ratio | pos_delta_frac |
|------------------------------------|--------:|-----------:|-------------:|------------------:|---------------:|
| gsm8k_test                         | 22,551  | 1.2737     | 1.2383       | 0.9652            | 0.2700         |
| mbpp_test                          | 4,772   | 1.4518     | 1.6475       | 1.2162            | 0.3433         |
| alpaca_cleaned_train_tail          | 16,583  | 1.3481     | 1.5630       | 1.2398            | 0.3618         |
| wikitext103_validation_extra       | 19,386  | 2.7587     | 3.3450       | 1.7973            | 0.5601         |
| hellaswag_validation_extra         | 11,164  | 3.6333     | 4.5688       | 2.5485            | 0.6210         |
| **Aggregate**                      | 74,456  | 2.0421     | 2.3847       | 1.4086            | 0.4178         |

The router with `max_delta=-0.20` patches only the 2% of tokens whose predicted
patched-minus-dense loss is at most -0.20 (capped further by the per-suite
threshold). The resulting PPL ratio of 0.9923x means the patched 2% improves
aggregate loss enough to offset the dense fallback on the other 98%.

## Implication for the Paper

This sweep establishes the **suite-robust eligibility policy** that the paper's
Discussion previously listed as the highest-value follow-up experiment. The
defensible claim is now strengthened to:

1. In-distribution / calibration-slice benefit (Belle held-out 1.180x, GSM8K
   0.9652x).
2. A dense-fallback router with a tighter eligibility policy
   (`max_delta=-0.20`, `suite_median` or `global` threshold) preserves dense
   PPL while patching ~2% of tokens, recovering a **net five-suite selective
   win** of 0.9923x under leakage-clean seeded evaluation.
3. The win is robust across the four threshold policies tested and across three
   seeds (per-cell variance < 1e-4 in PPL ratio).

The next follow-up is a finer-grained `max_delta` sweep in {-0.30, -0.25, -0.18,
-0.15, -0.12} to map the Pareto frontier of patch fraction vs. PPL improvement,
and a multi-layer extension to test whether the tighter-eligibility win
generalizes to layers 17 and 18.
