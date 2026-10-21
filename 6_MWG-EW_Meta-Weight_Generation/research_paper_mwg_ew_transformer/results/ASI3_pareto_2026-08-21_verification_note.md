# Pareto Sweep Number Verification (2026-08-21)

Re-derived every headline number of the tighter-eligibility Pareto story from
the authoritative artifact
`results/asi3_tighter_eligibility_pareto_20260708T125309Z/tighter_eligibility_pareto_summary.json`
(96 cells, 8 max_delta x 4 policy x 3 target budgets, each mean over 3 seeds;
raw per-seed cells in the `cells` key).

## Corrections applied to main.tex (all now match the artifact)

1. **tab:tighterpareto, row (-0.20, suite_min, 0.10)**: was 0.0201 / 0.9928x —
   corrected to 0.0129 / 0.9933x (the 0.0201/0.9923x pair belongs to global).
2. **tab:tighterpareto, row (-0.25, suite_mean, 0.05)**: was 0.0119 / 0.9941x —
   corrected to 0.0074 / 0.9963x (0.9941x is the -0.15 row median, not -0.25).
3. **tab:tighterpareto, row (-0.08, suite_min, 0.05)**: was 0.0574 / 1.0014x —
   corrected to 0.0563 / 1.0032x (1.0014x originates from the July 7 sweep's
   -0.50 row, a different grid).
4. **tab:tighterpareto, row (-0.10, suite_mean, 0.05)**: 0.9980x -> 0.9981x
   (exact 0.998127), actual 0.0463 -> 0.0462.
5. **Text distribution claim**: "spans [0.9923, 1.0138]: 66/18/12" corrected
   to "spans [0.9923, 1.0195]: 66/19/11" (max cell is -0.05 global,
   1.0195x; 1.0138x is only the -0.05 suite_mean 0.05 frontier cell).
6. **tab:ckptreplication Orig column**: inherited the same wrong cells
   (-0.25: 0.9941x/1.19% -> 0.9963x/0.74%; -0.08: 1.0014x/5.74% ->
   1.0032x/5.63%; -0.10: 0.9980x/4.63% -> 0.9981x/4.62%).
7. **"identical per-row win pattern" claims** (variance-scope paragraph,
   tab:ckptreplication caption, evidence ladder, REBUTTAL_DRAFT) corrected:
   both checkpoints win 66/96 and rows -0.25..-0.12 win 12/12 on both, but
   the extremes differ within checkpoint variation: -0.30 (orig 12/12,
   best 0.9992x vs repl 0/12 near-neutral 1.0002x), -0.10 (orig 6/12 vs
   repl 12/12), -0.08/-0.05 (orig 0/12 vs repl 3/12).

## New table added (reviewer W1(b) request)

**tab:paretofull**: full 96-cell distribution per max_delta row — min/median/
max over the 12 cells, win count, mean actual patch fraction. Rows -0.30..
-0.12 all win 12/12; -0.10: 6/12; -0.08/-0.05: 0/12.

## Per-row statistics (original checkpoint, authoritative)

| dmax  | min    | median | max    | wins  | actual |
|-------|--------|--------|--------|-------|--------|
| -0.30 | 0.9990 | 0.9992 | 0.9994 | 12/12 | 0.36%  |
| -0.25 | 0.9958 | 0.9961 | 0.9966 | 12/12 | 0.74%  |
| -0.20 | 0.9923 | 0.9925 | 0.9933 | 12/12 | 1.79%  |
| -0.15 | 0.9928 | 0.9941 | 0.9944 | 12/12 | 3.15%  |
| -0.12 | 0.9928 | 0.9972 | 0.9988 | 12/12 | 3.96%  |
| -0.10 | 0.9928 | 1.0007 | 1.0034 | 6/12  | 4.57%  |
| -0.08 | 1.0032 | 1.0075 | 1.0078 | 0/12  | 6.52%  |
| -0.05 | 1.0032 | 1.0187 | 1.0195 | 0/12  | 8.20%  |

Build verified: 0 warnings, 38 pages.

## Full-table audit (2026-08-21, second pass)

Extended the verification to every data-backed table in main.tex against
local artifacts:

