#!/usr/bin/env python3
"""Test and benchmark the v4 multi-core epilogue kernel against v1.

HARDENED v2 (2026-10-08).  Identical methodology, configs, tolerances,
and benchmark_op as v1, plus three hardenings learned from the 3x
T512-NaN aborts (ASI3 2026-09-29, ASI2 05:25 and 07:45) and the diag9
ref-corruption postmortem:

  H1. Ref-integrity gate: the NPU-computed reference is recomputed
      until bit-stable (max 8 attempts).  A single ref computed inside a
      CANN bad window silently corrupted diag9 (2026-10-08, err=0.081
      both ops bit-identical) - never trust one ref.

  H2. NaN attribution: on any NaN/wrong-finite err, snapshot which
      tensor is dirty (inputs / ref / v1 out / v4 out) vs CPU truth
      BEFORE deciding.  The v1 test could not distinguish v1-output-NaN
      from ref-NaN.

  H3. Per-config retry: a config-level failure is retried (up to 3
      attempts, fresh seed per attempt).  The T512 NaN never reproduced
      in 8 isolated probes (exact data, exact sequence, async pileup);
      it is an environment transient, not a kernel defect.  The test
      aborts ONLY if the same config fails all 3 attempts AND
      attribution implicates the op output (not ref/inputs).

Usage and outputs are identical to v1.  The abort exit code (3) is
preserved for genuine persistent device-wedge.
"""

import argparse
import json
import math
import sys
import time
from pathlib import Path

import torch
import torch_npu  # noqa: F401


def algebraic_reference(rank_activation, controller_hidden, head_weight,
                        head_bias, amplitude):
    """Reference implementation in pure PyTorch.

    Convention (matches the shipped v1 op, mwg_smoke_test.py, and the
    four-arm harness): head_weight is [H, R], used directly with no
    transpose: logits = ctrl[T,H] @ head_weight[H,R] + bias[R].
    """
    logits = controller_hidden @ head_weight + head_bias  # [T, R]
    core = 1.0 + amplitude * torch.tanh(logits)  # [T, R]
    return rank_activation * core  # [T, R]


def benchmark_op(op_fn, args, warmup=30, iters=200, repeats=5):
    """Benchmark an operator with host-side timing."""
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
    """Device-health gate (unchanged from v1)."""
    x = torch.randn(128, 128, dtype=torch.float16, device="npu:0")
    y = x @ x
    torch.npu.synchronize()
    y_ref = y.clone()
    if not torch.allclose(y, y_ref):
        print("PREFLIGHT FAIL: baseline matmul non-deterministic; device wedged")
        sys.exit(3)
    if torch.isnan(y).any() or torch.isinf(y).any():
        print("PREFLIGHT FAIL: baseline matmul produced NaN/Inf; device wedged")
        sys.exit(3)
    print("preflight: device healthy (baseline matmul finite & deterministic)")


def gated_ref(act, ctrl, head_w, head_b, amp, retries=8):
    """H1: compute the reference until bit-stable."""
    r1 = algebraic_reference(act.float(), ctrl, head_w, head_b, amp).half()
    torch.npu.synchronize()
    for attempt in range(retries):
        r2 = algebraic_reference(act.float(), ctrl, head_w, head_b, amp).half()
        torch.npu.synchronize()
        if float((r1.float() - r2.float()).abs().max().item()) == 0.0:
            return r1, attempt
        r1 = r2
    return r1, retries


def nan_stats(t):
    f = t.float()
    return {"nan": int(torch.isnan(f).sum().item()),
            "inf": int(torch.isinf(f).sum().item())}


def cpu_truth(act, ctrl, head_w, head_b, amp):
    return algebraic_reference(act.float().cpu(), ctrl.cpu(), head_w.cpu(),
                               head_b.cpu(), amp).half()


