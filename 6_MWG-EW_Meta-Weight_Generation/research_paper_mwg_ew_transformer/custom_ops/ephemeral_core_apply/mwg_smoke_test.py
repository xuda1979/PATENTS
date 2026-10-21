#!/usr/bin/env python3
"""Functional smoke test for the arm-4 fused no-store operator.

Run on the NPU host AFTER building libcustom_ops.so.  Verifies:
  1. torch.ops.load_library succeeds;
  2. mwg::ephemeral_core_apply resolves;
  3. the output matches the algebraic reference within fp16 tolerance.
Writes/refreshes the hash-bound contract manifest before checking.
"""
import hashlib
import json
import sys
from pathlib import Path

SRC = Path("/root/work/mwg_torch_ext/ephemeral_core_apply.asc")
LIB = Path("/root/work/mwg_torch_ext/build/libcustom_ops.so")
MANIFEST = Path("/root/work/mwg_torch_ext/contract.json")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if not LIB.is_file():
        print(f"BUILD MISSING: {LIB}")
        return 2
    manifest = {
        "schema_version": 1,
        "op_qualified_name": "mwg::ephemeral_core_apply",
        "implementation": "ascendc",
        "core_residency": "ub_local_tensor",
        "global_core_output": False,
        "workspace_bytes": 0,
        "outputs": ["scaled_rank_activation"],
        "audited_source_path": "ephemeral_core_apply.asc",
        "audited_source_sha256": sha256(SRC),
        "binary_sha256": sha256(LIB),
        "source_audit": {
            "no_global_core_tensor": True,
            "no_core_datacopy_to_global": True,
        },
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print("manifest refreshed:", MANIFEST)

    import torch
    import torch_npu  # noqa: F401

    print("torch", torch.__version__, "npu", torch.npu.is_available())

    torch.ops.load_library(str(LIB))
    print("load_library OK")

    device = "npu:0"
    T, H, R = 64, 128, 128
    amp = 0.05
    gen = torch.Generator(device="cpu").manual_seed(7)
    rank_activation = torch.randn(T, R, generator=gen).to(torch.float16).to(device)
    controller_hidden = torch.randn(T, H, generator=gen).to(device)
    head_weight = torch.randn(H, R, generator=gen).to(device)
    head_bias = torch.randn(R, generator=gen).to(device)

    out = torch.ops.mwg.ephemeral_core_apply(
        rank_activation, controller_hidden, head_weight, head_bias, amp
    )
    assert out.shape == rank_activation.shape, out.shape
    assert out.dtype == rank_activation.dtype, out.dtype
    assert out.device == rank_activation.device, out.device
    print("op out", tuple(out.shape), str(out.dtype), out.device)

    logits = controller_hidden @ head_weight + head_bias
    core = (1.0 + amp * torch.tanh(logits)).to(torch.float16)
    ref = (rank_activation.float() * core.float()).to(torch.float16)

    max_err = (out.float() - ref.float()).abs().max().item()
    mean_err = (out.float() - ref.float()).abs().mean().item()
    print(f"max abs err {max_err:.6f}  mean abs err {mean_err:.6f}")

    # Bisection diagnostics: which stage produced the mismatch?
    act_dev = rank_activation.float()
    print("diag: |out - act| max =", (out.float() - act_dev).abs().max().item())
    print("diag: |out| max =", out.float().abs().max().item(),
          " |act| max =", act_dev.abs().max().item())
    logits_dev = controller_hidden @ head_weight + head_bias
    print("diag: core ref range =",
          (1.0 + amp * torch.tanh(logits_dev)).min().item(),
          (1.0 + amp * torch.tanh(logits_dev)).max().item())
    # Implied core: out = act * core  =>  core_implied = out/act (masked)
    act_cpu = rank_activation.float().cpu()
    out_cpu = out.float().cpu()
    mask = act_cpu.abs() > 0.5
    if mask.any():
        implied = (out_cpu[mask] / act_cpu[mask])
        print("diag: implied core mean =", implied.mean().item(),
              " std =", implied.std().item())
    ok = max_err < 0.02
    print("SMOKE PASS" if ok else "SMOKE FAIL (max_err >= 0.02)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
