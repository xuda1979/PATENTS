# ASI2 MWG-EW Transformer Benchmark

Created: `20260923T025207Z`
World size: `4`
Backend: `hccl`
Visible NPUs: `0,1,2,3`

## Configuration

```json
{
  "preset": "ASI2_sweep",
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
  "train_iters": 5,
  "comm_iters": 5,
  "conditioned_generator": true,
  "integrated_gradient_sync": {
    "enabled": true,
    "implementation": "DistributedDataParallel",
    "timed_work": "forward + loss + backward + gradient synchronization",
    "optimizer_step_included": false,
    "bucket_cap_mb": 25
  },
  "optimizer_inclusive_sync": {
    "enabled": true,
    "implementation": "DistributedDataParallel + torch.optim.AdamW(lr=1e-3, weight_decay=0)",
    "timed_work": "zero-grad + forward + loss + backward + gradient synchronization + elementwise optimizer update",
    "optimizer_step_included": true,
    "bucket_cap_mb": 25
  }
}
```

## Results

| Method | Params MiB | Descriptor MiB | Fwd ms | Train ms | Fwd speedup | Train speedup | Traffic reduction | AllReduce ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dense | 336.0 | 336.0 | 0.5918 | 6.5244 | 1.0 | 1.0 | 1.0 | 10.5672 |
| mwg_r32 | 7.564 | 3.375 | 0.8924 | 3.3125 | 0.663 | 1.97 | 99.556 | 0.6548 |
| mwg_r64 | 11.127 | 6.75 | 0.9285 | 3.356 | 0.637 | 1.944 | 49.778 | 0.7307 |
| mwg_r96 | 14.691 | 10.125 | 0.882 | 3.2031 | 0.671 | 2.037 | 33.185 | 0.8196 |
| mwg_r128 | 18.254 | 13.5 | 0.9093 | 3.2688 | 0.651 | 1.996 | 24.889 | 0.9135 |
| mwg_r192 | 25.38 | 20.25 | 0.8998 | 3.2442 | 0.658 | 2.011 | 16.593 | 1.1637 |
| mwg_r256 | 32.507 | 27.0 | 0.8777 | 3.2734 | 0.674 | 1.993 | 12.444 | 1.3635 |
| mwg_r384 | 46.76 | 40.5 | 1.0064 | 3.3088 | 0.588 | 1.972 | 8.296 | 1.8711 |
| mwg_r512 | 61.013 | 54.0 | 0.9383 | 3.3836 | 0.631 | 1.928 | 6.222 | 2.3455 |

## Integrated DDP Gradient Synchronization

`Train+sync` measures forward + loss + backward with DistributedDataParallel gradient synchronization. It excludes the optimizer step.

| Method | Train+sync ms | Train+sync speedup | Train+sync tok/s | Gradient payload MiB |
|---|---:|---:|---:|---:|
| dense | 15.0944 | 1.0 | 271358.91 | 336.0 |
| mwg_r32 | 5.3081 | 2.844 | 771650.87 | 7.564 |
| mwg_r64 | 5.1506 | 2.931 | 795247.16 | 11.127 |
| mwg_r96 | 5.2081 | 2.898 | 786467.23 | 14.691 |
| mwg_r128 | 5.1371 | 2.938 | 797337.02 | 18.254 |
| mwg_r192 | 5.2715 | 2.863 | 777008.44 | 25.38 |
| mwg_r256 | 4.9588 | 3.044 | 826006.29 | 32.507 |
| mwg_r384 | 5.4035 | 2.793 | 758027.2 | 46.76 |
| mwg_r512 | 5.8451 | 2.582 | 700757.9 | 61.013 |

## Throughput and Communication

Decode tokens per timed step: `512`
Training tokens per timed step: `4096`

| Method | Decode tok/s | Train tok/s | Communication MiB | Communication reduction |
|---|---:|---:|---:|---:|
| dense | 865157.15 | 627797.19 | 336.0 | 1.0 |
| mwg_r32 | 573733.75 | 1236528.3 | 7.564 | 44.42 |
| mwg_r64 | 551427.03 | 1220500.6 | 11.127 | 30.196 |
| mwg_r96 | 580498.87 | 1278761.2 | 14.691 | 22.872 |
| mwg_r128 | 563070.49 | 1253059.23 | 18.254 | 18.407 |
| mwg_r192 | 569015.34 | 1262560.88 | 25.38 | 13.239 |
| mwg_r256 | 583342.83 | 1251298.34 | 32.507 | 10.336 |
| mwg_r384 | 508744.04 | 1237911.03 | 46.76 | 7.186 |
| mwg_r512 | 545667.7 | 1210544.98 | 61.013 | 5.507 |
