"""Prepare new, named test-only corpora for the final quality evaluation.

The selected rows are never used for fitting, calibration, early stopping, or
router threshold selection.  Dataset repository revisions and rendered-file
hashes are recorded so the test set can be reproduced and frozen before any
new model run starts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    repo_id: str
    config: str | None
    split: str
    render: Callable[[dict[str, Any]], str]
    fields: tuple[str, ...]


def normalize(text: str) -> str:
    return " ".join(str(text).split())


def render_lambada(row: dict[str, Any]) -> str:
    return normalize(row["text"])


def render_boolq(row: dict[str, Any]) -> str:
    return normalize(f"Passage: {row['passage']} Question: {row['question']}")


def render_arc(row: dict[str, Any]) -> str:
    choices = row.get("choices") or {}
    labels = choices.get("label") or []
    texts = choices.get("text") or []
    rendered = " ".join(f"{label}. {text}" for label, text in zip(labels, texts))
    return normalize(f"Question: {row['question']} Choices: {rendered}")


SPECS = (
    DatasetSpec(
        name="lambada_openai_test",
        repo_id="EleutherAI/lambada_openai",
        config=None,
        split="test",
        render=render_lambada,
        fields=("text",),
    ),
    DatasetSpec(
        name="boolq_validation",
        repo_id="google/boolq",
        config=None,
        split="validation",
        render=render_boolq,
        fields=("passage", "question"),
    ),
    DatasetSpec(
        name="arc_challenge_test",
        repo_id="allenai/ai2_arc",
        config="ARC-Challenge",
        split="test",
        render=render_arc,
        fields=("question", "choices"),
    ),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_unique(rows: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for row in rows:
        key = row.casefold()
        if not row or key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def select_rows(rows: list[str], count: int, seed: int, namespace: str) -> list[str]:
    rows = stable_unique(rows)
    ordered = sorted(
        rows,
        key=lambda text: hashlib.sha256(f"{seed}\0{namespace}\0{text}".encode("utf-8")).hexdigest(),
    )
    if len(ordered) < count:
        raise SystemExit(f"{namespace} has only {len(ordered)} unique rendered rows; requested {count}")
    return ordered[:count]


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    try:
        from datasets import load_dataset
        from huggingface_hub import HfApi
    except ImportError as exc:
        raise SystemExit("datasets and huggingface_hub are required") from exc

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    api = HfApi()
    suites: list[dict[str, Any]] = []

    for spec in SPECS:
        resolved_revision = api.dataset_info(spec.repo_id, revision=args.revision).sha
        dataset = load_dataset(
            spec.repo_id,
            spec.config,
            split=spec.split,
            revision=resolved_revision,
            cache_dir=args.cache_dir,
        )
        rendered = [spec.render(row) for row in dataset]
        selected = select_rows(rendered, args.rows_per_suite, args.seed, spec.name)
        output = out_dir / f"{spec.name}.txt"
        output.write_text("\n".join(selected) + "\n", encoding="utf-8")
        suites.append(
            {
                "name": spec.name,
                "dataset": spec.repo_id,
                "config": spec.config,
                "split": spec.split,
                "resolved_revision": resolved_revision,
                "dataset_fingerprint": getattr(dataset, "_fingerprint", None),
                "rendered_fields": list(spec.fields),
                "selection": "SHA-256 ordering over seed, suite name, and rendered text",
                "selected_rows": len(selected),
                "texts": str(output),
                "sha256": sha256_file(output),
            }
        )

    payload = {
        "schema_version": 1,
        "purpose": "frozen test-only quality evaluation corpus",
        "seed": args.seed,
        "rows_per_suite": args.rows_per_suite,
        "datasets_library": __import__("datasets").__version__,
        "suites": suites,
        "test_policy": (
            "Do not use these rows for fitting, SVD selection, controller training, router training, "
            "threshold calibration, hyperparameter selection, or early stopping. Evaluate once after "
            "the final method and policy are frozen."
        ),
    }
    manifest = out_dir / "manifest.json"
    manifest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="data/quality_frozen_test_sources")
    parser.add_argument("--cache-dir", default=".cache/huggingface_quality_test")
    parser.add_argument("--revision", default="main")
    parser.add_argument("--rows-per-suite", type=int, default=256)
    parser.add_argument("--seed", type=int, default=20260823)
    return parser.parse_args()


def main() -> None:
    payload = prepare(parse_args())
    summary = {
        "manifest": str(Path("data/quality_frozen_test_sources/manifest.json")),
        "suites": [
            {
                "name": suite["name"],
                "dataset": suite["dataset"],
                "split": suite["split"],
                "resolved_revision": suite["resolved_revision"],
                "selected_rows": suite["selected_rows"],
                "sha256": suite["sha256"],
            }
            for suite in payload["suites"]
        ],
    }
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
