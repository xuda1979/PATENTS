"""Summarize the scoped positive MWG-EW regime from completed result JSONs.

The goal is not to declare broad readiness. It is to make the current claim
boundary reproducible: bounded selective routing has stable positive windows,
while always-patched replacement and persistent low-rank controls remain broad
negative under the current evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_BASE = Path("results/pulled_asi3/asi3_validation_20260525")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def pct_gain(ratio: float) -> float:
    return (1.0 - ratio) * 100.0


def keyed_frontier(rows: list[dict[str, Any]], ratio_key: str) -> dict[float, dict[str, Any]]:
    keyed = {}
    for row in rows:
        target = float(row["target_patch_fraction"])
        keyed[target] = {
            "target_patch_fraction": target,
            "mean_actual_patch_token_fraction": float(row["mean_actual_patch_token_fraction"]),
            "mean_ratio": float(row[ratio_key]),
            "min_ratio": float(row.get("min_token_weighted_ppl_ratio", row.get("min_ppl_ratio"))),
            "max_ratio": float(row.get("max_token_weighted_ppl_ratio", row.get("max_ppl_ratio"))),
            "replicate_count": int(row.get("seed_count", row.get("run_count", 0))),
        }
    return keyed


def classify_target(
    broad: dict[str, Any],
    leave_suite_out: dict[str, Any],
    strict_margin: float,
) -> str:
    if broad["max_ratio"] < 1.0 and leave_suite_out["max_ratio"] < 1.0:
        if broad["mean_ratio"] <= 1.0 - strict_margin and leave_suite_out["mean_ratio"] <= 1.0 - strict_margin:
            return "stable_positive"
        return "weak_positive"
    if broad["mean_ratio"] < 1.0 and leave_suite_out["mean_ratio"] < 1.0:
        return "promising_but_unstable"
    return "negative_or_unready"


def summarize_router(
    broad_seed_sweep: dict[str, Any],
    leave_suiteout_seed_sweep: dict[str, Any],
    cv_summary: dict[str, Any],
    strict_margin: float,
) -> dict[str, Any]:
    broad = keyed_frontier(broad_seed_sweep["aggregate_frontier"], "mean_token_weighted_ppl_ratio")
    leave_suite = keyed_frontier(
        leave_suiteout_seed_sweep["aggregate_frontier"],
        "mean_token_weighted_ppl_ratio",
    )
    cv = keyed_frontier(cv_summary["aggregate_frontier"], "mean_ppl_ratio")
    targets = []
    for target in sorted(set(broad) & set(leave_suite)):
        broad_row = broad[target]
        leave_row = leave_suite[target]
        status = classify_target(broad_row, leave_row, strict_margin)
        targets.append(
            {
                "target_patch_fraction": target,
                "status": status,
                "broad_seed_sweep": broad_row,
                "leave_suite_out": leave_row,
                "cv": cv.get(target),
                "mean_broad_gain_percent": pct_gain(broad_row["mean_ratio"]),
                "mean_leave_suite_out_gain_percent": pct_gain(leave_row["mean_ratio"]),
            }
        )
    stable_targets = [row["target_patch_fraction"] for row in targets if row["status"] == "stable_positive"]
    weak_targets = [row["target_patch_fraction"] for row in targets if row["status"] == "weak_positive"]
    promising_targets = [row["target_patch_fraction"] for row in targets if row["status"] == "promising_but_unstable"]
    return {
        "claim": "bounded_selective_routing",
        "stable_positive_targets": stable_targets,
        "weak_positive_targets": weak_targets,
        "promising_but_unstable_targets": promising_targets,
        "targets": targets,
    }


def summarize_broad_negative(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["aggregate"]
    suites = []
    for suite in payload["suites"]:
        suites.append(
            {
                "name": suite["name"],
                "tokens": int(suite["tokens"]),
                "ppl_ratio": float(suite["ppl_ratio"]),
            }
        )
    return {
        "name": name,
        "token_weighted_ppl_ratio": float(aggregate["token_weighted_ppl_ratio"]),
        "max_ppl_ratio": float(aggregate["max_ppl_ratio"]),
        "tokens": int(float(aggregate["tokens"])),
        "suite_count": int(aggregate["suite_count"]),
        "all_suites_negative": all(row["ppl_ratio"] > 1.0 for row in suites),
        "suites": suites,
    }


def summarize_runtime(payload: dict[str, Any]) -> dict[str, Any]:
    raw_cases = payload.get("cases", {})
    if isinstance(raw_cases, dict):
        cases = [{"name": name, **row} for name, row in raw_cases.items()]
    else:
        cases = list(raw_cases)
    result = {
        "hardware_counter_complete": bool(payload.get("claim_boundary", {}).get("hardware_counter_complete", False)),
        "dense_mean_ms": None,
        "mwg_mean_ms": {},
        "fused_like_observed": False,
    }
    for row in cases:
        name = str(row.get("name", ""))
        mean_ms = row.get("timing", {}).get("mean_ms")
        if name == "dense":
            result["dense_mean_ms"] = mean_ms
        elif name.startswith("mwg_"):
            result["mwg_mean_ms"][name] = mean_ms
        profiler = row.get("profiler_summary", {})
        operator = row.get("operator_summary", {})
        fused_like = operator.get("fused_like_op_observed") or profiler.get("fused_like_op_observed")
        if fused_like:
            result["fused_like_observed"] = True
    return result


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    base = Path(args.base)
    router = summarize_router(
        load_json(Path(args.broad_seed_sweep)),
        load_json(Path(args.leave_suiteout_seed_sweep)),
        load_json(Path(args.cv_summary)),
        args.strict_margin,
    )
    negatives = [
        summarize_broad_negative("always_patched_mwg", load_json(Path(args.always_patched_broad))),
        summarize_broad_negative("persistent_low_rank_r384", load_json(Path(args.persistent_broad))),
        summarize_broad_negative("persistent_low_rank_r384_lmce", load_json(Path(args.persistent_lmce_broad))),
    ]
    runtime = summarize_runtime(load_json(Path(args.runtime_probe)))
    stable = router["stable_positive_targets"] + router["weak_positive_targets"]
    return {
        "created_from": {
            "base": str(base),
            "broad_seed_sweep": str(args.broad_seed_sweep),
            "leave_suiteout_seed_sweep": str(args.leave_suiteout_seed_sweep),
            "cv_summary": str(args.cv_summary),
            "always_patched_broad": str(args.always_patched_broad),
            "persistent_broad": str(args.persistent_broad),
            "persistent_lmce_broad": str(args.persistent_lmce_broad),
            "runtime_probe": str(args.runtime_probe),
        },
        "paper_answer": (
            "A top-journal paper can center on scoped positive scenarios, but the current evidence supports "
            "bounded selective routing only. It does not support broad always-patched replacement or systems "
            "deployment claims yet."
        ),
        "publishable_positive_regime": {
            "algorithm": "MWG-EW with benefit-supervised token routing and dense fallback",
            "stable_or_weak_positive_targets": stable,
            "strongest_target": max(stable) if stable else None,
            "router": router,
        },
        "negative_boundaries": negatives,
        "systems_boundary": runtime,
        "readiness": {
            "ready_for_top_journal_broad_claim": False,
            "ready_for_scoped_positive_case_study": bool(stable),
            "missing_for_stronger_claim": [
                "broader independent benchmark families",
                "distribution-robust target 0.25 without unstable seeds",
                "stronger paired baselines beyond current persistent low-rank controls",
                "device hardware-counter or fused-kernel evidence",
            ],
        },
    }


def fmt_pct(value: float) -> str:
    return f"{value * 100.0:.2f}%"


def write_markdown(summary: dict[str, Any], path: Path) -> None:
    router = summary["publishable_positive_regime"]["router"]
    lines = [
        "# Publishable Positive Regime Boundary",
        "",
        summary["paper_answer"],
        "",
        "## Positive Scoped Regime",
        "",
        "Current defensible positive case: MWG-EW as a benefit-supervised, token-level selective router with dense fallback.",
        "",
        "| Target | Status | Broad actual | Broad mean ratio | Broad max | Leave-suite-out actual | Leave-suite-out mean ratio | Leave-suite-out max |",
        "|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in router["targets"]:
        broad = row["broad_seed_sweep"]
        leave = row["leave_suite_out"]
        lines.append(
            "| "
            f"{row['target_patch_fraction']:.2f} | {row['status']} | "
            f"{fmt_pct(broad['mean_actual_patch_token_fraction'])} | {broad['mean_ratio']:.4f} | {broad['max_ratio']:.4f} | "
            f"{fmt_pct(leave['mean_actual_patch_token_fraction'])} | {leave['mean_ratio']:.4f} | {leave['max_ratio']:.4f} |"
        )
    lines.extend(
        [
            "",
            "Interpretation: target 0.05 and 0.10 are the present stable positive window. Target 0.25 is promising but still unstable under leave-suite-out validation, and target 0.50 is negative.",
            "",
            "## Negative Boundaries",
            "",
            "| Boundary | Tokens | Token-weighted ratio | Max suite ratio |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in summary["negative_boundaries"]:
        lines.append(
            f"| {row['name']} | {row['tokens']:,} | {row['token_weighted_ppl_ratio']:.4f} | {row['max_ppl_ratio']:.4f} |"
        )
    systems = summary["systems_boundary"]
    lines.extend(
        [
            "",
            "## Systems Boundary",
            "",
            f"Hardware-counter complete: `{str(systems['hardware_counter_complete']).lower()}`.",
            f"Fused-like MWG op observed: `{str(systems['fused_like_observed']).lower()}`.",
            "",
            "## Readiness",
            "",
            f"Ready for scoped positive case study: `{str(summary['readiness']['ready_for_scoped_positive_case_study']).lower()}`.",
            f"Ready for broad top-journal claim: `{str(summary['readiness']['ready_for_top_journal_broad_claim']).lower()}`.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--strict-margin", type=float, default=0.002)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-md", type=Path, required=True)
    args = parser.parse_args()
    base = args.base
    args.broad_seed_sweep = base / "token_router_broad_seed_sweep_20260525T161810Z.summary.json"
    args.leave_suiteout_seed_sweep = base / "token_router_leave_suiteout_seed_sweep_20260525T171658Z.summary.json"
    args.cv_summary = base / "token_router_cv_20260525T131335Z.summary.json"
    args.always_patched_broad = base / "summary_broad_eval.json"
    args.persistent_broad = base / "summary_broad_eval_persistent_r384_20260525T115053Z.json"
    args.persistent_lmce_broad = base / "summary_broad_eval_persistent_lmce_20260526T024509Z.json"
    args.runtime_probe = base / "runtime_profiler_probe_20260525T192357Z.latest.json"
    return args


def main() -> None:
    args = parse_args()
    summary = build_summary(args)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_markdown(summary, args.out_md)


if __name__ == "__main__":
    main()
