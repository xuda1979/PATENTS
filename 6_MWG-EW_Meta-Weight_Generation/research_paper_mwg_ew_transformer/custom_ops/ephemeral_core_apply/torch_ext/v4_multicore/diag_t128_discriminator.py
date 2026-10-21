#!/usr/bin/env python3
"""Discriminate the ASI3 v1-NaN@T128: kernel bug vs device anomaly.

Bisects the failure using v1's built-in diagnostic amplitudes and geometry/
seed sweeps, all against the shipped v1 library in ONE process:

  P1  repeat baseline: v1@T128 seed 1234 x3 calls (determinism within process)
  P2  amp=-1.0 canary: launch+copy path only (no matmul); NaN here means the
      fault is in launch/tiling/DataCopy, not the matmul/core path
  P3  amp=-2.0 core-only: out = 1+0.5*tanh(A@B+bias), skips the final Mul
  P4  seed sweep: seeds 1234/456/789 at T=128 (input-dependent vs structural)
  P5  geometry sweep: T=64,96,128,160,192,256,384,512 at H=R=128 (tiling edge)
  P6  NaN fingerprint: at T=128, which output elements are NaN (row pattern)

Usage: python3 diag_t128_discriminator.py [results_out_json]
Writes human-readable lines to stdout; optionally dumps JSON.
"""
import json
import math
import sys
from collections import Counter

import torch

V1_SO = "/root/work/mwg_torch_ext/build/libcustom_ops.so"

H, R = 128, 128


def make_inputs(T, seed=1234, device="npu:0"):
    torch.manual_seed(seed)
    ctrl = torch.randn(T, H, dtype=torch.float32, device=device)
    head_w = torch.randn(H, R, dtype=torch.float32, device=device)
    head_b = torch.randn(R, dtype=torch.float32, device=device)
    act = torch.randn(T, R, dtype=torch.float16, device=device)
    return act, ctrl, head_w, head_b


def reference(act, ctrl, head_w, head_b, amp):
    logits = ctrl @ head_w + head_b
    core = 1.0 + amp * torch.tanh(logits)
    return act * core


def run_case(name, T, amp, seed=1234, fingerprint=False, results=None):
    act, ctrl, head_w, head_b = make_inputs(T, seed)
    if amp in (-1.0, -2.0):
        # diagnostic paths: reference undefined for the fill value; just
        # inspect output finiteness and value distribution
        out = torch.ops.mwg.ephemeral_core_apply(act, ctrl, head_w, head_b, amp)
        torch.npu.synchronize()
        o = out.float()
        n_nan = int(torch.isnan(o).sum().item())
        n_inf = int(torch.isinf(o).sum().item())
        print(f"{name}: shape={tuple(o.shape)} nan={n_nan} inf={n_inf} "
              f"finite={bool(torch.isfinite(o).all().item())}")
        if fingerprint and n_nan:
            _fingerprint(name, out, results)
        if results is not None:
            results[name] = {"nan": n_nan, "inf": n_inf}
        return out

    ref = reference(act.float(), ctrl, head_w, head_b, amp).half()
    out = torch.ops.mwg.ephemeral_core_apply(act, ctrl, head_w, head_b, amp)
    torch.npu.synchronize()
    o = out.float()
    n_nan = int(torch.isnan(o).sum().item())
    n_inf = int(torch.isinf(o).sum().item())
    err = (o - ref.float()).abs().max().item()
    print(f"{name}: max_err={err:.6f} nan={n_nan} inf={n_inf} "
          f"PASS={(err < 5e-3) and n_nan == 0}")
    if fingerprint and n_nan:
        _fingerprint(name, out, results)
    if results is not None:
        results[name] = {"max_err": err, "nan": n_nan, "inf": n_inf,
                         "pass": bool(err < 5e-3 and n_nan == 0)}
    return out


def _fingerprint(name, out, results):
    o = out.float()
    nan_mask = torch.isnan(o)
    T_act = o.shape[0]
    # which rows contain NaN
    nan_rows = torch.nonzero(nan_mask.any(dim=1)).flatten().tolist()
    nan_cols = torch.nonzero(nan_mask.any(dim=0)).flatten().tolist()
    rows_with = len(nan_rows)
    total_nan = int(nan_mask.sum().item())
    print(f"    fingerprint: {total_nan} NaN els; {rows_with}/{T_act} rows; "
          f"first rows {nan_rows[:12]}")
    print(f"    nan col range: {min(nan_cols) if nan_cols else '-'}.."
          f"{max(nan_cols) if nan_cols else '-'} "
          f"({len(nan_cols)} cols)")
    # row-pattern classification: all-rows vs contiguous block vs scattered
    if rows_with == T_act:
        print("    pattern: ALL rows affected")
    elif rows_with == 0:
        print("    pattern: no rows (element-scattered)")
    else:
        contiguous = nan_rows == list(range(nan_rows[0],
                                            nan_rows[0] + rows_with))
        if contiguous:
            print(f"    pattern: CONTIGUOUS block from row {nan_rows[0]}")
        else:
            print("    pattern: SCATTERED rows")
    if results is not None:
        results.setdefault(name + "_fingerprint", {}).update({
            "total_nan": total_nan, "rows_with_nan": rows_with,
            "first_rows": nan_rows[:32],
            "nan_col_min": min(nan_cols) if nan_cols else None,
            "nan_col_max": max(nan_cols) if nan_cols else None,
        })


def main():
    out_json = sys.argv[1] if len(sys.argv) > 1 else None
    torch.npu.set_device(0)
    results = {}

    # sanity: plain matmul on device
    a = torch.randn(128, 128, device="npu:0")
    b = a @ a
    torch.npu.synchronize()
    print(f"sanity matmul: finite={bool(torch.isfinite(b).all().item())}")

    torch.ops.load_library(V1_SO)
    print(f"loaded v1: {V1_SO}")

    # P1: baseline determinism — 3 calls, same inputs
    print("\n--- P1: baseline v1@T128 x3 (same inputs) ---")
    for k in range(3):
        run_case(f"P1 call{k+1}", 128, 0.05, fingerprint=(k == 0),
                 results=results)

    # P2: canary — launch + UB->GM copy only, matmul skipped (fill 3.0)
    print("\n--- P2: amp=-1.0 launch/copy canary @T128 ---")
    run_case("P2 canary T128", 128, -1.0, results=results)

    # P3: core-only — 1+0.5*tanh(A@B+bias), no final Mul
    print("\n--- P3: amp=-2.0 core-only @T128 ---")
    run_case("P3 coreonly T128", 128, -2.0, fingerprint=True,
             results=results)

    # P4: seed sweep
    print("\n--- P4: seed sweep @T128 ---")
    for seed in (1234, 456, 789):
        run_case(f"P4 seed{seed}", 128, 0.05, seed=seed, results=results)

    # P5: geometry sweep over T
    print("\n--- P5: T sweep (H=R=128) ---")
    for T in (64, 96, 128, 160, 192, 256, 384, 512):
        run_case(f"P5 T{T}", T, 0.05, results=results)

    # P6: fresh-process baseline confirmed at T2048 (known-pass control)
    print("\n--- P6: control T2048 ---")
    run_case("P6 T2048", 2048, 0.05, results=results)

    if out_json:
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"\nresults written to {out_json}")


if __name__ == "__main__":
    main()
