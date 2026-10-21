from __future__ import annotations

import sys
from pathlib import Path

import pytest
import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from mwg_ppl_patch_eval import load_student  # noqa: E402
from mwg_quality_distillation import LowRankFFN  # noqa: E402


def make_factors(d: int = 8, m: int = 12, rank: int = 4) -> dict[str, tuple[torch.Tensor, torch.Tensor]]:
    generator = torch.Generator(device="cpu").manual_seed(7)

    def matrix(*shape: int) -> torch.Tensor:
        return 0.1 * torch.randn(*shape, generator=generator)

    return {
        "up": (matrix(d, rank), matrix(rank, m)),
        "gate": (matrix(d, rank), matrix(rank, m)),
        "down": (matrix(m, rank), matrix(rank, d)),
    }


def make_model(generator_hidden: int | None = 10) -> LowRankFFN:
    torch.manual_seed(11)
    return LowRankFFN(
        make_factors(),
        dtype=torch.float32,
        generator="token_expert_residual",
        generator_hidden=generator_hidden,
        residual_rank=3,
        scale_amplitude=0.2,
        basis_count=3,
    ).eval()


@torch.no_grad()
def test_token_expert_residual_is_prefix_invariant() -> None:
    model = make_model()
    x = torch.randn(2, 7, model.d)
    prefix = 4

    full_prefix = model(x)[:, :prefix]
    prefix_only = model(x[:, :prefix])

    torch.testing.assert_close(full_prefix, prefix_only, rtol=1e-5, atol=1e-6)


@torch.no_grad()
def test_token_expert_residual_is_batch_invariant() -> None:
    model = make_model()
    target = torch.randn(1, 6, model.d)
    unrelated = 20.0 * torch.randn(1, 6, model.d)

    alone = model(target)
    in_batch = model(torch.cat([target, unrelated], dim=0))[:1]

    torch.testing.assert_close(alone, in_batch, rtol=1e-5, atol=1e-6)


def test_token_scaled_projection_matches_expanded_factor_formula() -> None:
    generator = torch.Generator(device="cpu").manual_seed(23)
    x = torch.randn(2, 5, 8, generator=generator)
    u = torch.randn(8, 4, generator=generator)
    v = torch.randn(4, 12, generator=generator)
    left_scale = torch.randn(2, 5, 4, generator=generator)
    right_scale = torch.randn(2, 5, 4, generator=generator)

    expanded_u = u.unsqueeze(0).unsqueeze(0) * left_scale.unsqueeze(-2)
    expanded_v = v.unsqueeze(0).unsqueeze(0) * right_scale.unsqueeze(-1)
    expected = torch.matmul(torch.matmul(x.unsqueeze(-2), expanded_u), expanded_v).squeeze(-2)
    actual = LowRankFFN._token_scaled_project(x, u, v, left_scale, right_scale)

    torch.testing.assert_close(actual, expected, rtol=1e-5, atol=1e-6)


@pytest.mark.parametrize(
    ("mode", "generator_hidden", "save_generator_hidden"),
    [
        ("expert_residual", None, False),
        ("token_expert_residual", 10, True),
    ],
)
@torch.no_grad()
def test_checkpoint_loader_supports_legacy_and_token_modes(
    tmp_path: Path,
    mode: str,
    generator_hidden: int | None,
    save_generator_hidden: bool,
) -> None:
    torch.manual_seed(31)
    model = LowRankFFN(
        make_factors(),
        dtype=torch.float32,
        generator=mode,
        generator_hidden=generator_hidden,
        residual_rank=3,
        scale_amplitude=0.2,
        basis_count=3,
    ).eval()
    init = {
        "d": model.d,
        "m": model.m,
        "rank": model.rank,
        "generator_mode": model.generator_mode,
        "residual_rank": model.residual_rank,
        "scale_amplitude": model.scale_amplitude,
        "basis_count": model.basis_count,
    }
    if save_generator_hidden:
        init["generator_hidden"] = model.generator_hidden
    checkpoint = tmp_path / f"{mode}.pt"
    torch.save({"init": init, "state_dict": model.state_dict()}, checkpoint)

    loaded, _payload = load_student(checkpoint, torch.device("cpu"), torch.float32)
    x = torch.randn(2, 5, model.d)

    assert loaded.generator_mode == mode
    assert loaded.generator_hidden == model.generator_hidden
    torch.testing.assert_close(loaded(x), model(x), rtol=1e-5, atol=1e-6)