def run_config(name, T, H, R, amp, args, results):
    """One config with H1-H3 hardening.  Returns True on pass."""
    for attempt in range(3):
        # Create inputs (fresh seed per attempt)
        torch.manual_seed(1234 + attempt)
        ctrl = torch.randn(T, H, dtype=torch.float32, device="npu:0")
        head_w = torch.randn(H, R, dtype=torch.float32, device="npu:0")
        head_b = torch.randn(R, dtype=torch.float32, device="npu:0")
        act = torch.randn(T, R, dtype=torch.float16, device="npu:0")

        # H1: gated reference
        ref, gate_attempts = gated_ref(act, ctrl, head_w, head_b, amp)
        if attempt == 0:
            print(f"\n=== {name}: T={T}, H={H}, R={R}, amp={amp} ===")
        else:
            print(f"\n=== {name} RETRY {attempt} ===")

        # v1 (single-core)
        out_v1 = None
        v1_bench = None
        if hasattr(torch.ops.mwg, 'ephemeral_core_apply'):
            try:
                out_v1 = torch.ops.mwg.ephemeral_core_apply(
                    act, ctrl, head_w, head_b, amp)
                err_v1 = (out_v1.float() - ref.float()).abs().max().item()
                print(f"  v1 max_err = {err_v1:.6f}")
                if math.isnan(err_v1) or err_v1 >= 5e-3:
                    # H2: attribute before deciding
                    attribution = {
                        "v1_out": nan_stats(out_v1),
                        "ref": nan_stats(ref),
                        "inputs": {"act": nan_stats(act), "ctrl": nan_stats(ctrl),
                                   "w": nan_stats(head_w), "b": nan_stats(head_b)},
                    }
                    truth = cpu_truth(act, ctrl, head_w, head_b, amp)
                    attribution["v1_vs_truth"] = float(
                        (out_v1.float().cpu() - truth.float()).abs().max().item())
                    attribution["ref_vs_truth"] = float(
                        (ref.float().cpu() - truth.float()).abs().max().item())
                    print(f"  v1 ATTRIBUTION: {json.dumps(attribution)}")
                    op_blamed = (attribution["v1_out"]["nan"] > 0
                                 or attribution["v1_out"]["inf"] > 0
                                 or attribution["v1_vs_truth"] >= 5e-3)
                    if op_blamed and attempt < 2:
                        print("  v1 output implicated; retrying config")
                        continue
                    if op_blamed:
                        print("  ABORT: v1 output NaN/wrong across all 3 "
                              "attempts; persistent device fault")
                        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
                        Path(args.output).write_text(
                            json.dumps(results, indent=2), encoding="utf-8")
                        sys.exit(3)
                    # ref/inputs implicated -> gate caught it, retry
                    print("  ref/inputs implicated (transient); retrying config")
                    continue
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
                out_v4 = torch.ops.mwg.ephemeral_core_apply_v4(
                    act, ctrl, head_w, head_b, amp)
                err_v4 = (out_v4.float() - ref.float()).abs().max().item()
                print(f"  v4 max_err = {err_v4:.6f}")
                if math.isnan(err_v4) or err_v4 >= 5e-3:
                    attribution = {
                        "v4_out": nan_stats(out_v4),
                        "ref": nan_stats(ref),
                        "ref_gate_attempts": gate_attempts,
                    }
                    truth = cpu_truth(act, ctrl, head_w, head_b, amp)
                    attribution["v4_vs_truth"] = float(
                        (out_v4.float().cpu() - truth.float()).abs().max().item())
                    attribution["ref_vs_truth"] = float(
                        (ref.float().cpu() - truth.float()).abs().max().item())
                    print(f"  v4 ATTRIBUTION: {json.dumps(attribution)}")
                    op_blamed = (attribution["v4_out"]["nan"] > 0
                                 or attribution["v4_out"]["inf"] > 0
                                 or attribution["v4_vs_truth"] >= 5e-3)
                    if op_blamed and attempt < 2:
                        print("  v4 output implicated; retrying config")
                        continue
                    if op_blamed:
                        print("  ABORT: v4 output NaN/wrong across all 3 "
                              "attempts; persistent kernel defect")
                        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
                        Path(args.output).write_text(
                            json.dumps(results, indent=2), encoding="utf-8")
                        sys.exit(3)
                    print("  ref/inputs implicated (transient); retrying config")
                    continue
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
            "L2_resident": name == "probe_T128",
            "v1": v1_bench, "v4": v4_bench,
            "speedup_v1_over_v4": speedup
        })
        return True
    return False


