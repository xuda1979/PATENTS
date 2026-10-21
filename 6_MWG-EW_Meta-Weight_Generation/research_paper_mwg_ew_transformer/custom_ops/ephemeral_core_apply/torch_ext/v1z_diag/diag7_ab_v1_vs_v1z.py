#!/usr/bin/env python3
"""Diag 7: A/B test shipped v1 vs v1z in ONE process on the SAME device.

v1z is byte-identical to the shipped v1 except:
  (a) workspace zeroed via aclrtMemset right after aclrtMalloc
  (b) pointer-keyed fp16 weight cache removed (convert per call)
  (c) op registered as mwgz::ephemeral_core_apply_z

Decision rule:
  - shipped v1 NaNs/garbage while v1z passes  => device-wedged theory is
    DEAD; the fault is a v1 software bug (cache/workspace).
  - both fail identically                     => kernel/launch-level fault,
    device/driver side.

Sections:
  S0  load both .so; preflight (small matmul gate)
  S1  FRESH-PROCESS FIRST-CALL: v1 call1, v1z call1, on IDENTICAL inputs
      (probe geometry T=128 H=128 R=128 amp=0.05 seed=1234)
  S2  after-preflight replication of the harness order (preflight, then
      v1, then v1z, then v1 again) - reproduces the diag6 S2 pattern
  S3  weight-tensor recycling: allocate/free weight tensors so a NEW
      weight lands at a RECYCLED address; v1's pointer-keyed cache
      would then serve stale fp16 bytes.  v1 vs v1z side by side.
  S4  T sweep: T in {64, 128, 160, 256, 512, 2048}, v1 vs v1z on each,
      same seed and identical tensors
  S5  repeat probe_T128 x5 both arms - call-count stability
"""

import json
import os
import sys
import traceback

import torch
import torch_npu

V1_SO = "/root/work/mwg_torch_ext/build/libcustom_ops.so"
V1Z_SO = "/root/work/mwgz_torch_ext/build/libcustom_ops_z.so"
OUT = "/root/work/filestorage/mwg-ew-transformer-research/results/diag7_ab_v1_vs_v1z.json"


def fingerprint(t):
    """Compact numeric fingerprint of a tensor."""
    if t is None:
        return None
    f = t.float()
    nan_count = int(torch.isnan(f).sum().item())
    inf_count = int(torch.isinf(f).sum().item())
    finite = f[torch.isfinite(f)]
    if finite.numel() == 0:
        stats = {"max": None, "min": None, "mean": None}
    else:
        stats = {
            "max": float(finite.max().item()),
            "min": float(finite.min().item()),
            "mean": float(finite.mean().item()),
        }
    return {"nan": nan_count, "inf": inf_count, **stats}


def run_arm(torch_lib_ns, op, act, ctrl, weight, bias, amp):
    """Call one arm; return (out, fp) or (None, error string)."""
    try:
        out = torch.ops.__getattr__(torch_lib_ns).__getattr__(op)(
            act, ctrl, weight, bias, amp)
        torch.npu.synchronize()
        return out, fingerprint(out)
    except Exception as e:  # noqa: BLE001
        return None, f"EXC: {type(e).__name__}: {e}"


def ref_out(act, ctrl, weight, bias, amp):
    """Pure-torch fp32 reference (same formula as the kernel)."""
    ctrl16 = ctrl.to(torch.float16).float()
    w16 = weight.to(torch.float16).float()
    b16 = bias.to(torch.float16).float() if bias.dtype != torch.float32 else bias
    a = act.float()
    core = torch.tanh(ctrl16 @ w16 + b16) * amp + 1.0
    return a * core


def probe_tensors(T=128, H=128, R=128, seed=1234, amp=0.05):
    g = torch.Generator(device="cpu").manual_seed(seed)
    act = (torch.randn(T, R, generator=g) * 0.5).to(torch.float16).npu()
    ctrl = (torch.randn(T, H, generator=g) * 0.5).to(torch.float32).npu()
    weight = (torch.randn(H, R, generator=g) * 0.1).to(torch.float32).npu()
    bias = (torch.randn(R, generator=g) * 0.05).to(torch.float32).npu()
    return act, ctrl, weight, bias, amp


