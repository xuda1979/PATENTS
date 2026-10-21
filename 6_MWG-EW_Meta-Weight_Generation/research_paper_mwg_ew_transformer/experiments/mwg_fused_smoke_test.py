#!/usr/bin/env python3
"""Smoke test for the fused EphemeralCoreApply op via the torchair registration
module.  Runs on an NPU host; compares the compiled custom-op output against
the materialized algebraic reference."""
import sys

import torch
import torch_npu  # noqa: F401

sys.path.insert(0, "/root/work/filestorage/mwg-ew-transformer-research")

from custom_ops.ephemeral_core_apply import fused_registration_module as reg  # noqa: E402

OP_PACKAGE = "/root/work/mwg_op_build/mwg_op_package.tgz"
MANIFEST = "/root/work/mwg_op_build/ephemeral_core_apply.contract.json"


def main() -> int:
    torch.manual_seed(0)
    dev = torch.device("npu:0")
    T, R, H = 128, 128, 128
    ra = torch.randn(T, R, device=dev, dtype=torch.float16)
    ch = torch.randn(T, H, device=dev, dtype=torch.float32)
    hw = torch.randn(H, R, device=dev, dtype=torch.float32)
    hb = torch.randn(R, device=dev, dtype=torch.float32)
    amp = 0.05

    op_fn, info = reg.load_fused_backend(OP_PACKAGE, MANIFEST)
    print("INFO", info, flush=True)
    ref = reg._materialized_reference(ra, ch, hw, hb, amp)
    out = op_fn(ra, ch, hw, hb, amp)
    torch.npu.synchronize()
    diff = (out.float() - ref.float()).abs()
    rel = diff / ref.float().abs().clamp_min(1e-3)
    print("out_shape", tuple(out.shape), "out_dtype", out.dtype, flush=True)
    print("max_abs_diff", diff.max().item(), flush=True)
    print("mean_abs_diff", diff.mean().item(), flush=True)
    print("max_rel", rel.max().item(), flush=True)
    ok = diff.max().item() < 5e-2
    print("SMOKE_PASS" if ok else "SMOKE_FAIL", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
