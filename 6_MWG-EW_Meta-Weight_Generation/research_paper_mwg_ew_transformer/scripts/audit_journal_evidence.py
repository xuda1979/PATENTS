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


COUNTER_GEOMETRIES = ["probe_T128", "large_T512", "large_T1024", "large_T2048", "large_T4096"]
COUNTER_KERNEL_FIELDS = ["aic_total_cycles", "aic_main_mem_read_bw_mean",
                         "aic_main_mem_write_bw_mean", "l2_hit_rates_mean"]


def device_counter_gate(data, host_record):
    """Validate the parsed v1-vs-v4 device-counter record (2026-11-10).

    Confirms structural completeness of the counter tables only. Counter
    magnitudes come from the CANN profiler sqlite exports; this gate cannot
    authenticate the underlying hardware execution or the export pipeline.
    """
    if set(data.get("pairs", {})) != {f"{g}_{v}" for g in COUNTER_GEOMETRIES
                                      for v in ("v1", "v4")}:
        raise ValueError("device-counter pair coverage mismatch")
    if set(host_record.get("geometries", {})) != set(COUNTER_GEOMETRIES):
        raise ValueError("device-counter host record geometry coverage mismatch")
    rows = {}
    for g in COUNTER_GEOMETRIES:
        for v in ("v1", "v4"):
            pair = data["pairs"][f"{g}_{v}"]
            names = list(pair["kernels"])
            if names != [f"ephemeral_core_apply{'_v4' if v == 'v4' else ''}_kernel"]:
                raise ValueError(f"unexpected kernel name for {g}_{v}")
            k = pair["kernels"][names[0]]
            if k["occurrences"] != 50:
                raise ValueError(f"profiled-iteration count mismatch for {g}_{v}")
            for f in COUNTER_KERNEL_FIELDS:
                if k[f] is None:
                    raise ValueError(f"missing counter field {f} for {g}_{v}")
            rows[f"{g}_{v}"] = {f: k[f] for f in COUNTER_KERNEL_FIELDS}
        ht = data["pairs"][f"{g}_v1"]["host_timing_ms"]
        for key in ("v1_median", "v4_median", "speedup_v1_over_v4"):
            if not finite(ht[key]):
                raise ValueError(f"nonfinite host timing {key} for {g}")
        host_g = host_record["geometries"][g]
        for side, parsed_key in (("v1_host", "v1_median"), ("v4_host", "v4_median")):
            if abs(host_g[side]["median_ms"] - ht[parsed_key]) > 1e-9:
                raise ValueError(f"host/parsed timing disagreement for {g} {side}")
        rows[g] = {"v1_median_ms": ht["v1_median"], "v4_median_ms": ht["v4_median"],
                   "speedup_v1_over_v4": ht["speedup_v1_over_v4"]}
    return {"evidence_class": "parsed_cann_profile_export",
            "per_geometry": rows,
            "eligible_for_mechanism_claim": True,
            "eligible_for_trained_model_claim": False,
            "limitations": ["counters attribute traffic only; numerical outputs "
                            "not re-verified during profiling",
                            "raw CANN exports retained on ASI3, not in repository",
                            "L2-resident geometries; no residency-class claim"]}


