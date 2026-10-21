# ASI1 GSM8K Zero-Shot Re-Run, Left-Padded (2026-08-21)

- Platform: Huanxin ASI1, single Ascend 910B2 NPU, torch 2.7.1/torch_npu 2.7.1.
- Purpose: close the right-padding caveat of the Aug 13 GSM8K EM probe — the
  local script now sets `tokenizer.padding_side = "left"` (the staged fix);
  this run uses it, everything else identical (260 items, greedy zero-shot,
  max 256 new tokens, batch 4, Delta_max=-0.20, budget 0.10, seed 0).
- Checkpoint: calibrated layer-16 mwg_expert_residual_r384_belle_lmce_cal_1200.pt.

## Results (final-answer exact match, binomial SE ≈ 2.4pp per arm, ≈3.4pp pairwise)

| arm            | left-padded (this run) | right-padded (Aug 13) |
|----------------|------------------------|-----------------------|
| dense          | 22.69% (59/260)        | 18.08% (47/260)       |
| selective      | 23.46% (61/260)        | 16.92% (44/260)       |
| random 2%      | 19.23% (50/260)        | 21.15% (55/260)       |

## Interpretation

- Verdict unchanged: all pairwise differences <= 1.3 sigma of the
  pairwise-difference SE (max |23.46-19.23| = 4.23pp = 1.26 sigma) —
  task-accuracy-neutral at the ~2% budget under the correct (left-padded)
  protocol. The selective arm is now numerically the best (23.46% vs dense
  22.69%), within noise.
- Absolute scores improve with left padding (right padding degraded
  generation), consistent with the model's known zero-shot GSM8K range.
- The right-padding caveat is dropped from the paper (tab:gsm8kem footnote,
  downstream paragraph, limitations); all probes now share left-padded
  batching.
- Raw JSON on ASI1: results/gsm8k_leftpad_20260821T*.json (run log
  logs/gsm8k_leftpad_20260821T*.log).
