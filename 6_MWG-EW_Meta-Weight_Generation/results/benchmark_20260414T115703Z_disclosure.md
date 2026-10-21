# MWG-EW Real GPU Benchmark Results

Timestamp: 20260414T115703Z

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
    128,
    256
  ]
}

### Performance

| label | batch_size | seq_len | latency_ms | throughput_tokens_per_s | peak_memory_mib | model_params_m |
| --- | --- | --- | --- | --- | --- | --- |
| dense_baseline | 1 | 128 | 0.187 | 683471.9 | 72.5 | 34.6 |
| mwg_ew_direct_r32 | 1 | 128 | 0.655 | 195555.4 | 437.91 | 189.27 |
| mwg_ew_direct_r64 | 1 | 128 | 0.707 | 181131.3 | 799.32 | 378.01 |
| mwg_ew_direct_r128 | 1 | 128 | 1.194 | 107219.6 | 1524.0 | 755.5 |
| mwg_ew_direct_r256 | 1 | 128 | 2.251 | 56854.2 | 2970.75 | 1510.47 |

### Quality

| max_abs_error | mean_relative_error | cosine_similarity | label |
| --- | --- | --- | --- |
| 1.101562 | inf | 0.000245 | mwg_ew_direct_r32 |
| 2.664062 | inf | 0.000222 | mwg_ew_direct_r64 |
| 10.0 | inf | -0.001069 | mwg_ew_direct_r128 |
| 21.390625 | inf | -0.000495 | mwg_ew_direct_r256 |

### HBM Traffic

| label | total_param_bytes | total_param_mib | estimated_hbm_read_per_forward_mib |
| --- | --- | --- | --- |
| dense_baseline | 69206016 | 66.0 | 66.0 |
| mwg_ew_direct_r32 | 378535936 | 361.0 | 361.0 |
| mwg_ew_direct_r64 | 756023296 | 721.0 | 721.0 |
| mwg_ew_direct_r128 | 1510998016 | 1441.0 | 1441.0 |
| mwg_ew_direct_r256 | 3020947456 | 2881.0 | 2881.0 |

## patent_8b

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
  "d": 4096,
  "m": 14336,
  "batch_size": 4,
  "seq_len": 512,
  "dtype": "fp16",
  "ranks": [
    32,
    64,
    128,
    256
  ]
}

### Performance

| label | batch_size | seq_len | latency_ms | throughput_tokens_per_s | peak_memory_mib | model_params_m |
| --- | --- | --- | --- | --- | --- | --- |
| dense_baseline | 4 | 512 | 2.738 | 747965.2 | 520.0 | 176.16 |
| mwg_ew_basis_bank_r32 | 4 | 512 | 1.124 | 1822356.7 | 619.53 | 15.22 |
| mwg_ew_basis_bank_r64 | 4 | 512 | 1.043 | 1962906.6 | 660.03 | 29.37 |
| mwg_ew_basis_bank_r128 | 4 | 512 | 1.625 | 1260063.4 | 740.04 | 57.68 |
| mwg_ew_basis_bank_r256 | 4 | 512 | 2.979 | 687405.4 | 902.04 | 114.31 |

### Quality

| max_abs_error | mean_relative_error | cosine_similarity | label |
| --- | --- | --- | --- |
| 0.557617 | nan | 0.0 | mwg_ew_basis_bank_r32 |
| 0.557617 | nan | 0.0 | mwg_ew_basis_bank_r64 |
| 0.557617 | nan | 0.0 | mwg_ew_basis_bank_r128 |
| 0.557617 | nan | 0.0 | mwg_ew_basis_bank_r256 |

### HBM Traffic

| label | total_param_bytes | total_param_mib | estimated_hbm_read_per_forward_mib |
| --- | --- | --- | --- |
| dense_baseline | 352321536 | 336.0 | 336.0 |
| mwg_ew_basis_bank_r32 | 30433280 | 29.02 | 29.02 |
| mwg_ew_basis_bank_r64 | 58744832 | 56.02 | 56.02 |
| mwg_ew_basis_bank_r128 | 115367936 | 110.02 | 110.02 |
| mwg_ew_basis_bank_r256 | 228614144 | 218.02 | 218.02 |

## distributed_comm

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
  "d": 4096,
  "m": 14336,
  "rank": 128,
  "batch_size": 4,
  "seq_len": 512,
  "dtype": "fp16"
}

### Performance

| dense_grad_bytes | dense_grad_mib | mwg_ew_grad_bytes | mwg_ew_grad_mib | reduction_ratio | savings_pct |
| --- | --- | --- | --- | --- | --- |
| 352321536 | 336.0 | 115367936 | 110.02 | 3.05 | 67.3 |

