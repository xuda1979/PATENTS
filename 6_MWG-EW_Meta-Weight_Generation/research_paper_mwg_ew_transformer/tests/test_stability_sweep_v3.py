"""Unit tests for the v3 stability-sweep hardening (H4-H7).

These tests exercise the v3 stability logic with a fully mocked torch
surface so the gate behavior can be verified on CPU without an NPU.
They encode the documented behaviors:

  1. A clean 1000-call sweep passes with a finite final error.
  2. A transient bad call that recovers on retry is recorded as an
     environment transient and does NOT fail the gate.
  3. A persistent op-attributed failure (every call wrong vs CPU
     truth) fails the gate with persistent_failures > 0.
  4. More than STABILITY_MAX_TRANSIENTS transient calls fails the
     gate (transient budget enforced).
  5. The recorded JSON is serializable with allow_nan=False.
"""

import importlib.util
import json
import math
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS_PATH = (ROOT / "custom_ops/ephemeral_core_apply/torch_ext/v4_multicore"
                "/test_v4_multicore_v3.py")


class ScriptedErr:
    def __init__(self, err):
        self.err = err

    def item(self):
        return self.err

    def cpu(self):
        return self

    def float(self):
        return self

    def abs(self):
        return self

    def max(self):
        return self

    def __sub__(self, other):
        return self


class ScriptedOut:
    def __init__(self, err):
        self.err = err

    def float(self):
        return self

    def cpu(self):
        return self

    def __sub__(self, other):
        return ScriptedErr(self.err)

    def abs(self):
        return ScriptedErr(self.err)

    def max(self):
        return ScriptedErr(self.err)


class ScriptedTensor:
    """Stand-in for an input tensor (act/ctrl/head_w/head_b)."""

    def __init__(self, data=None):
        self.data = data


def build_mock_torch(call_errors, call_counter):
    """Build a fake torch module surface sufficient for stability_sweep_v3."""
    fake_torch = types.SimpleNamespace()

    def fake_op(act, ctrl, head_w, head_b, amp):
        idx = call_counter["n"]
        call_counter["n"] += 1
        idx = min(idx, len(call_errors) - 1)
        return ScriptedOut(call_errors[idx])

    fake_torch.manual_seed = lambda *a, **k: None
    fake_torch.randn = lambda *a, **k: ScriptedTensor()
    fake_torch.float32 = "float32"
    fake_torch.float16 = "float16"
    fake_torch.isnan = lambda t: t  # not exercised on scripted path
    fake_torch.isinf = lambda t: t
    fake_torch.npu = types.SimpleNamespace(synchronize=lambda *a, **k: None)
    fake_torch.ops = types.SimpleNamespace(
        mwg=types.SimpleNamespace(ephemeral_core_apply_v4=fake_op))
    return fake_torch, fake_op


def run_sweep_with_mocked_op(call_errors, max_transients=10, retry_attempts=3):
    """Load the harness fresh and run stability_sweep_v3 under mocks.

    Returns the stability record dict.
    """
    torch_npu_stub = types.ModuleType("torch_npu")
    sys.modules.setdefault("torch_npu", torch_npu_stub)

    spec = importlib.util.spec_from_file_location("test_v4_multicore_v3_unit", HARNESS_PATH)
    harness = importlib.util.module_from_spec(spec)
    real_torch = sys.modules.get("torch")

    call_counter = {"n": 0}
    fake_torch, fake_op = build_mock_torch(call_errors, call_counter)

    # Replace torch with the fake inside the harness namespace only.
    harness_torch_holder = types.SimpleNamespace(torch=fake_torch)

    # Execute the harness module with its __name__ guarded so __main__
    # does not run; then patch module-level names.
    spec.loader.exec_module(harness)

    # Patch the module-level torch and constants.
    harness.torch = fake_torch
    harness.STABILITY_MAX_TRANSIENTS = max_transients
    harness.STABILITY_RETRY_ATTEMPTS = retry_attempts

    # cpu_truth/gated_ref/nan_stats operate on scripted tensors; replace them
    # with objects that support the arithmetic chain the sweep uses:
    #   err = (out.float().cpu() - truth.float()).abs().max().item()
    # ScriptedErr/ScriptedOut propagate the scripted op error regardless
    # of the right operand, so a NeutralTruth (zero error) on the right
    # yields the scripted error.
    class NeutralTruth(ScriptedOut):
        def __init__(self):
            super().__init__(0.0)

    harness.cpu_truth = lambda *a, **k: NeutralTruth()
    harness.gated_ref = lambda *a, **k: (NeutralTruth(), 0)
    harness.nan_stats = lambda t: {"nan": 0, "inf": 0}

    results = {}
    args = types.SimpleNamespace(output="/tmp/test_v4_v3_unit_ignored.json")
    harness.stability_sweep_v3(args, results)
    if real_torch is not None:
        sys.modules["torch"] = real_torch
    return results.get("stability_1000_calls", {}), harness


