"""Prepare explicit router-train / broad-eval splits with overlap removal."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def read_lines(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-source", action="append", required=True)
    parser.add_argument("--heldout-dir", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--train-fraction", type=float, default=1.0)
    parser.add_argument("--max-train-count", type=int, default=0)
    args = parser.parse_args()
    if not (0.0 < args.train_fraction <= 1.0):
        raise SystemExit("--train-fraction must be in (0, 1]")

    train_rows: list[str] = []
    seen: set[str] = set()
    for item in args.train_source:
        for line in read_lines(Path(item)):
            if line in seen:
                continue
            seen.add(line)
            train_rows.append(line)

    heldout_dir = Path(args.heldout_dir)
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    outdir = Path(args.outdir)
    payload = {
        "train_sources": args.train_source,
        "heldout_dir": str(heldout_dir),
        "manifest": args.manifest,
        "unique_train_source_count": len(train_rows),
        "seed": args.seed,
        "train_fraction": args.train_fraction,
        "max_train_count": args.max_train_count,
        "suites": [],
    }
    for suite_index, suite in enumerate(manifest["suites"]):
        name = suite["name"]
        eval_source = heldout_dir / suite["texts"]
        eval_rows = read_lines(eval_source)
        eval_set = set(eval_rows)
        train_filtered = [line for line in train_rows if line not in eval_set]
        overlap_removed = len(train_rows) - len(train_filtered)
        candidate_count = len(train_filtered)
        if args.train_fraction < 1.0 or args.max_train_count > 0:
            rng = random.Random(args.seed + 1000003 * suite_index)
            shuffled = list(train_filtered)
            rng.shuffle(shuffled)
            fraction_count = max(1, int(round(candidate_count * args.train_fraction)))
            if args.max_train_count > 0:
                fraction_count = min(fraction_count, args.max_train_count)
            train_filtered = shuffled[:fraction_count]
        suite_dir = outdir / name
        train_path = suite_dir / "router_train.txt"
        eval_path = suite_dir / "router_eval.txt"
        write_lines(train_path, train_filtered)
        write_lines(eval_path, eval_rows)
        if set(train_filtered) & eval_set:
            raise SystemExit(f"failed to remove train/eval overlap for {name}")
        payload["suites"].append(
            {
                "name": name,
                "train_texts": str(train_path),
                "eval_texts": str(eval_path),
                "source_eval_texts": str(eval_source),
                "train_count": len(train_filtered),
                "candidate_train_count": candidate_count,
                "eval_count": len(eval_rows),
                "overlap_removed": overlap_removed,
            }
        )
    (outdir / "manifest.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2), flush=True)


if __name__ == "__main__":
    main()
