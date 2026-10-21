#!/usr/bin/env python3
"""
ingest_causal_quality_results.py

Reads pulled causal-quality per-seed report JSONs (the reports that
scripts/launch_ASI2_causal_quality_oneshot.sh --collect places into
results/asi2_causal_quality_pull/) and emits:

  1. A JSON summary (means/std across all seeds) for the paper tables, and
  2. Ready-to-paste LaTeX table rows (mean +/- std) for the manuscript.

Only seeds whose report is marked evidence_mode=true, env_label=ASI2, and
whose dense teacher control is exact (relative_mse==0.0, cosine==1.0) are
accepted, mirroring the launcher's own gates.  The non-inferiority verdict
compares the diagonal-core (token_diag_core r384) mean against the
parameter-matched persistent r401 control within the operator-predeclared
margin (default relative_mse margin 0.0; supply --margin to relax).

The four-arm systems numbers are NEVER modified by this tool.

Usage:
  python3 scripts/ingest_causal_quality_results.py \
      --pull-dir results/asi2_causal_quality_pull \
      [--out-json results/causal_quality_summary.json] \
      [--margin 0.0] [--seeds 2026,2027,2028]
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import math
from pathlib import Path
from typing import Any

# Trained-student key -> (paper label, control, parameter-matching rank)
STUDENT_KEY = {
    # causal method
    "mwg_token_diag_core_r384": ("token\\_diag\\_core (r384)", "causal", 384),
    # persistent controls
    "persistent_low_rank_r384": ("persistent low-rank (r384)", "same_rank", 384),
    "persistent_low_rank_r401": ("persistent low-rank (r401)", "param_matched", 401),
    "persistent_low_rank_r512": ("persistent low-rank (r512)", "effective", 512),
    # static SVD controls (measured at r384/401/512)
    "static_svd_r384": ("static SVD (r384)", "same_rank", 384),
    "static_svd_r401": ("static SVD (r401)", "param_matched", 401),
    "static_svd_r512": ("static SVD (r512)", "effective", 512),
}
DENSE_KEY = "dense_teacher"
DIAG_KEY = "mwg_token_diag_core_r384"   # causal method
MATCHED_KEY = "persistent_low_rank_r401"  # parameter-matched persistent control
SEEDS = [2026, 2027, 2028]


def load_report(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data


def valid_seed_report(data: dict[str, Any]) -> tuple[bool, str]:
    """Apply the launcher's gates. Returns (ok, reason)."""
    cfg = data.get("config", {})
    if not cfg.get("evidence_mode"):
        return False, "not evidence_mode"
    if cfg.get("env_label") != "ASI2":
        return False, "env_label != ASI2"
    # dense teacher exact control
    res = data.get("results", {})
    dense = res.get("dense_teacher", {}).get("metrics", {})
    if abs(float(dense.get("relative_mse", -1))) > 1e-9 or \
       abs(float(dense.get("cosine", 0.0)) - 1.0) > 1e-9:
        return False, f"dense teacher not exact control (mse={dense.get('relative_mse')}, cos={dense.get('cosine')})"
    # all required students present
    required = list(STUDENT_KEY.keys())
    missing = [k for k in required if k not in res]
    if missing:
        return False, f"missing students: {missing}"
    return True, "ok"


def gather(pull_dir: Path, seeds: list[int]) -> tuple[dict[str, list[float]], dict[str, Any], list[str]]:
    """Return (by_key -> {rel_mse, cosine} per seed), per-seed metadata, accepted warnings."""
    out: dict[str, dict[str, list[float]]] = {k: {"rel_mse": [], "cosine": []} for k in STUDENT_KEY}
    meta: dict[str, Any] = {}
    warnings: list[str] = []
    seen_seeds: set[int] = set()
    for path in sorted(pull_dir.glob("*report.json")):
        data = load_report(path)
        if not valid_seed_report(data)[0]:
            continue
        seed = int(data.get("config", {}).get("seed", -1))
        if seed not in seeds:
            continue
        if seed in seen_seeds:
            warnings.append(f"duplicate seed {seed} in {path.name}; keeping first")
            continue
        seen_seeds.add(seed)
        for key in STUDENT_KEY:
            metrics = data["results"][key]["metrics"]
            out[key]["rel_mse"].append(float(metrics["relative_mse"]))
            out[key]["cosine"].append(float(metrics["cosine"]))
        meta[f"seed_{seed}"] = {
            "seed": seed,
            "file": path.name,
            "layer": data.get("config", {}).get("layer"),
            "dtype": data.get("config", {}).get("dtype"),
            "steps": data.get("config", {}).get("steps"),
        }
    for s in seeds:
        if s not in seen_seeds:
            warnings.append(f"missing completed seed {s}")
    return out, meta, warnings


