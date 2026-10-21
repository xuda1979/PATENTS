"""Aggregate MWG-EW four-arm benchmark reports without upgrading claims.

The summarizer accepts files or directories.  It recognizes only reports with
the explicit four-arm schema and keeps ordinary timing, compiled-op execution,
and parsed hardware-counter evidence as separate levels of evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from mwg_four_arm_lifetime_benchmark import ALL_ARMS, SCHEMA_VERSION


SUMMARY_SCHEMA_VERSION = "mwg-four-arm-lifetime-summary-v1"
CONFIG_KEYS = (
    "d",
    "m",
    "rank",
    "controller_hidden",
    "batch",
    "seq",
    "amplitude",
    "dtype",
    "seed",
)


def utc_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def discover(paths: Iterable[str | Path]) -> list[Path]:
    discovered: list[Path] = []
    for raw in paths:
        path = Path(raw).expanduser()
        if path.is_dir():
            discovered.extend(sorted(path.rglob("*.json")))
        elif path.is_file():
            discovered.append(path)
    return list(dict.fromkeys(item.resolve() for item in discovered))


def load_reports(
    paths: Iterable[str | Path],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    reports: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for path in discover(paths):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            rejected.append({"path": str(path), "reason": f"parse_error:{exc}"})
            continue
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != SCHEMA_VERSION
        ):
            continue
        payload = dict(payload)
        payload["_source_path"] = str(path)
        reports.append(payload)
    return reports, rejected


def config_projection(report: Mapping[str, Any]) -> dict[str, Any]:
    config = report.get("config", {})
    return {key: config.get(key) for key in CONFIG_KEYS}


def config_id(config: Mapping[str, Any]) -> str:
    encoded = json.dumps(dict(config), sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()[:16]


def aggregate_numbers(values: Sequence[float]) -> dict[str, Any]:
    return {
        "n": len(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
        "std": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def valid_fused_contract(report: Mapping[str, Any]) -> bool:
    contract = report.get("backend_contract", {})
    boundary = report.get("claim_boundary", {})
    return bool(
        isinstance(contract, Mapping)
        and contract.get("validated") is True
        and contract.get("arm4_executed") is True
        and contract.get("workspace_bytes") == 0
        and contract.get("global_core_output") is False
        and boundary.get("arm4_execution_observed") is True
    )


def valid_pair_equivalence(report: Mapping[str, Any]) -> bool:
    validation = report.get("validations", {}).get("materialized_vs_fused", {})
    return isinstance(validation, Mapping) and validation.get("passed") is True


PUBLICATION_COUNTER_FIELDS = (
    "hbm_read_bytes",
    "hbm_write_bytes",
    "l2_read_bytes",
    "l2_write_bytes",
    "core_global_store_bytes",
    "kernel_latency_ms",
    "achieved_flop_per_s",
    "occupancy_percent",
    "energy_joules",
    "peak_temporary_bytes",
)


def validated_counter(record: Any) -> bool:
    """Require parsed publication-grade fields, not merely an msprof run."""

    return bool(
        isinstance(record, Mapping)
        and record.get("validated") is True
        and record.get("publication_complete") is True
        and record.get("source") == "msprof"
        and int(record.get("sample_count", 0)) >= 5
        and all(
            isinstance(record.get(field), (int, float))
            for field in PUBLICATION_COUNTER_FIELDS
        )
    )


def counter_pairs(reports: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return only genuinely parsed, matched materialized/fused counters."""

    by_pair: dict[str, dict[str, Mapping[str, Any]]] = {}
    for report in reports:
        pair_id = str(report.get("counter_pair_id", ""))
        if not pair_id:
            continue
        for arm in ("materialized", "fused"):
            arm_record = report.get("arms", {}).get(arm)
            if not isinstance(arm_record, Mapping):
                continue
            counters = arm_record.get("hardware_counters")
            if validated_counter(counters):
                by_pair.setdefault(pair_id, {})[arm] = counters
    pairs: list[dict[str, Any]] = []
    for pair_id, arms in sorted(by_pair.items()):
        if set(arms) != {"materialized", "fused"}:
            continue
        materialized = arms["materialized"]
        fused = arms["fused"]
        materialized_hbm = float(materialized["hbm_read_bytes"]) + float(
            materialized["hbm_write_bytes"]
        )
        fused_hbm = float(fused["hbm_read_bytes"]) + float(fused["hbm_write_bytes"])
        pairs.append(
            {
                "counter_pair_id": pair_id,
                "materialized_hbm_bytes": materialized_hbm,
                "fused_hbm_bytes": fused_hbm,
                "hbm_delta_bytes": materialized_hbm - fused_hbm,
                "fused_reduces_hbm": fused_hbm < materialized_hbm,
                "materialized_core_global_store_bytes": materialized[
                    "core_global_store_bytes"
                ],
                "fused_core_global_store_bytes": fused["core_global_store_bytes"],
                "core_store_contract_observed": bool(
                    float(materialized["core_global_store_bytes"]) > 0
                    and float(fused["core_global_store_bytes"]) == 0
                ),
            }
        )
    return pairs


