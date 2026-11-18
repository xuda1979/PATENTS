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


# ---------------------------------------------------------------------------
# Kernel-faithful numeric model (closes the algorithm-correctness question)
# ---------------------------------------------------------------------------
# The Ascend-C prototype (block_givens_tile_apply_kernel.cpp) computes, per
# output tile of width TILE_N and per row-block of TILE_M tokens:
#
#   z  <- fp16(rank_activation)            [GM load, fp16]
#   v  <- fp16(v_tile)                     [GM load, fp16]
#   c  <- fp32(z @ v) accumulated element-wise
#   a  <- fp32(angles)                     [GM load, fp32 descriptor]
#   cos/sin <- fp32 transcendental of a
#   c  <- pair rotation in fp32, in place
#   out <- fp16(c)                         [CAST_NONE to fp16, GM store]
#
# The model below reproduces that numeric sequence on CPU so the kernel's
# *algorithm* can be validated against the reference block-Givens path
# (experiments/mwg_block_givens.apply_block_givens on the dense projection)
# without a device.  It is a correctness model only: no timing, no UB
# scheduling, no multi-core partition claim.

KERNEL_TILE_M = 8     # tokens per M tile (kernel constexpr TILE_M)
KERNEL_TILE_N = 128   # output tile width (kernel constexpr TILE_N)
KERNEL_MAX_RANK = 128  # kernel constexpr MAX_RANK


def simulate_kernel_numeric_model(
    x: torch.Tensor,
    u: torch.Tensor,
    v: torch.Tensor,
    angles: torch.Tensor,
    tile_m: int = KERNEL_TILE_M,
    tile_n: int = KERNEL_TILE_N,
) -> tuple[torch.Tensor, dict[str, int]]:
    """Numeric model of the Ascend-C kernel's compute sequence.

    Mirrors block_givens_tile_apply_kernel.cpp exactly:
      * the rank activation is materialized in fp16 before the tile loop
        (the kernel loads z = fp16(rankActivation) from GM);
      * each M-tile processes min(TILE_M, T - rowStart) rows (partial tiles
        handled by the kernel's rows = Min(...) logic);
      * the accumulate is an explicit fp32 element-wise loop over the tile
        (the prototype's MatmulZxV stand-in);
      * cos/sin are fp32; the rotation is fp32 in place;
      * the result is cast to fp16 (CAST_NONE) on store.

    Returns (output fp16 (T, d), stats).
    """
    d = v.shape[1]
    t_count = x.shape[0]
    rank = v.shape[0]
    if tile_n <= 0 or d % tile_n != 0 or tile_n % 2 != 0:
        raise ValueError(f"tile_n must be a positive even divisor of d={d}")
    if tile_m <= 0:
        raise ValueError("tile_m must be positive")
    if rank > KERNEL_MAX_RANK:
        raise ValueError(
            f"rank {rank} exceeds the kernel's MAX_RANK={KERNEL_MAX_RANK}")
    if angles.shape != (t_count, d // 2):
        raise ValueError(
            f"angles must have shape {(t_count, d // 2)}, "
            f"got {tuple(angles.shape)}"
        )

    # GM-resident inputs as the kernel sees them (fp16 activation/factors,
    # fp32 descriptor).
    rank_activation = (x @ u).to(torch.float16)
    v_fp16 = v.to(torch.float16)
    angles_fp32 = angles.to(torch.float32)

    out = torch.empty(t_count, d, dtype=torch.float16)
    m_tiles = (t_count + tile_m - 1) // tile_m
    n_tiles = d // tile_n
    for m in range(m_tiles):
        row_start = m * tile_m
        rows = min(tile_m, t_count - row_start)
        for n in range(n_tiles):
            col_start = n * tile_n
            # 1. CopyIn: z tile and angle chunk from GM (fp16 / fp32).
            z_tile = rank_activation[row_start:row_start + rows, :].to(
                torch.float32)
            v_tile = v_fp16[:, col_start:col_start + tile_n].to(torch.float32)
            angle_chunk = angles_fp32[
                row_start:row_start + rows,
                col_start // 2:col_start // 2 + tile_n // 2,
            ]
            # 2. MatmulZxV: explicit fp32 accumulate (prototype stand-in).
            c = torch.zeros(rows, tile_n, dtype=torch.float32)
            for t in range(rows):
                for j in range(tile_n):
                    acc = 0.0
                    for k in range(rank):
                        acc += float(z_tile[t, k]) * float(v_tile[k, j])
                    c[t, j] = acc
            # 3. rotate: fp32 cos/sin, in-place pair rotation.
            cos = torch.cos(angle_chunk)
            sin = torch.sin(angle_chunk)
            for t in range(rows):
                for k in range(tile_n // 2):
                    e = float(c[t, 2 * k])
                    o = float(c[t, 2 * k + 1])
                    cc = float(cos[t, k])
                    ss = float(sin[t, k])
                    c[t, 2 * k] = cc * e - ss * o
                    c[t, 2 * k + 1] = ss * e + cc * o
            # 4. CopyOut: fp16 cast (CAST_NONE) and store.
            out[row_start:row_start + rows,
                col_start:col_start + tile_n] = c.to(torch.float16)
    stats = {
        "m_tiles": m_tiles,
        "n_tiles": n_tiles,
        "tile_m": tile_m,
        "tile_n": tile_n,
        "partial_m_tiles": sum(
            1 for m in range(m_tiles)
            if min(tile_m, t_count - m * tile_m) < tile_m),
    }
    return out, stats
