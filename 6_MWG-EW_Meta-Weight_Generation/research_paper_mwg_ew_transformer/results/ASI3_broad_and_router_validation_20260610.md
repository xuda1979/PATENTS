# ASI3 Broad and Router Validation, 2026-06-10

Environment: ASI3, Ascend 910B2, `ASCEND_RT_VISIBLE_DEVICES=0`.

Checkpoint:
`/vllm-workspace/mwg-ew-transformer-research/results/asi3_layer16_recovery_20260610T020738Z/layer16/checkpoints/mwg_expert_residual_r384_belle_lmce_cal_1200.pt`

## Broad Validation

Run: `asi3_broad_validation_20260610T051748Z`

Status: `done`

Manifest: `/vllm-workspace/mwg-ew-transformer-research/data/heldout/manifest.json`

Results:

| Suite | Tokens | Dense PPL | Patched PPL | PPL ratio |
| --- | ---: | ---: | ---: | ---: |
| GSM8K test | 22,655 | 3.461194 | 2.772514 | 0.801028 |
| MBPP test | 6,767 | 3.961548 | 3.024176 | 0.763382 |
| Alpaca cleaned train tail | 18,186 | 3.818243 | 3.816426 | 0.999524 |
| Token-weighted aggregate | 47,608 | - | - | 0.871502 |

Interpretation: this is a positive broad always-patched validation for the
2026-06-10 calibrated layer-16 checkpoint. It supersedes older always-patched
broad controls for the calibrated checkpoint, while the selective-router claim
remains the deployment-oriented claim because it reduces the number of patched
tokens.

## Router/Global Suite

Run: `asi3_token_router_global_suite_balanced_1npu_20260610T052338Z`

Status: `done`

Split manifest: `data/heldout/router_global_splits/manifest.json`

Eval summary:

| Policy | Tokens | Dense PPL | Patched/mixed PPL | PPL ratio |
| --- | ---: | ---: | ---: | ---: |
| Always patched eval split | 45,027 | 3.677811 | 3.164644 | 0.860469 |
| Router target 0.05 | 45,384 | 3.677811 baseline | 3.623168 | 0.985142 |
| Router target 0.10 | 45,384 | 3.677811 baseline | 3.533190 | 0.960677 |
| Router target 0.25 | 45,384 | 3.677811 baseline | 3.356569 | 0.912654 |

Eval suite ratios for the always-patched checkpoint:

| Suite | Examples | Tokens | PPL ratio |
| --- | ---: | ---: | ---: |
| GSM8K test | 130 | 23,015 | 0.799747 |
| MBPP test | 97 | 4,551 | 0.734979 |
| Alpaca cleaned train tail | 130 | 17,461 | 0.987350 |

Router mixed frontier actual patch fractions:

| Target patch fraction | Actual patch fraction | PPL ratio |
| ---: | ---: | ---: |
| 0.05 | 0.007200 | 0.985142 |
| 0.10 | 0.019192 | 0.960677 |
| 0.25 | 0.068781 | 0.912654 |

Interpretation: the calibrated checkpoint is now beneficial both as a full
layer-16 patch on this disjoint router/global eval split and as a selective
dense-fallback policy. The paper should still avoid claiming full Transformer
replacement because the validation is one layer, one model family, and three
broad suite families.
