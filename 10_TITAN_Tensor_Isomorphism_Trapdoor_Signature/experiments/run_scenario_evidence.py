from __future__ import annotations

import copy
import json
from pathlib import Path
from statistics import mean

from scenario_bindings import (
    build_firmware_payload,
    build_model_payload,
    build_node_payload,
    canonical_serialize,
    firmware_policy_check,
    model_policy_check,
    node_policy_check,
)

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
SUMMARY_PATH = RESULTS / "summary.json"
OUT_JSON = RESULTS / "scenario_evidence.json"
OUT_MD = RESULTS / "scenario_evidence.md"


def node_bad_payload(i: int):
    payload = build_node_payload(i)
    payload["scheduling_domain"] = "domain-z"
    return payload


def firmware_bad_payload(i: int):
    payload = build_firmware_payload(i)
    payload["rollback_counter"] = 3
    return payload


def model_bad_payload(i: int):
    payload = build_model_payload(i)
    payload["dependency_digest"] = "deadbeef"
    return payload


def evaluate(name, build_ok, build_bad, checker, checker_kwargs, mapped_scheme):
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    scheme = summary["schemes"][mapped_scheme]
    valid_lengths = []
    valid_accept = 0
    invalid_reject = 0
    sample_valid = build_ok(0)
    sample_invalid = build_bad(0)
    last_invalid_reason = None

    for i in range(50):
        payload = build_ok(i)
        valid_lengths.append(len(canonical_serialize(payload)))
        ok, _ = checker(payload, **checker_kwargs)
        valid_accept += int(ok)

        bad = build_bad(i)
        ok_bad, reason_bad = checker(bad, **checker_kwargs)
        invalid_reject += int(not ok_bad)
        last_invalid_reason = reason_bad

    return {
        "scenario": name,
        "mapped_scheme": mapped_scheme,
        "structured_payload_bytes": {
            "min": min(valid_lengths),
            "max": max(valid_lengths),
            "mean": round(mean(valid_lengths), 2),
        },
        "policy_experiment": {
            "valid_accept_count": valid_accept,
            "valid_total": 50,
            "invalid_reject_count": invalid_reject,
            "invalid_total": 50,
            "invalid_reason": last_invalid_reason,
        },
        "signature_experiment_from_existing_real_benchmark": {
            "verify_success_count": scheme["correctness"]["verify_success_count"],
            "verify_total": scheme["correctness"]["verify_total"],
            "tampered_msg_reject_count": scheme["correctness"]["tampered_msg_reject_count"],
            "tampered_sig_reject_count": scheme["correctness"]["tampered_sig_reject_count"],
            "verify_mean_ms": scheme["verify"]["mean_ms"],
            "verify_p95_ms": scheme["verify"]["p95_ms"],
            "verify_throughput_sig_s": scheme["verify_throughput_sig_s"],
            "pk_bytes": scheme["sizes"]["pk_bytes"],
            "sig_bytes": scheme["sizes"]["sig_bytes"],
        },
        "sample_valid_payload": sample_valid,
        "sample_invalid_payload": sample_invalid,
    }


def main():
    evidence = {
        "source_summary": str(SUMMARY_PATH),
        "note": "Policy experiment executed locally with Python standard library. Signature metrics are imported from the repository's existing real benchmark summary.json.",
        "scenarios": [
            evaluate(
                name="量子计算网络节点准入",
                build_ok=build_node_payload,
                build_bad=node_bad_payload,
                checker=node_policy_check,
                checker_kwargs={"expected_domain": "domain-a", "allowed_roles": {"scheduler", "worker"}},
                mapped_scheme="titan-n8-r16",
            ),
            evaluate(
                name="AI加速设备固件升级",
                build_ok=build_firmware_payload,
                build_bad=firmware_bad_payload,
                checker=firmware_policy_check,
                checker_kwargs={"expected_device_model": "CM-A100", "min_rollback_counter": 5},
                mapped_scheme="titan-n10-r32",
            ),
            evaluate(
                name="模型发布完整性校验",
                build_ok=build_model_payload,
                build_bad=model_bad_payload,
                checker=model_policy_check,
                checker_kwargs={"expected_accelerator": "Ascend-910B", "expected_dependency_digest": build_model_payload(0)["dependency_digest"]},
                mapped_scheme="titan-n12-r32",
            ),
        ],
    }
    OUT_JSON.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Scenario-Coupled Evidence",
        "",
        evidence["note"],
        "",
    ]
    for item in evidence["scenarios"]:
        sig = item["signature_experiment_from_existing_real_benchmark"]
        pol = item["policy_experiment"]
        lines.extend([
            f"## {item['scenario']}",
            f"- Mapped TITAN point: {item['mapped_scheme']}",
            f"- Structured payload bytes: min={item['structured_payload_bytes']['min']}, max={item['structured_payload_bytes']['max']}, mean={item['structured_payload_bytes']['mean']}",
            f"- Policy experiment: valid accept {pol['valid_accept_count']}/{pol['valid_total']}, invalid reject {pol['invalid_reject_count']}/{pol['invalid_total']} (reason={pol['invalid_reason']})",
            f"- Signature experiment: verify {sig['verify_success_count']}/{sig['verify_total']}, tampered message reject {sig['tampered_msg_reject_count']}/{sig['verify_total']}, tampered signature reject {sig['tampered_sig_reject_count']}/{sig['verify_total']}",
            f"- Verify latency: mean={sig['verify_mean_ms']} ms, p95={sig['verify_p95_ms']} ms, throughput={sig['verify_throughput_sig_s']} sig/s",
            "",
        ])
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] wrote {OUT_JSON}")
    print(f"[OK] wrote {OUT_MD}")


if __name__ == "__main__":
    main()
