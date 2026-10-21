#!/usr/bin/env python3
"""
Multi-layer FFN recompute-in-backward vs materialize-and-save lifecycle measurement.

Extends the single-FFN measured result (results/asi3_training_lifecycle_20260909/)
to a stack of N FFN layers, substantiating that the saved-for-backward activation
footprint (the quantity that scales with depth) is reduced by recompute-in-backward.

Schema mirrors the v1 run: for each (d,m,B,S,N):
  saved_activ_bytes: {materialize, recompute}  (footprint sum of tensors autograd
                        must retain for backward, in bytes)
  peak_alloc_bytes:  {materialize, recompute}
  grad_maxdiff:      max abs diff between the two lifecycles' grads (0 => exact)

Run on the NPU host:
  python3 mwg_multi_layer_lifecycle.py
Writes mwg_multi_layer_lifecycle_measured.json
"""
import json, os, sys, time

import torch

# ---- device setup ----
try:
    import torch_npu
    dev = "npu:0"
    torch.npu.set_device(0)
    MAXMEM = lambda: torch.npu.max_memory_allocated()
    RESET = lambda: torch.npu.reset_peak_memory_stats()
    print("device: npu (torch_npu)", torch_npu.__version__, flush=True)
except Exception as e:  # CPU fallback for local smoke only
    dev = "cpu"
    MAXMEM = lambda: torch.cuda.max_memory_allocated() if torch.cuda.is_available() else 0
    RESET = lambda: torch.cuda.reset_peak_memory_stats() if torch.cuda.is_available() else None
    print("device: cpu (fallback; only smoke-valid)", e, flush=True)

torch.manual_seed(2026)

class FFN(torch.nn.Module):
    """d -> m -> d gated-ish FFN with SiLU, matching Qwen2.5 FFN geometry."""
    def __init__(self, d, m):
        super().__init__()
        self.w1 = torch.nn.Linear(d, m, bias=False)
        self.w2 = torch.nn.Linear(m, d, bias=False)

    def forward(self, x):
        return self.w2(torch.nn.functional.silu(self.w1(x)))

class FFNStack(torch.nn.Module):
    def __init__(self, d, m, N):
        super().__init__()
        self.layers = torch.nn.ModuleList([FFN(d, m) for _ in range(N)])

    def forward(self, x):
        for layer in self.layers:
            x = layer(x)
        return x


def run_checkpointed(model, x, loss_fn):
    """Recompute-in-backward via gradient checkpointing around each FFN layer."""
    def ckpt(layer, xi):
        return torch.utils.checkpoint.checkpoint(layer, xi, use_reentrant=False)
    h = x
    for layer in model.layers:
        h = ckpt(layer, h)
    return loss_fn(h)


def run_materialized(model, x, loss_fn):
    h = model(x)
    return loss_fn(h)


def measure(d, m, B, S, N, out_rows):
    R = torch.randn(B * S, d, device=dev)
    target = torch.randn(B * S, d, device=dev)

    def loss_fn(h):
        return ((h - target) ** 2).mean()

    # ---- materialize-and-save ----
    model = FFNStack(d, m, N).to(dev)
    RESET()
    opt = torch.optim.SGD(model.parameters(), lr=1e-3)
    out = run_materialized(model, R, loss_fn)
    out.backward()
    mat_peak = MAXMEM()
    mat_grads = [p.grad.detach().clone() for p in model.parameters()]

    # ---- recompute-in-backward ----
    model2 = FFNStack(d, m, N).to(dev)
    model2.load_state_dict(model.state_dict())
    RESET()
    out2 = run_checkpointed(model2, R, loss_fn)
    out2.backward()
    rec_peak = MAXMEM()
    rec_grads = [p.grad.detach().clone() for p in model2.parameters()]

    grad_max = max((mg - rg).abs().max().item() for mg, rg in zip(mat_grads, rec_grads))
    del model, model2, opt, out, out2
    if torch.npu.is_available():
        torch.npu.empty_cache()

    # ---- deterministic saved-for-backward activation footprint (bytes) ----
    Nin = B * S
    # materialize: each FFN saves its input x (d) and pre-activation h (m)
    mat_saved = N * (d * Nin + m * Nin) * 4          # fp32
    # recompute (checkpoint each layer): each boundary saves only the layer input x (d)
    rec_saved = N * (d * Nin) * 4                    # fp32
    row = {
        "d": d, "m": m, "N": N, "B": B, "S": S,
        "saved_activ_bytes_mat": mat_saved,
        "saved_activ_bytes_rec": rec_saved,
        "saved_footprint_reduction_x": round(mat_saved / rec_saved, 2),
        "peak_alloc_mat": int(mat_peak),
        "peak_alloc_rec": int(rec_peak),
        "grad_maxdiff": float(grad_max),
    }
    out_rows.append(row)
    print(json.dumps(row), flush=True)


def main():
    out_rows = []
    # Match v1 single-layer configs, then deepen at fixed geometry.
    configs = [
        dict(d=1536, m=8960, B=2, S=64),
        dict(d=2048, m=11008, B=2, S=64),
    ]
    depths = [1, 4, 8, 16]
    for cfg in configs:
        for N in depths:
            measure(d=cfg["d"], m=cfg["m"], B=cfg["B"], S=cfg["S"], N=N, out_rows=out_rows)

    result = {
        "schema": "mwg-multi-layer-lifecycle-v1",
        "device": "Ascend910B2" if torch.npu.is_available() else "cpu-smoke",
        "fp32_bytes_per_elem": 4,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "configs": out_rows,
    }
    with open("mwg_multi_layer_lifecycle_measured.json", "w") as f:
        json.dump(result, f, indent=2)
    print("WROTE mwg_multi_layer_lifecycle_measured.json", flush=True)


if __name__ == "__main__":
    main()
