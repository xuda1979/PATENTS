# AI3 MWG-EW Transformer Benchmark

Created: `20260512T071342Z`
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
| dense | 336.0 | 336.0 | 0.8802 | 5.4167 | 1.0 | 1.0 | 1.0 | 12.6704 |
| mwg_r32 | 7.564 | 3.375 | 1.216 | 3.23 | 0.724 | 1.677 | 99.556 | 0.8374 |
| mwg_r64 | 11.127 | 6.75 | 1.209 | 3.1465 | 0.728 | 1.722 | 49.778 | 1.0547 |
| mwg_r96 | 14.691 | 10.125 | 1.1902 | 3.2182 | 0.74 | 1.683 | 33.185 | 1.0973 |
| mwg_r128 | 18.254 | 13.5 | 1.3692 | 3.3368 | 0.643 | 1.623 | 24.889 | 1.1633 |
| mwg_r192 | 25.38 | 20.25 | 1.3861 | 3.3357 | 0.635 | 1.624 | 16.593 | 1.3849 |
| mwg_r256 | 32.507 | 27.0 | 1.3959 | 3.4419 | 0.631 | 1.574 | 12.444 | 1.6034 |
| mwg_r384 | 46.76 | 40.5 | 1.4137 | 3.4216 | 0.623 | 1.583 | 8.296 | 2.194 |
| mwg_r512 | 61.013 | 54.0 | 1.381 | 3.3813 | 0.637 | 1.602 | 6.222 | 3.0004 |

## Throughput and Communication

Decode tokens per timed step: `512`
Training tokens per timed step: `4096`

| Method | Decode tok/s | Train tok/s | Communication MiB | Communication reduction |
|---|---:|---:|---:|---:|
| dense | 581685.98 | 756179.96 | 336.0 | 1.0 |
| mwg_r32 | 421052.63 | 1268111.46 | 7.564 | 44.42 |
| mwg_r64 | 423490.49 | 1301763.86 | 11.127 | 30.196 |
| mwg_r96 | 430179.8 | 1272761.17 | 14.691 | 22.872 |
| mwg_r128 | 373940.99 | 1227523.38 | 18.254 | 18.407 |
| mwg_r192 | 369381.72 | 1227928.17 | 25.38 | 13.239 |
| mwg_r256 | 366788.45 | 1190040.38 | 32.507 | 10.336 |
| mwg_r384 | 362170.19 | 1197100.77 | 46.76 | 7.186 |
| mwg_r512 | 370745.84 | 1211368.41 | 61.013 | 5.507 |
