#!/usr/bin/env python3
"""Diag 8: dirty-device-memory A/B - reproduce the v1 first-call NaN under
deliberate device-memory dirt, and test whether v1z (zeroed workspace)
survives it.

Why: diag7 A/B in a clean fresh process could NOT reproduce the harness
NaN (both arms passed).  diag6 showed first-call garbage (759) then NaN
then pass-by-call-3 - a settling state machine consistent with an
UNINITIALIZED aclrtMalloc workspace (KFC matmul handshake reads garbage
semaphores; partial kernel completion leaves at::empty_like output
memory unwritten -> NaN/garbage).

Hypothesis: whether the first call fails depends on the dirt level of the
device memory that the raw aclrtMalloc (outside the torch caching
allocator) happens to grab.  The harness runs after v4 .so load +
preflight + reference matmuls (aclnn workspaces) and possibly after
co-tenant processes on the device.

Dirt recipe (before ANY custom-op call):
  1. allocate ~512 MiB of NPU tensors filled with 1e30 and NaN patterns
  2. free them; torch.npu.empty_cache() releases blocks to the driver
  3. run preflight-like matmuls (aclnn workspace alloc/free churn)
  4. THEN the first custom-op call on probe tensors (T=128)

Arm via argv[1]: 'v1' or 'v1z' (fresh process per run; caller loops).
Prints one JSON line per run: first 3 call fingerprints + errs.
"""

import json
import sys

import torch
import torch_npu

V1_SO = "/root/work/mwg_torch_ext/build/libcustom_ops.so"
V1Z_SO = "/root/work/mwgz_torch_ext/build/libcustom_ops_z.so"

ARM = sys.argv[1] if len(sys.argv) > 1 else "v1"
if ARM == "v1":
    NS, OP, SO = "mwg", "ephemeral_core_apply", V1_SO
else:
    NS, OP, SO = "mwgz", "ephemeral_core_apply_z", V1Z_SO


def fingerprint(t):
    if t is None:
        return None
    f = t.float()
    nan_count = int(torch.isnan(f).sum().item())
    inf_count = int(torch.isinf(f).sum().item())
    finite = f[torch.isfinite(f)]
    if finite.numel() == 0:
        return {"nan": nan_count, "inf": inf_count, "max": None, "min": None,
                "mean": None}
    return {"nan": nan_count, "inf": inf_count,
            "max": float(finite.max().item()),
            "min": float(finite.min().item()),
            "mean": float(finite.mean().item())}


def ref_out(act, ctrl, weight, bias, amp):
    ctrl16 = ctrl.to(torch.float16).float()
    w16 = weight.to(torch.float16).float()
    b16 = bias if bias.dtype == torch.float32 else bias.float()
    core = torch.tanh(ctrl16 @ w16 + b16) * amp + 1.0
    return act.float() * core


def main():
    r = {"arm": ARM}
    torch.npu.set_device(0)
    r["device"] = torch.npu.get_device_name(0)

    # ---- dirt phase (BEFORE loading/calling the custom op) ----
    dirt_blocks = []
    oom = False
    try:
        for i in range(8):
            big = torch.empty(16 * 1024 * 1024, device="npu",
                              dtype=torch.float32)  # 64 MiB each
            big.fill_(1e30 if i % 2 == 0 else float("nan"))
            dirt_blocks.append(big)
    except Exception as e:  # noqa: BLE001
        oom = True
        r["dirt_oom"] = f"{type(e).__name__}"
    r["dirt_mib"] = len(dirt_blocks) * 64
    del dirt_blocks
    torch.npu.empty_cache()
    # preflight-like matmul churn (aclnn workspace alloc/free)
    a = torch.randn(64, 64, device="npu", dtype=torch.float16)
    for _ in range(3):
        c = a @ a
        torch.npu.synchronize()
        del c
    torch.npu.empty_cache()
    r["dirt_done"] = True

    # ---- load + probe ----
    torch.ops.load_library(SO)
    r["loaded"] = True

    g = torch.Generator(device="cpu").manual_seed(1234)
    act = (torch.randn(128, 128, generator=g) * 0.5).to(torch.float16).npu()
    ctrl = (torch.randn(128, 128, generator=g) * 0.5).to(torch.float32).npu()
    weight = (torch.randn(128, 128, generator=g) * 0.1).to(torch.float32).npu()
    bias = (torch.randn(128, generator=g) * 0.05).to(torch.float32).npu()
    amp = 0.05
    ref = ref_out(act, ctrl, weight, bias, amp)

    for call in (1, 2, 3):
        try:
            out = torch.ops.__getattr__(NS).__getattr__(OP)(
                act, ctrl, weight, bias, amp)
            torch.npu.synchronize()
            fp = fingerprint(out)
            err = float((out.float() - ref).abs().max().item())
        except Exception as e:  # noqa: BLE001
            fp = f"EXC: {type(e).__name__}: {e}"
            err = None
        r[f"call{call}"] = fp
        r[f"call{call}_err"] = err

    print("DIAG8_RESULT " + json.dumps(r))


if __name__ == "__main__":
    main()
