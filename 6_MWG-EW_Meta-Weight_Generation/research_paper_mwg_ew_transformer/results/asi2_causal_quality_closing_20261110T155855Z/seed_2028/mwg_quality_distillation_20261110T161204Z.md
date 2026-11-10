# MWG-EW Quality Distillation

Created: `20261110T161204Z`
World size: `4`
Device: `npu`
Teacher: `{'gate': 'model.layers.16.mlp.gate_proj.weight', 'up': 'model.layers.16.mlp.up_proj.weight', 'down': 'model.layers.16.mlp.down_proj.weight', 'state_file': '/root/work/filestorage/Qwen2.5-1.5B-Instruct/model.safetensors', 'layer': '16', 'model_digest': 'b6c944482ac7fe5c54afe482fadc7cf9a100a652a79ca1fbe684e268261c1c40'}`

| Method | Rank | Rel. MSE | Cosine | Params MiB | Persistent-factor MiB | Analytic dense/factor payload |
|---|---:|---:|---:|---:|---:|---:|
| dense_teacher | None | 0 | 1.000000 | 157.5 | None | None |
| static_svd_r384 | 384 | 0.833522 | 0.414622 |  | 46.125 | 3.415 |
| persistent_low_rank_r384 | 384 | 0.446165 | 0.745798 | 46.125 | 46.125 | 3.415 |
| mwg_token_diag_core_r384 | 384 | 0.44661 | 0.745574 | 48.099 | 46.125 | 3.415 |
| static_svd_r401 | 401 | 0.82284 | 0.427270 |  | 48.167 | 3.27 |
| persistent_low_rank_r401 | 401 | 0.436463 | 0.752305 | 48.167 | 48.167 | 3.27 |
| mwg_token_diag_core_r401 | 401 | 0.43685 | 0.752144 | 50.178 | 48.167 | 3.27 |
| static_svd_r512 | 512 | 0.751507 | 0.503046 |  | 61.5 | 2.561 |
| persistent_low_rank_r512 | 512 | 0.37599 | 0.791398 | 61.5 | 61.5 | 2.561 |
