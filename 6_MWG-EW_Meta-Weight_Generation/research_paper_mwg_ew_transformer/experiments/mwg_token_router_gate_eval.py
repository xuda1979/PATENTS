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

try:
    import torch_npu  # type: ignore

    if hasattr(torch, "npu") and torch.npu.is_available():
        try:
            torch.serialization.add_safe_globals(
                [
                    torch_npu.utils.storage._rebuild_npu_tensor,
                    torch_npu.npu._format.Format,
                ]
            )
        except Exception:
            pass
except Exception:
    pass

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


def select_labeled_texts(
    texts: list[str],
    labels: list[str],
    count: int,
    seed: int,
) -> tuple[list[str], list[str]]:
    if len(texts) != len(labels):
        raise ValueError("texts and labels must have the same length")
    if count <= 0:
        return texts, labels
    indices = [index % len(texts) for index in range(count)]
    rng = random.Random(seed)
    rng.shuffle(indices)
    return [texts[index] for index in indices], [labels[index] for index in indices]


def select_suite_balanced_labeled_texts(
    texts: list[str],
    labels: list[str],
    count: int,
    seed: int,
) -> tuple[list[str], list[str]]:
    if len(texts) != len(labels):
        raise ValueError("texts and labels must have the same length")
    if count <= 0:
        return texts, labels
    by_label: dict[str, list[str]] = {}
    for text, label in zip(texts, labels):
        by_label.setdefault(label, []).append(text)
    rng = random.Random(seed)
    for bucket in by_label.values():
        rng.shuffle(bucket)
    ordered_labels = sorted(by_label)
    selected_texts: list[str] = []
    selected_labels: list[str] = []
    for index in range(count):
        label = ordered_labels[index % len(ordered_labels)]
        bucket = by_label[label]
        selected_texts.append(bucket[(index // len(ordered_labels)) % len(bucket)])
        selected_labels.append(label)
    order = list(range(len(selected_texts)))
    rng.shuffle(order)
    return [selected_texts[index] for index in order], [selected_labels[index] for index in order]


def read_lines(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_suite_split_manifest(path: Path, key: str) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    texts: list[str] = []
    labels: list[str] = []
    sources = []
    for suite in payload.get("suites", []):
        source = suite.get(key)
        if not source:
            continue
        suite_texts = read_lines(Path(source))
        texts.extend(suite_texts)
        labels.extend([str(suite["name"])] * len(suite_texts))
        sources.append({"suite": suite["name"], "key": key, "path": source, "count": len(suite_texts)})
    if not texts:
        raise ValueError(f"no texts loaded from {path} using key {key!r}")
    return texts, labels, sources


def remove_text_overlap(
    train_texts: list[str],
    train_labels: list[str],
    eval_texts: list[str],
) -> tuple[list[str], list[str], int]:
    eval_set = set(eval_texts)
    kept_texts: list[str] = []
    kept_labels: list[str] = []
    removed = 0
    for text, label in zip(train_texts, train_labels):
        if text in eval_set:
            removed += 1
            continue
        kept_texts.append(text)
        kept_labels.append(label)
    return kept_texts, kept_labels, removed


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
    suite_labels: list[str],
    model: nn.Module,
    tokenizer: Any,
    args: argparse.Namespace,
    dense_mlp: nn.Module,
    patched_mlp: nn.Module,
    device: torch.device,
) -> dict[str, Any]:
    feature_blocks: list[torch.Tensor] = []
    delta_blocks: list[torch.Tensor] = []
    suite_ids: list[str] = []
    suite_summary: dict[str, dict[str, Any]] = {}
    dense_loss_sum = 0.0
    patched_loss_sum = 0.0
    token_count = 0
    positive_delta = 0

    for index, text in enumerate(texts):
        suite_id = suite_labels[index] if index < len(suite_labels) else "unknown"
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
        suite_ids.extend([suite_id] * int(delta.numel()))
        dense_loss_sum += float(dense_valid.sum().item())
        patched_loss_sum += float(patched_valid.sum().item())
        token_count += int(delta.numel())
        positive_delta += int(delta.gt(0).sum().item())
        suite_row = suite_summary.setdefault(
            suite_id,
            {"examples": 0, "tokens": 0, "dense_loss_sum": 0.0, "patched_loss_sum": 0.0, "positive_delta": 0},
        )
        suite_row["examples"] += 1
        suite_row["tokens"] += int(delta.numel())
        suite_row["dense_loss_sum"] += float(dense_valid.sum().item())
        suite_row["patched_loss_sum"] += float(patched_valid.sum().item())
        suite_row["positive_delta"] += int(delta.gt(0).sum().item())

        if index == 0 or (index + 1) % 25 == 0:
            print(
                json.dumps(
                    {
                        "event": "token_router_collect",
                        "split": split,
                        "index": index + 1,
                        "suite": suite_id,
                        "tokens": int(delta.numel()),
                        "mean_delta": float(delta.mean().item()) if delta.numel() else 0.0,
                    }
                ),
                flush=True,
            )

    x = torch.cat(feature_blocks, dim=0) if feature_blocks else torch.empty(0, len(FEATURE_NAMES))
    y = torch.cat(delta_blocks, dim=0) if delta_blocks else torch.empty(0)
    suite_metrics = {}
    for suite_id, row in suite_summary.items():
        tokens = max(int(row["tokens"]), 1)
        dense_loss = float(row["dense_loss_sum"]) / tokens
        patched_loss = float(row["patched_loss_sum"]) / tokens
        suite_metrics[suite_id] = {
            "examples": row["examples"],
            "tokens": row["tokens"],
            "dense_loss": dense_loss,
            "patched_loss": patched_loss,
            "patched_ppl_ratio": math.exp(min(20.0, patched_loss)) / math.exp(min(20.0, dense_loss)),
            "positive_delta_fraction": float(row["positive_delta"]) / tokens,
        }
    return {
        "features": x,
        "delta_loss": y,
        "suite_ids": suite_ids,
        "summary": {
            "split": split,
            "examples": len(texts),
            "tokens": token_count,
            "dense_loss": dense_loss_sum / max(token_count, 1),
            "patched_loss": patched_loss_sum / max(token_count, 1),
            "patched_ppl_ratio": math.exp(min(20.0, patched_loss_sum / max(token_count, 1)))
            / math.exp(min(20.0, dense_loss_sum / max(token_count, 1))),
            "positive_delta_fraction": positive_delta / max(token_count, 1),
            "suite_metrics": suite_metrics,
        },
    }


def fit_ridge(features: torch.Tensor, delta: torch.Tensor, l2: float) -> dict[str, Any]:
    return fit_weighted_ridge(features, delta, l2, weights=None)


def fit_weighted_ridge(
    features: torch.Tensor,
    delta: torch.Tensor,
    l2: float,
    weights: torch.Tensor | None,
) -> dict[str, Any]:
    x = features.to(dtype=torch.float64)
    y = delta.to(dtype=torch.float64).view(-1, 1)
    if weights is None:
        weights64 = torch.ones(x.shape[0], dtype=torch.float64)
    else:
        weights64 = weights.to(dtype=torch.float64).view(-1).clamp_min(0.0)
        if weights64.numel() != x.shape[0]:
            raise ValueError("weights must match feature rows")
        if float(weights64.sum().item()) <= 0:
            raise ValueError("weights must have positive sum")
    weights64 = weights64 * (weights64.numel() / weights64.sum().clamp_min(1e-12))
    weight_col = weights64.view(-1, 1)
    mean = (x * weight_col).sum(dim=0, keepdim=True) / weight_col.sum().clamp_min(1e-12)
    variance = ((x - mean).square() * weight_col).sum(dim=0, keepdim=True) / weight_col.sum().clamp_min(1e-12)
    std = torch.sqrt(variance).clamp_min(1e-6)
    z = (x - mean) / std
    design = torch.cat([torch.ones(z.shape[0], 1, dtype=z.dtype), z], dim=1)
    penalty = torch.eye(design.shape[1], dtype=z.dtype) * l2
    penalty[0, 0] = 0.0
    weighted_design = design * torch.sqrt(weight_col)
    weighted_y = y * torch.sqrt(weight_col)
    coef = torch.linalg.solve(weighted_design.T @ weighted_design + penalty, weighted_design.T @ weighted_y).view(-1)
    pred = (design @ coef.view(-1, 1)).view(-1)
    weighted_mse = torch.sum(weights64 * (pred - y.view(-1)).square()) / weights64.sum().clamp_min(1e-12)
    return {
        "mean": mean.view(-1).tolist(),
        "std": std.view(-1).tolist(),
        "coef": coef.tolist(),
        "train_mse": float(torch.mean((pred - y.view(-1)).square()).item()),
        "train_weighted_mse": float(weighted_mse.item()),
        "train_corr": float(torch.corrcoef(torch.stack([pred.float(), y.view(-1).float()]))[0, 1].item())
        if pred.numel() > 1
        else 0.0,
    }


def suite_balanced_weights(suite_ids: list[str]) -> torch.Tensor:
    counts: dict[str, int] = {}
    for suite_id in suite_ids:
        counts[suite_id] = counts.get(suite_id, 0) + 1
    if not counts:
        return torch.empty(0)
    total = len(suite_ids)
    num_suites = len(counts)
    return torch.tensor([total / (num_suites * counts[suite_id]) for suite_id in suite_ids], dtype=torch.float32)


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


def threshold_for_fraction(
    scores: torch.Tensor,
    suite_ids: list[str],
    fraction: float,
    policy: str,
) -> dict[str, Any]:
    global_threshold = quantile(scores, fraction)
    if policy == "global" or not suite_ids:
        return {
            "threshold": global_threshold,
            "policy": "global",
            "global_threshold": global_threshold,
            "suite_thresholds": {},
        }
    if len(suite_ids) != int(scores.numel()):
        raise ValueError("suite_ids must match score rows for suite threshold policy")
    suite_thresholds = {}
    for suite_id in sorted(set(suite_ids)):
        mask = torch.tensor([item == suite_id for item in suite_ids], dtype=torch.bool)
        suite_thresholds[suite_id] = quantile(scores[mask], fraction)
    values = list(suite_thresholds.values())
    if not values:
        threshold = global_threshold
    elif policy == "suite_min":
        threshold = min(values)
    elif policy == "suite_mean":
        threshold = sum(values) / len(values)
    elif policy == "suite_median":
        ordered = sorted(values)
        threshold = ordered[len(ordered) // 2]
    elif policy == "suite_local":
        threshold = global_threshold
    else:
        raise ValueError(f"unknown threshold policy: {policy}")
    return {
        "threshold": float(threshold),
        "policy": policy,
        "global_threshold": global_threshold,
        "suite_thresholds": suite_thresholds,
    }


def threshold_for_risk_budget(
    predicted_delta: torch.Tensor,
    suite_ids: list[str],
    max_predicted_delta: float,
    max_patch_fraction: float,
    policy: str,
) -> dict[str, Any]:
    if not 0.0 <= max_patch_fraction <= 1.0:
        raise ValueError("max_patch_fraction must be in [0, 1]")
    if policy != "global" and suite_ids and len(suite_ids) != int(predicted_delta.numel()):
        raise ValueError("suite_ids must match score rows for suite risk policy")

    scores = predicted_delta.float()

    def choose_threshold(values: torch.Tensor) -> float:
        allowed = values[values.le(float(max_predicted_delta))]
        if allowed.numel() == 0 or max_patch_fraction <= 0.0:
            return float("-inf")
        allowed_count = max(1, int(math.floor(values.numel() * max_patch_fraction)))
        allowed_count = min(allowed_count, int(allowed.numel()))
        ordered = torch.sort(allowed).values
        return float(ordered[allowed_count - 1].item())

    global_threshold = choose_threshold(scores)
    if policy == "global" or not suite_ids:
        return {
            "threshold": global_threshold,
            "policy": "risk_global",
            "global_threshold": global_threshold,
            "suite_thresholds": {},
            "max_predicted_delta": float(max_predicted_delta),
            "max_patch_fraction": float(max_patch_fraction),
        }

    suite_thresholds = {}
    for suite_id in sorted(set(suite_ids)):
        mask = torch.tensor([item == suite_id for item in suite_ids], dtype=torch.bool)
        suite_thresholds[suite_id] = choose_threshold(scores[mask])
    finite = [value for value in suite_thresholds.values() if math.isfinite(value)]
    if not finite:
        threshold = float("-inf")
    elif policy == "suite_min":
        threshold = min(finite)
    elif policy == "suite_mean":
        threshold = sum(finite) / len(finite)
    elif policy == "suite_median":
        ordered = sorted(finite)
        threshold = ordered[len(ordered) // 2]
    elif policy == "suite_local":
        # suite_local applies per-suite thresholds at evaluation time via
        # thresholds_by_example; the summary threshold is the strictest
        # (min) so that the scalar `threshold` field remains informative.
        threshold = min(finite)
    else:
        threshold = min(finite)
    return {
        "threshold": threshold,
        "policy": "risk_suite_local" if policy == "suite_local" else f"risk_{policy}",
        "global_threshold": global_threshold,
        "suite_thresholds": suite_thresholds,
        "max_predicted_delta": float(max_predicted_delta),
        "max_patch_fraction": float(max_patch_fraction),
    }


def threshold_for_joint_budget(
    predicted_delta: torch.Tensor,
    suite_ids: list[str],
    max_predicted_delta: float,
    target_fraction: float,
    policy: str,
) -> dict[str, Any]:
    if not 0.0 <= target_fraction <= 1.0:
        raise ValueError("target_fraction must be in [0, 1]")
    if policy != "global" and suite_ids and len(suite_ids) != int(predicted_delta.numel()):
        raise ValueError("suite_ids must match score rows for suite joint budget policy")

    scores = predicted_delta.float()
    masked_scores = scores.clone()
    masked_scores[masked_scores.gt(float(max_predicted_delta))] = float("inf")
    base_policy = "global" if policy == "global" else policy
    row = threshold_for_fraction(masked_scores, suite_ids, target_fraction, base_policy)
    row["policy"] = "joint_global" if policy == "global" or not suite_ids else f"joint_{policy}"
    row["max_predicted_delta"] = float(max_predicted_delta)
    row["target_patch_fraction"] = float(target_fraction)
    return row


class TokenRouterMLP(nn.Module):
    def __init__(
        self,
        dense_mlp: nn.Module,
        patched_mlp: nn.Module,
        router: dict[str, Any],
        threshold: float,
        thresholds_by_example: list[float] | None = None,
    ):
        super().__init__()
        self.dense_mlp = dense_mlp
        self.patched_mlp = patched_mlp
        self.router = router
        self.threshold = threshold
        self.thresholds_by_example = thresholds_by_example or []
        self.example_index = 0
        self.last_patch_tokens = 0
        self.last_total_tokens = 0

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        scores = predict_features(token_features(x, torch.ones(x.shape[:2], device=x.device, dtype=torch.long)), self.router)
        if self.thresholds_by_example:
            count = scores.shape[0]
            values = self.thresholds_by_example[self.example_index : self.example_index + count]
            if len(values) != count:
                raise RuntimeError("not enough per-example router thresholds for this forward pass")
            threshold = torch.tensor(values, dtype=scores.dtype, device=scores.device).view(count, 1)
            self.example_index += count
        else:
            threshold = torch.tensor(float(self.threshold), dtype=scores.dtype, device=scores.device)
        use_patch = scores.le(threshold).unsqueeze(-1)
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
    router_mlp.example_index = 0
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
    parser.add_argument("--suite-split-manifest", default="")
    parser.add_argument("--suite-train-key", default="train_texts")
    parser.add_argument("--suite-eval-key", default="eval_texts")
    parser.add_argument("--suite-balanced-sampling", action="store_true")
    parser.add_argument("--suite-balanced-ridge", action="store_true")
    parser.add_argument("--fail-on-suite-overlap", action="store_true")
    parser.add_argument("--require-texts", action="store_true")
    parser.add_argument("--seq", type=int, default=256)
    parser.add_argument("--train-examples", type=int, default=256)
    parser.add_argument("--eval-examples", type=int, default=256)
    parser.add_argument("--fractions", type=parse_fractions, default=[0.10, 0.25, 0.50])
    parser.add_argument("--risk-budgets", type=parse_fractions, default=[])
    parser.add_argument("--joint-budgets", type=parse_fractions, default=[])
    parser.add_argument(
        "--risk-max-predicted-delta",
        type=float,
        default=0.0,
        help=(
            "If --risk-budgets is set, patch only train tokens whose predicted "
            "patched-minus-dense loss is at most this value, additionally capped "
            "by the requested maximum patch fraction."
        ),
    )
    parser.add_argument(
        "--threshold-policy",
        choices=["global", "suite_min", "suite_mean", "suite_median", "suite_local"],
        default="global",
        help=(
            "Choose how target patch-fraction thresholds are set from train scores. "
            "suite_min is conservative for suite-balanced manifests because it only "
            "patches tokens below the strictest per-suite train quantile. suite_local "
            "uses each eval example's suite threshold, preserving the target fraction "
            "within suites instead of one global threshold."
        ),
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--ridge-l2", type=float, default=1.0)
    parser.add_argument("--dtype", choices=["auto", "fp16", "bf16", "fp32"], default="auto")
    parser.add_argument("--out-json", required=True)
    args = parser.parse_args()

    from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore

    if args.require_texts and not args.suite_split_manifest and (not args.train_texts or not args.eval_texts):
        raise SystemExit("explicit --train-texts/--eval-texts or --suite-split-manifest are required; refusing DEFAULT_TEXTS fallback")

    train_sources: list[dict[str, Any]] = []
    eval_sources: list[dict[str, Any]] = []
    if args.suite_split_manifest:
        train_pool, train_label_pool, train_sources = load_suite_split_manifest(
            Path(args.suite_split_manifest), args.suite_train_key
        )
        eval_pool, eval_label_pool, eval_sources = load_suite_split_manifest(
            Path(args.suite_split_manifest), args.suite_eval_key
        )
        train_pool, train_label_pool, overlap_removed = remove_text_overlap(train_pool, train_label_pool, eval_pool)
        if args.fail_on_suite_overlap and overlap_removed:
            raise SystemExit(f"suite split manifest has {overlap_removed} train/eval overlaps")
        if overlap_removed:
            train_sources.append(
                {
                    "suite": "__all__",
                    "key": args.suite_train_key,
                    "path": args.suite_split_manifest,
                    "overlap_removed_against_eval_union": overlap_removed,
                }
            )
        if not train_pool:
            raise SystemExit(
                "suite split manifest has no train texts after removing the eval union; "
                "use per-suite runs or prepare a global leakage-clean split"
            )
        selector = select_suite_balanced_labeled_texts if args.suite_balanced_sampling else select_labeled_texts
        train_texts, train_suite_labels = selector(train_pool, train_label_pool, args.train_examples, args.seed)
        eval_texts, eval_suite_labels = selector(eval_pool, eval_label_pool, args.eval_examples, args.seed + 1009)
    else:
        train_texts = select_texts(args.train_texts or DEFAULT_TEXTS, args.train_examples, args.seed)
        eval_texts = select_texts(args.eval_texts or DEFAULT_TEXTS, args.eval_examples, args.seed + 1009)
        train_suite_labels = ["explicit_train"] * len(train_texts)
        eval_suite_labels = ["explicit_eval"] * len(eval_texts)

    if args.require_texts and (not train_texts or not eval_texts):
        raise SystemExit("explicit train/eval texts are required; refusing DEFAULT_TEXTS fallback")
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

    train = collect_token_rows(
        "train",
        train_texts,
        train_suite_labels,
        model,
        tokenizer,
        args,
        dense_mlp,
        patched_mlp,
        device,
    )
    eval_rows = collect_token_rows(
        "eval",
        eval_texts,
        eval_suite_labels,
        model,
        tokenizer,
        args,
        dense_mlp,
        patched_mlp,
        device,
    )
    train_weights = suite_balanced_weights(train["suite_ids"]) if args.suite_balanced_ridge else None
    router = fit_weighted_ridge(train["features"], train["delta_loss"], args.ridge_l2, train_weights)
    router["suite_balanced_ridge"] = bool(args.suite_balanced_ridge)
    if args.suite_balanced_ridge:
        router["suite_weight_summary"] = train["summary"]["suite_metrics"]
    train_scores = predict_features(train["features"], router).cpu()

    dense_loss = float(eval_rows["summary"]["dense_loss"])
    dense_ppl = math.exp(min(20.0, dense_loss))
    frontier: list[dict[str, float]] = []
    budget_rows: list[tuple[float, dict[str, Any]]] = []
    if args.risk_budgets and args.joint_budgets:
        raise SystemExit("use either --risk-budgets or --joint-budgets, not both")
    if args.risk_budgets:
        for fraction in args.risk_budgets:
            budget_rows.append(
                (
                    fraction,
                    threshold_for_risk_budget(
                        train_scores,
                        train["suite_ids"],
                        args.risk_max_predicted_delta,
                        fraction,
                        args.threshold_policy,
                    ),
                )
            )
    elif args.joint_budgets:
        for fraction in args.joint_budgets:
            budget_rows.append(
                (
                    fraction,
                    threshold_for_joint_budget(
                        train_scores,
                        train["suite_ids"],
                        args.risk_max_predicted_delta,
                        fraction,
                        args.threshold_policy,
                    ),
                )
            )
    else:
        for fraction in args.fractions:
            budget_rows.append((fraction, threshold_for_fraction(train_scores, train["suite_ids"], fraction, args.threshold_policy)))

    for fraction, threshold_row in budget_rows:
        threshold = float(threshold_row["threshold"])
        thresholds_by_example = None
        if args.threshold_policy == "suite_local":
            suite_thresholds = threshold_row.get("suite_thresholds", {})
            missing_suites = sorted(set(eval_suite_labels) - set(suite_thresholds))
            if missing_suites:
                raise SystemExit(f"suite_local threshold policy has no train threshold for eval suites: {missing_suites}")
            thresholds_by_example = [float(suite_thresholds[label]) for label in eval_suite_labels]
        mixed_mlp = TokenRouterMLP(dense_mlp, patched_mlp, router, threshold, thresholds_by_example)
        mixed = evaluate_mixed(model, tokenizer, eval_texts, args, device, mixed_mlp)
        mixed["target_patch_fraction"] = fraction
        mixed["train_score_threshold"] = threshold
        mixed["threshold_policy"] = args.threshold_policy
        mixed["threshold_details"] = threshold_row
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
        "suite_sources": {"train": train_sources, "eval": eval_sources},
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
