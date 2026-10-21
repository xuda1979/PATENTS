"""Aggregate repeated ASI2 MWG-EW benchmark runs.

This script consumes the per-run JSON files written by
``mwg_transformer_ASI3_benchmark.py`` with ``--env-label ASI2`` and creates a
compact reliability/scaling summary for paper tables. It intentionally uses
only the Python standard library so it can run in constrained Huanxin
environments.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


def mean_std(values: list[float]) -> dict[str, float | int | None]:
    clean = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    if not clean:
        return {"n": 0, "mean": None, "std": None, "min": None, "max": None}
    return {
        "n": len(clean),
        "mean": round(statistics.mean(clean), 4),
        "std": round(statistics.stdev(clean), 4) if len(clean) > 1 else 0.0,
        "min": round(min(clean), 4),
        "max": round(max(clean), 4),
    }


def get_metric(payload: dict[str, Any], method: str, metric: str) -> float | None:
    row = payload["results"].get(method)
    if row is None:
        return None
    if metric in {"forward_ms", "train_ms", "allreduce_ms"}:
        key = metric.removesuffix("_ms")
        timing = row.get(key)
        return None if timing is None else timing.get("mean_ms")
    return row.get(metric)


def group_key(payload: dict[str, Any]) -> str:
    env = payload.get("env", {})
    config = payload.get("config", {})
    devices = env.get("ascend_rt_visible_devices", "")
    return f"world{env.get('world_size')}_devices{devices}_preset{config.get('preset')}"


def aggregate(paths: list[Path]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["_source_path"] = str(path)
        groups[group_key(payload)].append(payload)

    summary: dict[str, Any] = {"groups": {}}
    metrics = [
        "forward_ms",
        "train_ms",
        "allreduce_ms",
        "train_speedup_x",
        "forward_speedup_x",
        "traffic_reduction_x",
        "communication_reduction_x",
        "train_tokens_per_s",
    ]

    for key, runs in sorted(groups.items()):
        first = runs[0]
        methods = ["dense"] + [name for name in first["results"] if name.startswith("mwg_r")]
        methods = ["dense"] + sorted(methods[1:], key=lambda item: int(item.split("r", 1)[1]))
        group: dict[str, Any] = {
            "n_runs": len(runs),
            "sources": [run["_source_path"] for run in runs],
            "env": {
                "world_size": first.get("env", {}).get("world_size"),
                "visible_devices": first.get("env", {}).get("ascend_rt_visible_devices"),
                "backend": first.get("env", {}).get("backend"),
                "device_type": first.get("env", {}).get("device_type"),
                "env_label": first.get("env_label", "ASI2"),
            },
            "config": first.get("config", {}),
            "methods": {},
        }
        for method in methods:
            group["methods"][method] = {
                metric: mean_std(
                    [
                        value
                        for value in (get_metric(run, method, metric) for run in runs)
                        if value is not None
                    ]
                )
                for metric in metrics
            }
            row = first["results"].get(method, {})
            for stable in ("parameter_mib", "descriptor_mib", "communication_mib", "rank"):
                if stable in row:
                    group["methods"][method][stable] = row[stable]
        summary["groups"][key] = group
    return summary


def write_markdown(summary: dict[str, Any], path: Path) -> None:
    lines = [
        "# ASI2 MWG-EW Reliability and Scaling Summary",
        "",
        "| Group | Runs | Method | Train ms mean | Train ms std | Train speedup mean | AllReduce ms mean | Traffic reduction | Train tok/s mean |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for group_name, group in summary["groups"].items():
        for method, metrics in group["methods"].items():
            train = metrics["train_ms"]
            speedup = metrics["train_speedup_x"]
            allreduce = metrics["allreduce_ms"]
            traffic = metrics["traffic_reduction_x"]
            tok = metrics["train_tokens_per_s"]
            lines.append(
                "| "
                + " | ".join(
                    [
                        group_name,
                        str(group["n_runs"]),
                        method,
                        str(train["mean"]),
                        str(train["std"]),
                        str(speedup["mean"]),
                        str(allreduce["mean"]),
                        str(traffic["mean"]),
                        str(tok["mean"]),
                    ]
                )
                + " |"
            )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--glob", action="append", default=[])
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    args = parser.parse_args()

    paths: list[Path] = []
    for pattern in args.glob:
        paths.extend(Path(item) for item in sorted(glob.glob(pattern)))
    if not paths:
        raise SystemExit("no input files matched")

    summary = aggregate(paths)
    Path(args.out_json).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_markdown(summary, Path(args.out_md))


if __name__ == "__main__":
    main()
