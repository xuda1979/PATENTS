"""Prepare explicit router cross-validation text splits.

The output files are ordinary newline-delimited text corpora. They are intended
for launcher paths that require explicit ``--train-texts`` and ``--eval-texts``
arguments, so no run needs to fall back to DEFAULT_TEXTS.
"""

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
    parser.add_argument("--source", action="append", required=True, help="source text file; can be repeated")
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--seeds", default="0,1,2")
    parser.add_argument("--eval-count", type=int, default=256)
    args = parser.parse_args()

    sources = [Path(item) for item in args.source]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for source in sources:
        for line in read_lines(source):
            if line in seen:
                continue
            seen.add(line)
            rows.append({"text": line, "source": str(source)})

    if len(rows) <= args.eval_count:
        raise SystemExit(f"need more than eval-count={args.eval_count} unique rows; got {len(rows)}")

    outdir = Path(args.outdir)
    manifest = {
        "sources": [str(path) for path in sources],
        "unique_rows": len(rows),
        "eval_count": args.eval_count,
        "splits": [],
    }
    for seed in [int(item.strip()) for item in args.seeds.split(",") if item.strip()]:
        shuffled = list(rows)
        random.Random(seed).shuffle(shuffled)
        eval_rows = shuffled[: args.eval_count]
        train_rows = shuffled[args.eval_count :]
        split_dir = outdir / f"seed{seed}"
        train_path = split_dir / "router_train.txt"
        eval_path = split_dir / "router_eval.txt"
        write_lines(train_path, [row["text"] for row in train_rows])
        write_lines(eval_path, [row["text"] for row in eval_rows])
        overlap = set(row["text"] for row in train_rows) & set(row["text"] for row in eval_rows)
        if overlap:
            raise SystemExit(f"split seed {seed} has train/eval overlap")
        manifest["splits"].append(
            {
                "seed": seed,
                "train_texts": str(train_path),
                "eval_texts": str(eval_path),
                "train_count": len(train_rows),
                "eval_count": len(eval_rows),
            }
        )
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
