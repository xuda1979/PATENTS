#!/usr/bin/env python3
"""Bisect the harness-only v1-NaN on ASI3: preflight? seed? fp16 ref? device obj?

Replicates test_v4_multicore.py's run_comparison() step by step, printing
fingerprint after each stage, to find which minimal difference vs the
passing diag4_device_sweep.py triggers the NaN.  All in ONE process.

Stages (in order, checkpoint after each):
  S1  set_device + load v1 library                     (diag4 baseline)
  S2  + device_preflight() (harness fp16 matmul check)
  S3  + torch.device("npu:0") object                   (harness style)
  S4  probe v1 T128 exactly like harness (fp16 ref via .half())
  S5  repeat probe x3 (determinism in-process)

Usage: python3 diag6_bisect.py [out_json]
"""
import json
import math
import sys

import torch
import torch_npu  # noqa: F401

H = 128
R = 128
V1_SO = "/root/work/mwg_torch_ext/build/libcustom_ops.so"


def algebraic_reference(rank_activation, controller_hidden, head_weight,
                        head_bias, amplitude):
    logits = controller_hidden @ head_weight + head_bias
    core = 1.0 + amplitude * torch.tanh(logits)
    return rank_activation * core


def device_preflight():
    x = torch.randn(128, 128, dtype=torch.float16, device="npu:0")
    w = torch.randn(128, 128, dtype=torch.float16, device="npu:0")
    y = (x.float() @ w.float()).half()
    y_ref = y.clone()
    if not torch.allclose(y, y_ref):
        print("PREFLIGHT FAIL: non-deterministic")
        sys.exit(3)
    if torch.isnan(y).any() or torch.isinf(y).any():
        print("PREFLIGHT FAIL: NaN/Inf")
        sys.exit(3)
    print("preflight: device healthy")


def fingerprint(tag, out, ref, results):
    diff = (out.float() - ref.float()).abs()
    err = diff.max().item()
    nan = bool(torch.isnan(out.float()).any().item())
    out32 = out.float()
    nan_mask = torch.isnan(out32)
    nan_rows = sorted(set(torch.nonzero(nan_mask)[:, 0].tolist()))
    print(f"  {tag}: max_err={err:.6f} out_nan={nan} "
          f"nan_els={int(nan_mask.sum().item())} "
          f"nan_rows={len(nan_rows)}/{out.shape[0]}"
          f"{' first=' + str(nan_rows[:8]) if nan_rows else ''}")
    results[tag] = {"max_err": err, "nan": nan,
                    "nan_els": int(nan_mask.sum().item()),
                    "pass": (not math.isnan(err)) and err < 5e-3}
    return results


def probe_harness_style(results, T=128, label="probe"):
    device = torch.device("npu:0")
    torch.manual_seed(1234)
    ctrl = torch.randn(T, H, dtype=torch.float32, device=device)
    head_w = torch.randn(H, R, dtype=torch.float32, device=device)
    head_b = torch.randn(R, dtype=torch.float32, device=device)
    act = torch.randn(T, R, dtype=torch.float16, device=device)
    ref = algebraic_reference(act.float(), ctrl, head_w, head_b,
                              0.05).half()
    out = torch.ops.mwg.ephemeral_core_apply(act, ctrl, head_w, head_b, 0.05)
    torch.npu.synchronize()
    fingerprint(f"{label} T{T}", out, ref, results)
    return out, ref


def main():
    out_json = sys.argv[1] if len(sys.argv) > 1 else "results/diag6_bisect.json"
    results = {}

    print("S1: set_device + load v1")
    torch.npu.set_device(0)
    torch.ops.load_library(V1_SO)

    # diag4-style probe immediately after load
    torch.manual_seed(1234)
    ctrl = torch.randn(128, H, dtype=torch.float32, device="npu:0")
    head_w = torch.randn(H, R, dtype=torch.float32, device="npu:0")
    head_b = torch.randn(R, dtype=torch.float32, device="npu:0")
    act = torch.randn(128, R, dtype=torch.float16, device="npu:0")
    ref = algebraic_reference(act.float(), ctrl, head_w, head_b, 0.05).half()
    out = torch.ops.mwg.ephemeral_core_apply(act, ctrl, head_w, head_b, 0.05)
    torch.npu.synchronize()
    fingerprint("S1 diag4-style first call", out, ref, results)

    print("S2: + device_preflight()")
    device_preflight()
    probe_harness_style(results, label="S2 after-preflight")

    print("S3/S4: harness-style probe x3 (same inputs each time)")
    for k in range(3):
        probe_harness_style(results, label=f"S4 repeat{k + 1}")

    n_pass = sum(1 for v in results.values() if v.get("pass"))
    print(f"\n=== diag6 bisect: {n_pass}/{len(results)} PASS ===")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"results written to {out_json}")


if __name__ == "__main__":
    main()
