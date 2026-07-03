# MWG-EW Quality Distillation

Created: `20260610T020848Z`
World size: `1`
Device: `npu`
Teacher: `{'gate': 'model.layers.16.mlp.gate_proj.weight', 'up': 'model.layers.16.mlp.up_proj.weight', 'down': 'model.layers.16.mlp.down_proj.weight', 'state_file': '/root/work/filestorage/Qwen2.5-1.5B-Instruct/model.safetensors', 'layer': '16'}`

| Method | Rank | Rel. MSE | Cosine | Params MiB | Descriptor MiB | Traffic red. |
|---|---:|---:|---:|---:|---:|---:|
| static_svd_r384 | 384 | 0.836682 | 0.404468 |  | 46.125 | 3.415 |
| mwg_expert_residual_r384 | 384 | 0.101849 | 0.947711 | 64.325 | 46.125 | 3.415 |
