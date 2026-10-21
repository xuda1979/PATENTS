"""Create a frozen, near-duplicate-clean train/dev/test text split.

The splitter operates on the named corpus files in a held-out manifest.  It
normalizes Unicode and whitespace, groups exact and near-duplicate records,
keeps one deterministic representative per group, and assigns each surviving
record to exactly one split.  The test split is intended to be frozen before
training and used once for the final paper evaluation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class Record:
    suite: str
    source: str
    source_index: int
    text: str
    normalized: str
    masked: str


class DisjointSet:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if self.rank[left_root] < self.rank[right_root]:
            left_root, right_root = right_root, left_root
        self.parent[right_root] = left_root
        if self.rank[left_root] == self.rank[right_root]:
            self.rank[left_root] += 1


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return SPACE_RE.sub(" ", text).strip()


def mask_volatile(text: str) -> str:
    return NUMBER_RE.sub("#", text.casefold())


def char_ngrams(text: str, width: int) -> frozenset[str]:
    compact = SPACE_RE.sub("", text)
    if len(compact) < width:
        return frozenset({compact}) if compact else frozenset()
    return frozenset(compact[index : index + width] for index in range(len(compact) - width + 1))


def jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def read_records(manifest_path: Path) -> tuple[list[Record], list[dict[str, Any]]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = manifest_path.parent
    records: list[Record] = []
    sources: list[dict[str, Any]] = []
    for suite in manifest.get("suites", []):
        name = str(suite["name"])
        source = Path(str(suite["texts"]))
        if not source.is_absolute() and not source.is_file():
            source = root / source
        if not source.is_file():
            raise SystemExit(f"missing source for suite {name!r}: {source}")
        rows = [line for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not rows:
            raise SystemExit(f"empty source for suite {name!r}: {source}")
        sources.append(
            {
                "suite": name,
                "path": str(source),
                "rows": len(rows),
                "sha256": sha256_file(source),
            }
        )
        for index, raw in enumerate(rows):
            normalized = normalize_text(raw)
            if not normalized:
                continue
            records.append(
                Record(
                    suite=name,
                    source=str(source),
                    source_index=index,
                    text=normalized,
                    normalized=normalized.casefold(),
                    masked=mask_volatile(normalized),
                )
            )
    if not records:
        raise SystemExit("no non-empty records found")
    return records, sources


def duplicate_components(
    records: list[Record], *, threshold: float, ngram_width: int
) -> tuple[list[list[int]], int, int]:
    dsu = DisjointSet(len(records))
    exact: dict[str, int] = {}
    exact_pairs = 0
    for index, record in enumerate(records):
        prior = exact.get(record.normalized)
        if prior is None:
            exact[record.normalized] = index
        else:
            dsu.union(prior, index)
            exact_pairs += 1

    grams = [char_ngrams(record.masked, ngram_width) for record in records]
    near_pairs = 0
    for left in range(len(records)):
        left_size = len(grams[left])
        for right in range(left + 1, len(records)):
            if records[left].normalized == records[right].normalized:
                continue
            right_size = len(grams[right])
            larger = max(left_size, right_size)
            if larger and min(left_size, right_size) / larger < threshold:
                continue
            if jaccard(grams[left], grams[right]) >= threshold:
                dsu.union(left, right)
                near_pairs += 1

    grouped: dict[int, list[int]] = {}
    for index in range(len(records)):
        grouped.setdefault(dsu.find(index), []).append(index)
    components = sorted(grouped.values(), key=lambda group: min(group))
    return components, exact_pairs, near_pairs


def representative(records: list[Record], component: Iterable[int], seed: int) -> int:
    def key(index: int) -> tuple[int, str]:
        record = records[index]
        tie = hashlib.sha256(f"{seed}\0{record.suite}\0{record.text}".encode("utf-8")).hexdigest()
        return (len(record.text), tie)

    return max(component, key=key)


def split_for(record: Record, seed: int, train_fraction: float, dev_fraction: float) -> str:
    value = int(hashlib.sha256(f"{seed}\0{record.suite}\0{record.text}".encode("utf-8")).hexdigest(), 16)
    unit = value / float(1 << 256)
    if unit < train_fraction:
        return "train"
    if unit < train_fraction + dev_fraction:
        return "dev"
    return "test"


def write_rows(path: Path, rows: list[Record]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(record.text for record in rows) + ("\n" if rows else ""), encoding="utf-8")


def create(args: argparse.Namespace) -> dict[str, Any]:
    if not 0.0 < args.train_fraction < 1.0:
        raise SystemExit("--train-fraction must be in (0,1)")
    if not 0.0 < args.dev_fraction < 1.0:
        raise SystemExit("--dev-fraction must be in (0,1)")
    if args.train_fraction + args.dev_fraction >= 1.0:
        raise SystemExit("train and dev fractions must leave a non-empty test fraction")
    if not 0.0 < args.near_duplicate_threshold <= 1.0:
        raise SystemExit("--near-duplicate-threshold must be in (0,1]")

    manifest_path = Path(args.source_manifest)
    records, sources = read_records(manifest_path)
    components, exact_pairs, near_pairs = duplicate_components(
        records,
        threshold=args.near_duplicate_threshold,
        ngram_width=args.ngram_width,
    )
    kept_indices = [representative(records, group, args.seed) for group in components]
    kept_records = [records[index] for index in kept_indices]

    splits: dict[str, list[Record]] = {"train": [], "dev": [], "test": []}
    for record in kept_records:
        splits[split_for(record, args.seed, args.train_fraction, args.dev_fraction)].append(record)
    for rows in splits.values():
        rows.sort(key=lambda record: (record.suite, record.source_index, record.text))

    suites = sorted({record.suite for record in kept_records})
    for name, rows in splits.items():
        if not rows:
            raise SystemExit(f"deterministic split {name!r} is empty")
        missing_suites = [suite for suite in suites if not any(record.suite == suite for record in rows)]
        if missing_suites:
            raise SystemExit(f"split {name!r} lacks suites: {missing_suites}; choose another seed")

    out_dir = Path(args.out_dir)
    outputs: dict[str, dict[str, Any]] = {}
    for name, rows in splits.items():
        path = out_dir / f"{name}.txt"
        write_rows(path, rows)
        outputs[name] = {
            "path": str(path),
            "rows": len(rows),
            "characters": sum(len(record.text) for record in rows),
            "sha256": sha256_file(path),
            "suite_counts": {suite: sum(record.suite == suite for record in rows) for suite in suites},
        }

    test_fraction = 1.0 - args.train_fraction - args.dev_fraction
    payload: dict[str, Any] = {
        "schema_version": 1,
        "source_manifest": str(manifest_path),
        "source_manifest_sha256": sha256_file(manifest_path),
        "sources": sources,
        "seed": args.seed,
        "fractions": {
            "train": args.train_fraction,
            "dev": args.dev_fraction,
            "test": test_fraction,
        },
        "deduplication": {
            "normalization": "Unicode NFKC, whitespace collapse, case-fold for comparison",
            "volatile_mask": "decimal and integer substrings replaced by #",
            "ngram_width": args.ngram_width,
            "near_duplicate_threshold": args.near_duplicate_threshold,
            "input_records": len(records),
            "duplicate_components": len(components),
            "records_removed": len(records) - len(kept_records),
            "exact_duplicate_links": exact_pairs,
            "near_duplicate_links": near_pairs,
        },
        "outputs": outputs,
        "test_policy": (
            "Frozen before model fitting. Test rows and labels must not be used for training, "
            "hyperparameter selection, threshold calibration, or early stopping. Evaluate once "
            "after the method and routing policy are fixed."
        ),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_out = out_dir / "manifest.json"
    manifest_out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", default="data/heldout/manifest_with_extra.json")
    parser.add_argument("--out-dir", default="data/quality")
    parser.add_argument("--seed", type=int, default=20260823)
    parser.add_argument("--train-fraction", type=float, default=0.5)
    parser.add_argument("--dev-fraction", type=float, default=0.25)
    parser.add_argument("--near-duplicate-threshold", type=float, default=0.82)
    parser.add_argument("--ngram-width", type=int, default=4)
    return parser.parse_args()


def main() -> None:
    payload = create(parse_args())
    print(json.dumps(payload, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
