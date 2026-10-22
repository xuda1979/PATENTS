"""Acceptance contract for actual-MWG CPU rematerialization evidence."""
import sys
import unittest
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
import measure_journal_lifecycle as lifecycle
from mwg_quality_distillation import LowRankFFN


class LifecycleContract(unittest.TestCase):
    def test_unique_storage_excludes_parameter_aliases(self):
        parameter = torch.nn.Parameter(torch.ones(2, 4))
        activation = torch.ones(3, 4)
        ledger = lifecycle.SavedStorageLedger([parameter])
        ledger.pack(parameter)
        ledger.pack(parameter.t())
        ledger.pack(activation)
        ledger.pack(activation[:, :2])
        ledger.pack(torch.empty(0))
        self.assertEqual(ledger.snapshot()["unique_storage_bytes"], 48)
        self.assertEqual(ledger.snapshot()["unique_storages"], 1)
        self.assertEqual(ledger.snapshot()["excluded_parameter_references"], 2)

    def test_real_model_checkpoint_contract(self):
        self.assertIs(lifecycle.LowRankFFN, LowRankFFN)
        result = lifecycle.measure_case(seed=2026, depth=2)
        self.assertTrue(result["passed"])
        self.assertGreater(result["eager"]["unique_storage_bytes"],
                           result["checkpoint"]["unique_storage_bytes"])
        self.assertGreater(result["controller_context_max_abs_delta"], 0)
        self.assertGreater(result["controller_gradient_l1"], 0)
        self.assertEqual(result["validated_parameter_gradients"], 20)

    def test_corrupted_gradient_fails_validation(self):
        template, x, target = lifecycle.make_case(seed=17, depth=1)
        eager = lifecycle.run_arm(template, x, target, checkpointed=False)
        candidate = lifecycle.run_arm(template, x, target, checkpointed=True)
        candidate["gradients"][next(iter(candidate["gradients"]))].fill_(float("nan"))
        with self.assertRaisesRegex(AssertionError, "non-finite"):
            lifecycle.validate_pair(eager, candidate)

    def test_missing_gradient_fails_validation(self):
        template, x, target = lifecycle.make_case(seed=18, depth=1)
        eager = lifecycle.run_arm(template, x, target, checkpointed=False)
        candidate = lifecycle.run_arm(template, x, target, checkpointed=True)
        candidate["gradients"].pop(next(iter(candidate["gradients"])))
        with self.assertRaisesRegex(AssertionError, "gradient names"):
            lifecycle.validate_pair(eager, candidate)


if __name__ == "__main__":
    unittest.main()
