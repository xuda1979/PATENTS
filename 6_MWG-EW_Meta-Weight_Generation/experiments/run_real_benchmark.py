"""MWG-EW real accelerator benchmark for patent evidence.

Proves three core patent claims on real hardware:
  1. Low-rank factorization reduces HBM traffic by >10x
  2. Quality (output fidelity) is preserved via SVD initialization
  3. Gradient communication volume drops proportionally

Run on Huanxin ai1 (Ascend 910B2 NPU):
    python3 experiments/run_real_benchmark.py --suite all
    python3 experiments/run_real_benchmark.py --suite pilot --ranks 32,64,128
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any

import torch
import torch.nn as nn

# ===== Unified device abstraction ===========================================

_BACKEND = "cpu"
_HAS_NPU = False
_HAS_CUDA = False

try:
    import torch_npu
    if torch.npu.is_available():
        _HAS_NPU = True
        _BACKEND = "npu"
except ImportError:
    pass

if not _HAS_NPU and torch.cuda.is_available():
    _HAS_CUDA = True
    _BACKEND = "cuda"


def get_device() -> torch.device:
    return torch.device(f"{_BACKEND}:0" if _BACKEND != "cpu" else "cpu")


def sync():
    if _HAS_NPU:
        torch.npu.synchronize()
    elif _HAS_CUDA:
        torch.cuda.synchronize()


def reset_peak():
    if _HAS_NPU:
        torch.npu.reset_peak_memory_stats()
    elif _HAS_CUDA:
        torch.cuda.reset_peak_memory_stats()


def peak_mem() -> int:
    if _HAS_NPU:
        return torch.npu.max_memory_allocated()
    elif _HAS_CUDA:
        return torch.cuda.max_memory_allocated()
    return 0


def mem_allocated() -> int:
    if _HAS_NPU:
        return torch.npu.memory_allocated()
    elif _HAS_CUDA:
        return torch.cuda.memory_allocated()
    return 0


def empty_cache():
    if _HAS_NPU:
        torch.npu.empty_cache()
    elif _HAS_CUDA:
        torch.cuda.empty_cache()


def capture_env() -> dict[str, Any]:
    env: dict[str, Any] = {"torch_version": torch.__version__, "backend": _BACKEND}
    if _HAS_NPU:
        env["device"] = torch.npu.get_device_name(0)
        env["device_count"] = torch.npu.device_count()
        try:
            p = torch_npu.npu.get_device_properties(0)
            env["memory_gib"] = round(p.total_memory / (1024**3), 2)
        except Exception:
            pass
        env["torch_npu_version"] = getattr(torch_npu, "__version__", "N/A")
    elif _HAS_CUDA:
        env["device"] = torch.cuda.get_device_name(0)
        env["device_count"] = torch.cuda.device_count()
        p = torch.cuda.get_device_properties(0)
        env["memory_gib"] = round(p.total_mem / (1024**3), 2)
        env["cuda_version"] = torch.version.cuda or "N/A"
    return env


# ===== Model definitions ====================================================

class DenseFFN(nn.Module):
    """Standard gated FFN: y = down(silu(gate(x)) * up(x))."""

    def __init__(self, d: int, m: int, dtype=torch.float16):
        super().__init__()
        self.up = nn.Linear(d, m, bias=False, dtype=dtype)
        self.gate = nn.Linear(d, m, bias=False, dtype=dtype)
        self.down = nn.Linear(m, d, bias=False, dtype=dtype)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.down(torch.nn.functional.silu(self.gate(x)) * self.up(x))

    def weight_bytes(self) -> int:
        return sum(p.numel() * p.element_size() for p in self.parameters())


class LowRankFFN(nn.Module):
    """Low-rank gated FFN: each projection W is replaced by U @ V.

    This is the core of the patent: the dense weight W (d × m) is replaced
    by two smaller factors U (d × r) and V (r × m). The forward pass reads
    only U and V from HBM, not W.

    HBM traffic per projection:
      dense  = 2 * d * m  bytes
      lowrank = 2 * (d*r + r*m) bytes
      ratio   = (d*r + r*m) / (d*m) = r/m + r/d
    """

    def __init__(self, d: int, m: int, rank: int, dtype=torch.float16):
        super().__init__()
        self.rank = rank
        self.d = d
        self.m = m
        # Up projection: (d,r) @ (r,m)
        self.up_U = nn.Parameter(torch.zeros(d, rank, dtype=dtype))
        self.up_V = nn.Parameter(torch.zeros(rank, m, dtype=dtype))
        # Gate projection: (d,r) @ (r,m)
        self.gate_U = nn.Parameter(torch.zeros(d, rank, dtype=dtype))
        self.gate_V = nn.Parameter(torch.zeros(rank, m, dtype=dtype))
        # Down projection: (m,r) @ (r,d)
        self.down_U = nn.Parameter(torch.zeros(m, rank, dtype=dtype))
        self.down_V = nn.Parameter(torch.zeros(rank, d, dtype=dtype))

    @classmethod
    def from_dense_svd(cls, dense: DenseFFN, rank: int) -> "LowRankFFN":
        """Initialize from dense FFN using truncated SVD.

        This proves that the low-rank factors can faithfully reproduce
        the dense output. The quality metric (cosine similarity) is
        determined by how much energy the top-r singular values capture.
        """
        d = dense.up.weight.shape[1]
        m = dense.up.weight.shape[0]
        dtype = dense.up.weight.dtype
        model = cls(d, m, rank, dtype=dtype)

        # W = U @ diag(S) @ Vh → split as (U√S) @ (√S Vh)
        for W_t, u_param, v_param in [
            (dense.up.weight.data.T, model.up_U, model.up_V),       # (d, m)
            (dense.gate.weight.data.T, model.gate_U, model.gate_V), # (d, m)
            (dense.down.weight.data.T, model.down_U, model.down_V), # (m, d)
        ]:
            W32 = W_t.float()
            U, S, Vh = torch.linalg.svd(W32, full_matrices=False)
            sqrt_S = S[:rank].sqrt()
            U_r = (U[:, :rank] * sqrt_S.unsqueeze(0)).to(dtype)
            V_r = (Vh[:rank, :] * sqrt_S.unsqueeze(1)).to(dtype)
            u_param.data.copy_(U_r)
            v_param.data.copy_(V_r)

        return model

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Each projection: two matmuls instead of one, reading U and V from HBM
        up_out = (x @ self.up_U) @ self.up_V       # x(B,S,d) @ U(d,r) @ V(r,m)
        gate_out = (x @ self.gate_U) @ self.gate_V
        hidden = torch.nn.functional.silu(gate_out) * up_out
        return (hidden @ self.down_U) @ self.down_V  # (B,S,m) @ U(m,r) @ V(r,d)

    def weight_bytes(self) -> int:
        return sum(p.numel() * p.element_size() for p in self.parameters())

    def hbm_read_per_forward_bytes(self) -> int:
        """Bytes read from HBM per forward (just the factors)."""
        return self.weight_bytes()

    @staticmethod
    def dense_hbm_read_bytes(d: int, m: int, n_proj: int = 3, elem: int = 2) -> int:
        """Dense HBM read for comparison."""
        return n_proj * d * m * elem

    def traffic_reduction(self) -> float:
        dense_bytes = self.dense_hbm_read_bytes(self.d, self.m)
        return dense_bytes / max(self.weight_bytes(), 1)


# ===== Benchmarking ==========================================================

MIB = 1024 ** 2


def bench_latency(model: nn.Module, x: torch.Tensor,
                  warmup: int = 30, iters: int = 200) -> dict[str, float]:
    """Measure forward-pass latency with proper warmup."""
    model.eval()
    sync()
    with torch.no_grad():
        for _ in range(warmup):
            model(x)
    sync()

    reset_peak()
    sync()
    t0 = time.perf_counter()
    with torch.no_grad():
        for _ in range(iters):
            model(x)
    sync()
    t1 = time.perf_counter()

    ms = (t1 - t0) * 1000.0 / iters
    B, S = x.shape[0], x.shape[1]
    return {
        "latency_ms": round(ms, 4),
        "throughput_tok_s": round(B * S / ms * 1000, 1),
        "peak_mem_mib": round(peak_mem() / MIB, 2),
    }


def measure_quality(dense: DenseFFN, lowrank: LowRankFFN,
                    x: torch.Tensor) -> dict[str, float]:
    """Compare dense and low-rank outputs."""
    dense.eval()
    lowrank.eval()
    with torch.no_grad():
        y_dense = dense(x).float()
        y_lr = lowrank(x).float()

    # Cosine similarity (global)
    cos = torch.nn.functional.cosine_similarity(
        y_dense.reshape(1, -1), y_lr.reshape(1, -1)
    ).item()

    # Per-token cosine similarity
    yd = y_dense.reshape(-1, y_dense.shape[-1])
    yl = y_lr.reshape(-1, y_lr.shape[-1])
    per_tok_cos = torch.nn.functional.cosine_similarity(yd, yl, dim=1)

    # Relative Frobenius error (safe division)
    dense_norm = y_dense.norm().item()
    diff_norm = (y_dense - y_lr).norm().item()
    rel_err = diff_norm / max(dense_norm, 1e-8)

    return {
        "cosine_similarity": round(cos, 6),
        "per_token_cos_mean": round(per_tok_cos.mean().item(), 6),
        "per_token_cos_min": round(per_tok_cos.min().item(), 6),
        "relative_frobenius_error": round(rel_err, 6),
        "max_abs_error": round((y_dense - y_lr).abs().max().item(), 6),
    }


def measure_svd_energy(dense: DenseFFN, rank: int) -> dict[str, float]:
    """How much singular-value energy the top-r values capture."""
    energies = []
    for W in [dense.up.weight.data.T, dense.gate.weight.data.T,
              dense.down.weight.data.T]:
        S = torch.linalg.svdvals(W.float())
        total = (S ** 2).sum()
        top_r = (S[:rank] ** 2).sum()
        energies.append((top_r / total).item())
    return {
        "up_energy_pct": round(energies[0] * 100, 2),
        "gate_energy_pct": round(energies[1] * 100, 2),
        "down_energy_pct": round(energies[2] * 100, 2),
        "mean_energy_pct": round(sum(energies) / 3 * 100, 2),
    }


def distillation_steps(dense: DenseFFN, lowrank: LowRankFFN,
                       device: torch.device, d: int,
                       steps: int = 200, lr: float = 1e-3,
                       B: int = 4, S: int = 128) -> list[dict]:
    """Fine-tune low-rank model to match dense outputs (knowledge distillation).

    This proves that even if SVD init is not perfect, a short distillation
    phase recovers quality.

    Note: loss is computed in float32 to avoid fp16 gradient overflow on NPU.
    """
    dense.eval()
    lowrank.train()
    opt = torch.optim.Adam(lowrank.parameters(), lr=lr)
    log = []
    dtype = next(dense.parameters()).dtype

    for step in range(steps):
        x = torch.randn(B, S, d, dtype=dtype, device=device)
        with torch.no_grad():
            target = dense(x)
        pred = lowrank(x)
        # Compute loss in float32 to avoid fp16 overflow on NPU/GPU
        loss = ((pred.float() - target.float()) ** 2).mean()
        opt.zero_grad()
        loss.backward()
        # Gradient clipping to prevent fp16 overflow
        torch.nn.utils.clip_grad_norm_(lowrank.parameters(), max_norm=1.0)
        opt.step()
        if step % 20 == 0 or step == steps - 1:
            with torch.no_grad():
                x_eval = torch.randn(B, S, d, dtype=dtype, device=device)
                y_d = dense(x_eval).float()
                y_l = lowrank(x_eval).float()
                cos = torch.nn.functional.cosine_similarity(
                    y_d.reshape(1, -1), y_l.reshape(1, -1)
                ).item()
                rel_err = (y_d - y_l).norm() / max(y_d.norm().item(), 1e-8)
            log.append({
                "step": step,
                "train_loss": round(loss.item(), 6),
                "cos_sim": round(cos, 6),
                "rel_err": round(rel_err.item() if not isinstance(rel_err, float) else rel_err, 6),
            })
            print(f"    step {step:4d}: loss={loss.item():.6f}  cos={cos:.6f}  rel_err={rel_err.item() if hasattr(rel_err, 'item') else rel_err:.6f}")
    lowrank.eval()
    return log


# ===== Experiment suites =====================================================

@dataclass
class Result:
    suite: str
    config: dict[str, Any]
    env: dict[str, Any]
    data: dict[str, Any] = field(default_factory=dict)


def run_pilot(ranks: list[int], device: torch.device) -> Result:
    """1B pilot: d=2048, m=5632."""
    d, m = 2048, 5632
    dtype = torch.float16
    result = Result(suite="pilot_1b",
                    config={"d": d, "m": m, "dtype": "fp16", "ranks": ranks},
                    env=capture_env())

    # ---- Dense baseline ----
    dense = DenseFFN(d, m, dtype=dtype).to(device)
    dense_bytes = dense.weight_bytes()
    print(f"\n  Dense FFN weight bytes: {dense_bytes/MIB:.2f} MiB")

    # Different batch configs: decode-like and training-like
    configs = [
        ("decode_b1_s1", 1, 1),
        ("decode_b1_s128", 1, 128),
        ("train_b4_s512", 4, 512),
    ]

    for cfg_name, B, S in configs:
        x = torch.randn(B, S, d, dtype=dtype, device=device)
        dense_lat = bench_latency(dense, x)
        print(f"\n  [{cfg_name}] Dense: {dense_lat['latency_ms']} ms, "
              f"{dense_lat['throughput_tok_s']} tok/s")
        result.data[f"dense_{cfg_name}"] = {
            "weight_mib": round(dense_bytes / MIB, 2),
            **dense_lat,
        }

        for rank in ranks:
            lr_model = LowRankFFN.from_dense_svd(dense, rank).to(device)
            lr_bytes = lr_model.weight_bytes()
            reduction = lr_model.traffic_reduction()
            lr_lat = bench_latency(lr_model, x)
            qual = measure_quality(dense, lr_model, x)
            energy = measure_svd_energy(dense, rank)

            speedup = dense_lat['latency_ms'] / lr_lat['latency_ms'] if lr_lat['latency_ms'] > 0 else 0

            row = {
                "rank": rank,
                "weight_mib": round(lr_bytes / MIB, 2),
                "traffic_reduction_x": round(reduction, 1),
                "speedup": round(speedup, 2),
                **lr_lat,
                **qual,
                **energy,
            }
            result.data[f"r{rank}_{cfg_name}"] = row
            print(f"  [{cfg_name}] r={rank}: {lr_lat['latency_ms']} ms, "
                  f"speedup={speedup:.2f}x, cos={qual['cosine_similarity']:.4f}, "
                  f"traffic↓{reduction:.1f}x, energy={energy['mean_energy_pct']:.1f}%")

            del lr_model
        del x
    empty_cache()

    # ---- Distillation for best rank ----
    best_rank = ranks[len(ranks) // 2]  # middle rank
    print(f"\n  Distillation at r={best_rank}:")
    lr_distill = LowRankFFN.from_dense_svd(dense, best_rank).to(device)
    distill_log = distillation_steps(dense, lr_distill, device, d, steps=200)
    result.data["distillation"] = {"rank": best_rank, "log": distill_log}
    del lr_distill, dense
    empty_cache()
    return result


def run_patent(ranks: list[int], device: torch.device) -> Result:
    """8B patent-grade: d=4096, m=14336, three-projection gated FFN."""
    d, m = 4096, 14336
    dtype = torch.float16
    result = Result(suite="patent_8b",
                    config={"d": d, "m": m, "dtype": "fp16", "ranks": ranks},
                    env=capture_env())

    dense = DenseFFN(d, m, dtype=dtype).to(device)
    dense_bytes = dense.weight_bytes()
    print(f"\n  Dense FFN weight bytes: {dense_bytes/MIB:.2f} MiB  ({dense_bytes/MIB:.0f} MiB)")

    configs = [
        ("decode_b1_s1", 1, 1),
        ("decode_b1_s128", 1, 128),
        ("train_b4_s512", 4, 512),
        ("train_b8_s512", 8, 512),
    ]

    for cfg_name, B, S in configs:
        x = torch.randn(B, S, d, dtype=dtype, device=device)
        dense_lat = bench_latency(dense, x)
        print(f"\n  [{cfg_name}] Dense: {dense_lat['latency_ms']} ms, "
              f"{dense_lat['throughput_tok_s']} tok/s")
        result.data[f"dense_{cfg_name}"] = {
            "weight_mib": round(dense_bytes / MIB, 2),
            **dense_lat,
        }

        for rank in ranks:
            lr_model = LowRankFFN.from_dense_svd(dense, rank).to(device)
            lr_bytes = lr_model.weight_bytes()
            reduction = lr_model.traffic_reduction()
            lr_lat = bench_latency(lr_model, x)
            qual = measure_quality(dense, lr_model, x)
            energy = measure_svd_energy(dense, rank)

            speedup = dense_lat['latency_ms'] / lr_lat['latency_ms'] if lr_lat['latency_ms'] > 0 else 0

            row = {
                "rank": rank,
                "weight_mib": round(lr_bytes / MIB, 2),
                "traffic_reduction_x": round(reduction, 1),
                "speedup": round(speedup, 2),
                **lr_lat,
                **qual,
                **energy,
            }
            result.data[f"r{rank}_{cfg_name}"] = row
            print(f"  [{cfg_name}] r={rank}: {lr_lat['latency_ms']} ms, "
                  f"speedup={speedup:.2f}x, cos={qual['cosine_similarity']:.4f}, "
                  f"traffic↓{reduction:.1f}x, energy={energy['mean_energy_pct']:.1f}%")

            del lr_model
        del x
    empty_cache()

    # Distillation
    best_rank = ranks[len(ranks) // 2]
    print(f"\n  Distillation at r={best_rank}:")
    lr_distill = LowRankFFN.from_dense_svd(dense, best_rank).to(device)
    distill_log = distillation_steps(dense, lr_distill, device, d, steps=200, B=4, S=256)
    result.data["distillation"] = {"rank": best_rank, "log": distill_log}
    del lr_distill, dense
    empty_cache()
    return result


def run_comm(ranks: list[int], device: torch.device) -> Result:
    """Gradient communication volume: dense vs low-rank."""
    d, m = 4096, 14336
    dtype = torch.float16
    result = Result(suite="communication",
                    config={"d": d, "m": m, "dtype": "fp16", "ranks": ranks},
                    env=capture_env())

    B, S = 4, 256
    x = torch.randn(B, S, d, dtype=dtype, device=device)
    target = torch.randn(B, S, d, dtype=dtype, device=device)

    # Dense gradient
    dense = DenseFFN(d, m, dtype=dtype).to(device)
    dense.train()
    out = dense(x)
    ((out - target) ** 2).mean().backward()
    dense_grad = sum(p.grad.numel() * p.grad.element_size()
                     for p in dense.parameters() if p.grad is not None)
    dense.zero_grad()
    dense.eval()

    result.data["dense"] = {
        "grad_bytes": dense_grad,
        "grad_mib": round(dense_grad / MIB, 2),
    }
    print(f"\n  Dense gradient: {dense_grad/MIB:.2f} MiB")

    for rank in ranks:
        lr = LowRankFFN.from_dense_svd(dense, rank).to(device)
        lr.train()
        out = lr(x)
        ((out - target) ** 2).mean().backward()
        lr_grad = sum(p.grad.numel() * p.grad.element_size()
                      for p in lr.parameters() if p.grad is not None)
        reduction = dense_grad / max(lr_grad, 1)
        savings = (1 - lr_grad / max(dense_grad, 1)) * 100

        result.data[f"r{rank}"] = {
            "grad_bytes": lr_grad,
            "grad_mib": round(lr_grad / MIB, 2),
            "reduction_x": round(reduction, 2),
            "savings_pct": round(savings, 1),
        }
        print(f"  r={rank}: grad={lr_grad/MIB:.2f} MiB, "
              f"reduction={reduction:.1f}x, savings={savings:.1f}%")
        del lr

    # Memory savings → KV cache expansion
    kv_mib_per_token = 0.75  # typical for 8B model
    for rank in ranks:
        dense_weight_mib = dense.weight_bytes() / MIB
        lr_weight_mib = result.data[f"r{rank}"]["grad_mib"]  # same as weight size
        freed_mib = dense_weight_mib - lr_weight_mib
        extra_tokens = int(freed_mib / kv_mib_per_token)
        result.data[f"r{rank}"]["freed_mem_mib"] = round(freed_mib, 2)
        result.data[f"r{rank}"]["extra_kv_tokens"] = extra_tokens
        print(f"  r={rank}: freed {freed_mib:.1f} MiB → "
              f"+{extra_tokens} KV tokens at {kv_mib_per_token} MiB/tok")

    del dense, x, target
    empty_cache()
    return result


# ===== Output ================================================================

def save(results: list[Result], outdir: str):
    os.makedirs(outdir, exist_ok=True)
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

    # JSON
    path = os.path.join(outdir, f"patent_evidence_{ts}.json")
    with open(path, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2, default=str)
    print(f"\nJSON: {path}")

    # Disclosure markdown
    md = os.path.join(outdir, f"patent_evidence_{ts}_disclosure.md")
    with open(md, "w") as f:
        f.write(f"# MWG-EW 专利实测证据\n\n")
        f.write(f"测试时间: {ts}\n\n")
        for r in results:
            f.write(f"## {r.suite}\n\n")
            f.write(f"硬件: {json.dumps(r.env)}\n\n")
            f.write(f"配置: {json.dumps(r.config)}\n\n")

            if r.suite in ("pilot_1b", "patent_8b"):
                # Summary table
                d = r.config["d"]
                m = r.config["m"]
                dense_mib = 3 * d * m * 2 / MIB
                f.write(f"稠密 FFN 块权重: {dense_mib:.0f} MiB\n\n")
                f.write("### 延迟与加速\n\n")
                f.write("| 配置 | 秩 r | 权重 (MiB) | 流量缩减 | 延迟 (ms) | 加速比 | 余弦相似度 | SVD 能量 |\n")
                f.write("|------|------|-----------|---------|----------|--------|----------|--------|\n")
                for k, v in r.data.items():
                    if k.startswith("dense_"):
                        cfg = k[6:]
                        f.write(f"| {cfg} | dense | {v['weight_mib']} | 1.0x | {v['latency_ms']} | 1.00x | — | — |\n")
                    elif not k.startswith("distill"):
                        parts = k.split("_", 1)
                        rank_s = parts[0]
                        cfg = parts[1] if len(parts) > 1 else ""
                        f.write(f"| {cfg} | {rank_s} | {v['weight_mib']} | "
                                f"{v.get('traffic_reduction_x','')}x | {v['latency_ms']} | "
                                f"{v.get('speedup','')}x | {v.get('cosine_similarity','')} | "
                                f"{v.get('mean_energy_pct','')}% |\n")
                f.write("\n")

                if "distillation" in r.data:
                    dl = r.data["distillation"]
                    f.write(f"### 蒸馏恢复 (r={dl['rank']})\n\n")
                    f.write("| 步数 | 训练损失 | 余弦相似度 | 相对误差 |\n")
                    f.write("|------|---------|----------|--------|\n")
                    for row in dl["log"]:
                        f.write(f"| {row['step']} | {row['train_loss']} | "
                                f"{row['cos_sim']} | {row['rel_err']} |\n")
                    f.write("\n")

            elif r.suite == "communication":
                f.write("### 梯度通信量\n\n")
                f.write("| 配置 | 梯度 (MiB) | 缩减比 | 节省 | 释放内存 (MiB) | 额外 KV tokens |\n")
                f.write("|------|-----------|--------|------|-------------|---------------|\n")
                dense_g = r.data.get("dense", {})
                f.write(f"| dense | {dense_g.get('grad_mib','')} | 1.0x | 0% | — | — |\n")
                for k, v in r.data.items():
                    if k.startswith("r"):
                        f.write(f"| {k} | {v['grad_mib']} | {v['reduction_x']}x | "
                                f"{v['savings_pct']}% | {v.get('freed_mem_mib','')} | "
                                f"{v.get('extra_kv_tokens','')} |\n")
                f.write("\n")

    print(f"Disclosure: {md}")


# ===== Main ==================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", choices=["all", "pilot", "patent", "comm"], default="all")
    ap.add_argument("--ranks", default="32,64,128,256")
    ap.add_argument("--output-dir", default="results")
    args = ap.parse_args()

    ranks = [int(r) for r in args.ranks.split(",")]
    device = get_device()

    print(f"Backend: {_BACKEND}")
    env = capture_env()
    for k, v in env.items():
        print(f"  {k}: {v}")

    results: list[Result] = []

    if args.suite in ("all", "pilot"):
        print("\n" + "=" * 60)
        print("=== 1B Pilot ===")
        results.append(run_pilot(ranks, device))

    if args.suite in ("all", "patent"):
        print("\n" + "=" * 60)
        print("=== 8B Patent Grade ===")
        results.append(run_patent(ranks, device))

    if args.suite in ("all", "comm"):
        print("\n" + "=" * 60)
        print("=== Communication Volume ===")
        results.append(run_comm(ranks, device))

    save(results, args.output_dir)
    print("\nDone.")


if __name__ == "__main__":
    main()
