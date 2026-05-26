# MWG-EW Quality Distillation

Created: `20260518T083242Z`
World size: `8`
Device: `npu`
Teacher: `Qwen2.5-1.5B-Instruct layer 0 FFN (gate_proj, up_proj, down_proj), model.safetensors`

| Method | Rank | Rel. MSE | Cosine | Params MiB | Descriptor MiB | Traffic red. |
|---|---:|---:|---:|---:|---:|---:|
| static_svd_r64 | 64 | 0.989094 | 0.133395 |  | 7.688 | 20.488 |
| persistent_low_rank_r64 | 64 | 0.966727 | 0.225573 | 9.096 | 7.688 | 20.488 |
| mwg_ephemeral_r64 | 64 | 0.966702 | 0.225632 | 9.096 | 7.688 | 20.488 |
| static_svd_r128 | 128 | 0.971749 | 0.187598 |  | 15.375 | 10.244 |
| persistent_low_rank_r128 | 128 | 0.942873 | 0.257047 | 17.066 | 15.375 | 10.244 |
| mwg_ephemeral_r128 | 128 | 0.942804 | 0.257052 | 17.066 | 15.375 | 10.244 |