class TestStabilitySweepV3(unittest.TestCase):

    def test_clean_sweep_passes(self):
        record, _ = run_sweep_with_mocked_op([0.001] * 1010)
        self.assertTrue(record["pass"])
        self.assertEqual(record["completed"], 1000)
        self.assertEqual(record["transients_recovered"], 0)
        self.assertEqual(record["persistent_failures"], 0)
        self.assertAlmostEqual(record["final_max_abs_err"], 0.001)
        self.assertTrue(math.isfinite(record["final_max_abs_err"]))
        self.assertEqual(record["comparison_target"], "cpu_truth")

    def test_transient_recovers_and_passes(self):
        # Call 500 returns NaN (documented bad-window signature), then
        # the retry call returns a clean value; all others clean.
        errs = [0.001] * 1010
        errs[500] = float("nan")
        record, _ = run_sweep_with_mocked_op(errs)
        self.assertTrue(record["pass"])
        self.assertEqual(record["transients_recovered"], 1)
        self.assertEqual(record["persistent_failures"], 0)
        self.assertEqual(len(record["transient_events"]), 1)
        ev = record["transient_events"][0]
        self.assertEqual(ev["call_index"], 500)
        self.assertEqual(ev["retries_used"], 1)
        # NaN bad_err is strictly-JSON-encoded as the string "nan"
        self.assertEqual(ev["bad_err"], "nan")
        self.assertAlmostEqual(ev["recovered_err"], 0.001)

    def test_persistent_failure_fails_gate(self):
        # Every call returns NaN: the op is persistently broken.
        record, _ = run_sweep_with_mocked_op([float("nan")] * 1010)
        self.assertFalse(record["pass"])
        self.assertEqual(record["persistent_failures"], 1)
        self.assertIsNone(record["final_err_vs_gated_npu_ref"])
        self.assertLess(record["completed"], 1000)

    def test_transient_budget_enforced(self):
        # 11 transients (budget 10): gate must fail even though each
        # bad call recovers on the first retry.
        errs = [0.001] * 1200
        for i in range(11):
            errs[50 * (i + 1)] = float("nan")
        record, _ = run_sweep_with_mocked_op(errs, max_transients=10)
        self.assertFalse(record["pass"])
        self.assertGreaterEqual(record["transients_recovered"], 11)
        self.assertEqual(record["persistent_failures"], 0)
        self.assertEqual(record["completed"], 1000)

    def test_json_serializable_no_nan_leak(self):
        # The recorded JSON must be serializable with allow_nan=False
        # (the audit reads records with allow_nan=False); transient
        # bad errors are recorded only when finite, and the recorded
        # final error is finite when the gate passes.
        errs = [0.001] * 1010
        errs[500] = float("nan")
        record, _ = run_sweep_with_mocked_op(errs)
        json.dumps(record, allow_nan=False)

    def test_bad_err_nan_encoded_finite_or_absent(self):
        # In transient_events, a NaN bad_err must be representable in
        # strict JSON; the harness must therefore encode it as a
        # string or omit it.  Verify the actual record.
        errs = [0.001] * 1010
        errs[500] = float("nan")
        record, _ = run_sweep_with_mocked_op(errs)
        ev = record["transient_events"][0]
        # json.dumps with allow_nan=False must not raise.
        json.dumps(ev, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
