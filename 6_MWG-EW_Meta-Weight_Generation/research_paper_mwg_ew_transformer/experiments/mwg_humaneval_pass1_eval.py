"""HumanEval pass@1 on the layer-16 selective regime.

Required downstream-accuracy probe: greedy single-sample pass@1 on the
canonical HumanEval problem set (164 problems, from the human_eval PyPI
wheel's HumanEval.jsonl.gz) for three arms sharing the same calibrated
layer-16 checkpoint: (a) always-dense, (b) selective learned router at the
tighter-eligibility operating point (Delta_max = -0.20, policy global,
budget 0.10), and (c) a random 2%-budget control. Router fitting matches
mwg_token_router_gate_eval.py (suite-balanced ridge, leakage-clean).
Completions are executed against the problem's canonical test harness in an
isolated subprocess with a timeout.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import subprocess
import sys
import textwrap
import zipfile
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

STOP_MARKERS = ["\nclass ", "\ndef ", "\n#", "\nif __name__", "\n```"]


def load_problems(wheel: Path) -> list[dict[str, Any]]:
    with zipfile.ZipFile(wheel) as archive:
        name = [n for n in archive.namelist() if n.endswith("HumanEval.jsonl.gz")][0]
        lines = gzip.decompress(archive.read(name)).decode().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def truncate_completion(completion: str) -> str:
    for marker in STOP_MARKERS:
        index = completion.find(marker)
        if index >= 0:
            completion = completion[:index]
    return completion


def run_tests(problem: dict[str, Any], completion: str) -> bool:
    code = problem["prompt"] + truncate_completion(completion)
    harness = textwrap.dedent(
        f"""
import sys
from io import StringIO

_capture = StringIO()
def check(candidate):
    global _last_candidate
    _last_candidate = candidate
"""
    ) + problem["test"] + f"\ncheck({problem['entry_point']})\n"
    full = code + "\n" + harness
    try:
        result = subprocess.run(
            [sys.executable, "-c", full],
            capture_output=True,
            timeout=20,
            cwd="/tmp",
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False


@torch.no_grad()
def generate_completions(
    model: Any,
    tokenizer: Any,
    prompts: list[str],
    mlp: Any,
    layer: int,
    device: torch.device,
    batch_size: int,
    max_new_tokens: int,
) -> list[str]:
    model.model.layers[layer].mlp = mlp  # type: ignore[attr-defined]
    outputs: list[str] = []
    for start in range(0, len(prompts), batch_size):
        batch = prompts[start : start + batch_size]
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
    parser.add_argument("--humaneval-wheel", required=True)
    parser.add_argument("--suite-split-manifest", required=True)
    parser.add_argument("--seq", type=int, default=256)
    parser.add_argument("--max-new-tokens", type=int, default=512)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--num-items", type=int, default=0, help="0 = all problems")
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

    problems = load_problems(Path(args.humaneval_wheel))
    if args.num_items > 0:
        problems = problems[: args.num_items]
    prompts = [problem["prompt"] for problem in problems]
    print(json.dumps({"event": "humaneval_loaded", "n_problems": len(problems)}), flush=True)

    train_pool, train_label_pool, _ = load_suite_split_manifest(Path(args.suite_split_manifest), "train_texts")
    eval_pool, eval_label_pool, _ = load_suite_split_manifest(Path(args.suite_split_manifest), "eval_texts")
    train_pool, train_label_pool, overlap_removed = remove_text_overlap(train_pool, train_label_pool, eval_pool)
    if overlap_removed:
        raise SystemExit(f"suite split manifest has {overlap_removed} train/eval overlaps; refusing leakage-prone run")
    train_texts, train_suite_labels = select_suite_balanced_labeled_texts(train_pool, train_label_pool, 0, args.router_seed)

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
    arms: list[tuple[str, Any]] = [("dense", dense_mlp), ("selective", selective_mlp), ("random", random_mlp)]

    result: dict[str, Any] = {
        "run": "humaneval_pass1_eval",
        "layer": args.layer,
        "checkpoint": args.checkpoint,
        "n_problems": len(problems),
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
        completions = generate_completions(
            model, tokenizer, prompts, mlp, args.layer, device, args.batch_size, args.max_new_tokens
        )
        passed = 0
        per_problem: list[dict[str, Any]] = []
        for problem, completion in zip(problems, completions):
            ok = run_tests(problem, completion)
            passed += int(ok)
            per_problem.append({
                "task_id": problem["task_id"],
                "entry_point": problem["entry_point"],
                "passed": ok,
                "completion_tail": completion[-150:],
            })
        score = passed / max(len(problems), 1)
        result["arms"][arm_name] = {"pass@1": score, "n_passed": passed, "n_problems": len(problems), "per_problem": per_problem}
        print(json.dumps({"event": "arm_done", "arm": arm_name, "pass@1": score}), flush=True)

    out = Path(args.out_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"event": "saved", "json": str(out)}), flush=True)


if __name__ == "__main__":
    main()
