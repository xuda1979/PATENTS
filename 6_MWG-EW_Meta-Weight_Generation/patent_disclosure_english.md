1.73×** | 352.6 |
| MWG-EW r=256 | 27.00 | **12.4×** | 0.1631 | **1.97×** | 363.1 |

**Scenario B: Prefill B=1, S=128 (128 Token Prefix Encoding)**

| Configuration | Weights (MiB) | Traffic Reduction | Latency (ms) | Speedup | Throughput (tok/s) |
|--------------|---------------|------------------|--------------|---------|-------------------|
| Dense Baseline | 336.00 | 1.0× | 0.3771 | 1.00× | 339,436 |
| MWG-EW r=32 | 3.38 | **99.6×** | 0.1911 | **1.97×** | 669,945 |
| MWG-EW r=64 | 6.75 | **49.8×** | 0.1737 | **2.17×** | 736,859 |
| MWG-EW r=128 | 13.50 | **24.9×** | 0.1576 | **2.39×** | 812,421 |
| MWG-EW r=256 | 27.00 | **12.4×** | 0.2017 | **1.87×** | 634,464 |

**Scenario C: Training B=4, S=512 (Training/Large Batch Inference)**

| Configuration | Weights (MiB) | Traffic Reduction | Latency (ms) | Speedup | Throughput (tok/s) |
|--------------|---------------|------------------|--------------|---------|-------------------|
| Dense Baseline | 336.00 | 1.0× | 2.8077 | 极