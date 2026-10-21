from __future__ import annotations

import sys
from pathlib import Path

import pytest
import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from mwg_quality_distillation import (  # noqa: E402
    build_parser,
    load_fingerprinted_cache,
    prepare_text_splits,
    publish_fingerprinted_cache,
    run,
    sample_batch,
    select_valid_activations,
    svd_factor_sweep,
)


def evidence_args(train: Path, evaluation: Path):
    return build_parser().parse_args(
        [
            "--model-dir",
            str(train.parent / "model"),
            "--activation-source",
            "text",
            "--train-texts-file",
            str(train),
            "--eval-texts-file",
            str(evaluation),
            "--evidence-mode",
            "--save-students",
            "--checkpoint-every",
            "1",
        ]
    )


def test_evidence_splits_are_explicit_hashed_and_disjoint(tmp_path: Path) -> None:
    train = tmp_path / "train.txt"
    evaluation = tmp_path / "eval.txt"
    train.write_text("A compiler schedules matrix tiles.\nA router predicts bounded risk.\n", encoding="utf-8")
    evaluation.write_text("A telescope measures a distant galaxy.\nA baker prepares sourdough.\n", encoding="utf-8")

    splits, metadata = prepare_text_splits(evidence_args(train, evaluation))

    assert set(splits) == {"train", "eval"}
    assert set(splits["train"]).isdisjoint(splits["eval"])
    assert metadata["mode"] == "explicit_disjoint"
    assert len(metadata["train"]["sha256"]) == 64
    assert len(metadata["eval"]["sha256"]) == 64


def test_evidence_split_rejects_exact_and_near_duplicates(tmp_path: Path) -> None:
    train = tmp_path / "train.txt"
    evaluation = tmp_path / "eval.txt"
    body = "return ''.join(x.capitalize() or '_' for x in word.split('_'))"
    train.write_text(f"import re def snake_to_camel(word): {body}\n", encoding="utf-8")
    evaluation.write_text(f"import re def snake_to_camel(word): {body}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="exact overlap"):
        prepare_text_splits(evidence_args(train, evaluation))

    evaluation.write_text(f"def snake_to_camel(word): import re {body}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="near-duplicate"):
        prepare_text_splits(evidence_args(train, evaluation))


def test_attention_mask_filters_padding_activations() -> None:
    activations = torch.arange(2 * 4 * 3, dtype=torch.float32).view(2, 4, 3)
    mask = torch.tensor([[1, 1, 0, 0], [1, 0, 1, 0]])

    selected = select_valid_activations(activations, mask)

    expected = torch.stack([activations[0, 0], activations[0, 1], activations[1, 0], activations[1, 2]])
    torch.testing.assert_close(selected, expected)


def test_split_specific_token_pools_do_not_cross(tmp_path: Path) -> None:
    args = build_parser().parse_args(["--d", "3", "--batch", "2", "--seq", "4"])
    args._train_activation_cache = torch.zeros(7, 3)
    args._eval_activation_cache = torch.ones(5, 3)

    train = sample_batch(args, torch.device("cpu"), torch.float32, 7, split="train")
    evaluation = sample_batch(args, torch.device("cpu"), torch.float32, 7, split="eval")

    assert train.shape == evaluation.shape == (2, 4, 3)
    assert torch.count_nonzero(train) == 0
    assert torch.count_nonzero(evaluation - 1) == 0


def test_fingerprinted_cache_rejects_stale_marker(tmp_path: Path) -> None:
    path = tmp_path / "cache.pt"
    publish_fingerprinted_cache({"value": torch.tensor([3.0])}, path, "fresh")

    assert load_fingerprinted_cache(path, "fresh") is not None
    assert load_fingerprinted_cache(path, "stale") is None


def test_svd_sweep_reuses_one_decomposition_for_nested_ranks() -> None:
    matrix = torch.randn(7, 5, generator=torch.Generator().manual_seed(19))

    sweep = svd_factor_sweep(matrix, [2, 4])

    torch.testing.assert_close(sweep[2][0], sweep[4][0][:, :2])
    torch.testing.assert_close(sweep[2][1], sweep[4][1][:2, :])
    assert 0.0 < sweep[2][2] <= sweep[4][2] <= 1.0


def test_student_specs_run_only_requested_mode_rank_pairs(tmp_path: Path) -> None:
    args = build_parser().parse_args(
        [
            "--d",
            "8",
            "--m",
            "12",
            "--student-specs",
            "persistent:2,token_diag_core:2,persistent:3",
            "--batch",
            "1",
            "--seq",
            "3",
            "--steps",
            "0",
            "--eval-batches",
            "1",
            "--dtype",
            "fp32",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--outdir",
            str(tmp_path / "run"),
        ]
    )

    payload = run(args)

    assert payload is not None
    trained = {
        name
        for name in payload["results"]
        if name != "dense_teacher" and not name.startswith("static_svd_")
    }
    assert trained == {
        "persistent_low_rank_r2",
        "mwg_token_diag_core_r2",
        "persistent_low_rank_r3",
    }


def test_atomic_training_checkpoint_resumes_optimizer_rng_and_step(tmp_path: Path) -> None:
    outdir = tmp_path / "run"
    cache_dir = tmp_path / "cache"
    argv = [
        "--d",
        "8",
        "--m",
        "12",
        "--ranks",
        "2",
        "--batch",
        "1",
        "--seq",
        "3",
        "--steps",
        "1",
        "--eval-batches",
        "1",
        "--log-every",
        "1",
        "--students",
        "persistent",
        "--dtype",
        "fp32",
        "--save-students",
        "--checkpoint-every",
        "1",
        "--resume",
        "auto",
        "--cache-dir",
        str(cache_dir),
        "--outdir",
        str(outdir),
    ]

    first = run(build_parser().parse_args(argv))
    checkpoint = outdir / "checkpoints" / "persistent_low_rank_r2.resume.pt"
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    second = run(build_parser().parse_args(argv))

    assert first is not None and second is not None
    assert payload["global_step"] == 1
    assert payload["completed"] is True
    assert "optimizer_state_dict" in payload
    assert "rng_state" in payload
    assert second["results"]["persistent_low_rank_r2"]["resumed"] is True
    assert second["results"]["persistent_low_rank_r2"]["start_step"] == 1
    metrics = second["results"]["persistent_low_rank_r2"]["metrics"]
    assert metrics["token_relative_mse_p50"] <= metrics["token_relative_mse_p90"]
    assert metrics["token_relative_mse_p90"] <= metrics["token_relative_mse_p99"]
    assert metrics["token_relative_mse_p99"] <= metrics["token_relative_mse_max"]
