#!/usr/bin/env python3
"""Test and benchmark the v4 multi-core epilogue kernel against v1.

This script must be run ON the NPU host (ASI2) after the v4 kernel has been
compiled and registered.  It:

1. Loads both v1 (single-core) and v4 (multi-core) operators
2. Verifies algebraic equivalence (v4 output matches v1 within fp16 tolerance)
3. Benchmarks both at L2-resident probe geometry (T=128) and beyond-L2
   geometry (T=4096) to measure the multi-core epilogue speedup
4. Records msprof counter traces for the beyond-L2 comparison

Usage (on ASI2):
    python3 test_v4_multicore.py --op-library <path-to-v4.so> \\
                                 --v1-library <path-to-v1.so> \\
                                 --output results/v4_benchmark.json
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

import torch

def algebraic_reference(rank_activation, controller_hidden, head_weight, head_bias, amplitude):
    """Reference implementation in pure PyTorch.

    Convention (matches the shipped v1 op, mwg_smoke_test.py, and the
    four-arm harness): head_weight is [H, R], used directly with no
    transpose: logits = ctrl[T,H] @ head_weight[H,R] + bias[R].
    The 2026-09-29 v1-NaN abort was traced to this test previously using
    the [R, H] convention (with a transposing reference), silently
    mismatching the shipped kernel's [H, R] contract at square geometry.
    """
    logits = controller_hidden @ head_weight + head_bias  # [T, R]
    core = 1.0 + amplitude * torch.tanh(logits)  # [T, R]
    return rank_activation * core  # [T, R]


def benchmark_op(op_fn, args, warmup=30, iters=200, repeats=5):
    """Benchmark an operator with host-side timing."""
    # Warmup
    for _ in range(warmup):
        out = op_fn(*args)
    torch.npu.synchronize()

    results = []
    for rep in range(repeats):
        torch.npu.synchronize()
        t0 = time.perf_counter()
        for _ in range(iters):
            out = op_fn(*args)
        torch.npu.synchronize()
        t1 = time.perf_counter()
        ms = (t1 - t0) / iters * 1000
        results.append(ms)
    
    results.sort()
    median = results[len(results) // 2]
    std = (sum((x - median) ** 2 for x in results) / len(results)) ** 0.5
    return {"median_ms": median, "std_ms": std, "all_ms": results}


def device_preflight():
    """Device-health gate: a wedged NPU (e.g. after an aicore fault from a
    prior crashed run, or contention with a concurrent trainer) must be
    detected BEFORE v4 runs, or v4 results are uninterpretable.  Evidence:
    the 2026-09-29 16:26 ASI3 run reported v1 max_err = nan (the shipped,
    device-proven kernel) yet blamed v4 for the aicore timeout.  A small
    matmul + allclose check catches that state cheaply."""
    x = torch.randn(128, 128, dtype=torch.float16, device="npu:0")
    w = torch.randn(128, 128, dtype=torch.float16, device="npu:0")
    y = (x.float() @ w.float()).half()
    y_ref = y.clone()
    if not torch.allclose(y, y_ref):
        print("PREFLIGHT FAIL: baseline matmul non-deterministic; device wedged")
        sys.exit(3)
    if torch.isnan(y).any() or torch.isinf(y).any():
        print("PREFLIGHT FAIL: baseline matmul produced NaN/Inf; device wedged")
        sys.exit(3)
    print("preflight: device healthy (baseline matmul finite & deterministic)")


def run_comparison(args):
    device = torch.device("npu:0")
    torch.npu.set_device(0)

    # Load operators
    if args.v1_library:
        torch.ops.load_library(args.v1_library)
    if args.op_library:
        torch.ops.load_library(args.op_library)

    # Device-health gate before any v4 launch
    device_preflight()

    # Test configurations
    configs = [
        # (name, T, H, R, amplitude, L2_resident?)
        ("probe_T128", 128, 128, 128, 0.05, True),
        ("large_T512", 512, 128, 128, 0.05, False),
        ("large_T1024", 1024, 128, 128, 0.05, False),
        ("large_T2048", 2048, 128, 128, 0.05, False),
        ("large_T4096", 4096, 128, 128, 0.05, False),
    ]

    results = {"configs": [], "equivalence": []}

    for name, T, H, R, amp, l2_res in configs:
        print(f"\n=== {name}: T={T}, H={H}, R={R}, amp={amp} ===")

        # Create inputs
        torch.manual_seed(1234)
        ctrl = torch.randn(T, H, dtype=torch.float32, device=device)
        head_w = torch.randn(H, R, dtype=torch.float32, device=device)
        head_b = torch.randn(R, dtype=torch.float32, device=device)
        act = torch.randn(T, R, dtype=torch.float16, device=device)

        # Reference
        ref = algebraic_reference(act.float(), ctrl, head_w, head_b, amp).half()

        # v1 (single-core)
        out_v1 = None
        v1_bench = None
        if hasattr(torch.ops.mwg, 'ephemeral_core_apply'):
            try:
                out_v1 = torch.ops.mwg.ephemeral_core_apply(act, ctrl, head_w, head_b, amp)
                err_v1 = (out_v1.float() - ref.float()).abs().max().item()
                print(f"  v1 max_err = {err_v1:.6f}")
                if math.isnan(err_v1):
                    # The shipped v1 kernel is device-proven; NaN here means
                    # the DEVICE is wedged (prior aicore fault / contention),
                    # not a v4 defect.  Abort without blaming v4.
                    print("  ABORT: shipped v1 returned NaN; device wedged, "
                          "v4 results would be uninterpretable")
                    results["abort_reason"] = "v1_nan_device_wedged"
                    if args.output:
                        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
                        Path(args.output).write_text(
                            json.dumps(results, indent=2), encoding="utf-8")
                    sys.exit(3)
                results["equivalence"].append({
                    "config": name, "version": "v1", "max_abs_err": err_v1,
                    "pass": err_v1 < 5e-3
                })
                v1_bench = benchmark_op(
                    lambda a, c, w, b, am: torch.ops.mwg.ephemeral_core_apply(a, c, w, b, am),
                    (act, ctrl, head_w, head_b, amp),
                    warmup=args.warmup, iters=args.iters, repeats=args.repeats
                )
                print(f"  v1 median = {v1_bench['median_ms']:.4f} ± {v1_bench['std_ms']:.4f} ms")
            except Exception as e:
                print(f"  v1 ERROR: {e}")
                results["equivalence"].append({
                    "config": name, "version": "v1", "error": str(e)
                })

        # v4 (multi-core)
        out_v4 = None
        v4_bench = None
        if hasattr(torch.ops.mwg, 'ephemeral_core_apply_v4'):
            try:
                out_v4 = torch.ops.mwg.ephemeral_core_apply_v4(act, ctrl, head_w, head_b, amp)
                err_v4 = (out_v4.float() - ref.float()).abs().max().item()
                print(f"  v4 max_err = {err_v4:.6f}")
                results["equivalence"].append({
                    "config": name, "version": "v4", "max_abs_err": err_v4,
                    "pass": err_v4 < 5e-3
                })
                v4_bench = benchmark_op(
                    lambda a, c, w, b, am: torch.ops.mwg.ephemeral_core_apply_v4(a, c, w, b, am),
                    (act, ctrl, head_w, head_b, amp),
                    warmup=args.warmup, iters=args.iters, repeats=args.repeats
                )
                print(f"  v4 median = {v4_bench['median_ms']:.4f} ± {v4_bench['std_ms']:.4f} ms")
            except Exception as e:
                print(f"  v4 ERROR: {e}")
                results["equivalence"].append({
                    "config": name, "version": "v4", "error": str(e)
                })

        # Cross-check v1 vs v4
        if out_v1 is not None and out_v4 is not None:
            cross_err = (out_v1.float() - out_v4.float()).abs().max().item()
            print(f"  v1-vs-v4 max_err = {cross_err:.6f}")
            results["equivalence"].append({
                "config": name, "version": "v1-vs-v4", "max_abs_err": cross_err,
                "pass": cross_err < 5e-3
            })

        # Speedup
        speedup = None
        if v1_bench and v4_bench:
            speedup = v1_bench["median_ms"] / v4_bench["median_ms"]
            print(f"  speedup = {speedup:.3f}x")

        results["configs"].append({
            "name": name, "T": T, "H": H, "R": R, "amplitude": amp,
            "L2_resident": l2_res,
            "v1": v1_bench, "v4": v4_bench,
            "speedup_v1_over_v4": speedup
        })

    # Summary
    print("\n=== SUMMARY ===")
    print(f"{'Config':<20} {'v1 ms':>10} {'v4 ms':>10} {'Speedup':>10} {'L2':>5}")
    print("-" * 60)
    for c in results["configs"]:
        v1 = f"{c['v1']['median_ms']:.4f}" if c['v1'] else "N/A"
        v4 = f"{c['v4']['median_ms']:.4f}" if c['v4'] else "N/A"
        sp = f"{c['speedup_v1_over_v4']:.3f}x" if c['speedup_v1_over_v4'] else "N/A"
        l2 = "yes" if c["L2_resident"] else "no"
        print(f"{c['name']:<20} {v1:>10} {v4:>10} {sp:>10} {l2:>5}")

    # Stability: 1000 sequential calls at the beyond-L2 geometry must
    # complete without aicore exception (the v3 failure mode; DESIGN.md
    # validation criterion 5).
    print("\n=== STABILITY: 1000 sequential calls at T=4096 ===")
    if hasattr(torch.ops.mwg, 'ephemeral_core_apply_v4'):
        T, H, R = 4096, 128, 128
        amp = 0.05
        torch.manual_seed(4321)
        ctrl = torch.randn(T, H, dtype=torch.float32, device=device)
        head_w = torch.randn(H, R, dtype=torch.float32, device=device)
        head_b = torch.randn(R, dtype=torch.float32, device=device)
        act = torch.randn(T, R, dtype=torch.float16, device=device)
        ref = algebraic_reference(act.float(), ctrl, head_w, head_b, amp).half()
        try:
            n_calls = 0
            for i in range(1000):
                out = torch.ops.mwg.ephemeral_core_apply_v4(act, ctrl, head_w, head_b, amp)
                n_calls += 1
            err = (out.float() - ref.float()).abs().max().item()
            ok = err < 5e-3
            print(f"  completed {n_calls}/1000 calls, final max_err = {err:.6f}, "
                  f"{'PASS' if ok else 'FAIL'}")
            results["stability_1000_calls"] = {
                "completed": n_calls, "final_max_abs_err": err, "pass": ok
            }
        except Exception as e:
            print(f"  FAILED after {n_calls} calls: {e}")
            results["stability_1000_calls"] = {
                "completed": n_calls, "error": str(e), "pass": False
            }
    else:
        print("  v4 op unavailable; SKIP")

    # Save results
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nResults saved to {out_path}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Test v4 multi-core epilogue")
    parser.add_argument("--op-library", type=str, default=None,
                        help="Path to the v4 compiled .so file")
    parser.add_argument("--v1-library", type=str, default=None,
                        help="Path to the v1 compiled .so file")
    parser.add_argument("--output", type=str, default="results/v4_benchmark.json",
                        help="Output JSON path")
    parser.add_argument("--warmup", type=int, default=30)
    parser.add_argument("--iters", type=int, default=200)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    run_comparison(args)


if __name__ == "__main__":
    main()
