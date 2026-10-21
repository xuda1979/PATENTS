"""Local probe for budgeted selective MWG residuals.

The earlier broad validation suggests always replacing an FFN is fragile. This
script tests a narrower algorithmic claim: keep a low-rank/persistent base and
apply a small learned residual only to a budgeted subset of tokens.

It is intentionally CPU-friendly and synthetic by default so local iterations
can answer whether the idea has a signal before launching ASI3 jobs.
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

from mwg_quality_distillation import (
    DenseTeacher,
    LowRankFFN,
    make_batch,
    make_synthetic_teacher,
    parameter_bytes,
    svd_factors,
)

MIB = 1024**2


def now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_ints(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def parse_floats(value: str) -> list[float]:
    return [float(item.strip()) for item in value.split(",") if item.strip()]


@dataclass
class Metrics:
    mse: float
    relative_mse: float
    cosine: float
    actual_budget: float


class LowRankCorrection(nn.Module):
    def __init__(self, in_dim: int, out_dim: int, residual_rank: int, dtype: torch.dtype):
        super().__init__()
        self.a = nn.Linear(in_dim, residual_rank, bias=False, dtype=dtype)
        self.b = nn.Linear(residual_rank, out_dim, bias=False, dtype=dtype)
        nn.init.normal_(self.a.weight, mean=0.0, std=1e-3)
        nn.init.zeros_(self.b.weight)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.b(torch.nn.functional.silu(self.a(x)))


class SelectiveResidualFFN(nn.Module):
    def __init__(
        self,
        base: LowRankFFN,
        d: int,
        residual_rank: int,
        dtype: torch.dtype,
        router_hidden: int,
        always_on: bool = False,
    ):
        super().__init__()
        self.base = base
        for param in self.base.parameters():
            param.requires_grad_(False)
        self.residual = LowRankCorrection(d, d, residual_rank, dtype)
        self.always_on = always_on
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

    @staticmethod
    def topk_mask(logits: torch.Tensor, budget: float) -> torch.Tensor:
        if budget <= 0:
            return torch.zeros_like(logits)
        if budget >= 1:
            return torch.ones_like(logits)
        flat = logits.reshape(-1)
        k = max(1, min(flat.numel(), int(round(budget * flat.numel()))))
        threshold = torch.topk(flat, k=k).values[-1]
        mask = (logits >= threshold).to(dtype=logits.dtype)
        # Ties can push the budget slightly high; keep the exact top-k when that happens.
        if int(mask.sum().item()) > k:
            exact = torch.zeros_like(flat)
            exact[torch.topk(flat, k=k).indices] = 1.0
            mask = exact.view_as(logits)
        return mask

    def base_output(self, x: torch.Tensor) -> torch.Tensor:
        return self.base(x)

    def full_output(self, x: torch.Tensor) -> torch.Tensor:
        return self.base_output(x) + self.residual(x)

    def forward_soft(self, x: torch.Tensor, temperature: float) -> tuple[torch.Tensor, torch.Tensor]:
        base = self.base_output(x)
        delta = self.full_output(x) - base
        if self.always_on:
            gate = torch.ones(x.shape[:2], device=x.device, dtype=delta.dtype)
        else:
            gate = torch.sigmoid(self.route_logits(x) / temperature).to(dtype=delta.dtype)
        return base + gate.unsqueeze(-1) * delta, gate.float()

    @torch.no_grad()
    def forward_hard(self, x: torch.Tensor, budget: float) -> tuple[torch.Tensor, torch.Tensor]:
        base = self.base_output(x)
        delta = self.full_output(x) - base
        if self.always_on:
            gate = torch.ones(x.shape[:2], device=x.device, dtype=delta.dtype)
        else:
            gate = self.topk_mask(self.route_logits(x), budget).to(dtype=delta.dtype)
        return base + gate.unsqueeze(-1) * delta, gate.float()


class SelectiveInternalResidualFFN(SelectiveResidualFFN):
    def __init__(
        self,
        base: LowRankFFN,
        d: int,
        m: int,
        residual_rank: int,
        dtype: torch.dtype,
        router_hidden: int,
        always_on: bool = False,
    ):
        super().__init__(base, d, residual_rank, dtype, router_hidden, always_on=always_on)
        self.residual = None
        self.gate_residual = LowRankCorrection(d, m, residual_rank, dtype)
        self.up_residual = LowRankCorrection(d, m, residual_rank, dtype)
        self.down_residual = LowRankCorrection(m, d, residual_rank, dtype)

    def _base_parts(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        gate = (x @ self.base.gate_u) @ self.base.gate_v
        up = (x @ self.base.up_u) @ self.base.up_v
        hidden = torch.nn.functional.silu(gate) * up
        out = (hidden @ self.base.down_u) @ self.base.down_v
        return gate, up, hidden, out

    def base_output(self, x: torch.Tensor) -> torch.Tensor:
        return self._base_parts(x)[-1]

    def full_output(self, x: torch.Tensor) -> torch.Tensor:
        gate, up, _hidden, _out = self._base_parts(x)
        gate = gate + self.gate_residual(x)
        up = up + self.up_residual(x)
        hidden = torch.nn.functional.silu(gate) * up
        return (hidden @ self.base.down_u) @ self.base.down_v + self.down_residual(hidden)


def build_factors(d: int, m: int, rank: int, seed: int) -> tuple[DenseTeacher, dict[str, tuple[torch.Tensor, torch.Tensor]]]:
    gate, up, down, _meta = make_synthetic_teacher(d, m, seed)
    teacher = DenseTeacher(gate, up, down, torch.float32)
    factors = {}
    for name, weight in [("gate", gate), ("up", up), ("down", down)]:
        left, right, _energy = svd_factors(weight, rank)
        factors[name] = (left, right)
    return teacher, factors


def sample(args: argparse.Namespace, seed: int) -> torch.Tensor:
    return make_batch(args.batch, args.seq, args.d, torch.device("cpu"), torch.float32, seed)


@torch.no_grad()
def evaluate_model(
    model: nn.Module,
    teacher: DenseTeacher,
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
        if isinstance(model, SelectiveResidualFFN):
            if budget is None:
                pred, gate = model.forward_soft(x, args.temperature)
            else:
                pred, gate = model.forward_hard(x, budget)
        else:
            pred = model(x)
            gate = torch.ones(x.shape[:2]) if budget == 1.0 else torch.zeros(x.shape[:2])
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
def evaluate_oracle(
    model: SelectiveResidualFFN,
    teacher: DenseTeacher,
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
        base = model.base_output(x).float()
        residual_pred = model.full_output(x).float()
        delta = residual_pred - base
        base_err = (base - target).square().mean(dim=-1)
        residual_err = (residual_pred - target).square().mean(dim=-1)
        benefit = base_err - residual_err
        gate = SelectiveResidualFFN.topk_mask(benefit, budget).float()
        pred = base + gate.unsqueeze(-1) * delta
        diff = pred - target
        sum_mse += float(diff.square().mean().item())
        sum_target += float(target.square().mean().item())
        sum_dot += float((pred * target).sum().item())
        sum_pred_norm += float(pred.square().sum().item())
        sum_target_norm += float(target.square().sum().item())
        sum_budget += float(gate.mean().item())
    mse = sum_mse / args.eval_batches
    target_power = max(sum_target / args.eval_batches, 1e-12)
    cosine = sum_dot / max(math.sqrt(sum_pred_norm) * math.sqrt(sum_target_norm), 1e-12)
    return Metrics(mse=mse, relative_mse=mse / target_power, cosine=cosine, actual_budget=sum_budget / args.eval_batches)


def train_base(base: LowRankFFN, teacher: DenseTeacher, args: argparse.Namespace) -> list[float]:
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


def clone_base(base: LowRankFFN, factors: dict[str, tuple[torch.Tensor, torch.Tensor]]) -> LowRankFFN:
    clone = LowRankFFN(factors, dtype=torch.float32, generator="none")
    clone.load_state_dict(base.state_dict())
    return clone


def train_selective(
    model: SelectiveResidualFFN,
    teacher: DenseTeacher,
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
            budget_loss = (gate.mean() - target_budget) ** 2
            loss = mse + args.budget_penalty * budget_loss
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


def oracle_labels(model: SelectiveResidualFFN, teacher: DenseTeacher, x: torch.Tensor, budget: float) -> torch.Tensor:
    with torch.no_grad():
        target = teacher(x).float()
        base = model.base_output(x).float()
        residual_pred = model.full_output(x).float()
        base_err = (base - target).square().mean(dim=-1)
        residual_err = (residual_pred - target).square().mean(dim=-1)
        benefit = base_err - residual_err
        return SelectiveResidualFFN.topk_mask(benefit, budget).float()


def train_supervised_router(
    model: SelectiveResidualFFN,
    teacher: DenseTeacher,
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
        labels = oracle_labels(model, teacher, x, target_budget)
        logits = model.route_logits(x)
        bce = torch.nn.functional.binary_cross_entropy_with_logits(logits, labels, pos_weight=pos_weight)
        probs = torch.sigmoid(logits)
        budget_loss = (probs.mean() - target_budget) ** 2
        loss = bce + args.router_budget_penalty * budget_loss
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


def make_selective_model(
    residual_placement: str,
    base: LowRankFFN,
    factors: dict[str, tuple[torch.Tensor, torch.Tensor]],
    args: argparse.Namespace,
    always_on: bool,
) -> SelectiveResidualFFN:
    cloned = clone_base(base, factors)
    if residual_placement == "internal":
        return SelectiveInternalResidualFFN(
            cloned,
            d=args.d,
            m=args.m,
            residual_rank=args.residual_rank,
            dtype=torch.float32,
            router_hidden=args.router_hidden,
            always_on=always_on,
        )
    return SelectiveResidualFFN(
        cloned,
        d=args.d,
        residual_rank=args.residual_rank,
        dtype=torch.float32,
        router_hidden=args.router_hidden,
        always_on=always_on,
    )


def train_residual_family(
    residual_placement: str,
    base: LowRankFFN,
    factors: dict[str, tuple[torch.Tensor, torch.Tensor]],
    teacher: DenseTeacher,
    args: argparse.Namespace,
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    prefix = "internal" if residual_placement == "internal" else "output"

    always = make_selective_model(residual_placement, base, factors, args, always_on=True)
    losses = train_selective(always, teacher, args, 1.0, f"{prefix}_always_residual")
    always_metrics = evaluate_model(always, teacher, args, 100_000, budget=1.0)
    always_key = f"{prefix}_always_residual"
    results[always_key] = {
        "metrics": asdict(always_metrics),
        "parameter_mib": round(parameter_bytes(always) / MIB, 6),
        "train_loss_trace": losses,
    }

    for budget in args.budgets:
        label = f"{prefix}_oracle_residual_b{budget:g}"
        metrics = evaluate_oracle(always, teacher, args, 100_000, budget)
        results[label] = {
            "metrics": asdict(metrics),
            "parameter_mib": round(parameter_bytes(always) / MIB, 6),
            "note": "oracle top-k over per-token residual benefit; diagnostic upper bound, not deployable",
        }

    residual_state = {
        key: value.detach().clone()
        for key, value in always.state_dict().items()
        if "residual" in key
    }

    for budget in args.budgets:
        label = f"{prefix}_selective_residual_b{budget:g}"
        model = make_selective_model(residual_placement, base, factors, args, always_on=False)
        losses = train_selective(model, teacher, args, budget, label)
        hard_metrics = evaluate_model(model, teacher, args, 100_000, budget=budget)
        soft_metrics = evaluate_model(model, teacher, args, 100_000, budget=None)
        results[label] = {
            "metrics": asdict(hard_metrics),
            "soft_metrics": asdict(soft_metrics),
            "parameter_mib": round(parameter_bytes(model) / MIB, 6),
            "train_loss_trace": losses,
        }

        supervised_label = f"{prefix}_supervised_router_b{budget:g}"
        supervised = make_selective_model(residual_placement, base, factors, args, always_on=False)
        state = supervised.state_dict()
        state.update(residual_state)
        supervised.load_state_dict(state)
        router_losses = train_supervised_router(supervised, teacher, args, budget, supervised_label)
        hard_metrics = evaluate_model(supervised, teacher, args, 100_000, budget=budget)
        soft_metrics = evaluate_model(supervised, teacher, args, 100_000, budget=None)
        results[supervised_label] = {
            "metrics": asdict(hard_metrics),
            "soft_metrics": asdict(soft_metrics),
            "parameter_mib": round(parameter_bytes(supervised) / MIB, 6),
            "train_loss_trace": router_losses,
        }

    return results


def run(args: argparse.Namespace) -> dict[str, Any]:
    torch.manual_seed(args.seed)
    teacher, factors = build_factors(args.d, args.m, args.rank, args.seed)
    base = LowRankFFN(factors, dtype=torch.float32, generator="none")
    base_losses = train_base(base, teacher, args)
    base_metrics = evaluate_model(base, teacher, args, 100_000, budget=0.0)

    results: dict[str, Any] = {
        "persistent_low_rank": {
            "metrics": asdict(base_metrics),
            "parameter_mib": round(parameter_bytes(base) / MIB, 6),
            "train_loss_trace": base_losses,
        }
    }

    placements = ["output", "internal"] if args.residual_placement == "both" else [args.residual_placement]
    for placement in placements:
        results.update(train_residual_family(placement, base, factors, teacher, args))

    return {
        "created_at": now_tag(),
        "config": vars(args),
        "results": results,
    }


def write_outputs(payload: dict[str, Any], outdir: Path) -> tuple[Path, Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    tag = payload["created_at"]
    json_path = outdir / f"mwg_selective_residual_probe_{tag}.json"
    md_path = outdir / f"mwg_selective_residual_probe_{tag}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    base_rel = payload["results"]["persistent_low_rank"]["metrics"]["relative_mse"]
    lines = [
        "# MWG Selective Residual Probe",
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
    parser.add_argument("--d", type=int, default=128)
    parser.add_argument("--m", type=int, default=384)
    parser.add_argument("--rank", type=int, default=32)
    parser.add_argument("--residual-rank", type=int, default=8)
    parser.add_argument("--residual-placement", choices=["output", "internal", "both"], default="output")
    parser.add_argument("--router-hidden", type=int, default=64)
    parser.add_argument("--batch", type=int, default=2)
    parser.add_argument("--seq", type=int, default=48)
    parser.add_argument("--base-steps", type=int, default=80)
    parser.add_argument("--patch-steps", type=int, default=80)
    parser.add_argument("--router-steps", type=int, default=80)
    parser.add_argument("--eval-batches", type=int, default=8)
    parser.add_argument("--budgets", type=parse_floats, default=[0.05, 0.10, 0.25, 0.50])
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--budget-penalty", type=float, default=0.1)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--router-lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--router-budget-penalty", type=float, default=0.1)
    parser.add_argument("--log-every", type=int, default=40)
    parser.add_argument("--seed", type=int, default=20260526)
    parser.add_argument("--outdir", default="results")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    payload = run(args)
    json_path, md_path = write_outputs(payload, Path(args.outdir))
    print(json.dumps({"event": "saved", "json": str(json_path), "markdown": str(md_path)}, indent=2), flush=True)


if __name__ == "__main__":
    main()
