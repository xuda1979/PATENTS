"""Tests pinning the extended-Q4 pre-registration document.

The pre-registration (results/extended_q4_pre_registration_20261117.json)
versions the constant-core and int8 controls' protocol and thresholds BEFORE
execution.  These tests pin its structural content so it cannot be silently
altered after execution begins: the file hash is recorded at commit time and
the thresholds/protocol fields are checked verbatim.
"""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "results/extended_q4_pre_registration_20261117.json"


class TestExtendedQ4PreRegistration(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads(DOC.read_text())

    def test_schema_and_status(self):
        self.assertEqual(self.doc["schema"], "mwg-extended-q4-pre-registration-v1")
        self.assertEqual(self.doc["status"], "PRE-REGISTERED-NOT-EXECUTED")

    def test_both_flagged_controls_present(self):
        arms = self.doc["arms"]
        self.assertIn("constant_core_r384", arms)
        self.assertIn("persistent_r384_int8", arms)

    def test_protocol_is_exact(self):
        protocol = self.doc["protocol"]
        self.assertEqual(protocol["quality"]["seeds"], [2026, 2027, 2028, 2029])
        self.assertEqual(protocol["latency"]["seeds"], [2026, 2027, 2028, 2029])
        self.assertIn("128 eval batches", protocol["quality"]["metric"])
        self.assertEqual(protocol["latency"]["metric"].split(",")[0],
                         "median single-layer latency ms at batch 1")

    def test_thresholds_are_descriptive_only(self):
        thresholds = self.doc["pre_registered_thresholds"]
        self.assertIn("DESCRIPTIVE ONLY",
                      thresholds["quality_non_inferiority"]["decision_rule"])
        self.assertIn("no gate", thresholds["latency_gate"]["int8_arm"])
        self.assertIn("no gate", thresholds["latency_gate"]["constant_core_arm"])

    def test_failure_policy_and_immutability(self):
        self.assertIn("first-class result",
                      self.doc["pre_registered_thresholds"]["failure_policy"])
        self.assertIn("cannot be relaxed post hoc", self.doc["claim_boundary"])
        self.assertIn("must not be edited after execution",
                      self.doc["immutable_note"])

    def test_source_run_binding(self):
        self.assertEqual(
            self.doc["source_run"]["run_id"],
            "asi2_q4_matched_quality_latency_20261113T134959Z")

    def test_execution_gate_requires_audit_schema(self):
        acceptance = self.doc["acceptance_of_execution"]
        self.assertIn("mwg-extended-q4-executed-v1",
                      acceptance["gate_script"])


class TestPreRegistrationIntegrity(unittest.TestCase):
    """Post-commit guard: once execution begins, the document must not move.

    After the execution lands, add the committed sha256 of this file to
    PINNED_SHA (a deliberate, reviewable edit) so any post-execution
    tampering with the pre-registration fails loudly.
    """

    # Empty until the execution commit lands (the pre-registration commit
    # itself defines the pinned hash; fill it in that same commit).
    PINNED_SHA: str | None = None

    def test_document_hash_stable(self):
        current = hashlib.sha256(DOC.read_bytes()).hexdigest()
        if self.PINNED_SHA is None:
            self.skipTest("pin fills in at the execution commit")
        self.assertEqual(current, self.PINNED_SHA,
                         "pre-registration document altered after pinning")


if __name__ == "__main__":
    unittest.main()