def provenance_regeneration_gate(root, reg_dir, manifest):
    """Validate the 2026-11-10 4-seed quality regeneration (checkpoints + hashes).

    All report artifacts listed in the run manifest must be present with a
    matching sha256. Checkpoint binaries (~6 GB) are retained on the execution
    host (ASI2) and are verified against the manifest only when present
    locally; their absence is recorded, not treated as failure. The gate does
    not establish cross-seed dataset disjointness or end-to-end rerun identity.
    """
    local, remote_only = 0, 0
    for entry in manifest["artifacts"]:
        p = root / reg_dir / entry["path"]
        if not p.is_file():
            if entry["path"].endswith(".pt"):
                remote_only += 1
                continue
            raise ValueError(f"regeneration report artifact missing: {entry['path']}")
        if p.stat().st_size != entry["bytes"]:
            raise ValueError(f"regeneration artifact size mismatch: {entry['path']}")
        if file_hash(p) != entry["sha256"]:
            raise ValueError(f"regeneration artifact hash mismatch: {entry['path']}")
        local += 1
    per_seed_metrics = {}
    for seed in SEEDS:
        report = sorted((root / reg_dir / seed).glob("mwg_quality_distillation_*.json"))
        if len(report) != 1:
            raise ValueError(f"expected exactly one distillation report for {seed}")
        data = json.loads(report[0].read_text())
        per_seed_metrics[seed] = {arm: r["metrics"]["relative_mse"]
                                  for arm, r in data["results"].items()
                                  if "relative_mse" in r.get("metrics", {})}
    # Cross-check the regenerated cells against the canonical summary (same
    # family, tolerant to nondeterministic retraining noise).
    canonical = json.loads((root / QUALITY / "per_seed_results.json").read_text())
    compared, worst = 0, 0.0
    for seed in SEEDS:
        for arm, new_rmse in per_seed_metrics[seed].items():
            if arm in canonical[seed]:
                old_rmse = canonical[seed][arm]["relative_mse"]
                compared += 1
                worst = max(worst, abs(new_rmse - old_rmse))
    if compared < 24:
        raise ValueError("regeneration cross-check coverage too thin")
    return {"evidence_class": "regenerated_run_reports_manifest_verified",
            "manifest_artifacts": {"total": len(manifest["artifacts"]),
                                   "verified_local": local,
                                   "checkpoint_binaries_on_execution_host": remote_only},
            "per_seed_relative_mse": per_seed_metrics,
            "cross_check": {"cells_compared": compared, "max_abs_delta_vs_canonical": worst,
                            "tolerance": 0.02,
                            "within_tolerance": worst <= 0.02},
            "limitations": ["disjoint datasets across seeds still not established",
                            "checkpoint binaries verified by manifest only while "
                            "resident on ASI2; local copies absent",
                            "canonical family remains the citable record; regeneration "
                            "demonstrates recoverability of the provenance chain only"]}


FLOORS_PATH = Path("results/asi2_causal_quality_closing_20261110T155855Z/floors_and_constant_core.json")


def floors_and_constant_core_gate(root, data):
    """Validate the Theorem-1 floors + Proposition-1 constant-core eval.

    The evaluation (2026-11-11, ASI2 CPU) recomputes the five per-rank
    checkpoints' token and frozen-core FFN outputs on the regeneration eval
    activations.  Cross-check the recorded token relative MSE against the
    archived per-seed reports (tolerance well above any subset-vs-full
    mismatch); require the dynamic controller's frozen-core penalty to be
    small (not a quality claim, just a sanity bound on the evaluation).
    """
    rows = data["rows"]
    if len(rows) != 5 * 4:
        raise ValueError("floor eval missing per-seed rows")
    if data.get("calibration_split") != "train":
        raise ValueError("floor eval must calibrate on train splits")
    tail = {t["rank"]: t["tail_energy_relmse"] for t in data["tail_floors"]}
    if set(tail) != {384, 401, 512} or not all(finite(v) and 0 <= v for v in tail.values()):
        raise ValueError("invalid rank-tail floors")
    # Cross-check token relmse per (seed, arm) against the archived report.
    expected = {}
    for seed in SEEDS:
        report = sorted((root / "results/asi2_causal_quality_closing_20261110T155855Z" / seed)
                        .glob("mwg_quality_distillation_*.json"))
        if len(report) != 1:
            raise ValueError(f"expected one contraction report for {seed}")
        cells = json.loads(report[0].read_text())["results"]
        for arm in ["mwg_token_diag_core", "persistent_low_rank"]:
            for rank in RANKS:
                key = f"{arm}_r{rank}"
                if key in cells:
                    expected[f"{seed}/{key}"] = cells[key]["metrics"]["relative_mse"]
    compared, worst = 0, 0.0
    for row in rows:
        seed_name = row["seed"] if isinstance(row["seed"], str) else f"seed_{row['seed']}"
        key = f"{seed_name}/{row['name']}"
        if key in expected:
            compared += 1
            worst = max(worst, abs(row["token_relmse"] - expected[key]))
    if compared < 16:
        raise ValueError("floor eval cross-coverage too thin")
    for row in rows:
        for field in ("token_relmse", "constant_core_relmse", "mean_core_relmse",
                      "subspace_relmse", "rank_tail_relmse"):
            v = row[field]
            if not finite(v) or v < 0:
                raise ValueError(f"invalid floor-eval metric {field}")
    return {"evidence_class": "floors_and_constant_core_recomputed",
            "cross_check": {"cells_compared": compared, "max_abs_delta_vs_archive": worst},
            "tail_floors": data["tail_floors"],
            "rows": rows,
            "report_hash": data["report_hash"],
            "limitations": ["new evaluation of 2026-11-10 checkpoints on CPU; "
                            "no re-execution of training",
                            "constant-core calibration on train splits fixes "
                            "out-of-sample eval behavior only",
                            "rank-floor is an Eckart-Young lower bound on the "
                            "teacher output, not a matched subspace lower bound"]}


