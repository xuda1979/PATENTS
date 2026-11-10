#!/usr/bin/env python3
"""Device-counter profiling harness for v1 (single-core) vs v4 (multicore)
ephemeral_core_apply on Ascend 910B2 (2026-11-10).

Companion to test_v4_multicore_v3.py (md5 526839744b6c2916822b3a1a9387609f):
identical probe geometries (probe_T128, large_T512..T4096), identical input
construction (ctrl fp32 [T,H]; head_w fp32 [H,R]; head_b fp32 [R];
act fp16 [T,R]; amp 0.05; seed 1234), plus a torch_npu-profiler pass per
arm with AICORE Memory counters and L2-cache metrics so the observed
speedup can be attributed to measured device behavior, not host timing
alone.

Counter parsing: torch_npu profiler with experimental_config(aic_metrics=
Memory, l2_cache=True) exports kernel-level summaries; we scan the export
directory for per-kernel CSV rows of our two kernels and sum
aiv_aicore hbm read/write (and l2) byte columns. The harness records both
the parsed totals and the list of files parsed so the numbers are
auditable.
"""

import argparse
import glob
import json
import os
import statistics
import time
from pathlib import Path

import torch
import torch_npu  # noqa: F401
from torch_npu.profiler import _ExperimentalConfig, AiCMetrics, ProfilerActivity, profile


# Same geometries as the v3 harness comparison sweep.
CONFIGS = [
    ("probe_T128", 128, 128, 128),
    ("large_T512", 512, 128, 128),
    ("large_T1024", 1024, 128, 128),
    ("large_T2048", 2048, 128, 128),
    ("large_T4096", 4096, 128, 128),
]
AMP = 0.05
SEED = 1234


def make_inputs(T, H, R):
    """Identical construction to run_config in test_v4_multicore_v3.py."""
    torch.manual_seed(SEED)
    ctrl = torch.randn(T, H, dtype=torch.float32, device="npu:0")
    head_w = torch.randn(H, R, dtype=torch.float32, device="npu:0")
    head_b = torch.randn(R, dtype=torch.float32, device="npu:0")
    act = torch.randn(T, R, dtype=torch.float16, device="npu:0")
    return act, ctrl, head_w, head_b


def host_benchmark(op_fn, op_args, warmup, iters, repeats):
    for _ in range(warmup):
        op_fn(*op_args)
    torch.npu.synchronize()
    results = []
    for _ in range(repeats):
        torch.npu.synchronize()
        t0 = time.perf_counter()
        for _ in range(iters):
            op_fn(*op_args)
        torch.npu.synchronize()
        t1 = time.perf_counter()
        results.append((t1 - t0) / iters * 1000)
    results.sort()
    return {
        "median_ms": statistics.median(results),
        "std_ms": statistics.stdev(results) if len(results) > 1 else 0.0,
        "all_ms": results,
    }


def parse_kernel_csvs(export_root):
    """Sum hbm/l2 byte columns across kernel-summary CSVs for our kernels."""
    totals = {"hbm_read_bytes": 0.0, "hbm_write_bytes": 0.0,
              "l2_read_bytes": 0.0, "l2_write_bytes": 0.0,
              "rows_matched": 0, "files": []}
    for csv_path in glob.glob(os.path.join(export_root, "**", "*.csv"), recursive=True):
        rel = os.path.relpath(csv_path, export_root)
        try:
            with open(csv_path) as f:
                lines = f.read().splitlines()
        except Exception:
            continue
        if not lines:
            continue
        # header may repeat; find rows whose Name contains our kernels
        for i, line in enumerate(lines):
            low = line.lower()
            if "ephemeral" in low or "coreapply" in low or "core_apply" in low:
                row = [c.strip().strip('"') for c in line.split(",")]
                # pick nearest preceding header
                header = None
                for j in range(i - 1, -1, -1):
                    if "name" in lines[j].lower() and "," in lines[j]:
                        header = [c.strip().strip('"').lower() for c in lines[j].split(",")]
                        break
                if not header:
                    continue
                totals["rows_matched"] += 1
                if not totals["files"] or totals["files"][-1] != rel:
                    totals["files"].append(rel)
                for k, key in enumerate(header):
                    if k >= len(row):
                        continue
                    try:
                        v = float(row[k].replace(",", ""))
                    except ValueError:
                        continue
                    kl = key
                    if ("hbm" in kl or "ddr" in kl) and "read" in kl:
                        totals["hbm_read_bytes"] += v
                    elif ("hbm" in kl or "ddr" in kl) and "write" in kl:
                        totals["hbm_write_bytes"] += v
                    elif "l2" in kl and "read" in kl:
                        totals["l2_read_bytes"] += v
                    elif "l2" in kl and "write" in kl:
                        totals["l2_write_bytes"] += v
    return totals


