#!/usr/bin/env python3
"""Root-cause the ASI3 v1/v4 failures: stale weight-cache vs partial write.

Four modes, ONE process each (run separately to avoid cross-contamination):

  v1-held     v1, inference-contract inputs (all weights allocated up front
              and held alive for the whole process => cache keys stay valid),
              9 geometries x 3 calls, fingerprint + ptr logging.
  v1-fresh    v1, harness pattern (fresh randn weights per case => freed
              addresses get reused => stale g_w16 hits), 10 calls at T=128,
              ptr + collision logging + fingerprint every call.
  v1-magic    v1, harness pattern at T=128 but a fp16 buffer filled with
              12345.0 (same byte size as the output) is allocated+freed
              right before each op call, so at::empty_like likely grabs it.
              Any element == 12345.0 in the output proves the kernel left
              output elements UNWRITTEN (partial-write bug), vs stale-cache
              (wrong finite values != magic).
  v4-held / v4-fresh / v4-magic   same three, v4 op.

Usage: python3 diag2_root_cause.py <mode> [out_json]
"""
import json
import math
import sys

import torch

V1_SO = "/root/work/mwg_torch_ext/build/libcustom_ops.so"
V4_SO = "/root/work/mwg_v4_torch_ext/build/libcustom_ops_v4.so"

H, R = 128, 128
MAGIC = 12345.0
TS_HELD = (64, 96, 128, 160, 192, 256, 384, 512, 2048)


def reference(act, ctrl, head_w, head_b, amp):
    logits = ctrl @ head_w + head_b
    core = 1.0 + amp * torch.tanh(logits)
    return act * core


def make_inputs(T, seed=1234, device="npu:0"):
    torch.manual_seed(seed)
    ctrl = torch.randn(T, H, dtype=torch.float32, device=device)
    head_w = torch.randn(H, R, dtype=torch.float32, device=device)
    head_b = torch.randn(R, dtype=torch.float32, device=device)
    act = torch.randn(T, R, dtype=torch.float16, device=device)
    return {"act": act, "ctrl": ctrl, "head_w": head_w, "head_b": head_b}


def fingerprint(tag, out, ref, results):
    o = out.float()
    rf = ref.float()
    nan_mask = torch.isnan(o)
    n_nan = int(nan_mask.sum().item())
    err = (o - rf).abs()
    err = torch.where(torch.isnan(err), torch.full_like(err, float("inf")),
                      err)
    max_err = float(err.max().item())
    n_magic = int((o == MAGIC).sum().item())
    bad = int(((err >= 5e-3) | nan_mask).sum().item())
    status = "PASS" if (bad == 0 and max_err < 5e-3) else "FAIL"
    line = (f"{tag}: max_err={max_err:.6f} nan={n_nan} magic={n_magic} "
            f"bad={bad}/{o.numel()} {status}")
    if n_nan or n_magic or status == "FAIL":
        bad_mask = (err >= 5e-3) | nan_mask
        rows = torch.nonzero(bad_mask.any(dim=1)).flatten().tolist()
        cols = torch.nonzero(bad_mask.any(dim=0)).flatten().tolist()
        line += (f" | rows {len(rows)}/{o.shape[0]} first={rows[:10]}"
                 f" cols {len(cols)} range="
                 f"{min(cols) if cols else '-'}..{max(cols) if cols else '-'}")
        if n_magic:
            mrows = torch.nonzero((o == MAGIC).any(dim=1)).flatten().tolist()
            line += f" | MAGIC rows {len(mrows)} first={mrows[:10]}"
        if rows:
            gap = (rows[-1] - rows[0] + 1) if rows else 0
            line += f" | row-span {rows[0]}..{rows[-1]} (span {gap})"
    print(line)
    results.append({"tag": tag, "max_err": max_err, "nan": n_nan,
                    "magic": n_magic, "bad": bad,
                    "pass": bool(status == "PASS")})


