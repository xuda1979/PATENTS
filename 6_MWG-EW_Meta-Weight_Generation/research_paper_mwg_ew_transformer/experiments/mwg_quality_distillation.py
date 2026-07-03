"""Quality/distillation experiment for MWG-EW FFN replacements.

This script complements the latency/communication benchmark. It asks a
different question: given a dense gated FFN teacher, how well do low-rank
student families recover the teacher's outputs after distillation?

It supports two teacher sources:
  * synthetic: reproducible random dense FFN weights
  * checkpoint: Hugging Face-style model folders with safetensors or .bin files

The main comparison is between:
  * static_svd: truncated-SVD factors with no training
  * persistent_low_rank: trainable low-rank factors, equivalent to a durable
    low-rank FFN baseline
  * mwg_ephemeral: the same low-rank factors plus a small context-conditioned
    rank-scale generator, representing the generated descriptor path
  * mwg_token_scale: per-token generated rank scales, testing whether the
    descriptor should adapt at token granularity rather than only from a batch
    context
  * mwg_token_rank_mixer: per-token generated rank-channel mixers, testing
    whether descriptors need cross-rank interactions rather than diagonal scales
  * mwg_token_residual: the rank-scale generator plus a token-conditioned
    low-rank residual descriptor, testing a more expressive generated path
  * mwg_mixture: a token-group router over multiple low-rank basis banks plus
    token residuals, testing whether conditional generation can beat a durable
    low-rank baseline at the same rank
  * mwg_expert_residual: the same low-rank base with a context-routed bank of
    small residual experts, designed to improve quality without storing several
    full rank-r basis banks

When launched with torch.distributed.run, each rank trains on independent
activation batches and gradients are synchronized with DDP.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import socket
import statistics
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import torch.distributed as dist
import torch.nn as nn

try:
    import torch_npu  # type: ignore

    HAS_NPU = hasattr(torch, "npu") and torch.npu.is_available()
except Exception:
    torch_npu = None  # type: ignore
    HAS_NPU = False

HAS_CUDA = torch.cuda.is_available() and not HAS_NPU
MIB = 1024**2


def now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_ints(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def parse_texts(value: str) -> list[str]:
    path = Path(value)
    if path.exists():
        return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [item.strip() for item in value.split("||") if item.strip()]


def setup_runtime() -> tuple[torch.device, int, int, int, str]:
    rank = int(os.environ.get("RANK", "0"))
    local_rank = int(os.environ.get("LOCAL_RANK", "0"))
    world_size = int(os.environ.get("WORLD_SIZE", "1"))
    if HAS_NPU:
        torch.npu.set_device(local_rank)
        device = torch.device(f"npu:{local_rank}")
        backend = "hccl"
    elif HAS_CUDA:
        torch.cuda.set_device(local_rank)
        device = torch.device(f"cuda:{local_rank}")
        backend = "nccl"
    else:
        device = torch.device("cpu")
        backend = "gloo"
    if world_size > 1 and not dist.is_initialized():
        dist.init_process_group(backend=backend)
    return device, rank, local_rank, world_size, backend


def sync_device() -> None:
    if HAS_NPU:
        torch.npu.synchronize()
    elif HAS_CUDA:
        torch.cuda.synchronize()


def barrier() -> None:
    if dist.is_initialized():
        dist.barrier()


def env_payload(device: torch.device, local_rank: int, world_size: int, backend: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "hostname": socket.gethostname(),
        "python": sys.version.split()[0],
        "torch": torch.__version__,
        "backend": backend,
        "device_type": device.type,
        "local_rank": local_rank,
        "world_size": world_size,
        "ascend_rt_visible_devices": os.environ.get("ASCEND_RT_VISIBLE_DEVICES", ""),
    }
    if HAS_NPU:
        payload["torch_npu"] = getattr(torch_npu, "__version__", "unknown")
        payload["npu_count"] = torch.npu.device_count()
        try:
            payload["device_name"] = torch.npu.get_device_name(local_rank)
        except Exception:
            payload["device_name"] = "npu"
    elif HAS_CUDA:
        payload["cuda"] = torch.version.cuda
        payload["device_name"] = torch.cuda.get_device_name(local_rank)
    else:
        payload["device_name"] = "cpu"
    return payload


def elem_bytes(dtype: torch.dtype) -> int:
    return torch.empty((), dtype=dtype).element_size()


def parameter_bytes(module: nn.Module) -> int:
    return sum(p.numel() * p.element_size() for p in module.parameters())


def dense_bytes(d: int, m: int, dtype: torch.dtype) -> int:
    return 3 * d * m * elem_bytes(dtype)


def descriptor_bytes(d: int, m: int, rank: int, dtype: torch.dtype) -> int:
    return 3 * rank * (d + m) * elem_bytes(dtype)


def dtype_from_name(name: str, device: torch.device) -> torch.dtype:
    if name == "auto":
        return torch.float16 if device.type in {"npu", "cuda"} else torch.float32
    return {"fp16": torch.float16, "bf16": torch.bfloat16, "fp32": torch.float32}[name]


def safe_torch_load(path: Path) -> dict[str, torch.Tensor]:
    try:
        return torch.load(path, map_location="cpu", weights_only=True)
    except Exception:
        try:
            return torch.load(path, map_location="cpu", weights_only=False)
        except TypeError:
            return torch.load(path, map_location="cpu")


def iter_state_files(model_dir: Path) -> list[Path]:
    safes = sorted(model_dir.glob("*.safetensors"))
    if safes:
        return safes
    bins = sorted(model_dir.glob("pytorch_model*.bin")) + sorted(model_dir.glob("*.bin"))
    return bins


def load_state_file(path: Path) -> dict[str, torch.Tensor]:
    if path.suffix == ".safetensors":
        from safetensors.torch import load_file  # type: ignore

        return load_file(str(path), device="cpu")
    return safe_torch_load(path)


def find_ffn_triplet(model_dir: Path, layer: int | None) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, dict[str, str]]:
    names = {
        "gate": [
            r"model\.layers\.(\d+)\.mlp\.gate_proj\.weight",
            r"layers\.(\d+)\.mlp\.gate_proj\.weight",
        ],
        "up": [
            r"model\.layers\.(\d+)\.mlp\.up_proj\.weight",
            r"layers\.(\d+)\.mlp\.up_proj\.weight",
        ],
        "down": [
            r"model\.layers\.(\d+)\.mlp\.down_proj\.weight",
            r"layers\.(\d+)\.mlp\.down_proj\.weight",
        ],
    }
    found: dict[int, dict[str, tuple[str, torch.Tensor]]] = {}
    for state_path in iter_state_files(model_dir):
        state = load_state_file(state_path)
        for key, tensor in state.items():
            if not torch.is_tensor(tensor) or tensor.ndim != 2:
                continue
            for kind, patterns in names.items():
                for pattern in patterns:
                    match = re.fullmatch(pattern, key)
                    if match:
                        idx = int(match.group(1))
                        found.setdefault(idx, {})[kind] = (key, tensor.float().cpu())
        complete = [idx for idx, parts in found.items() if {"gate", "up", "down"} <= set(parts)]
        if complete:
            chosen = layer if layer is not None else min(complete)
            if chosen in complete:
                parts = found[chosen]
                gate = parts["gate"][1].t().contiguous()
                up = parts["up"][1].t().contiguous()
                down = parts["down"][1].t().contiguous()
                return gate, up, down, {
                    "gate": parts["gate"][0],
                    "up": parts["up"][0],
                    "down": parts["down"][0],
                    "state_file": str(state_path),
                    "layer": str(chosen),
                }
    raise RuntimeError(f"could not find Qwen/LLaMA-style gate/up/down FFN weights in {model_dir}")


def make_synthetic_teacher(d: int, m: int, seed: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, dict[str, str]]:
    gen = torch.Generator(device="cpu").manual_seed(seed)
    scale_d = 1.0 / math.sqrt(d)
    scale_m = 1.0 / math.sqrt(m)
    gate = torch.randn(d, m, generator=gen) * scale_d
    up = torch.randn(d, m, generator=gen) * scale_d
    down = torch.randn(m, d, generator=gen) * scale_m
    return gate, up, down, {"source": "synthetic", "layer": "none"}


DEFAULT_TEXTS = [
    "Transformer feed-forward layers dominate parameter movement in large language model inference.",
    "Efficient systems research should measure latency, memory traffic, communication, and model quality together.",
    "A conditional generator can select different low-rank subspaces for code, mathematics, dialogue, and factual prose.",
    "Bandwidth-aware neural architecture design changes where weights live during execution.",
    "The quick brown fox writes a compiler pass for a matrix multiplication kernel.",
    "In distributed training, gradient synchronization can become the bottleneck when layers contain huge dense matrices.",
    "Scientific evidence improves when negative baselines are shown beside positive systems measurements.",
    "Low-rank approximation alone is not enough when pretrained feed-forward matrices have slowly decaying spectra.",
    "A robust experiment should compare static SVD, persistent low-rank factors, and generated ephemeral factors.",
    "Careful ablation studies distinguish an architectural contribution from an implementation artifact.",
    "Machine learning papers need clear claims, strong baselines, and reproducible artifacts.",
    "The model solves a small algebra problem by composing several intermediate facts.",
    "During long-context decoding, attention cache storage and feed-forward weight bandwidth are different resources.",
    "A top journal submission needs evidence that quality survives the proposed systems optimization.",
    "Routing among basis banks can give token groups specialized descriptor subspaces.",
    "The generated descriptors are consumed by the kernel and should not become durable model tensors.",
]


def activation_cache_path(args: argparse.Namespace, world_size: int) -> Path:
    source = "synthetic" if not args.model_dir else re.sub(r"[^A-Za-z0-9_.-]+", "_", args.model_dir.strip("/"))
    text_sig = f"{len(args.texts)}texts_max{args.activation_max_batches}_seq{args.activation_seq}"
    return Path(tempfile.gettempdir()) / (
        f"mwg_activation_cache_v1_{source}_layer{args.layer}_{text_sig}_seed{args.seed}_w{world_size}.pt"
    )


def capture_text_activations(args: argparse.Namespace, device: torch.device, rank: int, world_size: int) -> torch.Tensor | None:
    if args.activation_source != "text":
        return None
    cache_path = activation_cache_path(args, world_size)
    done_path = cache_path.with_suffix(cache_path.suffix + ".done")
    if world_size > 1 and rank != 0:
        while not done_path.exists():
            time.sleep(1.0)
        payload = safe_torch_load(cache_path)
        barrier()
        return payload["activations"].float()

    if not args.model_dir:
        raise RuntimeError("--activation-source text requires --model-dir")

    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore
    except Exception as exc:
        raise RuntimeError("text activation capture requires transformers") from exc

    model_dir = Path(args.model_dir)
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir), trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model_dtype = torch.float16 if device.type in {"npu", "cuda"} else torch.float32
    model = AutoModelForCausalLM.from_pretrained(
        str(model_dir),
        torch_dtype=model_dtype,
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    ).to(device)
    model.eval()

    layer = 0 if args.layer is None else args.layer
    captured: list[torch.Tensor] = []

    def hook(_module: nn.Module, inputs: tuple[torch.Tensor, ...], _output: Any) -> None:
        captured.append(inputs[0].detach().float().cpu())

    handle = model.model.layers[layer].mlp.register_forward_hook(hook)  # type: ignore[attr-defined]
    texts = args.texts or DEFAULT_TEXTS
    batches: list[torch.Tensor] = []
    try:
        with torch.no_grad():
            for index in range(args.activation_max_batches):
                offset = (index * args.activation_text_batch) % len(texts)
                batch_texts = [texts[(offset + j) % len(texts)] for j in range(args.activation_text_batch)]
                encoded = tokenizer(
                    batch_texts,
                    return_tensors="pt",
                    padding="max_length",
                    truncation=True,
                    max_length=args.activation_seq,
                )
                encoded = {key: value.to(device) for key, value in encoded.items()}
                captured.clear()
                _ = model(**encoded)
                if not captured:
                    raise RuntimeError(f"MLP hook did not capture activations for layer {layer}")
                batches.append(captured[0])
                if rank == 0 and (index == 0 or (index + 1) % max(1, args.activation_log_every) == 0):
                    print(json.dumps({"event": "activation_capture", "batch": index + 1, "shape": list(captured[0].shape)}), flush=True)
    finally:
        handle.remove()
        del model
        if HAS_NPU:
            torch.npu.empty_cache()
        elif HAS_CUDA:
            torch.cuda.empty_cache()

    activations = torch.cat(batches, dim=0).contiguous()
    if rank == 0:
        tmp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
        done_path.unlink(missing_ok=True)
        torch.save({"activations": activations.half(), "shape": tuple(activations.shape)}, tmp_path)
        tmp_path.replace(cache_path)
        done_path.write_text("ok\n", encoding="utf-8")
        print(json.dumps({"event": "activation_cache_ready", "path": str(cache_path), "shape": list(activations.shape)}), flush=True)
    barrier()
    return activations.float()


def svd_factors(
    weight: torch.Tensor,
    rank: int,
    method: str = "exact",
    oversample: int = 16,
    niter: int = 2,
) -> tuple[torch.Tensor, torch.Tensor, float]:
    matrix = weight.float()
    if method == "pca_lowrank":
        q = min(min(matrix.shape), rank + max(0, oversample))
        u, s, v = torch.pca_lowrank(matrix, q=q, center=False, niter=niter)
        u = u[:, :rank]
        s = s[:rank]
        vh = v[:, :rank].t()
    else:
        u, s, vh = torch.linalg.svd(matrix, full_matrices=False)
    total = torch.sum(s.square()).clamp_min(1e-12)
    kept = torch.sum(s[:rank].square())
    root = torch.sqrt(s[:rank])
    left = u[:, :rank] * root.view(1, -1)
    right = root.view(-1, 1) * vh[:rank, :]
    return left.contiguous(), right.contiguous(), float((kept / total).item())


class DenseTeacher(nn.Module):
    def __init__(self, gate: torch.Tensor, up: torch.Tensor, down: torch.Tensor, dtype: torch.dtype):
        super().__init__()
        self.register_buffer("gate", gate.to(dtype=dtype))
        self.register_buffer("up", up.to(dtype=dtype))
        self.register_buffer("down", down.to(dtype=dtype))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return (torch.nn.functional.silu(x @ self.gate) * (x @ self.up)) @ self.down


class LowRankFFN(nn.Module):
    def __init__(
        self,
        factors: dict[str, tuple[torch.Tensor, torch.Tensor]],
        dtype: torch.dtype,
        generator: str = "none",
        generator_hidden: int | None = None,
        residual_rank: int = 8,
        scale_amplitude: float = 0.05,
        basis_count: int = 4,
        basis_noise: float = 0.01,
    ):
        super().__init__()
        if generator not in {"none", "rank_scale", "token_scale", "token_rank_mixer", "token_residual", "mixture", "expert_residual"}:
            raise ValueError(f"unknown generator mode: {generator}")
        self.generator_mode = generator
        self.rank = factors["up"][0].shape[1]
        self.d = factors["up"][0].shape[0]
        self.m = factors["up"][1].shape[1]
        self.residual_rank = min(max(1, residual_rank), self.rank)
        self.scale_amplitude = scale_amplitude
        self.basis_count = max(1, basis_count if generator in {"mixture", "expert_residual"} else 1)

        def make_bank(name: str, side: int) -> nn.Parameter:
            base = factors[name][side].to(dtype=dtype)
            if generator != "mixture" or self.basis_count == 1:
                return nn.Parameter(base)
            gen = torch.Generator(device="cpu").manual_seed(17 + len(name) * 31 + side)
            banks = []
            for index in range(self.basis_count):
                noise = torch.randn(base.shape, generator=gen, dtype=torch.float32).to(dtype=dtype)
                banks.append(base + (basis_noise * (index + 1)) * noise)
            return nn.Parameter(torch.stack(banks, dim=0))

        self.up_u = make_bank("up", 0)
        self.up_v = make_bank("up", 1)
        self.gate_u = make_bank("gate", 0)
        self.gate_v = make_bank("gate", 1)
        self.down_u = make_bank("down", 0)
        self.down_v = make_bank("down", 1)
        hidden = generator_hidden or min(256, max(32, self.d // 8))
        if generator != "none":
            if generator == "token_rank_mixer":
                out_dim = 3 * self.rank * self.rank
            else:
                out_dim = 6 * self.rank + (self.basis_count if generator in {"mixture", "expert_residual"} else 0)
            self.generator = nn.Sequential(
                nn.Linear(self.d, hidden, dtype=torch.float32),
                nn.SiLU(),
                nn.Linear(hidden, out_dim, dtype=torch.float32),
            )
        else:
            self.generator = None
        if generator in {"token_residual", "mixture"}:
            self.residual_gate_a = nn.Linear(self.d, self.residual_rank, bias=False, dtype=dtype)
            self.residual_gate_b = nn.Linear(self.residual_rank, self.m, bias=False, dtype=dtype)
            self.residual_up_a = nn.Linear(self.d, self.residual_rank, bias=False, dtype=dtype)
            self.residual_up_b = nn.Linear(self.residual_rank, self.m, bias=False, dtype=dtype)
            self.residual_down_a = nn.Linear(self.m, self.residual_rank, bias=False, dtype=dtype)
            self.residual_down_b = nn.Linear(self.residual_rank, self.d, bias=False, dtype=dtype)
            self._init_residual()
        else:
            self.residual_gate_a = None
            self.residual_gate_b = None
            self.residual_up_a = None
            self.residual_up_b = None
            self.residual_down_a = None
            self.residual_down_b = None
        if generator == "expert_residual":
            self.expert_gate_a = nn.Parameter(torch.empty(self.basis_count, self.d, self.residual_rank, dtype=dtype))
            self.expert_gate_b = nn.Parameter(torch.empty(self.basis_count, self.residual_rank, self.m, dtype=dtype))
            self.expert_up_a = nn.Parameter(torch.empty(self.basis_count, self.d, self.residual_rank, dtype=dtype))
            self.expert_up_b = nn.Parameter(torch.empty(self.basis_count, self.residual_rank, self.m, dtype=dtype))
            self.expert_down_a = nn.Parameter(torch.empty(self.basis_count, self.m, self.residual_rank, dtype=dtype))
            self.expert_down_b = nn.Parameter(torch.empty(self.basis_count, self.residual_rank, self.d, dtype=dtype))
            self._init_experts()
        else:
            self.expert_gate_a = None
            self.expert_gate_b = None
            self.expert_up_a = None
            self.expert_up_b = None
            self.expert_down_a = None
            self.expert_down_b = None

    def _init_residual(self) -> None:
        modules = [
            self.residual_gate_a,
            self.residual_gate_b,
            self.residual_up_a,
            self.residual_up_b,
            self.residual_down_a,
            self.residual_down_b,
        ]
        for module in modules:
            assert module is not None
            nn.init.normal_(module.weight, mean=0.0, std=1e-3)

    def _init_experts(self) -> None:
        for param in [
            self.expert_gate_a,
            self.expert_gate_b,
            self.expert_up_a,
            self.expert_up_b,
            self.expert_down_a,
            self.expert_down_b,
        ]:
            assert param is not None
            nn.init.normal_(param, mean=0.0, std=1e-3)

    def _factors(self, x: torch.Tensor) -> tuple[torch.Tensor, ...]:
        if self.generator is None:
            return self.up_u, self.up_v, self.gate_u, self.gate_v, self.down_u, self.down_v
        context = x.float() if self.generator_mode == "token_scale" else x.float().mean(dim=(0, 1))
        generated = self.generator(context)
        if self.generator_mode in {"mixture", "expert_residual"}:
            scale_logits = generated[: 6 * self.rank]
            route_logits = generated[6 * self.rank :]
            alpha = torch.softmax(route_logits.float(), dim=0).to(dtype=x.dtype)
            self._last_alpha = alpha

            if self.generator_mode == "mixture":
                def blend(bank: torch.Tensor) -> torch.Tensor:
                    view_shape = (self.basis_count,) + (1,) * (bank.ndim - 1)
                    return torch.sum(bank * alpha.view(view_shape), dim=0)

                up_u = blend(self.up_u)
                up_v = blend(self.up_v)
                gate_u = blend(self.gate_u)
                gate_v = blend(self.gate_v)
                down_u = blend(self.down_u)
                down_v = blend(self.down_v)
            else:
                up_u, up_v, gate_u, gate_v, down_u, down_v = (
                    self.up_u,
                    self.up_v,
                    self.gate_u,
                    self.gate_v,
                    self.down_u,
                    self.down_v,
                )
        else:
            scale_logits = generated
            up_u, up_v, gate_u, gate_v, down_u, down_v = (
                self.up_u,
                self.up_v,
                self.gate_u,
                self.gate_v,
                self.down_u,
                self.down_v,
            )
        scales = 1.0 + self.scale_amplitude * torch.tanh(scale_logits).to(dtype=x.dtype)
        su, sv, sg, sgv, sd, sdv = scales.chunk(6, dim=-1)
        if self.generator_mode == "token_scale":
            return (
                self.up_u.unsqueeze(0).unsqueeze(0) * su.unsqueeze(-2),
                self.up_v.unsqueeze(0).unsqueeze(0) * sv.unsqueeze(-1),
                self.gate_u.unsqueeze(0).unsqueeze(0) * sg.unsqueeze(-2),
                self.gate_v.unsqueeze(0).unsqueeze(0) * sgv.unsqueeze(-1),
                self.down_u.unsqueeze(0).unsqueeze(0) * sd.unsqueeze(-2),
                self.down_v.unsqueeze(0).unsqueeze(0) * sdv.unsqueeze(-1),
            )
        return (
            up_u * su.view(1, -1),
            up_v * sv.view(-1, 1),
            gate_u * sg.view(1, -1),
            gate_v * sgv.view(-1, 1),
            down_u * sd.view(1, -1),
            down_v * sdv.view(-1, 1),
        )

    def _expert_project(self, x: torch.Tensor, a: torch.Tensor, b: torch.Tensor, alpha: torch.Tensor) -> torch.Tensor:
        expert_outputs = []
        for index in range(self.basis_count):
            expert_outputs.append((x @ a[index]) @ b[index])
        stacked = torch.stack(expert_outputs, dim=0)
        return torch.sum(stacked * alpha.view(self.basis_count, 1, 1, 1), dim=0)

    def _rank_mixers(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        assert self.generator is not None
        logits = self.generator(x.float()).view(*x.shape[:2], 3, self.rank, self.rank)
        delta = self.scale_amplitude * torch.tanh(logits).to(dtype=x.dtype)
        eye = torch.eye(self.rank, device=x.device, dtype=x.dtype).view(1, 1, 1, self.rank, self.rank)
        mixers = eye + delta
        return mixers[:, :, 0], mixers[:, :, 1], mixers[:, :, 2]

    def _mix_rank(self, z: torch.Tensor, mixer: torch.Tensor) -> torch.Tensor:
        return torch.matmul(z.unsqueeze(-2), mixer).squeeze(-2)

    def _forward_token_rank_mixer(self, x: torch.Tensor) -> torch.Tensor:
        mix_up, mix_gate, mix_down = self._rank_mixers(x)
        up = self._mix_rank(x @ self.up_u, mix_up) @ self.up_v
        gate = self._mix_rank(x @ self.gate_u, mix_gate) @ self.gate_v
        hidden = torch.nn.functional.silu(gate) * up
        return self._mix_rank(hidden @ self.down_u, mix_down) @ self.down_v

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.generator_mode == "token_rank_mixer":
            return self._forward_token_rank_mixer(x)
        up_u, up_v, gate_u, gate_v, down_u, down_v = self._factors(x)
        if self.generator_mode == "token_scale":
            up = torch.matmul(torch.matmul(x.unsqueeze(-2), up_u), up_v).squeeze(-2)
            gate = torch.matmul(torch.matmul(x.unsqueeze(-2), gate_u), gate_v).squeeze(-2)
        else:
            up = (x @ up_u) @ up_v
            gate = (x @ gate_u) @ gate_v
        if self.generator_mode in {"token_residual", "mixture"}:
            assert self.residual_gate_a is not None
            assert self.residual_gate_b is not None
            assert self.residual_up_a is not None
            assert self.residual_up_b is not None
            gate = gate + self.residual_gate_b(torch.nn.functional.silu(self.residual_gate_a(x)))
            up = up + self.residual_up_b(torch.nn.functional.silu(self.residual_up_a(x)))
        if self.generator_mode == "expert_residual":
            alpha = getattr(self, "_last_alpha")
            assert self.expert_gate_a is not None
            assert self.expert_gate_b is not None
            assert self.expert_up_a is not None
            assert self.expert_up_b is not None
            gate = gate + self._expert_project(x, self.expert_gate_a, self.expert_gate_b, alpha)
            up = up + self._expert_project(x, self.expert_up_a, self.expert_up_b, alpha)
        hidden = torch.nn.functional.silu(gate) * up
        if self.generator_mode == "token_scale":
            out = torch.matmul(torch.matmul(hidden.unsqueeze(-2), down_u), down_v).squeeze(-2)
        else:
            out = (hidden @ down_u) @ down_v
        if self.generator_mode in {"token_residual", "mixture"}:
            assert self.residual_down_a is not None
            assert self.residual_down_b is not None
            out = out + self.residual_down_b(torch.nn.functional.silu(self.residual_down_a(hidden)))
        if self.generator_mode == "expert_residual":
            alpha = getattr(self, "_last_alpha")
            assert self.expert_down_a is not None
            assert self.expert_down_b is not None
            out = out + self._expert_project(hidden, self.expert_down_a, self.expert_down_b, alpha)
        return out


@dataclass
class Metrics:
    mse: float
    relative_mse: float
    cosine: float


def reduce_mean(value: torch.Tensor) -> torch.Tensor:
    if dist.is_initialized():
        dist.all_reduce(value, op=dist.ReduceOp.SUM)
        value /= dist.get_world_size()
    return value


def make_batch(batch: int, seq: int, d: int, device: torch.device, dtype: torch.dtype, seed: int) -> torch.Tensor:
    gen = torch.Generator(device="cpu").manual_seed(seed)
    x = torch.randn(batch, seq, d, generator=gen, dtype=torch.float32)
    # Mixture amplitudes make the quality test less tied to a single Gaussian shell.
    scales = torch.empty(batch, seq, 1).uniform_(0.5, 1.5, generator=gen)
    return (x * scales).to(device=device, dtype=dtype)


def sample_batch(args: argparse.Namespace, device: torch.device, dtype: torch.dtype, seed: int) -> torch.Tensor:
    activation_cache = getattr(args, "_activation_cache", None)
    if activation_cache is None:
        return make_batch(args.batch, args.seq, args.d, device, dtype, seed)

    gen = torch.Generator(device="cpu").manual_seed(seed)
    total, cache_seq, _ = activation_cache.shape
    indices = torch.randint(0, total, (args.batch,), generator=gen)
    x = activation_cache.index_select(0, indices)
    if args.seq < cache_seq:
        start = int(torch.randint(0, cache_seq - args.seq + 1, (1,), generator=gen).item())
        x = x[:, start : start + args.seq, :]
    elif args.seq > cache_seq:
        repeats = math.ceil(args.seq / cache_seq)
        x = x.repeat(1, repeats, 1)[:, : args.seq, :]
    return x.to(device=device, dtype=dtype)


@torch.no_grad()
def evaluate(model: nn.Module, teacher: DenseTeacher, args: argparse.Namespace, device: torch.device, dtype: torch.dtype, rank: int) -> Metrics:
    model.eval()
    sum_mse = torch.zeros((), device=device, dtype=torch.float32)
    sum_target = torch.zeros((), device=device, dtype=torch.float32)
    sum_dot = torch.zeros((), device=device, dtype=torch.float32)
    sum_pred_norm = torch.zeros((), device=device, dtype=torch.float32)
    sum_target_norm = torch.zeros((), device=device, dtype=torch.float32)
    for step in range(args.eval_batches):
        x = sample_batch(args, device, dtype, args.seed + 100_000 + step * 997 + rank * 17)
        target = teacher(x).float()
        pred = model(x).float()
        diff = pred - target
        sum_mse += diff.square().mean()
        sum_target += target.square().mean()
        sum_dot += (pred * target).sum()
        sum_pred_norm += pred.square().sum()
        sum_target_norm += target.square().sum()
    values = torch.stack([sum_mse, sum_target, sum_dot, sum_pred_norm, sum_target_norm])
    values = reduce_mean(values)
    mse = values[0] / args.eval_batches
    target_power = (values[1] / args.eval_batches).clamp_min(1e-12)
    cosine = values[2] / (torch.sqrt(values[3].clamp_min(1e-12)) * torch.sqrt(values[4].clamp_min(1e-12)))
    return Metrics(float(mse.item()), float((mse / target_power).item()), float(cosine.item()))


def train_student(name: str, model: nn.Module, teacher: DenseTeacher, args: argparse.Namespace, device: torch.device, dtype: torch.dtype, rank: int) -> dict[str, Any]:
    if dist.is_initialized():
        model = torch.nn.parallel.DistributedDataParallel(
            model,
            device_ids=[int(os.environ["LOCAL_RANK"])] if device.type in {"npu", "cuda"} else None,
            find_unused_parameters=False,
        )
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    losses: list[float] = []
    t0 = datetime.now(timezone.utc)
    for step in range(args.steps):
        model.train()
        x = sample_batch(args, device, dtype, args.seed + step * 1297 + rank * 53)
        with torch.no_grad():
            target = teacher(x).float()
        pred = model(x).float()
        loss = torch.nn.functional.mse_loss(pred, target)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
        opt.step()
        reduced = reduce_mean(loss.detach().float().clone())
        if rank == 0 and (step == 0 or (step + 1) % args.log_every == 0 or step + 1 == args.steps):
            losses.append(float(reduced.item()))
            print(json.dumps({"event": "train", "student": name, "step": step + 1, "loss": losses[-1]}), flush=True)
    sync_device()
    elapsed = (datetime.now(timezone.utc) - t0).total_seconds()
    raw_model = model.module if hasattr(model, "module") else model
    metrics = evaluate(raw_model, teacher, args, device, dtype, rank)
    row = {
        "student": name,
        "train_loss_trace": losses,
        "elapsed_s": round(elapsed, 3),
        "metrics": asdict(metrics),
        "parameter_bytes": parameter_bytes(raw_model),
        "parameter_mib": round(parameter_bytes(raw_model) / MIB, 3),
    }
    if rank == 0 and args.save_students:
        checkpoint_dir = Path(args.outdir) / "checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = checkpoint_dir / f"{name}.pt"
        torch.save(
            {
                "student": name,
                "state_dict": {key: value.detach().cpu() for key, value in raw_model.state_dict().items()},
                "init": {
                    "d": raw_model.d,
                    "m": raw_model.m,
                    "rank": raw_model.rank,
                    "generator_mode": raw_model.generator_mode,
                    "residual_rank": raw_model.residual_rank,
                    "scale_amplitude": raw_model.scale_amplitude,
                    "basis_count": raw_model.basis_count,
                },
                "config": {
                    "layer": args.layer,
                    "dtype": str(dtype).replace("torch.", ""),
                    "activation_source": args.activation_source,
                    "steps": args.steps,
                    "eval_batches": args.eval_batches,
                },
                "metrics": asdict(metrics),
            },
            checkpoint_path,
        )
        row["checkpoint"] = str(checkpoint_path)
    return row


def cache_key(args: argparse.Namespace, world_size: int) -> Path:
    source = "synthetic" if not args.model_dir else re.sub(r"[^A-Za-z0-9_.-]+", "_", args.model_dir.strip("/"))
    ranks = "-".join(str(r) for r in args.ranks)
    return Path(tempfile.gettempdir()) / f"mwg_quality_cache_v2_{source}_layer{args.layer}_r{ranks}_seed{args.seed}_w{world_size}.pt"


def load_or_build_teacher_and_factors(args: argparse.Namespace, rank: int, world_size: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, dict[str, str], dict[int, dict[str, tuple[torch.Tensor, torch.Tensor]]], dict[int, dict[str, float]]]:
    cache_path = cache_key(args, world_size)
    done_path = cache_path.with_suffix(cache_path.suffix + ".done")
    if world_size > 1 and rank != 0:
        while not done_path.exists():
            time.sleep(1.0)
        payload = safe_torch_load(cache_path)
        args.d = int(payload["d"])
        args.m = int(payload["m"])
        barrier()
        return (
            payload["gate"],
            payload["up"],
            payload["down"],
            payload["teacher_meta"],
            payload["factors_by_rank"],
            payload["energy_by_rank"],
        )

    if args.model_dir:
        gate, up, down, teacher_meta = find_ffn_triplet(Path(args.model_dir), args.layer)
        args.d = up.shape[0]
        args.m = up.shape[1]
    else:
        gate, up, down, teacher_meta = make_synthetic_teacher(args.d, args.m, args.seed)

    factors_by_rank: dict[int, dict[str, tuple[torch.Tensor, torch.Tensor]]] = {}
    energy_by_rank: dict[int, dict[str, float]] = {}
    for r in args.ranks:
        rank_factors: dict[str, tuple[torch.Tensor, torch.Tensor]] = {}
        rank_energy: dict[str, float] = {}
        for name, weight in [("gate", gate), ("up", up), ("down", down)]:
            left, right, energy = svd_factors(weight, r, method=args.svd_method, oversample=args.svd_oversample, niter=args.svd_niter)
            rank_factors[name] = (left, right)
            rank_energy[name] = round(energy, 6)
        factors_by_rank[r] = rank_factors
        energy_by_rank[r] = rank_energy
        if rank == 0:
            print(json.dumps({"event": "svd_done", "rank": r, "energy": rank_energy}), flush=True)

    if world_size > 1 and rank == 0:
        tmp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
        done_path.unlink(missing_ok=True)
        torch.save(
            {
                "d": args.d,
                "m": args.m,
                "gate": gate,
                "up": up,
                "down": down,
                "teacher_meta": teacher_meta,
                "factors_by_rank": factors_by_rank,
                "energy_by_rank": energy_by_rank,
            },
            tmp_path,
        )
        tmp_path.replace(cache_path)
        done_path.write_text("ok\n", encoding="utf-8")
    barrier()
    return gate, up, down, teacher_meta, factors_by_rank, energy_by_rank


def run(args: argparse.Namespace) -> dict[str, Any] | None:
    device, rank, local_rank, world_size, backend = setup_runtime()
    dtype = dtype_from_name(args.dtype, device)
    torch.manual_seed(args.seed + rank)

    gate, up, down, teacher_meta, factors_by_rank, energy_by_rank = load_or_build_teacher_and_factors(args, rank, world_size)

    teacher = DenseTeacher(gate, up, down, dtype=dtype).to(device).eval()
    activation_cache = capture_text_activations(args, device, rank, world_size)
    setattr(args, "_activation_cache", activation_cache)
    if rank == 0:
        print(json.dumps({"event": "teacher_loaded", "d": args.d, "m": args.m, "meta": teacher_meta}), flush=True)
    output: dict[str, Any] = {
        "created_at": now_tag(),
        "env": env_payload(device, local_rank, world_size, backend),
        "teacher": teacher_meta,
        "config": {
            "d": args.d,
            "m": args.m,
            "ranks": args.ranks,
            "batch": args.batch,
            "seq": args.seq,
            "steps": args.steps,
            "eval_batches": args.eval_batches,
            "dtype": str(dtype).replace("torch.", ""),
            "lr": args.lr,
            "weight_decay": args.weight_decay,
            "students": args.students,
            "generator_hidden": args.generator_hidden,
            "residual_rank": args.residual_rank,
            "scale_amplitude": args.scale_amplitude,
            "activation_source": args.activation_source,
            "activation_cache_shape": None if activation_cache is None else list(activation_cache.shape),
            "basis_count": args.basis_count,
            "basis_noise": args.basis_noise,
        },
        "dense_parameter_mib": round(dense_bytes(args.d, args.m, dtype) / MIB, 3),
        "results": {},
    }

    for r in args.ranks:
        static = LowRankFFN(factors_by_rank[r], dtype=dtype, generator="none").to(device)
        for param in static.parameters():
            param.requires_grad_(False)
        static_metrics = evaluate(static, teacher, args, device, dtype, rank)
        if rank == 0:
            output["results"][f"static_svd_r{r}"] = {
                "rank": r,
                "svd_energy": energy_by_rank[r],
                "metrics": asdict(static_metrics),
                "descriptor_mib": round(descriptor_bytes(args.d, args.m, r, dtype) / MIB, 3),
                "traffic_reduction_x": round(dense_bytes(args.d, args.m, dtype) / max(descriptor_bytes(args.d, args.m, r, dtype), 1), 3),
            }
        del static

        rows: list[dict[str, Any]] = []
        if "persistent" in args.students:
            persistent = LowRankFFN(factors_by_rank[r], dtype=dtype, generator="none").to(device)
            rows.append(train_student(f"persistent_low_rank_r{r}", persistent, teacher, args, device, dtype, rank))
            del persistent
            barrier()
        if "rank_scale" in args.students:
            mwg = LowRankFFN(
                factors_by_rank[r],
                dtype=dtype,
                generator="rank_scale",
                generator_hidden=args.generator_hidden,
                scale_amplitude=args.scale_amplitude,
            ).to(device)
            rows.append(train_student(f"mwg_ephemeral_r{r}", mwg, teacher, args, device, dtype, rank))
            del mwg
            barrier()
        if "token_scale" in args.students:
            token_scale = LowRankFFN(
                factors_by_rank[r],
                dtype=dtype,
                generator="token_scale",
                generator_hidden=args.generator_hidden,
                scale_amplitude=args.scale_amplitude,
            ).to(device)
            rows.append(train_student(f"mwg_token_scale_r{r}", token_scale, teacher, args, device, dtype, rank))
            del token_scale
            barrier()
        if "token_rank_mixer" in args.students:
            token_rank_mixer = LowRankFFN(
                factors_by_rank[r],
                dtype=dtype,
                generator="token_rank_mixer",
                generator_hidden=args.generator_hidden,
                scale_amplitude=args.scale_amplitude,
            ).to(device)
            rows.append(train_student(f"mwg_token_rank_mixer_r{r}", token_rank_mixer, teacher, args, device, dtype, rank))
            del token_rank_mixer
            barrier()
        if "token_residual" in args.students:
            residual = LowRankFFN(
                factors_by_rank[r],
                dtype=dtype,
                generator="token_residual",
                generator_hidden=args.generator_hidden,
                residual_rank=args.residual_rank,
                scale_amplitude=args.scale_amplitude,
            ).to(device)
            rows.append(train_student(f"mwg_token_residual_r{r}", residual, teacher, args, device, dtype, rank))
            del residual
            barrier()
        if "mixture" in args.students:
            mixture = LowRankFFN(
                factors_by_rank[r],
                dtype=dtype,
                generator="mixture",
                generator_hidden=args.generator_hidden,
                residual_rank=args.residual_rank,
                scale_amplitude=args.scale_amplitude,
                basis_count=args.basis_count,
                basis_noise=args.basis_noise,
            ).to(device)
            rows.append(train_student(f"mwg_mixture_r{r}", mixture, teacher, args, device, dtype, rank))
            del mixture
            barrier()
        if "expert_residual" in args.students:
            expert = LowRankFFN(
                factors_by_rank[r],
                dtype=dtype,
                generator="expert_residual",
                generator_hidden=args.generator_hidden,
                residual_rank=args.residual_rank,
                scale_amplitude=args.scale_amplitude,
                basis_count=args.basis_count,
                basis_noise=args.basis_noise,
            ).to(device)
            rows.append(train_student(f"mwg_expert_residual_r{r}", expert, teacher, args, device, dtype, rank))
            del expert
            barrier()
        if rank == 0:
            for row in rows:
                row["rank"] = r
                row["descriptor_mib"] = round(descriptor_bytes(args.d, args.m, r, dtype) / MIB, 3)
                row["traffic_reduction_x"] = round(dense_bytes(args.d, args.m, dtype) / max(descriptor_bytes(args.d, args.m, r, dtype), 1), 3)
                output["results"][row["student"]] = row
        barrier()

    if dist.is_initialized():
        dist.destroy_process_group()
    return output if rank == 0 else None


def write_outputs(payload: dict[str, Any], outdir: Path) -> tuple[Path, Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    tag = payload["created_at"]
    json_path = outdir / f"mwg_quality_distillation_{tag}.json"
    md_path = outdir / f"mwg_quality_distillation_{tag}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# MWG-EW Quality Distillation",
        "",
        f"Created: `{tag}`",
        f"World size: `{payload['env'].get('world_size')}`",
        f"Device: `{payload['env'].get('device_type')}`",
        f"Teacher: `{payload['teacher']}`",
        "",
        "| Method | Rank | Rel. MSE | Cosine | Params MiB | Descriptor MiB | Traffic red. |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for key, row in payload["results"].items():
        metrics = row["metrics"]
        lines.append(
            f"| {key} | {row.get('rank')} | {metrics['relative_mse']:.6g} | "
            f"{metrics['cosine']:.6f} | {row.get('parameter_mib', '')} | "
            f"{row.get('descriptor_mib')} | {row.get('traffic_reduction_x')} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default="")
    parser.add_argument("--layer", type=int, default=None)
    parser.add_argument("--d", type=int, default=256)
    parser.add_argument("--m", type=int, default=768)
    parser.add_argument("--ranks", type=parse_ints, default=[16, 32, 64])
    parser.add_argument("--svd-method", choices=["exact", "pca_lowrank"], default="exact")
    parser.add_argument("--svd-oversample", type=int, default=16)
    parser.add_argument("--svd-niter", type=int, default=2)
    parser.add_argument("--batch", type=int, default=2)
    parser.add_argument("--seq", type=int, default=64)
    parser.add_argument("--steps", type=int, default=80)
    parser.add_argument("--eval-batches", type=int, default=8)
    parser.add_argument("--log-every", type=int, default=20)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--students", type=lambda value: [item.strip() for item in value.split(",") if item.strip()], default=["persistent", "rank_scale", "token_scale", "token_rank_mixer", "token_residual"])
    parser.add_argument("--generator-hidden", type=int, default=None)
    parser.add_argument("--residual-rank", type=int, default=8)
    parser.add_argument("--scale-amplitude", type=float, default=0.05)
    parser.add_argument("--basis-count", type=int, default=4)
    parser.add_argument("--basis-noise", type=float, default=0.01)
    parser.add_argument("--activation-source", choices=["gaussian", "text"], default="gaussian")
    parser.add_argument("--texts", type=parse_texts, default=[])
    parser.add_argument("--activation-max-batches", type=int, default=32)
    parser.add_argument("--activation-text-batch", type=int, default=2)
    parser.add_argument("--activation-seq", type=int, default=256)
    parser.add_argument("--activation-log-every", type=int, default=8)
    parser.add_argument("--save-students", action="store_true")
    parser.add_argument("--dtype", choices=["auto", "fp16", "bf16", "fp32"], default="auto")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--outdir", default="results")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    payload = run(args)
    if payload is not None:
        json_path, md_path = write_outputs(payload, Path(args.outdir))
        print(json.dumps({"event": "saved", "json": str(json_path), "markdown": str(md_path)}, indent=2), flush=True)


if __name__ == "__main__":
    main()
