import copy
import importlib.util
import json
from pathlib import Path
import shutil
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("journal_audit", ROOT / "scripts/audit_journal_evidence.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.records = json.loads((ROOT / audit.QUALITY / "per_seed_results.json").read_text())
        self.meta = json.loads((ROOT / audit.QUALITY / "VERIFIED_RESULT_RECORD.json").read_text())

    def test_archived_quality_exact_pair_and_storage(self):
        q = audit.quality_summary(self.records, self.meta)
        contrast = q["contrasts"][0]
        self.assertAlmostEqual(contrast["difference"], -0.0007545)
        self.assertLess(contrast["descriptive_t95_interval"][1], 0)
        self.assertAlmostEqual(q["rows"][-1]["reconstructed_fp32_mib"], 63.756591796875)

    def test_missing_seed_rejected(self):
        del self.records["seed_2029"]
        with self.assertRaisesRegex(ValueError, "seed"):
            audit.quality_summary(self.records, self.meta)

    def test_disagreeing_duplicate_rejected(self):
        self.records["seed_2026"]["persistent_low_rank_r384"]["relative_mse"] += .1
        with self.assertRaisesRegex(ValueError, "disagree"):
            audit.quality_summary(self.records, self.meta)

    def test_matching_nan_records_rejected(self):
        self.records["seed_2026"]["persistent_low_rank_r384"]["relative_mse"] = float("nan")
        self.meta["per_seed_results"] = self.records
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            audit.quality_summary(self.records, self.meta)

    def test_nan_cannot_be_promoted_by_pass_flag(self):
        data = {"equivalence": [{"pass": True, "max_abs_err": 0}],
                "stability_1000_calls": {"pass": True, "completed": 1000, "final_max_abs_err": float("nan")}}
        self.assertFalse(audit.kernel_gate(data)["eligible_for_speedup_claim"])

    def test_empty_equivalence_fails(self):
        data = {"stability_1000_calls": {"pass": True, "completed": 1000, "final_max_abs_err": 0}}
        self.assertEqual(audit.kernel_gate(data)["verdict"], "FAIL")

    def test_failed_stability_blocks_finite_equivalence(self):
        data = {"equivalence": [{"pass": True, "max_abs_err": 0}],
                "stability_1000_calls": {"pass": False, "completed": 1000, "final_max_abs_err": 0}}
        self.assertEqual(audit.kernel_gate(data)["verdict"], "FAIL")

    def test_real_v4_failure_preserved(self):
        result = audit.collect(ROOT)
        # The superseded v2 record (NaN final error on ASI2) must remain FAIL.
        self.assertEqual(result["v4_kernel_superseded"]["verdict"], "FAIL")
        # The current hardened v3 re-run (ASI3, 2026-11-08) passes the same gate.
        self.assertEqual(result["v4_kernel"]["verdict"], "PASS")
        self.assertFalse(result["submission_ready"])
        json.dumps(result, allow_nan=False)

    def test_complete_numerical_gate_does_not_assert_materialized_speedup(self):
        path = ROOT / "results/v4_multicore_benchmark_asi2_v2_20261008.json"
        data = json.loads(path.read_text())
        data["stability_1000_calls"] = {"pass": True, "completed": 1000, "final_max_abs_err": 0}
        result = audit.kernel_gate(data)
        self.assertEqual(result["verdict"], "PASS")
        self.assertFalse(result["eligible_for_materialized_speedup_claim"])
        for key, value in [("completed", float("inf")), ("final_max_abs_err", 999)]:
            bad = copy.deepcopy(data)
            bad["stability_1000_calls"][key] = value
            self.assertEqual(audit.kernel_gate(bad)["verdict"], "FAIL")
        data["equivalence"][0]["max_abs_err"] = 999
        self.assertEqual(audit.kernel_gate(data)["verdict"], "FAIL")

    def test_current_v3_archive_passes_gate_without_speedup_eligibility(self):
        path = ROOT / "results/v4_multicore_benchmark_asi3_v3_20261108.json"
        data = json.loads(path.read_text())
        result = audit.kernel_gate(data)
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["completed_stability_calls"], 1000)
        self.assertTrue(result["finite_final_error"])
        self.assertFalse(result["eligible_for_speedup_claim"])
        self.assertFalse(result["eligible_for_materialized_speedup_claim"])

    def test_v2_failure_mutation_aborts_collect(self):
        # Rewriting history: if the superseded v2 record ever stops failing,
        # collect() must abort rather than silently accept the alteration.
        originals = [
            "results/v4_multicore_benchmark_asi2_v2_20261008.json",
            "results/v4_multicore_benchmark_asi3_v3_20261108.json",
            "results/ASI3_arm4_decisive_20260828/key_results_SHIPPED.json",
        ]
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            for rel in originals + [str(audit.QUALITY / "VERIFIED_RESULT_RECORD.json"),
                                    str(audit.QUALITY / "per_seed_results.json")]:
                dst = tmp_root / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(ROOT / rel, dst)
            for src in (ROOT / "results/asi2_opt_inclusive_sync_20260923T025114Z").glob(
                    "ASI2_mwg_transformer_*.json"):
                dst = tmp_root / "results/asi2_opt_inclusive_sync_20260923T025114Z" / src.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(src, dst)
            mutated = json.loads((tmp_root / originals[0]).read_text())
            mutated["stability_1000_calls"] = {"pass": True, "completed": 1000,
                                               "final_max_abs_err": 0.0}
            (tmp_root / originals[0]).write_text(json.dumps(mutated))
            with self.assertRaisesRegex(ValueError, "superseded"):
                audit.collect(tmp_root)

    def test_failed_gate_removes_stale_multicore_table(self):
        """A stale journal_multicore_rows.tex must not survive a failed gate."""
        import tempfile
        summary = {"quality": {"rows": [], "contrasts": []},
                   "v4_kernel": {"verdict": "FAIL",
                                 "observed_timing_only": [
                                     {"T": 128, "v1_ms": 0.1, "v4_ms": 0.1,
                                      "ratio_v1_over_v4": 1.0}]},
                   "optimizer_timing": {"rows": []}}
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            stale = folder / "journal_multicore_rows.tex"
            stale.write_text("stale content from a previously passing gate")
            with self.assertRaisesRegex(ValueError, "failed gate"):
                audit.emit_tables(summary, folder)
            self.assertFalse(stale.exists(),
                             "stale multicore table survived a failed gate")


if __name__ == "__main__":
    unittest.main()
