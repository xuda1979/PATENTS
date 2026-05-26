# AI3 MWG-EW Transformer Benchmark

Created: `20260518T070030Z`
World size: `4`
Backend: `hccl`
Visible NPUs: `0,1,2,3`

## Configuration

```json
{
  "preset": "ai3_sweep",
  "d": 4096,
  "m": 14336,
  "ranks": [
    32,
    64,
    96,
    128,
    192,
    256,
    384,
    512
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
  "warmup": 3,
  "iters": 10,
  "train_iters": 3,
  "comm_iters": 5,
  "conditioned_generator": true
}
```

## Results

| Method | Params MiB | Descriptor MiB | Fwd ms | Train ms | Fwd speedup | Train speedup | Traffic reduction | AllReduce ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dense | 336.0 | 336.0 | 0.8715 | 5.3603 | 1.0 | 1.0 | 1.0 | 12.8545 |
| mwg_r32 | 7.564 | 3.375 | 1.24 | 3.5683 | 0.703 | 1.502 | 99.556 | 0.8614 |
| mwg_r64 | 11.127 | 6.75 | 1.2522 | 3.4146 | 0.696 | 1.57 | 49.778 | 0.9576 |
| mwg_r96 | 14.691 | 10.125 | 1.4806 | 3.4862 | 0.589 | 1.538 | 33.185 | 1.0482 |
| mwg_r128 | 18.254 | 13.5 | 1.2167 | 3.4103 | 0.716 | 1.572 | 24.889 | 1.1606 |
| mwg_r192 | 25.38 | 20.25 | 1.1661 | 3.4116 | 0.747 | 1.571 | 16.593 | 1.399 |
| mwg_r256 | 32.507 | 27.0 | 1.1859 | 3.6066 | 0.735 | 1.486 | 12.444 | 1.5745 |
| mwg_r384 | 46.76 | 40.5 | 1.288 | 3.5785 | 0.677 | 1.498 | 8.296 | 2.125 |
| mwg_r512 | 61.013 | 54.0 | 1.2741 | 3.5846 | 0.684 | 1.495 | 6.222 | 2.9204 |

## Throughput and Communication

Decode tokens per timed step: `512`
Training tokens per timed step: `4096`

| Method | Decode tok/s | Train tok/s | Communication MiB | Communication reduction |
|---|---:|---:|---:|---:|
| dense | 587492.83 | 764136.34 | 336.0 | 1.0 |
| mwg_r32 | 412903.23 | 1147885.55 | 7.564 | 44.42 |
| mwg_r64 | 408880.37 | 1199554.85 | 11.127 | 30.196 |
| mwg_r96 | 345805.75 | 1174918.25 | 14.691 | 22.872 |
| mwg_r128 | 420810.39 | 1201067.35 | 18.254 | 18.407 |
| mwg_r192 | 439070.41 | 1200609.68 | 25.38 | 13.239 |
| mwg_r256 | 431739.61 | 1135695.67 | 32.507 | 10.336 |
| mwg_r384 | 397515.53 | 1144613.66 | 46.76 | 7.186 |
| mwg_r512 | 401852.29 | 1142665.85 | 61.013 | 5.507 |
