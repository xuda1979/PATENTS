"""Build dialogue and long-context corpora for the unseen-family transfer test.

Downloads small subsets via hf-mirror and writes plain-text files (one
document per line), matching the manifest suite format:
  - dialogue: databricks/databricks-dolly-15k, ~100 instruction+response rows
  - long-context: emozilla/pg19 test, ~100 book excerpts (~1K-2K tokens each)
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from datasets import load_dataset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-dialogue", type=int, default=100)
    parser.add_argument("--n-longcontext", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260821)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)

    dolly = load_dataset("databricks/databricks-dolly-15k", split="train")
    dialogue_lines = []
    for row in dolly:
        if not row.get("response") or not row.get("instruction"):
            continue
        dialogue_lines.append(f"Instruction: {row['instruction']}\nResponse: {row['response']}")
        if len(dialogue_lines) >= args.n_dialogue:
            break
    (out / "dolly_dialogue.txt").write_text(
        "\n".join(dialogue_lines) + "\n", encoding="utf-8")

    pg19 = load_dataset("emozilla/pg19", split="test")
    texts = [row["text"] for row in pg19]
    chosen = rng.sample(range(len(texts)), min(args.n_longcontext, len(texts)))
    long_lines = []
    for i in chosen:
        t = texts[i].strip()
        if not t:
            continue
        # keep a ~4K-char slice per book (long-context prose, seq 256 windows)
        long_lines.append(t[:8000])
    (out / "pg19_longcontext.txt").write_text(
        "\n".join(long_lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "dialogue_items": len(dialogue_lines),
        "dialogue_chars": sum(len(x) for x in dialogue_lines),
        "longcontext_books": len(long_lines),
        "longcontext_chars": sum(len(x) for x in long_lines),
        "out": str(out),
    }))


if __name__ == "__main__":
    main()
