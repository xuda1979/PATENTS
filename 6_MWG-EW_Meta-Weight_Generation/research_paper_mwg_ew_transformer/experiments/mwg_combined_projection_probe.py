"""Local probe for combined projection-internal MWG residuals.

This extends the FFN-internal and K/V probes into a small synthetic block:
dense single-head attention plus dense gated FFN. The low-rank base is patched
by token-budgeted generated residuals in either the FFN path, the K/V path, or
both. Combined models can use separate routers, one shared token router, or a
joint router over FFN-token and K/V-token slots. The joint router is the closest
local proxy for a true allocator: one budget can move work between projection
families instead of spending the same token fraction on each path.
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

from mwg_kv_selective_probe import DenseAttentionTeacher, LowRankKVAttention, make_teacher_weights
from mwg_quality_distillation import DenseTeacher, LowRankFFN, make_batch, make_synthetic_teacher, parameter_bytes, svd_factors
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
    actual_ffn_budget: float
    actual_kv_budget: float


class DenseBlockTeacher(nn.Module):
    def __init__(self, ffn: DenseTeacher, attention: DenseAttentionTeacher):
        super().__init__()
        self.ffn = ffn
        self.attention = attention

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.attention(x) + self.ffn(x)


class LowRankBlockBase(nn.Module):
    def __init__(self, ffn: LowRankFFN, attention: LowRankKVAttention):
        super().__init__()
        self.ffn = ffn
        self.attention = attention

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.attention(x) + self.ffn(x)


class CombinedProjectionResidualBlock(nn.Module):
    def __init__(
        self,
        base: LowRankBlockBase,
        d: int,
        m: int,
        residual_rank: int,
        router_hidden: int,
        patch_mode: str,
        router_mode: str,
        always_on: bool = False,
    ):
        super().__init__()
        if patch_mode not in {"ffn", "kv", "combined"}:
            raise ValueError(f"unknown patch mode: {patch_mode}")
        if router_mode not in {"separate", "shared", "joint"}:
            raise ValueError(f"unknown router mode: {router_mode}")
        self.base = base
        self.patch_mode = patch_mode
        self.router_mode = router_mode
        self.always_on = always_on
        for param in self.base.parameters():
            param.requires_grad_(False)

        self.ffn_enabled = patch_mode in {"ffn", "combined"}
        self.kv_enabled = patch_mode in {"kv", "combined"}
        self.ffn_gate_residual = LowRankCorrection(d, m, residual_rank, torch.float32) if self.ffn_enabled else None
        self.ffn_up_residual = LowRankCorrection(d, m, residual_rank, torch.float32) if self.ffn_enabled else None
        self.ffn_down_residual = LowRankCorrection(m, d, residual_rank, torch.float32) if self.ffn_enabled else None
        self.k_residual = LowRankCorrection(d, d, residual_rank, torch.float32) if self.kv_enabled else None
        self.v_residual = LowRankCorrection(d, d, residual_rank, torch.float32) if self.kv_enabled else None

        if always_on:
            self.shared_router = None
            self.joint_router = None
            self.ffn_router = None
            self.kv_router = None
        elif router_mode == "shared":
            self.shared_router = nn.Sequential(
                nn.Linear(d, router_hidden, dtype=torch.float32),
                nn.SiLU(),
                nn.Linear(router_hidden, 1, dtype=torch.float32),
            )
            self.joint_router = None
            self.ffn_router = None
            self.kv_router = None
        elif router_mode == "joint":
            self.shared_router = None
            self.joint_router = nn.Sequential(
                nn.Linear(d, router_hidden, dtype=torch.float32),
                nn.SiLU(),
                nn.Linear(router_hidden, 2, dtype=torch.float32),
            )
            self.ffn_router = None
            self.kv_router = None
        else:
            self.shared_router = None
            self.joint_router = None
            self.ffn_router = (
                nn.Sequential(
                    nn.Linear(d, router_hidden, dtype=torch.float32),
                    nn.SiLU(),
                    nn.Linear(router_hidden, 1, dtype=torch.float32),
                )
                if self.ffn_enabled
                else None
            )
            self.kv_router = (
                nn.Sequential(
                    nn.Linear(d, router_hidden, dtype=torch.float32),
                    nn.SiLU(),
                    nn.Linear(router_hidden, 1, dtype=torch.float32),
                )
                if self.kv_enabled
                else None
            )

    def route_logits(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        if self.always_on:
            ones = torch.ones(x.shape[:2], device=x.device, dtype=torch.float32)
            return {"ffn": ones, "kv": ones}
        if self.shared_router is not None:
            logits = self.shared_router(x.float()).squeeze(-1)
            return {"ffn": logits, "kv": logits}
        if self.joint_router is not None:
            logits = self.joint_router(x.float())
            return {"ffn": logits[..., 0], "kv": logits[..., 1]}
        out: dict[str, torch.Tensor] = {}
        if self.ffn_router is not None:
            out["ffn"] = self.ffn_router(x.float()).squeeze(-1)
        if self.kv_router is not None:
            out["kv"] = self.kv_router(x.float()).squeeze(-1)
        return out

    def _ffn_output(self, x: torch.Tensor, gate: torch.Tensor) -> torch.Tensor:
        base = self.base.ffn
        gate_proj = (x @ base.gate_u) @ base.gate_v
        up = (x @ base.up_u) @ base.up_v
        if self.ffn_gate_residual is not None and self.ffn_up_residual is not None:
            gate_proj = gate_proj + gate.unsqueeze(-1) * self.ffn_gate_residual(x)
            up = up + gate.unsqueeze(-1) * self.ffn_up_residual(x)
        hidden = torch.nn.functional.silu(gate_proj) * up
        out = (hidden @ base.down_u) @ base.down_v
        if self.ffn_down_residual is not None:
            out = out + gate.unsqueeze(-1) * self.ffn_down_residual(hidden)
        return out

    def _kv_output(self, x: torch.Tensor, gate: torch.Tensor) -> torch.Tensor:
        q, k, v = self.base.attention.project(x)
        if self.k_residual is not None:
            k = k + gate.unsqueeze(-1) * self.k_residual(x)
        if self.v_residual is not None:
            v = v + gate.unsqueeze(-1) * self.v_residual(x)
        scale = 1.0 / math.sqrt(q.shape[-1])
        weights = torch.softmax(torch.matmul(q, k.transpose(-1, -2)) * scale, dim=-1)
        return torch.matmul(weights, v) @ self.base.attention.o

    def base_output(self, x: torch.Tensor) -> torch.Tensor:
        return self.base(x)

    def output_with_gates(self, x: torch.Tensor, ffn_gate: torch.Tensor, kv_gate: torch.Tensor) -> torch.Tensor:
        if not self.ffn_enabled:
            ffn_gate = torch.zeros_like(ffn_gate)
        if not self.kv_enabled:
            kv_gate = torch.zeros_like(kv_gate)
        return self._kv_output(x, kv_gate) + self._ffn_output(x, ffn_gate)

    def full_output(self, x: torch.Tensor) -> torch.Tensor:
        ones = torch.ones(x.shape[:2], device=x.device, dtype=x.dtype)
        return self.output_with_gates(x, ones, ones)

    def forward_soft(self, x: torch.Tensor, temperature: float) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        if self.always_on:
            ones = torch.ones(x.shape[:2], device=x.device, dtype=x.dtype)
            zeros = torch.zeros_like(ones)
            ffn_gate = ones if self.ffn_enabled else zeros
            kv_gate = ones if self.kv_enabled else zeros
        else:
            logits = self.route_logits(x)
            zeros = torch.zeros(x.shape[:2], device=x.device, dtype=x.dtype)
            ffn_gate = (
                torch.sigmoid(logits["ffn"] / temperature).to(dtype=x.dtype)
                if self.ffn_enabled
                else zeros
            )
            kv_gate = (
                torch.sigmoid(logits["kv"] / temperature).to(dtype=x.dtype)
                if self.kv_enabled
                else zeros
            )
        return self.output_with_gates(x, ffn_gate, kv_gate), ffn_gate.float(), kv_gate.float()

    @torch.no_grad()
    def forward_hard(self, x: torch.Tensor, budget: float) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        if self.always_on:
            ones = torch.ones(x.shape[:2], device=x.device, dtype=x.dtype)
            zeros = torch.zeros_like(ones)
            ffn_gate = ones if self.ffn_enabled else zeros
            kv_gate = ones if self.kv_enabled else zeros
        else:
            logits = self.route_logits(x)
            zeros = torch.zeros(x.shape[:2], device=x.device, dtype=x.dtype)
            if self.joint_router is not None and self.ffn_enabled and self.kv_enabled:
                ffn_gate, kv_gate = joint_topk_masks(logits["ffn"], logits["kv"], budget)
                ffn_gate = ffn_gate.to(dtype=x.dtype)
                kv_gate = kv_gate.to(dtype=x.dtype)
            else:
                ffn_gate = (
                    SelectiveResidualFFN.topk_mask(logits["ffn"], budget).to(dtype=x.dtype)
                    if self.ffn_enabled
                    else zeros
                )
                kv_gate = (
                    SelectiveResidualFFN.topk_mask(logits["kv"], budget).to(dtype=x.dtype)
                    if self.kv_enabled
                    else zeros
                )
        return self.output_with_gates(x, ffn_gate, kv_gate), ffn_gate.float(), kv_gate.float()


def joint_topk_masks(ffn_scores: torch.Tensor, kv_scores: torch.Tensor, budget: float) -> tuple[torch.Tensor, torch.Tensor]:
    if budget <= 0:
        return torch.zeros_like(ffn_scores), torch.zeros_like(kv_scores)
    if budget >= 1:
        return torch.ones_like(ffn_scores), torch.ones_like(kv_scores)
    stacked = torch.stack([ffn_scores, kv_scores], dim=-1)
    flat = stacked.reshape(-1)
    k = max(1, min(flat.numel(), int(round(budget * flat.numel()))))
    exact = torch.zeros_like(flat)
    exact[torch.topk(flat, k=k).indices] = 1.0
    masks = exact.view_as(stacked)
    return masks[..., 0], masks[..., 1]


def build_block(args: argparse.Namespace) -> tuple[DenseBlockTeacher, LowRankBlockBase, dict[str, Any]]:
    gate, up, down, ffn_meta = make_synthetic_teacher(args.d, args.m, args.seed)
    ffn_teacher = DenseTeacher(gate, up, down, torch.float32)
    ffn_factors = {}
    for name, weight in [("gate", gate), ("up", up), ("down", down)]:
        left, right, _energy = svd_factors(weight, args.rank)
        ffn_factors[name] = (left, right)
    ffn_base = LowRankFFN(ffn_factors, dtype=torch.float32, generator="none")

    attn_weights = make_teacher_weights(args.d, args.seed + 17)
    attn_teacher = DenseAttentionTeacher(attn_weights)
    attn_base = LowRankKVAttention(attn_weights, args.rank)
    return DenseBlockTeacher(ffn_teacher, attn_teacher), LowRankBlockBase(ffn_base, attn_base), {
        "ffn_factors": ffn_factors,
        "attention_weights": attn_weights,
        "ffn_meta": ffn_meta,
    }


def clone_base(base: LowRankBlockBase, cache: dict[str, Any], rank: int) -> LowRankBlockBase:
    ffn = LowRankFFN(cache["ffn_factors"], dtype=torch.float32, generator="none")
    attn = LowRankKVAttention(cache["attention_weights"], rank)
    clone = LowRankBlockBase(ffn, attn)
    clone.load_state_dict(base.state_dict())
    return clone


def sample(args: argparse.Namespace, seed: int) -> torch.Tensor:
    return make_batch(args.batch, args.seq, args.d, torch.device("cpu"), torch.float32, seed)


@torch.no_grad()
def evaluate_model(
    model: nn.Module,
    teacher: DenseBlockTeacher,
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
    sum_ffn_budget = 0.0
    sum_kv_budget = 0.0
    for step in range(args.eval_batches):
        x = sample(args, args.seed + seed_offset + step * 997)
        target = teacher(x).float()
        if isinstance(model, CombinedProjectionResidualBlock):
            if budget is None:
                pred, ffn_gate, kv_gate = model.forward_soft(x, args.temperature)
            else:
                pred, ffn_gate, kv_gate = model.forward_hard(x, budget)
        else:
            pred = model(x)
            ffn_gate = torch.zeros(x.shape[:2])
            kv_gate = torch.zeros(x.shape[:2])
        pred = pred.float()
        diff = pred - target
        sum_mse += float(diff.square().mean().item())
        sum_target += float(target.square().mean().item())
        sum_dot += float((pred * target).sum().item())
        sum_pred_norm += float(pred.square().sum().item())
        sum_target_norm += float(target.square().sum().item())
        ffn_mean = float(ffn_gate.mean().item())
        kv_mean = float(kv_gate.mean().item())
        active_paths = int(getattr(model, "ffn_enabled", False)) + int(getattr(model, "kv_enabled", False))
        sum_budget += (ffn_mean + kv_mean) / max(active_paths, 1)
        sum_ffn_budget += ffn_mean
        sum_kv_budget += kv_mean
    mse = sum_mse / args.eval_batches
    target_power = max(sum_target / args.eval_batches, 1e-12)
    cosine = sum_dot / max(math.sqrt(sum_pred_norm) * math.sqrt(sum_target_norm), 1e-12)
    return Metrics(
        mse=mse,
        relative_mse=mse / target_power,
        cosine=cosine,
        actual_budget=sum_budget / args.eval_batches,
        actual_ffn_budget=sum_ffn_budget / args.eval_batches,
        actual_kv_budget=sum_kv_budget / args.eval_batches,
    )


@torch.no_grad()
def oracle_masks(
    model: CombinedProjectionResidualBlock,
    teacher: DenseBlockTeacher,
    x: torch.Tensor,
    budget: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    target = teacher(x).float()
    base = model.base_output(x).float()
    base_err = (base - target).square().mean()
    zero = torch.zeros(x.shape[:2], dtype=x.dtype)
    benefits: dict[str, torch.Tensor] = {}
    if model.ffn_enabled:
        scores = torch.empty(x.shape[:2], dtype=torch.float32)
        for batch in range(x.shape[0]):
            for token in range(x.shape[1]):
                gate = torch.zeros(x.shape[:2], dtype=x.dtype)
                gate[batch, token] = 1.0
                pred = model.output_with_gates(x, gate, zero).float()
                benefits["ffn"] = scores
                scores[batch, token] = base_err - (pred - target).square().mean()
    if model.kv_enabled:
        scores = torch.empty(x.shape[:2], dtype=torch.float32)
        for batch in range(x.shape[0]):
            for token in range(x.shape[1]):
                gate = torch.zeros(x.shape[:2], dtype=x.dtype)
                gate[batch, token] = 1.0
                pred = model.output_with_gates(x, zero, gate).float()
                benefits["kv"] = scores
                scores[batch, token] = base_err - (pred - target).square().mean()

    if model.router_mode == "joint" and model.ffn_enabled and model.kv_enabled:
        return joint_topk_masks(benefits["ffn"], benefits["kv"], budget)

    if model.router_mode == "shared" and model.ffn_enabled and model.kv_enabled:
        stacked = torch.maximum(benefits["ffn"], benefits["kv"])
        gate = SelectiveResidualFFN.topk_mask(stacked, budget).float()
        return gate, gate

    ffn_gate = SelectiveResidualFFN.topk_mask(benefits["ffn"], budget).float() if model.ffn_enabled else zero.float()
    kv_gate = SelectiveResidualFFN.topk_mask(benefits["kv"], budget).float() if model.kv_enabled else zero.float()
    return ffn_gate, kv_gate


@torch.no_grad()
def evaluate_oracle(
    model: CombinedProjectionResidualBlock,
    teacher: DenseBlockTeacher,
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
    sum_ffn_budget = 0.0
    sum_kv_budget = 0.0
    active_paths = int(model.ffn_enabled) + int(model.kv_enabled)
    for step in range(args.eval_batches):
        x = sample(args, args.seed + seed_offset + step * 997)
        target = teacher(x).float()
        ffn_gate, kv_gate = oracle_masks(model, teacher, x, budget)
        pred = model.output_with_gates(x, ffn_gate, kv_gate).float()
        diff = pred - target
        sum_mse += float(diff.square().mean().item())
        sum_target += float(target.square().mean().item())
        sum_dot += float((pred * target).sum().item())
        sum_pred_norm += float(pred.square().sum().item())
        sum_target_norm += float(target.square().sum().item())
        ffn_mean = float(ffn_gate.mean().item())
        kv_mean = float(kv_gate.mean().item())
        sum_budget += (ffn_mean + kv_mean) / max(active_paths, 1)
        sum_ffn_budget += ffn_mean
        sum_kv_budget += kv_mean
    mse = sum_mse / args.eval_batches
    target_power = max(sum_target / args.eval_batches, 1e-12)
    cosine = sum_dot / max(math.sqrt(sum_pred_norm) * math.sqrt(sum_target_norm), 1e-12)
    return Metrics(
        mse=mse,
        relative_mse=mse / target_power,
        cosine=cosine,
        actual_budget=sum_budget / args.eval_batches,
        actual_ffn_budget=sum_ffn_budget / args.eval_batches,
        actual_kv_budget=sum_kv_budget / args.eval_batches,
    )


def train_base(base: LowRankBlockBase, teacher: DenseBlockTeacher, args: argparse.Namespace) -> list[float]:
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
    model: CombinedProjectionResidualBlock,
    teacher: DenseBlockTeacher,
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
        pred, ffn_gate, kv_gate = model.forward_soft(x, args.temperature)
        mse = torch.nn.functional.mse_loss(pred.float(), target)
        if model.always_on:
            loss = mse
        else:
            active = int(model.ffn_enabled) + int(model.kv_enabled)
            budget_mean = (ffn_gate.mean() + kv_gate.mean()) / max(active, 1)
            loss = mse + args.budget_penalty * (budget_mean - target_budget) ** 2
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
                        "ffn_soft_budget": round(float(ffn_gate.mean().item()), 6),
                        "kv_soft_budget": round(float(kv_gate.mean().item()), 6),
                    }
                ),
                flush=True,
            )
    return losses


def train_supervised_router(
    model: CombinedProjectionResidualBlock,
    teacher: DenseBlockTeacher,
    args: argparse.Namespace,
    target_budget: float,
    label: str,
) -> list[float]:
    for name, param in model.named_parameters():
        param.requires_grad_("router" in name)
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=args.router_lr, weight_decay=args.weight_decay)
    pos_weight = torch.tensor(max((1.0 - target_budget) / max(target_budget, 1e-4), 1.0), dtype=torch.float32)
    losses = []
    for step in range(args.router_steps):
        x = sample(args, args.seed + 20_000 + step * 1297)
        ffn_labels, kv_labels = oracle_masks(model, teacher, x, target_budget)
        logits = model.route_logits(x)
        loss = torch.tensor(0.0)
        probs_for_log: list[torch.Tensor] = []
        if model.joint_router is not None and model.ffn_enabled and model.kv_enabled:
            logits = model.route_logits(x)
            ffn_raw = logits["ffn"]
            kv_raw = logits["kv"]
            ffn_loss = torch.nn.functional.binary_cross_entropy_with_logits(ffn_raw, ffn_labels, pos_weight=pos_weight)
            kv_loss = torch.nn.functional.binary_cross_entropy_with_logits(kv_raw, kv_labels, pos_weight=pos_weight)
            ffn_probs = torch.sigmoid(ffn_raw)
            kv_probs = torch.sigmoid(kv_raw)
            budget_mean = (ffn_probs.mean() + kv_probs.mean()) / 2
            loss = ffn_loss + kv_loss + args.router_budget_penalty * (budget_mean - target_budget) ** 2
            probs_for_log.extend([ffn_probs, kv_probs])
        elif model.shared_router is not None:
            labels = torch.maximum(ffn_labels, kv_labels)
            raw = logits["ffn"]
            loss = torch.nn.functional.binary_cross_entropy_with_logits(raw, labels, pos_weight=pos_weight)
            probs = torch.sigmoid(raw)
            loss = loss + args.router_budget_penalty * (probs.mean() - target_budget) ** 2
            probs_for_log.append(probs)
        else:
            if model.ffn_enabled:
                raw = logits["ffn"]
                ffn_loss = torch.nn.functional.binary_cross_entropy_with_logits(raw, ffn_labels, pos_weight=pos_weight)
                ffn_probs = torch.sigmoid(raw)
                loss = loss + ffn_loss + args.router_budget_penalty * (ffn_probs.mean() - target_budget) ** 2
                probs_for_log.append(ffn_probs)
            if model.kv_enabled:
                raw = logits["kv"]
                kv_loss = torch.nn.functional.binary_cross_entropy_with_logits(raw, kv_labels, pos_weight=pos_weight)
                kv_probs = torch.sigmoid(raw)
                loss = loss + kv_loss + args.router_budget_penalty * (kv_probs.mean() - target_budget) ** 2
                probs_for_log.append(kv_probs)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(params, args.grad_clip)
        opt.step()
        if step == 0 or step + 1 == args.router_steps or (step + 1) % args.log_every == 0:
            losses.append(float(loss.item()))
            soft_budget = sum(float(probs.mean().item()) for probs in probs_for_log) / max(len(probs_for_log), 1)
            print(
                json.dumps(
                    {
                        "event": "train_router",
                        "student": label,
                        "step": step + 1,
                        "loss": losses[-1],
                        "soft_budget": round(soft_budget, 6),
                    }
                ),
                flush=True,
            )
    return losses


def make_model(
    patch_mode: str,
    router_mode: str,
    base: LowRankBlockBase,
    cache: dict[str, Any],
    args: argparse.Namespace,
    always_on: bool,
) -> CombinedProjectionResidualBlock:
    return CombinedProjectionResidualBlock(
        clone_base(base, cache, args.rank),
        d=args.d,
        m=args.m,
        residual_rank=args.residual_rank,
        router_hidden=args.router_hidden,
        patch_mode=patch_mode,
        router_mode=router_mode,
        always_on=always_on,
    )


def run_family(
    patch_mode: str,
    router_mode: str,
    base: LowRankBlockBase,
    cache: dict[str, Any],
    teacher: DenseBlockTeacher,
    args: argparse.Namespace,
) -> dict[str, Any]:
    prefix = f"{patch_mode}_{router_mode}"
    results: dict[str, Any] = {}
    always = make_model(patch_mode, router_mode, base, cache, args, always_on=True)
    always_label = f"{prefix}_always"
    losses = train_patch(always, teacher, args, 1.0, always_label)
    results[always_label] = {
        "metrics": asdict(evaluate_model(always, teacher, args, 100_000, budget=1.0)),
        "parameter_mib": round(parameter_bytes(always) / MIB, 6),
        "train_loss_trace": losses,
    }
    residual_state = {key: value.detach().clone() for key, value in always.state_dict().items() if "residual" in key}

    for budget in args.budgets:
        oracle_label = f"{prefix}_oracle_b{budget:g}"
        results[oracle_label] = {
            "metrics": asdict(evaluate_oracle(always, teacher, args, 100_000, budget)),
            "parameter_mib": round(parameter_bytes(always) / MIB, 6),
            "note": "oracle top-k over per-token projection-family benefit; diagnostic upper bound",
        }

        selective_label = f"{prefix}_selective_b{budget:g}"
        selective = make_model(patch_mode, router_mode, base, cache, args, always_on=False)
        losses = train_patch(selective, teacher, args, budget, selective_label)
        results[selective_label] = {
            "metrics": asdict(evaluate_model(selective, teacher, args, 100_000, budget=budget)),
            "soft_metrics": asdict(evaluate_model(selective, teacher, args, 100_000, budget=None)),
            "parameter_mib": round(parameter_bytes(selective) / MIB, 6),
            "train_loss_trace": losses,
        }

        supervised_label = f"{prefix}_supervised_b{budget:g}"
        supervised = make_model(patch_mode, router_mode, base, cache, args, always_on=False)
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
    return results


def run(args: argparse.Namespace) -> dict[str, Any]:
    torch.manual_seed(args.seed)
    teacher, base, cache = build_block(args)
    base_losses = train_base(base, teacher, args)
    base_metrics = evaluate_model(base, teacher, args, 100_000)
    results: dict[str, Any] = {
        "low_rank_block": {
            "metrics": asdict(base_metrics),
            "parameter_mib": round(parameter_bytes(base) / MIB, 6),
            "train_loss_trace": base_losses,
        }
    }

    families = [
        ("ffn", "separate"),
        ("kv", "separate"),
        ("combined", "separate"),
        ("combined", "shared"),
        ("combined", "joint"),
    ]
    for patch_mode, router_mode in families:
        results.update(run_family(patch_mode, router_mode, base, cache, teacher, args))

    return {"created_at": now_tag(), "config": vars(args), "results": results}


def write_outputs(payload: dict[str, Any], outdir: Path) -> tuple[Path, Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    tag = payload["created_at"]
    json_path = outdir / f"mwg_combined_projection_probe_{tag}.json"
    md_path = outdir / f"mwg_combined_projection_probe_{tag}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    base_rel = payload["results"]["low_rank_block"]["metrics"]["relative_mse"]
    lines = [
        "# MWG Combined Projection Probe",
        "",
        f"Created: `{tag}`",
        "",
        "| Method | Budget | FFN budget | K/V budget | Rel. MSE | Cosine | Improvement vs base | Params MiB |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key, row in payload["results"].items():
        metrics = row["metrics"]
        rel = metrics["relative_mse"]
        improvement = (base_rel - rel) / base_rel if base_rel else 0.0
        lines.append(
            f"| {key} | {metrics['actual_budget']:.4f} | {metrics['actual_ffn_budget']:.4f} | "
            f"{metrics['actual_kv_budget']:.4f} | {rel:.6g} | {metrics['cosine']:.6f} | "
            f"{100 * improvement:.3f}% | {row['parameter_mib']} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--d", type=int, default=64)
    parser.add_argument("--m", type=int, default=192)
    parser.add_argument("--rank", type=int, default=16)
    parser.add_argument("--residual-rank", type=int, default=8)
    parser.add_argument("--router-hidden", type=int, default=48)
    parser.add_argument("--batch", type=int, default=2)
    parser.add_argument("--seq", type=int, default=24)
    parser.add_argument("--base-steps", type=int, default=80)
    parser.add_argument("--patch-steps", type=int, default=120)
    parser.add_argument("--router-steps", type=int, default=60)
    parser.add_argument("--eval-batches", type=int, default=4)
    parser.add_argument("--budgets", type=parse_floats, default=[0.10, 0.25, 0.50])
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--budget-penalty", type=float, default=0.2)
    parser.add_argument("--router-budget-penalty", type=float, default=0.2)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--router-lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--log-every", type=int, default=60)
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
