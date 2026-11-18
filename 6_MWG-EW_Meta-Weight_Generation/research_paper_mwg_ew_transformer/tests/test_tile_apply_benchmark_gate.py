"""Offline tests for the tile-apply benchmark gate enforcement.

These exercise the pre-registered TILE_GATE evaluation logic without a
device: verdict PASS/FAIL, refusal on missing or failed records, threshold
pinned to the harness header values, and the device-only modes refusing to
fabricate results locally.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "experiments/verify_tile_apply_benchmark.py"
HARNESS = ROOT / "scripts/asi2_block_givens_tile_apply_benchmark_worker.sh"

spec = importlib.util.spec_from_file_location("tile_gate", SCRIPT)
tile_gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tile_gate)


def _write_run_dir(rd: Path, tile_ms=(0.5, 0.6, 0.7), pers_ms=1.0,
                   verification_passed=True):
    (rd / "verification.json").write_text(json.dumps({
        "passed": verification_passed, "max_rel_diff": 0.001}))
    for seed, tile in zip((2026, 2027, 2028), tile_ms):
        (rd / f"seed_{seed}_benchmark.json").write_text(json.dumps({
            "tile_apply": {"median_ms": tile},
            "persistent": {"median_ms": pers_ms}}))


def _run_gate(rd: Path, out: Path):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--gate", "--run-dir", str(rd),
         "--out", str(out)],
        capture_output=True, text=True)


class TestTileGate(unittest.TestCase):
    def test_gate_thresholds_are_pre_registered(self):
        gate = tile_gate.TILE_GATE
        self.assertEqual(gate["speed_ceiling_ratio"], 0.80)
        self.assertEqual(gate["correctness_max_rel"], 2e-2)
        self.assertEqual(gate["batch"], 1)
        self.assertEqual(gate["seq"], 128)
        self.assertEqual(gate["dtype"], "fp16")

    def test_harness_header_declares_same_thresholds(self):
        header = HARNESS.read_text()
        self.assertIn(">= 20% lower", header)
        self.assertIn("0.80", header)
        self.assertIn("2e-2", header)
        self.assertIn("never promoted", header)

    def test_pass_verdict_on_all_seeds_under_ceiling(self):
        with tempfile.TemporaryDirectory() as td:
            rd, out = Path(td) / "run", Path(td) / "report.json"
            rd.mkdir()
            _write_run_dir(rd)
            result = _run_gate(rd, out)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text())
            self.assertEqual(report["verdict"], "PASS")
            for seed, margin in (("2026", 0.5), ("2027", 0.4), ("2028", 0.3)):
                self.assertAlmostEqual(report["per_seed"][seed]["speed_margin"],
                                       margin)

    def test_fail_verdict_recorded_as_negative_result(self):
        # One seed over the ceiling: rc stays 0 but verdict is FAIL, and the
        # report records the failed margins as first-class results.
        with tempfile.TemporaryDirectory() as td:
            rd, out = Path(td) / "run", Path(td) / "report.json"
            rd.mkdir()
            _write_run_dir(rd, tile_ms=(0.5, 0.6, 0.9))
            result = _run_gate(rd, out)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text())
            self.assertEqual(report["verdict"], "FAIL")
            self.assertFalse(report["per_seed"]["2028"]["passed"])
            self.assertIn("negative result", report["claim_boundary"])

    def test_missing_seed_refused(self):
        with tempfile.TemporaryDirectory() as td:
            rd, out = Path(td) / "run", Path(td) / "report.json"
            rd.mkdir()
            _write_run_dir(rd)
            (rd / "seed_2027_benchmark.json").unlink()
            result = _run_gate(rd, out)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing", result.stderr)

    def test_failed_verification_refused(self):
        # A failed correctness verification voids timing: the gate must
        # refuse rather than evaluate speed alone.
        with tempfile.TemporaryDirectory() as td:
            rd, out = Path(td) / "run", Path(td) / "report.json"
            rd.mkdir()
            _write_run_dir(rd, verification_passed=False)
            result = _run_gate(rd, out)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("verification", result.stderr)

    def test_missing_verification_refused(self):
        with tempfile.TemporaryDirectory() as td:
            rd, out = Path(td) / "run", Path(td) / "report.json"
            rd.mkdir()
            _write_run_dir(rd)
            (rd / "verification.json").unlink()
            result = _run_gate(rd, out)
            self.assertNotEqual(result.returncode, 0)

    def test_device_modes_refuse_offline(self):
        # --verify-only and --benchmark must refuse locally rather than
        # fabricate results.
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "v.json"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--verify-only",
                 "--out", str(out)],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(out.exists())

    def test_harness_bash_syntax_valid(self):
        result = subprocess.run(["bash", "-n", str(HARNESS)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
