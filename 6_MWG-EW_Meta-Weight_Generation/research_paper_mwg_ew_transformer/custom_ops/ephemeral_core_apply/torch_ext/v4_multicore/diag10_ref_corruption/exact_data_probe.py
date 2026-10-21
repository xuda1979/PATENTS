#!/usr/bin/env python3
"""ASI2 exact-data T512 probe (2026-10-08).

The decisive test aborts at large_T512 with v1 err=nan (3x). The
NaN-attribution probe with seeds (0, 1234+rep) and generation order
(head_w, head_b, act, ctrl) did NOT reproduce. The test differs:
  - torch.manual_seed(1234) for EVERY config
  - generation order: ctrl, head_w, head_b, act
This probe replicates the test's exact data and sequence:
  Phase 1: probe_T128 exactly as the test (seed 1234, same order,
           same checks, same benchmark: warmup=30, iters=200, repeats=5).
  Phase 2: large_T512 exactly as the test (seed 1234, same order), then:
           - v1 output NaN check + err vs ref
           - ref NaN check + ref vs CPU truth
           - v4 output NaN check + err vs ref
           - which tensor has NaN, elementwise location stats
  Repeats phase 2 three times (fresh gen each time, same seed).
"""
import json

import torch
import torch_npu  # noqa: F401

V1_SO = "/root/work/mwg_torch_ext/build/libcustom_ops.so"
V4_SO = "/root/work/mwg_v4_torch_ext/build/libcustom_ops_v4.so"
OUT = "/tmp/asi2_exact_data_probe.json"


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
    return sorted(times)[len(times) // 2]


def nan_stats(t):
    f = t.float()
    n = int(torch.isnan(f).sum().item())
    i = int(torch.isinf(f).sum().item())
    if n:
        idx = torch.nonzero(torch.isnan(f))
        r0 = int(idx[:, 0].min().item())
        r1 = int(idx[:, 0].max().item())
        c0 = int(idx[:, 1].min().item())
        c1 = int(idx[:, 1].max().item())
        return {"nan": n, "inf": i, "rows": [r0, r1], "cols": [c0, c1]}
    return {"nan": n, "inf": i}


def main():
    r = {}
    device = torch.device("npu:0")
    torch.npu.set_device(0)

    x = torch.randn(128, 128, dtype=torch.float16, device=device)
    y = x @ x
    torch.npu.synchronize()
    assert torch.allclose(y, y.clone()), "preflight fail"
    print("preflight ok")

    torch.ops.load_library(V1_SO)
    torch.ops.load_library(V4_SO)

    # ---- Phase 1: probe_T128 exactly as the test ----
    T, H, R, amp = 128, 128, 128, 0.05
    torch.manual_seed(1234)
    ctrl = torch.randn(T, H, dtype=torch.float32, device=device)
    head_w = torch.randn(H, R, dtype=torch.float32, device=device)
    head_b = torch.randn(R, dtype=torch.float32, device=device)
    act = torch.randn(T, R, dtype=torch.float16, device=device)
    ref = algebraic_reference(act.float(), ctrl, head_w, head_b, amp).half()
    out_v1 = torch.ops.mwg.ephemeral_core_apply(act, ctrl, head_w, head_b, amp)
    err_v1 = (out_v1.float() - ref.float()).abs().max().item()
    out_v4 = torch.ops.mwg.ephemeral_core_apply_v4(act, ctrl, head_w, head_b, amp)
    err_v4 = (out_v4.float() - ref.float()).abs().max().item()
    r["phase1_T128"] = {"v1_err": err_v1, "v4_err": err_v4}
    print("phase1:", r["phase1_T128"])
    v1_ms = bench_op(lambda a, c, w, b, am: torch.ops.mwg.ephemeral_core_apply(a, c, w, b, am),
                     (act, ctrl, head_w, head_b, amp), 30, 200, 5)
    v4_ms = bench_op(lambda a, c, w, b, am: torch.ops.mwg.ephemeral_core_apply_v4(a, c, w, b, am),
                     (act, ctrl, head_w, head_b, amp), 30, 200, 5)
    r["phase1_T128"].update({"v1_ms": v1_ms, "v4_ms": v4_ms})
    print("phase1 bench:", v1_ms, v4_ms)

    # ---- Phase 2: large_T512 exactly as the test, 3 reps ----
    T = 512
    for rep in range(3):
        step = {}
        torch.manual_seed(1234)
        ctrl = torch.randn(T, H, dtype=torch.float32, device=device)
        head_w = torch.randn(H, R, dtype=torch.float32, device=device)
        head_b = torch.randn(R, dtype=torch.float32, device=device)
        act = torch.randn(T, R, dtype=torch.float16, device=device)
        step["inputs"] = {k: nan_stats(v) for k, v in
                          (("ctrl", ctrl), ("w", head_w), ("b", head_b), ("act", act))}
        ref = algebraic_reference(act.float(), ctrl, head_w, head_b, amp).half()
        torch.npu.synchronize()
        step["ref"] = nan_stats(ref)
        # CPU truth for the ref
        truth = algebraic_reference(act.float().cpu(), ctrl.cpu(), head_w.cpu(),
                                    head_b.cpu(), amp).half()
        step["ref_vs_cpu_truth"] = float((ref.float().cpu() - truth.float()).abs().max().item())
        # v1 exactly as the test: call, then err vs ref
        out_v1 = torch.ops.mwg.ephemeral_core_apply(act, ctrl, head_w, head_b, amp)
        err_v1 = (out_v1.float() - ref.float()).abs().max().item()
        step["v1"] = nan_stats(out_v1)
        step["v1_err_vs_ref"] = err_v1
        step["v1_err_vs_truth"] = float((out_v1.float().cpu() - truth.float()).abs().max().item())
        # v4
        out_v4 = torch.ops.mwg.ephemeral_core_apply_v4(act, ctrl, head_w, head_b, amp)
        err_v4 = (out_v4.float() - ref.float()).abs().max().item()
        step["v4"] = nan_stats(out_v4)
        step["v4_err_vs_ref"] = err_v4
        r[f"T512_rep{rep}"] = step
        print(f"T512 rep{rep}:", json.dumps(step))

    json.dump(r, open(OUT, "w"), indent=1)
    print("WROTE", OUT)


if __name__ == "__main__":
    main()
