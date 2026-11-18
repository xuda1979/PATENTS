"""Gate-enforcement verifier for the tile-local block-Givens benchmark.

Single source of truth for the PRE-REGISTERED acceptance gate of the compiled
``block_givens_tile_apply`` kernel, invoked by
``scripts/asi2_block_givens_tile_apply_benchmark_worker.sh``.

TILE_GATE (versioned before any measurement; thresholds, not predictions;
must mirror the harness header verbatim):

  speed_ceiling_ratio : 0.80   # tile median_ms <= 0.80 * persistent median_ms
                               # (>=20% lower latency, Q4's threshold)
  correctness_max_rel : 2e-2   # compiled vs CPU-model, scale-relative
  batch               : 1      # Q4 timing boundary
  seq                 : 128
  dtype               : fp16
  verdict_policy      : PASS only if speed AND correctness hold for every
                        seed; a failed target is recorded as a first-class
                        negative result, never promoted.

Modes:
  --verify-only  : run the numeric verification fixture (device op vs CPU
                   model) and write verification.json.  Requires the compiled
                   op on the NPU host.
  --benchmark    : measure the tile-apply path and the matched persistent arm
                   on one trained checkpoint seed; write seed_<s>_benchmark.json.
  --gate         : evaluate TILE_GATE over the run directory's benchmark
                   records; write report.json with verdict PASS/FAIL and the
                   recorded margins.  Refuses to emit PASS if any verification
                   or benchmark record is missing or failed.

Local/offline-safe: without a device the script refuses modes that need the
op rather than pretending to run them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TILE_GATE = {
    "speed_ceiling_ratio": 0.80,
    "speed_margin_label": ">=20% lower latency than the matched persistent arm",
    "correctness_max_rel": 2e-2,
    "batch": 1,
    "seq": 128,
    "dtype": "fp16",
    "verdict_policy": "PASS requires speed and correctness for every seed; "
                      "failures are recorded as first-class negative results",
}

GATE_SCHEMA = "mwg-tile-apply-benchmark-gate-v1"
EXPECTED_SEEDS = (2026, 2027, 2028)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _device_op():
    try:
        import torch  # noqa: F401
        import torch_npu  # noqa: F401  # noqa: F401
    except Exception as exc:  # pragma: no cover - device-only path
        raise SystemExit(
            f"this mode requires the NPU host (torch_npu unavailable: {exc})")
    # The compiled op is loaded through the vendor-built extension; its
    # module name is fixed by the build flow.
    import importlib
    try:
        return importlib.import_module("block_givens_tile_apply_ext")
    except Exception as exc:
        raise SystemExit(
            f"compiled op extension not importable (compile first): {exc}")


def cpu_model_reference(x, u, v, angles):
    sys.path.insert(0, str(ROOT / "custom_ops" / "block_givens_tile_apply"))
    sys.path.insert(0, str(ROOT / "experiments"))
    from sim_block_givens_tile_apply import simulate_kernel_numeric_model
    out, _ = simulate_kernel_numeric_model(x, u, v, angles)
    return out


def verify_only(out_path: Path) -> None:
    torch = _device_torch()
    op = _device_op()
    generator = torch.Generator(device="cpu").manual_seed(20261117)
    t, d, r = 21, 512, 64
    x = torch.randn(t, d, generator=generator)
    u = torch.randn(d, r, generator=generator)
    v = torch.randn(r, d, generator=generator)
    angles = (torch.rand(t, d // 2, generator=generator) - 0.5) * 2.0

    device_out = op.apply(x.npu(), u.npu(), v.npu(), angles.npu()).cpu()
    model_out = cpu_model_reference(x, u, v, angles)
    scale = model_out.float().abs().max().item()
    rel = (device_out.float() - model_out.float()).abs().max().item() / max(scale, 1e-6)
    passed = rel <= TILE_GATE["correctness_max_rel"]
    payload = {
        "schema": GATE_SCHEMA,
        "mode": "verify-only",
        "fixture": {"t": t, "d": d, "r": r, "seed": 20261117},
        "max_rel_diff": rel,
        "threshold": TILE_GATE["correctness_max_rel"],
        "passed": passed,
        "time": datetime.now(timezone.utc).isoformat(),
    }
    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    if not passed:
        raise SystemExit(f"verification FAILED: {rel:.4%} > "
                         f"{TILE_GATE['correctness_max_rel']:.2%}")
    print(json.dumps({"mode": "verify-only", "passed": True, "max_rel_diff": rel}))


def _device_torch():
    try:
        import torch
        import torch_npu  # noqa: F401
        return torch
    except Exception as exc:
        raise SystemExit(f"requires the NPU host (torch_npu: {exc})")


def benchmark(seed: int, out_path: Path, op_name: str) -> None:
    torch = _device_torch()
    # The trained checkpoints live on the measurement host under the Q4 run
    # tree; the arm geometry follows the closing run (d=1536, m=8960, r=384).
    ckpt_dir = Path("/vllm-workspace/mwg-ew-transformer-research/results/"
                    "asi2_q4_matched_quality_latency_20261113")
    sys.path.insert(0, str(ROOT / "experiments"))
    from mwg_transformer_ASI3_benchmark import load_trained_master_weights  # type: ignore
    raise SystemExit(
        "benchmark mode is device-only: implemented on the NPU host against "
        "the Q4 checkpoint tree; this local copy refuses to fabricate timings")


def evaluate_gate(run_dir: Path, out_path: Path) -> None:
    """Evaluate the pre-registered gate over the run directory records."""
    verification_path = run_dir / "verification.json"
    if not verification_path.is_file():
        raise SystemExit("gate evaluation refused: verification.json missing")
    verification = json.loads(verification_path.read_text())
    if not verification.get("passed"):
        raise SystemExit("gate evaluation refused: verification did not pass")

    benchmarks = {}
    for seed in EXPECTED_SEEDS:
        path = run_dir / f"seed_{seed}_benchmark.json"
        if not path.is_file():
            raise SystemExit(f"gate evaluation refused: seed {seed} "
                             f"benchmark record missing")
        benchmarks[seed] = json.loads(path.read_text())

    per_seed = {}
    all_pass = True
    for seed, record in benchmarks.items():
        tile_ms = record["tile_apply"]["median_ms"]
        persistent_ms = record["persistent"]["median_ms"]
        ratio = tile_ms / persistent_ms
        passed = ratio <= TILE_GATE["speed_ceiling_ratio"]
        all_pass &= passed
        per_seed[str(seed)] = {
            "tile_apply_median_ms": tile_ms,
            "persistent_median_ms": persistent_ms,
            "ratio": ratio,
            "speed_ceiling_ratio": TILE_GATE["speed_ceiling_ratio"],
            "speed_margin": 1.0 - ratio,
            "passed": passed,
        }
    verdict = "PASS" if all_pass else "FAIL"
    payload = {
        "schema": GATE_SCHEMA,
        "mode": "gate",
        "verdict": verdict,
        "gate": TILE_GATE,
        "verification": {
            "max_rel_diff": verification["max_rel_diff"],
            "passed": verification["passed"],
        },
        "per_seed": per_seed,
        "claim_boundary": (
            "single-layer, batch 1, S=128, fp16, one Ascend 910B2 device; "
            "not end-to-end decode latency; PASS does not by itself set "
            "submission_ready (the audit's gate list decides that); a FAIL "
            "is a first-class negative result for the compiled tile-local "
            "realization"),
        "time": datetime.now(timezone.utc).isoformat(),
    }
    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "seeds": len(per_seed)}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--gate", action="store_true")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--batch", type=int, default=TILE_GATE["batch"])
    parser.add_argument("--seq", type=int, default=TILE_GATE["seq"])
    parser.add_argument("--op", default="block_givens_tile_apply")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if args.verify_only:
        verify_only(args.out)
    elif args.benchmark:
        if args.seed is None:
            raise SystemExit("--benchmark requires --seed")
        benchmark(args.seed, args.out, args.op)
    elif args.gate:
        if args.run_dir is None:
            raise SystemExit("--gate requires --run-dir")
        evaluate_gate(args.run_dir, args.out)
    else:
        raise SystemExit("choose --verify-only, --benchmark, or --gate")


if __name__ == "__main__":
    main()
