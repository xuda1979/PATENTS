#!/usr/bin/env python3
"""Diag 9: validation of the FIXED v1 + v4 pair (2026-10-02 root-cause fix).

Both libs rebuilt with:
  (1) pointer-keyed fp16 weight cache REMOVED (cast per call)
  (2) workspace zeroed via aclrtMemset after aclrtMalloc

Sections (all must pass):
  S1  probe_T128 first-call + repeat, v1 and v4 vs fp32 reference
  S2  weight recycling: v1 and v4 with a NEW weight at a RECYCLED address
      (the diag7 S3 scenario that caught the stale cache) - err must be
      <= fp16 noise, NOT 0.14
  S3  T sweep {64,128,192,256,512,2048} both ops vs reference
      (all multiples of 64: v4 requires T % 64 == 0; 160 violated it)
  S4  v4-specific: block_dim>1 path (T=1024 -> 8 cores), correctness
  S5  5x repeat stability both ops
"""

import json
import os
import sys

import torch
import torch_npu

V1_SO = "/root/work/mwg_torch_ext/build/libcustom_ops.so"
V4_SO = "/root/work/mwg_v4_torch_ext/build/libcustom_ops_v4.so"
OUT = "/root/work/filestorage/mwg-ew-transformer-research/results/diag9_fixed_pair_validation.json"
TOL = 0.01  # well above fp16 noise (~0.002), far below stale-cache err (0.14)


def fingerprint(t):
    if t is None:
        return None
    f = t.float()
    return {
        "nan": int(torch.isnan(f).sum().item()),
        "inf": int(torch.isinf(f).sum().item()),
    }


def run_op(ns, op, act, ctrl, weight, bias, amp):
    try:
        out = torch.ops.__getattr__(ns).__getattr__(op)(
            act, ctrl, weight, bias, amp)
        torch.npu.synchronize()
        return out
    except Exception as e:  # noqa: BLE001
        print(f"EXC in {ns}.{op}: {type(e).__name__}: {e}", file=sys.stderr)
        return None


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


def check(tag, out, ref, r, sec):
    if out is None:
        sec[tag] = {"ok": False, "why": "exception"}
        return False
    err = float((out.float() - ref).abs().max().item())
    fp = fingerprint(out)
    ok = fp["nan"] == 0 and fp["inf"] == 0 and err <= TOL
    sec[tag] = {"ok": ok, "err": err, **fp}
    return ok


def main():
    r = {"sections": {}, "pass": True}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)

    torch.npu.set_device(0)
    a = torch.randn(64, 64, device="npu", dtype=torch.float16)
    torch.npu.synchronize()
    assert torch.isfinite(a @ a).all().item(), "preflight failed"

    torch.ops.load_library(V1_SO)
    torch.ops.load_library(V4_SO)

    # S1: probe_T128
    s1 = {}
    act, ctrl, weight, bias, amp = probe()
    ref = ref_out(act, ctrl, weight, bias, amp)
    o1 = run_op("mwg", "ephemeral_core_apply", act, ctrl, weight, bias, amp)
    o4 = run_op("mwg", "ephemeral_core_apply_v4", act, ctrl, weight, bias, amp)
    p1 = check("v1", o1, ref, r, s1)
    p4 = check("v4", o4, ref, r, s1)
    # repeat
    o1r = run_op("mwg", "ephemeral_core_apply", act, ctrl, weight, bias, amp)
    o4r = run_op("mwg", "ephemeral_core_apply_v4", act, ctrl, weight, bias, amp)
    p1r = check("v1_repeat", o1r, ref, r, s1)
    p4r = check("v4_repeat", o4r, ref, r, s1)
    r["sections"]["S1"] = s1
    r["pass"] = r["pass"] and p1 and p4 and p1r and p4r
    print("S1:", json.dumps(s1))

    # S2: weight recycling (diag7 S3 scenario)
    s2 = {}
    act2, ctrl2, _, bias2, amp2 = probe(seed=777)
    W0 = (torch.randn(128, 128) * 0.1).to(torch.float32).npu()
    run_op("mwg", "ephemeral_core_apply", act2, ctrl2, W0, bias2, amp2)
    run_op("mwg", "ephemeral_core_apply_v4", act2, ctrl2, W0, bias2, amp2)
    addr0 = W0.data_ptr()
    del W0
    W1 = (torch.randn(128, 128) * 0.1).to(torch.float32).npu()
    s2["recycled_addr"] = bool(W1.data_ptr() == addr0)
    ref2 = ref_out(act2, ctrl2, W1, bias2, amp2)
    o1w = run_op("mwg", "ephemeral_core_apply", act2, ctrl2, W1, bias2, amp2)
    o4w = run_op("mwg", "ephemeral_core_apply_v4", act2, ctrl2, W1, bias2, amp2)
    p1w = check("v1_new_weight", o1w, ref2, r, s2)
    p4w = check("v4_new_weight", o4w, ref2, r, s2)
    r["sections"]["S2"] = s2
    r["pass"] = r["pass"] and p1w and p4w
    print("S2:", json.dumps(s2))

    # S3: T sweep.  All T must be multiples of 64: v4 requires
    # T % BASE_M_V4(64) == 0 (v1 pads, v4 does not), so 160 was replaced
    # with 192 (still exercises the 3-tile odd case for v4's 8-core split).
    s3 = {}
    ok3 = True
    for T in (64, 128, 192, 256, 512, 2048):
        aT, cT, wT, bT, amT = probe(T=T)
        refT = ref_out(aT, cT, wT, bT, amT)
        e = {}
        okT = True
        o1T = run_op("mwg", "ephemeral_core_apply", aT, cT, wT, bT, amT)
        okT &= check("v1", o1T, refT, r, e)
        o4T = run_op("mwg", "ephemeral_core_apply_v4", aT, cT, wT, bT, amT)
        okT &= check("v4", o4T, refT, r, e)
        s3[f"T{T}"] = e
        ok3 &= okT
        print(f"S3 T={T}:", json.dumps(e))
    r["sections"]["S3"] = s3
    r["pass"] = r["pass"] and ok3

    # S4: v4 multi-core path (T=1024 -> 8 cores)
    s4 = {}
    a4, c4, w4, b4, am4 = probe(T=1024)
    ref4 = ref_out(a4, c4, w4, b4, am4)
    o4m = run_op("mwg", "ephemeral_core_apply_v4", a4, c4, w4, b4, am4)
    p4m = check("v4_T1024_multicore", o4m, ref4, r, s4)
    r["sections"]["S4"] = s4
    r["pass"] = r["pass"] and p4m
    print("S4:", json.dumps(s4))

    # S5: repeat x5
    s5 = {}
    ok5 = True
    for i in range(5):
        o1x = run_op("mwg", "ephemeral_core_apply", act, ctrl, weight, bias, amp)
        o4x = run_op("mwg", "ephemeral_core_apply_v4", act, ctrl, weight, bias, amp)
        e = {}
        ok5 &= check("v1", o1x, ref, r, e)
        ok5 &= check("v4", o4x, ref, r, e)
        s5[f"call{i+1}"] = e
    r["sections"]["S5"] = s5
    r["pass"] = r["pass"] and ok5
    print("S5:", json.dumps(s5))

    json.dump(r, open(OUT, "w"), indent=1)
    print("WROTE", OUT)
    print("OVERALL_PASS" if r["pass"] else "OVERALL_FAIL")


if __name__ == "__main__":
    main()
