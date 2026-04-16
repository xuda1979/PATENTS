# MWG-EW Real GPU Benchmark Results

Timestamp: 20260414T115543Z

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
| dense_baseline | 4 | 512 | 2.756 | 742978.7 | 520.0 | 176.16 |
| mwg_ew_basis_bank_r32 | 4 | 512 | 1.201 | 1704679.8 | 621.03 | 15.22 |
| mwg_ew_basis_bank_r64 | 4 | 512 | 1.184 | 1729849.4 | 661.03 | 29.37 |
| mwg_ew_basis_bank_r128 | 4 | 512 | 1.611 | 1271192.4 | 741.03 | 57.68 |
| mwg_ew_basis_bank_r256 | 4 | 512 | 2.977 | 687970.6 | 902.04 | 114.31 |

### Quality

| max_abs_error | mean_relative_error | cosine_similarity | label |
| --- | --- | --- | --- |
| 0.565918 | nan | 0.0 | mwg_ew_basis_bank_r32 |
| 0.565918 | nan | 0.0 | mwg_ew_basis_bank_r64 |
| 0.565918 | nan | 0.0 | mwg_ew_basis_bank_r128 |
| 0.565918 | nan | 0.0 | mwg_ew_basis_bank_r256 |

### HBM Traffic

| label | total_param_bytes | total_param_mib | estimated_hbm_read_per_forward_mib |
| --- | --- | --- | --- |
| dense_baseline | 352321536 | 336.0 | 336.0 |
| mwg_ew_basis_bank_r32 | 30433280 | 29.02 | 29.02 |
| mwg_ew_basis_bank_r64 | 58744832 | 56.02 | 56.02 |
| mwg_ew_basis_bank_r128 | 115367936 | 110.02 | 110.02 |
| mwg_ew_basis_bank_r256 | 228614144 | 218.02 | 218.02 |

