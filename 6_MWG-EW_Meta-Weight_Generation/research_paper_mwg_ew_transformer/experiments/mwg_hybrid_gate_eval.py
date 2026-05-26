"""Oracle dense-fallback frontier for a patched MWG FFN layer.

This evaluation does not claim a deployable router. It estimates whether a
hybrid policy could make the method publishable by using the patched FFN only
on examples whose measured dense-vs-patched loss increase is smallest, while
falling back to the dense FFN elsewhere.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn

from mwg_ppl_patch_eval import PatchedMLP, load_student, setup_device, sync_device
from mwg_quality_distillation import DEFAULT_TEXTS, dtype_from_name, parse_texts


@torch.no_grad()
def example_loss(
    model: nn.Module,
    tokenizer: Any,
    text: str,
    seq: int,
    device: torch.device,
) -> dict[str, float]:
    encoded = tokenizer(
        [text],
        return_tensors="pt",
        padding="max_length",
        truncation=True,
        max_length=seq,
    )
    encoded = {key: value.to(device) for key, value in encoded.items()}
    labels = encoded["input_ids"].clone()
    labels[encoded["attention_mask"] == 0] = -100
    output = model(**encoded, labels=labels)
    tokens = int((labels != -100).sum().item())
    return {"loss": float(output.loss.item()), "tokens": float(tokens)}


def weighted_loss(items: list[dict[str, float]], key: str) -> float:
    total_tokens = sum(item["tokens"] for item in items)
    return sum(item[key] * item["tokens"] for item in items) / max(total_tokens, 1.0)


def frontier(items: list[dict[str, float]], fractions: list[float]) -> list[dict[str, float]]:
    ordered = sorted(items, key=lambda item: item["delta_loss"])
    total_tokens = sum(item["tokens"] for item in ordered)
    dense_loss = weighted_loss(ordered, "dense_loss")
    rows: list[dict[str, float]] = []
    for fraction in fractions:
        target_tokens = total_tokens * fraction
        patched_tokens = 0.0
        hybrid_loss_sum = 0.0
        used_patched = 0
        for item in ordered:
            if patched_tokens < target_tokens:
                hybrid_loss_sum += item["patched_loss"] * item["tokens"]
                patched_tokens += item["tokens"]
                used_patched += 1
            else:
                hybrid_loss_sum += item["dense_loss"] * item["tokens"]
        hybrid_loss = hybrid_loss_sum / max(total_tokens, 1.0)
        rows.append(
            {
                "target_patch_fraction": fraction,
                "actual_patch_token_fraction": patched_tokens / max(total_tokens, 1.0),
                "patched_examples": float(used_patched),
                "loss": hybrid_loss,
                "ppl": math.exp(min(20.0, hybrid_loss)),
                "delta_loss": hybrid_loss - dense_loss,
                "ppl_ratio": math.exp(min(20.0, hybrid_loss)) / math.exp(min(20.0, dense_loss)),
            }
        )
    return rows


def parse_fractions(value: str) -> list[float]:
    return [float(item.strip()) for item in value.split(",") if item.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--layer", type=int, required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--texts", type=parse_texts, default=[])
    parser.add_argument("--require-texts", action="store_true")
    parser.add_argument("--seq", type=int, default=256)
    parser.add_argument("--eval-examples", type=int, default=256)
    parser.add_argument("--fractions", type=parse_fractions, default=[0.25, 0.5, 0.75, 1.0])
    parser.add_argument("--dtype", choices=["auto", "fp16", "bf16", "fp32"], default="auto")
    parser.add_argument("--out-json", required=True)
    args = parser.parse_args()

    from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore

    device = setup_device()
    dtype = dtype_from_name(args.dtype, device)
    model_dtype = dtype if device.type in {"npu", "cuda"} else torch.float32
    tokenizer = AutoTokenizer.from_pretrained(args.model_dir, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        args.model_dir,
        torch_dtype=model_dtype,
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    ).to(device)
    model.eval()

    if args.require_texts and not args.texts:
        raise SystemExit("explicit --texts is required for this hybrid eval path; refusing DEFAULT_TEXTS fallback")
    texts = args.texts or DEFAULT_TEXTS
    texts = [texts[index % len(texts)] for index in range(args.eval_examples)]

    student, payload = load_student(Path(args.checkpoint), device, dtype)
    dense_mlp = model.model.layers[args.layer].mlp  # type: ignore[attr-defined]
    patched_mlp = PatchedMLP(student)
    rows: list[dict[str, float]] = []
    for index, text in enumerate(texts):
        model.model.layers[args.layer].mlp = dense_mlp  # type: ignore[attr-defined]
        dense = example_loss(model, tokenizer, text, args.seq, device)
        model.model.layers[args.layer].mlp = patched_mlp  # type: ignore[attr-defined]
        patched = example_loss(model, tokenizer, text, args.seq, device)
        row = {
            "index": float(index),
            "tokens": dense["tokens"],
            "dense_loss": dense["loss"],
            "patched_loss": patched["loss"],
            "delta_loss": patched["loss"] - dense["loss"],
        }
        rows.append(row)
        if index == 0 or (index + 1) % 25 == 0:
            print(json.dumps({"event": "hybrid_eval", "index": index + 1, **row}), flush=True)

    sync_device()
    dense_loss = weighted_loss(rows, "dense_loss")
    patched_loss = weighted_loss(rows, "patched_loss")
    result = {
        "dense": {"loss": dense_loss, "ppl": math.exp(min(20.0, dense_loss)), "tokens": sum(item["tokens"] for item in rows)},
        "patched": {
            "loss": patched_loss,
            "ppl": math.exp(min(20.0, patched_loss)),
            "tokens": sum(item["tokens"] for item in rows),
            "ppl_ratio": math.exp(min(20.0, patched_loss)) / math.exp(min(20.0, dense_loss)),
        },
        "frontier": frontier(rows, args.fractions),
        "examples": rows,
        "checkpoint": str(args.checkpoint),
        "checkpoint_student": payload.get("student"),
        "config": vars(args),
    }
    Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_json).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({key: result[key] for key in ["dense", "patched", "frontier"]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
