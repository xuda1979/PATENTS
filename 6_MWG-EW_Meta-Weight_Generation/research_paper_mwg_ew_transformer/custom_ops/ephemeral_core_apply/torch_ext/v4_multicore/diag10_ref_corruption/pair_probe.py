#!/usr/bin/env python3
"""ASI2 both-libs reproduction probe (2026-10-08).

Reproduces diag9's exact S1 sequence: load V1 then V4, probe seed-1234,
compute ref, call v1, call v4 — with before/after input snapshots and
per-call err tracking. Also tests load-order reversal (V4 then V1) in a
separate process invocation (--reverse).
"""
import json
import sys

import torch

V1_SO = "/root/work/mwg_torch_ext/build/libcustom_ops.so"
V4_SO = "/root/work/mwg_v4_torch_ext/build/libcustom_ops_v4.so"
TOL = 0.01


def ref_out(act, ctrl, weight, bias, amp):
    ctrl16 = ctrl.to(torch.float16).float()
    w16 = weight.to(torch.float16).float()
    core = torch.tanh(ctrl16 @ w16 + bias) * amp + 1.0
    return act.float() * core


def probe(T=128, H=128, R=128, seed=1234, amp=0.05):
    g = torch.Generator(device="cpu").manual_seed(seed)
    act = (torch.randn(T, R, generator=g) * 0.5).to(torch.float16).npu()
    ctrl = (torch.randn(T, H, generator=g) * 0.5).to(torch.float32).npu()
    weight = (torch.randn(H, R, generator=g) * 0.1).to(torch.float32).npu()
    bias = (torch.randn(R, generator=g) * 0.05).to(torch.float32).npu()
    return act, ctrl, weight, bias, amp


def snap(t):
    return t.detach().to("cpu").clone()


def maxdiff(a, b):
    return float((a.float() - b.float()).abs().max().item())


def main():
    reverse = "--reverse" in sys.argv
    r = {"reverse_load_order": reverse}

    torch.npu.set_device(0)
    a = torch.randn(64, 64, device="npu", dtype=torch.float16)
    torch.npu.synchronize()
    assert torch.isfinite(a @ a).all().item(), "preflight failed"

    if reverse:
        torch.ops.load_library(V4_SO)
        torch.ops.load_library(V1_SO)
    else:
        torch.ops.load_library(V1_SO)
        torch.ops.load_library(V4_SO)

    act, ctrl, weight, bias, amp = probe()
    ref = ref_out(act, ctrl, weight, bias, amp)
    torch.npu.synchronize()

    act_b, ctrl_b, weight_b, bias_b = snap(act), snap(ctrl), snap(weight), snap(bias)
    ref_b = snap(ref)

    o1 = torch.ops.mwg.ephemeral_core_apply(act, ctrl, weight, bias, amp)
    torch.npu.synchronize()
    o4 = torch.ops.mwg.ephemeral_core_apply_v4(act, ctrl, weight, bias, amp)
    torch.npu.synchronize()

    r["input_corruption_after_both_calls"] = {
        "act": maxdiff(act_b, snap(act)),
        "ctrl": maxdiff(ctrl_b, snap(ctrl)),
        "weight": maxdiff(weight_b, snap(weight)),
        "bias": maxdiff(bias_b, snap(bias)),
    }
    r["ref_corruption"] = maxdiff(ref_b, snap(ref))
    r["v1_err"] = maxdiff(snap(o1), ref_b)
    r["v4_err"] = maxdiff(snap(o4), ref_b)
    r["v1_vs_v4"] = maxdiff(snap(o1), snap(o4))
    r["v1_pass"] = r["v1_err"] <= TOL
    r["v4_pass"] = r["v4_err"] <= TOL

    # repeats (S5 analog)
    r["repeat_errs_v1"] = []
    r["repeat_errs_v4"] = []
    for _ in range(4):
        o1x = torch.ops.mwg.ephemeral_core_apply(act, ctrl, weight, bias, amp)
        o4x = torch.ops.mwg.ephemeral_core_apply_v4(act, ctrl, weight, bias, amp)
        torch.npu.synchronize()
        r["repeat_errs_v1"].append(maxdiff(snap(o1x), ref_b))
        r["repeat_errs_v4"].append(maxdiff(snap(o4x), ref_b))

    # S3-T128 analog: fresh tensors, same seed/geometry
    act2, ctrl2, weight2, bias2, amp2 = probe()
    ref2 = ref_out(act2, ctrl2, weight2, bias2, amp2)
    o1f = torch.ops.mwg.ephemeral_core_apply(act2, ctrl2, weight2, bias2, amp2)
    o4f = torch.ops.mwg.ephemeral_core_apply_v4(act2, ctrl2, weight2, bias2, amp2)
    torch.npu.synchronize()
    r["fresh_T128_v1_err"] = maxdiff(snap(o1f), snap(ref2))
    r["fresh_T128_v4_err"] = maxdiff(snap(o4f), snap(ref2))

    out = f"/tmp/asi2_pair_probe{'_rev' if reverse else ''}.json"
    json.dump(r, open(out, "w"), indent=1)
    print(json.dumps(r, indent=1))
    print("WROTE", out)
    print("REPRODUCED" if not (r["v1_pass"] and r["v4_pass"]) else "NOT_REPRODUCED")


if __name__ == "__main__":
    main()
