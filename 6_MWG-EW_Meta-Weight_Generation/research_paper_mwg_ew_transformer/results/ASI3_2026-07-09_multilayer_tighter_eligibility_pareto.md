# ASI3 2026-07-09 — Multi-Layer Tighter-Eligibility Pareto Sweep

Hardware: Huanxin ASI3, Ascend 910B2, single NPU (device 0).
Model: Qwen2.5-1.5B-Instruct, FFN MWG-EW patch at layers 16, 17, 18,
rank r=384, expert_residual student, LM-CE calibrated 1200 steps.
Checkpoint family: `results/asi3_layer16_recovery_20260624T110725Z/`.

## Sweep design

Each layer runs the tighter-eligibility Pareto sweep independently:
- `max_delta` ∈ {-0.30, -0.25, -0.20, -0.15, -0.12, -0.10, -0.08, -0.05}
- `policy` ∈ {suite_min, suite_mean, suite_median, global}
- `target_patch_fraction` ∈ {0.05, 0.10, 0.25}
- `seed` ∈ {0, 1, 2}
- 96 cells per layer, 3 seeds per cell

The five-suite token-router evaluation covers GSM8K, MBPP, Alpaca-tail,
Wikitext-103, and HellaSwag, aggregated with token-weighted losses.

## Layer 16 (baseline, from 2026-07-08 sweep)

- Run: `asi3_tighter_eligibility_pareto_20260708T125309Z`
- Cell count: 96
- Net win count (PPL ratio < 1.0): **66 / 96**
- Always-patched control: 1.4086x
- Best cell: `max_delta=-0.20, policy=global, target=0.10`
  - Actual patch fraction: 0.0201 (2.0%)
  - Mean PPL ratio: **0.9923x** (0.77% improvement over dense)
  - Per-seed variance: < 1e-6
  - Policy-invariant: global, suite_median, suite_mean all converge
    to the same operating point at `max_delta=-0.20`

## Layer 17 (from 2026-07-09 sweep)

- Run: `asi3_tighter_eligibility_pareto_layer17_20260709T091024Z`
- Cell count: 96
- Net win count: **0 / 96** (no cell achieves PPL < 1.0)
- Always-patched control: 1.4311x (worse than layer 16)
- Best cell: `max_delta=-0.12, policy=global, target=0.05`
  - Actual patch fraction: 0.0039 (0.4%)
  - Mean PPL ratio: **1.0007x** (essentially neutral)
- The tighter eligibility suppresses false-positive patches
  (actual patching ≤ 0.4% for `max_delta ≤ -0.12`), but unlike layer 16,
  the surviving patches do not produce a net PPL improvement on the
  five-suite mix.

## Layer 18 (from 2026-07-09 sweep)

- Run: `asi3_tighter_eligibility_pareto_layer18_20260709T091024Z`
- Status: results being fetched from remote; will be filled in once
  the summary JSON is pulled.

## Interpretation

The net five-suite selective win at layer 16 (0.9923x) does **not**
generalize to layer 17 under the same checkpoint family and sweep grid.
Layer 17's best achievable PPL ratio is 1.0007x — essentially neutral —
and its always-patched control is worse (1.4311x vs 1.4086x). This is
consistent with the layer-16 calibration being specifically tuned for
that layer's FFN geometry, and it scopes the paper's positive claim:
the tighter-eligibility selective win is a layer-specific result, not
a universal property of all FFN layers.

The implication for the paper is that the contribution should be framed
as: (a) a layer-specific tighter-eligibility win exists for the
calibrated layer-16 checkpoint, and (b) multi-layer generalization
requires per-layer calibration and is left as future work. The layer 17
result is reported as a negative control that bounds the claim.
