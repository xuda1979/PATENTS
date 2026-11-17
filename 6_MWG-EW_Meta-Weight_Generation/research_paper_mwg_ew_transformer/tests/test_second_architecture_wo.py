"""Acceptance contract for the second-architecture (attention W_O) audit."""
import json
import sys
import unittest
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
import audit_second_architecture_wo as wo

REPORT = (ROOT / "results/second_architecture_wo_cpu_20261116"
          / "second_architecture_wo_audit.json")


class FixtureTests(unittest.TestCase):
    def test_dense_reference_matches_blocks(self):
        factors, w_blocks, x, y_dense = wo.make_fixture(2026)
        for h in range(wo.HEADS):
            sl = slice(h * wo.HEAD_DIM, (h + 1) * wo.HEAD_DIM)
            y_h = x[..., sl] @ w_blocks[h]
            self.assertTrue(torch.equal(y_dense[..., sl], y_h))

    def test_module_does_not_mutate_caller_factors(self):
        factors, w_blocks, x, y_dense = wo.make_fixture(2026)
        before = [f.clone() for f in factors]
        model = wo.PerHeadLowRankAttentionOut(
            factors, wo.PerHeadController(wo.HEADS, wo.HEAD_DIM,
                                          wo.RANK_PER_HEAD, wo.ALPHA),
            wo.HEADS, wo.RANK_PER_HEAD, True, torch.float64)
        opt = torch.optim.Adam(model.parameters(), lr=1e-2)
        for _ in range(5):
            opt.zero_grad()
            ((model(x) - y_dense) ** 2).mean().backward()
            opt.step()
        for b, a in zip(before, factors):
            self.assertTrue(torch.equal(b, a))

    def test_error_budget_is_additive_for_in_subspace_output(self):
        # A valid model output: coefficients in the row space of the final
        # factor, deliberately non-optimal so the within-subspace term is
        # strictly positive.
        factors, w_blocks, x, y_dense = wo.make_fixture(2027)
        h = 0
        sl = slice(h * wo.HEAD_DIM, (h + 1) * wo.HEAD_DIM)
        x_h = x[..., sl]
        coeffs = torch.randn(*x_h.shape[:-1], wo.RANK_PER_HEAD,
                             dtype=torch.float64)
        y_hat = (coeffs @ factors[2 * h + 1].double())
        budget = wo.head_error_budget(
            y_dense[..., sl], y_hat,
            factors[2 * h].double(), factors[2 * h + 1].double(),
            wo.RANK_PER_HEAD)
        total = (budget["rank_loss_rel"] + budget["subspace_selection_rel"]
                 + budget["within_subspace_fit_rel"])
        self.assertAlmostEqual(budget["actual_rel"], total, places=12)
        self.assertGreater(budget["within_subspace_fit_rel"], 0)

    def test_error_budget_rejects_out_of_subspace_output(self):
        factors, w_blocks, x, y_dense = wo.make_fixture(2027)
        h = 0
        sl = slice(h * wo.HEAD_DIM, (h + 1) * wo.HEAD_DIM)
        y_bad = y_dense[..., sl] * 0.9  # leaves the factor's row space
        with self.assertRaises(ValueError):
            wo.head_error_budget(
                y_dense[..., sl], y_bad,
                factors[2 * h].double(), factors[2 * h + 1].double(),
                wo.RANK_PER_HEAD)

    def test_capacity_compensation_respects_budget(self):
        factors, w_blocks, x, y_dense = wo.make_fixture(2026)
        row = wo.measure_q1_contrast(2026)
        self.assertLessEqual(row["persistent_compensated_parameter_count"],
                             row["conditioned_parameter_count"])
        self.assertGreater(row["persistent_compensated_rank"],
                           row["persistent_rank"])


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT.read_text())

    def test_report_schema_and_status(self):
        self.assertEqual(self.report["schema"],
                         "mwg-second-architecture-wo-audit-v2")
        self.assertEqual(self.report["status"], "PASS")
        self.assertEqual(self.report["evidence_kind"],
                         "cpu_synthetic_fixture_audit_demonstration")
        self.assertTrue(self.report["source_script_sha256"])

    def test_q1_rows_training_matched_and_finite(self):
        rows = self.report["q1_matched_contrast"]
        self.assertEqual([r["seed"] for r in rows], [2026, 2027, 2028])
        for r in rows:
            for field in ("persistent_rel_mse", "conditioned_rel_mse",
                          "persistent_compensated_rel_mse",
                          "static_svd_rel_mse"):
                self.assertTrue(
                    isinstance(r[field], float) and r[field] > 0
                    and r[field] == r[field], msg=field)
            self.assertLess(abs(r["conditioned_minus_persistent"]), 1e-4)

    def test_error_budgets_additive_in_report(self):
        for r in self.report["q1_matched_contrast"]:
            for key in ("head_error_budgets_conditioned",
                        "head_error_budgets_persistent",
                        "head_error_budgets_persistent_compensated"):
                for b in r[key]:
                    total = (b["rank_loss_rel"] + b["subspace_selection_rel"]
                             + b["within_subspace_fit_rel"])
                    self.assertAlmostEqual(b["actual_rel"], total, places=12)

    def test_constant_core_not_better_than_learned(self):
        for r in self.report["constant_core_control"]:
            self.assertGreaterEqual(r["constant_minus_conditioned"], -1e-9)

    def test_q3_identity_exact(self):
        for r in self.report["q3_checkpointing_identity"]:
            self.assertTrue(r["passed"])
            self.assertEqual(r["max_output_abs_delta"], 0.0)
            self.assertEqual(r["max_gradient_abs_delta"], 0.0)

    def test_claim_boundary_recorded(self):
        cb = self.report["claim_boundary"]
        self.assertIn("CPU synthetic fixture", cb["evidence_class"])
        for banned in ("accelerator latency", "perplexity"):
            self.assertIn(banned, cb["not_measured"])


if __name__ == "__main__":
    unittest.main()
