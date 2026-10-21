# ASI1 GSM8K 5-shot CoT Probe (2026-08-20/21)

- Platform: Huanxin ASI1, Ascend 910B2, single NPU, torch 2.7.1/torch_npu 2.7.1.
- Checkpoint: calibrated layer-16 `mwg_expert_residual_r384_belle_lmce_cal_1200.pt`
  (asi3_layer16_recovery_20260624T110725Z). Router: suite-balanced ridge,
  threshold -0.2015, policy global, budget 0.10 (the 0.9923x tighter-eligibility
  cell; identical threshold to the zero-shot GSM8K and MMLU runs).
- Protocol: 260-item GSM8K subset (same as the zero-shot EM run), standard
  few-shot chain-of-thought prompt with five canonical CoT exemplars
  (Wei et al. 2022 style), greedy generation, max 256 new tokens, batch 4,
  left-padded. Scoring: #### final-answer extraction (same as zero-shot).
- Results (final-answer exact match, binomial SE ≈ 3.1pp):

| arm            | EM     | correct |
|----------------|--------|---------|
| dense          | 41.54% | 108/260 |
| selective      | 41.15% | 107/260 |
| random 2%      | 38.85% | 101/260 |

- Interpretation: all pairwise differences <= 0.9 sigma — the standard
  few-shot CoT protocol reproduces the task-accuracy-neutral verdict of the
  zero-shot probes (GSM8K 18.08/16.92/21.15%, HumanEval 34.76/34.15/31.71%,
  MMLU 62.11/62.11/62.46%). The 0.77% PPL win does not translate into a
  measurable task win or regression at this budget under zero-shot or
  few-shot protocols.
- Raw JSON archived on ASI1:
  `results/gsm8k_cot_eval_20260820T151552Z.json` (per-item generations and
  scores; run log `logs/gsm8k_cot_eval_20260820T151552Z.log`).
- Paper updated: new Table tab:gsm8kcot, downstream-accuracy paragraph,
  evidence-ladder row, limitations eighth item, future work, conclusion
  (two sites), reproducibility paragraph, and REBUTTAL_DRAFT.md; compiles clean.