def call_op(op, inp, amp):
    return op(inp["act"], inp["ctrl"], inp["head_w"], inp["head_b"], amp)


def held_mode(op_name, op, results):
    print(f"--- {op_name}: HELD-weights (inference contract) ---")
    inputs = {T: make_inputs(T, seed=1000 + T) for T in TS_HELD}
    ptrs = {T: inputs[T]["head_w"].data_ptr() for T in TS_HELD}
    print("held weight ptrs:", {t: hex(p) for t, p in ptrs.items()})
    for T in TS_HELD:
        inp = inputs[T]
        ref = reference(inp["act"].float(), inp["ctrl"], inp["head_w"],
                        inp["head_b"], 0.05).half()
        for k in range(3):
            out = call_op(op, inp, 0.05)
            torch.npu.synchronize()
            fingerprint(f"{op_name} held T{T} call{k+1}", out, ref, results)


def fresh_mode(op_name, op, results, n_calls=10, T=128):
    print(f"--- {op_name}: FRESH-weights (harness pattern) T={T} ---")
    seen_ptrs = {}
    for k in range(n_calls):
        inp = make_inputs(T, seed=5000 + k)
        ptr = inp["head_w"].data_ptr()
        coll = seen_ptrs.get(ptr)
        seen_ptrs[ptr] = k
        ref = reference(inp["act"].float(), inp["ctrl"], inp["head_w"],
                        inp["head_b"], 0.05).half()
        out = call_op(op, inp, 0.05)
        torch.npu.synchronize()
        tag = f"{op_name} fresh T{T} call{k+1} ptr={hex(ptr)}"
        if coll is not None:
            tag += f" COLLIDE(call{coll + 1})"
        fingerprint(tag, out, ref, results)


def magic_mode(op_name, op, results, n_calls=6, T=128):
    print(f"--- {op_name}: MAGIC-prefill partial-write test T={T} ---")
    for k in range(n_calls):
        inp = make_inputs(T, seed=7000 + k)
        ref = reference(inp["act"].float(), inp["ctrl"], inp["head_w"],
                        inp["head_b"], 0.05).half()
        # Pre-fill a block the exact byte size of the output with MAGIC,
        # then free it so empty_like likely reuses it for `out`.
        magic = torch.full((T, R), MAGIC, dtype=torch.float16,
                           device="npu:0")
        del magic
        out = call_op(op, inp, 0.05)
        torch.npu.synchronize()
        fingerprint(f"{op_name} magic T{T} call{k+1}", out, ref, results)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "v1-held"
    out_json = sys.argv[2] if len(sys.argv) > 2 else None
    torch.npu.set_device(0)

    a = torch.randn(128, 128, device="npu:0")
    b = a @ a
    torch.npu.synchronize()
    print(f"sanity matmul: finite={bool(torch.isfinite(b).all().item())}")

    results = []
    if mode.startswith("v1"):
        torch.ops.load_library(V1_SO)
        op = torch.ops.mwg.ephemeral_core_apply
        print(f"loaded v1: {V1_SO}")
    elif mode.startswith("v4"):
        torch.ops.load_library(V4_SO)
        op = torch.ops.mwg.ephemeral_core_apply_v4
        print(f"loaded v4: {V4_SO}")
    else:
        print(f"unknown mode {mode}")
        sys.exit(2)

    kind = mode.split("-", 1)[1]
    if kind == "held":
        held_mode(mode, op, results)
    elif kind == "fresh":
        fresh_mode(mode, op, results)
    elif kind == "magic":
        magic_mode(mode, op, results)
    else:
        print(f"unknown kind {kind}")
        sys.exit(2)

    n_pass = sum(1 for r in results if r["pass"])
    print(f"\n=== {mode}: {n_pass}/{len(results)} PASS ===")
    if out_json:
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"results written to {out_json}")


if __name__ == "__main__":
    main()
