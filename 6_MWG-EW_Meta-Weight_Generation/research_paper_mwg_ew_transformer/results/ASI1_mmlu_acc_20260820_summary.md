# ASI1 MMLU Accuracy Probe (2026-08-20)

- Platform: Huanxin ASI1, Ascend 910B2, single NPU, torch 2.7.1/torch_npu 2.7.1.
- Checkpoint: calibrated layer-16 `mwg_expert_residual_r384_belle_lmce_cal_1200.pt`
  (asi3_layer16_recovery_20260624T110725Z). Router: suite-balanced ridge,
  threshold -0.2015, policy global, budget 0.10 (the 0.9923x tighter-eligibility
  cell, identical threshold to the GSM8K run).
- Protocol: 570-item MMLU subset, 10 items from each of the 57 subjects
  (seed 20260820, balanced and reproducible), greedy zero-shot 4-choice
  letter extraction, max 32 new tokens, batch 4, left-padded.
- Data: `data/mmlu_subset_10x57.jsonl` (built by
  `experiments/prep_mmlu_subset.py` from cais/mmlu test split).
- Results (letter accuracy, binomial SE ≈ 2.1pp):

| arm            | accuracy | correct |
|----------------|----------|---------|
| dense          | 62.11%   | 354/570 |
| selective      | 62.11%   | 354/570 |
| random 2%      | 62.46%   | 356/570 |

- Interpretation: all pairwise differences <= 0.2 sigma — the third
  downstream probe is task-accuracy-neutral at ~2% patching, mirroring
  GSM8K EM (18.08/16.92/21.15%) and HumanEval pass@1 (34.76/34.15/31.71%).
  The 0.77% PPL win does not translate into a measurable task win or
  regression at this budget.
- Raw JSON archived on ASI1:
  `results/mmlu_acc_eval_20260820T145220Z.json` (per-item generations and
  scores; run log `logs/mmlu_acc_eval_20260820T145220Z.log`).
- Paper updated: new Table tab:mmluacc, evidence-ladder row, limitations
  (MMLU no longer outstanding), future work, conclusion,
  reproducibility paragraph, and REBUTTAL_DRAFT.md; compiles clean.