SWEEP_ARMS = ["dense", "persistent", "materialized", "fused", "fused_v4"]
SWEEP_GEOMETRIES = ["T128", "T512", "T1024", "T2048", "T4096"]


def complete_ffn_sweep_gate(root):
    """Gate the 2026-11-12 complete-FFN five-arm v4 sweep.

    The sweep (ASI3, five geometries) extends the kernel-only v1-vs-v4
    record to the complete FFN timing boundary.  Require all five
    geometries, all five arms, finite medians, and all four numerical
    validations passing at every geometry; cross-check the local
    sweep_summary against the sha256 recorded in the provenance digest.
    """
    sweep_dir = root / "results/asi3_complete_ffn_v4_sweep_20261112"
    summary = json.loads((sweep_dir / "sweep_summary.json").read_text())
    digest = json.loads((sweep_dir / "provenance_digest.json").read_text())
    local_sha = file_hash(sweep_dir / "sweep_summary.json")
    recorded = digest["remote_file_sha256"]["sweep_summary.json"].split(" ")[0]
    if local_sha != recorded:
        raise ValueError("sweep summary hash mismatch vs provenance digest")
    rows = []
    for entry in summary:
        geom = entry["geometry"]
        if geom not in SWEEP_GEOMETRIES:
            raise ValueError(f"unexpected geometry {geom}")
        for arm in SWEEP_ARMS:
            if not finite(entry[arm]) or entry[arm] <= 0:
                raise ValueError(f"invalid median for {geom}/{arm}")
        for name, passed in entry["validations"].items():
            if passed is not True:
                raise ValueError(f"validation {name} failed at {geom}")
        rows.append({"geometry": geom, "batch": entry["batch"], "seq": entry["seq"],
                     "tokens": entry["tokens"],
                     "dense_ms": entry["dense"], "persistent_ms": entry["persistent"],
                     "materialized_ms": entry["materialized"], "fused_ms": entry["fused"],
                     "fused_v4_ms": entry["fused_v4"],
                     "fused_over_fused_v4": entry["fused"] / entry["fused_v4"]})
    if [r["geometry"] for r in rows] != SWEEP_GEOMETRIES:
        raise ValueError("sweep geometries incomplete or out of order")
    return {"evidence_class": "complete_ffn_sweep_verified",
            "arm_set": SWEEP_ARMS,
            "rows": rows,
            "claim_boundary": digest["claim_boundary"],
            "limitations": digest["limitations"],
            "sha256_summary": local_sha}


PAIRED_CONTROL_PATH = Path("results/asi2_shuffled_paired_regen_20261112/shuffled_context_summary.json")
PAIRED_CELLS_PATH = Path("results/asi2_shuffled_paired_regen_20261112/paired_cells.json")


