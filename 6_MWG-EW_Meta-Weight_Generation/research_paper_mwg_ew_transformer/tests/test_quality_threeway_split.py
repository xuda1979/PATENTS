from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from audit_quality_threeway_split import audit
from create_quality_threeway_split import create


def _write_source(tmp_path: Path, name: str, rows: list[str]) -> Path:
    path = tmp_path / f"{name}.txt"
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


def _alpha(index: int) -> str:
    return chr(ord("a") + index // 26) + chr(ord("a") + index % 26)


def test_threeway_split_deduplicates_and_freezes_hashes(tmp_path: Path) -> None:
    suites = []
    suite_topics = ["astronomy", "chemistry", "linguistics"]
    for suite_index, topic in enumerate(suite_topics):
        rows = [
            f"The {topic} record {_alpha(row_index)} asks for an explanation of {_alpha(row_index + 7)} in detail."
            for row_index in range(40)
        ]
        if suite_index == 1:
            rows.append("Template 123 asks for a deterministic result with seed 7.")
        if suite_index == 2:
            rows.append("Template 456 asks for a deterministic result with seed 9.")
        source = _write_source(tmp_path, f"suite_{suite_index}", rows)
        suites.append({"name": f"suite_{suite_index}", "texts": source.name})
    manifest = tmp_path / "source_manifest.json"
    manifest.write_text(json.dumps({"suites": suites}), encoding="utf-8")
    out_dir = tmp_path / "quality"
    args = argparse.Namespace(
        source_manifest=str(manifest),
        out_dir=str(out_dir),
        seed=20260823,
        train_fraction=0.5,
        dev_fraction=0.25,
        near_duplicate_threshold=0.82,
        ngram_width=4,
    )

    payload = create(args)

    assert payload["deduplication"]["records_removed"] >= 1
    audited = audit(out_dir / "manifest.json")
    assert audited["ready"] is True
    assert all(row["near_duplicate_pairs"] == 0 for row in audited["cross_split"].values())


def test_audit_detects_post_freeze_mutation(tmp_path: Path) -> None:
    suites = []
    suite_topics = ["geometry", "ecology", "musicology"]
    for suite_index, topic in enumerate(suite_topics):
        source = _write_source(
            tmp_path,
            f"suite_{suite_index}",
            [
                f"A long independent {topic} sample named {_alpha(row_index)} discusses {_alpha(row_index + 11)} carefully."
                for row_index in range(60)
            ],
        )
        suites.append({"name": f"suite_{suite_index}", "texts": source.name})
    manifest = tmp_path / "source_manifest.json"
    manifest.write_text(json.dumps({"suites": suites}), encoding="utf-8")
    out_dir = tmp_path / "quality"
    create(
        argparse.Namespace(
            source_manifest=str(manifest),
            out_dir=str(out_dir),
            seed=19,
            train_fraction=0.5,
            dev_fraction=0.25,
            near_duplicate_threshold=0.99,
            ngram_width=4,
        )
    )
    train_path = out_dir / "train.txt"
    train_path.write_text(train_path.read_text(encoding="utf-8") + "mutated row\n", encoding="utf-8")

    payload = audit(out_dir / "manifest.json")

    assert payload["ready"] is False
    assert any("hash mismatch" in item for item in payload["failures"])
