"""Tests for the block_givens trained-checkpoint path in the four-arm benchmark.

Covers:
  * ``load_trained_master_weights`` on a schema_version 2 block_givens
    checkpoint (angle generator mapped into ``MasterWeights.givens_*``);
  * ``BlockGivensArm`` reproducing the distillation student's
    ``_forward_block_givens`` numerically on the same tensors;
  * rejection guards: non-block_givens checkpoints keep working, and the
    3*rank token_diag_core validation no longer misfires on angle heads.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from mwg_four_arm_lifetime_benchmark import (  # noqa: E402
    BLOCK_GIVENS_ARM,
    BenchmarkConfig,
    BlockGivensArm,
    DenseArm,
    MasterWeights,
    PersistentLowRankArm,
    generate_master_weights,
    load_trained_master_weights,
    parse_arms,
)
from mwg_block_givens import apply_block_givens  # noqa: E402


def tiny_config() -> BenchmarkConfig:
    return BenchmarkConfig(
        d=8,
        m=12,
        rank=4,
        controller_hidden=6,
        batch=2,
        seq=3,
        amplitude=0.2,
        dtype="fp32",
        seed=71,
    )


def make_block_givens_checkpoint(tmp_path: Path) -> Path:
    """Save a schema_version 2 checkpoint mirroring LowRankFFN.state_dict."""
    config = tiny_config()
    master = generate_master_weights(config)
    hidden = 5
    angle_dim = 2 * (config.m // 2) + config.d // 2
    generator = torch.Generator().manual_seed(11)
    # nn.Linear stores weights as [out, in], matching the real checkpoint.
    w1 = torch.randn(hidden, config.d, generator=generator) * 0.1
    b1 = torch.randn(hidden, generator=generator) * 0.01
    w2 = torch.randn(angle_dim, hidden, generator=generator) * 0.1
    b2 = torch.randn(angle_dim, generator=generator) * 0.01
    state = {
        "up_u": master.up_u,
        "up_v": master.up_v,
        "gate_u": master.gate_u,
        "gate_v": master.gate_v,
        "down_u": master.down_u,
        "down_v": master.down_v,
        "generator.0.weight": w1,
        "generator.0.bias": b1,
        "generator.2.weight": w2,
        "generator.2.bias": b2,
    }
    path = tmp_path / "mwg_block_givens_r4.pt"
    torch.save(
        {
            "schema_version": 2,
            "student": "mwg_block_givens_r4",
            "state_dict": state,
        },
        path,
    )
    return path


def distillation_reference_forward(
    x: torch.Tensor, master: MasterWeights, config: BenchmarkConfig
) -> torch.Tensor:
    """Replicates LowRankFFN._forward_block_givens on loaded tensors."""
    state_w1 = master.givens_w1
    angles = (
        torch.nn.functional.silu(x.float() @ state_w1.t() + master.givens_b1)
        @ master.givens_w2.t()
        + master.givens_b2
    )
    half_m = config.m // 2
    half_d = config.d // 2
    angle_up = angles[..., 0:half_m]
    angle_gate = angles[..., half_m : 2 * half_m]
    angle_down = angles[..., 2 * half_m : 2 * half_m + half_d]
    up = apply_block_givens((x @ master.up_u) @ master.up_v, angle_up)
    gate = apply_block_givens((x @ master.gate_u) @ master.gate_v, angle_gate)
    hidden = torch.nn.functional.silu(gate) * up
    return apply_block_givens(
        (hidden @ master.down_u) @ master.down_v, angle_down
    )


def test_block_givens_arm_registered_and_parsed() -> None:
    assert BLOCK_GIVENS_ARM == "block_givens"
    assert "block_givens" in parse_arms("all")
    assert "block_givens" in parse_arms("dense,block_givens")


def test_load_block_givens_checkpoint(tmp_path: Path) -> None:
    config = tiny_config()
    path = make_block_givens_checkpoint(tmp_path)
    master = load_trained_master_weights(path, config)
    assert master.givens_w1 is not None
    assert master.givens_b1 is not None
    assert master.givens_w2 is not None
    assert master.givens_b2 is not None
    assert master.givens_w2.shape[0] == 2 * (config.m // 2) + config.d // 2
    # Factor tensors must round-trip exactly.
    torch.testing.assert_close(master.up_u, generate_master_weights(config).up_u)


def test_block_givens_arm_matches_distillation_forward(
    tmp_path: Path,
) -> None:
    config = tiny_config()
    path = make_block_givens_checkpoint(tmp_path)
    master = load_trained_master_weights(path, config)
    arm = BlockGivensArm(master, torch.float32)
    torch.manual_seed(3)
    x = torch.randn(config.batch, config.seq, config.d)
    out_arm = arm(x)
    out_ref = distillation_reference_forward(x, master, config)
    assert out_arm.shape == x.shape
    torch.testing.assert_close(out_arm, out_ref, rtol=1e-5, atol=1e-6)


def test_block_givens_arm_matches_real_lowrankffn(tmp_path: Path) -> None:
    """End-to-end: save a real LowRankFFN(generator='block_givens') checkpoint
    (schema_version 2, exactly as the Q4 worker saves it), load it through
    the benchmark loader, and require the latency arm to reproduce the
    distillation student's forward bit-comparably in fp32."""
    from mwg_quality_distillation import LowRankFFN

    config = tiny_config()
    master = generate_master_weights(config)
    hidden = 5
    factors = {
        "up": (master.up_u, master.up_v),
        "gate": (master.gate_u, master.gate_v),
        "down": (master.down_u, master.down_v),
    }
    student = LowRankFFN(
        factors, dtype=torch.float32, generator="block_givens",
        generator_hidden=hidden,
    )
    torch.manual_seed(3)
    x = torch.randn(config.batch, config.seq, config.d)
    with torch.no_grad():
        out_student = student(x)
    path = tmp_path / "mwg_block_givens_r4.pt"
    torch.save(
        {
            "schema_version": 2,
            "student": "mwg_block_givens_r4",
            "state_dict": {
                key: value.detach().cpu()
                for key, value in student.state_dict().items()
            },
        },
        path,
    )
    loaded = load_trained_master_weights(path, config)
    arm = BlockGivensArm(loaded, torch.float32)
    with torch.no_grad():
        out_arm = arm(x)
    torch.testing.assert_close(out_arm, out_student, rtol=0.0, atol=0.0)