def summarize_configuration(
    config: Mapping[str, Any], reports: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    arm_timings: dict[str, Any] = {}
    observed_arms: set[str] = set()
    for arm in ALL_ARMS:
        medians: list[float] = []
        source_reports: list[str] = []
        for report in reports:
            record = report.get("arms", {}).get(arm)
            if not isinstance(record, Mapping):
                continue
            median = record.get("timing", {}).get("median_ms")
            if isinstance(median, (int, float)) and math.isfinite(float(median)):
                medians.append(float(median))
                source_reports.append(report["_source_path"])
                observed_arms.add(arm)
        if medians:
            arm_timings[arm] = {
                "median_ms_across_reports": aggregate_numbers(medians),
                "source_reports": source_reports,
            }

    ratios: dict[str, float] = {}
    central = {
        arm: record["median_ms_across_reports"]["median"]
        for arm, record in arm_timings.items()
    }
    if "dense" in central:
        for arm in ("persistent", "materialized", "fused"):
            if arm in central and central[arm] > 0:
                ratios[f"{arm}_speedup_vs_dense"] = central["dense"] / central[arm]
    if "materialized" in central and "fused" in central and central["fused"] > 0:
        ratios["fused_speedup_vs_materialized"] = (
            central["materialized"] / central["fused"]
        )

    contract_reports = [
        report["_source_path"] for report in reports if valid_fused_contract(report)
    ]
    equivalent_reports = [
        report["_source_path"] for report in reports if valid_pair_equivalence(report)
    ]
    scheduled_counter_metrics = sorted(
        {
            str(report.get("counter_metric"))
            for report in reports
            if report.get("counter_metric")
        }
    )
    parsed_pairs = counter_pairs(reports)
    all_pairs_reduce_hbm = len(parsed_pairs) >= 3 and all(
        pair["fused_reduces_hbm"] and pair["core_store_contract_observed"]
        for pair in parsed_pairs
    )
    required_arms_present = set(ALL_ARMS).issubset(observed_arms)
    static_and_numeric = bool(contract_reports) and bool(equivalent_reports)
    claim_ready = required_arms_present and static_and_numeric and all_pairs_reduce_hbm

    gaps: list[str] = []
    if not required_arms_present:
        gaps.append("one or more of the four arms have no timing report")
    if not contract_reports:
        gaps.append("no validated compiled no-store contract execution")
    if not equivalent_reports:
        gaps.append("no passing materialized-versus-fused output equivalence report")
    if not parsed_pairs:
        gaps.append("no matched publication-complete parsed HBM/L2 counter pair")
    elif len(parsed_pairs) < 3:
        gaps.append("fewer than three matched publication-complete counter repeats")
    elif not all_pairs_reduce_hbm:
        gaps.append("parsed counters do not consistently show lower fused HBM traffic")

    return {
        "config": dict(config),
        "report_count": len(reports),
        "observed_arms": sorted(observed_arms),
        "arm_timings": arm_timings,
        "timing_ratios": ratios,
        "evidence": {
            "validated_fused_contract_reports": contract_reports,
            "passing_pair_equivalence_reports": equivalent_reports,
            "scheduled_counter_metrics": scheduled_counter_metrics,
            "parsed_counter_pairs": parsed_pairs,
            "counter_trace_names_are_not_parsed_counters": True,
        },
        "claim_status": {
            "arm4_execution_observed": bool(contract_reports),
            "hardware_counter_complete": len(parsed_pairs) >= 3,
            "no_store_claim_ready": claim_ready,
            "open_gaps": gaps,
        },
    }


def summarize_reports(reports: Sequence[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, tuple[dict[str, Any], list[dict[str, Any]]]] = {}
    for report in reports:
        config = config_projection(report)
        identifier = config_id(config)
        grouped.setdefault(identifier, (config, []))[1].append(report)
    configurations = {
        identifier: summarize_configuration(config, group)
        for identifier, (config, group) in sorted(grouped.items())
    }
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "created_at": utc_tag(),
        "input_report_count": len(reports),
        "configurations": configurations,
        "global_claim_boundary": {
            "no_store_claim_ready": bool(configurations)
            and all(
                item["claim_status"]["no_store_claim_ready"]
                for item in configurations.values()
            ),
            "timing_or_a_profiler_directory_alone_is_not_hardware_counter_evidence": True,
        },
    }


def render_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# MWG-EW Four-Arm Lifetime Summary",
        "",
        f"Created: `{summary['created_at']}`",
        f"Input reports: `{summary['input_report_count']}`",
        f"Global no-store claim ready: `{str(summary['global_claim_boundary']['no_store_claim_ready']).lower()}`",
        "",
    ]
    for identifier, item in summary.get("configurations", {}).items():
        config = item["config"]
        lines.extend(
            [
                f"## Configuration `{identifier}`",
                "",
                (
                    f"`d={config['d']}, m={config['m']}, r={config['rank']}, "
                    f"B={config['batch']}, S={config['seq']}, dtype={config['dtype']}`"
                ),
                "",
                "| Arm | Reports | Median latency (ms) |",
                "|---|---:|---:|",
            ]
        )
        for arm in ALL_ARMS:
            timing = item["arm_timings"].get(arm)
            if timing:
                agg = timing["median_ms_across_reports"]
                lines.append(f"| {arm} | {agg['n']} | {agg['median']:.6f} |")
        lines.extend(
            [
                "",
                f"Arm 4 execution observed: `{str(item['claim_status']['arm4_execution_observed']).lower()}`",
                f"Hardware counters complete: `{str(item['claim_status']['hardware_counter_complete']).lower()}`",
                f"No-store claim ready: `{str(item['claim_status']['no_store_claim_ready']).lower()}`",
                "",
            ]
        )
        if item["claim_status"]["open_gaps"]:
            lines.append("Open gaps:")
            lines.append("")
            for gap in item["claim_status"]["open_gaps"]:
                lines.append(f"- {gap}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="report files or directories")
    parser.add_argument("--output", required=True)
    parser.add_argument("--markdown")
    parser.add_argument(
        "--strict", action="store_true", help="fail when no valid reports are found"
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    reports, rejected = load_reports(args.inputs)
    if args.strict and not reports:
        raise SystemExit("no valid four-arm reports found")
    summary = summarize_reports(reports)
    summary["rejected_inputs"] = rejected
    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    markdown = (
        Path(args.markdown).expanduser() if args.markdown else output.with_suffix(".md")
    )
    markdown.write_text(render_markdown(summary), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "markdown": str(markdown),
                "reports": len(reports),
                "no_store_claim_ready": summary["global_claim_boundary"][
                    "no_store_claim_ready"
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
