"""Build a balanced MMLU test subset for the layer-16 selective-regime probe.

Downloads cais/mmlu (test split) via the datasets library and writes a
deterministic, subject-balanced JSONL with the same shape as the eval
script's parser: {"question", "choices", "answer"} per line.

Balanced sampling: per_item items from every subject that has at least
per_item test items (all 57 subjects do), in subject order with a fixed
seed, so the subset is reproducible and covers all domains.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from datasets import load_dataset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-item", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260820)
    parser.add_argument("--out-jsonl", required=True)
    args = parser.parse_args()

    ds = load_dataset("cais/mmlu", "all", split="test", trust_remote_code=True)
    rng = random.Random(args.seed)

    subjects = sorted(set(ds["subject"]))
    items: list[dict] = []
    for subject in subjects:
        rows = [r for r in ds if r["subject"] == subject]
        chosen = rng.sample(rows, min(args.per_item, len(rows)))
        for row in chosen:
            items.append({
                "question": row["question"],
                "choices": list(row["choices"]),
                "answer": int(row["answer"]),
                "subject": subject,
            })

    out = Path(args.out_jsonl)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(json.dumps({
        "n_items": len(items),
        "n_subjects": len(subjects),
        "per_item": args.per_item,
        "out": str(out),
    }))


if __name__ == "__main__":
    main()
