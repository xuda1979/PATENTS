#!/usr/bin/env python3
"""Extract parsed v4 device-counter evidence from the 10 CANN profiler exports.

The profile_v4_device_counters.py run (2026-11-10, ASI3) exported one
profiler tree per geometry-arm pair in chronological order:
  0: probe_T128_v1, 1: probe_T128_v4, 2: large_T512_v1, 3: large_T512_v4,
  4: large_T1024_v1, 5: large_T1024_v4, 6: large_T2048_v1, 7: large_T2048_v4,
  8: large_T4096_v1, 9: large_T4096_v4.
This script joins ge_summary (kernel names), metric_summary (aic/aiv
main-memory = HBM read/write bandwidth, cycles), and l2cache (hit rate)
per export, aggregates per kernel, and writes the parsed record.
"""

import glob
import json
import sqlite3
from pathlib import Path

ORDER = [
    "probe_T128_v1", "probe_T128_v4",
    "large_T512_v1", "large_T512_v4",
    "large_T1024_v1", "large_T1024_v4",
    "large_T2048_v1", "large_T2048_v4",
    "large_T4096_v1", "large_T4096_v4",
]


def aggregate_export(export_path):
    prof = sorted(glob.glob(str(Path(export_path) / "PROF_*")))
    if not prof:
        return {"error": "no PROF tree"}
    sd = sorted(glob.glob(str(Path(prof[0]) / "device_0" / "sqlite")))
    if not sd:
        return {"error": "no sqlite dir"}
    sd = sd[0]
    ge = sqlite3.connect(str(Path(sd) / "ai_core_op_summary.db"))
    ms = sqlite3.connect(str(Path(sd) / "metric_summary.db"))
    l2 = sqlite3.connect(str(Path(sd) / "l2cache.db"))

    out = {"kernels": {}}
    names = dict(ge.execute("SELECT task_id, op_name FROM ge_summary"))
    metrics = {
        r[0]: r
        for r in ms.execute(
            "SELECT task_id, aic_total_time, aic_total_cycles, "
            "aic_main_mem_read_bw, aic_main_mem_write_bw, "
            "aiv_total_time, aiv_total_cycles, "
            "aiv_main_mem_read_bw, aiv_main_mem_write_bw FROM MetricSummary"
        )
    }
    l2rows = {r[0]: r for r in l2.execute("SELECT task_id, hit_rate, victim_rate FROM L2CacheSummary")}
    for task_id, name in names.items():
        if "ephemeral" not in (name or "").lower():
            continue
        m = metrics.get(task_id)
        if m is None:
            continue
        rec = out["kernels"].setdefault(name, {
            "occurrences": 0,
            "aic_total_time_us": 0.0, "aic_total_cycles": 0.0,
            "aic_main_mem_read_bw": [], "aic_main_mem_write_bw": [],
            "aiv_total_time_us": 0.0, "aiv_total_cycles": 0.0,
            "aiv_main_mem_read_bw": [], "aiv_main_mem_write_bw": [],
            "l2_hit_rates": [], "l2_victim_rates": [],
        })
        rec["occurrences"] += 1
        rec["aic_total_time_us"] += m[1] or 0
        rec["aic_total_cycles"] += m[2] or 0
        if m[3]: rec["aic_main_mem_read_bw"].append(m[3])
        if m[4]: rec["aic_main_mem_write_bw"].append(m[4])
        rec["aiv_total_time_us"] += m[5] or 0
        rec["aiv_total_cycles"] += m[6] or 0
        if m[7]: rec["aiv_main_mem_read_bw"].append(m[7])
        if m[8]: rec["aiv_main_mem_write_bw"].append(m[8])
        lr = l2rows.get(task_id)
        if lr:
            if lr[1] is not None: rec["l2_hit_rates"].append(lr[1])
            if lr[2] is not None: rec["l2_victim_rates"].append(lr[2])
    ge.close(); ms.close(); l2.close()
    for name, rec in out["kernels"].items():
        for key in ("aic_main_mem_read_bw", "aic_main_mem_write_bw",
                    "aiv_main_mem_read_bw", "aiv_main_mem_write_bw",
                    "l2_hit_rates", "l2_victim_rates"):
            vals = rec.pop(key)
            rec[key + "_mean"] = (sum(vals) / len(vals)) if vals else None
            rec[key + "_n"] = len(vals)
    return out


def main():
    exports = sorted(glob.glob("/root/work/export_only_prof_dir/*_ascend_pt"))
    assert len(exports) == len(ORDER), f"expected {len(ORDER)} exports, got {len(exports)}"
    parsed = {
        "schema_version": 1,
        "run": "v4 device-counter profiling on ASI3, 2026-11-10T17:16Z",
        "units": {"bw": "GB/s per CANN metric_summary convention", "time": "us", "hit_rate": "fraction"},
        "pairs": {},
    }
    host = {}
    hr = Path("/root/work/v4_device_counters_20261110.json")
    if hr.is_file():
        host = json.loads(hr.read_text()).get("geometries", {})
    for label, exp in zip(ORDER, exports):
        agg = aggregate_export(exp)
        geom = label.rsplit("_", 1)[0]
        entry = parsed["pairs"].setdefault(label, {"geometry": geom})
        entry.update(agg)
        if geom in host:
            entry["host_timing_ms"] = {
                "v1_median": host[geom].get("v1_host", {}).get("median_ms"),
                "v4_median": host[geom].get("v4_host", {}).get("median_ms"),
                "speedup_v1_over_v4": host[geom].get("speedup_v1_over_v4"),
                "max_abs_diff": host[geom].get("max_abs_diff"),
            }
    out_path = "/root/work/v4_device_counters_parsed_20261110.json"
    Path(out_path).write_text(json.dumps(parsed, indent=1))
    print("wrote", out_path)
    for label in ORDER:
        entry = parsed["pairs"].get(label, {})
        for kern, rec in entry.get("kernels", {}).items():
            print(
                f"{label:20s} {kern[:40]:40s} occ={rec['occurrences']:3d} "
                f"aic_r_bw={rec['aic_main_mem_read_bw_mean'] and round(rec['aic_main_mem_read_bw_mean'],3)} "
                f"aic_w_bw={rec['aic_main_mem_write_bw_mean'] and round(rec['aic_main_mem_write_bw_mean'],3)} "
                f"aiv_r_bw={rec['aiv_main_mem_read_bw_mean'] and round(rec['aiv_main_mem_read_bw_mean'],3)} "
                f"aiv_w_bw={rec['aiv_main_mem_write_bw_mean'] and round(rec['aiv_main_mem_write_bw_mean'],3)} "
                f"l2_hit={rec['l2_hit_rates_mean'] and round(rec['l2_hit_rates_mean'],5)}"
            )


if __name__ == "__main__":
    main()
