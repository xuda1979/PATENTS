# ASI2 Multi-Model Probe: Baichuan2-13B Layer-16 (2026-08-21)

- Platform: Huanxin ASI2, 4x Ascend 910B2 NPU (world 1 used), torch
  2.9.0/torch_npu 2.9.0.
- Purpose: first multi-model data point — does the MWG-EW generator's
  advantage over static SVD reproduce beyond Qwen2.5-1.5B?
- Setup: layer-16 FFN of Baichuan2-13B_Chat (d=5120, m=13696), rank 384,
  expert_residual student (K=4, r_res=32), 5000 steps, fp16 activation
  caching + fp32 student training (fp16 training produced NaN metrics on
  the 13B — fp32 required).

## Results (FFN-output reconstruction, held-out activations)

| method | rel MSE | cosine |
|--------|---------|--------|
| Static SVD r384 | 0.9386 | 0.2681 |
| MWG-EW expert_residual r384 | 0.1097 | 0.9471 |

## Comparison with Qwen2.5-1.5B (layer 16, r384)

| method | Qwen2.5-1.5B | Baichuan2-13B |
|--------|--------------|---------------|
| Static SVD | 0.8367 / 0.4045 | 0.9386 / 0.2681 |
| MWG-EW | 0.1018 / 0.9477 | 0.1097 / 0.9471 |

- The generator reaches near-identical quality on both models (rel MSE
  0.10-0.11, cosine ~0.95) while static SVD is markedly weaker on
  Baichuan (0.939 vs 0.837) — the conditional-generation advantage
  reproduces and is even more pronounced on the second model.
- Platform note: fp16/bf16 lm_head logits are degenerate on this Ascend
  NPU platform-wide (loss ~ ln(vocab)); the fp32 lm_head pre-hook
  workaround (see below) unlocks full-model CE evals at 13B scale.
- Artifacts: results/baichuan_multimodel_asi2_fp32_20260821T054249Z/
  (distillation output JSON + checkpoint
  mwg_expert_residual_r384.pt); run log
  logs/baichuan_distill_asi2_fp32_20260821T054249Z.log.

## Always-patched PPL (added 2026-08-21, with fp32 lm_head workaround)

- Found: fp16/bf16 lm_head on the Ascend NPU produces degenerate uniform
  logits (loss ~ ln(vocab)) platform-wide; casting the lm_head input to
  fp32 via a forward pre-hook restores normal logits (Qwen fp16 test:
  loss 2.37 / PPL 10.68). This unlocked the 13B full-model CE eval.
- Result (Baichuan2-13B layer-16 r384, uncalibrated student, router_eval
  slice, 5,964 tokens, fp32 lm_head):
  - dense: loss 1.4628 / PPL 4.318
  - patched: loss 1.4850 / PPL 4.415
  - **ppl_ratio 1.0225x** — always-patched replacement degrades PPL by
    ~2.2% without calibration, qualitatively consistent with the Qwen
    uncalibrated baseline (1.287x on its Belle slice; corpora differ).
- The fp32-trained student (rel MSE 0.11 / cosine 0.95) makes the patch a
  good approximation; the residual 2.2% PPL cost is the approximation gap.
- Script: run_baichuan_eval_fixed.py on AI1 (log /tmp/bef.log).
