"""Prepare additional held-out corpus families without modifying the main set.

The initial broad manifest covers math, code, and instruction following. This
helper tries to add explicit files for missing families in a separate output
directory. It is intentionally failure-tolerant: unavailable Hugging Face
datasets are recorded in provenance rather than silently replaced by defaults.
"""

from __future__ import annotations

import argparse
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ExtraCorpusSpec:
    name: str
    family: str
    dataset: str
    config: str | None
    split: str
    fields: tuple[str, ...]
    max_items: int


@dataclass(frozen=True)
class LocalTextSpec:
    name: str
    family: str
    path: Path
    fields: tuple[str, ...]


EXTRA_CORPORA = [
    ExtraCorpusSpec(
        "wikitext103_validation_extra",
        "general_language_modeling",
        "Salesforce/wikitext",
        "wikitext-103-raw-v1",
        "validation",
        ("text",),
        260,
    ),
    ExtraCorpusSpec(
        "hellaswag_validation_extra",
        "commonsense_reasoning",
        "Rowan/hellaswag",
        None,
        "validation",
        ("ctx", "endings", "label"),
        260,
    ),
    ExtraCorpusSpec(
        "daily_dialog_validation_extra",
        "multi_turn_dialogue",
        "daily_dialog",
        None,
        "validation",
        ("dialog",),
        260,
    ),
    ExtraCorpusSpec(
        "qasper_validation_extra",
        "long_context",
        "allenai/qasper",
        None,
        "validation",
        ("title", "abstract", "full_text", "qas"),
        120,
    ),
]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\x00", " ")).strip()


def flatten_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return normalize(value)
    if isinstance(value, (int, float, bool)):
        return normalize(str(value))
    if isinstance(value, list):
        return normalize(" ".join(flatten_value(item) for item in value))
    if isinstance(value, dict):
        return normalize(" ".join(flatten_value(item) for item in value.values()))
    return normalize(str(value))


def item_text(item: dict[str, Any], fields: tuple[str, ...]) -> str:
    parts = []
    for field in fields:
        value = item.get(field)
        text = flatten_value(value)
        if text:
            parts.append(text)
    return normalize(" ".join(parts))


def load_items(spec: ExtraCorpusSpec, min_chars: int, seed: int) -> tuple[list[str], dict[str, Any]]:
    from datasets import load_dataset  # type: ignore

    kwargs: dict[str, Any] = {"split": spec.split}
    if spec.config is None:
        dataset = load_dataset(spec.dataset, **kwargs)
    else:
        dataset = load_dataset(spec.dataset, spec.config, **kwargs)

    rows = []
    for item in dataset:
        text = item_text(dict(item), spec.fields)
        if len(text) >= min_chars:
            rows.append(text)
        if len(rows) >= spec.max_items * 4:
            break
    rng = random.Random(seed)
    rng.shuffle(rows)
    rows = rows[: spec.max_items]
    metadata = {
        "name": spec.name,
        "family": spec.family,
        "dataset": spec.dataset,
        "config": spec.config,
        "split": spec.split,
        "fields": list(spec.fields),
        "selected_items": len(rows),
        "characters": sum(len(row) for row in rows),
    }
    return rows, metadata


def parse_local_text_spec(value: str) -> LocalTextSpec:
    parts = value.split("=", 2)
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("expected name=family=/path/to/data[.txt|.jsonl][:field1,field2]")
    name, family, path = (part.strip() for part in parts)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
        raise argparse.ArgumentTypeError(f"invalid local suite name: {name!r}")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", family):
        raise argparse.ArgumentTypeError(f"invalid local family: {family!r}")
    if not path:
        raise argparse.ArgumentTypeError("local text path is empty")
    field_text = ""
    path_text = path
    if ":" in path and not Path(path).exists():
        candidate_path, candidate_fields = path.rsplit(":", 1)
        if candidate_fields and all(re.fullmatch(r"[A-Za-z0-9_.-]+", item.strip()) for item in candidate_fields.split(",")):
            path_text = candidate_path
            field_text = candidate_fields
    fields = tuple(item.strip() for item in field_text.split(",") if item.strip())
    return LocalTextSpec(name=name, family=family, path=Path(path_text), fields=fields)


def load_json_rows(path: Path, fields: tuple[str, ...]) -> list[str]:
    raw = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not raw:
        return []
    values: list[Any] = []
    if path.suffix.lower() == ".jsonl":
        for line in raw.splitlines():
            line = line.strip()
            if line:
                values.append(json.loads(line))
    else:
        parsed = json.loads(raw)
        values = parsed if isinstance(parsed, list) else [parsed]
    rows = []
    for value in values:
        if isinstance(value, dict):
            selected_fields = fields or tuple(value.keys())
            text = item_text(value, selected_fields)
        else:
            text = flatten_value(value)
        if text:
            rows.append(text)
    return rows


def load_plain_text_rows(path: Path, paragraph_mode: bool) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if paragraph_mode:
        chunks = re.split(r"\n\s*\n+", text)
    else:
        chunks = text.splitlines()
    return [normalize(chunk) for chunk in chunks if normalize(chunk)]


