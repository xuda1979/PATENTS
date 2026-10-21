#!/usr/bin/env python3
"""Build script for the v4 multi-core ephemeral_core_apply kernel.

This script assembles the kernel source and prepares it for compilation
on the NPU host (ASI2).  The build process is:

1. Read the .asc source from this directory
2. Optionally patch in the host wrapper from the parent directory
3. Write the assembled source to /tmp/mwg_kernel_v4.asc
4. The actual compilation happens on ASI2 via the build_kernel.sh script

Usage (local, pre-staging):
    python3 build_v4.py

Usage (on ASI2):
    cd /vllm-workspace/mwg-ew-transformer-research/custom_ops/ephemeral_core_apply/torch_ext/v4_multicore
    python3 build_v4.py
    # Then compile with the CANN toolchain:
    # ascendc compile --soc=Ascend910B2 -o ephemeral_core_apply_v4.o ephemeral_core_apply_v4_multicore.asc
    # Or use the torch extension build:
    # python3 -m torch.utils.cpp_extension --npu ephemeral_core_apply_v4
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
ASC = HERE / "ephemeral_core_apply_v4_multicore.asc"

def main():
    src = ASC.read_text(encoding="utf-8")
    out = pathlib.Path("/tmp/mwg_kernel_v4.asc")
    out.write_text(src, encoding="utf-8")
    print(f"assembled {len(src)} bytes -> {out}")
    print(f"  source: {ASC}")
    print(f"  lines:  {len(src.splitlines())}")

if __name__ == "__main__":
    main()
