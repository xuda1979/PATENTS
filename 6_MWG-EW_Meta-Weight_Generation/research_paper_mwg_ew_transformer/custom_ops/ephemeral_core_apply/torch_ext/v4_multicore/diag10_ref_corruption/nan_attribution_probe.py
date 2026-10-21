#!/usr/bin/env python3
"""ASI2 NaN-attribution probe (2026-10-08).

The decisive test aborted 3x at large_T512 with v1 err=nan
(ASI3 2026-09-29, ASI2 05:25 and 07:45 today), always at the FIRST T512
call after ~1030 T=128 benchmark iterations of both ops. The test cannot
distinguish which tensor NaN'd: v1 output, the test ref, or an
intermediate. This probe replicates the sequence and attributes the NaN.

Design:
  Phase 1: probe_T128 full benchmark, exactly like test_v4_multicore
           (warmup=30, iters=200, repeats=5, v1 then v4, err checks).
  Phase 2: T512 step. For EACH tensor involved, snapshot + NaN-check
           independently and in order:
             a. inputs (act, ctrl, head_w, head_b) generated on device
             b. ref = algebraic_reference(...) computed on NPU
             c. ref recomputed -> stability check
             d. CPU truth for ref
             e. v1 output -> NaN check
             f. v4 output -> NaN check
           Record which step first shows NaN/wrong-finite.
  Also run the T512 step 5 times (repeat) to see persistence.
"""
import json
import math
import sys

import torch
import torch_npu  # noqa: F401

V1_SO = "/root/work/mwg_torch_ext/build/libcustom_ops.so"
V4_SO = "/root/work/mwg_v4_torch_ext/build/libcustom_ops_v4.so"
OUT = "/tmp/asi2_nan_attribution.json"
TOL = 0.01


def algebraic_reference(rank_activation, controller_hidden, head_weight,
                        head_bias, amplitude):
    logits = controller_hidden @ head_weight + head_bias
    core = 1.0 + amplitude * torch.tanh(logits)
    return rank_activation * core


def bench_op(fn, args, warmup, iters, repeats):
    times = []
    for _ in range(repeats):
        torch.npu.synchronize()
        for _ in range(warmup):
            fn(*args)
        torch.npu.synchronize()
        s = torch.npu.Event(enable_timing=True)
        e = torch.npu.Event(enable_timing=True)
        s.record()
        for _ in range(iters):
            fn(*args)
        e.record()
        torch.npu.synchronize()
        times.append(s.elapsed_time(e) / iters)
    return times


def nan_inf(t):
    f = t.float()
    return int(torch.isnan(f).sum().item()), int(torch.isinf(f).sum().item())


