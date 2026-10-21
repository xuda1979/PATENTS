from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from aggregate_ASI3_scaling import aggregate, write_markdown  # noqa: E402


def write_run(path: Path, *, train_ms: float, sync_ms: float | None) -> Path:
    dense = {
        "train": {"mean_ms": train_ms},
        "train_speedup_x": 1.0,
        "train_tokens_per_s": 100.0,
    }
    mwg = {
        "rank": 64,
        "train": {"mean_ms": train_ms / 2},
        "train_speedup_x": 2.0,
        "train_tokens_per_s": 200.0,
    }
    if sync_ms is not None:
        dense.update(
            {
                "train_integrated_sync": {"mean_ms": sync_ms},
                "train_integrated_sync_speedup_x": 1.0,
                "train_integrated_sync_tokens_per_s": 80.0,
            }
        )
        mwg.update(
            {
                "train_integrated_sync": {"mean_ms": sync_ms / 2},
                "train_integrated_sync_speedup_x": 2.0,
                "train_integrated_sync_tokens_per_s": 160.0,
            }
        )
    payload = {
        "env": {
            "world_size": 2,
            "ascend_rt_visible_devices": "0,1",
            "backend": "hccl",
            "device_type": "npu",
        },
        "config": {"preset": "ASI3_large"},
        "results": {"dense": dense, "mwg_r64": mwg},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_aggregate_and_markdown_include_integrated_sync(tmp_path: Path) -> None:
    paths = [
        write_run(tmp_path / "run1.json", train_ms=10.0, sync_ms=12.0),
        write_run(tmp_path / "run2.json", train_ms=12.0, sync_ms=14.0),
    ]

    summary = aggregate(paths)
    group = next(iter(summary["groups"].values()))
    dense = group["methods"]["dense"]
    mwg = group["methods"]["mwg_r64"]

    assert "optimizer update is excluded" in summary["measurement_definitions"][
        "train_integrated_sync_ms"
    ]
    assert dense["train_integrated_sync_ms"] == {
        "n": 2,
        "mean": 13.0,
        "std": 1.4142,
        "min": 12.0,
        "max": 14.0,
    }
    assert mwg["train_integrated_sync_ms"]["mean"] == 6.5
    assert mwg["train_integrated_sync_speedup_x"]["mean"] == 2.0
    assert mwg["train_integrated_sync_tokens_per_s"]["mean"] == 160.0

    markdown_path = tmp_path / "summary.md"
    write_markdown(summary, markdown_path)
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "## Integrated DDP Gradient Synchronization" in markdown
    assert "the optimizer update is excluded" in markdown
    assert "F+B+DDP sync ms mean" in markdown


def test_legacy_runs_keep_original_table_without_empty_sync_section(tmp_path: Path) -> None:
    summary = aggregate([write_run(tmp_path / "legacy.json", train_ms=10.0, sync_ms=None)])
    group = next(iter(summary["groups"].values()))

    assert group["methods"]["dense"]["train_ms"]["mean"] == 10.0
    assert group["methods"]["dense"]["train_integrated_sync_ms"]["n"] == 0

    markdown_path = tmp_path / "legacy.md"
    write_markdown(summary, markdown_path)
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "| Group | Runs | Method | Train ms mean" in markdown
    assert "## Integrated DDP Gradient Synchronization" not in markdown
