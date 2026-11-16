"""Executable simulator of the tile-local block-Givens apply kernel.

This is the Python-side prototype of the kernel documented in this
directory's README: for each output tile, (1) load the tile's descriptor
chunk (its Givens angles) into a per-tile scratch buffer, (2) accumulate the
tile's output columns from the rank contributions, (3) apply the tile's block
Givens rotations in place, and (4) write the tile.

The simulator is intentionally explicit about the tile loop and the scratch
buffer so that tests can verify:

* tile equivalence — the tiled result equals the vectorized reference
  (``experiments.mwg_block_givens.apply_block_givens`` applied to the full
  projection);
* scratch discipline — the scratch buffer is fully overwritten by each
  tile's angle chunk before use (no stale-angle leakage between tiles);
* pair locality — no Givens pair reads or writes outside its tile.

It is a semantics prototype, not a performance model; no timing claim is
made for it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "experiments"))

from mwg_block_givens import (  # noqa: E402
    apply_block_givens,
    check_output_dim,
)


def simulate_tile_apply(
    x: torch.Tensor,
    u: torch.Tensor,
    v: torch.Tensor,
    angles: torch.Tensor,
    tile: int,
    scratch: torch.Tensor | None = None,
) -> tuple[torch.Tensor, dict[str, int]]:
    """Simulate the tile-local scratch/accumulate/rotate/write loop.

    Args:
        x: token inputs, shape (T, d).
        u: persistent left factor, shape (d, r).
        v: persistent right factor, shape (r, d).
        angles: descriptor angles, shape (T, d // 2).
        tile: output tile width TILE_N (even, divides d).
        scratch: optional preallocated per-tile angle scratch of shape
            (T, tile // 2); if given it must contain garbage (it is
            overwritten per tile, which the tests use to detect leakage).

    Returns:
        (rotated output (T, d), stats dict with tile counts).
    """
    d = v.shape[1]
    check_output_dim(d, tile)
    if angles.shape != (x.shape[0], d // 2):
        raise ValueError(
            f"angles must have shape {(x.shape[0], d // 2)}, got {tuple(angles.shape)}"
        )
    rank_activation = x @ u
    out = torch.empty_like(rank_activation @ v)
    if scratch is None:
        scratch = torch.empty(
            x.shape[0], tile // 2, dtype=angles.dtype, device=angles.device
        )
    if scratch.shape != (x.shape[0], tile // 2):
        raise ValueError(
            f"scratch must have shape {(x.shape[0], tile // 2)}, "
            f"got {tuple(scratch.shape)}"
        )
    tiles = 0
    pairs = 0
    for start in range(0, d, tile):
        stop = start + tile
        # 1. scratch: load this tile's descriptor chunk (angles).
        scratch.copy_(angles[:, start // 2 : start // 2 + tile // 2])
        # 2. accumulate: this tile's output columns from rank contributions.
        y_tile = rank_activation @ v[:, start:stop]
        # 3. rotate: apply the tile's block Givens rotations in place.
        y_tile = apply_block_givens(y_tile, scratch)
        # 4. write: store the rotated tile.
        out[:, start:stop] = y_tile
        tiles += 1
        pairs += tile // 2
    stats = {"tiles": tiles, "pairs_per_tile": tile // 2, "pairs_total": pairs}
    return out, stats


def simulate_tile_apply_from_dense(
    y_dense: torch.Tensor,
    angles: torch.Tensor,
    tile: int,
    scratch: torch.Tensor | None = None,
) -> torch.Tensor:
    """Tile-local rotation of an already-accumulated dense output.

    Convenience wrapper for tests: takes y = (x @ u) @ v directly and applies
    the tile loop (steps 1, 3, 4) without recomputing the projection.
    """
    d = y_dense.shape[-1]
    check_output_dim(d, tile)
    if angles.shape != y_dense.shape[:-1] + (d // 2,):
        raise ValueError("angles shape mismatch")
    out = torch.empty_like(y_dense)
    if scratch is None:
        scratch = torch.empty(
            *y_dense.shape[:-1], tile // 2, dtype=angles.dtype, device=angles.device
        )
    for start in range(0, d, tile):
        stop = start + tile
        scratch.copy_(angles[..., start // 2 : start // 2 + tile // 2])
        out[..., start:stop] = apply_block_givens(
            y_dense[..., start:stop], scratch
        )
    return out
