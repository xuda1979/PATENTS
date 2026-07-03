# ASI3 Layer-16 Recovery Verified Snapshot

Date: 2026-06-10 Asia/Shanghai

Run observed on ASI3 before the `/vllm-workspace` container reset:
`asi3_layer16_recovery_20260609T140159Z`.

Verified artifacts from terminal output:

| Method | Rank | Rel. MSE | Cosine | Params MiB | Descriptor MiB | Traffic red. |
|---|---:|---:|---:|---:|---:|---:|
| static_svd_r384 | 384 | 0.836682 | 0.404468 |  | 46.125 | 3.415 |
| mwg_expert_residual_r384 | 384 | 0.101849 | 0.947711 | 64.325 | 46.125 | 3.415 |

Observed remote files before reset:

- `results/asi3_layer16_recovery_20260609T140159Z/layer16/checkpoints/mwg_expert_residual_r384.pt`
- `results/asi3_layer16_recovery_20260609T140159Z/layer16/mwg_quality_distillation_20260609T140309Z.json`
- `results/asi3_layer16_recovery_20260609T140159Z/layer16/mwg_quality_distillation_20260609T140309Z.md`

Boundary:

- The layer-16 distillation result is verified from ASI3 terminal output.
- The subsequent LM-CE calibration and hybrid eval had not completed before the remote project disappeared.
- Use this as generator-side evidence only; do not claim completed calibration from this run.
