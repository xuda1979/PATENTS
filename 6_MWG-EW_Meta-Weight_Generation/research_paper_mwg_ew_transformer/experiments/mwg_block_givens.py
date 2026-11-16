"""Input-dependent output subspaces via block Givens rotations.

This module implements the dynamic output-subspace mechanism proposed in the
manuscript's future-work section: instead of modulating coefficients inside a
fixed rank-r output subspace (the ``diag`` core family, whose outputs always
lie in the column span of the right factor V), the descriptor here rotates the
*output coordinates themselves* per token.

Concretely, for each FFN projection the token descriptor emits one angle per
Givens pair of adjacent output coordinates.  Pairing adjacent coordinates
partitions the output dimension into blocks of width 2; applying all pair
rotations simultaneously is a block-diagonal orthogonal map

    Q_theta(x) = blockdiag(R(theta_0), R(theta_1), ..., R(theta_{d/2-1}))

with R(a) the 2x2 rotation [[cos a, -sin a], [sin a, cos a]].

Because every Q_theta(x) is orthogonal for any angles, the mechanism never
changes the output norm budget -- it only changes *which* directions of the
persistent right factor's row span are combined.  Composing with the frozen
low-rank projection, the effective output row space for token t becomes

    span(Q_theta(x_t) V^T)

which is input dependent while the persistent parameters remain exactly the
low-rank factors plus a small angle head.

Execution model (tile-local):
    The output dimension is processed in tiles of width ``tile`` (default 128).
    For one output tile, execution is:
      1. load this tile's descriptor chunk (its angles) into scratch;
      2. accumulate the tile's output rows from the rank contributions;
      3. apply the tile's block Givens rotations (angle pairs live entirely
         inside the tile);
      4. write the tile.
    Givens pairs never straddle tile boundaries, so each tile is a closed
    scratch/accumulate/rotate/write unit; see :func:`tile_local_apply` and
    :func:`apply_block_givens_tiles`.

Numerical notes:
    Angles are emitted through a bounded head (tanh) so rotations stay
    differentiable and well-conditioned.  All compositions here are exact in
    float32 against the dense-matrix reference up to tolerance; tests verify
    orthogonality, tile equivalence, and gradient flow.
"""

from __future__ import annotations

import math

import torch
import torch.nn as nn


def check_output_dim(output_dim: int, tile: int) -> None:
    """Validate that output_dim is tileable with tile-aligned Givens pairs."""
    if output_dim <= 0:
        raise ValueError(f"output_dim must be positive, got {output_dim}")
    if tile <= 0 or tile % 2 != 0:
        raise ValueError(f"tile must be a positive even number, got {tile}")
    if output_dim % tile != 0:
        raise ValueError(
            f"output_dim {output_dim} must be divisible by tile {tile}"
        )


def givens_pair_rotation(angles: torch.Tensor) -> torch.Tensor:
    """Compute per-token 2x2 Givens rotation matrices.

    Args:
        angles: tensor of shape (..., P) with one angle per Givens pair.

    Returns:
        Tensor of shape (..., P, 2, 2) with R(theta) blocks.
    """
    cos = torch.cos(angles)
    sin = torch.sin(angles)
    return torch.stack(
        [
            torch.stack([cos, -sin], dim=-1),
            torch.stack([sin, cos], dim=-1),
        ],
        dim=-2,
    )


