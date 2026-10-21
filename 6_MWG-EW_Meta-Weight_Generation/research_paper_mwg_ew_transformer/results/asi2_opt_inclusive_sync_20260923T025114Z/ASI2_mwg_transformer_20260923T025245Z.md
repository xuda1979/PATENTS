# ASI2 MWG-EW Transformer Benchmark

Created: `20260923T025245Z`
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
| dense | 336.0 | 336.0 | 1.3863 | 6.5534 | 1.0 | 1.0 | 1.0 | 10.4251 |
| mwg_r32 | 7.564 | 3.375 | 0.9046 | 3.1523 | 1.533 | 2.079 | 99.556 | 0.61 |
| mwg_r64 | 11.127 | 6.75 | 0.9135 | 3.1164 | 1.518 | 2.103 | 49.778 | 0.7124 |
| mwg_r96 | 14.691 | 10.125 | 0.8967 | 2.9698 | 1.546 | 2.207 | 33.185 | 0.8111 |
| mwg_r128 | 18.254 | 13.5 | 0.8709 | 3.009 | 1.592 | 2.178 | 24.889 | 0.958 |
| mwg_r192 | 25.38 | 20.25 | 0.8693 | 2.9817 | 1.595 | 2.198 | 16.593 | 1.1033 |
| mwg_r256 | 32.507 | 27.0 | 0.8746 | 3.041 | 1.585 | 2.155 | 12.444 | 1.3116 |
| mwg_r384 | 46.76 | 40.5 | 0.908 | 3.0109 | 1.527 | 2.177 | 8.296 | 1.8385 |
| mwg_r512 | 61.013 | 54.0 | 1.0503 | 3.3779 | 1.32 | 1.94 | 6.222 | 2.5094 |

## Integrated DDP Gradient Synchronization

`Train+sync` measures forward + loss + backward with DistributedDataParallel gradient synchronization. It excludes the optimizer step.

| Method | Train+sync ms | Train+sync speedup | Train+sync tok/s | Gradient payload MiB |
|---|---:|---:|---:|---:|
| dense | 16.3931 | 1.0 | 249861.22 | 336.0 |
| mwg_r32 | 5.0159 | 3.268 | 816603.2 | 7.564 |
| mwg_r64 | 5.2395 | 3.129 | 781753.98 | 11.127 |
| mwg_r96 | 4.7719 | 3.435 | 858358.31 | 14.691 |
| mwg_r128 | 5.048 | 3.247 | 811410.46 | 18.254 |
| mwg_r192 | 5.0767 | 3.229 | 806823.33 | 25.38 |
| mwg_r256 | 4.6997 | 3.488 | 871544.99 | 32.507 |
| mwg_r384 | 5.0339 | 3.257 | 813683.23 | 46.76 |
| mwg_r512 | 5.973 | 2.745 | 685752.55 | 61.013 |

## Throughput and Communication

Decode tokens per timed step: `512`
Training tokens per timed step: `4096`

| Method | Decode tok/s | Train tok/s | Communication MiB | Communication reduction |
|---|---:|---:|---:|---:|
| dense | 369328.43 | 625019.07 | 336.0 | 1.0 |
| mwg_r32 | 565996.02 | 1299368.71 | 7.564 | 44.42 |
| mwg_r64 | 560481.66 | 1314337.06 | 11.127 | 30.196 |
| mwg_r96 | 570982.49 | 1379217.46 | 14.691 | 22.872 |
| mwg_r128 | 587897.58 | 1361249.58 | 18.254 | 18.407 |
| mwg_r192 | 588979.64 | 1373712.98 | 25.38 | 13.239 |
| mwg_r256 | 585410.47 | 1346925.35 | 32.507 | 10.336 |
| mwg_r384 | 563876.65 | 1360390.58 | 46.76 | 7.186 |
| mwg_r512 | 487479.77 | 1212587.7 | 61.013 | 5.507 |