def fmt(mean: float, std: float, nd: int = 3) -> str:
    if std is None or math.isnan(std):
        return f"{mean:.{nd}f}"
    return f"${mean:.{nd}f}\\pm{std:.{nd}f}$"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pull-dir", default="results/asi2_causal_quality_pull")
    ap.add_argument("--out-json", default=None)
    ap.add_argument("--margin", type=float, default=0.0,
                    help="non-inferiority margin on relative_mse vs param-matched persistent r401 (default 0.0)")
    ap.add_argument("--seeds", default="2026,2027,2028")
    args = ap.parse_args()

    pull = Path(args.pull_dir)
    if not pull.is_dir():
        raise SystemExit(f"pull dir not found: {pull}")
    seeds = [int(x) for x in args.seeds.split(",") if x.strip()]
    data, meta, warnings = gather(pull, seeds)

    complete = all(len(data[k]["rel_mse"]) == len(seeds) for k in STUDENT_KEY)
    print("=== Causal-quality multi-seed summary ===")
    print(f"completed seeds: {len(meta)}/{len(seeds)}  complete={complete}")
    for w in warnings:
        print(f"  WARN: {w}")
    if not complete:
        print("Not all seeds complete; summary is partial.")
    print()

    rows: dict[str, dict[str, Any]] = {}
    for key, (label, control, pmatch) in STUDENT_KEY.items():
        rel = data[key]["rel_mse"]
        cos = data[key]["cosine"]
        rows[key] = {
            "label": label, "control": control, "param_match_rank": pmatch,
            "n": len(rel),
            "rel_mse": {"mean": statistics.mean(rel) if rel else None,
                        "std": statistics.stdev(rel) if len(rel) > 1 else None,
                        "per_seed": rel},
            "cosine": {"mean": statistics.mean(cos) if cos else None,
                       "std": statistics.stdev(cos) if len(cos) > 1 else None,
                       "per_seed": cos},
        }

    print(f"{'Model (paper label)':<34}{'Rel.MSE mean±std':<22}{'Cosine mean±std':<22}")
    print("-" * 78)
    for key in STUDENT_KEY:
        r, c = rows[key]["rel_mse"], rows[key]["cosine"]
        if r["mean"] is None:
            continue
        print(f"{rows[key]['label']:<34}{fmt(r['mean'], r['std']):<22}{fmt(c['mean'], c['std']):<22}")

    # Non-inferiority verdict (causal diag-core vs parameter-matched persistent r401)
    print()
    if DIAG_KEY in rows and MATCHED_KEY in rows and complete:
        diag = rows[DIAG_KEY]["rel_mse"]["mean"]
        matched = rows[MATCHED_KEY]["rel_mse"]["mean"]
        margin = args.margin
        if diag is not None and matched is not None:
            noninf = diag <= matched + margin
            print(f"Non-inferiority verdict (rel_mse, margin={margin}): "
                  f"diag-core {diag:.4f} vs param-matched persistent {matched:.4f} -> "
                  f"{'NON-INFERIOR ✓' if noninf else 'WORSE (honest negative)'}")
            rows["_verdict"] = {"diag_core_rel_mse": diag, "param_matched_rel_mse": matched,
                                "margin": margin, "non_inferior": bool(noninf)}
    else:
        rows["_verdict"] = {"non_inferior": None, "reason": "incomplete"}

    # LaTeX table rows (only if complete)
    print("\n=== LaTeX table rows (mean $\\pm$ std) ===")
    if complete:
        print("\\begin{tabular}{lrrrr}")
        print("\\toprule")
        print("Method & Rank & Rel.~MSE & Cosine & Params MiB \\\\")
        print("\\midrule")
        # dense teacher row
        print("Dense teacher & --- & $0.000$ & $1.000$ & --- \\\\")
        for key in STUDENT_KEY:
            r, c = rows[key]["rel_mse"], rows[key]["cosine"]
            if r["mean"] is None:
                continue
            print(f"{rows[key]['label']} & {rows[key]['param_match_rank']} & "
                  f"{fmt(r['mean'], r['std'])} & {fmt(c['mean'], c['std'], 4)} & --- \\\\")
        print("\\bottomrule")
        print("\\end{tabular}")

    if args.out_json:
        payload = {"complete": complete, "rows": rows, "meta": meta,
                   "warnings": warnings, "margin": args.margin}
        out = Path(args.out_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\nWrote summary JSON -> {out}")


if __name__ == "__main__":
    main()