def main():
    r = {"tol": TOL}
    device = torch.device("npu:0")
    torch.npu.set_device(0)

    # preflight (same as test)
    x = torch.randn(128, 128, dtype=torch.float16, device=device)
    y = x @ x
    torch.npu.synchronize()
    y_ref = y.clone()
    assert torch.allclose(y, y_ref), "preflight matmul non-deterministic"
    print("preflight ok")

    torch.ops.load_library(V1_SO)
    torch.ops.load_library(V4_SO)

    # ---- Phase 1: probe_T128 benchmark, exactly like the test ----
    T, H, R, amp = 128, 128, 128, 0.05
    torch.manual_seed(0)
    head_w = torch.randn(H, R, dtype=torch.float32, device=device)
    head_b = torch.randn(R, dtype=torch.float32, device=device)
    act = torch.randn(T, R, dtype=torch.float16, device=device)
    ctrl = torch.randn(T, H, dtype=torch.float32, device=device)
    ref = algebraic_reference(act.float(), ctrl, head_w, head_b, amp).half()
    out_v1 = torch.ops.mwg.ephemeral_core_apply(act, ctrl, head_w, head_b, amp)
    err_v1 = (out_v1.float() - ref.float()).abs().max().item()
    out_v4 = torch.ops.mwg.ephemeral_core_apply_v4(act, ctrl, head_w, head_b, amp)
    err_v4 = (out_v4.float() - ref.float()).abs().max().item()
    r["phase1_T128"] = {"v1_err": err_v1, "v4_err": err_v4,
                        "v1_vs_v4": float((out_v1.float() - out_v4.float()).abs().max().item())}
    print("phase1 T128:", r["phase1_T128"])

    t_v1 = bench_op(lambda a, c, w, b, am: torch.ops.mwg.ephemeral_core_apply(a, c, w, b, am),
                    (act, ctrl, head_w, head_b, amp), 30, 200, 5)
    t_v4 = bench_op(lambda a, c, w, b, am: torch.ops.mwg.ephemeral_core_apply_v4(a, c, w, b, am),
                    (act, ctrl, head_w, head_b, amp), 30, 200, 5)
    r["phase1_T128"]["v1_ms"] = sorted(t_v1)[len(t_v1)//2]
    r["phase1_T128"]["v4_ms"] = sorted(t_v4)[len(t_v4)//2]
    print("phase1 bench: v1", r["phase1_T128"]["v1_ms"], "v4", r["phase1_T128"]["v4_ms"])

    # ---- Phase 2: T512 step, attributed ----
    for rep in range(5):
        T = 512
        step = {}
        torch.manual_seed(1234 + rep)
        head_w = torch.randn(H, R, dtype=torch.float32, device=device)
        head_b = torch.randn(R, dtype=torch.float32, device=device)
        act = torch.randn(T, R, dtype=torch.float16, device=device)
        ctrl = torch.randn(T, H, dtype=torch.float32, device=device)
        step["inputs_nan"] = dict(zip(("act", "ctrl", "w", "b"),
                                      [nan_inf(t) for t in (act, ctrl, head_w, head_b)]))
        if any(any(v) for v in step["inputs_nan"].values()):
            step["first_nan"] = "INPUTS"
            r[f"T512_rep{rep}"] = step
            break
        # ref on NPU
        ref = algebraic_reference(act.float(), ctrl, head_w, head_b, amp).half()
        torch.npu.synchronize()
        step["ref_nan"] = nan_inf(ref)
        # ref stability: recompute
        ref2 = algebraic_reference(act.float(), ctrl, head_w, head_b, amp).half()
        torch.npu.synchronize()
        step["ref_recompute_delta"] = float((ref.float() - ref2.float()).abs().max().item())
        # CPU truth (inputs copied to CPU first)
        act_c, ctrl_c, w_c, b_c = (t.cpu() for t in (act, ctrl, head_w, head_b))
        truth = algebraic_reference(act_c.float(), ctrl_c, w_c, b_c, amp).half()
        step["ref_vs_cpu_truth"] = float((ref.float().cpu() - truth.float()).abs().max().item())
        # v1
        out_v1 = torch.ops.mwg.ephemeral_core_apply(act, ctrl, head_w, head_b, amp)
        torch.npu.synchronize()
        step["v1_nan"] = nan_inf(out_v1)
        step["v1_err_vs_ref"] = float((out_v1.float() - ref.float()).abs().max().item())
        step["v1_err_vs_truth"] = float((out_v1.float().cpu() - truth.float()).abs().max().item())
        # v4
        out_v4 = torch.ops.mwg.ephemeral_core_apply_v4(act, ctrl, head_w, head_b, amp)
        torch.npu.synchronize()
        step["v4_nan"] = nan_inf(out_v4)
        step["v4_err_vs_ref"] = float((out_v4.float() - ref.float()).abs().max().item())
        step["v4_err_vs_truth"] = float((out_v4.float().cpu() - truth.float()).abs().max().item())
        # attribution
        first = []
        if step["ref_nan"] != (0, 0):
            first.append("REF")
        if step["ref_vs_cpu_truth"] > TOL:
            first.append("REF_WRONG_VS_TRUTH")
        if step["v1_nan"] != (0, 0):
            first.append("V1_OUTPUT")
        if step["v4_nan"] != (0, 0):
            first.append("V4_OUTPUT")
        step["first_nan"] = first if first else "NONE"
        r[f"T512_rep{rep}"] = step
        print(f"T512 rep{rep}:", json.dumps(step))

    json.dump(r, open(OUT, "w"), indent=1)
    print("WROTE", OUT)


if __name__ == "__main__":
    main()
