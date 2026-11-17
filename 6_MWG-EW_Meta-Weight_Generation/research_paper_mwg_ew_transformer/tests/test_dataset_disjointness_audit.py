"""Tests for the archived-artifact dataset-disjointness audit."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "experiments"))

from audit_dataset_disjointness import (  # noqa: E402
    cross_overlap_check,
    rederive_split,
    verify_regeneration_provenance,
)


def load_manifest():
    return json.loads((ROOT / "data/quality/manifest.json").read_text())


class RederivationTests(unittest.TestCase):
    def test_byte_exact_rederivation_matches_archived_files(self):
        manifest = load_manifest()
        derived = rederive_split(manifest)
        for split in ("train", "dev", "test"):
            disk = (ROOT / f"data/quality/{split}.txt").read_bytes()
            self.assertEqual(derived[split], disk,
                             f"{split} split is not byte-identical after "
                             f"re-derivation from the recorded parameters")

    def test_rederivation_uses_recorded_seed_and_fractions(self):
        manifest = load_manifest()
        self.assertEqual(manifest["seed"], 20260823)
        self.assertEqual(manifest["fractions"],
                         {"train": 0.5, "dev": 0.25, "test": 0.25})
        self.assertEqual(
            manifest["deduplication"]["near_duplicate_threshold"], 0.82)


class DisjointnessTests(unittest.TestCase):
    def test_cross_split_disjoint_under_recorded_metric(self):
        overlap = cross_overlap_check()
        for pair, metrics in overlap.items():
            self.assertEqual(metrics["exact_line_overlap"], 0, pair)
            self.assertEqual(metrics["near_duplicate_pairs_at_0.82"], 0, pair)

    def test_archived_split_audit_agrees(self):
        archived = json.loads(
            (ROOT / "results/asi2_causal_quality_closing_20261110T155855Z"
             / "split_audit.json").read_text())
        self.assertTrue(archived["ready"])
        for pair in ("train_vs_dev", "train_vs_test", "dev_vs_test"):
            self.assertEqual(archived["cross_split"][pair]["exact_overlap"], 0)
            self.assertEqual(
                archived["cross_split"][pair]["near_duplicate_pairs"], 0)


class ProvenanceTests(unittest.TestCase):
    def test_all_four_regeneration_seeds_share_the_frozen_split(self):
        per_seed = verify_regeneration_provenance()
        manifest = load_manifest()
        train_hash = manifest["outputs"]["train"]["sha256"]
        eval_hash = manifest["outputs"]["dev"]["sha256"]
        for seed in (2026, 2027, 2028, 2029):
            self.assertEqual(per_seed[seed]["recorded_train_sha256"],
                             train_hash, f"seed {seed} train split diverged")
            self.assertEqual(per_seed[seed]["recorded_eval_sha256"],
                             eval_hash, f"seed {seed} eval split diverged")
            self.assertEqual(per_seed[seed]["torch_seed"], seed)

    def test_seeds_vary_training_randomness_not_data(self):
        per_seed = verify_regeneration_provenance()
        seeds = [info["torch_seed"] for info in per_seed.values()]
        self.assertEqual(len(set(seeds)), 4, "training seeds must differ")
        train_hashes = {info["recorded_train_sha256"]
                        for info in per_seed.values()}
        self.assertEqual(len(train_hashes), 1,
                         "training data must be one shared frozen split")


class ReportTests(unittest.TestCase):
    def test_report_passes_and_pins_claim_boundary(self):
        report = json.loads(
            (ROOT / "results/journal_revision_20261022"
             / "dataset_disjointness_audit.json").read_text())
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["schema"],
                         "mwg-quality-split-disjointness-audit-v1")
        # The claim boundary must forbid over-claiming per-seed datasets.
        self.assertIn("no new model training", report["claim_boundary"])
        self.assertIn("not the design property",
                      report["design_note"])
        # Split hashes must match the frozen manifest.
        manifest = load_manifest()
        for split in ("train", "dev", "test"):
            self.assertEqual(report["split_hashes"][split],
                             manifest["outputs"][split]["sha256"])


if __name__ == "__main__":
    unittest.main()
