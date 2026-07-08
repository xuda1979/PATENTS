# ASI3 2026-07-08 — Tighter-Eligibility Pareto Sweep (Launched)

Hardware: Huanxin ASI3, Ascend 910B2, single NPU (device 0).
Model: Qwen2.5-1.5B-Instruct, layer-16 FFN MWG-EW patch, rank r=384,
expert_residual student, LM-CE calibrated 1200 steps.
Checkpoint: `results/asi3_layer16_recovery_20260624T110725Z/layer16/checkpoints/mwg_expert_residual_r384_belle_lmce_cal_1200.pt`

## Launch

- **run_id**: `asi3_tighter_eligibility_pareto_20260708T125309Z`
- **pid** (remote): 4403
- **launcher**: `scripts/launch_asi3_tighter_eligibility_pareto_detached.sh`
- **project_root** (remote): `/root/work/filestorage/mwg-ew-transformer-research`
- **outdir** (remote): `results/asi3_tighter_eligibility_pareto_20260708T125309Z`
- **wrapper_log** (remote): `logs/asi3_tighter_eligibility_pareto_20260708T125309Z.log`
- **status** (remote): `logs/asi3_tighter_eligibility_pareto_20260708T125309Z.status.json`
- **launched_at**: 2026-07-08T12:53:09Z

## Sweep Grid

- **max_deltas**: -0.30, -0.25, -0.20, -0.15, -0.12, -0.10, -0.08, -0.05 (8 values)
- **policies**: suite_min, suite_mean, suite_median, global (4)
- **seeds**: 0, 1, 2 (3)
- **risk_budgets**: 0.05, 0.10, 0.25
- **total cells**: 8 × 4 × 3 = 96

## Motivation

The 2026-07-07 tighter-eligibility sweep established that max_delta=-0.20
with suite_median or global threshold policy recovers a net five-suite
selective win of 0.9923x while patching ~2% of tokens. The grid was
coarse ({-0.50, -0.20, -0.10, -0.05, 0.0}), so the Pareto frontier
between patch fraction and PPL improvement was undersampled. This sweep
fills in the finer grid {-0.30, -0.25, -0.20, -0.15, -0.12, -0.10, -0.08,
-0.05} to map the frontier and identify the best operating point.

## Expected Outcomes

1. **Pareto frontier**: For each (policy, seed), plot ppl_ratio vs.
   actual_patch_token_fraction across max_deltas. The frontier should
   show that tighter max_delta (more negative) reduces patch fraction
   but preserves dense PPL, while looser max_delta increases patch
   fraction but risks PPL regression.

2. **Best operating point**: The cell with the lowest ppl_ratio that
   still patches a meaningful fraction of tokens (>0.5%). Hypothesis:
   max_delta=-0.20 with suite_median remains the best, but -0.25 or
   -0.15 may offer a better trade-off.

3. **Policy robustness**: Confirm that suite_median and global policies
   are robust across the finer grid, while suite_min is too conservative
   and suite_mean is too aggressive.

## Monitoring

The detached sweep writes:
- Per-cell `token_router_five_suite.json` under
  `results/asi3_tighter_eligibility_pareto_20260708T125309Z/max_delta=XX/policy=YY/seedZ/`
- A `pareto_summary.json` aggregating all cells at the end.
- A `logs/asi3_tighter_eligibility_pareto_20260708T125309Z.status.json`
  with live state updates.

The sweep is expected to take several hours (96 cells × ~3-5 min per
cell). Results will be pulled via S3 and incorporated into the paper
once complete.

## Status

- 2026-07-08T12:53:19Z: First cell started (max_delta=-0.30/policy=suite_min/seed0).
- 2026-07-08T13:37Z: Monitoring blocked by Huanxin daemon terminal
  injection instability; the sweep itself continues on the remote.
