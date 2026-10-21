# ASI1 GSM8K Exact-Match Probe (2026-08-13)

- Platform: Huanxin ASI1, Ascend 910B2, single NPU, torch 2.7.1/torch_npu 2.7.1.
- Checkpoint: calibrated layer-16 `mwg_expert_residual_r384_belle_lmce_cal_1200.pt`
  (asi3_layer16_recovery_20260624T110725Z). Router: suite-balanced ridge,
  threshold -0.2003, policy global, budget 0.10 (matches the 0.9923x cell).
- Protocol: 260-item local GSM8K test subset, greedy zero-shot, max 256 new
  tokens, batch 4, right-padded (tokenizer default; all arms identical).
- Results (final-answer exact match, binomial SE ≈ 2.4pp):

| arm            | EM     | correct |
|----------------|--------|---------|
| dense          | 18.08% | 47/260  |
| selective      | 16.92% | 44/260  |
| random 2%      | 21.15% | 55/260  |

- Interpretation: all pairwise differences within 1.4 sigma — the 0.77% PPL
  win does not translate into a measurable task-accuracy change at ~2%
  patching (neither win nor regression). Raw JSON archived on ASI1:
  `results/asi1_reviewer_controls_20260813T080428Z/gsm8k_em_eval.json`.
- Caveats: zero-shot (no few-shot/CoT) and right-padded generation keep
  absolute scores below few-shot benchmarks; a padding_side="left" fixed
  script (`mwg_gsm8k_em_eval.py.fixed`) is staged on ASI1 for re-runs.
