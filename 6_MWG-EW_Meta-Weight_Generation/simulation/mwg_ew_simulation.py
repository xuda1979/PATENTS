from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from math import exp, floor
from typing import Iterable


MIB = 1024**2


@dataclass(frozen=True)
class DescriptorProfile:
    name: str
    compaction: float
    generator_overhead_base_mib: float
    generator_overhead_per_rank_mib: float


@dataclass(frozen=True)
class ModelProfile:
    name: str
    d: int
    m: int
    projections: int
    dense_latency: float
    dense_latency_unit: str
    dense_throughput: float
    throughput_unit: str
    dense_quality: float
    quality_name: str
    dense_tensor_util_pct: float
    tensor_util_gain_pct: float
    total_device_mem_gib: float
    dense_peak_mem_gib: float
    target_mem_share_gib: float
    kv_mib_per_token: float
    default_memory_weight: float
    fixed_latency_share: float
    generator_compute_base: float
    lowrank_compute_scale: float
    quality_floor_pct: float
    quality_scale_pct: float
    quality_decay_rank: float
    dense_allreduce_mib: float
    non_target_sync_mib: float
    generator_grad_full_mib: float
    dense_comm_time_ms: float
    reference_bandwidth_tbps: float
    dense_hardware_fixed_share: float


PILOT_MODEL = ModelProfile(
    name="1B pilot single projection",
    d=2048,
    m=5632,
    projections=1,
    dense_latency=2.8,
    dense_latency_unit="ms",
    dense_throughput=357.0,
    throughput_unit="tokens/s",
    dense_quality=8.2,
    quality_name="Perplexity",
    dense_tensor_util_pct=68.0,
    tensor_util_gain_pct=16.0,
    total_device_mem_gib=80.0,
    dense_peak_mem_gib=19.5,
    target_mem_share_gib=3.2,
    kv_mib_per_token=0.22,
    default_memory_weight=0.78,
    fixed_latency_share=0.44,
    generator_compute_base=0.08,
    lowrank_compute_scale=3.6,
    quality_floor_pct=1.0,
    quality_scale_pct=16.0,
    quality_decay_rank=42.0,
    dense_allreduce_mib=0.0,
    non_target_sync_mib=0.0,
    generator_grad_full_mib=0.0,
    dense_comm_time_ms=0.0,
    reference_bandwidth_tbps=1.6,
    dense_hardware_fixed_share=0.52,
)


PATENT_MODEL = ModelProfile(
    name="8B gated FFN block",
    d=4096,
    m=14336,
    projections=3,
    dense_latency=4.2,
    dense_latency_unit="s",
    dense_throughput=290.0,
    throughput_unit="tokens/s",
    dense_quality=2.14,
    quality_name="Validation Loss",
    dense_tensor_util_pct=68.0,
    tensor_util_gain_pct=18.0,
    total_device_mem_gib=80.0,
    dense_peak_mem_gib=68.0,
    target_mem_share_gib=26.0,
    kv_mib_per_token=0.75,
    default_memory_weight=0.72,
    fixed_latency_share=0.48,
    generator_compute_base=0.14,
    lowrank_compute_scale=4.8,
    quality_floor_pct=1.5,
    quality_scale_pct=22.0,
    quality_decay_rank=50.0,
    dense_allreduce_mib=1024.0,
    non_target_sync_mib=96.0,
    generator_grad_full_mib=96.0,
    dense_comm_time_ms=340.0,
    reference_bandwidth_tbps=2.4,
    dense_hardware_fixed_share=0.45,
)


DIRECT = DescriptorProfile(
    name="direct_factor",
    compaction=1.0,
    generator_overhead_base_mib=0.08,
    generator_overhead_per_rank_mib=0.0012,
)


BASIS_BANK = DescriptorProfile(
    name="basis_bank",
    compaction=0.72,
    generator_overhead_base_mib=0.85,
    generator_overhead_per_rank_mib=0.0040,
)


