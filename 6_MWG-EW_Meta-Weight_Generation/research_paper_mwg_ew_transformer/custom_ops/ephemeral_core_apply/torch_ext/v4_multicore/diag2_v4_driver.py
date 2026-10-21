#!/usr/bin/env python3
"""Run v4 held-weights mode excluding T=64 (which hard-faults the device).

Imported-driver variant of diag2_root_cause.py so TS_HELD can be overridden
without touching the original file.
"""
import json
import sys

import torch

import diag2_root_cause as d

OUT = sys.argv[1] if len(sys.argv) > 1 else "results/diag2_v4_held_no64.json"
d.TS_HELD = (128, 192, 256, 384, 512, 2048)

torch.npu.set_device(0)
a = torch.randn(128, 128, device="npu:0")
b = a @ a
torch.npu.synchronize()
print(f"sanity matmul: finite={bool(torch.isfinite(b).all().item())}")

results = []
torch.ops.load_library(d.V4_SO)
op = torch.ops.mwg.ephemeral_core_apply_v4
print(f"loaded v4: {d.V4_SO}")

d.held_mode("v4-held-noT64", op, results)

n_pass = sum(1 for r in results if r["pass"])
print(f"\n=== v4-held-noT64: {n_pass}/{len(results)} PASS ===")
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)
print(f"results written to {OUT}")