def profile_arm(op_fn, op_args, profile_root, label, warmup, iters):
    """Profile one arm; return host-timed stats plus parsed counters."""
    export_dir = os.path.join(profile_root, label)
    Path(export_dir).mkdir(parents=True, exist_ok=True)
    exp = _ExperimentalConfig(
        profiler_level=0,
        aic_metrics=AiCMetrics.Memory,
        l2_cache=True,
        data_simplification=False,
    )
    for _ in range(warmup):
        op_fn(*op_args)
    torch.npu.synchronize()
    with profile(
        activities=[ProfilerActivity.CPU, ProfilerActivity.NPU],
        experimental_config=exp,
    ) as prof:
        for _ in range(iters):
            op_fn(*op_args)
        torch.npu.synchronize()
    # export both chrome trace and msprof summary; trace for audit, csv for counters
    prof.export_chrome_trace(os.path.join(export_dir, "trace.json"))
    prof.export_key_averages(os.path.join(export_dir, "key_averages.csv"), "csv") if hasattr(
        prof, "export_key_averages"
    ) else None
    parsed = parse_kernel_csvs(export_dir)
    parsed["iters_profiled"] = iters
    return parsed


def main():
    parser = argparse.ArgumentParser(description="v4-vs-v1 device-counter profiling")
    parser.add_argument("--v1-library", required=True)
    parser.add_argument("--v4-library", required=True)
    parser.add_argument("--output", default="results/v4_device_counters.json")
    parser.add_argument("--profile-root", default="/root/work/v4_profiling")
    parser.add_argument("--warmup", type=int, default=30)
    parser.add_argument("--iters", type=int, default=50)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()

    torch.npu.set_device(0)
    torch.ops.load_library(args.v1_library)
    torch.ops.load_library(args.v4_library)

    v1 = torch.ops.mwg.ephemeral_core_apply
    v4 = torch.ops.mwg.ephemeral_core_apply_v4

    record = {
        "schema_version": 1,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "harness": "profile_v4_device_counters.py (2026-11-10)",
        "config": {
            "warmup": args.warmup,
            "iters": args.iters,
            "repeats": args.repeats,
            "amp": AMP,
            "seed": SEED,
            "input_contract": "ctrl fp32 [T,H]; head_w fp32 [H,R]; head_b fp32 [R]; act fp16 [T,R]",
        },
        "geometries": {},
    }

    for name, T, H, R in CONFIGS:
        act, ctrl, head_w, head_b = make_inputs(T, H, R)
        op_args = (act, ctrl, head_w, head_b, AMP)
        entry = {"T": T, "H": H, "R": R}
        # equivalence once
        y1 = v1(*op_args)
        y4 = v4(*op_args)
        torch.npu.synchronize()
        entry["max_abs_diff"] = float((y1.float() - y4.float()).abs().max().item())
        # host timing (same loop shape as v3)
        entry["v1_host"] = host_benchmark(v1, op_args, args.warmup, args.iters, args.repeats)
        entry["v4_host"] = host_benchmark(v4, op_args, args.warmup, args.iters, args.repeats)
        # device counters
        entry["v1_counters"] = profile_arm(v1, op_args, args.profile_root, f"{name}_v1", args.warmup, args.iters)
        entry["v4_counters"] = profile_arm(v4, op_args, args.profile_root, f"{name}_v4", args.warmup, args.iters)
        m1, m4 = entry["v1_host"]["median_ms"], entry["v4_host"]["median_ms"]
        entry["speedup_v1_over_v4"] = (m1 / m4) if m4 > 0 else None
        record["geometries"][name] = entry
        print(
            f"{name}: v1 {m1:.4f} ms, v4 {m4:.4f} ms, speedup "
            f"{(m1/m4 if m4 else 0):.3f}x, maxdiff {entry['max_abs_diff']}, "
            f"v1 hbm_r {entry['v1_counters']['hbm_read_bytes']:.3g}, "
            f"v4 hbm_r {entry['v4_counters']['hbm_read_bytes']:.3g}",
            flush=True,
        )

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(record, f, indent=1)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
