"""Local probe for selective MWG residuals on attention K/V projections.

This script returns to the original MWG intuition: avoid using large projection
matrices blindly by replacing or patching K/V projections with compact generated
descriptors. It keeps Q and O dense, approximates K/V with trainable low-rank
factors, and tests whether a small token-budgeted MWG residual can recover
teacher attention outputs.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn

from mwg_quality_distillation import make_batch, parameter_bytes, svd_factors
from mwg_selective_residual_probe import LowRankCorrection, SelectiveResidualFFN

MIB = 1024**2


def now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_floats(value: str) -> list[float]:
    return [float(item.strip()) for item in value.split(",") if item.strip()]


@dataclass
class Metrics:
    mse: float
    relative_mse: float
    cosine: float
    actual_budget: float


def attention(q: torch.Tensor, k: torch.Tensor, v: torch.Tensor, o: torch.Tensor) -> torch.Tensor:
    scale = 1.0 / math.sqrt(q.shape[-1])
    weights = torch.softmax(torch.matmul(q, k.transpose(-1, -2)) * scale, dim=-1)
    return torch.matmul(weights, v) @ o


def make_teacher_weights(d: int, seed: int) -> dict[str, torch.Tensor]:
    gen = torch.Generator(device="cpu").manual_seed(seed)
    scale = 1.0 / math.sqrt(d)
    return {
        "q": torch.randn(d, d, generator=gen) * scale,
        "k": torch.randn(d, d, generator=gen) * scale,
        "v": torch.randn(d, d, generator=gen) * scale,
        "o": torch.randn(d, d, generator=gen) * scale,
    }


class DenseAttentionTeacher(nn.Module):
    def __init__(self, weights: dict[str, torch.Tensor]):
        super().__init__()
        for name, weight in weights.items():
            self.register_buffer(name, weight.float())

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return attention(x @ self.q, x @ self.k, x @ self.v, self.o)


class LowRankKVAttention(nn.Module):
    def __init__(self, weights: dict[str, torch.Tensor], rank: int):
        super().__init__()
        self.register_buffer("q", weights["q"].float())
        self.register_buffer("o", weights["o"].float())
        k_u, k_v, _ = svd_factors(weights["k"], rank)
        v_u, v_v, _ = svd_factors(weights["v"], rank)
        self.k_u = nn.Parameter(k_u.float())
        self.k_v = nn.Parameter(k_v.float())
        self.v_u = nn.Parameter(v_u.float())
        self.v_v = nn.Parameter(v_v.float())

    def project(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        q = x @ self.q
        k = (x @ self.k_u) @ self.k_v
        v = (x @ self.v_u) @ self.v_v
        return q, k, v

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        q, k, v = self.project(x)
        return attention(q, k, v, self.o)


class SelectiveKVResidualAttention(nn.Module):
    def __init__(
        self,
        base: LowRankKVAttention,
        d: int,
        residual_rank: int,
        router_hidden: int,
        patch: str,
        always_on: bool = False,
    ):
        super().__init__()
        if patch not in {"k", "v", "kv"}:
            raise ValueError(f"unknown patch target: {patch}")
        self.base = base
        self.patch = patch
        self.always_on = always_on
        for param in self.base.parameters():
            param.requires_grad_(False)
        self.k_residual = LowRankCorrection(d, d, residual_rank, torch.float32) if patch in {"k", "kv"} else None
        self.v_residual = LowRankCorrection(d, d, residual_rank, torch.float32) if patch in {"v", "kv"} else None
        if always_on:
            self.router = None
        else:
            self.router = nn.Sequential(
                nn.Linear(d, router_hidden, dtype=torch.float32),
                nn.SiLU(),
                nn.Linear(router_hidden, 1, dtype=torch.float32),
            )

    def route_logits(self, x: torch.Tensor) -> torch.Tensor:
        if self.router is None:
            return torch.ones(x.shape[:2], device=x.device, dtype=torch.float32)
        return self.router(x.float()).squeeze(-1)

    def _apply_residuals(self, x: torch.Tensor, gate: torch.Tensor) -> torch.Tensor:
        q, k, v = self.base.project(x)
        if self.k_residual is not None:
            k = k + gate.unsqueeze(-1) * self.k_residual(x)
        if self.v_residual is not None:
            v = v + gate.unsqueeze(-1) * self.v_residual(x)
        return attention(q, k, v, self.base.o)

    def base_output(self, x: torch.Tensor) -> torch.Tensor:
        return self.base(x)

    def full_output(self, x: torch.Tensor) -> torch.Tensor:
        gate = torch.ones(x.shape[:2], device=x.device, dtype=x.dtype)
        return self._apply_residuals(x, gate)

    def forward_soft(self, x: torch.Tensor, temperature: float) -> tuple[torch.Tensor, torch.Tensor]:
        if self.always_on:
            gate = torch.ones(x.shape[:2], device=x.device, dtype=x.dtype)
        else:
            gate = torch.sigmoid(self.route_logits(x) / temperature).to(dtype=x.dtype)
        return self._apply_residuals(x, gate), gate.float()

    @torch.no_grad()
    def forward_hard(self, x: torch.Tensor, budget: float) -> tuple[torch.Tensor, torch.Tensor]:
        if self.always_on:
            gate = torch.ones(x.shape[:2], device=x.device, dtype=x.dtype)
        else:
            gate = SelectiveResidualFFN.topk_mask(self.route_logits(x), budget).to(dtype=x.dtype)
        return self._apply_residuals(x, gate), gate.float()


def sample(args: argparse.Namespace, seed: int) -> torch.Tensor:
    return make_batch(args.batch, args.seq, args.d, torch.device("cpu"), torch.float32, seed)


def clone_base(base: LowRankKVAttention, weights: dict[str, torch.Tensor], rank: int) -> LowRankKVAttention:
    clone = LowRankKVAttention(weights, rank)
    clone.load_state_dict(base.state_dict())
    return clone


@torch.no_grad()
def evaluate_model(
    model: nn.Module,
    teacher: DenseAttentionTeacher,
    args: argparse.Namespace,
    seed_offset: int,
    budget: float | None = None,
) -> Metrics:
    model.eval()
    sum_mse = 0.0
    sum_target = 0.0
    sum_dot = 0.0
    sum_pred_norm = 0.0
    sum_target_norm = 0.0
    sum_budget = 0.0
    for step in range(args.eval_batches):
        x = sample(args, args.seed + seed_offset + step * 997)
        target = teacher(x).float()
        if isinstance(model, SelectiveKVResidualAttention):
            if budget is None:
                pred, gate = model.forward_soft(x, args.temperature)
            else:
                pred, gate = model.forward_hard(x, budget)
        else:
            pred = model(x)
            gate = torch.zeros(x.shape[:2])
        pred = pred.float()
        diff = pred - target
        sum_mse += float(diff.square().mean().item())
        sum_target += float(target.square().mean().item())
        sum_dot += float((pred * target).sum().item())
        sum_pred_norm += float(pred.square().sum().item())
        sum_target_norm += float(target.square().sum().item())
        sum_budget += float(gate.float().mean().item())
    mse = sum_mse / args.eval_batches
    target_power = max(sum_target / args.eval_batches, 1e-12)
    cosine = sum_dot / max(math.sqrt(sum_pred_norm) * math.sqrt(sum_target_norm), 1e-12)
    return Metrics(mse=mse, relative_mse=mse / target_power, cosine=cosine, actual_budget=sum_budget / args.eval_batches)


@torch.no_grad()
def oracle_mask(
    model: SelectiveKVResidualAttention,
    teacher: DenseAttentionTeacher,
    x: torch.Tensor,
    budget: float,
) -> torch.Tensor:
    target = teacher(x).float()
    base = model.base_output(x).float()
    base_err = (base - target).square().mean()
    benefits = torch.empty(x.shape[:2], dtype=torch.float32)
    for batch in range(x.shape[0]):
        for token in range(x.shape[1]):
            gate = torch.zeros(x.shape[:2], dtype=x.dtype)
            gate[batch, token] = 1.0
            pred = model._apply_residuals(x, gate).float()
            benefits[batch, token] = base_err - (pred - target).square().mean()
    return SelectiveResidualFFN.topk_mask(benefits, budget).float()


@torch.no_grad()
def evaluate_oracle(
    model: SelectiveKVResidualAttention,
    teacher: DenseAttentionTeacher,
    args: argparse.Namespace,
    seed_offset: int,
    budget: float,
) -> Metrics:
    model.eval()
    sum_mse = 0.0
    sum_target = 0.0
    sum_dot = 0.0
    sum_pred_norm = 0.0
    sum_target_norm = 0.0
    sum_budget = 0.0
    for step in range(args.eval_batches):
        x = sample(args, args.seed + seed_offset + step * 997)
        target = teacher(x).float()
        gate = oracle_mask(model, teacher, x, budget)
        pred = model._apply_residuals(x, gate).float()
        diff = pred - target
        sum_mse += float(diff.square().mean().item())
        sum_target += float(target.square().mean().item())
        sum_dot += float((pred * target).sum().item())
        sum_pred_norm += float(pred.square().sum().item())
        sum_target_norm += float(target.square().sum().item())
        sum_budget += float(gate.float().mean().item())
    mse = sum_mse / args.eval_batches
    target_power = max(sum_target / args.eval_batches, 1e-12)
    cosine = sum_dot / max(math.sqrt(sum_pred_norm) * math.sqrt(sum_target_norm), 1e-12)
    return Metrics(mse=mse, relative_mse=mse / target_power, cosine=cosine, actual_budget=sum_budget / args.eval_batches)


def train_base(base: LowRankKVAttention, teacher: DenseAttentionTeacher, args: argparse.Namespace) -> list[float]:
    opt = torch.optim.AdamW(base.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    losses = []
    for step in range(args.base_steps):
        x = sample(args, args.seed + step * 1297)
        with torch.no_grad():
            target = teacher(x).float()
        pred = base(x).float()
        loss = torch.nn.functional.mse_loss(pred, target)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(base.parameters(), args.grad_clip)
        opt.step()
        if step == 0 or step + 1 == args.base_steps or (step + 1) % args.log_every == 0:
            losses.append(float(loss.item()))
            print(json.dumps({"event": "train_base", "step": step + 1, "loss": losses[-1]}), flush=True)
    return losses


def train_patch(
    model: SelectiveKVResidualAttention,
    teacher: DenseAttentionTeacher,
    args: argparse.Namespace,
    target_budget: float,
    label: str,
) -> list[float]:
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.lr, weight_decay=args.weight_decay)
    losses = []
    for step in range(args.patch_steps):
        x = sample(args, args.seed + 10_000 + step * 1297)
        with torch.no_grad():
            target = teacher(x).float()
        pred, gate = model.forward_soft(x, args.temperature)
        mse = torch.nn.functional.mse_loss(pred.float(), target)
        if model.always_on:
            loss = mse
        else:
            loss = mse + args.budget_penalty * (gate.mean() - target_budget) ** 2
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
        opt.step()
        if step == 0 or step + 1 == args.patch_steps or (step + 1) % args.log_every == 0:
            losses.append(float(loss.item()))
            print(
                json.dumps(
                    {
                        "event": "train_patch",
                        "student": label,
                        "step": step + 1,
                        "loss": losses[-1],
                        "soft_budget": round(float(gate.mean().item()), 6),
                    }
                ),
                flush=True,
            )
    return losses


def train_supervised_router(
    model: SelectiveKVResidualAttention,
    teacher: DenseAttentionTeacher,
    args: argparse.Namespace,
    target_budget: float,
    label: str,
) -> list[float]:
    assert model.router is not None
    for name, param in model.named_parameters():
        if not name.startswith("router."):
            param.requires_grad_(False)
    opt = torch.optim.AdamW(model.router.parameters(), lr=args.router_lr, weight_decay=args.weight_decay)
    losses = []
    pos_weight = torch.tensor(max((1.0 - target_budget) / max(target_budget, 1e-4), 1.0), dtype=torch.float32)
    for step in range(args.router_steps):
        x = sample(args, args.seed + 20_000 + step * 1297)
        labels = oracle_mask(model, teacher, x, target_budget)
        logits = model.route_logits(x)
        bce = torch.nn.functional.binary_cross_entropy_with_logits(logits, labels, pos_weight=pos_weight)
        probs = torch.sigmoid(logits)
        loss = bce + args.router_budget_penalty * (probs.mean() - target_budget) ** 2
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.router.parameters(), args.grad_clip)
        opt.step()
        if step == 0 or step + 1 == args.router_steps or (step + 1) % args.log_every == 0:
            losses.append(float(loss.item()))
            print(
                json.dumps(
                    {
                        "event": "train_router",
                        "student": label,
                        "step": step + 1,
                        "loss": losses[-1],
                        "soft_budget": round(float(probs.mean().item()), 6),
                    }
                ),
                flush=True,
            )
    return losses


def make_model(
    patch: str,
    base: LowRankKVAttention,
    weights: dict[str, torch.Tensor],
    args: argparse.Namespace,
    always_on: bool,
) -> SelectiveKVResidualAttention:
    return SelectiveKVResidualAttention(
        clone_base(base, weights, args.rank),
        d=args.d,
        residual_rank=args.residual_rank,
        router_hidden=args.router_hidden,
        patch=patch,
        always_on=always_on,
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    torch.manual_seed(args.seed)
    weights = make_teacher_weights(args.d, args.seed)
    teacher = DenseAttentionTeacher(weights)
    base = LowRankKVAttention(weights, args.rank)
    base_losses = train_base(base, teacher, args)
    base_metrics = evaluate_model(base, teacher, args, 100_000)
    results: dict[str, Any] = {
        "low_rank_kv": {
            "metrics": asdict(base_metrics),
            "parameter_mib": round(parameter_bytes(base) / MIB, 6),
            "train_loss_trace": base_losses,
        }
    }

    for patch in args.patch_targets:
        always = make_model(patch, base, weights, args, always_on=True)
        label = f"{patch}_always_residual"
        losses = train_patch(always, teacher, args, 1.0, label)
        results[label] = {
            "metrics": asdict(evaluate_model(always, teacher, args, 100_000, budget=1.0)),
            "parameter_mib": round(parameter_bytes(always) / MIB, 6),
            "train_loss_trace": losses,
        }
        residual_state = {
            key: value.detach().clone()
            for key, value in always.state_dict().items()
            if "residual" in key
        }
        for budget in args.budgets:
            oracle_label = f"{patch}_oracle_b{budget:g}"
            results[oracle_label] = {
                "metrics": asdict(evaluate_oracle(always, teacher, args, 100_000, budget)),
                "parameter_mib": round(parameter_bytes(always) / MIB, 6),
                "note": "oracle top-k over per-token attention-output benefit; diagnostic upper bound",
            }

            selective_label = f"{patch}_selective_b{budget:g}"
            selective = make_model(patch, base, weights, args, always_on=False)
            losses = train_patch(selective, teacher, args, budget, selective_label)
            results[selective_label] = {
                "metrics": asdict(evaluate_model(selective, teacher, args, 100_000, budget=budget)),
                "soft_metrics": asdict(evaluate_model(selective, teacher, args, 100_000, budget=None)),
                "parameter_mib": round(parameter_bytes(selective) / MIB, 6),
                "train_loss_trace": losses,
            }

            supervised_label = f"{patch}_supervised_b{budget:g}"
            supervised = make_model(patch, base, weights, args, always_on=False)
            state = supervised.state_dict()
            state.update(residual_state)
            supervised.load_state_dict(state)
            losses = train_supervised_router(supervised, teacher, args, budget, supervised_label)
            results[supervised_label] = {
                "metrics": asdict(evaluate_model(supervised, teacher, args, 100_000, budget=budget)),
                "soft_metrics": asdict(evaluate_model(supervised, teacher, args, 100_000, budget=None)),
                "parameter_mib": round(parameter_bytes(supervised) / MIB, 6),
                "train_loss_trace": losses,
            }

    return {"created_at": now_tag(), "config": vars(args), "results": results}


def write_outputs(payload: dict[str, Any], outdir: Path) -> tuple[Path, Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    tag = payload["created_at"]
    json_path = outdir / f"mwg_kv_selective_probe_{tag}.json"
    md_path = outdir / f"mwg_kv_selective_probe_{tag}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    base_rel = payload["results"]["low_rank_kv"]["metrics"]["relative_mse"]
    lines = [
        "# MWG K/V Selective Probe",
        "",
        f"Created: `{tag}`",
        "",
        "| Method | Actual budget | Rel. MSE | Cosine | Improvement vs base | Params MiB |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for key, row in payload["results"].items():
        metrics = row["metrics"]
        rel = metrics["relative_mse"]
        improvement = (base_rel - rel) / base_rel if base_rel else 0.0
        lines.append(
            f"| {key} | {metrics['actual_budget']:.4f} | {rel:.6g} | "
            f"{metrics['cosine']:.6f} | {100 * improvement:.3f}% | {row['parameter_mib']} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--d", type=int, default=96)
    parser.add_argument("--rank", type=int, default=24)
    parser.add_argument("--residual-rank", type=int, default=12)
    parser.add_argument("--router-hidden", type=int, default=64)
    parser.add_argument("--patch-targets", type=lambda value: [item.strip() for item in value.split(",") if item.strip()], default=["k", "v", "kv"])
    parser.add_argument("--batch", type=int, default=2)
    parser.add_argument("--seq", type=int, default=32)
    parser.add_argument("--base-steps", type=int, default=120)
    parser.add_argument("--patch-steps", type=int, default=180)
    parser.add_argument("--router-steps", type=int, default=80)
    parser.add_argument("--eval-batches", type=int, default=6)
    parser.add_argument("--budgets", type=parse_floats, default=[0.05, 0.10, 0.25, 0.50])
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--budget-penalty", type=float, default=0.2)
    parser.add_argument("--router-budget-penalty", type=float, default=0.2)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--router-lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--log-every", type=int, default=90)
    parser.add_argument("--seed", type=int, default=20260527)
    parser.add_argument("--outdir", default="results")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    payload = run(args)
    json_path, md_path = write_outputs(payload, Path(args.outdir))
    print(json.dumps({"event": "saved", "json": str(json_path), "markdown": str(md_path)}, indent=2), flush=True)


if __name__ == "__main__":
    main()
