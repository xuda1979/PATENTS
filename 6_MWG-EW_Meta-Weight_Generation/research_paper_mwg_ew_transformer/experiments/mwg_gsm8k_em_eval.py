"""GSM8K final-answer exact-match on the layer-16 selective regime.

Required downstream-accuracy probe: greedy-generation exact match on the
local GSM8K test subset for three arms sharing the same calibrated layer-16
checkpoint: (a) always-dense, (b) selective learned router at the
tighter-eligibility operating point (Delta_max = -0.20, policy global,
budget 0.10, the 0.9923x cell), and (c) a random 2%-budget control
(RandomTokenMLP) as the non-learned intervention of comparable budget.

The router is fitted exactly as in mwg_token_router_gate_eval.py on the
manifest train pool (suite-balanced ridge, seed 0, leakage-clean), and
generation routes tokens through the same TokenRouterMLP module.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

import torch

from mwg_ppl_patch_eval import PatchedMLP, load_student, setup_device
from mwg_quality_distillation import dtype_from_name
from mwg_random_perturbation_control import RandomTokenMLP
from mwg_token_router_gate_eval import (
    TokenRouterMLP,
    collect_token_rows,
    fit_weighted_ridge,
    load_suite_split_manifest,
    predict_features,
    remove_text_overlap,
    select_suite_balanced_labeled_texts,
    suite_balanced_weights,
    threshold_for_risk_budget,
)


def parse_gsm8k(path: Path) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or "####" not in line:
            continue
        left, answer = line.rsplit("####", 1)
        question = left
        qmark = left.find("?")
        if qmark >= 0:
            question = left[: qmark + 1]
        items.append((question.strip(), answer.strip()))
    return items


def normalize_answer(value: str) -> str:
    value = value.strip().lower()
    value = value.replace(",", "")
    value = value.replace("$", "")
    value = value.replace("%", "")
    value = re.sub(r"\.0+$", "", value)
    value = value.strip()
    return value


def extract_final_answer(generation: str) -> str:
    hash_match = re.findall(r"####\s*([^\n#]+)", generation)
    if hash_match:
        return hash_match[-1].strip()
    numbers = re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", generation)
    return numbers[-1] if numbers else ""


def exact_match(prediction: str, gold: str) -> bool:
    pred = normalize_answer(prediction)
    gold = normalize_answer(gold)
    if pred == gold:
        return True
    try:
        return abs(float(pred) - float(gold)) < 1e-6
    except (ValueError, TypeError):
        return False


@torch.no_grad()
def generate_answers(
    model: Any,
    tokenizer: Any,
    questions: list[str],
    mlp: Any,
    layer: int,
    device: torch.device,
    batch_size: int,
    max_new_tokens: int,
) -> list[str]:
    model.model.layers[layer].mlp = mlp  # type: ignore[attr-defined]
    outputs: list[str] = []
    for start in range(0, len(questions), batch_size):
        batch = questions[start : start + batch_size]
        inputs = tokenizer(batch, return_tensors="pt", padding=True).to(device)
        generated = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
        new_tokens = generated[:, inputs["input_ids"].shape[1] :]
        outputs.extend(tokenizer.batch_decode(new_tokens, skip_special_tokens=True))
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--layer", type=int, required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--gsm8k-file", required=True)
    parser.add_argument("--suite-split-manifest", required=True)
    parser.add_argument("--seq", type=int, default=256)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--num-items", type=int, default=0, help="0 = all items")
    parser.add_argument("--max-predicted-delta", type=float, default=-0.20)
    parser.add_argument("--budget", type=float, default=0.10)
    parser.add_argument("--random-fraction", type=float, default=0.02)
    parser.add_argument("--router-seed", type=int, default=0)
    parser.add_argument("--ridge-l2", type=float, default=1.0)
    parser.add_argument("--dtype", choices=["auto", "fp16", "bf16", "fp32"], default="fp32")
    parser.add_argument("--out-json", required=True)
    args = parser.parse_args()

    from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore

    device = setup_device()
    dtype = dtype_from_name(args.dtype, device)
    model_dtype = dtype if device.type in {"npu", "cuda"} else torch.float32
    tokenizer = AutoTokenizer.from_pretrained(args.model_dir, trust_remote_code=True)
    tokenizer.padding_side = "left"
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

    items = parse_gsm8k(Path(args.gsm8k_file))
    if args.num_items > 0:
        items = items[: args.num_items]
    questions = [f"{q}\n" for q, _ in items]
    golds = [a for _, a in items]
    print(json.dumps({"event": "gsm8k_loaded", "n_items": len(items)}), flush=True)

    # Fit the learned router exactly as in the tighter-eligibility sweep.
    train_pool, train_label_pool, _ = load_suite_split_manifest(Path(args.suite_split_manifest), "train_texts")
    eval_pool, eval_label_pool, _ = load_suite_split_manifest(Path(args.suite_split_manifest), "eval_texts")
    train_pool, train_label_pool, overlap_removed = remove_text_overlap(train_pool, train_label_pool, eval_pool)
    if overlap_removed:
        raise SystemExit(f"suite split manifest has {overlap_removed} train/eval overlaps; refusing leakage-prone run")
    train_texts, train_suite_labels = select_suite_balanced_labeled_texts(train_pool, train_label_pool, 0, args.router_seed)
    if not train_texts:
        raise SystemExit("no router train texts loaded from the manifest")

    collect_args = argparse.Namespace(layer=args.layer, seq=args.seq, dtype=args.dtype)
    print(json.dumps({"event": "router_fit_collect", "n_train_texts": len(train_texts)}), flush=True)
    train = collect_token_rows(
        "train", train_texts, train_suite_labels, model, tokenizer, collect_args,
        dense_mlp, patched_mlp, device,
    )
    weights = suite_balanced_weights(train["suite_ids"])
    router = fit_weighted_ridge(train["features"], train["delta_loss"], args.ridge_l2, weights)
    router["suite_balanced_ridge"] = True
    train_scores = predict_features(train["features"], router).cpu()
    threshold_row = threshold_for_risk_budget(
        train_scores, train["suite_ids"], args.max_predicted_delta, args.budget, "global"
    )
    threshold = float(threshold_row["threshold"])
    print(json.dumps({"event": "router_fit_done", "threshold": threshold}), flush=True)

    selective_mlp = TokenRouterMLP(dense_mlp, patched_mlp, router, threshold)
    random_mlp = RandomTokenMLP(dense_mlp, patched_mlp, args.random_fraction, args.router_seed)

    arms: list[tuple[str, Any]] = [
        ("dense", dense_mlp),
        ("selective", selective_mlp),
        ("random", random_mlp),
    ]

    result: dict[str, Any] = {
        "run": "gsm8k_em_eval",
        "layer": args.layer,
        "checkpoint": args.checkpoint,
        "gsm8k_file": args.gsm8k_file,
        "n_items": len(items),
        "max_new_tokens": args.max_new_tokens,
        "max_predicted_delta": args.max_predicted_delta,
        "budget": args.budget,
        "router_seed": args.router_seed,
        "random_fraction": args.random_fraction,
        "threshold": threshold,
        "arms": {},
    }
    for arm_name, mlp in arms:
        print(json.dumps({"event": "arm_start", "arm": arm_name}), flush=True)
        generations = generate_answers(
            model, tokenizer, questions, mlp, args.layer, device, args.batch_size, args.max_new_tokens
        )
        correct = 0
        per_item: list[dict[str, Any]] = []
        for question, gold, generation in zip(questions, golds, generations):
            prediction = extract_final_answer(generation)
            ok = exact_match(prediction, gold)
            correct += int(ok)
            per_item.append({
                "question": question[:200],
                "gold": gold,
                "prediction": prediction,
                "generation_tail": generation[-200:],
                "exact_match": ok,
            })
        score = correct / max(len(items), 1)
        result["arms"][arm_name] = {"exact_match": score, "n_correct": correct, "n_items": len(items), "per_item": per_item}
        print(json.dumps({"event": "arm_done", "arm": arm_name, "exact_match": score}), flush=True)

    out = Path(args.out_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"event": "saved", "json": str(out)}), flush=True)


if __name__ == "__main__":
    main()
