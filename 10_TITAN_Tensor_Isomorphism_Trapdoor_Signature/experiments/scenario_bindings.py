from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Tuple


def canonical_serialize(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_node_payload(index: int) -> dict[str, Any]:
    roles = ["scheduler", "worker", "worker", "scheduler"]
    return {
        "scenario": "quantum_network_node_admission",
        "certificate_digest": _sha256_hex(f"node-cert-{index}"),
        "node_id": f"qnode-{index:04d}",
        "node_role": roles[index % len(roles)],
        "scheduling_domain": "domain-a",
        "session_timestamp": 1710000000 + index,
        "handshake_nonce": _sha256_hex(f"nonce-{index}")[:32],
    }


def build_firmware_payload(index: int) -> dict[str, Any]:
    return {
        "scenario": "ai_accelerator_firmware_upgrade",
        "device_model": "CM-A100",
        "firmware_version": f"1.2.{index % 10}",
        "image_digest": _sha256_hex(f"firmware-image-{index}"),
        "rollback_counter": 5 + (index % 4),
        "release_timestamp": 1711000000 + index,
    }


def build_model_payload(index: int) -> dict[str, Any]:
    dependency_digest = _sha256_hex("torch=2.3.1;transformers=4.44.0;tokenizers=0.19.1")
    return {
        "scenario": "model_release_integrity",
        "model_id": f"cm-llm-{index:04d}",
        "weight_digest": _sha256_hex(f"model-weight-{index}"),
        "framework_version": "PyTorch-2.3.1",
        "target_accelerator": "Ascend-910B",
        "dependency_digest": dependency_digest,
        "release_tag": f"2026.04.{(index % 28) + 1:02d}",
    }


def node_policy_check(payload: dict[str, Any], expected_domain: str, allowed_roles: Iterable[str]) -> Tuple[bool, str]:
    if payload.get("scenario") != "quantum_network_node_admission":
        return False, "scenario_mismatch"
    if payload.get("scheduling_domain") != expected_domain:
        return False, "domain_mismatch"
    if payload.get("node_role") not in set(allowed_roles):
        return False, "role_not_allowed"
    if not payload.get("certificate_digest"):
        return False, "missing_certificate_digest"
    return True, "ok"


def firmware_policy_check(payload: dict[str, Any], expected_device_model: str, min_rollback_counter: int) -> Tuple[bool, str]:
    if payload.get("scenario") != "ai_accelerator_firmware_upgrade":
        return False, "scenario_mismatch"
    if payload.get("device_model") != expected_device_model:
        return False, "device_model_mismatch"
    rollback_counter = int(payload.get("rollback_counter", -1))
    if rollback_counter < min_rollback_counter:
        return False, "rollback_counter_too_small"
    if not payload.get("image_digest"):
        return False, "missing_image_digest"
    return True, "ok"


def model_policy_check(payload: dict[str, Any], expected_accelerator: str, expected_dependency_digest: str) -> Tuple[bool, str]:
    if payload.get("scenario") != "model_release_integrity":
        return False, "scenario_mismatch"
    if payload.get("target_accelerator") != expected_accelerator:
        return False, "accelerator_mismatch"
    if payload.get("dependency_digest") != expected_dependency_digest:
        return False, "dependency_digest_mismatch"
    if not payload.get("weight_digest"):
        return False, "missing_weight_digest"
    return True, "ok"
