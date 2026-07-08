# ASI3 2026-07-06 — Five-Suite Risk-Policy Sweep

Hardware: Huanxin ASI3, Ascend 910B2, single NPU (device 0).
Model: Qwen2.5-1.5B-Instruct, layer-16 FFN MWG-EW patch, rank r=384,
expert_residual student, LM-CE calibrated 1200 steps.
Checkpoint: `results/asi3_layer16_recovery_20260624T110725Z/layer16/checkpoints/mwg_expert_residual_r384_belle_lmce_cal_1200.pt`
Split manifest: `data/heldout/combined_extra_splits/manifest.json`
Run ID: `asi3_five_suite_risk_policy_sweep_20260706T044501Z`

## Sweep Configuration

- Seeds: 0, 1, 2
- Policies: `global`, `suite_min`, `suite_mean`, `suite_median`
- Risk budgets (target patch fractions): 0.05, 0.10, 0.25
- `--risk-max-predicted-delta 0.0` (mask tokens with positive predicted delta)
- `--suite-balanced-sampling --suite-balanced-ridge --fail-on-suite-overlap`
- Total cells: 3 seeds × 4 policies = 12

## Always-Patched Per-Suite Baseline

| Suite | PPL ratio | Positive delta fraction | Tokens |
|---|---|---|---|
| gsm8k_test | 0.9652x | 0.2700 | 22,551 |
| mbpp_test | 1.2162x | 0.2567 | 4,772 |
| alpaca_cleaned_train_tail | 1.2398x | 0.3618 | 16,583 |
| wikitext103_validation_extra | 1.7973x | 0.5601 | 19,386 |
| hellaswag_validation_extra | 2.5485x | 0.6210 | 11,164 |
| **Five-suite aggregate** | **1.4086x** | — | 74,456 |

Only GSM8K benefits from always-patching. The other four suites get
worse, and the aggregate is 1.4086x of dense (i.e., 40.86% worse PPL).

## Mixed-Router Frontier (mean across 3 seeds)

| Policy | Target patch | Actual patch | PPL ratio |
|---|---|---|---|
| global | 0.05 | 0.1120 | 1.0353x |
| global | 0.10 | 0.1259 | 1.0438x |
| global | 0.25 | 0.1259 | 1.0438x |
| suite_min | 0.05 | 0.0563 | 1.0032x |
| suite_min | 0.10 | 0.0924 | 1.0227x |
| suite_min | 0.25 | 0.1167 | 1.0382x |
| suite_mean | 0.05 | 0.0563 | 1.0032x |
| suite_mean | 0.10 | 0.0924 | 1.0227x |
| suite_mean | 0.25 | 0.1167 | 1.0382x |
| suite_median | 0.05 | 0.0563 | 1.0032x |
| suite_median | 0.10 | 0.0924 | 1.0227x |
| suite_median | 0.25 | 0.1167 | 1.0382x |

## Findings

1. **`suite_min`, `suite_mean`, `suite_median` produce identical
   frontiers.** This exposed a bug in `threshold_for_risk_budget`
   (fixed in commit 8693459): all non-global policies collapsed to
   `min(suite_thresholds)`. The fix differentiates them so the next
   sweep will report distinct cells for each policy.

2. **`global` over-patches.** With `max_predicted_delta=0.0`, the
   global policy caps at 12.59% actual patch (the fraction of train
   tokens with predicted_delta ≤ 0). This produces 1.035–1.044x,
   worse than the suite-aware policies at matched target.

3. **Best router frontier is 1.003x at 5% target (suite_min-like).**
   This is essentially break-even with dense, not a positive regime.
   The router can preserve dense PPL while patching ~5.6% of tokens,
   but cannot achieve a net five-suite win.

4. **The always-patched policy hurts 4 of 5 suites.** Only GSM8K
   benefits (0.9652x). HellaSwag is the worst (2.5485x). Any router
   that patches more than a tiny fraction inherits this hurt.

## Implication for the Paper

The defensible claim remains: (a) in-distribution / calibration-slice
benefit (Belle held-out 1.180x, GSM8K 0.9652x), and (b) a router can
preserve dense PPL while patching a small fraction of tokens. A
uniformly safe five-suite always-patched policy is NOT established,
and a tighter eligibility policy than threshold quantiles is required
to recover a net selective win on the broad mix.

The follow-up sweep with the bug fix will test whether `suite_mean`
and `suite_median` (which now properly aggregate per-suite quantiles)
find a better trade-off than `suite_min`.
