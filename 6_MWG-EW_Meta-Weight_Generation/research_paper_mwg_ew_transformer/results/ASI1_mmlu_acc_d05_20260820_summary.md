# ASI1 MMLU Accuracy Probe at Loose Eligibility (2026-08-20/21, Delta_max=-0.05)

- Platform: Huanxin ASI1, Ascend 910B2, single NPU, torch 2.7.1/torch_npu 2.7.1.
- Checkpoint: calibrated layer-16 `mwg_expert_residual_r384_belle_lmce_cal_1200.pt`
  (same as all other probes). Router: suite-balanced ridge, threshold
  **-0.0500**, policy global, budget 0.10 (vs -0.2015 for the Delta_max=-0.20 runs).
- Protocol: identical to the Delta_max=-0.20 MMLU probe (570 items, 10 per
  subject, greedy zero-shot, left-padded).
- Actual patching: ~8.7% (per the Pareto raw cells: Delta_max=-0.05, global,
  budget 0.10 -> actual 0.0868 on all three seeds; the five-suite PPL row at
  this threshold degrades to 1.0032x-1.0195x, median 1.0187x).

## Results (letter accuracy, binomial SE ≈ 2.1pp)

| arm            | accuracy | correct |
|----------------|----------|---------|
| dense          | 62.11%   | 354/570 |
| selective      | 62.11%   | 354/570 |
| random 2%      | 62.46%   | 356/570 |

## Interpretation

- **Task-accuracy-neutral at ~8.7% patching** — identical aggregate to the
  ~2% run. Per-item comparison vs the Delta_max=-0.20 selective run: only
  5/561 differing predictions, i.e. the generated path preserves
  classification-relevant behavior even when patching 4x more tokens.
- The PPL-degrading loose-threshold regime (median PPL 1.0187x, worst cell
  1.0195x) does not produce a measurable end-task change at this probe
  power — the boundary lies in the perplexity regime, not in task accuracy.
- Dense arm identical across runs (62.11%) — threshold-independent
  consistency check passed.
- Raw JSON archived on ASI1: `results/mmlu_acc_eval_d05_20260820T165443Z.json`
  (run log `logs/mmlu_acc_eval_d05_20260820T165443Z.log`).
- Paper updated: Discussion future work, limitations eighth item, evidence
  ladder downstream row, conclusion, REBUTTAL_DRAFT; compiles clean.
