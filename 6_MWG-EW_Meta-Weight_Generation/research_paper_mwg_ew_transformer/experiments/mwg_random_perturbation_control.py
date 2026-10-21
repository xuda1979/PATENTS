"""Random-perturbation control for the layer-16 selective quality claim.

Required reviewer control: route a target fraction of tokens through the
calibrated MWG patch with a *non-learned* selection (uniform random mask), at
the same budget as the tighter-eligibility router cell (0.9923x at ~2%
patching), and report the five-suite PPL ratio against the always-dense
baseline. If randomly altering ~2% of tokens reproduces the selective win, the
learned router is not the cause; if random patching degrades PPL while the
learned router improves it, the win is attributable to learned eligibility.

Reuses the exact model/checkpoint/manifest/eval plumbing of
mwg_token_router_gate_eval.py so the comparison is apples-to-apples.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn

from mwg_ppl_patch_eval import PatchedMLP, load_student, setup_device
from mwg_quality_distillation import dtype_from_name
from mwg_token_router_gate_eval import (
    encode,
    labels_from,
    load_suite_split_manifest,
    remove_text_overlap,
    select_suite_balanced_labeled_texts,
)


class RandomTokenMLP(nn.Module):
    """Patches a uniformly random token subset at the given budget (no learning)."""

    def __init__(self, dense_mlp: nn.Module, patched_mlp: nn.Module, fraction: float, seed: int):
        super().__init__()
        self.dense_mlp = dense_mlp
        self.patched_mlp = patched_mlp
        self.fraction = fraction
        self.rng = torch.Generator(device="cpu").manual_seed(seed)
        self.last_patch_tokens = 0
        self.last_total_tokens = 0

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, s, _ = x.shape
        mask = torch.rand(b, s, generator=self.rng, device="cpu").to(x.device) < self.fraction
        use_patch = mask.unsqueeze(-1)
        self.last_patch_tokens += int(use_patch.sum().item())
        self.last_total_tokens += int(use_patch.numel())
        return torch.where(use_patch, self.patched_mlp(x), self.dense_mlp(x))


@torch.no_grad()
def evaluate_ppl(
    mlp: nn.Module,
    model: Any,
    tokenizer: Any,
    texts: list[str],
    args: argparse.Namespace,
    device: torch.device,
) -> dict[str, float]:
    loss_sum = 0.0
    token_count = 0
    patch_tokens = 0
    total_tokens = 0
    model.model.layers[args.layer].mlp = mlp  # type: ignore[attr-defined]
    for text in texts:
        encoded = encode(tokenizer, text, args.seq, device)
        labels = labels_from(encoded)
        output = model(**encoded, labels=labels)
        valid = int(labels.ne(-100).sum().item())
        loss_sum += float(output.loss.item()) * valid
        token_count += valid
        patch_tokens += int(getattr(mlp, "last_patch_tokens", 0))
        total_tokens += int(getattr(mlp, "last_total_tokens", 0))
    loss = loss_sum / max(token_count, 1)
    return {
        "tokens": float(token_count),
        "loss": loss,
        "ppl": math.exp(min(20.0, loss)),
        "actual_patch_token_fraction": patch_tokens / max(total_tokens, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--layer", type=int, required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--suite-split-manifest", required=True)
    parser.add_argument("--seq", type=int, default=256)
    parser.add_argument("--dtype", choices=["auto", "fp16", "bf16", "fp32"], default="fp32")
    parser.add_argument("--seeds", default="0,1,2")
    parser.add_argument("--fractions", default="0.01,0.02,0.05")
    parser.add_argument("--out-json", required=True)
    args = parser.parse_args()

    from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore

    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
    fractions = [float(f.strip()) for f in args.fractions.split(",") if f.strip()]

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

    train_pool, train_label_pool, _ = load_suite_split_manifest(Path(args.suite_split_manifest), "train_texts")
    eval_pool, eval_label_pool, _ = load_suite_split_manifest(Path(args.suite_split_manifest), "eval_texts")
    train_pool, train_label_pool, overlap_removed = remove_text_overlap(train_pool, train_label_pool, eval_pool)
    if overlap_removed:
        raise SystemExit(f"suite split manifest has {overlap_removed} train/eval overlaps; refusing leakage-prone run")
    eval_texts, eval_suite_labels = select_suite_balanced_labeled_texts(eval_pool, eval_label_pool, 0, 0)
    if not eval_texts:
        raise SystemExit("no eval texts loaded from the manifest")

    print(json.dumps({"event": "dense_eval", "n_texts": len(eval_texts)}), flush=True)
    dense = evaluate_ppl(dense_mlp, model, tokenizer, eval_texts, args, device)
    print(json.dumps({"event": "always_patched_eval"}), flush=True)
    always_patched = evaluate_ppl(patched_mlp, model, tokenizer, eval_texts, args, device)

    cells: list[dict[str, Any]] = []
    for fraction in fractions:
        for seed in seeds:
            print(json.dumps({"event": "random_cell", "fraction": fraction, "seed": seed}), flush=True)
            mixed = evaluate_ppl(
                RandomTokenMLP(dense_mlp, patched_mlp, fraction, seed),
                model, tokenizer, eval_texts, args, device,
            )
            cell = {
                "patch_fraction_target": fraction,
                "seed": seed,
                "tokens": mixed["tokens"],
                "loss": mixed["loss"],
                "ppl": mixed["ppl"],
                "actual_patch_token_fraction": mixed["actual_patch_token_fraction"],
                "ppl_ratio": mixed["ppl"] / dense["ppl"],
            }
            cells.append(cell)
            print(json.dumps({"event": "random_cell_done", **cell}), flush=True)

    result = {
        "run": "random_perturbation_control",
        "layer": args.layer,
        "checkpoint": args.checkpoint,
        "suite_split_manifest": args.suite_split_manifest,
        "seq": args.seq,
        "seeds": seeds,
        "fractions": fractions,
        "dense": {"tokens": dense["tokens"], "loss": dense["loss"], "ppl": dense["ppl"]},
        "always_patched": {
            "tokens": always_patched["tokens"],
            "loss": always_patched["loss"],
            "ppl": always_patched["ppl"],
            "ppl_ratio": always_patched["ppl"] / dense["ppl"],
            "actual_patch_token_fraction": 1.0,
        },
        "cells": cells,
    }
    out = Path(args.out_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"event": "saved", "json": str(out)}), flush=True)


if __name__ == "__main__":
    main()
