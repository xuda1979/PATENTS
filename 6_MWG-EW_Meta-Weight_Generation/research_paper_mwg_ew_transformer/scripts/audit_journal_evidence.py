#!/usr/bin/env python3
"""Recompute archived evidence, retaining failed gates and provenance limits.

Uses only the standard library. Hash matching proves archive integrity, never
hardware execution, independence, checkpoint identity, or data disjointness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import mean, stdev

ROOT = Path(__file__).resolve().parents[1]
QUALITY = Path("results/asi2_rank512_control_20260922")
EXPECTED = {
    QUALITY / "VERIFIED_RESULT_RECORD.json": "1153803d14339009b65a1648733d126ff2178541f8591b42952cc1f4fb3764ea",
    QUALITY / "per_seed_results.json": "6283b14cb63697c5f56404ffe4afccf50882504d63ed43fda8020af62a611a5a",
}
SEEDS = [f"seed_{s}" for s in range(2026, 2030)]
RANKS = [384, 401, 512]
METHODS = ["static_svd", "persistent_low_rank", "mwg_shuffled_diag_core", "mwg_token_diag_core"]
T975_DF3 = 3.182446305284263


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def verify_hashes(root):
    for path, expected in EXPECTED.items():
        if file_hash(root / path) != expected:
            raise ValueError(f"archive hash mismatch: {path}")


def paired_stats(a, b):
    if len(a) != 4 or len(b) != 4 or not all(finite(x) for x in a + b):
        raise ValueError("paired summary requires four finite, aligned records")
    delta = [x - y for x, y in zip(a, b)]
    centre, sd = mean(delta), stdev(delta)
    half_width = T975_DF3 * sd / 2
    return {"n": 4, "difference": centre, "sample_sd": sd,
            "descriptive_t95_interval": [centre - half_width, centre + half_width]}


def controller_parameters(d, r, h):
    if min(d, r, h) < 1:
        raise ValueError("positive dimensions required")
    return (d + 1) * h + (h + 1) * 3 * r


def quality_summary(per_seed, record):
    if set(per_seed) != set(SEEDS):
        raise ValueError("missing or unexpected seed records")
    if record.get("per_seed_results") != per_seed:
        raise ValueError("duplicate per-seed archive records disagree")
    if record.get("run_id") != "asi2_rank512_control_20260922T080042Z":
        raise ValueError("unexpected quality family")
    rows, contrasts = [], []
    def values(method, rank):
        return [per_seed[s][f"{method}_r{rank}"]["relative_mse"] for s in SEEDS]
    for r in RANKS:
        for method in METHODS:
            vals = values(method, r)
            if not all(finite(v) and v >= 0 for v in vals):
                raise ValueError("nonfinite or negative quality metric")
            factor = 3 * r * (1536 + 8960)
            gen = 0 if method in METHODS[:2] else controller_parameters(1536, r, 192)
            rows.append({"method": method, "rank": r, "mean": mean(vals),
                         "sample_sd": stdev(vals), "reconstructed_fp32_mib": (factor + gen) * 4 / 2**20})
        for control in ["persistent_low_rank", "mwg_shuffled_diag_core"]:
            contrasts.append({"rank": r, "control": control,
                              **paired_stats(values("mwg_token_diag_core", r), values(control, r))})
    near = paired_stats(values("mwg_token_diag_core", 384), values("persistent_low_rank", 401))
    near["relative_penalty_percent"] = 100 * (mean(values("mwg_token_diag_core", 384)) /
                                               mean(values("persistent_low_rank", 401)) - 1)
    return {"evidence_class": "archived_summary_recomputed",
            "run_id": record["run_id"], "rows": rows, "contrasts": contrasts,
            "near_budget_contrast": near,
            "limitations": ["original per-seed run reports and checkpoints absent from canonical family",
                            "shared activation/factor seeds; disjoint datasets across seeds not established",
                            "intervals descriptive under an unverified independent normal paired-run model",
                            "storage reconstructed using code-default controller width h=192; not measured"]}


def kernel_gate(data):
    stability = data.get("stability_1000_calls", {})
    configs = data.get("configs", [])
    names = [c.get("name") for c in configs]
    complete = (len(names) == 5 and len(set(names)) == 5
                and {c.get("T") for c in configs} == {128, 512, 1024, 2048, 4096})
    equivalence = data.get("equivalence", [])
    expected_pairs = {(name, version) for name in names for version in ("v1", "v4", "v1-vs-v4")}
    actual_pairs = [(e.get("config"), e.get("version")) for e in equivalence]
    good_equivalence = (complete and len(actual_pairs) == len(expected_pairs)
                        and set(actual_pairs) == expected_pairs and all(
        e.get("pass") is True and finite(e.get("max_abs_err"))
        and 0 <= e["max_abs_err"] <= 0.005 for e in equivalence))
    final_error = stability.get("final_max_abs_err")
    completed = stability.get("completed")
    passed = (good_equivalence and stability.get("pass") is True
              and type(completed) is int and completed >= 1000
              and finite(final_error) and 0 <= final_error <= 0.005)
    rows = []
    for config in data.get("configs", []):
        x, y = config["v1"]["median_ms"], config["v4"]["median_ms"]
        if not all(finite(v) and v > 0 for v in [x, y]):
            raise ValueError("invalid kernel timing")
        rows.append({"T": config["T"], "v1_ms": x, "v4_ms": y, "ratio_v1_over_v4": x / y})
    return {"verdict": "PASS" if passed else "FAIL", "eligible_for_speedup_claim": False,
            "eligible_for_materialized_speedup_claim": False,
            "numeric_tolerance_abs": 0.005,
            "observed_timing_only": rows,
            "completed_stability_calls": stability.get("completed"),
            "finite_final_error": finite(final_error),
            "stability_pass_flag": stability.get("pass"),
            "reason": "archive numerical gate only; no matched materialized comparison or independently authenticated reference"}


def collect(root):
    verify_hashes(root)
    sources = list(EXPECTED)
    read = lambda p: json.loads((root / p).read_text())
    q = quality_summary(read(QUALITY / "per_seed_results.json"), read(QUALITY / "VERIFIED_RESULT_RECORD.json"))
    kp = Path("results/v4_multicore_benchmark_asi2_v2_20261008.json")
    fp = Path("results/ASI3_arm4_decisive_20260828/key_results_SHIPPED.json")
    sources.extend([kp, fp])
    four = read(fp)
    for key in ("probe_geometry", "largeT_geometry"):
        required = {"dense", "persistent", "materialized", "fused"} if key == "probe_geometry" else {"materialized", "fused"}
        if set(four[key]["median_ms"]) != required or not all(
                finite(v) and v > 0 for v in four[key]["median_ms"].values()):
            raise ValueError("incomplete or nonfinite four-arm timings")
    kernel = kernel_gate(read(kp))  # archive has NaN; output below encodes verdict only
    timings = {}
    folder = root / "results/asi2_opt_inclusive_sync_20260923T025114Z"
    paths = sorted(folder.glob("ASI2_mwg_transformer_*.json"))
    if len(paths) != 3:
        raise ValueError("expected exactly three optimizer timing reports")
    expected_arms = {"dense"} | {f"mwg_r{r}" for r in [32, 64, 96, 128, 192, 256, 384, 512]}
    first_config = None
    for p in paths:
        sources.append(p.relative_to(root))
        data = json.loads(p.read_text())
        if set(data["results"]) != expected_arms:
            raise ValueError("optimizer report arm coverage mismatch")
        config = data["config"]
        if (data["env"]["world_size"] != 4
                or config["optimizer_inclusive_sync"]["optimizer_step_included"] is not True):
            raise ValueError("optimizer timing scope mismatch")
        if first_config is not None and config != first_config:
            raise ValueError("incompatible optimizer configurations")
        first_config = config
        for arm, result in data["results"].items():
            value = result["train_opt_inclusive_sync"]["mean_ms"]
            if not finite(value) or value <= 0:
                raise ValueError("invalid optimizer timing")
            timings.setdefault(arm, []).append(value)
    if any(len(v) != 3 for v in timings.values()):
        raise ValueError("incomplete optimizer repeat coverage")
    dense = mean(timings["dense"])
    opt = [{"arm": arm, "mean_ms": mean(vals), "sample_sd_ms": stdev(vals),
            "dense_over_arm": dense / mean(vals)} for arm, vals in timings.items()]
    return {"schema_version": 1, "quality": q, "v4_kernel": kernel,
            "v1_four_arm": {key: {"median_ms": four[key]["median_ms"],
                                   "fused_over_materialized": four[key]["median_ms"]["fused"] /
                                       four[key]["median_ms"]["materialized"]}
                            for key in ["probe_geometry", "largeT_geometry"]},
            "optimizer_timing": {"rows": opt, "evidence_class": "archived_run_report_recomputed",
                                  "numerical_health": "UNKNOWN", "convergence_claim_eligible": False},
            "provenance": [{"path": str(p), "sha256": file_hash(root / p)} for p in sources],
            "submission_ready": False,
            "blocking_gaps": ["canonical quality raw reports/checkpoints/split manifests incomplete",
                              "v4 stability gate fails; no matched v4/materialized complete-FFN comparison",
                              "no verified quality/latency Pareto curve from same causal model and runtime"]}


def emit_tables(summary, folder):
    folder.mkdir(parents=True, exist_ok=True)
    def table(filename, columns, heading, rows):
        text = ("% Generated by audit_journal_evidence.py\n"
                + "\\begin{tabular}{" + columns + "}\n\\toprule\n"
                + heading + " \\\\\n\\midrule\n" + "\n".join(rows)
                + "\n\\bottomrule\n\\end{tabular}\n")
        (folder / filename).write_text(text)
    names = {"static_svd": "Static SVD", "persistent_low_rank": "Trained persistent",
             "mwg_shuffled_diag_core": "Shuffled controller", "mwg_token_diag_core": "Token controller"}
    rows = [f"{names[r['method']]} & {r['rank']} & {r['reconstructed_fp32_mib']:.3f} & "
            f"${r['mean']:.6f} \\pm {r['sample_sd']:.6f}$ \\\\" for r in summary["quality"]["rows"]]
    table("journal_quality_rows.tex", "llrr", "Model & Rank & fp32 MiB & Relative MSE", rows)
    rows = []
    for r in summary["quality"]["contrasts"]:
        lo, hi = r["descriptive_t95_interval"]
        rows.append(f"{r['rank']} & {names[r['control']]} & ${r['difference']:+.6f}$ & $[{lo:+.6f},{hi:+.6f}]$ \\\\")
    table("journal_contrast_rows.tex", "llrr", "Rank & Control & Mean difference & Descriptive 95\\% interval", rows)
    rows = [f"{r['arm'].replace('_', ' ')} & ${r['mean_ms']:.4f} \\pm {r['sample_sd_ms']:.4f}$ & "
            f"${r['dense_over_arm']:.3f}$ \\\\" for r in summary["optimizer_timing"]["rows"]]
    table("journal_timing_rows.tex", "lrr", "Arm & Time (ms) & Dense/arm ratio", rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "results/journal_revision_20261022/evidence_audit.json")
    parser.add_argument("--tables", action="store_true")
    parser.add_argument("--require-submission-ready", action="store_true")
    args = parser.parse_args()
    result = collect(ROOT)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    if args.tables:
        emit_tables(result, ROOT / "paper/generated_tables")
    print(json.dumps({"archive_recomputation": "PASS", "v4_stability": result["v4_kernel"]["verdict"],
                      "submission_ready": result["submission_ready"], "output": str(args.out)}))
    if args.require_submission_ready and not result["submission_ready"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
