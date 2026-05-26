"""Runtime profiler probe for MWG-EW dense vs associative FFN paths.

This script is deliberately modest: it collects operator-level profiler
evidence and environment/tool snapshots for the existing PyTorch prototype. It
does not claim full hardware-counter validation unless the backend exposes NPU
activities. Its main purpose is to make the current fused-kernel gap explicit:
the associative MWG path should appear as multiple ordinary matmul-like
operators unless a fused kernel is actually present.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
from torch.profiler import ProfilerActivity, profile

from mwg_transformer_ai3_benchmark import (
    DenseGatedFFN,
    EphemeralMetaWeightFFN,
    capture_env,
    dense_ffn_bytes,
    dtype_from_name,
    mwg_descriptor_bytes,
    parameter_bytes,
    setup_runtime,
    sync_device,
)


def now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_text_command(command: list[str], timeout_s: int) -> dict[str, Any]:
    if shutil.which(command[0]) is None:
        return {"cmd": command, "available": False}
    try:
        proc = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        return {
            "cmd": command,
            "available": True,
            "returncode": proc.returncode,
            "output_head": proc.stdout[:4000],
        }
    except Exception as exc:
        return {"cmd": command, "available": True, "error": repr(exc)}


def activities_for(device: torch.device) -> list[Any]:
    activities: list[Any] = [ProfilerActivity.CPU]
    if device.type == "cuda" and hasattr(ProfilerActivity, "CUDA"):
        activities.append(ProfilerActivity.CUDA)
    if device.type == "npu" and hasattr(ProfilerActivity, "NPU"):
        activities.append(getattr(ProfilerActivity, "NPU"))
    return activities


def make_input(batch: int, seq: int, d: int, dtype: torch.dtype, device: torch.device) -> torch.Tensor:
    return torch.randn(batch, seq, d, dtype=dtype, device=device)


def timed_step(fn, warmup: int, iters: int) -> dict[str, float]:
    for _ in range(warmup):
        fn()
    sync_device()
    times = []
    for _ in range(iters):
        sync_device()
        start = time.perf_counter()
        fn()
        sync_device()
        times.append((time.perf_counter() - start) * 1000.0)
    return {
        "mean_ms": sum(times) / max(len(times), 1),
        "min_ms": min(times) if times else 0.0,
        "max_ms": max(times) if times else 0.0,
        "iters": iters,
    }


def event_value(event: Any, names: list[str]) -> float | int | None:
    for name in names:
        if hasattr(event, name):
            value = getattr(event, name)
            if isinstance(value, (int, float)):
                return value
    return None


def summarize_profile(prof: Any, top_k: int) -> dict[str, Any]:
    events = prof.key_averages()
    rows: list[dict[str, Any]] = []
    for event in events:
        rows.append(
            {
                "key": event.key,
                "count": int(getattr(event, "count", 0)),
                "cpu_time_total_us": event_value(event, ["cpu_time_total"]),
                "self_cpu_time_total_us": event_value(event, ["self_cpu_time_total"]),
                "device_time_total_us": event_value(
                    event,
                    [
                        "device_time_total",
                        "self_device_time_total",
                        "cuda_time_total",
                        "self_cuda_time_total",
                        "npu_time_total",
                        "self_npu_time_total",
                    ],
                ),
                "cpu_memory_usage": event_value(event, ["cpu_memory_usage", "self_cpu_memory_usage"]),
                "device_memory_usage": event_value(
                    event,
                    [
                        "device_memory_usage",
                        "self_device_memory_usage",
                        "cuda_memory_usage",
                        "self_cuda_memory_usage",
                        "npu_memory_usage",
                        "self_npu_memory_usage",
                    ],
                ),
            }
        )
    rows.sort(key=lambda item: float(item.get("device_time_total_us") or item.get("cpu_time_total_us") or 0), reverse=True)
    matmul_terms = ("matmul", "mm", "bmm", "gemm", "addmm", "linear", "npu_matmul")
    matmul_rows = [row for row in rows if any(term in row["key"].lower() for term in matmul_terms)]
    fused_terms = ("fused", "mwg", "ephemeral")
    fused_rows = [row for row in rows if any(term in row["key"].lower() for term in fused_terms)]
    return {
        "top_ops": rows[:top_k],
        "matmul_like_op_count": sum(int(row["count"]) for row in matmul_rows),
        "matmul_like_keys": matmul_rows[:top_k],
        "fused_like_keys": fused_rows[:top_k],
        "observed_fused_like_op": bool(fused_rows),
    }


def profile_case(name: str, model: torch.nn.Module, x: torch.Tensor, args: argparse.Namespace, activities: list[Any]) -> dict[str, Any]:
    model.train(args.mode == "train")

    def step() -> None:
        if args.mode == "train":
            model.zero_grad(set_to_none=True)
            y = model(x)
            loss = y.float().square().mean()
            loss.backward()
        else:
            with torch.no_grad():
                y = model(x)
                if y.numel() == 0:
                    raise RuntimeError("empty output")

    timing = timed_step(step, args.warmup, args.iters)
    sync_device()
    try:
        with profile(activities=activities, record_shapes=True, profile_memory=True, with_stack=False) as prof:
            for _ in range(args.profile_iters):
                step()
                prof.step()
        summary = summarize_profile(prof, args.top_k)
        trace_path = ""
        if args.export_traces:
            trace_dir = Path(args.outdir) / "traces"
            trace_dir.mkdir(parents=True, exist_ok=True)
            trace_path = str(trace_dir / f"{name}.json")
            prof.export_chrome_trace(trace_path)
        profiler_error = ""
    except Exception as exc:
        summary = {"top_ops": [], "matmul_like_op_count": 0, "matmul_like_keys": [], "fused_like_keys": [], "observed_fused_like_op": False}
        trace_path = ""
        profiler_error = repr(exc)
    return {
        "name": name,
        "mode": args.mode,
        "timing": timing,
        "parameter_bytes": parameter_bytes(model),
        "profiler_activities": [str(item).split(".")[-1] for item in activities],
        "profiler_error": profiler_error,
        "profiler_summary": summary,
        "trace_path": trace_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default="results/runtime_profiler_probe")
    parser.add_argument("--d", type=int, default=2048)
    parser.add_argument("--m", type=int, default=5504)
    parser.add_argument("--ranks", default="128,256")
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--seq", type=int, default=128)
    parser.add_argument("--dtype", choices=["auto", "fp16", "bf16", "fp32"], default="auto")
    parser.add_argument("--mode", choices=["forward", "train"], default="forward")
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--iters", type=int, default=10)
    parser.add_argument("--profile-iters", type=int, default=3)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--export-traces", action="store_true")
    args = parser.parse_args()

    device, rank, local_rank, world_size, backend = setup_runtime()
    if rank != 0:
        raise SystemExit("runtime profiler probe is single-rank; set WORLD_SIZE=1")
    dtype = dtype_from_name(args.dtype, device)
    torch.manual_seed(args.seed)
    x = make_input(args.batch, args.seq, args.d, dtype, device)
    elem_bytes = torch.empty((), dtype=dtype).element_size()
    acts = activities_for(device)
    env = capture_env(device, local_rank, world_size, backend)
    env["tool_paths"] = {name: shutil.which(name) for name in ["npu-smi", "msprof", "msnpureport", "python3"]}
    env["npu_smi_info_head"] = run_text_command(["npu-smi", "info"], 8)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    cases = []
    dense = DenseGatedFFN(args.d, args.m, dtype).to(device)
    dense_case = profile_case("dense", dense, x, args, acts)
    dense_case["descriptor_bytes"] = dense_ffn_bytes(args.d, args.m, elem_bytes)
    cases.append(dense_case)
    del dense

    for rank_value in [int(item.strip()) for item in args.ranks.split(",") if item.strip()]:
        model = EphemeralMetaWeightFFN(args.d, args.m, rank_value, dtype=dtype).to(device)
        case = profile_case(f"mwg_r{rank_value}", model, x, args, acts)
        case["rank"] = rank_value
        case["descriptor_bytes"] = mwg_descriptor_bytes(args.d, args.m, rank_value, elem_bytes)
        case["traffic_reduction_x_vs_dense_descriptor"] = dense_ffn_bytes(args.d, args.m, elem_bytes) / max(case["descriptor_bytes"], 1)
        cases.append(case)
        del model

    payload = {
        "created_at": now_tag(),
        "purpose": "operator-level runtime profiler probe; negative fused-kernel evidence unless fused_like ops are observed",
        "env": env,
        "config": vars(args),
        "input_shape": [args.batch, args.seq, args.d],
        "dtype": str(dtype).replace("torch.", ""),
        "cases": cases,
        "claim_boundary": {
            "hardware_counter_complete": False,
            "reason": "This probe records profiler operators and tool availability. It is not a full off-chip traffic counter study unless backend device activities and counter tools are available in the captured environment.",
        },
    }
    out_json = outdir / f"mwg_runtime_profiler_probe_{payload['created_at']}.json"
    out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    latest = outdir / "mwg_runtime_profiler_probe_latest.json"
    latest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out_json": str(out_json), "latest": str(latest), "cases": [case["name"] for case in cases]}, indent=2))


if __name__ == "__main__":
    main()
