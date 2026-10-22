"""Analytic deployment-regime map for ephemeral low-rank FFN operands.

The quantities emitted here are logical/scheduled payload counts, not hardware
counter measurements.  In particular, cache hits, allocator traffic, compiler
fusion, and writeback policy can make physical HBM traffic differ from these
counts.  The JSON metadata and every output row preserve that claim boundary.

Groups are isolated by batch example: ``n = B * ceil(S / q)``.  This is the
appropriate default for a causal, batch-invariant controller because unrelated
examples may not share a generated core.  Consequently cached decode has
``S=q=1`` and one core per active sequence.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


FORMAT_VERSION = 2
VALID_WORKLOADS = ("prefill", "decode", "training")
DTYPE_BYTES = {"fp16": 2, "bf16": 2, "fp32": 4}


def parse_ints(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def parse_strings(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def ceil_div(numerator: int, denominator: int) -> int:
    if numerator < 0 or denominator <= 0:
        raise ValueError("ceil_div requires numerator >= 0 and denominator > 0")
    return (numerator + denominator - 1) // denominator


def group_count(batch: int, seq: int, reuse_group: int) -> int:
    """Return batch-isolated causal group count ``B * ceil(S / q)``."""
    if batch < 1:
        raise ValueError("batch must be at least 1")
    if seq < 1:
        raise ValueError("sequence length must be at least 1")
    if not 1 <= reuse_group <= seq:
        raise ValueError("reuse group q must satisfy 1 <= q <= S")
    return batch * ceil_div(seq, reuse_group)


def persistent_factor_elements(d: int, m: int, rank: int) -> int:
    return 3 * rank * (d + m)


def dense_weight_elements(d: int, m: int) -> int:
    return 3 * d * m


def diagonal_core_elements(groups: int, rank: int) -> int:
    return 3 * groups * rank


def full_factor_elements(d: int, m: int, rank: int, groups: int) -> int:
    return 3 * groups * rank * (d + m)


def canonical_controller_elements(d: int, rank: int, hidden: int) -> int:
    """Parameter elements in ``Linear(d,h) -> SiLU -> Linear(h,3r)``."""
    if min(d, rank, hidden) < 1:
        raise ValueError("controller dimensions must be positive")
    output = 3 * rank
    return d * hidden + hidden + hidden * output + output


def full_factor_gamma(d: int, m: int, rank: int) -> float:
    if min(d, m, rank) < 1:
        raise ValueError("d, m, and rank must be positive")
    return rank * (d + m) / (d * m)


def full_factor_q_min(d: int, m: int, rank: int, batch: int, seq: int) -> int | None:
    """Exact smallest within-example ``q`` giving strict base-payload saving.

    The generated full-factor ratio is
    ``B * ceil(S/q) * rank * (d+m) / (d*m)``.  ``None`` means that even one
    group per example cannot be strictly smaller than the dense weight payload.
    """
    if batch < 1 or seq < 1:
        raise ValueError("batch and sequence length must be positive")
    descriptor_per_group = rank * (d + m)
    dense_projection = d * m
    if descriptor_per_group >= dense_projection:
        return None
    # Largest integer n satisfying n * descriptor_per_group < dense_projection.
    # Integer arithmetic avoids a floating-point boundary error when 1/gamma
    # is close to an integer.
    max_total_groups = (dense_projection - 1) // descriptor_per_group
    max_groups_per_example = max_total_groups // batch
    if max_groups_per_example < 1:
        return None
    candidate = ceil_div(seq, max_groups_per_example)
    return candidate if candidate <= seq else None


@dataclass(frozen=True)
class WorkloadCase:
    workload: str
    batch: int
    seq: int
    reuse_group: int

    def validate(self) -> None:
        if self.workload not in VALID_WORKLOADS:
            raise ValueError(f"unknown workload: {self.workload}")
        if self.workload == "decode" and (self.seq != 1 or self.reuse_group != 1):
            raise ValueError("cached decode requires S=1 and q=1")
        if self.workload == "prefill" and self.seq <= 1:
            raise ValueError("prefill requires S>1")
        group_count(self.batch, self.seq, self.reuse_group)


@dataclass(frozen=True)
class AccountingConfig:
    d: int
    m: int
    rank: int
    controller_hidden: int
    factor_element_bytes: int = 2
    controller_element_bytes: int = 4
    source_element_bytes: int = 2
    factor_loads: int = 1
    controller_loads: int = 1
    source_passes: int = 1
    controller_param_elements: int | None = None

    def validate(self) -> None:
        if min(self.d, self.m, self.rank, self.controller_hidden) < 1:
            raise ValueError("model and controller dimensions must be positive")
        if min(self.factor_element_bytes, self.controller_element_bytes, self.source_element_bytes) < 1:
            raise ValueError("element widths must be positive")
        if min(self.factor_loads, self.controller_loads, self.source_passes) < 0:
            raise ValueError("load/pass multiplicities must be nonnegative")
        if self.controller_param_elements is not None and self.controller_param_elements < 0:
            raise ValueError("controller_param_elements must be nonnegative")

    @property
    def resolved_controller_elements(self) -> int:
        if self.controller_param_elements is not None:
            return self.controller_param_elements
        return canonical_controller_elements(self.d, self.rank, self.controller_hidden)


def compute_row(case: WorkloadCase, config: AccountingConfig) -> dict[str, Any]:
    """Compute one flat row suitable for both JSON and CSV serialization."""
    case.validate()
    config.validate()

    tokens = case.batch * case.seq
    groups = group_count(case.batch, case.seq, case.reuse_group)
    dense_elements = dense_weight_elements(config.d, config.m)
    dense_bytes = dense_elements * config.factor_element_bytes

    factor_elements = persistent_factor_elements(config.d, config.m, config.rank)
    factor_bytes = factor_elements * config.factor_element_bytes
    scheduled_factor_bytes = config.factor_loads * factor_bytes

    controller_elements = config.resolved_controller_elements
    controller_bytes = controller_elements * config.controller_element_bytes
    scheduled_controller_bytes = config.controller_loads * controller_bytes

    # The default ledger conservatively charges one complete source-state pass
    # per configured pass.  A measured implementation may read only group
    # anchors; that alternative must be reported as a different source policy.
    source_elements = config.source_passes * tokens * config.d
    source_bytes = source_elements * config.source_element_bytes

    core_elements = diagonal_core_elements(groups, config.rank)
    core_bytes = core_elements * config.factor_element_bytes
    core_store_bytes = core_bytes
    core_reload_bytes = core_bytes

    diagonal_base_bytes = factor_bytes + core_bytes
    # Generated scratch values are cardinality, not global-memory transfers.
    # This is a partial global ledger: common activation transfers are omitted.
    diagonal_no_store_bytes = scheduled_factor_bytes + scheduled_controller_bytes + source_bytes
    diagonal_materialized_bytes = diagonal_no_store_bytes + core_store_bytes + core_reload_bytes

    factor_descriptor_elements = full_factor_elements(config.d, config.m, config.rank, groups)
    factor_descriptor_bytes = factor_descriptor_elements * config.factor_element_bytes
    factor_store_bytes = factor_descriptor_bytes
    factor_reload_bytes = factor_descriptor_bytes
    full_factor_no_store_bytes = scheduled_controller_bytes + source_bytes
    full_factor_materialized_bytes = full_factor_no_store_bytes + factor_store_bytes + factor_reload_bytes

    q_min = full_factor_q_min(config.d, config.m, config.rank, case.batch, case.seq)

    return {
        "workload": case.workload,
        "d": config.d,
        "m": config.m,
        "rank": config.rank,
        "batch": case.batch,
        "seq": case.seq,
        "tokens": tokens,
        "reuse_group_q": case.reuse_group,
        "groups_per_example": ceil_div(case.seq, case.reuse_group),
        "group_count": groups,
        "grouping_policy": "batch_isolated_B_times_ceil_S_over_q",
        "factor_element_bytes": config.factor_element_bytes,
        "controller_element_bytes": config.controller_element_bytes,
        "source_element_bytes": config.source_element_bytes,
        "factor_loads": config.factor_loads,
        "controller_loads": config.controller_loads,
        "source_passes": config.source_passes,
        "dense_weight_elements": dense_elements,
        "dense_weight_bytes": dense_bytes,
        "persistent_factor_elements": factor_elements,
        "persistent_factor_bytes": factor_bytes,
        "scheduled_persistent_factor_bytes": scheduled_factor_bytes,
        "controller_hidden": config.controller_hidden,
        "controller_parameter_elements": controller_elements,
        "controller_parameter_bytes": controller_bytes,
        "scheduled_controller_bytes": scheduled_controller_bytes,
        "source_state_elements": source_elements,
        "source_state_bytes": source_bytes,
        "diagonal_core_generated_elements": core_elements,
        "diagonal_core_generated_bytes": core_bytes,
        "diagonal_core_materialization_store_bytes": core_store_bytes,
        "diagonal_core_materialization_reload_bytes": core_reload_bytes,
        "diagonal_core_base_logical_bytes": diagonal_base_bytes,
        "diagonal_core_base_ratio_vs_dense": diagonal_base_bytes / dense_bytes,
        "diagonal_core_scheduled_no_store_bytes": diagonal_no_store_bytes,
        "diagonal_core_scheduled_no_store_ratio_vs_dense": diagonal_no_store_bytes / dense_bytes,
        "diagonal_core_scheduled_materialized_bytes": diagonal_materialized_bytes,
        "diagonal_core_scheduled_materialized_ratio_vs_dense": diagonal_materialized_bytes / dense_bytes,
        "full_factor_generated_elements": factor_descriptor_elements,
        "full_factor_generated_bytes": factor_descriptor_bytes,
        "full_factor_materialization_store_bytes": factor_store_bytes,
        "full_factor_materialization_reload_bytes": factor_reload_bytes,
        "full_factor_base_logical_bytes": factor_descriptor_bytes,
        "full_factor_base_ratio_vs_dense": factor_descriptor_bytes / dense_bytes,
        "full_factor_scheduled_no_store_bytes": full_factor_no_store_bytes,
        "full_factor_scheduled_no_store_ratio_vs_dense": full_factor_no_store_bytes / dense_bytes,
        "full_factor_scheduled_materialized_bytes": full_factor_materialized_bytes,
        "full_factor_scheduled_materialized_ratio_vs_dense": full_factor_materialized_bytes / dense_bytes,
        "full_factor_gamma_single_group": full_factor_gamma(config.d, config.m, config.rank),
        "full_factor_q_min_strict_base_saving": q_min,
        "full_factor_current_q_strict_base_saving": factor_descriptor_bytes < dense_bytes,
        "physical_hbm_counter_measurement": False,
        "scheduled_ledger_scope": "partial_global_transfers_excluding_common_activations",
        "diagonal_core_removable_global_bytes": 2 * core_bytes,
    }


def build_workload_cases(
    modes: Iterable[str],
    *,
    prefill_batches: Iterable[int],
    prefill_seqs: Iterable[int],
    prefill_qs: Iterable[int],
    decode_batches: Iterable[int],
    training_batches: Iterable[int],
    training_seqs: Iterable[int],
    training_qs: Iterable[int],
) -> list[WorkloadCase]:
    requested = list(modes)
    unknown = sorted(set(requested) - set(VALID_WORKLOADS))
    if unknown:
        raise ValueError(f"unknown workloads: {unknown}")
    cases: list[WorkloadCase] = []
    if "prefill" in requested:
        cases.extend(
            WorkloadCase("prefill", batch, seq, reuse_group)
            for batch in prefill_batches
            for seq in prefill_seqs
            for reuse_group in prefill_qs
        )
    if "decode" in requested:
        cases.extend(WorkloadCase("decode", batch, 1, 1) for batch in decode_batches)
    if "training" in requested:
        cases.extend(
            WorkloadCase("training", batch, seq, reuse_group)
            for batch in training_batches
            for seq in training_seqs
            for reuse_group in training_qs
        )
    for case in cases:
        case.validate()
    return cases


def build_payload(rows: list[dict[str, Any]], args: argparse.Namespace | None = None) -> dict[str, Any]:
    return {
        "format_version": FORMAT_VERSION,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "claim_boundary": (
            "Logical and scheduled payload accounting only; no row is a physical HBM, "
            "cache-traffic, energy, or fused-kernel measurement."
        ),
        "grouping_policy": (
            "Generated groups do not cross batch examples: n=B*ceil(S/q), 1<=q<=S. "
            "Cached decode therefore uses S=q=1 and n=B."
        ),
        "source_policy": (
            "source_state_bytes conservatively charges source_passes complete B*S*d activation scans; "
            "an anchor-only implementation must be identified and accounted separately"
        ),
        "controller_policy": (
            "The default controller is Linear(d,h)-SiLU-Linear(h,3r). Full-factor scheduled rows use "
            "the same explicitly reported controller traffic as a proxy overhead; their base ratio is "
            "the controller-independent feasibility boundary."
        ),
        "format_v2_correction": (
            "Generated scratch cardinality is excluded from scheduled global bytes. "
            "Base logical payload fields retain their cardinality-only meaning; "
            "common activation transfers remain uncounted. Do not compare v1 and v2 totals."
        ),
        "config": vars(args) if args is not None else {},
        "rows": rows,
    }


def write_outputs(payload: dict[str, Any], json_path: Path, csv_path: Path) -> None:
    rows = payload.get("rows", [])
    if not rows:
        raise ValueError("cannot write an empty regime map")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--d", type=int, default=4096)
    parser.add_argument("--m", type=int, default=14336)
    parser.add_argument("--ranks", type=parse_ints, default=[64, 128, 256, 384])
    parser.add_argument("--modes", type=parse_strings, default=list(VALID_WORKLOADS))
    parser.add_argument("--prefill-batches", type=parse_ints, default=[1, 4])
    parser.add_argument("--prefill-seqs", type=parse_ints, default=[128, 1024])
    parser.add_argument("--prefill-qs", type=parse_ints, default=[1, 16, 64])
    parser.add_argument("--decode-batches", type=parse_ints, default=[1, 8, 32])
    parser.add_argument("--training-batches", type=parse_ints, default=[1, 2])
    parser.add_argument("--training-seqs", type=parse_ints, default=[128, 512])
    parser.add_argument("--training-qs", type=parse_ints, default=[1, 16, 64])
    parser.add_argument("--controller-hidden", type=int, default=None)
    parser.add_argument(
        "--controller-param-elements",
        type=int,
        default=None,
        help="override the canonical two-layer diagonal-core controller parameter count",
    )
    parser.add_argument("--factor-dtype", choices=sorted(DTYPE_BYTES), default="fp16")
    parser.add_argument("--controller-dtype", choices=sorted(DTYPE_BYTES), default="fp32")
    parser.add_argument("--source-dtype", choices=sorted(DTYPE_BYTES), default="fp16")
    parser.add_argument("--factor-loads", type=int, default=1)
    parser.add_argument("--controller-loads", type=int, default=1)
    parser.add_argument("--source-passes", type=int, default=1)
    parser.add_argument("--out-json", default="results/regime_map/mwg_regime_map.json")
    parser.add_argument("--out-csv", default="results/regime_map/mwg_regime_map.csv")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    hidden = args.controller_hidden or min(256, max(32, args.d // 8))
    cases = build_workload_cases(
        args.modes,
        prefill_batches=args.prefill_batches,
        prefill_seqs=args.prefill_seqs,
        prefill_qs=args.prefill_qs,
        decode_batches=args.decode_batches,
        training_batches=args.training_batches,
        training_seqs=args.training_seqs,
        training_qs=args.training_qs,
    )
    rows = []
    for rank in args.ranks:
        config = AccountingConfig(
            d=args.d,
            m=args.m,
            rank=rank,
            controller_hidden=hidden,
            factor_element_bytes=DTYPE_BYTES[args.factor_dtype],
            controller_element_bytes=DTYPE_BYTES[args.controller_dtype],
            source_element_bytes=DTYPE_BYTES[args.source_dtype],
            factor_loads=args.factor_loads,
            controller_loads=args.controller_loads,
            source_passes=args.source_passes,
            controller_param_elements=args.controller_param_elements,
        )
        rows.extend(compute_row(case, config) for case in cases)
    payload = build_payload(rows, args)
    write_outputs(payload, Path(args.out_json), Path(args.out_csv))
    print(
        json.dumps(
            {
                "out_json": args.out_json,
                "out_csv": args.out_csv,
                "rows": len(rows),
                "workloads": sorted({row["workload"] for row in rows}),
                "physical_hbm_counter_measurement": False,
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