def paired_shuffled_control_gate(root):
    """Validate the 2026-11-12 same-run paired shuffled-context control.

    The run re-trains token and shuffled students in one process per seed
    on the regeneration's teacher and activation caches.  Require all 8
    shuffled summary rows (4 seeds x ranks 384/401) with finite metrics
    plus the 4 per-seed paired-cell records; contrasts are computed
    within the same run (token minus shuffled) so that run-level noise
    cancels.  Mixing cells from independent runs (regeneration token
    minus paired-run shuffled) would not be a valid contrast estimate.
    """
    data = json.loads((root / PAIRED_CONTROL_PATH).read_text())
    rows = data["rows"]
    if len(rows) != 8:
        raise ValueError("paired control requires 8 shuffled rows")
    by_key = {(r["seed"], r["rank"]): r["relative_mse"] for r in rows}
    if len(by_key) != 8:
        raise ValueError("paired control rows not unique per (seed, rank)")
    for v in by_key.values():
        if not finite(v) or v <= 0:
            raise ValueError("invalid paired-control relative MSE")
    cells = json.loads((root / PAIRED_CELLS_PATH).read_text())
    if cells.get("kind") != "paired_shuffled_control_cells_v1":
        raise ValueError("unexpected paired-cells record kind")
    cell_rows = cells["rows"]
    expected_seeds = {int(s.rsplit("_", 1)[1]) for s in SEEDS}
    if len(cell_rows) != 4 or {r["seed"] for r in cell_rows} != expected_seeds:
        raise ValueError("paired cells require exactly one row per seed")
    for r in cell_rows:
        for rank in (384, 401):
            if r[f"mwg_shuffled_diag_core_r{rank}"] != by_key[(r["seed"], rank)]:
                raise ValueError(f"summary shuffled cell diverges from paired run at seed {r['seed']}")
            if not (finite(r[f"mwg_token_diag_core_r{rank}"]) and r[f"mwg_token_diag_core_r{rank}"] > 0):
                raise ValueError("invalid paired-run token cell")
    contrasts = {}
    for rank in (384, 401):
        diffs = [r[f"mwg_token_diag_core_r{rank}"] - r[f"mwg_shuffled_diag_core_r{rank}"]
                 for r in sorted(cell_rows, key=lambda r: r["seed"])]
        m = mean(diffs)
        sd = stdev(diffs)
        half_width = T975_DF3 * sd / 2
        contrasts[rank] = {"mean": m, "sample_sd": sd, "per_seed": diffs,
                           "descriptive_t95_interval": [m - half_width, m + half_width]}
    # Replication check vs archived family contrasts (tolerance 0.0003
    # in the mean; archived: -0.000208 / -0.000196).
    archived = {384: -0.000208, 401: -0.000196}
    for rank, target in archived.items():
        if abs(contrasts[rank]["mean"] - target) > 3.0e-4:
            raise ValueError(f"paired control failed replication at rank {rank}: "
                             f"{contrasts[rank]['mean']:+.6f} vs archived {target:+.6f}")
    return {"evidence_class": "paired_shuffled_control_replicated",
            "contrasts": contrasts,
            "rows": rows,
            "limitations": ["same-run pairs only; cross-run pairing of independently "
                            "trained students is not a valid contrast estimate",
                            "two ranks re-run (384, 401); archived rank-512 contrast "
                            "not re-established",
                            "descriptive intervals over four seeds; no population claim"]}


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
    kp_v2 = Path("results/v4_multicore_benchmark_asi2_v2_20261008.json")
    kp_v3 = Path("results/v4_multicore_benchmark_asi3_v3_20261108.json")
    fp = Path("results/ASI3_arm4_decisive_20260828/key_results_SHIPPED.json")
    sources.extend([kp_v2, kp_v3, fp])
    four = read(fp)
    for key in ("probe_geometry", "largeT_geometry"):
        required = {"dense", "persistent", "materialized", "fused"} if key == "probe_geometry" else {"materialized", "fused"}
        if set(four[key]["median_ms"]) != required or not all(
                finite(v) and v > 0 for v in four[key]["median_ms"].values()):
            raise ValueError("incomplete or nonfinite four-arm timings")
    kernel_v2 = kernel_gate(read(kp_v2))  # superseded: NaN final error on ASI2 (2026-10-08)
    kernel = kernel_gate(read(kp_v3))     # current: hardened v3 harness re-run on ASI3 (2026-11-08)
    if kernel_v2["verdict"] != "FAIL":
        raise ValueError("superseded v2 failure record has been altered")
    dc_dir = Path("results/v4_device_counters_asi3_20261110")
    dc_parsed = dc_dir / "v4_device_counters_parsed.json"
    dc_host = dc_dir / "v4_profiling_host_record.json"
    sources.extend([dc_parsed, dc_host])
    counters = device_counter_gate(read(dc_parsed), read(dc_host))
    reg_dir = Path("results/asi2_causal_quality_closing_20261110T155855Z")
    reg_manifest_path = reg_dir / "artifact_manifest.json"
    reg_status_path = reg_dir / "status.json"
    sources.extend([reg_manifest_path, reg_status_path])
    reg_status = read(reg_status_path)
    if reg_status.get("state") != "completed" or reg_status.get("stage") != "complete":
        raise ValueError("quality regeneration run did not complete")
    regeneration = provenance_regeneration_gate(root, reg_dir, read(reg_manifest_path))
    floors = floors_and_constant_core_gate(root, read(FLOORS_PATH))
    sources.append(FLOORS_PATH)
    sweep = complete_ffn_sweep_gate(root)
    sweep_dir_rel = Path("results/asi3_complete_ffn_v4_sweep_20261112")
    sources.extend([sweep_dir_rel / "sweep_summary.json",
                    sweep_dir_rel / "provenance_digest.json"])
    paired_control = paired_shuffled_control_gate(root)
    sources.extend([PAIRED_CONTROL_PATH, PAIRED_CELLS_PATH])
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
            "v4_kernel_superseded": kernel_v2,
            "v4_device_counters": counters,
            "quality_provenance_regeneration": regeneration,
            "floors_and_constant_core": floors,
            "complete_ffn_sweep": sweep,
            "paired_shuffled_control": paired_control,
            "v1_four_arm": {key: {"median_ms": four[key]["median_ms"],
                                   "fused_over_materialized": four[key]["median_ms"]["fused"] /
                                       four[key]["median_ms"]["materialized"]}
                            for key in ["probe_geometry", "largeT_geometry"]},
            "optimizer_timing": {"rows": opt, "evidence_class": "archived_run_report_recomputed",
                                  "numerical_health": "UNKNOWN", "convergence_claim_eligible": False},
            "provenance": [{"path": str(p), "sha256": file_hash(root / p)} for p in sources],
            "submission_ready": False,
            "blocking_gaps": ["canonical quality record lacks per-run raw reports and split manifests; "
                              "regeneration closes recoverability but not dataset disjointness",
                              "no matched v4 trained-model end-to-end run; device-counter evidence "
                              "covers kernel traffic only",
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
    if summary["v4_kernel"]["verdict"] != "PASS":
        (folder / "journal_multicore_rows.tex").unlink(missing_ok=True)
        raise ValueError("refusing to emit multicore table from a failed gate")
    rows = [f"{r['T']} & ${r['v1_ms']:.4f}$ & ${r['v4_ms']:.4f}$ & ${r['ratio_v1_over_v4']:.2f}$ \\\\"
            for r in summary["v4_kernel"]["observed_timing_only"]]
    table("journal_multicore_rows.tex", "rrrr",
          "Tokens & v1 single-core op (ms) & v4 multicore op (ms) & Ratio", rows)
    floor_rows = summary["floors_and_constant_core"]["rows"]
    if not floor_rows:
        raise ValueError("refusing to emit floors table without rows")
    def agg(field, arm):
        vals = [r[field] for r in floor_rows if r["name"] == arm]
        if not vals:
            return float("nan")
        return mean(vals)
    display = {"mwg_token_diag_core": "Token controller", "persistent_low_rank": "Trained persistent"}
    order = [f"persistent_low_rank_r{r}" for r in RANKS] + [f"mwg_token_diag_core_r{r}" for r in RANKS if r != 512]
    lines = []
    for arm in order:
        rank = int(arm.rsplit("_r", 1)[1])
        name = display.get(arm.rsplit("_r", 1)[0], arm)
        lines.append(
            f"{name} & {rank} & ${agg('token_relmse', arm):.6f}$ & ${agg('constant_core_relmse', arm):.6f}$"
            f" & ${agg('mean_core_relmse', arm):.6f}$ & ${agg('subspace_relmse', arm):.6f}$"
            f" & ${agg('rank_tail_relmse', arm):.6f}$ \\\\"
        )
    table("journal_floors_rows.tex", "llrrrrr",
          "Model & Rank & Token ctl. & Const.-core & Mean-core & Subspace & Rank tail",
          lines)
    sweep_rows = summary["complete_ffn_sweep"]["rows"]
    if not sweep_rows:
        raise ValueError("refusing to emit complete-FFN sweep table without rows")
    lines = []
    for r in sweep_rows:
        lines.append(
            f"{r['tokens']} & ${r['dense_ms']:.3f}$ & ${r['persistent_ms']:.3f}$"
            f" & ${r['materialized_ms']:.3f}$ & ${r['fused_ms']:.3f}$ & ${r['fused_v4_ms']:.3f}$"
            f" & ${r['fused_over_fused_v4']:.2f}$ \\\\"
        )
    table("journal_complete_ffn_sweep_rows.tex", "rrrrrrr",
          "Tokens & Dense (ms) & Persistent (ms) & Materialized (ms) & Fused v1 (ms) & Fused v4 (ms) & v1/v4",
          lines)


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
