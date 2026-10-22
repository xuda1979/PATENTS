"""Regression for scratch cardinality incorrectly counted as global traffic."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
from mwg_regime_map import AccountingConfig, WorkloadCase, compute_row


class GlobalTrafficTests(unittest.TestCase):
    def test_scratch_descriptor_is_not_a_global_transfer(self):
        row = compute_row(WorkloadCase("training", 2, 5, 2),
                          AccountingConfig(8, 16, 2, 4))
        common = (row["scheduled_persistent_factor_bytes"]
                  + row["scheduled_controller_bytes"] + row["source_state_bytes"])
        self.assertEqual(row["diagonal_core_scheduled_no_store_bytes"], common)
        self.assertEqual(row["diagonal_core_scheduled_materialized_bytes"],
                         common + 2 * row["diagonal_core_generated_bytes"])
        self.assertEqual(row["full_factor_scheduled_no_store_bytes"],
                         row["scheduled_controller_bytes"] + row["source_state_bytes"])


if __name__ == "__main__":
    unittest.main()
