#!/usr/bin/env python3
"""Discriminate ASI3 v1-NaN: device-0 hardware fault vs software bug.

Runs, in ONE process per device, the exact P1-style probe from
diag_t128_discriminator.py (v1, T=128, H=R=128, amp=0.05, seed 1234,
head_weight [H,R] convention, same inputs x N calls), pinned to the
device index given on the command line.  If some devices pass
deterministically while device 0 fails, the fault is device-0 hardware
(or device-0-local state); if all devices fail identically, the fault is
in software/environment shared across devices.

Usage (ON the NPU host, one process per device):
    python3 diag4_device_sweep.py <device_index> [n_calls] [out_json]

Defaults: n_calls=4, out_json=results/diag4_dev<idx>.json
"""
import json
import math
import os
import sys

import torch
import torch_npu  # noqa: F401  (registers the npu backend)

H = 128
R = 128
V1_SO = "/root/work/mwg_torch_ext/build/libcustom_ops.so"


def reference(ctrl, head_w, head_b, act, amplitude):
    """Shipped kernel contract: head_weight is [H, R], no transpose."""
    logits = ctrl @ head_w + head_b  # [T, R]
    core = 1.0 + amplitude * torch.tanh(logits)
    return act * core


def probe(device, n_calls, results):
    torch.npu.set_device(device)
    dev = f"npu:{device}"
    # sanity: plain matmul on THIS device
    a = torch.randn(128, 128, device=dev)
    b = a @ a
    torch.npu.synchronize()
    print(f"sanity matmul on {dev}: finite="
          f"{bool(torch.isfinite(b).all().item())}")

    torch.ops.load_library(V1_SO)

    T = 128
    torch.manual_seed(1234)
    ctrl = torch.randn(T, H, dtype=torch.float32, device=dev)
    head_w = torch.randn(H, R, dtype=torch.float32, device=dev)
    head_b = torch.randn(R, dtype=torch.float32, device=dev)
    act = torch.randn(T, R, dtype=torch.float16, device=dev)

    ref = reference(ctrl.float(), head_w, head_b, act.float(), 0.05).half()
    torch.npu.synchronize()

    for k in range(n_calls):
        out = torch.ops.mwg.ephemeral_core_apply(act, ctrl, head_w, head_b,
                                                 0.05)
        torch.npu.synchronize()
        err = (out.float() - ref.float()).abs().max().item()
        nan = bool(torch.isnan(out.float()).any().item())
        ok = (not math.isnan(err)) and err < 5e-3
        print(f"P1 dev{device} call{k + 1}: max_err={err:.6f} "
              f"nan={nan} PASS={ok}")
        results[f"P1 dev{device} call{k + 1}"] = {
            "max_err": err, "nan_count": int(
                torch.isnan(out.float()).sum().item()), "pass": ok,
        }


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    device = int(sys.argv[1])
    n_calls = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    out_json = (sys.argv[3] if len(sys.argv) > 3
                else f"results/diag4_dev{device}.json")

    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    results = {}
    probe(device, n_calls, results)

    n_pass = sum(1 for r in results.values() if r["pass"])
    print(f"\n=== diag4 dev{device}: {n_pass}/{len(results)} PASS ===")
    results["_summary"] = {"device": device, "pass": n_pass,
                           "total": len(results)}
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"results written to {out_json}")


if __name__ == "__main__":
    main()