def main():
    r = {"sections": {}}
    out_dir = os.path.dirname(OUT)
    os.makedirs(out_dir, exist_ok=True)

    # ---- S0: load + preflight ----
    s0 = {}
    try:
        torch.npu.set_device(0)
        s0["device"] = torch.npu.get_device_name(0)
        a = torch.randn(64, 64, device="npu", dtype=torch.float16)
        b = torch.randn(64, 64, device="npu", dtype=torch.float16)
        c = a @ b
        torch.npu.synchronize()
        s0["preflight_matmul"] = fingerprint(c)
        s0["preflight_ok"] = bool(torch.isfinite(c).all().item())
        torch.ops.load_library(V1_SO)
        s0["v1_loaded"] = True
        torch.ops.load_library(V1Z_SO)
        s0["v1z_loaded"] = True
    except Exception as e:  # noqa: BLE001
        s0["error"] = f"{type(e).__name__}: {e}"
        s0["traceback"] = traceback.format_exc()
        r["sections"]["S0"] = s0
        json.dump(r, open(OUT, "w"), indent=1)
        print("S0 FAILED:", s0["error"])
        return 3
    r["sections"]["S0"] = s0
    print("S0:", json.dumps(s0))

    act, ctrl, weight, bias, amp = probe_tensors()
    ref = ref_out(act, ctrl, weight, bias, amp)
    ref_fp = fingerprint(ref)

    # ---- S1: fresh-process first-call on identical inputs ----
    s1 = {}
    s1["ref"] = ref_fp
    o_v1, fp_v1 = run_arm("mwg", "ephemeral_core_apply", act, ctrl, weight, bias, amp)
    s1["v1_call1"] = fp_v1
    if o_v1 is not None:
        s1["v1_call1_vs_ref"] = float((o_v1.float() - ref).abs().max().item())
    o_z, fp_z = run_arm("mwgz", "ephemeral_core_apply_z", act, ctrl, weight, bias, amp)
    s1["v1z_call1"] = fp_z
    if o_z is not None:
        s1["v1z_call1_vs_ref"] = float((o_z.float() - ref).abs().max().item())
    r["sections"]["S1"] = s1
    print("S1:", json.dumps(s1))

    # ---- S2: harness-order replication (preflight then v1 then v1z then v1) ----
    s2 = {}
    a = torch.randn(64, 64, device="npu", dtype=torch.float16)
    torch.npu.synchronize()
    s2["preflight"] = fingerprint(a @ a)
    o1, f1 = run_arm("mwg", "ephemeral_core_apply", act, ctrl, weight, bias, amp)
    s2["v1"] = f1
    oz, fz = run_arm("mwgz", "ephemeral_core_apply_z", act, ctrl, weight, bias, amp)
    s2["v1z"] = fz
    o2, f2 = run_arm("mwg", "ephemeral_core_apply", act, ctrl, weight, bias, amp)
    s2["v1_repeat"] = f2
    r["sections"]["S2"] = s2
    print("S2:", json.dumps(s2))

    # ---- S3: weight-tensor recycling ----
    # Make a first weight W0, call v1 (populates its pointer-keyed cache at
    # addr X), free W0, allocate W1 (different values) which the caching
    # allocator will likely place at the SAME addr X, call both arms.
    s3 = {}
    act3, ctrl3, _, bias3, amp3 = probe_tensors(seed=777)
    W0 = (torch.randn(128, 128) * 0.1).to(torch.float32).npu()
    o_w0, f_w0 = run_arm("mwg", "ephemeral_core_apply", act3, ctrl3, W0, bias3, amp3)
    s3["v1_w0"] = f_w0
    addr0 = W0.data_ptr()
    del W0
    W1 = (torch.randn(128, 128) * 0.1).to(torch.float32).npu()
    addr1 = W1.data_ptr()
    s3["recycled_addr"] = bool(addr0 == addr1)
    s3["addr0"] = addr0
    s3["addr1"] = addr1
    ref3 = ref_out(act3, ctrl3, W1, bias3, amp3)
    o_v1_w1, f_v1_w1 = run_arm("mwg", "ephemeral_core_apply", act3, ctrl3, W1, bias3, amp3)
    s3["v1_w1"] = f_v1_w1
    if o_v1_w1 is not None:
        s3["v1_w1_vs_ref_w1"] = float((o_v1_w1.float() - ref3).abs().max().item())
    o_z_w1, f_z_w1 = run_arm("mwgz", "ephemeral_core_apply_z", act3, ctrl3, W1, bias3, amp3)
    s3["v1z_w1"] = f_z_w1
    if o_z_w1 is not None:
        s3["v1z_w1_vs_ref_w1"] = float((o_z_w1.float() - ref3).abs().max().item())
    r["sections"]["S3"] = s3
    print("S3:", json.dumps(s3))

    # ---- S4: T sweep ----
    s4 = {}
    for T in (64, 128, 160, 256, 512, 2048):
        aT, cT, wT, bT, amT = probe_tensors(T=T, seed=1234)
        refT = ref_out(aT, cT, wT, bT, amT)
        e = {}
        ov, fv = run_arm("mwg", "ephemeral_core_apply", aT, cT, wT, bT, amT)
        e["v1"] = fv
        if ov is not None:
            e["v1_vs_ref"] = float((ov.float() - refT).abs().max().item())
        oz_, fz_ = run_arm("mwgz", "ephemeral_core_apply_z", aT, cT, wT, bT, amT)
        e["v1z"] = fz_
        if oz_ is not None:
            e["v1z_vs_ref"] = float((oz_.float() - refT).abs().max().item())
        s4[f"T{T}"] = e
        print(f"S4 T={T}:", json.dumps(e))
    r["sections"]["S4"] = s4

    # ---- S5: repeat probe_T128 x5 both arms ----
    s5 = {}
    a5, c5, w5, b5, am5 = probe_tensors()
    for i in range(5):
        ov, fv = run_arm("mwg", "ephemeral_core_apply", a5, c5, w5, b5, am5)
        oz_, fz_ = run_arm("mwgz", "ephemeral_core_apply_z", a5, c5, w5, b5, am5)
        s5[f"call{i+1}"] = {"v1": fv, "v1z": fz_}
        print(f"S5 call{i+1}: v1={fv} v1z={fz_}")
    r["sections"]["S5"] = s5

    json.dump(r, open(OUT, "w"), indent=1)
    print("WROTE", OUT)

    # ---- verdict ----
    def bad(fp):
        if isinstance(fp, str):
            return True
        return fp is None or fp["nan"] > 0 or fp["inf"] > 0

    v1_bad = [k for k, v in {
        "S1": s1.get("v1_call1"), "S2": s2.get("v1"),
        "S3": s3.get("v1_w1"),
    }.items() if bad(v)]
    v1z_bad = [k for k, v in {
        "S1": s1.get("v1z_call1"), "S2": s2.get("v1z"),
        "S3": s3.get("v1z_w1"),
    }.items() if bad(v)]
    v1_s4_bad = [t for t, e in s4.items() if bad(e.get("v1"))]
    v1z_s4_bad = [t for t, e in s4.items() if bad(e.get("v1z"))]
    print("\n==== VERDICT INPUTS ====")
    print("v1 NaN/garbage sections:", v1_bad, v1_s4_bad)
    print("v1z NaN/garbage sections:", v1z_bad, v1z_s4_bad)
    if v1_bad or v1_s4_bad:
        if not (v1z_bad or v1z_s4_bad):
            print("VERDICT: v1 FAILS, v1z PASSES -> SOFTWARE BUG in v1 "
                  "(weight cache / uninitialized workspace). "
                  "Device-wedged theory is DEAD.")
        else:
            print("VERDICT: BOTH FAIL -> kernel/launch-level fault, "
                  "device/driver side.")
    else:
        print("VERDICT: v1 passed everywhere in this run - fault is "
              "intermittent; compare against v1z for divergence.")


if __name__ == "__main__":
    main()