def dense_block_mib(model: ModelProfile) -> float:
    return model.projections * 2.0 * model.d * model.m / MIB


def factor_block_mib(model: ModelProfile, rank: int) -> float:
    return model.projections * 2.0 * (model.d * rank + rank * model.m) / MIB


def generator_overhead_mib(descriptor: DescriptorProfile, rank: int, reuse_window: int) -> float:
    return (
        descriptor.generator_overhead_base_mib
        + descriptor.generator_overhead_per_rank_mib * rank
    ) / reuse_window


def effective_read_mib(
    model: ModelProfile,
    descriptor: DescriptorProfile,
    rank: int,
    reuse_window: int,
) -> float:
    return factor_block_mib(model, rank) * descriptor.compaction + generator_overhead_mib(
        descriptor, rank, reuse_window
    )


def lowrank_ratio(model: ModelProfile, rank: int) -> float:
    return factor_block_mib(model, rank) / dense_block_mib(model)


def compute_ratio(model: ModelProfile, rank: int, reuse_window: int) -> float:
    return model.generator_compute_base / reuse_window + model.lowrank_compute_scale * lowrank_ratio(
        model, rank
    )


def path_cost_ratio(
    model: ModelProfile,
    descriptor: DescriptorProfile,
    rank: int,
    reuse_window: int,
    memory_weight: float | None = None,
) -> float:
    memory_weight = model.default_memory_weight if memory_weight is None else memory_weight
    bytes_ratio = effective_read_mib(model, descriptor, rank, reuse_window) / dense_block_mib(model)
    return memory_weight * bytes_ratio + (1.0 - memory_weight) * compute_ratio(
        model, rank, reuse_window
    )


def total_latency_factor(
    model: ModelProfile,
    descriptor: DescriptorProfile,
    rank: int,
    replacement_ratio: float,
    reuse_window: int,
    memory_weight: float | None = None,
) -> float:
    target_ratio = (1.0 - replacement_ratio) + replacement_ratio * path_cost_ratio(
        model, descriptor, rank, reuse_window, memory_weight
    )
    return model.fixed_latency_share + (1.0 - model.fixed_latency_share) * target_ratio


def quality_increase_pct(model: ModelProfile, rank: int, replacement_ratio: float) -> float:
    full_replacement_gap = model.quality_floor_pct + model.quality_scale_pct * exp(
        -rank / model.quality_decay_rank
    )
    return full_replacement_gap * (replacement_ratio**0.85)


def reuse_penalty_pct(reuse_window: int) -> float:
    penalties = {1: 0.0, 2: 0.2, 4: 0.6, 8: 1.5}
    return penalties.get(reuse_window, 0.25 * max(0, reuse_window - 1))


def tensor_util_pct(
    model: ModelProfile,
    descriptor: DescriptorProfile,
    rank: int,
    replacement_ratio: float,
    reuse_window: int,
) -> float:
    bytes_ratio = effective_read_mib(model, descriptor, rank, reuse_window) / dense_block_mib(model)
    comp_ratio = compute_ratio(model, rank, reuse_window)
    numerator = model.default_memory_weight * bytes_ratio
    denominator = numerator + (1.0 - model.default_memory_weight) * comp_ratio
    memory_pressure = numerator / denominator if denominator else 1.0
    return model.dense_tensor_util_pct + replacement_ratio * model.tensor_util_gain_pct * (
        1.0 - memory_pressure
    )


def peak_memory_gib(
    model: ModelProfile,
    descriptor: DescriptorProfile,
    rank: int,
    replacement_ratio: float,
    reuse_window: int,
) -> float:
    resident_ratio = effective_read_mib(model, descriptor, rank, reuse_window) / dense_block_mib(model)
    saved = model.target_mem_share_gib * replacement_ratio * (1.0 - resident_ratio)
    return model.dense_peak_mem_gib - saved


