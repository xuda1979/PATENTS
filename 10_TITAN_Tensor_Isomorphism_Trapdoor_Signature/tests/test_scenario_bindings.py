import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / 'experiments'
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

from scenario_bindings import (
    build_node_payload,
    canonical_serialize,
    node_policy_check,
    firmware_policy_check,
    model_policy_check,
    build_firmware_payload,
    build_model_payload,
)


class ScenarioBindingsTests(unittest.TestCase):
    def test_canonical_serialize_is_stable_for_same_payload_content(self):
        payload_a = build_node_payload(0)
        payload_b = dict(reversed(list(payload_a.items())))
        self.assertEqual(canonical_serialize(payload_a), canonical_serialize(payload_b))

    def test_node_policy_rejects_wrong_domain_even_if_payload_is_well_formed(self):
        payload = build_node_payload(1)
        bad = copy.deepcopy(payload)
        bad['scheduling_domain'] = 'domain-z'
        ok, reason = node_policy_check(bad, expected_domain='domain-a', allowed_roles={'scheduler', 'worker'})
        self.assertFalse(ok)
        self.assertEqual(reason, 'domain_mismatch')

    def test_firmware_policy_rejects_rollback_version(self):
        payload = build_firmware_payload(2)
        bad = copy.deepcopy(payload)
        bad['firmware_version'] = '1.0.0'
        bad['rollback_counter'] = 3
        ok, reason = firmware_policy_check(bad, expected_device_model='CM-A100', min_rollback_counter=5)
        self.assertFalse(ok)
        self.assertEqual(reason, 'rollback_counter_too_small')

    def test_model_policy_rejects_dependency_digest_mismatch(self):
        payload = build_model_payload(3)
        bad = copy.deepcopy(payload)
        bad['dependency_digest'] = 'deadbeef'
        ok, reason = model_policy_check(bad, expected_accelerator='Ascend-910B', expected_dependency_digest=payload['dependency_digest'])
        self.assertFalse(ok)
        self.assertEqual(reason, 'dependency_digest_mismatch')


if __name__ == '__main__':
    unittest.main()
