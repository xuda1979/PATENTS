from __future__ import annotations

import csv
import json
import sys
from argparse import Namespace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from mwg_regime_map import (  # noqa: E402
    AccountingConfig,
    WorkloadCase,
    build_payload,
    build_workload_cases,
    compute_row,
    full_factor_q_min,
    group_count,
    write_outputs,
)


def test_group_count_is_batch_isolated() -> None:
    assert group_count(batch=3, seq=10, reuse_group=4) == 9
    assert group_count(batch=3, seq=10, reuse_group=4) != 8  # ceil((B*S)/q)


@pytest.mark.parametrize("reuse_group", [0, 11])
def test_group_count_enforces_reuse_group_bounds(reuse_group: int) -> None:
    with pytest.raises(ValueError, match="1 <= q <= S"):
        group_count(batch=1, seq=10, reuse_group=reuse_group)


def test_cached_decode_requires_one_token_groups() -> None:
    with pytest.raises(ValueError, match="cached decode"):
        WorkloadCase("decode", batch=8, seq=2, reuse_group=1).validate()
    with pytest.raises(ValueError, match="cached decode"):
        WorkloadCase("decode", batch=8, seq=1, reuse_group=2).validate()


def test_reviewer_full_factor_break_even_thresholds() -> None:
    assert full_factor_q_min(d=4096, m=14336, rank=128, batch=1, seq=1024) == 43
    assert full_factor_q_min(d=1536, m=8960, rank=384, batch=1, seq=1024) == 342


def test_full_factor_break_even_can_be_impossible_at_large_batch() -> None:
    # The first reviewer geometry allows at most 24 total groups.  At B=32,
    # even q=S leaves 32 groups, so no strict base-payload reduction exists.
    assert full_factor_q_min(d=4096, m=14336, rank=128, batch=32, seq=1024) is None


def test_component_ledger_and_mixed_dtype_bytes() -> None:
    case = WorkloadCase("training", batch=2, seq=5, reuse_group=2)
    config = AccountingConfig(
        d=8,
        m=16,
        rank=2,
        controller_hidden=4,
        factor_element_bytes=2,
        controller_element_bytes=4,
        source_element_bytes=2,
    )

    row = compute_row(case, config)

    assert row["tokens"] == 10
    assert row["group_count"] == 6
    assert row["dense_weight_elements"] == 384
    assert row["dense_weight_bytes"] == 768
    assert row["persistent_factor_elements"] == 144
    assert row["persistent_factor_bytes"] == 288
    assert row["controller_parameter_elements"] == 66
    assert row["controller_parameter_bytes"] == 264
    assert row["source_state_elements"] == 80
    assert row["source_state_bytes"] == 160
    assert row["diagonal_core_generated_elements"] == 36
    assert row["diagonal_core_generated_bytes"] == 72
    assert row["diagonal_core_scheduled_no_store_bytes"] == 784
    assert row["diagonal_core_scheduled_materialized_bytes"] == 928
    assert row["full_factor_generated_elements"] == 864
    assert row["full_factor_generated_bytes"] == 1728
    assert row["full_factor_scheduled_no_store_bytes"] == 2152
    assert row["full_factor_scheduled_materialized_bytes"] == 5608
    assert row["physical_hbm_counter_measurement"] is False


def test_workload_builder_covers_prefill_decode_and_training() -> None:
    cases = build_workload_cases(
        ["prefill", "decode", "training"],
        prefill_batches=[1],
        prefill_seqs=[128],
        prefill_qs=[1, 16],
        decode_batches=[1, 8],
        training_batches=[2],
        training_seqs=[64],
        training_qs=[1, 8],
    )

    assert {case.workload for case in cases} == {"prefill", "decode", "training"}
    decode = [case for case in cases if case.workload == "decode"]
    assert all(case.seq == 1 and case.reuse_group == 1 for case in decode)
    assert [group_count(case.batch, case.seq, case.reuse_group) for case in decode] == [1, 8]


def test_json_and_csv_outputs_preserve_flat_rows(tmp_path: Path) -> None:
    row = compute_row(
        WorkloadCase("prefill", batch=1, seq=128, reuse_group=16),
        AccountingConfig(d=64, m=128, rank=8, controller_hidden=32),
    )
    payload = build_payload([row], Namespace(example="test"))
    json_path = tmp_path / "regime.json"
    csv_path = tmp_path / "regime.csv"

    write_outputs(payload, json_path, csv_path)

    decoded = json.loads(json_path.read_text(encoding="utf-8"))
    assert decoded["rows"][0]["group_count"] == 8
    assert "no row is a physical HBM" in decoded["claim_boundary"]
    with csv_path.open(encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert len(csv_rows) == 1
    assert csv_rows[0]["workload"] == "prefill"
    assert csv_rows[0]["group_count"] == "8"
    assert csv_rows[0]["physical_hbm_counter_measurement"] == "False"
