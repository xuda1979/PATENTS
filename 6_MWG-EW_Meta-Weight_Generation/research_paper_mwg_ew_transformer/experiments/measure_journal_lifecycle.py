#!/usr/bin/env python3
"""CPU software verification of actual MWG FFN rematerialization.

This measures unique nonparameter storage retained by autograd during FFN
forward, including caller-owned input storage. It does NOT measure allocator
peak memory, HBM traffic, model quality, or accelerator efficiency. Synthetic
random inputs and random initialized factors are explicit software fixtures.

Run from the research workspace:
  python experiments/measure_journal_lifecycle.py --output \
    results/journal_revision_20261022/lifecycle_cpu.json
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import torch
from torch.utils.checkpoint import checkpoint

from mwg_quality_distillation import LowRankFFN

ROOT = Path(__file__).resolve().parents[1]
ATOL, RTOL = 1e-7, 1e-6


def storage_key(tensor: torch.Tensor) -> tuple:
    storage = tensor.untyped_storage()
    return str(tensor.device), storage.data_ptr(), storage.nbytes()


class SavedStorageLedger:
    """Count unique saved underlying storages, excluding parameter aliases."""

    def __init__(self, parameters):
        self.parameters = {storage_key(p) for p in parameters}
        self.saved = {}
        self.references = 0
        self.excluded_parameters = 0

    def pack(self, tensor):
        self.references += 1
        key = storage_key(tensor)
        if key in self.parameters:
            self.excluded_parameters += 1
        elif key[2]:
            # Retain the tensor as autograd itself does; views share one entry.
            self.saved.setdefault(key, tensor)
        return tensor

    @staticmethod
    def unpack(tensor):
        return tensor

    def snapshot(self):
        return {
            "unique_storage_bytes": sum(key[2] for key in self.saved),
            "unique_storages": len(self.saved),
            "save_references": self.references,
            "excluded_parameter_references": self.excluded_parameters,
        }


def make_case(seed: int, depth: int, d=32, m=64, rank=8, batch=2, seq=16):
    if depth <= 0 or min(d, m, rank, batch, seq) <= 0:
        raise ValueError("all dimensions and depth must be positive")
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        layers = torch.nn.ModuleList()
        for _ in range(depth):
            def pair(n_in, n_out):
                return (torch.randn(n_in, rank) / n_in ** 0.5,
                        torch.randn(rank, n_out) / rank ** 0.5)
            factors = {"up": pair(d, m), "gate": pair(d, m),
                       "down": pair(m, d)}
            layers.append(LowRankFFN(
                factors, dtype=torch.float32, generator="token_diag_core",
                generator_hidden=16, scale_amplitude=0.2,
            ))
        x = torch.randn(batch, seq, d)
        target = torch.randn_like(x)
    return layers, x, target


def model_hash(model):
    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        digest.update(name.encode())
        digest.update(str((tuple(tensor.shape), str(tensor.dtype))).encode())
        digest.update(bytes(tensor.contiguous().view(torch.uint8).flatten().tolist()))
    return digest.hexdigest()


def run_arm(template, x, target, checkpointed):
    # Separate models prevent gradient/storage state leaking between arms.
    model = copy.deepcopy(template)
    xi = x.detach().clone().requires_grad_(True)
    ledger = SavedStorageLedger(model.parameters())
    initial_hash = model_hash(model)
    with torch.autograd.graph.saved_tensors_hooks(ledger.pack, ledger.unpack):
        output = xi
        for layer in model:
            correction = (checkpoint(layer, output, use_reentrant=False)
                          if checkpointed else layer(output))
            output = output + correction
    # The ledger boundary is FFN forward. The MSE loss is deliberately outside.
    saved = ledger.snapshot()
    loss = (output - target).square().mean()
    loss.backward()
    gradients = {}
    for name, parameter in model.named_parameters():
        if parameter.grad is None:
            raise AssertionError(f"missing gradient for {name}")
        gradients[name] = parameter.grad.detach().clone()
    if xi.grad is None:
        raise AssertionError("missing input gradient")
    return {"saved": saved, "initial_state_sha256": initial_hash,
            "output": output.detach().clone(), "loss": loss.detach().clone(),
            "input_gradient": xi.grad.detach().clone(), "gradients": gradients}


def validate_pair(eager, candidate):
    if eager["initial_state_sha256"] != candidate["initial_state_sha256"]:
        raise AssertionError("initial state hashes differ")
    if set(eager["gradients"]) != set(candidate["gradients"]):
        raise AssertionError("gradient names differ")
    if not eager["gradients"]:
        raise AssertionError("empty parameter-gradient comparison")
    pairs = [(key, eager[key], candidate[key])
             for key in ("output", "loss", "input_gradient")]
    pairs.extend((f"gradient:{name}", value, candidate["gradients"][name])
                 for name, value in eager["gradients"].items())
    deltas = {}
    for name, left, right in pairs:
        if not torch.isfinite(left).all() or not torch.isfinite(right).all():
            raise AssertionError(f"non-finite value in {name}")
        torch.testing.assert_close(left, right, atol=ATOL, rtol=RTOL,
                                   msg=lambda msg: f"{name}: {msg}")
        deltas[name] = float((left - right).abs().max())
    return deltas


def measure_case(seed: int, depth: int):
    template, x, target = make_case(seed, depth)
    # Demonstrate nonconstant context controls; this rules out a vacuous fixed
    # controller. Require actual nonzero controller gradients below as well.
    responses = []
    with torch.no_grad():
        for layer in template:
            a = layer._token_diag_cores(x)
            b = layer._token_diag_cores(torch.roll(x, shifts=1, dims=1))
            responses.append(max(float((p - q).abs().max()) for p, q in zip(a, b)))
    if min(responses) <= 1e-7:
        raise AssertionError("controller context response is absent")
    eager = run_arm(template, x, target, checkpointed=False)
    recompute = run_arm(template, x, target, checkpointed=True)
    deltas = validate_pair(eager, recompute)
    controller_norm = sum(float(g.abs().sum()) for name, g in eager["gradients"].items()
                          if ".generator." in name)
    if not controller_norm > 0:
        raise AssertionError("controller gradient is absent")
    num = eager["saved"]["unique_storage_bytes"]
    den = recompute["saved"]["unique_storage_bytes"]
    if den <= 0:
        raise AssertionError("empty checkpoint activation ledger")
    return {"seed": seed, "depth": depth, "d": 32, "m": 64, "rank": 8,
            "batch": 2, "seq": 16, "generator_hidden": 16,
            "scale_amplitude": 0.2, "initial_state_sha256": eager["initial_state_sha256"],
            "eager": eager["saved"], "checkpoint": recompute["saved"],
            "retained_storage_ratio": num / den,
            "output_max_abs_delta": deltas["output"],
            "loss_abs_delta": deltas["loss"],
            "input_gradient_max_abs_delta": deltas["input_gradient"],
            "parameter_gradient_max_abs_delta": max(v for k, v in deltas.items()
                                                     if k.startswith("gradient:")),
            "validated_parameter_gradients": len(eager["gradients"]),
            "controller_context_max_abs_delta": max(responses),
            "controller_context_min_layer_max_abs_delta": min(responses),
            "controller_gradient_l1": controller_norm,
            "loss": float(eager["loss"]), "all_checked_tensors_finite": True,
            "passed": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    started = time.perf_counter()
    rows = [measure_case(seed, depth) for depth in (1, 2, 4)
            for seed in (2026, 2027, 2028)]
    sources = [Path(__file__), ROOT / "experiments/mwg_quality_distillation.py",
               ROOT / "tests/test_journal_lifecycle.py"]
    report = {
        "schema": "mwg-journal-cpu-lifecycle-v1", "status": "PASS",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "evidence_kind": "measured_cpu_software_verification_synthetic_fixture",
        "model_class": "mwg_quality_distillation.LowRankFFN",
        "architecture": "residual stack h = h + LowRankFFN(token_diag_core)(h)",
        "runtime": {"python": sys.version, "torch": torch.__version__,
                    "device": "cpu", "platform": platform.platform(),
                    "threads": torch.get_num_threads(), "dtype": "float32"},
        "contract": {
            "checkpoint": "torch.utils.checkpoint.checkpoint(use_reentrant=False)",
            "storage": "unique nonparameter underlying storage retained by FFN-forward saved tensors",
            "includes": ["saved caller-owned inputs", "full underlying storage for saved views"],
            "excludes": ["parameter aliases", "loss saved tensors", "zero-byte dummy tensors"],
            "not_measured": ["allocator peak", "HBM traffic", "accelerator speed", "trained-model quality"],
            "gradient_atol": ATOL, "gradient_rtol": RTOL,
            "parameter_state": "random initialized synthetic fixture; identical copies per arm",
        },
        "source_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in sources},
        "elapsed_seconds": time.perf_counter() - started, "cases": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": report["status"], "cases": len(rows),
                      "storage_ratio_range": [min(r["retained_storage_ratio"] for r in rows),
                                              max(r["retained_storage_ratio"] for r in rows)],
                      "max_parameter_gradient_delta": max(r["parameter_gradient_max_abs_delta"] for r in rows),
                      "output": str(args.output)}))


if __name__ == "__main__":
    main()
