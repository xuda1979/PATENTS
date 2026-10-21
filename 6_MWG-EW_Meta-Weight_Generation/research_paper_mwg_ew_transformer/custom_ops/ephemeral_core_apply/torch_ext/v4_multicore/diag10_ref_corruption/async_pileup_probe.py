#!/usr/bin/env python3
"""ASI2 async-pileup T512 probe (2026-10-08).

Both the NaN-attribution and exact-data probes (synchronized per-call)
PASS at T512. The decisive test differs in benchmark_op: 200 UNSYNCED
async op launches queued back-to-back (host perf_counter timing), then
one sync. 5 reps x (30 warmup + 200 iters) = 1150 queued calls per op
per config. The abort comes at the FIRST T512 err check right after the
probe_T128 benchmark's async pileup, on a fresh seed-1234 T512 tensor.

Hypothesis: the async-launch pileup (hundreds of pending launches, each
allocating an output tensor + workspace reuse) trips the v1 wrapper or
CANN runtime into a bad window, corrupting the NEXT fresh allocation's
computation. This probe replicates the EXACT benchmark_op sequence and
checks the post-pileup T512 call.
"""
import json
import time

import torch
import torch_npu  # noqa: F401

V1_SO = "/root/work/mwg_torch_ext/build/libcustom_ops.so"
V4_SO = "/root/work/mwg_v4_torch_ext/build/libcustom_ops_v4.so"
OUT = "/tmp/asi2_async_pileup_probe.json"


def algebraic_reference(rank_activation, controller_hidden, head_weight,
                        head_bias, amplitude):
    logits = controller_hidden @ head_weight + head_bias
    core = 1.0 + amplitude * torch.tanh(logits)
    return rank_activation * core


def benchmark_op(op_fn, args, warmup=30, iters=200, repeats=5):
    """EXACT copy of test_v4_multicore.benchmark_op (host timing)."""
    for _ in range(warmup):
        out = op_fn(*args)
    torch.npu.synchronize()

    results = []
    for rep in range(repeats):
        torch.npu.synchronize()
        t0 = time.perf_counter()
        for _ in range(iters):
            out = op_fn(*args)
        torch.npu.synchronize()
        t1 = time.perf_counter()
        ms = (t1 - t0) / iters * 1000
        results.append(ms)

    results.sort()
    median = results[len(results) // 2]
    std = (sum((x - median) ** 2 for x in results) / len(results)) ** 0.5
    return {"median_ms": median, "std_ms": std, "all_ms": results}


def nan_stats(t):
    f = t.float()
    n = int(torch.isnan(f).sum().item())
    i = int(torch.isinf(f).sum().item())
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

    H, R, amp = 128, 128, 0.05

    # ---- probe_T128: exact test sequence ----
    T = 128
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
    print(f"T128 v1_err={err_v1} v4_err={err_v4}")
    r["T128_pre_pileup"] = {"v1_err": err_v1, "v4_err": err_v4}

    # exact benchmark_op: v1 then v4
    v1_bench = benchmark_op(
        lambda a, c, w, b, am: torch.ops.mwg.ephemeral_core_apply(a, c, w, b, am),
        (act, ctrl, head_w, head_b, amp))
    v4_bench = benchmark_op(
        lambda a, c, w, b, am: torch.ops.mwg.ephemeral_core_apply_v4(a, c, w, b, am),
        (act, ctrl, head_w, head_b, amp))
    r["T128_bench"] = {"v1": v1_bench["median_ms"], "v4": v4_bench["median_ms"]}
    print("T128 bench:", r["T128_bench"])

    # ---- large_T512: exact test sequence, immediately after pileup ----
    T = 512
    torch.manual_seed(1234)
    ctrl = torch.randn(T, H, dtype=torch.float32, device=device)
    head_w = torch.randn(H, R, dtype=torch.float32, device=device)
    head_b = torch.randn(R, dtype=torch.float32, device=device)
    act = torch.randn(T, R, dtype=torch.float16, device=device)
    r["T512_inputs"] = {k: nan_stats(v) for k, v in
                        (("ctrl", ctrl), ("w", head_w), ("b", head_b), ("act", act))}

    ref = algebraic_reference(act.float(), ctrl, head_w, head_b, amp).half()
    torch.npu.synchronize()
    r["T512_ref"] = nan_stats(ref)

    out_v1 = torch.ops.mwg.ephemeral_core_apply(act, ctrl, head_w, head_b, amp)
    err_v1 = (out_v1.float() - ref.float()).abs().max().item()
    r["T512_v1"] = {"err_vs_ref": err_v1, **nan_stats(out_v1)}
    print("T512 v1:", r["T512_v1"])

    out_v4 = torch.ops.mwg.ephemeral_core_apply_v4(act, ctrl, head_w, head_b, amp)
    err_v4 = (out_v4.float() - ref.float()).abs().max().item()
    r["T512_v4"] = {"err_vs_ref": err_v4, **nan_stats(out_v4)}
    print("T512 v4:", r["T512_v4"])

    json.dump(r, open(OUT, "w"), indent=1)
    print("WROTE", OUT)


if __name__ == "__main__":
    main()