def max_context_tokens(
    model: ModelProfile,
    descriptor: DescriptorProfile,
    rank: int,
    replacement_ratio: float,
    reuse_window: int,
) -> int:
    kv_budget_gib = model.total_device_mem_gib - peak_memory_gib(
        model, descriptor, rank, replacement_ratio, reuse_window
    )
    return floor(kv_budget_gib * 1024.0 / model.kv_mib_per_token)


def allreduce_mib(model: ModelProfile, replacement_ratio: float) -> float:
    dense_target_sync = model.dense_allreduce_mib - model.non_target_sync_mib
    return (
        model.non_target_sync_mib
        + dense_target_sync * (1.0 - replacement_ratio)
        + model.generator_grad_full_mib * replacement_ratio
    )


def comm_time_ms(model: ModelProfile, replacement_ratio: float) -> float:
    if model.dense_allreduce_mib == 0:
        return 0.0
    return model.dense_comm_time_ms * allreduce_mib(model, replacement_ratio) / model.dense_allreduce_mib


def metric_row(
    model: ModelProfile,
    descriptor: DescriptorProfile,
    rank: int,
    replacement_ratio: float,
    reuse_window: int = 1,
    memory_weight: float | None = None,
    dense_latency_override: float | None = None,
) -> dict[str, float]:
    latency_factor = total_latency_factor(
        model, descriptor, rank, replacement_ratio, reuse_window, memory_weight
    )
    dense_latency = model.dense_latency if dense_latency_override is None else dense_latency_override
    loss_pct = quality_increase_pct(model, rank, replacement_ratio) + reuse_penalty_pct(reuse_window)
    quality = model.dense_quality * (1.0 + loss_pct / 100.0)
    return {
        "effective_read_mib": effective_read_mib(model, descriptor, rank, reuse_window),
        "latency": dense_latency * latency_factor,
        "throughput": model.dense_throughput / latency_factor,
        "quality": quality,
        "loss_increase_pct": loss_pct,
        "tensor_util_pct": tensor_util_pct(model, descriptor, rank, replacement_ratio, reuse_window),
        "peak_memory_gib": peak_memory_gib(model, descriptor, rank, replacement_ratio, reuse_window),
        "max_context_tokens": max_context_tokens(model, descriptor, rank, replacement_ratio, reuse_window),
        "allreduce_mib": allreduce_mib(model, replacement_ratio),
        "comm_time_ms": comm_time_ms(model, replacement_ratio),
    }


def dense_hardware_latency(model: ModelProfile, bandwidth_tbps: float) -> float:
    scale = model.dense_hardware_fixed_share + (1.0 - model.dense_hardware_fixed_share) * (
        model.reference_bandwidth_tbps / bandwidth_tbps
    )
    return model.dense_latency * scale


def round2(value: float) -> float:
    return round(value + 1e-9, 2)


