# ASI3 MWG-EW Transformer Benchmark

Created: `20260430T092119Z`
World size: `4`
Backend: `hccl`
Visible NPUs: `0,1,2,3`

## Configuration

```json
{
  "preset": "ASI3_large",
  "d": 4096,
  "m": 14336,
  "ranks": [
    64,
    128,
    256
  ],
  "dtype": "float16",
  "decode_shape": [
    1,
    128,
    4096
  ],
  "train_shape": [
    2,
    512,
    4096
  ],
  "warmup": 4,
  "iters": 12,
  "train_iters": 4,
  "comm_iters": 4,
  "conditioned_generator": true
}
```

## Results

| Method | Params MiB | Descriptor MiB | Fwd ms | Train ms | Fwd speedup | Train speedup | Traffic reduction | AllReduce ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dense | 336.0 | 336.0 | 0.9275 | 5.4483 | 1.0 | 1.0 | 1.0 | 10.9841 |
| mwg_r64 | 11.127 | 6.75 | 1.392 | 3.6486 | 0.666 | 1.493 | 49.778 | 0.9714 |
| mwg_r128 | 18.254 | 13.5 | 1.5094 | 3.5931 | 0.614 | 1.516 | 24.889 | 1.2116 |
| mwg_r256 | 32.507 | 27.0 | 1.2347 | 3.8407 | 0.751 | 1.419 | 12.444 | 1.5495 |
