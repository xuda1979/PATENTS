from __future__ import annotations

import sys
from pathlib import Path

import pytest
import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from mwg_token_router_gate_eval import threshold_for_fraction, threshold_for_joint_budget, threshold_for_risk_budget  # noqa: E402


def test_global_threshold_policy_matches_global_quantile() -> None:
    scores = torch.tensor([0.1, 0.2, 0.3, 0.4])
    row = threshold_for_fraction(scores, ["a", "a", "b", "b"], 0.5, "global")
    assert row["policy"] == "global"
    assert row["threshold"] == pytest.approx(0.2)
    assert row["global_threshold"] == pytest.approx(0.2)
    assert row["suite_thresholds"] == {}


def test_suite_min_threshold_uses_strictest_suite_quantile() -> None:
    scores = torch.tensor([0.1, 0.2, 10.0, 11.0])
    suites = ["easy", "easy", "hard", "hard"]
    row = threshold_for_fraction(scores, suites, 0.5, "suite_min")
    assert row["policy"] == "suite_min"
    assert row["global_threshold"] == pytest.approx(0.2)
    assert row["suite_thresholds"] == pytest.approx({"easy": 0.1, "hard": 10.0})
    assert row["threshold"] == pytest.approx(0.1)


def test_suite_local_threshold_keeps_per_suite_quantiles() -> None:
    scores = torch.tensor([0.1, 0.2, 10.0, 11.0])
    suites = ["easy", "easy", "hard", "hard"]
    row = threshold_for_fraction(scores, suites, 0.5, "suite_local")
    assert row["policy"] == "suite_local"
    assert row["global_threshold"] == pytest.approx(0.2)
    assert row["suite_thresholds"] == pytest.approx({"easy": 0.1, "hard": 10.0})
    assert row["threshold"] == pytest.approx(0.2)


def test_suite_policy_rejects_mismatched_suite_ids() -> None:
    scores = torch.tensor([0.1, 0.2])
    try:
        threshold_for_fraction(scores, ["only_one"], 0.5, "suite_min")
    except ValueError as exc:
        assert "suite_ids must match" in str(exc)
    else:
        raise AssertionError("expected mismatched suite_ids to fail")


def test_risk_budget_caps_by_predicted_delta_and_fraction() -> None:
    predicted_delta = torch.tensor([-0.4, -0.2, -0.1, 0.3])
    row = threshold_for_risk_budget(predicted_delta, [], 0.0, 0.5, "global")
    assert row["policy"] == "risk_global"
    assert row["threshold"] == pytest.approx(-0.2)
    assert row["max_predicted_delta"] == pytest.approx(0.0)
    assert row["max_patch_fraction"] == pytest.approx(0.5)


def test_suite_local_risk_budget_keeps_per_suite_thresholds() -> None:
    predicted_delta = torch.tensor([-0.4, 0.2, -0.3, -0.1])
    suites = ["a", "a", "b", "b"]
    row = threshold_for_risk_budget(predicted_delta, suites, 0.0, 0.5, "suite_local")
    assert row["policy"] == "risk_suite_local"
    assert row["suite_thresholds"] == pytest.approx({"a": -0.4, "b": -0.3})
    assert row["threshold"] == pytest.approx(-0.4)


def test_joint_budget_masks_bad_tokens_before_fraction_quantile() -> None:
    predicted_delta = torch.tensor([-0.5, -0.2, 0.1, 0.4])
    row = threshold_for_joint_budget(predicted_delta, [], 0.0, 0.5, "global")
    assert row["policy"] == "joint_global"
    assert row["threshold"] == pytest.approx(-0.2)
    assert row["global_threshold"] == pytest.approx(-0.2)
    assert row["max_predicted_delta"] == pytest.approx(0.0)
    assert row["target_patch_fraction"] == pytest.approx(0.5)


def test_joint_budget_suite_local_preserves_per_suite_masked_quantiles() -> None:
    predicted_delta = torch.tensor([-0.5, 0.1, -0.4, -0.2])
    suites = ["easy", "easy", "hard", "hard"]
    row = threshold_for_joint_budget(predicted_delta, suites, 0.0, 0.5, "suite_local")
    assert row["policy"] == "joint_suite_local"
    assert row["suite_thresholds"] == pytest.approx({"easy": -0.5, "hard": -0.4})
    assert row["threshold"] == pytest.approx(-0.4)
