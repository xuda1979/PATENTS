"""Token-level dense-fallback router for a patched MWG FFN layer.

This is stricter than the earlier example-level router: it trains on token CE
deltas from a separate split, then evaluates actual mixed dense/patch forward
passes on held-out text. The router features are computed from the FFN input,
so they are available before the target FFN executes.
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
import torch.nn.functional as F

from mwg_ppl_patch_eval import PatchedMLP, load_student, setup_device, sync_device
from mwg_quality_distillation import DEFAULT_TEXTS, dtype_from_name, parse_texts


FEATURE_NAMES = [
    "position",
    "fill_ratio",
    "hidden_mean",
    "hidden_std",
    "hidden_rms",
    "hidden_abs_mean",
    "hidden_abs_max",
    "hidden_abs_q95",
    "hidden_l2",
]


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


def token_features(hidden: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    values = hidden.detach().float()
    batch, seq, _dim = values.shape
    abs_values = values.abs()
    positions = torch.arange(seq, device=values.device, dtype=torch.float32).view(1, seq, 1)
    position = positions / max(seq - 1, 1)
    fill_ratio = attention_mask.float().sum(dim=1, keepdim=True).view(batch, 1, 1) / max(seq, 1)
    fill_ratio = fill_ratio.expand(batch, seq, 1)
    mean = values.mean(dim=-1, keepdim=True)
    std = values.std(dim=-1, unbiased=False, keepdim=True)
    rms = torch.sqrt(values.square().mean(dim=-1, keepdim=True).clamp_min(1e-12))
    abs_mean = abs_values.mean(dim=-1, keepdim=True)
    abs_max = abs_values.max(dim=-1, keepdim=True).values
    abs_q95 = torch.quantile(abs_values, 0.95, dim=-1, keepdim=True)
    l2 = torch.linalg.vector_norm(values, dim=-1, keepdim=True) / math.sqrt(max(values.shape[-1], 1))
    return torch.cat([position.expand(batch, -1, -1), fill_ratio, mean, std, rms, abs_mean, abs_max, abs_q95, l2], dim=-1)


def token_nll(logits: torch.Tensor, labels: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    shift_logits = logits[:, :-1, :].contiguous()
    shift_labels = labels[:, 1:].contiguous()
    flat_loss = F.cross_entropy(
        shift_logits.view(-1, shift_logits.shape[-1]),
        shift_labels.view(-1),
        ignore_index=-100,
        reduction="none",
    )
    losses = flat_loss.view_as(shift_labels)
    mask = shift_labels.ne(-100)
    return losses, mask


@torch.no_grad()
def collect_token_rows(
    split: str,
    texts: list[str],
    model: nn.Module,
    tokenizer: Any,
    args: argparse.Namespace,
    dense_mlp: nn.Module,
    patched_mlp: nn.Module,
    device: torch.device,
) -> dict[str, Any]:
    feature_blocks: list[torch.Tensor] = []
    delta_blocks: list[torch.Tensor] = []
    dense_loss_sum = 0.0
    patched_loss_sum = 0.0
    token_count = 0
    positive_delta = 0

    for index, text in enumerate(texts):
        encoded = encode(tokenizer, text, args.seq, device)
        labels = labels_from(encoded)
        captured: list[torch.Tensor] = []

        def capture(_module: nn.Module, inputs: tuple[torch.Tensor, ...]) -> None:
            captured.append(inputs[0].detach())

        model.model.layers[args.layer].mlp = dense_mlp  # type: ignore[attr-defined]
        handle = dense_mlp.register_forward_pre_hook(capture)
        try:
            dense_output = model(**encoded)
        finally:
            handle.remove()
        if not captured:
            raise RuntimeError(f"failed to capture layer {args.layer} FFN input")

        model.model.layers[args.layer].mlp = patched_mlp  # type: ignore[attr-defined]
        patched_output = model(**encoded)

        dense_losses, mask = token_nll(dense_output.logits, labels)
        patched_losses, _ = token_nll(patched_output.logits, labels)
        features = token_features(captured[0], encoded["attention_mask"])[:, :-1, :]
        flat_mask = mask.reshape(-1)
        flat_features = features.reshape(-1, features.shape[-1])[flat_mask].cpu()
        dense_valid = dense_losses.reshape(-1)[flat_mask].detach().float().cpu()
        patched_valid = patched_losses.reshape(-1)[flat_mask].detach().float().cpu()
        delta = patched_valid - dense_valid

        feature_blocks.append(flat_features)
        delta_blocks.append(delta)
        dense_loss_sum += float(dense_valid.sum().item())
        patched_loss_sum += float(patched_valid.sum().item())
        token_count += int(delta.numel())
        positive_delta += int(delta.gt(0).sum().item())

        if index == 0 or (index + 1) % 25 == 0:
            print(
                json.dumps(
                    {
                        "event": "token_router_collect",
                        "split": split,
                        "index": index + 1,
                        "tokens": int(delta.numel()),
                        "mean_delta": float(delta.mean().item()) if delta.numel() else 0.0,
                    }
                ),
                flush=True,
            )

    x = torch.cat(feature_blocks, dim=0) if feature_blocks else torch.empty(0, len(FEATURE_NAMES))
    y = torch.cat(delta_blocks, dim=0) if delta_blocks else torch.empty(0)
    return {
        "features": x,
        "delta_loss": y,
        "summary": {
            "split": split,
            "examples": len(texts),
            "tokens": token_count,
            "dense_loss": dense_loss_sum / max(token_count, 1),
            "patched_loss": patched_loss_sum / max(token_count, 1),
            "patched_ppl_ratio": math.exp(min(20.0, patched_loss_sum / max(token_count, 1)))
            / math.exp(min(20.0, dense_loss_sum / max(token_count, 1))),
            "positive_delta_fraction": positive_delta / max(token_count, 1),
        },
    }


def fit_ridge(features: torch.Tensor, delta: torch.Tensor, l2: float) -> dict[str, Any]:
    x = features.to(dtype=torch.float64)
    y = delta.to(dtype=torch.float64).view(-1, 1)
    mean = x.mean(dim=0, keepdim=True)
    std = x.std(dim=0, unbiased=False, keepdim=True).clamp_min(1e-6)
    z = (x - mean) / std
    design = torch.cat([torch.ones(z.shape[0], 1, dtype=z.dtype), z], dim=1)
    penalty = torch.eye(design.shape[1], dtype=z.dtype) * l2
    penalty[0, 0] = 0.0
    coef = torch.linalg.solve(design.T @ design + penalty, design.T @ y).view(-1)
    pred = (design @ coef.view(-1, 1)).view(-1)
    return {
        "mean": mean.view(-1).tolist(),
        "std": std.view(-1).tolist(),
        "coef": coef.tolist(),
        "train_mse": float(torch.mean((pred - y.view(-1)).square()).item()),
        "train_corr": float(torch.corrcoef(torch.stack([pred.float(), y.view(-1).float()]))[0, 1].item())
        if pred.numel() > 1
        else 0.0,
    }


def predict_features(features: torch.Tensor, router: dict[str, Any]) -> torch.Tensor:
    device = features.device
    mean = torch.tensor(router["mean"], dtype=torch.float32, device=device)
    std = torch.tensor(router["std"], dtype=torch.float32, device=device)
    coef = torch.tensor(router["coef"], dtype=torch.float32, device=device)
    z = (features.float() - mean) / std
    return coef[0] + (z * coef[1:]).sum(dim=-1)


def quantile(values: torch.Tensor, fraction: float) -> float:
    if values.numel() == 0:
        return 0.0
    ordered = torch.sort(values.float()).values
    index = min(ordered.numel() - 1, max(0, math.ceil(ordered.numel() * fraction) - 1))
    return float(ordered[index].item())


class TokenRouterMLP(nn.Module):
    def __init__(self, dense_mlp: nn.Module, patched_mlp: nn.Module, router: dict[str, Any], threshold: float):
        super().__init__()
        self.dense_mlp = dense_mlp
        self.patched_mlp = patched_mlp
        self.router = router
        self.threshold = threshold
        self.last_patch_tokens = 0
        self.last_total_tokens = 0

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        scores = predict_features(token_features(x, torch.ones(x.shape[:2], device=x.device, dtype=torch.long)), self.router)
        use_patch = scores.le(self.threshold).unsqueeze(-1)
        self.last_patch_tokens += int(use_patch.sum().item())
        self.last_total_tokens += int(use_patch.numel())
        return torch.where(use_patch, self.patched_mlp(x), self.dense_mlp(x))


@torch.no_grad()
def evaluate_mixed(
    model: nn.Module,
    tokenizer: Any,
    texts: list[str],
    args: argparse.Namespace,
    device: torch.device,
    router_mlp: TokenRouterMLP,
) -> dict[str, float]:
    loss_sum = 0.0
    token_count = 0
    router_mlp.last_patch_tokens = 0
    router_mlp.last_total_tokens = 0
    model.model.layers[args.layer].mlp = router_mlp  # type: ignore[attr-defined]
    for text in texts:
        encoded = encode(tokenizer, text, args.seq, device)
        labels = labels_from(encoded)
        output = model(**encoded, labels=labels)
        valid = int(labels.ne(-100).sum().item())
        loss_sum += float(output.loss.item()) * valid
        token_count += valid
    loss = loss_sum / max(token_count, 1)
    return {
        "tokens": float(token_count),
        "loss": loss,
        "ppl": math.exp(min(20.0, loss)),
        "actual_patch_token_fraction": router_mlp.last_patch_tokens / max(router_mlp.last_total_tokens, 1),
    }


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
    parser.add_argument("--fractions", type=parse_fractions, default=[0.10, 0.25, 0.50])
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
        raise SystemExit("train/eval text overlap detected; refusing leakage-prone token-router evaluation")

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

    train = collect_token_rows("train", train_texts, model, tokenizer, args, dense_mlp, patched_mlp, device)
    eval_rows = collect_token_rows("eval", eval_texts, model, tokenizer, args, dense_mlp, patched_mlp, device)
    router = fit_ridge(train["features"], train["delta_loss"], args.ridge_l2)
    train_scores = predict_features(train["features"], router).cpu()

    dense_loss = float(eval_rows["summary"]["dense_loss"])
    dense_ppl = math.exp(min(20.0, dense_loss))
    frontier: list[dict[str, float]] = []
    for fraction in args.fractions:
        threshold = quantile(train_scores, fraction)
        mixed_mlp = TokenRouterMLP(dense_mlp, patched_mlp, router, threshold)
        mixed = evaluate_mixed(model, tokenizer, eval_texts, args, device, mixed_mlp)
        mixed["target_patch_fraction"] = fraction
        mixed["train_score_threshold"] = threshold
        mixed["delta_loss"] = mixed["loss"] - dense_loss
        mixed["ppl_ratio"] = mixed["ppl"] / dense_ppl
        frontier.append(mixed)

    model.model.layers[args.layer].mlp = dense_mlp  # type: ignore[attr-defined]
    sync_device()
    result = {
        "dense": {"loss": dense_loss, "ppl": dense_ppl, "tokens": eval_rows["summary"]["tokens"]},
        "patched": {
            "loss": eval_rows["summary"]["patched_loss"],
            "ppl": math.exp(min(20.0, float(eval_rows["summary"]["patched_loss"]))),
            "tokens": eval_rows["summary"]["tokens"],
            "ppl_ratio": eval_rows["summary"]["patched_ppl_ratio"],
        },
        "router": router,
        "mixed_frontier": frontier,
        "feature_names": FEATURE_NAMES,
        "train_summary": train["summary"],
        "eval_summary": eval_rows["summary"],
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
                "mixed_frontier": result["mixed_frontier"],
                "train_summary": result["train_summary"],
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
