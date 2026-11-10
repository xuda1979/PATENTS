# MWG-EW Quality Distillation

Created: `20261110T160130Z`
World size: `4`
Device: `npu`
Teacher: `{'gate': 'model.layers.16.mlp.gate_proj.weight', 'up': 'model.layers.16.mlp.up_proj.weight', 'down': 'model.layers.16.mlp.down_proj.weight', 'state_file': '/root/work/filestorage/Qwen2.5-1.5B-Instruct/model.safetensors', 'layer': '16', 'model_digest': 'b6c944482ac7fe5c54afe482fadc7cf9a100a652a79ca1fbe684e268261c1c40'}`

| Method | Rank | Rel. MSE | Cosine | Params MiB | Persistent-factor MiB | Analytic dense/factor payload |
|---|---:|---:|---:|---:|---:|---:|
| dense_teacher | None | 0 | 1.000000 | 157.5 | None | None |
| static_svd_r384 | 384 | 0.83485 | 0.413171 |  | 46.125 | 3.415 |
| persistent_low_rank_r384 | 384 | 0.445426 | 0.746393 | 46.125 | 46.125 | 3.415 |
| mwg_token_diag_core_r384 | 384 | 0.445802 | 0.746209 | 48.099 | 46.125 | 3.415 |
| static_svd_r401 | 401 | 0.824084 | 0.425939 |  | 48.167 | 3.27 |
| persistent_low_rank_r401 | 401 | 0.435813 | 0.752784 | 48.167 | 48.167 | 3.27 |
| mwg_token_diag_core_r401 | 401 | 0.436112 | 0.752639 | 50.178 | 48.167 | 3.27 |
| static_svd_r512 | 512 | 0.752769 | 0.501873 |  | 61.5 | 2.561 |
| persistent_low_rank_r512 | 512 | 0.375485 | 0.791781 | 61.5 | 61.5 | 2.561 |
