"""Prepare explicit held-out text files for MWG broad/router validation.

The output is intentionally plain newline-separated text because the existing
MWG evaluators consume that format through ``parse_texts``. Each suite records
dataset provenance in a sidecar manifest so later paper tables can identify the
exact source split instead of relying on DEFAULT_TEXTS or hand-copied snippets.
"""

from __future__ import annotations

import argparse
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class CorpusSpec:
    name: str
    dataset: str
    config: str | None
    split: str
    fields: tuple[str, ...]
    max_items: int


CORPORA = [
    CorpusSpec("wikitext103_validation", "Salesforce/wikitext", "wikitext-103-raw-v1", "validation", ("text",), 260),
    CorpusSpec("gsm8k_test", "openai/gsm8k", "main", "test", ("question", "answer"), 260),
    CorpusSpec("mbpp_test", "google-research-datasets/mbpp", "sanitized", "test", ("text", "code"), 260),
    CorpusSpec("alpaca_cleaned_train_tail", "yahma/alpaca-cleaned", None, "train", ("instruction", "input", "output"), 260),
]


def normalize(text: str) -> str:
    text = re.sub(r"\s+", " ", text.replace("\x00", " ")).strip()
    return text


def item_text(item: dict[str, Any], fields: tuple[str, ...]) -> str:
    parts = []
    for field in fields:
        value = item.get(field)
        if value is None:
            continue
        value_text = normalize(str(value))
        if value_text:
            parts.append(value_text)
    return normalize(" ".join(parts))


def load_items(spec: CorpusSpec, min_chars: int, seed: int) -> tuple[list[str], dict[str, Any]]:
    from datasets import load_dataset  # type: ignore

    kwargs: dict[str, Any] = {"split": spec.split}
    if spec.config is None:
        dataset = load_dataset(spec.dataset, **kwargs)
    else:
        dataset = load_dataset(spec.dataset, spec.config, **kwargs)

    rows: list[str] = []
    for item in dataset:
        text = item_text(item, spec.fields)
        if len(text) >= min_chars:
            rows.append(text)
        if len(rows) >= spec.max_items * 4:
            break
    rng = random.Random(seed)
    rng.shuffle(rows)
    rows = rows[: spec.max_items]
    metadata = {
        "name": spec.name,
        "dataset": spec.dataset,
        "config": spec.config,
        "split": spec.split,
        "fields": spec.fields,
        "selected_items": len(rows),
        "characters": sum(len(row) for row in rows),
    }
    return rows, metadata


def write_texts(path: Path, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def split_router_rows(suites: dict[str, list[str]], train_count: int, eval_count: int, seed: int) -> tuple[list[str], list[str]]:
    combined: list[tuple[str, str]] = []
    for name, rows in suites.items():
        for row in rows:
            combined.append((name, row))
    rng = random.Random(seed + 17)
    rng.shuffle(combined)
    train = [row for _name, row in combined[:train_count]]
    eval_rows = [row for _name, row in combined[train_count : train_count + eval_count]]
    overlap = set(train) & set(eval_rows)
    if overlap:
        raise RuntimeError(f"router split overlap detected: {len(overlap)} item(s)")
    return train, eval_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default="data/heldout")
    parser.add_argument("--seed", type=int, default=20260524)
    parser.add_argument("--min-item-chars", type=int, default=80)
    parser.add_argument("--min-suite-texts", type=int, default=8)
    parser.add_argument("--min-suite-chars", type=int, default=4000)
    parser.add_argument("--router-train-count", type=int, default=256)
    parser.add_argument("--router-eval-count", type=int, default=256)
    parser.add_argument("--allow-partial", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    suites: dict[str, list[str]] = {}
    provenance: dict[str, Any] = {"seed": args.seed, "suites": [], "failures": []}
    for spec in CORPORA:
        try:
            rows, metadata = load_items(spec, args.min_item_chars, args.seed)
            if len(rows) < args.min_suite_texts:
                raise RuntimeError(f"only {len(rows)} rows after filtering")
            if sum(len(row) for row in rows) < args.min_suite_chars:
                raise RuntimeError("suite has too few characters after filtering")
            text_path = outdir / f"{spec.name}.txt"
            write_texts(text_path, rows)
            metadata["path"] = str(text_path)
            suites[spec.name] = rows
            provenance["suites"].append(metadata)
            print(json.dumps({"event": "suite_prepared", **metadata}), flush=True)
        except Exception as exc:
            failure = {"name": spec.name, "dataset": spec.dataset, "split": spec.split, "error": repr(exc)}
            provenance["failures"].append(failure)
            print(json.dumps({"event": "suite_failed", **failure}), flush=True)
            if not args.allow_partial:
                raise

    if not suites:
        raise SystemExit("no held-out suites were prepared")

    train_rows, eval_rows = split_router_rows(suites, args.router_train_count, args.router_eval_count, args.seed)
    if len(train_rows) < args.min_suite_texts or len(eval_rows) < args.min_suite_texts:
        raise SystemExit("router train/eval splits are too small")
    write_texts(outdir / "router_train.txt", train_rows)
    write_texts(outdir / "router_eval.txt", eval_rows)

    manifest = {
        "suites": [
            {"name": item["name"], "texts": Path(item["path"]).name}
            for item in provenance["suites"]
        ]
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    provenance["router"] = {
        "train_texts": str(outdir / "router_train.txt"),
        "eval_texts": str(outdir / "router_eval.txt"),
        "train_count": len(train_rows),
        "eval_count": len(eval_rows),
        "train_characters": sum(len(row) for row in train_rows),
        "eval_characters": sum(len(row) for row in eval_rows),
    }
    (outdir / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"event": "heldout_ready", "outdir": str(outdir), **provenance["router"]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