| Table | Artifact | Verdict |
|-------|----------|---------|
| tab:scaling (16 cells) | pulled_asi1/ASI3_reliability_scaling_20260518T072507Z | 16/16 exact |
| tab:statecomm | same reliability set | exact (params, traffic, AR 2/4/8) |
| tab:quality (12 cells) | pulled_asi1/asi1_quality_distillation_20260518T083242Z | 12/12 exact |
| tab:lifetimeablation | ASI1_lifetime_ablation_20260813_aggregate.json | all 8 ranks exact; 2.1x ratio confirmed |
| tab:randomcontrol | ASI1_random_perturbation_control_20260813.json | all budgets + always-patched exact; dense PPL 7.718 |
| tab:fivesuite | asi3_corrected_eval_20260611T064834Z (token_router_five_suite.json + hybrid) | 5/5 exact |
| tab:fivesuiteseed | asi3_five_suite_router_seed_sweep_20260624T111613Z | all rows exact |
| tab:multilayerpareto | layer17/layer18 summary JSONs | 0/96, 1.0007x, 1.0005x, 1.4311x, 1.5165x exact |
| tab:tokencvalid | pulled_asi3/.../token_router_cv_20260525T131335Z | 6/6 exact |
| tab:tokenbroadvalid | token_router_broad_20260525T141738Z | 6/6 exact |
| tab:tokenbroadseeds | token_router_broad_seed_sweep_20260525T161810Z | 6/6 exact |
| tab:tokenleavesuite | token_router_leave_suiteout_seed_sweep_20260525T171658Z | 6/6 exact |
| tab:pplheldout (0.404x row) | asi3_layer16_recovery_20260624T110725Z summary | 3.6854 -> 1.4899 exact |
| Ladder SVD row | asi3_layer16_recovery_20260610T020738Z distillation | 0.1018/0.9477 vs 0.8367/0.4045 exact |
| tab:runtimeprobe | runtime_profiler_probe_20260525T192357Z | timings exact (0.3391/0.7638/0.7559); op counts = full-trace (artifact keeps top-20: 18/30 seen) |
| tab:scalingsweep | params/traffic from scaled-sweep logs | params/traffic exact; TIMINGS NOT ARCHIVED LOCALLY — two independent world-4 families (0512: 1.57-1.72x, 0518: 1.49-1.57x) bracket the paper's 1.538-1.646x directionally; ASI3 pod loss noted |

**Zero discrepancies in this pass.** The only caveat: tab:scalingsweep timing
columns (including the 1.638+/-0.030 headline) trace to an eight-accelerator
run whose per-launch JSONs were lost with the ASI3 pod; direction and shape
are corroborated by two archived independent launch families.

Also verified label integrity: tab:tokenleavesuite, tab:tokenbroadvalid,
tab:tokenbroadseeds attach to their own tables (no mislabeling).

## Third pass (2026-08-21) — remaining qualitative/motivation tables

- **tab:positioning**: qualitative comparison table; no numeric claims.
- **tab:svd** (18 pretrained FFN matrices): no local artifact; the exact
  18-matrix selection is unknown. Values are internally consistent and
  consistent with the archived layer-16 r384 energies (45-51% at r384 vs
  table mean 55.6% at r512, monotone energy profile); tab:effectivesavings
  arithmetic re-verified exactly (99.65%/96.0% at 0.49%/5.65% patching with
  Gamma=0.293, 3.41x = 1/0.293). Marked motivation-only, no re-measurement
  without the original selection.
- **Statistical pass**: pairwise-difference sigma claims re-derived for all
  four downstream probes; GSM8K zero-shot corrected from 1.4 sigma to
  1.3 sigma of the difference-level SE (see ASI1_mmlu_acc_d05 summary);
  HumanEval (0.58), MMLU (0.12), CoT (0.62) claims verified correct.
- **Future-work phrasing audit**: all remaining "future work" references
  point to genuinely unmeasured items (fused kernel, multi-layer allocation,
  dialogue/long-context suites); no stale claims remain.

## Fourth pass (2026-08-21) — longer timing loop

- ASI2 world-4 sweep re-measured with --train-iters 10 (3 launches):
  speedup family 1.52-1.59x (mean), std much tighter (r32 0.224->0.055),
  consistent with the train_iters=3 family (1.42-1.58x) and the paper's
  world-8 numbers (1.538-1.646x). The limitations item "three training-timing
  iterations are short" is now addressed in the manuscript (main.tex
  limitations item 3).

## Fifth pass (2026-08-21) — unseen-family transfer test

- New measurement (ASI1): five-suite-calibrated router evaluated on two
  held-out families — Dolly dialogue (100 turns) and arXiv long-form prose
  (15 papers). Always-patched degrades both (2.29x / 1.29x); the router
  over-patches out-of-family tokens (18.9% / 41.8% actual at a 10%
  train-side target vs ~2% in-family) and degrades PPL (1.38x / 1.07x vs
  0.9923x in-family). Selective regime is family-specific; Seventh
  limitation, evidence ladder, and Discussion updated. Caveat recorded:
  uniform-ridge explicit-train branch (threshold derived from unweighted
  pool), robust to the conclusion.
- Evidence ladder font reduced to scriptsize to fit the extended rows
  (0 warnings, 38 pages).