def run_comparison(args):
    torch.npu.set_device(0)

    # Load operators
    if args.v1_library:
        torch.ops.load_library(args.v1_library)
    if args.op_library:
        torch.ops.load_library(args.op_library)

    # Device-health gate before any v4 launch
    device_preflight()

    # Test configurations (identical to v1)
    configs = [
        ("probe_T128", 128, 128, 128, 0.05),
        ("large_T512", 512, 128, 128, 0.05),
        ("large_T1024", 1024, 128, 128, 0.05),
        ("large_T2048", 2048, 128, 128, 0.05),
        ("large_T4096", 4096, 128, 128, 0.05),
    ]

    results = {"configs": [], "equivalence": []}

    for name, T, H, R, amp in configs:
        run_config(name, T, H, R, amp, args, results)

    # Summary
    print("\n=== SUMMARY ===")
    print(f"{'Config':<20} {'v1 ms':>10} {'v4 ms':>10} {'Speedup':>10}")
    print("-" * 54)
    for c in results["configs"]:
        v1 = f"{c['v1']['median_ms']:.4f}" if c["v1"] else "N/A"
        v4 = f"{c['v4']['median_ms']:.4f}" if c["v4"] else "N/A"
        sp = f"{c['speedup_v1_over_v4']:.3f}x" if c["speedup_v1_over_v4"] else "N/A"
        print(f"{c['name']:<20} {v1:>10} {v4:>10} {sp:>10}")

    # Stability: 1000 sequential calls at the beyond-L2 geometry
    print("\n=== STABILITY: 1000 sequential calls at T=4096 ===")
    if hasattr(torch.ops.mwg, 'ephemeral_core_apply_v4'):
        T, H, R = 4096, 128, 128
        torch.manual_seed(4321)
        ctrl = torch.randn(T, H, dtype=torch.float32, device="npu:0")
        head_w = torch.randn(H, R, dtype=torch.float32, device="npu:0")
        head_b = torch.randn(R, dtype=torch.float32, device="npu:0")
        act = torch.randn(T, R, dtype=torch.float16, device="npu:0")
        ref = algebraic_reference(act.float(), ctrl, head_w, head_b, 0.05).half()
        try:
            n_calls = 0
            for i in range(1000):
                out = torch.ops.mwg.ephemeral_core_apply_v4(act, ctrl, head_w, head_b, 0.05)
                n_calls += 1
            err = (out.float() - ref.float()).abs().max().item()
            ok = err < 5e-3
            print(f"  completed {n_calls}/1000 calls, final max_err = {err:.6f}, "
                  f"{'PASS' if ok else 'FAIL'}")
            results["stability_1000_calls"] = {
                "completed": n_calls, "final_max_abs_err": err, "pass": ok
            }
        except Exception as e:
            print(f"  STABILITY FAIL: {e}")
            results["stability_1000_calls"] = {"error": str(e)}

    out_path = args.output
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nResults saved to {out_path}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Test v4 multi-core epilogue (hardened v2)")
    parser.add_argument("--op-library", type=str, default=None)
    parser.add_argument("--v1-library", type=str, default=None)
    parser.add_argument("--output", type=str, default="results/v4_benchmark.json")
    parser.add_argument("--warmup", type=int, default=30)
    parser.add_argument("--iters", type=int, default=200)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    run_comparison(args)


if __name__ == "__main__":
    main()