def load_local_texts(
    spec: LocalTextSpec,
    min_chars: int,
    max_items: int,
    seed: int,
    paragraph_mode: bool,
) -> tuple[list[str], dict[str, Any]]:
    if not spec.path.exists():
        raise FileNotFoundError(str(spec.path))
    if spec.path.suffix.lower() in {".json", ".jsonl"}:
        rows = load_json_rows(spec.path, spec.fields)
    else:
        rows = load_plain_text_rows(spec.path, paragraph_mode)
    rows = [row for row in rows if len(row) >= min_chars]
    rng = random.Random(seed)
    rng.shuffle(rows)
    rows = rows[:max_items]
    metadata = {
        "name": spec.name,
        "family": spec.family,
        "source_type": "local_text",
        "source_path": str(spec.path),
        "fields": list(spec.fields),
        "paragraph_mode": paragraph_mode,
        "selected_items": len(rows),
        "characters": sum(len(row) for row in rows),
    }
    return rows, metadata


def write_texts(path: Path, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default="data/heldout_extra")
    parser.add_argument("--seed", type=int, default=20260526)
    parser.add_argument("--min-item-chars", type=int, default=80)
    parser.add_argument("--min-suite-texts", type=int, default=8)
    parser.add_argument("--min-suite-chars", type=int, default=4000)
    parser.add_argument("--local-max-items", type=int, default=260)
    parser.add_argument(
        "--local-paragraphs",
        action="store_true",
        help="For plain-text local sources, split examples on blank-line paragraph blocks instead of lines.",
    )
    parser.add_argument(
        "--local-text",
        action="append",
        default=[],
        type=parse_local_text_spec,
        help="Explicit local source as name=family=/path/to/data[.txt|.jsonl][:field1,field2]; may be repeated.",
    )
    parser.add_argument("--skip-hf", action="store_true", help="Only ingest explicit --local-text sources.")
    parser.add_argument("--allow-partial", action="store_true")
    return parser.parse_args()


def record_suite(
    outdir: Path,
    manifest: dict[str, Any],
    provenance: dict[str, Any],
    rows: list[str],
    metadata: dict[str, Any],
) -> None:
    text_path = outdir / f"{metadata['name']}.txt"
    write_texts(text_path, rows)
    metadata["path"] = str(text_path)
    provenance["suites"].append(metadata)
    manifest["suites"].append({"name": metadata["name"], "family": metadata["family"], "texts": text_path.name})
    print(json.dumps({"event": "extra_suite_prepared", **metadata}), flush=True)


def main() -> None:
    args = parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    provenance: dict[str, Any] = {
        "seed": args.seed,
        "purpose": "extra held-out family coverage; separate from the main manifest",
        "suites": [],
        "failures": [],
    }
    manifest = {"suites": []}
    seen_names: set[str] = set()
    for spec in [] if args.skip_hf else EXTRA_CORPORA:
        try:
            if spec.name in seen_names:
                raise RuntimeError(f"duplicate suite name: {spec.name}")
            rows, metadata = load_items(spec, args.min_item_chars, args.seed)
            if len(rows) < args.min_suite_texts:
                raise RuntimeError(f"only {len(rows)} rows after filtering")
            if sum(len(row) for row in rows) < args.min_suite_chars:
                raise RuntimeError("suite has too few characters after filtering")
            record_suite(outdir, manifest, provenance, rows, metadata)
            seen_names.add(spec.name)
        except Exception as exc:
            failure = {
                "name": spec.name,
                "family": spec.family,
                "dataset": spec.dataset,
                "config": spec.config,
                "split": spec.split,
                "error": repr(exc),
            }
            provenance["failures"].append(failure)
            print(json.dumps({"event": "extra_suite_failed", **failure}), flush=True)
            if not args.allow_partial:
                raise
    for spec in args.local_text:
        try:
            if spec.name in seen_names:
                raise RuntimeError(f"duplicate suite name: {spec.name}")
            rows, metadata = load_local_texts(
                spec,
                args.min_item_chars,
                args.local_max_items,
                args.seed,
                args.local_paragraphs,
            )
            if len(rows) < args.min_suite_texts:
                raise RuntimeError(f"only {len(rows)} rows after filtering")
            if sum(len(row) for row in rows) < args.min_suite_chars:
                raise RuntimeError("suite has too few characters after filtering")
            record_suite(outdir, manifest, provenance, rows, metadata)
            seen_names.add(spec.name)
        except Exception as exc:
            failure = {
                "name": spec.name,
                "family": spec.family,
                "source_type": "local_text",
                "source_path": str(spec.path),
                "error": repr(exc),
            }
            provenance["failures"].append(failure)
            print(json.dumps({"event": "extra_suite_failed", **failure}), flush=True)
            if not args.allow_partial:
                raise

    (outdir / "manifest_extra.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (outdir / "provenance_extra.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"event": "extra_heldout_ready", "outdir": str(outdir), **manifest}, indent=2), flush=True)


if __name__ == "__main__":
    main()
