"""Run leakage-resistant PPL validation from an explicit corpus manifest.

The manifest is intentionally simple:

{
  "suites": [
    {"name": "wikitext", "texts": "/path/to/wikitext_heldout.txt"},
    {"name": "code", "texts": "/path/to/code_heldout.txt", "eval_batches": 64}
  ]
}

Each text file is read by mwg_quality_distillation.parse_texts, so it may be a
newline-separated file or a ||-separated string. This harness never falls back
to DEFAULT_TEXTS.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from mwg_quality_distillation import parse_texts


def load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    suites = payload.get("suites")
    if not isinstance(suites, list) or not suites:
        raise SystemExit(f"manifest {path} must contain a non-empty suites list")
    return payload


def validate_suite(item: dict[str, Any], manifest_dir: Path, min_texts: int, min_chars: int) -> dict[str, Any]:
    name = item.get("name")
    text_spec = item.get("texts")
    if not isinstance(name, str) or not name.strip():
        raise SystemExit(f"invalid suite name in manifest item: {item!r}")
    if not isinstance(text_spec, str) or not text_spec.strip():
        raise SystemExit(f"suite {name!r} must provide explicit texts")

    text_path = Path(text_spec)
    if not text_path.is_absolute():
        text_path = manifest_dir / text_path
    resolved_spec = str(text_path) if text_path.exists() else text_spec
    texts = parse_texts(resolved_spec)
    char_count = sum(len(text) for text in texts)
    if len(texts) < min_texts:
        raise SystemExit(f"suite {name!r} has only {len(texts)} text item(s); need at least {min_texts}")
    if char_count < min_chars:
        raise SystemExit(f"suite {name!r} has only {char_count} characters; need at least {min_chars}")

    return {
        "name": name.strip(),
        "texts": resolved_spec,
        "text_count": len(texts),
        "char_count": char_count,
        "eval_batches": int(item.get("eval_batches", 0) or 0),
        "seq": int(item.get("seq", 0) or 0),
        "text_batch": int(item.get("text_batch", 0) or 0),
    }


def ppl_ratio(result: dict[str, Any]) -> float:
    return float(result["patched"]["ppl"]) / max(float(result["dense"]["ppl"]), 1e-12)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--patch", action="append", required=True, help="layer:/path/to/checkpoint.pt")
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--seq", type=int, default=256)
    parser.add_argument("--text-batch", type=int, default=2)
    parser.add_argument("--eval-batches", type=int, default=128)
    parser.add_argument("--dtype", choices=["auto", "fp16", "bf16", "fp32"], default="fp32")
    parser.add_argument("--min-texts", type=int, default=8)
    parser.add_argument("--min-chars", type=int, default=4000)
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    manifest = load_manifest(manifest_path)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    suites = [
        validate_suite(item, manifest_path.parent, args.min_texts, args.min_chars)
        for item in manifest["suites"]
    ]
    rows: list[dict[str, Any]] = []
    for suite in suites:
        out_json = outdir / f"ppl_{suite['name']}.json"
        command = [
            sys.executable,
            "experiments/mwg_ppl_patch_eval.py",
            "--model-dir",
            args.model_dir,
            "--texts",
            suite["texts"],
            "--seq",
            str(suite["seq"] or args.seq),
            "--text-batch",
            str(suite["text_batch"] or args.text_batch),
            "--eval-batches",
            str(suite["eval_batches"] or args.eval_batches),
            "--dtype",
            args.dtype,
            "--out-json",
            str(out_json),
            "--require-texts",
        ]
        for patch in args.patch:
            command.extend(["--patch", patch])
        subprocess.run(command, check=True)
        result = json.loads(out_json.read_text(encoding="utf-8"))
        row = {
            "name": suite["name"],
            "texts": suite["texts"],
            "text_count": suite["text_count"],
            "char_count": suite["char_count"],
            "path": str(out_json),
            "dense_ppl": result["dense"]["ppl"],
            "patched_ppl": result["patched"]["ppl"],
            "ppl_ratio": ppl_ratio(result),
            "tokens": result["patched"]["tokens"],
        }
        rows.append(row)
        print(json.dumps({"event": "suite_done", **row}), flush=True)

    total_tokens = sum(float(row["tokens"]) for row in rows)
    weighted_ratio = sum(float(row["ppl_ratio"]) * float(row["tokens"]) for row in rows) / max(total_tokens, 1.0)
    summary = {
        "manifest": str(manifest_path),
        "model_dir": args.model_dir,
        "patches": args.patch,
        "config": vars(args),
        "suites": rows,
        "aggregate": {
            "suite_count": len(rows),
            "tokens": total_tokens,
            "token_weighted_ppl_ratio": weighted_ratio,
            "max_ppl_ratio": max(float(row["ppl_ratio"]) for row in rows),
        },
    }
    summary_path = outdir / "summary_broad_eval.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
