# ASI2 MWG-EW Transformer Benchmark

Created: `20260923T025131Z`
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
| dense | 336.0 | 336.0 | 0.5856 | 6.3205 | 1.0 | 1.0 | 1.0 | 10.4386 |
| mwg_r32 | 7.564 | 3.375 | 0.9972 | 3.0225 | 0.587 | 2.091 | 99.556 | 0.6379 |
| mwg_r64 | 11.127 | 6.75 | 0.851 | 2.8839 | 0.688 | 2.192 | 49.778 | 0.7459 |
| mwg_r96 | 14.691 | 10.125 | 0.8594 | 2.9562 | 0.681 | 2.138 | 33.185 | 0.8308 |
| mwg_r128 | 18.254 | 13.5 | 0.8597 | 3.099 | 0.681 | 2.04 | 24.889 | 0.9209 |
| mwg_r192 | 25.38 | 20.25 | 0.8654 | 3.0017 | 0.677 | 2.106 | 16.593 | 1.14 |
| mwg_r256 | 32.507 | 27.0 | 0.9424 | 3.3829 | 0.621 | 1.868 | 12.444 | 1.3353 |
| mwg_r384 | 46.76 | 40.5 | 0.9214 | 3.0604 | 0.636 | 2.065 | 8.296 | 1.8337 |
| mwg_r512 | 61.013 | 54.0 | 0.9343 | 3.1971 | 0.627 | 1.977 | 6.222 | 2.3314 |

## Integrated DDP Gradient Synchronization

`Train+sync` measures forward + loss + backward with DistributedDataParallel gradient synchronization. It excludes the optimizer step.

| Method | Train+sync ms | Train+sync speedup | Train+sync tok/s | Gradient payload MiB |
|---|---:|---:|---:|---:|
| dense | 15.3869 | 1.0 | 266200.47 | 336.0 |
| mwg_r32 | 4.5943 | 3.349 | 891539.52 | 7.564 |
| mwg_r64 | 4.504 | 3.416 | 909413.85 | 11.127 |
| mwg_r96 | 5.2079 | 2.955 | 786497.44 | 14.691 |
| mwg_r128 | 4.821 | 3.192 | 849616.26 | 18.254 |
| mwg_r192 | 5.1155 | 3.008 | 800703.74 | 25.38 |
| mwg_r256 | 4.7251 | 3.256 | 866859.96 | 32.507 |
| mwg_r384 | 5.0387 | 3.054 | 812908.09 | 46.76 |
| mwg_r512 | 6.0969 | 2.524 | 671816.82 | 61.013 |

## Throughput and Communication

Decode tokens per timed step: `512`
Training tokens per timed step: `4096`

| Method | Decode tok/s | Train tok/s | Communication MiB | Communication reduction |
|---|---:|---:|---:|---:|
| dense | 874316.94 | 648050.0 | 336.0 | 1.0 |
| mwg_r32 | 513437.63 | 1355169.56 | 7.564 | 44.42 |
| mwg_r64 | 601645.12 | 1420298.9 | 11.127 | 30.196 |
| mwg_r96 | 595764.49 | 1385562.55 | 14.691 | 22.872 |
| mwg_r128 | 595556.59 | 1321716.68 | 18.254 | 18.407 |
| mwg_r192 | 591633.93 | 1364560.08 | 25.38 | 13.239 |
| mwg_r256 | 543293.72 | 1210795.47 | 32.507 | 10.336 |
| mwg_r384 | 555676.14 | 1338387.14 | 46.76 | 7.186 |
| mwg_r512 | 548003.85 | 1281161.05 | 61.013 | 5.507 |
