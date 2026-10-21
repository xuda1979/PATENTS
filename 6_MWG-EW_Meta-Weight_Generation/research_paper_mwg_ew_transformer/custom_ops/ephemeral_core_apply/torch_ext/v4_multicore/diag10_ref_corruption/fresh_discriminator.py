#!/usr/bin/env python3
"""ASI2 fresh-allocation discriminator probe (2026-10-08).

Question: in the fresh-T128 failures (pair-probe fresh analog, diag9 S1),
is the op output wrong, or is the NPU-computed reference wrong?

Design:
  1. probe() tensors generated on CPU (seed 1234) -> snapshots kept on CPU.
  2. CPU reference computed BEFORE any NPU work (ground truth).
  3. Both libs loaded (v1 then v4).
  4. Sequence A (diag9 order): compute NPU ref, call v1, call v4.
     Compare each against CPU ground truth AND against NPU ref.
  5. Sequence B (pair-probe fresh-analog order): fresh tensors same seed,
     NPU ref2 computed after 10 prior op calls, call v1, call v4.
     Compare against CPU truth and NPU ref2.
  6. Sequence C: 10 warmup calls on first tensors, then ANOTHER fresh
     allocation, NPU ref3, call v1/v4. CPU truth again.
"""
import json

import torch

V1_SO = "/root/work/mwg_torch_ext/build/libcustom_ops.so"
V4_SO = "/root/work/mwg_v4_torch_ext/build/libcustom_ops_v4.so"
TOL = 0.01

r = {"tol": TOL}


def cpu_probe(T=128, H=128, R=128, seed=1234, amp=0.05):
    g = torch.Generator(device="cpu").manual_seed(seed)
    act = (torch.randn(T, R, generator=g) * 0.5).to(torch.float16)
    ctrl = (torch.randn(T, H, generator=g) * 0.5).to(torch.float32)
    weight = (torch.randn(H, R, generator=g) * 0.1).to(torch.float32)
    bias = (torch.randn(R, generator=g) * 0.05).to(torch.float32)
    return act, ctrl, weight, bias, amp


def cpu_ref(act, ctrl, weight, bias, amp):
    ctrl16 = ctrl.to(torch.float16).float()
    w16 = weight.to(torch.float16).float()
    core = torch.tanh(ctrl16 @ w16 + bias) * amp + 1.0
    return act.float() * core


def md(a, b):
    if a.is_npu:
        a = a.cpu()
    if b.is_npu:
        b = b.cpu()
    return float((a.float() - b.float()).abs().max().item())


def main():
    # --- CPU ground truth (no NPU touched yet) ---
    act_c, ctrl_c, w_c, b_c, amp = cpu_probe()
    truth = cpu_ref(act_c, ctrl_c, w_c, b_c, amp)

    torch.npu.set_device(0)
    pf = torch.randn(64, 64, device="npu", dtype=torch.float16)
    torch.npu.synchronize()
    assert torch.isfinite(pf @ pf).all().item(), "preflight failed"

    torch.ops.load_library(V1_SO)
    torch.ops.load_library(V4_SO)

    # --- Sequence A: diag9 S1 order ---
    act = act_c.clone().npu()
    ctrl = ctrl_c.clone().npu()
    weight = w_c.clone().npu()
    bias = b_c.clone().npu()

    npu_ref = cpu_ref(act, ctrl, weight, bias, amp)  # computed on NPU
    o1 = torch.ops.mwg.ephemeral_core_apply(act, ctrl, weight, bias, amp)
    o4 = torch.ops.mwg.ephemeral_core_apply_v4(act, ctrl, weight, bias, amp)
    torch.npu.synchronize()

    a = {}
    a["npu_ref_vs_cpu_truth"] = md(npu_ref, truth)
    a["v1_vs_cpu_truth"] = md(o1, truth)
    a["v4_vs_cpu_truth"] = md(o4, truth)
    a["v1_vs_npu_ref"] = md(o1, npu_ref)
    a["v4_vs_npu_ref"] = md(o4, npu_ref)
    a["v1_vs_v4"] = md(o1, o4)
    r["seqA_diag9_order"] = a

    # --- warmup: 10 op calls on seq-A tensors (mimic pair probe) ---
    for _ in range(10):
        torch.ops.mwg.ephemeral_core_apply(act, ctrl, weight, bias, amp)
        torch.ops.mwg.ephemeral_core_apply_v4(act, ctrl, weight, bias, amp)
    torch.npu.synchronize()

    # --- Sequence B: fresh tensors, same seed; NPU ref AFTER 10 calls ---
    act2 = act_c.clone().npu()
    ctrl2 = ctrl_c.clone().npu()
    weight2 = w_c.clone().npu()
    bias2 = b_c.clone().npu()

    npu_ref2 = cpu_ref(act2, ctrl2, weight2, bias2, amp)
    o1b = torch.ops.mwg.ephemeral_core_apply(act2, ctrl2, weight2, bias2, amp)
    o4b = torch.ops.mwg.ephemeral_core_apply_v4(act2, ctrl2, weight2, bias2, amp)
    torch.npu.synchronize()

    b = {}
    b["npu_ref2_vs_cpu_truth"] = md(npu_ref2, truth)
    b["v1_vs_cpu_truth"] = md(o1b, truth)
    b["v4_vs_cpu_truth"] = md(o4b, truth)
    b["v1_vs_npu_ref2"] = md(o1b, npu_ref2)
    b["v4_vs_npu_ref2"] = md(o4b, npu_ref2)
    b["v1_vs_v4"] = md(o1b, o4b)
    r["seqB_fresh_after_warm"] = b

    # --- Sequence C: compute CPU-truth ref FIRST on seq-B tensors ---
    # NPU ref3 = recompute ref on the SAME seq-B tensors after more calls
    for _ in range(5):
        torch.ops.mwg.ephemeral_core_apply(act2, ctrl2, weight2, bias2, amp)
        torch.ops.mwg.ephemeral_core_apply_v4(act2, ctrl2, weight2, bias2, amp)
    torch.npu.synchronize()
    npu_ref3 = cpu_ref(act2, ctrl2, weight2, bias2, amp)
    o1c = torch.ops.mwg.ephemeral_core_apply(act2, ctrl2, weight2, bias2, amp)
    o4c = torch.ops.mwg.ephemeral_core_apply_v4(act2, ctrl2, weight2, bias2, amp)
    torch.npu.synchronize()
    c = {}
    c["npu_ref3_vs_cpu_truth"] = md(npu_ref3, truth)
    c["v1_vs_cpu_truth"] = md(o1c, truth)
    c["v4_vs_cpu_truth"] = md(o4c, truth)
    c["v1_vs_npu_ref3"] = md(o1c, npu_ref3)
    c["v4_vs_npu_ref3"] = md(o4c, npu_ref3)
    c["v1_vs_v4"] = md(o1c, o4c)
    r["seqC_ref_first_then_ops"] = c

    out = "/tmp/asi2_fresh_disc.json"
    json.dump(r, open(out, "w"), indent=1)
    print(json.dumps(r, indent=1))
    print("WROTE", out)


if __name__ == "__main__":
    main()
