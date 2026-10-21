# MWG-EW Real GPU Benchmark Results

Timestamp: 20260414T114553Z

## pilot_1b

Environment: {
  "torch_version": "2.6.0+cpu",
  "device_backend": "npu",
  "npu_available": true,
  "npu_name": "Ascend910B2",
  "npu_count": 8,
  "npu_memory_gib": 60.96,
  "torch_npu_version": "2.6.0"
}

Config: {
  "d": 2048,
  "m": 5632,
  "batch_size": 1,
  "seq_len": 128,
  "dtype": "fp16",
  "ranks": [
    32,
    64,
    128
  ]
}

### Performance

| label | batch_size | seq_len | latency_ms | throughput_tokens_per_s | peak_memory_mib | model_params_m |
| --- | --- | --- | --- | --- | --- | --- |
| dense_baseline | 1 | 128 | 0.21 | 609183.6 | 72.5 | 34.6 |
| mwg_ew_direct_r32 | 1 | 128 | 0.894 | 143113.3 | 437.91 | 189.27 |
| mwg_ew_direct_r64 | 1 | 128 | 0.81 | 158103.4 | 799.32 | 378.01 |
| mwg_ew_direct_r128 | 1 | 128 | 1.226 | 104365.9 | 1524.0 | 755.5 |

### Quality

| max_abs_error | mean_relative_error | cosine_similarity | label |
| --- | --- | --- | --- |
| 1.112305 | inf | 0.002731 | mwg_ew_direct_r32 |
| 2.466797 | inf | -0.001151 | mwg_ew_direct_r64 |
| 8.203125 | inf | 0.001309 | mwg_ew_direct_r128 |

### HBM Traffic

| label | total_param_bytes | total_param_mib | estimated_hbm_read_per_forward_mib |
| --- | --- | --- | --- |
| dense_baseline | 69206016 | 66.0 | 66.0 |
| mwg_ew_direct_r32 | 378535936 | 361.0 | 361.0 |
| mwg_ew_direct_r64 | 756023296 | 721.0 | 721.0 |
| mwg_ew_direct_r128 | 1510998016 | 1441.0 | 1441.0 |

