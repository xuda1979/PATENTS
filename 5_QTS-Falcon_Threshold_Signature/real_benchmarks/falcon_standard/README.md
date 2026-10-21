# Real Falcon Benchmark — COMPLETED

This directory contains **real** Falcon benchmark results from actual algorithm execution.

## Rules

- No simulated data
- No toy Falcon implementation
- No hand-written placeholder numbers
- All reported results come from an actual implementation run

## Implementation

| Item | Value |
|------|-------|
| Source | [tprest/falcon.py](https://github.com/tprest/falcon.py) by Thomas Prest (Falcon co-author) |
| License | MIT |
| Language | Pure Python (no C build tools required) |
| Clone location | `falcon_impl/` |
| Dependencies | `numpy`, `pycryptodome`, `beartype` |

This implementation faithfully follows the Falcon Round 3 specification: real NTRU key generation, real ffSampling-based signing, real NTT-based verification.

## Results

Benchmark executed on 2026-03-09 with Python 3.13.6 on Windows 11.

| Parameter | Keygen (ms) | Sign (ms) | Verify (ms) | SK (B) | VK (B) | Sig (B) |
|-----------|-------------|-----------|-------------|--------|--------|---------|
| Falcon-256 | 1,204.9 | 16.8 | 3.8 | 1,792 | 448 | 356 |
| Falcon-512 | 5,749.3 | 41.6 | 9.7 | 3,584 | 896 | 666 |
| Falcon-1024 | 21,201.6 | 91.7 | 20.8 | 7,168 | 1,792 | 1,280 |

## Output files

- `results/raw_benchmark.csv` — 69 individual per-iteration measurements
- `results/summary.json` — machine-readable aggregate statistics
- `results/report.md` — full analysis report with patent relevance
- `benchmark_falcon.py` — benchmark runner script

## Reproducibility

```bash
cd real_benchmarks/falcon_standard
pip install numpy pycryptodome beartype
python benchmark_falcon.py --kg 3 --sv 10 --params 256,512,1024
```

## Previous liboqs attempt

The initial plan was to use `liboqs-python` + `liboqs` (C library). This was blocked on this machine due to missing CMake/MSVC build tools and a broken auto-install branch mapping in the Python binding. The `probe_liboqs.py` script documents this diagnostic. The solution was to use Thomas Prest's pure-Python implementation instead, which requires no native build tools.