def block_givens_matrix(angles: torch.Tensor, output_dim: int) -> torch.Tensor:
    """Explicit dense block-diagonal rotation matrix Q_theta.

    Args:
        angles: shape (..., output_dim // 2).
        output_dim: the output dimension D (even).

    Returns:
        Tensor of shape (..., D, D); ``blockdiag`` of the 2x2 rotations.
    """
    if output_dim % 2 != 0:
        raise ValueError(f"output_dim must be even, got {output_dim}")
    expected = (output_dim // 2,)
    if angles.shape[-1:] != expected:
        raise ValueError(
            f"angles last dim {angles.shape[-1]} must equal {output_dim // 2}"
        )
    rotations = givens_pair_rotation(angles)
    batch = angles.shape[:-1]
    q = rotations.new_zeros((*batch, output_dim, output_dim))
    ar = torch.arange(output_dim // 2, device=angles.device)
    even_rows = 2 * ar
    odd_rows = 2 * ar + 1
    # Q[..., 2k, 2k]     = cos_k
    # Q[..., 2k, 2k+1]   = -sin_k
    # Q[..., 2k+1, 2k]   = sin_k
    # Q[..., 2k+1, 2k+1] = cos_k
    q[..., even_rows, even_rows] = rotations[..., 0, 0]
    q[..., even_rows, even_rows + 1] = rotations[..., 0, 1]
    q[..., odd_rows, even_rows] = rotations[..., 1, 0]
    q[..., odd_rows, odd_rows] = rotations[..., 1, 1]
    return q


def apply_block_givens(
    y: torch.Tensor, angles: torch.Tensor
) -> torch.Tensor:
    """Apply per-token block Givens rotations to output pairs (reference).

    ``y`` has shape (..., N, D) with D even; ``angles`` has shape
    (..., N, D // 2).  Pair k of row t becomes

        [y[t, 2k], y[t, 2k+1]] <- R(theta_{t,k}) [y[t, 2k], y[t, 2k+1]]

    Args:
        y: outputs to rotate, shape (..., N, D), D even.
        angles: one angle per pair, shape (..., N, D // 2).

    Returns:
        Rotated outputs, same shape as ``y``.
    """
    if y.shape[-1] % 2 != 0:
        raise ValueError(f"output dim must be even, got {y.shape[-1]}")
    if angles.shape != y.shape[:-1] + (y.shape[-1] // 2,):
        raise ValueError(
            f"angles shape {tuple(angles.shape)} must equal "
            f"{tuple(y.shape[:-1])} + ({y.shape[-1] // 2},)"
        )
    cos = torch.cos(angles)
    sin = torch.sin(angles)
    even = y[..., 0::2]
    odd = y[..., 1::2]
    return torch.stack(
        [cos * even - sin * odd, sin * even + cos * odd], dim=-1
    ).flatten(-2)


def tile_local_apply(
    tile_output: torch.Tensor,
    tile_angles: torch.Tensor,
) -> torch.Tensor:
    """One tile's scratch/rotate step of the tile-local execution model.

    Args:
        tile_output: this tile's accumulated output rows, shape (..., tile).
        tile_angles: this tile's descriptor chunk, shape (..., tile // 2).

    Returns:
        The rotated tile, shape (..., tile).
    """
    return apply_block_givens(tile_output, tile_angles)


def apply_block_givens_tiles(
    y: torch.Tensor, angles: torch.Tensor, tile: int
) -> torch.Tensor:
    """Tile-local application of block Givens rotations.

    Semantically identical to :func:`apply_block_givens`; the loop over tiles
    documents and verifies the tile-local execution model: for one output
    tile, load the tile's angle chunk into scratch, rotate the tile's pairs,
    and write the tile.  Pairs never straddle tile boundaries because tile is
    even and each tile contains ``tile // 2`` whole pairs.
    """
    check_output_dim(y.shape[-1], tile)
    pairs_per_tile = tile // 2
    tiles: list[torch.Tensor] = []
    for start in range(0, y.shape[-1], tile):
        stop = start + tile
        tile_out = y[..., start:stop]
        tile_angles = angles[..., start // 2 : start // 2 + pairs_per_tile]
        tiles.append(tile_local_apply(tile_out, tile_angles))
    return torch.cat(tiles, dim=-1)


class BlockGivensOutputHead(nn.Module):
    """Descriptor head emitting per-pair Givens angles.

    The head is a small MLP whose output is squashed by ``amplitude * tanh``
    so angles live in (-amplitude, amplitude).  ``amplitude=0`` disables the
    rotation (ablation control).
    """

    def __init__(
        self,
        descriptor_dim: int,
        hidden_dim: int,
        output_dim: int,
        tile: int,
        amplitude: float,
    ) -> None:
        super().__init__()
        check_output_dim(output_dim, tile)
        self.output_dim = output_dim
        self.tile = tile
        self.amplitude = float(amplitude)
        self.head = nn.Sequential(
            nn.Linear(descriptor_dim, hidden_dim, dtype=torch.float32),
            nn.SiLU(),
            nn.Linear(hidden_dim, output_dim // 2, dtype=torch.float32),
        )

    def forward(self, descriptor: torch.Tensor) -> torch.Tensor:
        raw = self.head(descriptor.float())
        return self.amplitude * torch.tanh(raw)


class BlockGivensLowRank(nn.Module):
    """Low-rank projection with input-dependent output subspace.

    Forward:
        z = x @ U                       (rank activation)
        y = z @ V                       (output in span(V^T))
        y_rot = apply_block_givens_tiles(y, Q_theta(x), tile)

    The persistent parameters are U, V and the small angle head; no core is
    ever materialized as a rank x rank object.
    """

    def __init__(
        self,
        u: torch.Tensor,
        v: torch.Tensor,
        hidden_dim: int,
        tile: int = 128,
        amplitude: float = math.pi / 8,
    ) -> None:
        super().__init__()
        if u.shape[1] != v.shape[0]:
            raise ValueError(
                f"factor inner dims must match: U {tuple(u.shape)}, "
                f"V {tuple(v.shape)}"
            )
        self.u = nn.Parameter(u.detach().clone())
        self.v = nn.Parameter(v.detach().clone())
        self.tile = tile
        self.output_dim = int(v.shape[1])
        check_output_dim(self.output_dim, tile)
        self.head = BlockGivensOutputHead(
            int(u.shape[0]), hidden_dim, self.output_dim, tile, amplitude
        )

    def angles(self, x: torch.Tensor) -> torch.Tensor:
        """Descriptor angles Q_theta(x) for each token."""
        return self.head(x)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        angles = self.head(x)
        y = (x @ self.u) @ self.v
        return apply_block_givens_tiles(y, angles, self.tile)

    def reference_forward(self, x: torch.Tensor) -> torch.Tensor:
        """Dense reference: rotate with the explicit matrix Q_theta(x).

        Q_theta acts on output columns as y_new^T = Q_theta y^T, so the
        row-vector form is y_new = y @ Q_theta^T.
        """
        angles = self.head(x)
        q = block_givens_matrix(angles, self.output_dim)
        y = (x @ self.u) @ self.v
        return torch.matmul(y.unsqueeze(-2), q.transpose(-2, -1)).squeeze(-2)


def block_givens_orthogonality_error(angles: torch.Tensor, output_dim: int) -> float:
    """Max |Q^T Q - I| entry, used by tests to verify orthogonality."""
    q = block_givens_matrix(angles, output_dim)
    eye = torch.eye(output_dim, dtype=q.dtype, device=q.device)
    qtq = torch.matmul(q.transpose(-2, -1), q)
    return float((qtq - eye).abs().max())
