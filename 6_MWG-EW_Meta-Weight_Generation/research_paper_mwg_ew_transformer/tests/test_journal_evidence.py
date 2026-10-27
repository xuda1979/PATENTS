import copy
import importlib.util
import json
from pathlib import Path
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
        self.assertEqual(result["v4_kernel"]["verdict"], "FAIL")
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


if __name__ == "__main__":
    unittest.main()
