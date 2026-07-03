"""Audit router split manifests for leakage and suite balance.

This is a lightweight local helper that checks whether a suite split manifest is
safe to use as one combined router train/eval pool. Some manifests are intended
for per-suite evaluation and can have large cross-suite train/eval overlap when
loaded globally.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_lines(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_suite_rows(manifest_path: Path, key: str) -> tuple[list[dict[str, Any]], list[str]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    suites = []
    all_rows = []
    for suite in manifest.get("suites", []):
        source = suite.get(key)
        if not source:
            continue
        rows = read_lines(Path(source))
        suites.append({"name": suite["name"], "path": source, "count": len(rows), "unique_count": len(set(rows))})
        all_rows.extend(rows)
    return suites, all_rows


def audit(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path = Path(args.manifest)
    train_suites, train_rows = load_suite_rows(manifest_path, args.train_key)
    eval_suites, eval_rows = load_suite_rows(manifest_path, args.eval_key)
    train_set = set(train_rows)
    eval_set = set(eval_rows)
    overlap = train_set & eval_set
    clean_train = [row for row in train_rows if row not in eval_set]
    clean_by_suite = []
    eval_by_suite = {row["name"]: row for row in eval_suites}
    train_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for suite in train_manifest.get("suites", []):
        source = suite.get(args.train_key)
        if not source:
            continue
        rows = read_lines(Path(source))
        clean_rows = [row for row in rows if row not in eval_set]
        own_eval_rows = read_lines(Path(suite[args.eval_key])) if suite.get(args.eval_key) else []
        own_overlap = set(rows) & set(own_eval_rows)
        clean_by_suite.append(
            {
                "name": suite["name"],
                "train_count": len(rows),
                "train_unique_count": len(set(rows)),
                "own_eval_count": eval_by_suite.get(suite["name"], {}).get("count", len(own_eval_rows)),
                "own_overlap_count": len(own_overlap),
                "removed_against_eval_union": len(rows) - len(clean_rows),
                "clean_train_count": len(clean_rows),
            }
        )
    ready = bool(clean_train) and not overlap
    return {
        "manifest": str(manifest_path),
        "train_key": args.train_key,
        "eval_key": args.eval_key,
        "train_total": len(train_rows),
        "train_unique_total": len(train_set),
        "eval_total": len(eval_rows),
        "eval_unique_total": len(eval_set),
        "train_eval_overlap_unique": len(overlap),
        "clean_train_total_after_eval_union_removal": len(clean_train),
        "train_suites": train_suites,
        "eval_suites": eval_suites,
        "suite_cleanup": clean_by_suite,
        "combined_manifest_ready": ready,
        "claim_boundary": (
            "ready for one combined router train/eval run"
            if ready
            else "not ready for one combined router run; use per-suite runs or prepare a global leakage-clean split"
        ),
    }


def write_markdown(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Router Split Manifest Audit",
        "",
        f"Manifest: `{payload['manifest']}`",
        "",
        f"Train/eval overlap unique rows: `{payload['train_eval_overlap_unique']}`",
        f"Clean train rows after eval-union removal: `{payload['clean_train_total_after_eval_union_removal']}`",
        f"Combined manifest ready: `{str(payload['combined_manifest_ready']).lower()}`",
        "",
        "## Suite Cleanup",
        "",
        "| Suite | Train | Own eval | Own overlap | Removed vs eval union | Clean train |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["suite_cleanup"]:
        lines.append(
            f"| {row['name']} | {row['train_count']} | {row['own_eval_count']} | {row['own_overlap_count']} | "
            f"{row['removed_against_eval_union']} | {row['clean_train_count']} |"
        )
    lines.extend(["", "## Claim Boundary", "", payload["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--train-key", default="train_texts")
    parser.add_argument("--eval-key", default="eval_texts")
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = audit(args)
    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    write_markdown(payload, Path(args.out_md))
    print(json.dumps(payload, indent=2), flush=True)


if __name__ == "__main__":
    main()
