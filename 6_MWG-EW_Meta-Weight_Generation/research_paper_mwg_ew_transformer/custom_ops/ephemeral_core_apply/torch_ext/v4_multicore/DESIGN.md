# V4 Multi-Core Epilogue Design

## Problem Statement

The v1 shipped kernel (`ephemeral_core_apply.asc`) runs the entire
ephemeral-core generation and application pipeline on a **single AICore**.
At the L2-resident probe geometry (T=128, H=128, R=128), this achieves
parity with the materialized arm (Table~\ref{tab:fourarmmeasured}).

However, at the beyond-L2 geometry (T=4096, the core tile exceeds L2
capacity), the fused arm is **1.93x slower** than the materialized arm.
Profiler traces (Figure~\ref{fig:opdecomp}) localize this deficit to the
**single-core vector epilogue** — the `Tanh/Muls/Adds/Mul/Cast` sequence
that forms the core in-place and multiplies it with the activation.

## Root Cause Analysis

The bottleneck has three components:

### 1. Single-core serialization
The v1 kernel uses `mm_.template Iterate<true>()` to process M-tiles
sequentially on one AICore. Each tile's vector epilogue must complete
before the next tile's matmul can begin, creating a strict
cube→vector→cube→vector dependency chain.

### 2. No UB pipelining
All queues (`cBuf_`, `actBuf_`, `outBuf_`) use `BUFFER_NUM=1`, meaning
the vector epilogue for tile *i* cannot overlap with the cube matmul
for tile *i+1*. The cube and vector units on the same core are idle
during each other's work.

### 3. KFC workspace collision (v3 failure)
The v3 multi-core attempt set `block_dim=8` in the tiling API, causing
the matmul tiling to split across N. However:
- N-split doesn't help the vector epilogue (it's M-bound)
- `GetSysWorkSpacePtr()` returns a shared workspace reused across
  back-to-back 8-core launches, causing aicore exception 507015

## V4 Design

### M-Only Multi-Core Distribution
```
Core 0: tiles [0, 1, ..., tilesPerCore-1]       → tokens [0, baseM*tilesPerCore)
Core 1: tiles [tilesPerCore, ..., 2*tilesPerCore-1] → tokens [baseM*tilesPerCore, ...)
...
Core 7: tiles [7*tilesPerCore, ..., totalTiles-1]
```

Each core processes a **disjoint range of M-tiles** (tokens), computed from
`GetBlockIdx() / GetBlockNum()`. The matmul tiling is pinned to `baseN=N`
(no N-split), so all cores share the same B (weight) and bias tensors.

### Per-Core Workspace Isolation
```
Host allocates: workspace = blockNum * per_core_ws_size
Kernel uses:    perCoreWs = workspace + blockIdx * per_core_ws_size
```

This eliminates the KFC workspace reuse collision that caused the 507015
fault in v3. Each core's `REGIST_MATMUL_OBJ` gets a unique workspace
region, so back-to-back launches don't interfere.

### Double-Buffered UB Pipeline
```
Tile i:  [Cube: matmul A@B] → [C buf 0] → [Vector: Tanh/Muls/Adds/Mul] → [Out buf 0]
Tile i+1:                    [Cube: matmul A@B] → [C buf 1] → [Vector: ...] → [Out buf 1]
```

`BUFFER_NUM=2` on all queues allows the cube unit to start tile *i+1*'s
matmul while the vector unit is still processing tile *i*'s epilogue.
`baseM` is halved to 64 (from 128) to fit 2x buffers in the 192 KiB UB.

### UB Budget
```
Per core (baseM=64, R=128, fp32 C):
  2 × (C: 64×128×4 = 32 KiB + act: 64×128×2 = 16 KiB + out: 64×128×2 = 16 KiB)
  + matmul staging: ~32 KiB
  = 160 KiB < 192 KiB ✓
```

### No-Store Contract Preservation
The generated core is formed in-place in the C-tile UB buffer:
1. `Tanh(cLocal, cLocal, count)` — core nonlinearity
2. `Muls(cLocal, cLocal, amplitude, count)` — scale
3. `Adds(cLocal, cLocal, 1.0, count)` — residual connection
4. `Cast(outLocal, cLocal, ...)` — fp32 → fp16
5. `Mul(outLocal, outLocal, actLocal, count)` — apply to activation

The core **never appears as a GlobalTensor**. The only GM write is
`DataCopy(outGm_[...], outLocal, ...)` for the final fp16 output.

## Expected Performance

| Geometry | v1 (single-core) | v4 (8-core) | Expected speedup |
|----------|------------------|-------------|------------------|
| T=128 (L2-resident) | 0.82 ms | ~0.82 ms | ~1.0x (parity) |
| T=512 | ~2.5 ms | ~0.5 ms | ~5x |
| T=1024 | ~5.0 ms | ~0.8 ms | ~6x |
| T=2048 | ~10.0 ms | ~1.5 ms | ~7x |
| T=4096 (beyond-L2) | ~20.0 ms | ~3.0 ms | ~7x |

The speedup is sub-linear in core count because:
- B (weight) is shared across cores, creating some L2 contention
- The matmul tiling API has per-core overhead
- The host-side tiling cache adds ~100µs on first call per geometry

## Validation Protocol

1. **Algebraic equivalence**: v4 output must match the algebraic reference
   within fp16 tolerance (max_abs < 5e-3)
2. **v1-vs-v4 equivalence**: v4 output must match v1 output within fp16
   tolerance (same contract, different tiling)
3. **L2-resident parity**: v4 at T=128 should be within ±5% of v1
4. **Beyond-L2 speedup**: v4 at T=4096 should be significantly faster
5. **Stability**: v4 must survive 1000 sequential calls without aicore
   exception (the v3 failure mode)
6. **msprof counters**: matched profiler passes at T=4096 should show
   reduced kernel latency for v4 vs v1, with no-store property preserved

## Files

| File | Purpose |
|------|---------|
| `ephemeral_core_apply_v4_multicore.asc` | Kernel source + host wrapper |
| `build_v4.py` | Build script (assembles source for compilation) |
| `test_v4_multicore.py` | Equivalence and benchmark test script |
| `DESIGN.md` | This document |