def markdown_table(headers: list[str], rows: Iterable[list[object]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(out)


def pilot_section() -> str:
    headers = [
        "Rank",
        "Effective Read (MiB/token)",
        f"Latency ({PILOT_MODEL.dense_latency_unit})",
        PILOT_MODEL.throughput_unit,
        PILOT_MODEL.quality_name,
        "Loss Increase",
    ]
    rows: list[list[object]] = [[
        "Dense",
        round2(dense_block_mib(PILOT_MODEL)),
        round2(PILOT_MODEL.dense_latency),
        round2(PILOT_MODEL.dense_throughput),
        round2(PILOT_MODEL.dense_quality),
        "0.00%",
    ]]
    for rank in (32, 64, 96, 128):
        metrics = metric_row(PILOT_MODEL, DIRECT, rank, replacement_ratio=1.0)
        rows.append([
            rank,
            round2(metrics["effective_read_mib"]),
            round2(metrics["latency"]),
            round2(metrics["throughput"]),
            round2(metrics["quality"]),
            f'{round2(metrics["loss_increase_pct"])}%',
        ])
    return "## 1B pilot single-projection sweep\n\n" + markdown_table(headers, rows)


def rank_sweep_section() -> str:
    headers = [
        "Rank",
        "Effective Read (MiB/block)",
        f"Batch Latency ({PATENT_MODEL.dense_latency_unit})",
        PATENT_MODEL.throughput_unit,
        "Tensor Utilization",
        PATENT_MODEL.quality_name,
        "Loss Increase",
    ]
    rows: list[list[object]] = [[
        "Dense",
        round2(dense_block_mib(PATENT_MODEL)),
        round2(PATENT_MODEL.dense_latency),
        round2(PATENT_MODEL.dense_throughput),
        f'{round2(PATENT_MODEL.dense_tensor_util_pct)}%',
        round2(PATENT_MODEL.dense_quality),
        "0.00%",
    ]]
    for rank in (32, 64, 96, 128, 160, 256):
        metrics = metric_row(PATENT_MODEL, BASIS_BANK, rank, replacement_ratio=1.0)
        rows.append([
            rank,
            round2(metrics["effective_read_mib"]),
            round2(metrics["latency"]),
            round2(metrics["throughput"]),
            f'{round2(metrics["tensor_util_pct"])}%',
            round2(metrics["quality"]),
            f'{round2(metrics["loss_increase_pct"])}%',
        ])
    return "## 8B full-replacement rank sweep\n\n" + markdown_table(headers, rows)


def replacement_section() -> str:
    headers = [
        "Replacement Ratio",
        "Effective Read (MiB/block)",
        f"Batch Latency ({PATENT_MODEL.dense_latency_unit})",
        "Peak Memory (GiB)",
        "Max Context (tokens)",
        PATENT_MODEL.quality_name,
        "All-Reduce (MiB/step)",
        "Comm Time (ms)",
    ]
    rows: list[list[object]] = [[
        "0%",
        round2(dense_block_mib(PATENT_MODEL)),
        round2(PATENT_MODEL.dense_latency),
        round2(PATENT_MODEL.dense_peak_mem_gib),
        max_context_tokens(PATENT_MODEL, BASIS_BANK, 128, 0.0, 1),
        round2(PATENT_MODEL.dense_quality),
        round2(PATENT_MODEL.dense_allreduce_mib),
        round2(PATENT_MODEL.dense_comm_time_ms),
    ]]
    for ratio in (0.25, 0.50, 0.75, 1.00):
        metrics = metric_row(PATENT_MODEL, BASIS_BANK, 128, replacement_ratio=ratio)
        rows.append([
            f"{int(ratio * 100)}%",
            round2(metrics["effective_read_mib"]),
            round2(metrics["latency"]),
            round2(metrics["peak_memory_gib"]),
            int(metrics["max_context_tokens"]),
            round2(metrics["quality"]),
            round2(metrics["allreduce_mib"]),
            round2(metrics["comm_time_ms"]),
        ])
    return "## 8B replacement sweep at rank 128\n\n" + markdown_table(headers, rows)


def reuse_section() -> str:
    headers = [
        "Reuse Window",
        "Effective Read (MiB/block)",
        f"Batch Latency ({PATENT_MODEL.dense_latency_unit})",
        PATENT_MODEL.throughput_unit,
        "Extra Loss Drift",
    ]
    rows: list[list[object]] = []
    for reuse_window in (1, 2, 4, 8):
        metrics = metric_row(
            PATENT_MODEL,
            BASIS_BANK,
            128,
            replacement_ratio=1.0,
            reuse_window=reuse_window,
        )
        rows.append([
            reuse_window,
            round2(metrics["effective_read_mib"]),
            round2(metrics["latency"]),
            round2(metrics["throughput"]),
            f'{round2(reuse_penalty_pct(reuse_window))}%',
        ])
    return "## Token-group reuse sweep at rank 128\n\n" + markdown_table(headers, rows)


def hardware_section() -> str:
    headers = [
        "HBM Bandwidth (TB/s)",
        f"Dense Latency ({PATENT_MODEL.dense_latency_unit})",
        f"MWG-EW Latency ({PATENT_MODEL.dense_latency_unit})",
        f"Dense {PATENT_MODEL.throughput_unit}",
        f"MWG-EW {PATENT_MODEL.throughput_unit}",
        "Speedup",
    ]
    rows: list[list[object]] = []
    for bandwidth_tbps, memory_weight in ((1.6, 0.82), (2.4, 0.72), (3.2, 0.62)):
        dense_latency = dense_hardware_latency(PATENT_MODEL, bandwidth_tbps)
        dense_throughput = PATENT_MODEL.dense_throughput * PATENT_MODEL.dense_latency / dense_latency
        metrics = metric_row(
            PATENT_MODEL,
            BASIS_BANK,
            128,
            replacement_ratio=1.0,
            memory_weight=memory_weight,
            dense_latency_override=dense_latency,
        )
        speedup = dense_latency / metrics["latency"]
        rows.append([
            bandwidth_tbps,
            round2(dense_latency),
            round2(metrics["latency"]),
            round2(dense_throughput),
            round2(metrics["throughput"] * PATENT_MODEL.dense_latency / dense_latency),
            f"{round2(speedup)}x",
        ])
    return "## Hardware sensitivity at rank 128\n\n" + markdown_table(headers, rows)


def json_payload() -> dict[str, object]:
    return {
        "models": {
            "pilot": asdict(PILOT_MODEL),
            "patent": asdict(PATENT_MODEL),
        },
        "descriptors": {
            "direct": asdict(DIRECT),
            "basis_bank": asdict(BASIS_BANK),
        },
        "pilot_rank_sweep": {
            str(rank): metric_row(PILOT_MODEL, DIRECT, rank, replacement_ratio=1.0)
            for rank in (32, 64, 96, 128)
        },
        "patent_rank_sweep": {
            str(rank): metric_row(PATENT_MODEL, BASIS_BANK, rank, replacement_ratio=1.0)
            for rank in (32, 64, 96, 128, 160, 256)
        },
        "patent_replacement_sweep": {
            str(ratio): metric_row(PATENT_MODEL, BASIS_BANK, 128, replacement_ratio=ratio)
            for ratio in (0.25, 0.50, 0.75, 1.00)
        },
    }


def markdown_report() -> str:
    assumptions = [
        "# MWG-EW analytical simulation",
        "",
        "## Assumptions",
        "",
        f"- 1B pilot uses `d={PILOT_MODEL.d}`, `m={PILOT_MODEL.m}`, one FFN projection, and the direct-factor path.",
        f"- Patent-grade simulation uses `d={PATENT_MODEL.d}`, `m={PATENT_MODEL.m}`, three FFN projections, the basis-bank path, and a dense baseline latency of `{PATENT_MODEL.dense_latency} {PATENT_MODEL.dense_latency_unit}`.",
        f"- Dense gated-FFN block footprint is `{round2(dense_block_mib(PATENT_MODEL))} MiB`; low-rank footprints are converted to effective read with explicit generator amortization.",
        "- Peak-memory and context results assume an 80 GiB card budget and a 0.75 MiB/token KV-cache cost.",
        "- Distributed-training communication assumes 1024 MiB/step dense synchronization, 96 MiB/step non-target traffic, and 96 MiB/step generator synchronization at 100% replacement.",
        "",
    ]
    sections = [
        pilot_section(),
        rank_sweep_section(),
        replacement_section(),
        reuse_section(),
        hardware_section(),
    ]
    return "\n\n".join(assumptions + sections)


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproducible MWG-EW analytical simulation")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args()

    if args.format == "json":
        print(json.dumps(json_payload(), indent=2))
    else:
        print(markdown_report())


if __name__ == "__main__":
    main()
