# ASI1 HumanEval pass@1 Probe (2026-08-13, done rc=0 20:36Z)

- Platform: Huanxin ASI1, Ascend 910B2, single NPU, torch 2.7.1/torch_npu 2.7.1.
- Checkpoint: calibrated layer-16 `mwg_expert_residual_r384_belle_lmce_cal_1200.pt`.
  Router: suite-balanced ridge, threshold -0.2015, policy global, budget 0.10
  (the tighter-eligibility operating point). Canonical 164-problem HumanEval
  set from the `human_eval-1.0.3` PyPI wheel; greedy single sample; exec
  harness in isolated subprocesses with 20s timeouts.
- Results:

| arm            | pass@1 | passed |
|----------------|--------|--------|
| dense          | 34.76% | 57/164 |
| selective      | 34.15% | 56/164 |
| random 2%      | 31.71% | 52/164 |

- Binomial SE ≈ 3.7pp; all pairwise differences ≤ 0.7σ — the selective regime
  is task-accuracy-neutral at ~2% patching, mirroring the GSM8K EM probe
  (18.08/16.92/21.15%). The 0.77% PPL win does not translate into a
  measurable task win or regression at this budget.
- Raw JSON: ASI1 `results/asi1_humaneval_20260813T191549Z/humaneval_pass1_eval.json`.
