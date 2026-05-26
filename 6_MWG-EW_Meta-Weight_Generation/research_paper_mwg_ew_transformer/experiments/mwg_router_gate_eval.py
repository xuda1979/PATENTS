"""Deployable dense-fallback router for a patched MWG FFN layer.

Unlike ``mwg_hybrid_gate_eval.py``, this script does not route with oracle
dense-vs-patched loss deltas from the evaluation split. It trains a small ridge
regressor on a separate text split to predict patch risk from features available
before the target FFN executes, then evaluates thresholded dense fallback on a
held-out split.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn

from mwg_ppl_patch_eval import PatchedMLP, load_student, setup_device, sync_device
from mwg_quality_distillation import DEFAULT_TEXTS, dtype_from_name, parse_texts


def parse_fractions(value: str) -> list[float]:
    return [float(item.strip()) for item in value.split(",") if item.strip()]


def select_texts(texts: list[str], count: int, seed: int) -> list[str]:
    if count <= 0:
        return texts
    expanded = [texts[index % len(texts)] for index in range(count)]
    rng = random.Random(seed)
    rng.shuffle(expanded)
    return expanded


def encode(tokenizer: Any, text: str, seq: int, device: torch.device) -> dict[str, torch.Tensor]:
    encoded = tokenizer(
        [text],
        return_tensors="pt",
        padding="max_length",
        truncation=True,
        max_length=seq,
    )
    return {key: value.to(device) for key, value in encoded.items()}


def labels_from(encoded: dict[str, torch.Tensor]) -> torch.Tensor:
    labels = encoded["input_ids"].clone()
    labels[encoded["attention_mask"] == 0] = -100
    return labels


def hidden_features(hidden: torch.Tensor, attention_mask: torch.Tensor) -> list[float]:
    mask = attention_mask.bool().view(-1)
    values = hidden.detach().float().view(-1, hidden.shape[-1])
    if bool(mask.any()):
        values = values[mask]
    flat = values.reshape(-1)
    token_count = float(max(int(mask.sum().item()), 1))
    seq_len = float(attention_mask.shape[-1])
    rms = torch.sqrt(torch.mean(values.square())).item()
    abs_values = values.abs()
    return [
        math.log1p(token_count),
        token_count / max(seq_len, 1.0),
        float(values.mean().item()),
        float(values.std(unbiased=False).item()),
        float(rms),
        float(abs_values.mean().item()),
        float(abs_values.max().item()),
        float(torch.quantile(abs_values.reshape(-1), 0.95).item()),
        float(flat.mean().item()),
        float(flat.std(unbiased=False).item()),
    ]


@torch.no_grad()
def loss_and_features(
    model: nn.Module,
    tokenizer: Any,
    text: str,
    seq: int,
    layer: int,
    dense_mlp: nn.Module,
    patched_mlp: nn.Module,
    device: torch.device,
) -> dict[str, Any]:
    encoded = encode(tokenizer, text, seq, device)
    labels = labels_from(encoded)
    captured: list[torch.Tensor] = []

    def capture(_module: nn.Module, inputs: tuple[torch.Tensor, ...]) -> None:
        captured.append(inputs[0].detach())

    model.model.layers[layer].mlp = dense_mlp  # type: ignore[attr-defined]
    handle = dense_mlp.register_forward_pre_hook(capture)
    try:
        dense_output = model(**encoded, labels=labels)
    finally:
        handle.remove()
    if not captured:
        raise RuntimeError(f"failed to capture layer {layer} FFN input features")

    model.model.layers[layer].mlp = patched_mlp  # type: ignore[attr-defined]
    patched_output = model(**encoded, labels=labels)
    tokens = float((labels != -100).sum().item())
    dense_loss = float(dense_output.loss.item())
    patched_loss = float(patched_output.loss.item())
    return {
        "tokens": tokens,
        "dense_loss": dense_loss,
        "patched_loss": patched_loss,
        "delta_loss": patched_loss - dense_loss,
        "features": hidden_features(captured[0], encoded["attention_mask"]),
    }


def weighted_loss(items: list[dict[str, Any]], key: str) -> float:
    total_tokens = sum(float(item["tokens"]) for item in items)
    return sum(float(item[key]) * float(item["tokens"]) for item in items) / max(total_tokens, 1.0)


def fit_ridge(rows: list[dict[str, Any]], l2: float) -> dict[str, Any]:
    x = torch.tensor([row["features"] for row in rows], dtype=torch.float64)
    y = torch.tensor([row["delta_loss"] for row in rows], dtype=torch.float64).view(-1, 1)
    mean = x.mean(dim=0, keepdim=True)
    std = x.std(dim=0, unbiased=False, keepdim=True).clamp_min(1e-6)
    z = (x - mean) / std
    design = torch.cat([torch.ones(z.shape[0], 1, dtype=z.dtype), z], dim=1)
    penalty = torch.eye(design.shape[1], dtype=z.dtype) * l2
    penalty[0, 0] = 0.0
    coef = torch.linalg.solve(design.T @ design + penalty, design.T @ y).view(-1)
    train_pred = (design @ coef.view(-1, 1)).view(-1)
    mse = torch.mean((train_pred - y.view(-1)).square()).item()
    return {
        "mean": mean.view(-1).tolist(),
        "std": std.view(-1).tolist(),
        "coef": coef.tolist(),
        "train_mse": mse,
    }


def predict(row: dict[str, Any], model: dict[str, Any]) -> float:
    x = torch.tensor(row["features"], dtype=torch.float64)
    mean = torch.tensor(model["mean"], dtype=torch.float64)
    std = torch.tensor(model["std"], dtype=torch.float64)
    coef = torch.tensor(model["coef"], dtype=torch.float64)
    design = torch.cat([torch.ones(1, dtype=torch.float64), (x - mean) / std])
    return float(torch.dot(design, coef).item())


def quantile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, math.ceil(len(ordered) * fraction) - 1))
    return ordered[index]


def routed_frontier(
    train_rows: list[dict[str, Any]],
    eval_rows: list[dict[str, Any]],
    router: dict[str, Any],
    fractions: list[float],
) -> list[dict[str, float]]:
    train_scores = [predict(row, router) for row in train_rows]
    dense_loss = weighted_loss(eval_rows, "dense_loss")
    total_tokens = sum(float(row["tokens"]) for row in eval_rows)
    rows: list[dict[str, float]] = []
    for fraction in fractions:
        threshold = quantile(train_scores, fraction)
        patched_tokens = 0.0
        patched_examples = 0
        loss_sum = 0.0
        for row in eval_rows:
            score = predict(row, router)
            use_patch = score <= threshold
            key = "patched_loss" if use_patch else "dense_loss"
            loss_sum += float(row[key]) * float(row["tokens"])
            if use_patch:
                patched_tokens += float(row["tokens"])
                patched_examples += 1
        loss = loss_sum / max(total_tokens, 1.0)
        rows.append(
            {
                "target_patch_fraction": fraction,
                "train_score_threshold": threshold,
                "actual_patch_token_fraction": patched_tokens / max(total_tokens, 1.0),
                "patched_examples": float(patched_examples),
                "loss": loss,
                "ppl": math.exp(min(20.0, loss)),
                "delta_loss": loss - dense_loss,
                "ppl_ratio": math.exp(min(20.0, loss)) / math.exp(min(20.0, dense_loss)),
            }
        )
    return rows


def oracle_frontier(eval_rows: list[dict[str, Any]], fractions: list[float]) -> list[dict[str, float]]:
    ordered = sorted(eval_rows, key=lambda item: float(item["delta_loss"]))
    dense_loss = weighted_loss(ordered, "dense_loss")
    total_tokens = sum(float(row["tokens"]) for row in ordered)
    rows: list[dict[str, float]] = []
    for fraction in fractions:
        target_tokens = total_tokens * fraction
        patched_tokens = 0.0
        patched_examples = 0
        loss_sum = 0.0
        for row in ordered:
            use_patch = patched_tokens < target_tokens
            key = "patched_loss" if use_patch else "dense_loss"
            loss_sum += float(row[key]) * float(row["tokens"])
            if use_patch:
                patched_tokens += float(row["tokens"])
                patched_examples += 1
        loss = loss_sum / max(total_tokens, 1.0)
        rows.append(
            {
                "target_patch_fraction": fraction,
                "actual_patch_token_fraction": patched_tokens / max(total_tokens, 1.0),
                "patched_examples": float(patched_examples),
                "loss": loss,
                "ppl": math.exp(min(20.0, loss)),
                "delta_loss": loss - dense_loss,
                "ppl_ratio": math.exp(min(20.0, loss)) / math.exp(min(20.0, dense_loss)),
            }
        )
    return rows


def collect_rows(
    split: str,
    texts: list[str],
    model: nn.Module,
    tokenizer: Any,
    args: argparse.Namespace,
    dense_mlp: nn.Module,
    patched_mlp: nn.Module,
    device: torch.device,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, text in enumerate(texts):
        row = loss_and_features(model, tokenizer, text, args.seq, args.layer, dense_mlp, patched_mlp, device)
        row["index"] = index
        row["split"] = split
        rows.append(row)
        if index == 0 or (index + 1) % 25 == 0:
            print(
                json.dumps(
                    {
                        "event": "router_collect",
                        "split": split,
                        "index": index + 1,
                        "tokens": row["tokens"],
                        "delta_loss": row["delta_loss"],
                    }
                ),
                flush=True,
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--layer", type=int, required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--train-texts", type=parse_texts, default=[])
    parser.add_argument("--eval-texts", type=parse_texts, default=[])
    parser.add_argument("--require-texts", action="store_true")
    parser.add_argument("--seq", type=int, default=256)
    parser.add_argument("--train-examples", type=int, default=256)
    parser.add_argument("--eval-examples", type=int, default=256)
    parser.add_argument("--fractions", type=parse_fractions, default=[0.25, 0.5, 0.75, 1.0])
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--ridge-l2", type=float, default=1.0)
    parser.add_argument("--dtype", choices=["auto", "fp16", "bf16", "fp32"], default="auto")
    parser.add_argument("--out-json", required=True)
    args = parser.parse_args()

    from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore

    if args.require_texts and (not args.train_texts or not args.eval_texts):
        raise SystemExit("explicit --train-texts and --eval-texts are required; refusing DEFAULT_TEXTS fallback")
    train_texts = select_texts(args.train_texts or DEFAULT_TEXTS, args.train_examples, args.seed)
    eval_texts = select_texts(args.eval_texts or DEFAULT_TEXTS, args.eval_examples, args.seed + 1009)
    if args.require_texts and set(train_texts) & set(eval_texts):
        raise SystemExit("train/eval text overlap detected; refusing leakage-prone router evaluation")

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

    student, payload = load_student(Path(args.checkpoint), device, dtype)
    dense_mlp = model.model.layers[args.layer].mlp  # type: ignore[attr-defined]
    patched_mlp = PatchedMLP(student)

    train_rows = collect_rows("train", train_texts, model, tokenizer, args, dense_mlp, patched_mlp, device)
    eval_rows = collect_rows("eval", eval_texts, model, tokenizer, args, dense_mlp, patched_mlp, device)
    model.model.layers[args.layer].mlp = dense_mlp  # type: ignore[attr-defined]
    sync_device()

    router = fit_ridge(train_rows, args.ridge_l2)
    dense_loss = weighted_loss(eval_rows, "dense_loss")
    patched_loss = weighted_loss(eval_rows, "patched_loss")
    result = {
        "dense": {"loss": dense_loss, "ppl": math.exp(min(20.0, dense_loss)), "tokens": sum(row["tokens"] for row in eval_rows)},
        "patched": {
            "loss": patched_loss,
            "ppl": math.exp(min(20.0, patched_loss)),
            "tokens": sum(row["tokens"] for row in eval_rows),
            "ppl_ratio": math.exp(min(20.0, patched_loss)) / math.exp(min(20.0, dense_loss)),
        },
        "router": router,
        "routed_frontier": routed_frontier(train_rows, eval_rows, router, args.fractions),
        "oracle_frontier": oracle_frontier(eval_rows, args.fractions),
        "feature_names": [
            "log_tokens",
            "fill_ratio",
            "hidden_mean",
            "hidden_std",
            "hidden_rms",
            "hidden_abs_mean",
            "hidden_abs_max",
            "hidden_abs_q95",
            "hidden_flat_mean",
            "hidden_flat_std",
        ],
        "train_examples": train_rows,
        "eval_examples": eval_rows,
        "checkpoint": str(args.checkpoint),
        "checkpoint_student": payload.get("student"),
        "config": vars(args),
    }
    Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_json).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "dense": result["dense"],
                "patched": result["patched"],
                "routed_frontier": result["routed_frontier"],
                "oracle_frontier": result["oracle_frontier"],
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