def test_block_givens_arm_requires_angle_generator() -> None:
    config = tiny_config()
    master = generate_master_weights(config)
    with pytest.raises(ValueError, match="block_givens checkpoint"):
        BlockGivensArm(master, torch.float32)


def test_token_diag_core_checkpoint_still_validates(tmp_path: Path) -> None:
    """A 3*rank generator must keep loading through the controller path."""
    config = tiny_config()
    master = generate_master_weights(config)
    state = {
        "up_u": master.up_u,
        "up_v": master.up_v,
        "gate_u": master.gate_u,
        "gate_v": master.gate_v,
        "down_u": master.down_u,
        "down_v": master.down_v,
        "generator.0.weight": torch.randn(config.controller_hidden, config.d) * 0.1,
        "generator.0.bias": torch.randn(config.controller_hidden) * 0.01,
        "generator.2.weight": torch.randn(3 * config.rank, config.controller_hidden) * 0.1,
        "generator.2.bias": torch.randn(3 * config.rank) * 0.01,
    }
    path = tmp_path / "mwg_token_diag_core_r4.pt"
    torch.save(
        {
            "schema_version": 2,
            "student": "mwg_token_diag_core_r4",
            "state_dict": state,
        },
        path,
    )
    loaded = load_trained_master_weights(path, config)
    assert loaded.givens_w1 is None
    assert loaded.controller_w2_up.shape == (config.controller_hidden, config.rank)
    with pytest.raises(ValueError, match="3 \\* rank"):
        # Corrupt the head width and confirm the token_diag_core guard fires.
        state["generator.2.weight"] = torch.randn(
            2 * (config.m // 2) + config.d // 2, config.controller_hidden
        )
        torch.save(
            {"schema_version": 2, "student": "mwg_token_diag_core_r4", "state_dict": state},
            path,
        )
        load_trained_master_weights(path, config)


def test_dense_and_persistent_arms_unchanged_by_givens_fields() -> None:
    config = tiny_config()
    master = generate_master_weights(config)
    x = torch.randn(config.batch, config.seq, config.d)
    dense = DenseArm(master, torch.float32)
    persistent = PersistentLowRankArm(master, torch.float32)
    torch.testing.assert_close(dense(x), persistent(x), rtol=2e-5, atol=2e-6)
