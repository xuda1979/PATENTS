#!/usr/bin/env python3
"""Isolate the ASI3 v1-NaN: run v1 alone, v4 alone, then both, in ONE process.

Mode A: load v1 only -> probe v1.
Mode B: load v4 only -> probe v4.
Mode C: load v1 then v4 -> probe v1, then v4.

Each probe uses the fixed test's exact convention (head_weight [H,R],
algebraic reference), seed 1234, probe_T128 geometry first, then large_T2048.

Run ON ASI3:
  python3 diag_v1_nan.py A   # v1 only
  python3 diag_v1_nan.py B   # v4 only
  python3 diag_v1_nan.py C   # both
"""
import math
import sys

import torch

V1_SO = "/root/work/mwg_torch_ext/build/libcustom_ops.so"
V4_SO = "/root/work/mwg_v4_torch_ext/build/libcustom_ops_v4.so"


def reference(act, ctrl, head_w, head_b, amp):
    logits = ctrl @ head_w + head_b
    core = 1.0 + amp * torch.tanh(logits)
    return act * core


def probe(name, op, T=128, H=128, R=128, amp=0.05):
    torch.manual_seed(1234)
    ctrl = torch.randn(T, H, dtype=torch.float32, device="npu:0")
    head_w = torch.randn(H, R, dtype=torch.float32, device="npu:0")
    head_b = torch.randn(R, dtype=torch.float32, device="npu:0")
    act = torch.randn(T, R, dtype=torch.float16, device="npu:0")
    ref = reference(act.float(), ctrl, head_w, head_b, amp).half()
    try:
        out = op(act, ctrl, head_w, head_b, amp)
        err = (out.float() - ref.float()).abs().max().item()
        print(f"{name}: max_err={err:.6f} nan={math.isnan(err)} "
              f"out_nan={torch.isnan(out.float()).any().item()} "
              f"PASS={err < 5e-3}")
        return err
    except Exception as e:
        print(f"{name}: EXCEPTION {type(e).__name__}: {e}")
        return None


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "A"
    torch.npu.set_device(0)

    # sanity: plain matmul on device
    a = torch.randn(128, 128, device="npu:0")
    b = a @ a
    torch.npu.synchronize()
    print(f"sanity matmul: finite={torch.isfinite(b).all().item()}")

    if mode == "A":
        torch.ops.load_library(V1_SO)
        print("loaded v1 only")
        probe("A v1 T128", lambda *x: torch.ops.mwg.ephemeral_core_apply(*x))
        probe("A v1 T2048", lambda *x: torch.ops.mwg.ephemeral_core_apply(*x), T=2048)
    elif mode == "B":
        torch.ops.load_library(V4_SO)
        print("loaded v4 only")
        probe("B v4 T128", lambda *x: torch.ops.mwg.ephemeral_core_apply_v4(*x))
        probe("B v4 T2048", lambda *x: torch.ops.mwg.ephemeral_core_apply_v4(*x), T=2048)
    elif mode == "C":
        torch.ops.load_library(V1_SO)
        torch.ops.load_library(V4_SO)
        print("loaded v1 then v4")
        probe("C v1 T128", lambda *x: torch.ops.mwg.ephemeral_core_apply(*x))
        probe("C v4 T128", lambda *x: torch.ops.mwg.ephemeral_core_apply_v4(*x))
        probe("C v1 T2048", lambda *x: torch.ops.mwg.ephemeral_core_apply(*x), T=2048)
        probe("C v4 T2048", lambda *x: torch.ops.mwg.ephemeral_core_apply_v4(*x), T=2048)
    else:
        print(f"unknown mode {mode}")
        sys.exit(2)


if __name__ == "__main__":
    main()
