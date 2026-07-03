"""Distributed MWG-EW Transformer FFN benchmark.

The benchmark is intentionally self-contained: it does not require pretrained
weights or datasets. It measures the systems quantities that matter for the
paper draft:

  * dense gated-FFN latency
  * MWG-EW associative low-rank latency
  * trainable parameter bytes and descriptor traffic estimates
  * distributed all-reduce latency for dense vs MWG-EW gradient volumes

Run locally:
    python3 experiments/mwg_transformer_ASI3_benchmark.py --preset tiny

Run a fast remote smoke test on ASI2:
    python3 experiments/mwg_transformer_ASI3_benchmark.py --preset ASI2_smoke --env-label ASI2

Run the full ASI2 setting:
    ASCEND_RT_VISIBLE_DEVICES=0,1,2,3 python3 -m torch.distributed.run \
      --nproc_per_node=4 experiments/mwg_transformer_ASI3_benchmark.py \
      --preset ASI2_large --env-label ASI2
"""

from __future__ import annotations

import argparse
import json
import math
import os
import socket
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

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


def parse_rank_list(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def setup_runtime() -> tuple[torch.device, int, int, int, str]:
    rank = int(os.environ.get("RANK", "0"))
    local_rank = int(os.environ.get("LOCAL_RANK", "0"))
    world_size = int(os.environ.get("WORLD_SIZE", "1"))

    if HAS_NPU:
        if local_rank >= torch.npu.device_count():
            raise RuntimeError(
                f"LOCAL_RANK={local_rank} but torch.npu.device_count()={torch.npu.device_count()} "
                f"with ASCEND_RT_VISIBLE_DEVICES={os.environ.get('ASCEND_RT_VISIBLE_DEVICES', '')!r}"
            )
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
        dist.init_process_group(backend=backend, timeout=timedelta(minutes=45))

    return device, rank, local_rank, world_size, backend


def sync_device() -> None:
    if HAS_NPU:
        torch.npu.synchronize()
    elif HAS_CUDA:
        torch.cuda.synchronize()


def barrier() -> None:
    if dist.is_initialized():
        dist.barrier()


def empty_cache() -> None:
    if HAS_NPU:
        torch.npu.empty_cache()
    elif HAS_CUDA:
        torch.cuda.empty_cache()


def dtype_from_name(name: str, device: torch.device) -> torch.dtype:
    if name == "auto":
        return torch.float16 if device.type in {"npu", "cuda"} else torch.float32
    if name == "fp16":
        return torch.float16
    if name == "bf16":
        return torch.bfloat16
    if name == "fp32":
        return torch.float32
    raise ValueError(f"unknown dtype: {name}")


def capture_env(device: torch.device, local_rank: int, world_size: int, backend: str) -> dict[str, Any]:
    env: dict[str, Any] = {
        "hostname": socket.gethostname(),
        "python": sys.version.split()[0],
        "torch": torch.__version__,
        "backend": backend,
        "device_type": device.type,
        "local_rank": local_rank,
        "world_size": world_size,
        "ascend_rt_visible_devices": os.environ.get("ASCEND_RT_VISIBLE_DEVICES", ""),
        "pytorch_npu_alloc_conf": os.environ.get("PYTORCH_NPU_ALLOC_CONF", ""),
    }
    if HAS_NPU:
        env["torch_npu"] = getattr(torch_npu, "__version__", "unknown")
        env["npu_count"] = torch.npu.device_count()
        env["npu_available"] = torch.npu.is_available()
        env["current_npu_device"] = torch.npu.current_device()
        try:
            env["device_name"] = torch.npu.get_device_name(local_rank)
        except Exception:
            env["device_name"] = "npu"
        names = []
        for index in range(torch.npu.device_count()):
            try:
                names.append(torch.npu.get_device_name(index))
            except Exception as exc:
                names.append(f"error:{exc!r}")
        env["npu_device_names"] = names
        try:
            props = torch_npu.npu.get_device_properties(local_rank)  # type: ignore[attr-defined]
            env["memory_gib"] = round(props.total_memory / (1024**3), 2)
        except Exception:
            pass
    elif HAS_CUDA:
        env["cuda"] = torch.version.cuda
        env["cuda_count"] = torch.cuda.device_count()
        env["device_name"] = torch.cuda.get_device_name(local_rank)
        props = torch.cuda.get_device_properties(local_rank)
        env["memory_gib"] = round(props.total_memory / (1024**3), 2)
    else:
        env["device_name"] = "cpu"
    return env


def parameter_bytes(module: nn.Module) -> int:
    return sum(p.numel() * p.element_size() for p in module.parameters())


def tensor_bytes(numel: int, dtype: torch.dtype) -> int:
    return numel * torch.empty((), dtype=dtype).element_size()


def dense_ffn_bytes(d: int, m: int, elem_bytes: int) -> int:
    return 3 * d * m * elem_bytes


def mwg_descriptor_bytes(d: int, m: int, rank: int, elem_bytes: int) -> int:
    return 3 * rank * (d + m) * elem_bytes


class DenseGatedFFN(nn.Module):
    def __init__(self, d: int, m: int, dtype: torch.dtype):
        super().__init__()
        self.up = nn.Linear(d, m, bias=False, dtype=dtype)
        self.gate = nn.Linear(d, m, bias=False, dtype=dtype)
        self.down = nn.Linear(m, d, bias=False, dtype=dtype)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.down(torch.nn.functional.silu(self.gate(x)) * self.up(x))


class EphemeralMetaWeightFFN(nn.Module):
    """Conditional low-rank FFN used for benchmarkable MWG-EW behavior.

    The base rank factors model the generated descriptor bank. A lightweight
    context head emits rank-channel scales, standing in for tile-local
    conditional generation without allocating a full dense matrix.
    """

    def __init__(self, d: int, m: int, rank: int, dtype: torch.dtype, condition: bool = True):
        super().__init__()
        self.d = d
        self.m = m
        self.rank = rank
        self.condition = condition

        def param(*shape: int) -> nn.Parameter:
            scale = 1.0 / math.sqrt(max(shape[0], 1))
            return nn.Parameter(torch.randn(*shape, dtype=dtype) * scale)

        self.up_u = param(d, rank)
        self.up_v = param(rank, m)
        self.gate_u = param(d, rank)
        self.gate_v = param(rank, m)
        self.down_u = param(m, rank)
        self.down_v = param(rank, d)

        hidden = min(256, max(32, d // 8))
        self.generator = nn.Sequential(
            nn.Linear(d, hidden, bias=True, dtype=torch.float32),
            nn.SiLU(),
            nn.Linear(hidden, 6 * rank, bias=True, dtype=torch.float32),
        )

    def _scaled_factors(self, x: torch.Tensor) -> tuple[torch.Tensor, ...]:
        if not self.condition:
            return self.up_u, self.up_v, self.gate_u, self.gate_v, self.down_u, self.down_v

        context = x.float().mean(dim=(0, 1))
        scales = 1.0 + 0.01 * torch.tanh(self.generator(context)).to(dtype=x.dtype)
        su, sv, sg, sgv, sd, sdv = scales.chunk(6)
        return (
            self.up_u * su.view(1, -1),
            self.up_v * sv.view(-1, 1),
            self.gate_u * sg.view(1, -1),
            self.gate_v * sgv.view(-1, 1),
            self.down_u * sd.view(1, -1),
            self.down_v * sdv.view(-1, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        up_u, up_v, gate_u, gate_v, down_u, down_v = self._scaled_factors(x)
        up = (x @ up_u) @ up_v
        gate = (x @ gate_u) @ gate_v
        hidden = torch.nn.functional.silu(gate) * up
        return (hidden @ down_u) @ down_v


@dataclass
class Timing:
    mean_ms: float
    median_ms: float
    min_ms: float
    max_ms: float
    iters: int
    per_rank: list[dict[str, Any]]


def summarize_times(times: list[float]) -> dict[str, float]:
    return {
        "mean_ms": round(statistics.mean(times), 4),
        "median_ms": round(statistics.median(times), 4),
        "min_ms": round(min(times), 4),
        "max_ms": round(max(times), 4),
    }


def gather_rank_stats(local: dict[str, Any], rank: int) -> list[dict[str, Any]]:
    if not dist.is_initialized():
        return [local]
    gathered: list[dict[str, Any] | None] = [None for _ in range(dist.get_world_size())]
    dist.all_gather_object(gathered, local)
    return [item for item in gathered if item is not None] if rank == 0 else []


def time_loop(fn: Callable[[], Any], warmup: int, iters: int, rank: int) -> Timing | None:
    for _ in range(warmup):
        fn()
    sync_device()
    barrier()

    times: list[float] = []
    for _ in range(iters):
        barrier()
        sync_device()
        t0 = time.perf_counter()
        fn()
        sync_device()
        barrier()
        times.append((time.perf_counter() - t0) * 1000.0)

    local = {"rank": rank, **summarize_times(times)}
    per_rank = gather_rank_stats(local, rank)
    if rank != 0:
        return None

    rank_means = [item["mean_ms"] for item in per_rank]
    return Timing(
        mean_ms=round(max(rank_means), 4),
        median_ms=round(statistics.median(rank_means), 4),
        min_ms=round(min(rank_means), 4),
        max_ms=round(max(rank_means), 4),
        iters=iters,
        per_rank=per_rank,
    )


def bench_forward(model: nn.Module, x: torch.Tensor, warmup: int, iters: int, rank: int) -> Timing | None:
    model.eval()

    def step() -> None:
        with torch.no_grad():
            y = model(x)
            if y.numel() == 0:
                raise RuntimeError("empty output")

    return time_loop(step, warmup, iters, rank)


def bench_train(model: nn.Module, x: torch.Tensor, warmup: int, iters: int, rank: int) -> Timing | None:
    model.train()

    def step() -> None:
        model.zero_grad(set_to_none=True)
        y = model(x)
        loss = y.float().square().mean()
        loss.backward()

    return time_loop(step, warmup, iters, rank)


def bench_allreduce(byte_count: int, dtype: torch.dtype, device: torch.device, warmup: int, iters: int, rank: int) -> Timing | None:
    if not dist.is_initialized() or dist.get_world_size() == 1:
        local = {
            "rank": rank,
            "mean_ms": 0.0,
            "median_ms": 0.0,
            "min_ms": 0.0,
            "max_ms": 0.0,
            "note": "single-process run",
        }
        per_rank = gather_rank_stats(local, rank)
        return Timing(0.0, 0.0, 0.0, 0.0, 0, per_rank) if rank == 0 else None

    elem_bytes = torch.empty((), dtype=dtype).element_size()
    numel = max(1, math.ceil(byte_count / elem_bytes))
    buf = torch.ones(numel, dtype=dtype, device=device)

    def step() -> None:
        dist.all_reduce(buf, op=dist.ReduceOp.SUM)

    try:
        return time_loop(step, warmup, iters, rank)
    finally:
        del buf
        empty_cache()


def make_input(batch: int, seq: int, d: int, dtype: torch.dtype, device: torch.device) -> torch.Tensor:
    return torch.randn(batch, seq, d, dtype=dtype, device=device)


def timing_to_dict(value: Timing | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return asdict(value)


def tokens_per_second(tokens: int, timing: Timing | None) -> float | None:
    if timing is None or timing.mean_ms <= 0:
        return None
    return round(tokens * 1000.0 / timing.mean_ms, 2)


def run_benchmarks(args: argparse.Namespace) -> dict[str, Any] | None:
    device, rank, local_rank, world_size, backend = setup_runtime()
    dtype = dtype_from_name(args.dtype, device)
    elem_bytes = torch.empty((), dtype=dtype).element_size()

    torch.manual_seed(args.seed + rank)
    if device.type in {"npu", "cuda"}:
        torch.set_default_dtype(torch.float32)

    env = capture_env(device, local_rank, world_size, backend)
    config = {
        "preset": args.preset,
        "d": args.d,
        "m": args.m,
        "ranks": args.ranks,
        "dtype": str(dtype).replace("torch.", ""),
        "decode_shape": [args.batch_decode, args.seq_decode, args.d],
        "train_shape": [args.batch_train, args.seq_train, args.d],
        "warmup": args.warmup,
        "iters": args.iters,
        "train_iters": args.train_iters,
        "comm_iters": args.comm_iters,
        "conditioned_generator": not args.no_conditioning,
    }
    decode_tokens_global = args.batch_decode * args.seq_decode * world_size
    train_tokens_global = args.batch_train * args.seq_train * world_size

    if rank == 0:
        print(json.dumps({"event": "start", "env": env, "config": config}, indent=2), flush=True)

    x_decode = make_input(args.batch_decode, args.seq_decode, args.d, dtype, device)
    x_train = make_input(args.batch_train, args.seq_train, args.d, dtype, device)

    dense_bytes = dense_ffn_bytes(args.d, args.m, elem_bytes)
    output: dict[str, Any] = {
        "created_at": now_tag(),
        "env": env,
        "config": config,
        "dense_theoretical_bytes": dense_bytes,
        "dense_theoretical_mib": round(dense_bytes / MIB, 3),
        "decode_tokens_global": decode_tokens_global,
        "train_tokens_global": train_tokens_global,
        "results": {},
    }

    dense = DenseGatedFFN(args.d, args.m, dtype=dtype).to(device)
    dense_param_bytes = parameter_bytes(dense)
    dense_forward = bench_forward(dense, x_decode, args.warmup, args.iters, rank)
    dense_train = bench_train(dense, x_train, max(1, args.warmup // 2), args.train_iters, rank)
    dense_comm = bench_allreduce(dense_param_bytes, dtype, device, 1, args.comm_iters, rank)
    if rank == 0:
        output["results"]["dense"] = {
            "parameter_bytes": dense_param_bytes,
            "parameter_mib": round(dense_param_bytes / MIB, 3),
            "descriptor_bytes": dense_bytes,
            "descriptor_mib": round(dense_bytes / MIB, 3),
            "communication_bytes": dense_param_bytes,
            "communication_mib": round(dense_param_bytes / MIB, 3),
            "forward": timing_to_dict(dense_forward),
            "train": timing_to_dict(dense_train),
            "allreduce": timing_to_dict(dense_comm),
            "decode_tokens_per_s": tokens_per_second(decode_tokens_global, dense_forward),
            "train_tokens_per_s": tokens_per_second(train_tokens_global, dense_train),
        }
        print(
            json.dumps({"event": "dense_done", "parameter_mib": round(dense_param_bytes / MIB, 3)}),
            flush=True,
        )
    del dense
    empty_cache()

    for r in args.ranks:
        model = EphemeralMetaWeightFFN(
            args.d, args.m, rank=r, dtype=dtype, condition=not args.no_conditioning
        ).to(device)
        param_bytes = parameter_bytes(model)
        descriptor_bytes = mwg_descriptor_bytes(args.d, args.m, r, elem_bytes)
        fwd = bench_forward(model, x_decode, args.warmup, args.iters, rank)
        train = bench_train(model, x_train, max(1, args.warmup // 2), args.train_iters, rank)
        comm = bench_allreduce(param_bytes, dtype, device, 1, args.comm_iters, rank)

        if rank == 0:
            dense_fwd_ms = output["results"]["dense"]["forward"]["mean_ms"]
            dense_train_ms = output["results"]["dense"]["train"]["mean_ms"]
            row = {
                "rank": r,
                "parameter_bytes": param_bytes,
                "parameter_mib": round(param_bytes / MIB, 3),
                "descriptor_bytes": descriptor_bytes,
                "descriptor_mib": round(descriptor_bytes / MIB, 3),
                "communication_bytes": param_bytes,
                "communication_mib": round(param_bytes / MIB, 3),
                "traffic_reduction_x": round(dense_bytes / max(descriptor_bytes, 1), 3),
                "parameter_reduction_x": round(dense_param_bytes / max(param_bytes, 1), 3),
                "communication_reduction_x": round(dense_param_bytes / max(param_bytes, 1), 3),
                "forward": timing_to_dict(fwd),
                "train": timing_to_dict(train),
                "allreduce": timing_to_dict(comm),
                "decode_tokens_per_s": tokens_per_second(decode_tokens_global, fwd),
                "train_tokens_per_s": tokens_per_second(train_tokens_global, train),
            }
            row["forward_speedup_x"] = round(dense_fwd_ms / max(row["forward"]["mean_ms"], 1e-9), 3)
            row["train_speedup_x"] = round(dense_train_ms / max(row["train"]["mean_ms"], 1e-9), 3)
            row["allreduce_reduction_x"] = round(
                output["results"]["dense"]["allreduce"]["mean_ms"] / max(row["allreduce"]["mean_ms"], 1e-9), 3
            ) if row["allreduce"]["mean_ms"] else None
            output["results"][f"mwg_r{r}"] = row
            print(
                json.dumps(
                    {
                        "event": "mwg_done",
                        "rank": r,
                        "parameter_mib": row["parameter_mib"],
                        "traffic_reduction_x": row["traffic_reduction_x"],
                        "forward_speedup_x": row["forward_speedup_x"],
                        "train_speedup_x": row["train_speedup_x"],
                    }
                ),
                flush=True,
            )
        del model
        empty_cache()

    del x_decode, x_train
    empty_cache()
    barrier()

    if dist.is_initialized():
        dist.destroy_process_group()

    return output if rank == 0 else None


def write_outputs(payload: dict[str, Any], outdir: Path) -> tuple[Path, Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    tag = payload["created_at"]
    env_label = payload.get("env_label", "ASI3")
    json_path = outdir / f"{env_label}_mwg_transformer_{tag}.json"
    md_path = outdir / f"{env_label}_mwg_transformer_{tag}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        f"# {env_label} MWG-EW Transformer Benchmark",
        "",
        f"Created: `{tag}`",
        f"World size: `{payload['env'].get('world_size')}`",
        f"Backend: `{payload['env'].get('backend')}`",
        f"Visible NPUs: `{payload['env'].get('ascend_rt_visible_devices')}`",
        "",
        "## Configuration",
        "",
        "```json",
        json.dumps(payload["config"], indent=2),
        "```",
        "",
        "## Results",
        "",
        "| Method | Params MiB | Descriptor MiB | Fwd ms | Train ms | Fwd speedup | Train speedup | Traffic reduction | AllReduce ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    dense = payload["results"]["dense"]
    lines.append(
        f"| dense | {dense['parameter_mib']} | {dense['descriptor_mib']} | "
        f"{dense['forward']['mean_ms']} | {dense['train']['mean_ms']} | 1.0 | 1.0 | 1.0 | "
        f"{dense['allreduce']['mean_ms']} |"
    )
    for key, row in payload["results"].items():
        if not key.startswith("mwg_r"):
            continue
        lines.append(
            f"| {key} | {row['parameter_mib']} | {row['descriptor_mib']} | "
            f"{row['forward']['mean_ms']} | {row['train']['mean_ms']} | "
            f"{row['forward_speedup_x']} | {row['train_speedup_x']} | "
            f"{row['traffic_reduction_x']} | {row['allreduce']['mean_ms']} |"
        )
    lines.append("")
    lines.extend(
        [
            "## Throughput and Communication",
            "",
            f"Decode tokens per timed step: `{payload.get('decode_tokens_global')}`",
            f"Training tokens per timed step: `{payload.get('train_tokens_global')}`",
            "",
            "| Method | Decode tok/s | Train tok/s | Communication MiB | Communication reduction |",
            "|---|---:|---:|---:|---:|",
            (
                f"| dense | {dense.get('decode_tokens_per_s')} | {dense.get('train_tokens_per_s')} | "
                f"{dense.get('communication_mib')} | 1.0 |"
            ),
        ]
    )
    for key, row in payload["results"].items():
        if not key.startswith("mwg_r"):
            continue
        lines.append(
            f"| {key} | {row.get('decode_tokens_per_s')} | {row.get('train_tokens_per_s')} | "
            f"{row.get('communication_mib')} | {row.get('communication_reduction_x')} |"
        )
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--preset",
        choices=["tiny", "ASI3_smoke", "ASI3_large", "ASI3_sweep", "ASI2_smoke", "ASI2_large", "ASI2_sweep"],
        default="tiny",
    )
    parser.add_argument("--env-label", default=None)
    parser.add_argument("--d", type=int, default=None)
    parser.add_argument("--m", type=int, default=None)
    parser.add_argument("--ranks", type=parse_rank_list, default=None)
    parser.add_argument("--batch-decode", type=int, default=None)
    parser.add_argument("--seq-decode", type=int, default=None)
    parser.add_argument("--batch-train", type=int, default=None)
    parser.add_argument("--seq-train", type=int, default=None)
    parser.add_argument("--warmup", type=int, default=None)
    parser.add_argument("--iters", type=int, default=None)
    parser.add_argument("--train-iters", type=int, default=None)
    parser.add_argument("--comm-iters", type=int, default=None)
    parser.add_argument("--dtype", choices=["auto", "fp16", "bf16", "fp32"], default="auto")
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--no-conditioning", action="store_true")
    parser.add_argument("--outdir", default="results")
    return parser


def apply_preset(args: argparse.Namespace) -> argparse.Namespace:
    preset_key = args.preset.replace("ASI2_", "ASI3_")
    if args.env_label is None:
        args.env_label = "ASI2" if args.preset.startswith("ASI2_") else "ASI3"
    if preset_key == "tiny":
        defaults = {
            "d": 64,
            "m": 128,
            "ranks": [8, 16],
            "batch_decode": 1,
            "seq_decode": 16,
            "batch_train": 2,
            "seq_train": 16,
            "warmup": 1,
            "iters": 2,
            "train_iters": 1,
            "comm_iters": 1,
        }
    elif preset_key == "ASI3_smoke":
        defaults = {
            "d": 512,
            "m": 1408,
            "ranks": [32, 64, 128],
            "batch_decode": 1,
            "seq_decode": 64,
            "batch_train": 1,
            "seq_train": 128,
            "warmup": 1,
            "iters": 4,
            "train_iters": 2,
            "comm_iters": 2,
        }
    else:
        if preset_key == "ASI3_large":
            defaults = {
                "d": 4096,
                "m": 14336,
                "ranks": [64, 128, 256],
                "batch_decode": 1,
                "seq_decode": 128,
                "batch_train": 2,
                "seq_train": 512,
                "warmup": 4,
                "iters": 12,
                "train_iters": 4,
                "comm_iters": 4,
            }
        else:
            defaults = {
                "d": 4096,
                "m": 14336,
                "ranks": [32, 64, 96, 128, 192, 256, 384, 512],
                "batch_decode": 1,
                "seq_decode": 128,
                "batch_train": 2,
                "seq_train": 512,
                "warmup": 3,
                "iters": 10,
                "train_iters": 3,
                "comm_iters": 5,
            }
    for key, value in defaults.items():
        if getattr(args, key) is None:
            setattr(args, key, value)
    return args


def main() -> None:
    args = apply_preset(build_parser().parse_args())
    payload = run_benchmarks(args)
    if payload is not None:
        payload["env_label"] = args.env_label
        json_path, md_path = write_outputs(payload, Path(args.outdir))
        print(json.dumps({"event": "saved", "json": str(json_path), "markdown": str(md_path)}, indent=2), flush=True)


if __name__ == "__main__":
    main()
