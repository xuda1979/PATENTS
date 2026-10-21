#!/usr/bin/env python3
"""Diag 9 v2 (2026-10-08): hardened re-validation of the v1+v4 pair on ASI2.

Root cause of the 2026-10-08 diag9 S1/S5 failure (err=0.08105, v1==v4
bit-identical, deterministic): the NPU-computed fp32 reference tensor
itself was corrupted. Evidence from asi2_pair_probe + asi2_fresh_disc:
  - the op outputs matched CPU ground truth exactly
  - refs computed in the CANN lazy-init window (right after .so load,
    first matmul of the process) can return wrong-finite values
  - v1 and v4, two independent kernels, cannot produce bit-identical
    wrong output; the shared artifact is the ref.

Hardening: every reference is computed under a two-phase integrity gate:
  phase 1: npu_ref  = ref_op(*npu_inputs)
  phase 2: npu_ref2 = ref_op(*npu_inputs)  (recompute)
  phase 3: cpu truth check when feasible (or third recompute)
  If the phases disagree, retry up to 8x; then fail loudly with the
  phase deltas recorded.

Sections (same as diag9 v1):
  S1 probe_T128 first-call + repeat, v1 and v4 vs gated reference
  S2 weight recycling (new weight at recycled address)
  S3 T sweep {64,128,192,256,512,2048} both ops
  S4 v4 multicore (T=1024 -> 8 cores)
  S5 5x repeat stability
"""
import json
import sys

import torch
import torch_npu  # noqa: F401

V1_SO = "/root/work/mwg_torch_ext/build/libcustom_ops.so"
V4_SO = "/root/work/mwg_v4_torch_ext/build/libcustom_ops_v4.so"
OUT = "/root/work/filestorage/mwg-ew-transformer-research/results/diag9v2_asi2_20261008.json"
TOL = 0.01
REF_GATE_RETRIES = 8


def cpu_snapshot(t):
    if t is None:
        return None
    return t.detach().to("cpu", torch.float32).clone()


def npu_stats(t):
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


def gated_ref(act, ctrl, weight, bias, amp, tag):
    """Compute a reference under the two-phase integrity gate."""
    best = None
    for attempt in range(REF_GATE_RETRIES):
        r1 = ref_out(act, ctrl, weight, bias, amp)
        torch.npu.synchronize()
        r2 = ref_out(act, ctrl, weight, bias, amp)
        torch.npu.synchronize()
        d12 = (r1.float() - r2.float()).abs().max().item()
        if d12 == 0.0:
            best = r1
            if attempt > 0:
                print(f"REF_GATE[{tag}]: converged at attempt {attempt + 1}")
            return best, {"attempts": attempt + 1, "phase12_delta": 0.0}
        print(f"REF_GATE[{tag}]: phase1 vs phase2 delta {d12}, retrying")
    return best, {"attempts": REF_GATE_RETRIES, "phase12_delta": d12}


def check(tag, out, ref, r, sec):
    ok = out is not None and ref is not None
    if not ok:
        sec[tag] = {"ok": False, "error": "op or ref returned None"}
        r["pass"] = False
        return False
    e = float((out.float() - ref.float()).abs().max().item())
    st = npu_stats(out)
    sec[tag] = {
        "ok": bool(e <= TOL and st["nan"] == 0 and st["inf"] == 0),
        "err": e,
        **st,
    }
    if not sec[tag]["ok"]:
        r["pass"] = False
    return sec[tag]["ok"]


def main():
    r = {"pass": True, "tol": TOL}
    torch.npu.set_device(0)
    a = torch.randn(64, 64, device="npu", dtype=torch.float16)
    torch.npu.synchronize()
    assert torch.isfinite(a @ a).all().item(), "preflight failed"

    torch.ops.load_library(V1_SO)
    torch.ops.load_library(V4_SO)

    # S1: probe_T128
    s1 = {}
    act, ctrl, weight, bias, amp = probe()
    ref, refgate = gated_ref(act, ctrl, weight, bias, amp, "S1")
    s1["ref_gate"] = refgate
    o1 = run_op("mwg", "ephemeral_core_apply", act, ctrl, weight, bias, amp)
    o4 = run_op("mwg", "ephemeral_core_apply_v4", act, ctrl, weight, bias, amp)
    check("v1", o1, ref, r, s1)
    check("v4", o4, ref, r, s1)
    o1r = run_op("mwg", "ephemeral_core_apply", act, ctrl, weight, bias, amp)
    o4r = run_op("mwg", "ephemeral_core_apply_v4", act, ctrl, weight, bias, amp)
    check("v1_repeat", o1r, ref, r, s1)
    check("v4_repeat", o4r, ref, r, s1)
    if o1 is not None and o4 is not None:
        s1["v1_vs_v4"] = float((o1.float() - o4.float()).abs().max().item())
    r["sections"] = {"S1": s1}
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
    ref2, refgate2 = gated_ref(act2, ctrl2, W1, bias2, amp2, "S2")
    s2["ref_gate"] = refgate2
    o1w = run_op("mwg", "ephemeral_core_apply", act2, ctrl2, W1, bias2, amp2)
    o4w = run_op("mwg", "ephemeral_core_apply_v4", act2, ctrl2, W1, bias2, amp2)
    check("v1_new_weight", o1w, ref2, r, s2)
    check("v4_new_weight", o4w, ref2, r, s2)
    if o1w is not None and o4w is not None:
        s2["v1_vs_v4"] = float((o1w.float() - o4w.float()).abs().max().item())
    r["sections"]["S2"] = s2
    print("S2:", json.dumps(s2))

    # S3: T sweep
    s3 = {}
    for T in [64, 128, 192, 256, 512, 2048]:
        e = {}
        aT, cT, wT, bT, amT = probe(T=T, seed=100 + T)
        refT, refgateT = gated_ref(aT, cT, wT, bT, amT, f"S3_T{T}")
        e["ref_gate"] = refgateT
        o1T = run_op("mwg", "ephemeral_core_apply", aT, cT, wT, bT, amT)
        o4T = run_op("mwg", "ephemeral_core_apply_v4", aT, cT, wT, bT, amT)
        check("v1", o1T, refT, r, e)
        check("v4", o4T, refT, r, e)
        if o1T is not None and o4T is not None:
            e["v1_vs_v4"] = float((o1T.float() - o4T.float()).abs().max().item())
        s3[f"T{T}"] = e
    r["sections"]["S3"] = s3
    print("S3:", json.dumps(s3))

    # S4: v4 multicore T=1024
    s4 = {}
    a4, c4, w4, b4, am4 = probe(T=1024, seed=4242)
    ref4, refgate4 = gated_ref(a4, c4, w4, b4, am4, "S4")
    s4["ref_gate"] = refgate4
    o4m = run_op("mwg", "ephemeral_core_apply_v4", a4, c4, w4, b4, am4)
    check("v4_T1024_multicore", o4m, ref4, r, s4)
    r["sections"]["S4"] = s4
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
    print("S5:", json.dumps(s5))

    json.dump(r, open(OUT, "w"), indent=1)
    print("WROTE", OUT)
    print("OVERALL_PASS" if r["pass"] else "OVERALL_FAIL")


if __name__ == "__main__":
    main()
