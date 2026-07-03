"""Create deterministic train/eval suite splits from held-out manifests.

The router experiment needs explicit train/eval files per suite so that the
learned fallback policy is not tuned on the same examples it reports. This
helper accepts one or more simple manifest files of the form used by
``mwg_broad_eval_manifest.py`` and writes a combined suite-split manifest.
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path
from typing import Any


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("._") or "suite"


def parse_texts(value: str) -> list[str]:
    path = Path(value)
    if path.exists():
        text = path.read_text(encoding="utf-8", errors="ignore")
    else:
        text = value
    if "||" in text:
        rows = text.split("||")
    else:
        rows = text.splitlines()
    return [row.strip() for row in rows if row.strip()]


def load_manifest_suites(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    suites = payload.get("suites")
    if not isinstance(suites, list) or not suites:
        raise SystemExit(f"manifest {path} must contain a non-empty suites list")
    rows = []
    for item in suites:
        if not isinstance(item, dict):
            raise SystemExit(f"invalid suite item in {path}: {item!r}")
        name = item.get("name")
        text_spec = item.get("texts")
        if not isinstance(name, str) or not name.strip():
            raise SystemExit(f"suite without valid name in {path}: {item!r}")
        if not isinstance(text_spec, str) or not text_spec.strip():
            raise SystemExit(f"suite {name!r} in {path} has no texts field")
        text_path = Path(text_spec)
        if not text_path.is_absolute():
            text_path = path.parent / text_path
        rows.append(
            {
                "name": safe_name(name),
                "family": str(item.get("family", "")),
                "texts": str(text_path) if text_path.exists() else text_spec,
                "source_manifest": str(path),
            }
        )
    return rows


def write_lines(path: Path, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", action="append", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--seed", type=int, default=20260611)
    parser.add_argument("--train-fraction", type=float, default=0.5)
    parser.add_argument("--min-train", type=int, default=4)
    parser.add_argument("--min-eval", type=int, default=4)
    parser.add_argument("--min-chars", type=int, default=4000)
    args = parser.parse_args()

    if not 0.0 < args.train_fraction < 1.0:
        raise SystemExit("--train-fraction must be between 0 and 1")

    outdir = Path(args.outdir)
    suites: list[dict[str, Any]] = []
    seen: set[str] = set()
    for manifest in args.manifest:
        for suite in load_manifest_suites(Path(manifest)):
            base_name = suite["name"]
            name = base_name
            suffix = 2
            while name in seen:
                name = f"{base_name}_{suffix}"
                suffix += 1
            suite["name"] = name
            seen.add(name)
            suites.append(suite)

    output_suites = []
    rng = random.Random(args.seed)
    for suite in suites:
        texts = [text for text in parse_texts(suite["texts"]) if text.strip()]
        if len(texts) < args.min_train + args.min_eval:
            raise SystemExit(
                f"suite {suite['name']!r} has {len(texts)} texts; "
                f"need at least {args.min_train + args.min_eval}"
            )
        if sum(len(text) for text in texts) < args.min_chars:
            raise SystemExit(f"suite {suite['name']!r} has too few characters")
        shuffled = list(texts)
        rng.shuffle(shuffled)
        train_count = round(len(shuffled) * args.train_fraction)
        train_count = max(args.min_train, min(len(shuffled) - args.min_eval, train_count))
        train_rows = shuffled[:train_count]
        eval_rows = shuffled[train_count:]
        suite_dir = outdir / suite["name"]
        train_path = suite_dir / "router_train.txt"
        eval_path = suite_dir / "router_eval.txt"
        write_lines(train_path, train_rows)
        write_lines(eval_path, eval_rows)
        output_suites.append(
            {
                "name": suite["name"],
                "family": suite["family"],
                "source_manifest": suite["source_manifest"],
                "source_texts": suite["texts"],
                "train_texts": str(train_path),
                "eval_texts": str(eval_path),
                "train_count": len(train_rows),
                "eval_count": len(eval_rows),
                "train_chars": sum(len(text) for text in train_rows),
                "eval_chars": sum(len(text) for text in eval_rows),
            }
        )

    summary = {
        "seed": args.seed,
        "train_fraction": args.train_fraction,
        "suites": output_suites,
    }
    manifest_path = outdir / "manifest.json"
    manifest_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"event": "suite_split_manifest_ready", "path": str(manifest_path), **summary}, indent=2))


if __name__ == "__main__":
    main()
