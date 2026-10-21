"""Audit a frozen quality split for hashes, diversity, and leakage."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from create_quality_threeway_split import char_ngrams, jaccard, mask_volatile, normalize_text, sha256_file


def read_rows(path: Path) -> list[str]:
    return [normalize_text(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def cross_near_duplicates(
    left: list[str], right: list[str], threshold: float, ngram_width: int
) -> list[tuple[float, int, int]]:
    left_grams = [char_ngrams(mask_volatile(row), ngram_width) for row in left]
    right_grams = [char_ngrams(mask_volatile(row), ngram_width) for row in right]
    hits: list[tuple[float, int, int]] = []
    for left_index, left_set in enumerate(left_grams):
        for right_index, right_set in enumerate(right_grams):
            larger = max(len(left_set), len(right_set))
            if larger and min(len(left_set), len(right_set)) / larger < threshold:
                continue
            score = jaccard(left_set, right_set)
            if score >= threshold:
                hits.append((score, left_index, right_index))
    return sorted(hits, reverse=True)


def audit(manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    threshold = float(manifest["deduplication"]["near_duplicate_threshold"])
    ngram_width = int(manifest["deduplication"]["ngram_width"])
    rows: dict[str, list[str]] = {}
    split_metrics: dict[str, Any] = {}
    failures: list[str] = []

    for split in ("train", "dev", "test"):
        spec = manifest["outputs"][split]
        path = Path(spec["path"])
        if not path.is_absolute():
            candidate = manifest_path.parent / path
            path = candidate if candidate.exists() else path
        if not path.is_file():
            failures.append(f"missing output: {path}")
            rows[split] = []
            continue
        split_rows = read_rows(path)
        rows[split] = split_rows
        actual_hash = sha256_file(path)
        if actual_hash != spec["sha256"]:
            failures.append(f"hash mismatch for {split}: {path}")
        if len(split_rows) != int(spec["rows"]):
            failures.append(f"row-count mismatch for {split}: expected {spec['rows']} got {len(split_rows)}")
        masked = [mask_volatile(row) for row in split_rows]
        compression = len(set(masked)) / len(masked) if masked else 0.0
        split_metrics[split] = {
            "path": str(path),
            "rows": len(split_rows),
            "unique_rows": len(set(row.casefold() for row in split_rows)),
            "distinct_templates": len(set(masked)),
            "template_compression_ratio": compression,
            "sha256": actual_hash,
        }
        if compression < 0.5:
            failures.append(f"template compression below 0.5 for {split}: {compression:.4f}")

    pair_metrics: dict[str, Any] = {}
    for left, right in (("train", "dev"), ("train", "test"), ("dev", "test")):
        exact = set(row.casefold() for row in rows[left]) & set(row.casefold() for row in rows[right])
        near = cross_near_duplicates(rows[left], rows[right], threshold, ngram_width)
        key = f"{left}_vs_{right}"
        pair_metrics[key] = {
            "exact_overlap": len(exact),
            "near_duplicate_pairs": len(near),
            "max_near_duplicate_score": near[0][0] if near else None,
        }
        if exact:
            failures.append(f"exact overlap in {key}: {len(exact)}")
        if near:
            failures.append(f"near-duplicate overlap in {key}: {len(near)}")

    return {
        "schema_version": 1,
        "manifest": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "threshold": threshold,
        "ngram_width": ngram_width,
        "splits": split_metrics,
        "cross_split": pair_metrics,
        "failures": failures,
        "ready": not failures,
        "claim_boundary": (
            "split integrity and diversity gate only; this audit does not establish model quality"
        ),
    }


def write_markdown(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Frozen Quality Split Audit",
        "",
        f"Ready: `{str(payload['ready']).lower()}`",
        f"Near-duplicate threshold: `{payload['threshold']}` (character `{payload['ngram_width']}`-grams)",
        "",
        "| Split | Rows | Unique | Distinct templates | Compression | SHA-256 |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for name, row in payload["splits"].items():
        lines.append(
            f"| {name} | {row['rows']} | {row['unique_rows']} | {row['distinct_templates']} | "
            f"{row['template_compression_ratio']:.4f} | `{row['sha256']}` |"
        )
    lines.extend(
        [
            "",
            "| Pair | Exact overlap | Near-duplicate pairs | Maximum score |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for name, row in payload["cross_split"].items():
        maximum = "--" if row["max_near_duplicate_score"] is None else f"{row['max_near_duplicate_score']:.4f}"
        lines.append(f"| {name} | {row['exact_overlap']} | {row['near_duplicate_pairs']} | {maximum} |")
    lines.extend(["", "## Claim boundary", "", payload["claim_boundary"], ""])
    if payload["failures"]:
        lines.extend(["## Failures", ""] + [f"- {item}" for item in payload["failures"]] + [""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="data/quality/manifest.json")
    parser.add_argument("--out-json", default="results/quality_split_audit_20260823.json")
    parser.add_argument("--out-md", default="results/quality_split_audit_20260823.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = audit(Path(args.manifest))
    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_markdown(payload, Path(args.out_md))
    print(json.dumps(payload, indent=2, ensure_ascii=False), flush=True)
    raise SystemExit(0 if payload["ready"] else 1)


if __name__ == "__main__":
    main()
