"""Create a global leakage-clean suite-aware router split manifest.

The existing per-suite broad-router splits are useful when each suite is
evaluated separately, but their train files overlap the union of broad eval
rows. This helper creates one combined manifest by partitioning each suite's
own held-out rows into disjoint train/eval files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any


def read_lines(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def stable_unique(rows: list[str]) -> list[str]:
    seen = set()
    unique = []
    for row in rows:
        if row in seen:
            continue
        seen.add(row)
        unique.append(row)
    return unique


def row_key(text: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}\0{text}".encode("utf-8")).hexdigest()


def write_lines(path: Path, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")


def build(args: argparse.Namespace) -> dict[str, Any]:
    source_manifest = Path(args.source_manifest)
    source_root = source_manifest.parent
    out_dir = Path(args.out_dir)
    manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
    rng = random.Random(args.seed)
    suites = []
    global_train = []
    global_eval = []

    for suite in manifest.get("suites", []):
        name = str(suite["name"])
        source = source_root / suite["texts"]
        rows = stable_unique(read_lines(source))
        if len(rows) < args.min_suite_rows:
            raise SystemExit(f"suite {name!r} has only {len(rows)} rows; need at least {args.min_suite_rows}")

        if args.stable_hash_split:
            ordered = sorted(rows, key=lambda text: row_key(text, args.seed))
        else:
            ordered = list(rows)
            rng.shuffle(ordered)

        eval_count = max(args.min_eval_rows, round(len(ordered) * args.eval_fraction))
        eval_count = min(eval_count, len(ordered) - args.min_train_rows)
        if eval_count <= 0:
            raise SystemExit(f"suite {name!r} cannot satisfy train/eval constraints")

        eval_rows = ordered[:eval_count]
        train_rows = ordered[eval_count:]
        if set(train_rows) & set(eval_rows):
            raise SystemExit(f"internal split overlap for suite {name!r}")

        suite_dir = out_dir / name
        train_path = suite_dir / "router_train.txt"
        eval_path = suite_dir / "router_eval.txt"
        write_lines(train_path, train_rows)
        write_lines(eval_path, eval_rows)

        global_train.extend(train_rows)
        global_eval.extend(eval_rows)
        suites.append(
            {
                "name": name,
                "train_texts": str(train_path),
                "eval_texts": str(eval_path),
                "source_texts": str(source),
                "train_count": len(train_rows),
                "eval_count": len(eval_rows),
                "source_unique_count": len(rows),
            }
        )

    overlap = set(global_train) & set(global_eval)
    if overlap:
        raise SystemExit(f"global train/eval overlap: {len(overlap)} unique rows")

    payload = {
        "source_manifest": str(source_manifest),
        "out_dir": str(out_dir),
        "seed": args.seed,
        "eval_fraction": args.eval_fraction,
        "stable_hash_split": args.stable_hash_split,
        "train_total": len(global_train),
        "train_unique_total": len(set(global_train)),
        "eval_total": len(global_eval),
        "eval_unique_total": len(set(global_eval)),
        "train_eval_overlap_unique": 0,
        "suites": suites,
        "claim_boundary": (
            "global leakage-clean suite-aware split for router robustness tests; "
            "not an independent broad-family benchmark expansion"
        ),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", default="data/heldout/manifest.json")
    parser.add_argument("--out-dir", default="data/heldout/router_global_splits")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--eval-fraction", type=float, default=0.5)
    parser.add_argument("--min-suite-rows", type=int, default=4)
    parser.add_argument("--min-train-rows", type=int, default=1)
    parser.add_argument("--min-eval-rows", type=int, default=1)
    parser.add_argument("--stable-hash-split", action="store_true", default=True)
    return parser.parse_args()


def main() -> None:
    payload = build(parse_args())
    print(json.dumps(payload, indent=2), flush=True)


if __name__ == "__main__":
    main()
