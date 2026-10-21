from __future__ import annotations

import sys
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from mwg_ppl_patch_eval import load_student  # noqa: E402
from mwg_quality_distillation import LowRankFFN  # noqa: E402


def make_factors(d: int = 8, m: int = 12, rank: int = 4) -> dict[str, tuple[torch.Tensor, torch.Tensor]]:
    generator = torch.Generator(device="cpu").manual_seed(41)

    def matrix(*shape: int) -> torch.Tensor:
        return 0.1 * torch.randn(*shape, generator=generator)

    return {
        "up": (matrix(d, rank), matrix(rank, m)),
        "gate": (matrix(d, rank), matrix(rank, m)),
        "down": (matrix(m, rank), matrix(rank, d)),
    }


def make_model() -> LowRankFFN:
    torch.manual_seed(43)
    return LowRankFFN(
        make_factors(),
        dtype=torch.float32,
        generator="token_diag_core",
        generator_hidden=10,
        scale_amplitude=0.2,
    ).eval()


@torch.no_grad()
def test_token_diag_core_is_prefix_invariant() -> None:
    model = make_model()
    x = torch.randn(2, 7, model.d)
    prefix = 4

    torch.testing.assert_close(model(x)[:, :prefix], model(x[:, :prefix]), rtol=1e-5, atol=1e-6)


@torch.no_grad()
def test_token_diag_core_is_batch_invariant() -> None:
    model = make_model()
    target = torch.randn(1, 6, model.d)
    unrelated = 20.0 * torch.randn(1, 6, model.d)

    torch.testing.assert_close(
        model(torch.cat([target, unrelated], dim=0))[:1],
        model(target),
        rtol=1e-5,
        atol=1e-6,
    )


def test_token_diag_projection_matches_explicit_diagonal_core() -> None:
    generator = torch.Generator(device="cpu").manual_seed(47)
    x = torch.randn(2, 5, 8, generator=generator)
    u = torch.randn(8, 4, generator=generator)
    v = torch.randn(4, 12, generator=generator)
    core = torch.randn(2, 5, 4, generator=generator)

    expected = torch.matmul(
        torch.matmul(x.unsqueeze(-2), u).squeeze(-2) * core,
        v,
    )
    actual = LowRankFFN._token_diag_project(x, u, v, core)

    torch.testing.assert_close(actual, expected, rtol=1e-5, atol=1e-6)


def test_token_diag_core_emits_three_rank_vectors() -> None:
    model = make_model()

    assert model.generator is not None
    assert isinstance(model.generator[-1], torch.nn.Linear)
    assert model.generator[-1].out_features == 3 * model.rank


def test_legacy_paired_scales_collapse_to_one_core() -> None:
    generator = torch.Generator(device="cpu").manual_seed(53)
    x = torch.randn(2, 5, 8, generator=generator)
    u = torch.randn(8, 4, generator=generator)
    v = torch.randn(4, 12, generator=generator)
    left = torch.randn(2, 5, 4, generator=generator)
    right = torch.randn(2, 5, 4, generator=generator)

    paired = LowRankFFN._token_scaled_project(x, u, v, left, right)
    canonical = LowRankFFN._token_diag_project(x, u, v, left * right)

    torch.testing.assert_close(paired, canonical, rtol=1e-5, atol=1e-6)


@torch.no_grad()
def test_token_diag_core_checkpoint_round_trip(tmp_path: Path) -> None:
    model = make_model()
    checkpoint = tmp_path / "token_diag_core.pt"
    torch.save(
        {
            "init": {
                "d": model.d,
                "m": model.m,
                "rank": model.rank,
                "generator_mode": model.generator_mode,
                "generator_hidden": model.generator_hidden,
                "residual_rank": model.residual_rank,
                "scale_amplitude": model.scale_amplitude,
                "basis_count": model.basis_count,
            },
            "state_dict": model.state_dict(),
        },
        checkpoint,
    )

    loaded, _payload = load_student(checkpoint, torch.device("cpu"), torch.float32)
    x = torch.randn(2, 5, model.d)

    assert loaded.generator_mode == "token_diag_core"
    torch.testing.assert_close(loaded(x), model(x), rtol=1e-5, atol=1e-6)
