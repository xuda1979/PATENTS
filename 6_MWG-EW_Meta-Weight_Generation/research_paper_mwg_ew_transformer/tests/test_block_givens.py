"""Tests for the block-Givens input-dependent output subspace Q_theta(x).

Covers:
  * pair rotation algebra (cos/sin pairing, sign convention);
  * orthogonality of Q_theta for arbitrary angle magnitudes;
  * tile-local execution equivalence: tiled apply == vectorized reference ==
    dense-matrix reference;
  * scratch discipline: per-tile angle scratch is overwritten each tile
    (garbage-filled scratch cannot leak between tiles);
  * descriptor head boundedness (tanh amplitude) and gradient flow;
  * end-to-end BlockGivensLowRank forward vs its dense reference;
  * the tile-local kernel simulator against the algebraic reference.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest
import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "experiments"))
sys.path.insert(0, str(REPO_ROOT / "custom_ops" / "block_givens_tile_apply"))

from mwg_block_givens import (  # noqa: E402
    BlockGivensLowRank,
    BlockGivensOutputHead,
    apply_block_givens,
    apply_block_givens_tiles,
    block_givens_matrix,
    block_givens_orthogonality_error,
    check_output_dim,
    givens_pair_rotation,
)
from sim_block_givens_tile_apply import (  # noqa: E402
    simulate_tile_apply,
    simulate_tile_apply_from_dense,
)


def test_check_output_dim_validation() -> None:
    check_output_dim(128, 128)
    check_output_dim(256, 128)
    with pytest.raises(ValueError):
        check_output_dim(0, 128)
    with pytest.raises(ValueError):
        check_output_dim(130, 128)
    with pytest.raises(ValueError):
        check_output_dim(256, 127)
    with pytest.raises(ValueError):
        check_output_dim(256, 0)


def test_givens_pair_rotation_values() -> None:
    angles = torch.tensor([0.0, math.pi / 2])
    rot = givens_pair_rotation(angles)
    assert rot.shape == (2, 2, 2)
    # R(0) = I
    assert torch.allclose(rot[0], torch.eye(2), atol=1e-6)
    # R(pi/2) = [[0, -1], [1, 0]]
    expected = torch.tensor([[0.0, -1.0], [1.0, 0.0]])
    assert torch.allclose(rot[1], expected, atol=1e-6)


def test_apply_block_givens_identity_and_quarter_turn() -> None:
    y = torch.tensor([[1.0, 2.0, 3.0, 4.0]])
    zero = torch.zeros(1, 2)
    out = apply_block_givens(y, zero)
    assert torch.allclose(out, y, atol=1e-6)

    quarter = torch.full((1, 2), math.pi / 2)
    out = apply_block_givens(y, quarter)
    # pair (1,2) -> (-2, 1); pair (3,4) -> (-4, 3)
    expected = torch.tensor([[-2.0, 1.0, -4.0, 3.0]])
    assert torch.allclose(out, expected, atol=1e-6)


def test_block_givens_matrix_orthogonality() -> None:
    torch.manual_seed(0)
    d = 64
    angles = (torch.rand(8, 16, d // 2) - 0.5) * 4.0  # up to +-2 rad
    err = block_givens_orthogonality_error(angles, d)
    assert err < 1e-5


def test_dense_matrix_matches_pairwise_apply() -> None:
    torch.manual_seed(1)
    n, d = 5, 32
    y = torch.randn(n, d)
    angles = (torch.rand(n, d // 2) - 0.5) * 2.0
    q = block_givens_matrix(angles, d)
    # Q acts on output columns; row-vector form is y @ Q^T.
    dense = torch.matmul(y.unsqueeze(-2), q.transpose(-2, -1)).squeeze(-2)
    pairwise = apply_block_givens(y, angles)
    assert torch.allclose(dense, pairwise, atol=1e-6)


def test_tiled_apply_matches_vectorized() -> None:
    torch.manual_seed(2)
    n, d = 7, 256
    y = torch.randn(2, n, d)
    angles = (torch.rand(2, n, d // 2) - 0.5) * 3.0
    reference = apply_block_givens(y, angles)
    for tile in (2, 16, 64, 128, 256):
        tiled = apply_block_givens_tiles(y, angles, tile)
        assert torch.allclose(tiled, reference, atol=1e-5), f"tile={tile}"


def test_output_head_boundedness() -> None:
    torch.manual_seed(3)
    amplitude = math.pi / 8
    head = BlockGivensOutputHead(64, 32, 128, 128, amplitude)
    x = torch.randn(20, 64) * 50.0  # extreme inputs
    angles = head(x)
    assert angles.shape == (20, 64)
    assert angles.abs().max() <= amplitude + 1e-6


def test_output_head_zero_amplitude_ablation() -> None:
    torch.manual_seed(4)
    head = BlockGivensOutputHead(32, 16, 64, 64, 0.0)
    x = torch.randn(4, 32)
    angles = head(x)
    assert torch.all(angles == 0.0)


def test_block_givens_low_rank_reference_equivalence() -> None:
    torch.manual_seed(5)
    d, r, out_d, hidden = 48, 16, 32, 24
    u = torch.randn(d, r)
    v = torch.randn(r, out_d)
    model = BlockGivensLowRank(u, v, hidden, tile=32, amplitude=0.7)
    x = torch.randn(6, d)
    fast = model(x)
    reference = model.reference_forward(x)
    assert fast.shape == (6, out_d)
    assert torch.allclose(fast, reference, atol=1e-5)


def test_block_givens_gradient_flow() -> None:
    torch.manual_seed(6)
    d, r, out_d, hidden = 32, 8, 16, 12
    u = torch.randn(d, r)
    v = torch.randn(r, out_d)
    model = BlockGivensLowRank(u, v, hidden, tile=16, amplitude=0.5)
    x = torch.randn(4, d)
    out = model(x)
    loss = out.pow(2).sum()
    loss.backward()
    u_param = model.u
    v_param = model.v
    assert u_param.grad is not None and u_param.grad.abs().sum() > 0
    assert v_param.grad is not None and v_param.grad.abs().sum() > 0
    head_params = list(model.head.parameters())
    assert all(p.grad is not None for p in head_params)
    assert any(p.grad.abs().sum() > 0 for p in head_params)


def test_amplitude_zero_reduces_to_persistent_low_rank() -> None:
    torch.manual_seed(7)
    d, r, out_d, hidden = 24, 6, 16, 8
    u = torch.randn(d, r)
    v = torch.randn(r, out_d)
    model = BlockGivensLowRank(u, v, hidden, tile=16, amplitude=0.0)
    x = torch.randn(3, d)
    out = model(x)
    persistent = (x @ u) @ v
    assert torch.allclose(out, persistent, atol=1e-6)


def test_tile_simulator_matches_algebraic_reference() -> None:
    torch.manual_seed(8)
    t, d, r, tile = 11, 64, 16, 16
    x = torch.randn(t, d)
    u = torch.randn(d, r)
    v = torch.randn(r, d)
    angles = (torch.rand(t, d // 2) - 0.5) * 2.0
    out, stats = simulate_tile_apply(x, u, v, angles, tile)
    reference = apply_block_givens((x @ u) @ v, angles)
    assert stats["tiles"] == d // tile
    assert stats["pairs_per_tile"] == tile // 2
    assert stats["pairs_total"] == d // 2
    assert torch.allclose(out, reference, atol=1e-5)


def test_tile_simulator_scratch_discipline() -> None:
    """Garbage-filled per-tile scratch must not leak between tiles."""
    torch.manual_seed(9)
    t, d, r, tile = 5, 32, 8, 16
    x = torch.randn(t, d)
    u = torch.randn(d, r)
    v = torch.randn(r, d)
    angles = (torch.rand(t, d // 2) - 0.5) * 2.0
    poison = torch.full((t, tile // 2), 123.456)
    out, _ = simulate_tile_apply(x, u, v, angles, tile, scratch=poison)
    reference = apply_block_givens((x @ u) @ v, angles)
    assert torch.allclose(out, reference, atol=1e-5)


def test_tile_simulator_from_dense_matches() -> None:
    torch.manual_seed(10)
    t, d, tile = 9, 48, 24
    y = torch.randn(t, d)
    angles = (torch.rand(t, d // 2) - 0.5) * 2.0
    out = simulate_tile_apply_from_dense(y, angles, tile)
    reference = apply_block_givens(y, angles)
    assert torch.allclose(out, reference, atol=1e-5)


def test_pair_locality_never_crosses_tiles() -> None:
    """A rotation in one tile must not touch any other tile's columns."""
    torch.manual_seed(11)
    t, d, tile = 3, 32, 16
    y = torch.zeros(t, d)
    y[..., 4] = 1.0  # pair (4,5) lives in tile 0 (cols 0..15)
    angles = torch.zeros(t, d // 2)
    angles[..., 2] = math.pi / 2  # rotate pair (4,5) by 90 degrees
    out = simulate_tile_apply_from_dense(y, angles, tile)
    # pair 2 rotated: (1, 0) in columns (4, 5)
    assert torch.allclose(out[..., 4], torch.full((t,), -0.0, dtype=torch.float32), atol=1e-6)
    assert torch.allclose(out[..., 5], torch.full((t,), 1.0), atol=1e-6)
    # every column outside pair (4,5) is untouched
    mask = torch.ones(d, dtype=torch.bool)
    mask[4] = mask[5] = False
    assert torch.all(out[..., mask] == 0.0)


def test_end_to_end_training_step_reduces_loss() -> None:
    """One gradient step on the head and factors must reduce MSE to a target."""
    torch.manual_seed(12)
    d, r, out_d, hidden = 32, 8, 32, 24
    u0 = torch.randn(d, r) / math.sqrt(d)
    v0 = torch.randn(r, out_d) / math.sqrt(r)
    target_projector = torch.randn(d, out_d) / math.sqrt(d)
    x = torch.randn(64, d)
    target = x @ target_projector

    model = BlockGivensLowRank(u0, v0, hidden, tile=32, amplitude=0.9)
    opt = torch.optim.Adam(model.parameters(), lr=1e-2)
    loss0 = None
    for step in range(60):
        opt.zero_grad()
        loss = torch.nn.functional.mse_loss(model(x), target)
        loss.backward()
        opt.step()
        loss_value = loss.detach()
        if loss0 is None:
            loss0 = float(loss_value)
    assert float(loss_value) < loss0
