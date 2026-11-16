# Block-Givens tile-local apply — kernel prototype

## What this is

A prototype of the tile-local execution model for the input-dependent output
subspace `Q_theta(x)` (block Givens rotations applied to output tiles).  It is
a **prototype only**: the Ascend-C source here is not compiled, and no
performance claim is made for it.  Its purpose is to fix the semantics and the
scratch/accumulate/rotate/write execution shape that a future compiled kernel
must reproduce, and to provide an executable simulator used by the repository
tests to validate that shape.

## Execution model

For one FFN projection with persistent factors `U in R^{d x r}`,
`V in R^{r x d}`, token input tile `X in R^{Tm x d}` (Tm tokens), and this
tile's descriptor chunk (Givens angles) `theta in R^{Tm x d/2}`:

```
for each output tile n in [0, d, TILE_N):        # d = N_TILES * TILE_N
    1. scratch:    load theta[:, n/2 : n/2 + TILE_N/2]   (descriptor chunk)
    2. accumulate: Y_tile = (X @ U) @ V[:, n : n+TILE_N]  (tile's columns)
    3. rotate:     for k in [0, TILE_N/2):
                       (e, o) = (Y_tile[:, 2k], Y_tile[:, 2k+1])
                       Y_tile[:, 2k]   = cos*e - sin*o
                       Y_tile[:, 2k+1] = sin*e + cos*o
    4. write:      store Y_tile to the output tile
```

Givens pairs never straddle a tile boundary (`TILE_N` even), so each output
tile is a closed load/accumulate/rotate/write unit and the descriptor chunk a
tile needs is contiguous in the angle tensor.

## Contents

- `sim_block_givens_tile_apply.py` — executable simulator of the tile loop,
  including a per-tile scratch buffer that is explicitly loaded/cleared, used
  by `tests/test_block_givens.py` to validate tile equivalence against the
  vectorized reference in `experiments/mwg_block_givens.py`.
- `block_givens_tile_apply_kernel.cpp` — Ascend-C prototype kernel source for
  one output tile's apply step (scratch load of the angle chunk, in-place pair
  rotation of the accumulated tile, tile write).  **Not compiled here**; it
  documents the UB layout and the per-tile compute sequence a compiled
  implementation must match.

## Contract notes (mirrors ephemeral_core_apply's contract style)

- The angle tensor is an ordinary persistent GM tensor (it is a *descriptor*,
  not an ephemeral core): no lifetime claim is made about it.
- The rotation acts only inside a tile's registers/UB; no global scratch
  tensor is written for the intermediate rotated values.
- One global output (the rotated projection output); zero global workspace.
