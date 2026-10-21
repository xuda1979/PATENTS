from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from mwg_four_arm_lifetime_benchmark import (  # noqa: E402
    DEFAULT_ARMS,
    BenchmarkConfig,
    DenseArm,
    FusedBackendUnavailable,
    MaterializedCoreArm,
    PersistentLowRankArm,
    generate_master_weights,
    parse_arms,
    prepare_fused_backend,
    reference_ephemeral_core_apply,
    reference_materialize_core,
    run_benchmark,
    sha256_file,
    validate_fused_contract_manifest,
)
from summarize_four_arm_lifetime import load_reports, summarize_reports  # noqa: E402


def tiny_config() -> BenchmarkConfig:
    return BenchmarkConfig(
        d=8,
        m=12,
        rank=4,
        controller_hidden=6,
        batch=2,
        seq=3,
        amplitude=0.2,
        dtype="fp32",
        seed=71,
    )


def test_default_arm_list_excludes_fused() -> None:
    assert parse_arms(",".join(DEFAULT_ARMS)) == ("dense", "persistent", "materialized")
    assert parse_arms("all")[-1] == "fused"
    with pytest.raises(ValueError, match="unknown arms"):
        parse_arms("dense,pretend_fused")


@torch.no_grad()
def test_dense_is_exact_factor_product_control() -> None:
    config = tiny_config()
    master = generate_master_weights(config)
    dense = DenseArm(master, torch.float32)
    persistent = PersistentLowRankArm(master, torch.float32)
    x = torch.randn(config.batch, config.seq, config.d)

    torch.testing.assert_close(dense(x), persistent(x), rtol=2e-5, atol=2e-6)


@torch.no_grad()
def test_reference_core_apply_matches_explicit_materialization() -> None:
    generator = torch.Generator(device="cpu").manual_seed(73)
    rank_activation = torch.randn(2, 3, 4, generator=generator)
    hidden = torch.randn(2, 3, 6, generator=generator)
    weight = torch.randn(6, 4, generator=generator)
    bias = torch.randn(4, generator=generator)
    core = reference_materialize_core(hidden, weight, bias, 0.2, rank_activation.dtype)

    torch.testing.assert_close(
        reference_ephemeral_core_apply(rank_activation, hidden, weight, bias, 0.2),
        rank_activation * core,
    )


@torch.no_grad()
def test_materialized_arm_records_three_global_core_regions() -> None:
    config = tiny_config()
    model = MaterializedCoreArm(
        generate_master_weights(config), torch.float32, config.amplitude
    )
    model.record_core_metadata = True
    x = torch.randn(config.batch, config.seq, config.d)
    output = model(x)

    assert output.shape == (config.batch, config.seq, config.d)
    assert [item["projection"] for item in model.last_core_metadata] == [
        "up",
        "gate",
        "down",
    ]
    assert all(item["global_framework_tensor"] for item in model.last_core_metadata)
    assert (
        sum(item["bytes"] for item in model.last_core_metadata)
        == 3 * config.tokens * config.rank * 4
    )


def test_fused_backend_fails_closed_on_cpu() -> None:
    with pytest.raises(FusedBackendUnavailable, match="restricted to an audited NPU"):
        prepare_fused_backend(torch.device("cpu"), "missing.json", "missing.so")


def write_valid_contract(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "ephemeral_core_apply.cpp"
    library = tmp_path / "libmwg_ephemeral_core_apply.so"
    source.write_text("// audited test source\n", encoding="utf-8")
    library.write_bytes(b"not a real shared object; hash-validation fixture only\n")
    manifest = tmp_path / "contract.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "op_qualified_name": "mwg::ephemeral_core_apply",
                "implementation": "ascendc",
                "core_residency": "ub_local_tensor",
                "global_core_output": False,
                "workspace_bytes": 0,
                "outputs": ["scaled_rank_activation"],
                "audited_source_path": source.name,
                "audited_source_sha256": sha256_file(source),
                "binary_sha256": sha256_file(library),
                "source_audit": {
                    "no_global_core_tensor": True,
                    "no_core_datacopy_to_global": True,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest, library


def test_contract_manifest_binds_source_and_binary_hashes(tmp_path: Path) -> None:
    manifest, library = write_valid_contract(tmp_path)
    result = validate_fused_contract_manifest(manifest, library)
    assert result["validated"] is True
    assert result["workspace_bytes"] == 0
    assert result["global_core_output"] is False

    library.write_bytes(b"changed")
    with pytest.raises(FusedBackendUnavailable, match="library hash"):
        validate_fused_contract_manifest(manifest, library)


def test_cpu_three_arm_smoke_stays_below_no_store_claim() -> None:
    config = tiny_config()
    report = run_benchmark(
        config,
        DEFAULT_ARMS,
        torch.device("cpu"),
        warmup=0,
        iters=1,
        repeats=1,
        rtol=2e-5,
        atol=2e-6,
    )

    assert set(report["arms"]) == set(DEFAULT_ARMS)
    assert report["validations"]["dense_vs_persistent_factorization"]["passed"] is True
    assert report["backend_contract"]["validated"] is False
    assert report["claim_boundary"]["arm4_execution_observed"] is False
    assert report["claim_boundary"]["no_store_claim_ready"] is False
    expected = 2 * 3 * config.tokens * config.rank * 4
    assert (
        report["logical_core_accounting"]["materialized_store_plus_reload_bytes"]
        == expected
    )


def test_summarizer_does_not_promote_three_arm_timing(tmp_path: Path) -> None:
    config = tiny_config()
    report = run_benchmark(
        config,
        DEFAULT_ARMS,
        torch.device("cpu"),
        warmup=0,
        iters=1,
        repeats=1,
        rtol=2e-5,
        atol=2e-6,
    )
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    loaded, rejected = load_reports([tmp_path])
    summary = summarize_reports(loaded)

    assert not rejected
    assert len(loaded) == 1
    assert summary["global_claim_boundary"]["no_store_claim_ready"] is False
    item = next(iter(summary["configurations"].values()))
    assert item["claim_status"]["arm4_execution_observed"] is False
    assert (
        "no validated compiled no-store contract execution"
        in item["claim_status"]["open_gaps"]
    )
