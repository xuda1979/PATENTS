from __future__ import annotations

import copy
import csv
import json
import subprocess
from pathlib import Path
from statistics import mean
from typing import Any, Callable

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
RESULTS.mkdir(exist_ok=True)
SUMMARY_PATH = RESULTS / "summary.json"
OUT_JSON = RESULTS / "scenario_summary.json"
OUT_CSV = RESULTS / "scenario_raw.csv"
OUT_MD = RESULTS / "scenario_summary.md"
CORRECTNESS_TEX = RESULTS / "scenario_correctness_chart.tex"
METRICS_TEX = RESULTS / "scenario_metrics_chart.tex"
CORRECTNESS_PDF = RESULTS / "scenario_correctness_chart.pdf"
METRICS_PDF = RESULTS / "scenario_metrics_chart.pdf"

PayloadBuilder = Callable[[int], dict[str, Any]]
PolicyChecker = Callable[..., tuple[bool, str]]
TamperFunc = Callable[[dict[str, Any], int], dict[str, Any]]


def _quoted_label(text: str) -> str:
    return "{" + text.replace("_", r"\_") + "}"


def _pct(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator * 100.0 / denominator, 2)


def _parse_index(text: str, prefix: str) -> int:
    if not text.startswith(prefix):
        raise ValueError(f"unexpected identifier {text!r}")
    return int(text[len(prefix):])


def node_tamper_domain(payload: dict[str, Any], _: int) -> dict[str, Any]:
    payload = copy.deepcopy(payload)
    payload["scheduling_domain"] = "domain-z"
    return payload


def node_tamper_role(payload: dict[str, Any], _: int) -> dict[str, Any]:
    payload = copy.deepcopy(payload)
    payload["node_role"] = "observer"
    return payload


def node_tamper_certificate(payload: dict[str, Any], index: int) -> dict[str, Any]:
    payload = copy.deepcopy(payload)
    payload["certificate_digest"] = f"tampered-cert-{index:04d}"
    return payload


def firmware_tamper_model(payload: dict[str, Any], _: int) -> dict[str, Any]:
    payload = copy.deepcopy(payload)
    payload["device_model"] = "CM-A200"
    return payload


def firmware_tamper_counter(payload: dict[str, Any], _: int) -> dict[str, Any]:
    payload = copy.deepcopy(payload)
    payload["rollback_counter"] = 3
    return payload


def firmware_tamper_digest(payload: dict[str, Any], index: int) -> dict[str, Any]:
    payload = copy.deepcopy(payload)
    payload["image_digest"] = f"tampered-image-{index:04d}"
    return payload


def model_tamper_accelerator(payload: dict[str, Any], _: int) -> dict[str, Any]:
    payload = copy.deepcopy(payload)
    payload["target_accelerator"] = "Ascend-310P"
    return payload


def model_tamper_dependency(payload: dict[str, Any], _: int) -> dict[str, Any]:
    payload = copy.deepcopy(payload)
    payload["dependency_digest"] = "deadbeef"
    return payload


def model_tamper_weight(payload: dict[str, Any], index: int) -> dict[str, Any]:
    payload = copy.deepcopy(payload)
    payload["weight_digest"] = f"tampered-weight-{index:04d}"
    return payload


def node_scenario_policy_check(payload: dict[str, Any]) -> tuple[bool, str]:
    ok, reason = node_policy_check(payload, expected_domain="domain-a", allowed_roles={"scheduler", "worker"})
    if not ok:
        return ok, reason
    index = _parse_index(str(payload.get("node_id", "")), "qnode-")
    expected = build_node_payload(index)["certificate_digest"]
    if payload.get("certificate_digest") != expected:
        return False, "certificate_registry_mismatch"
    return True, "ok"


def firmware_scenario_policy_check(payload: dict[str, Any]) -> tuple[bool, str]:
    ok, reason = firmware_policy_check(payload, expected_device_model="CM-A100", min_rollback_counter=5)
    if not ok:
        return ok, reason
    index = int(payload.get("release_timestamp", 1711000000)) - 1711000000
    expected = build_firmware_payload(index)["image_digest"]
    if payload.get("image_digest") != expected:
        return False, "image_digest_registry_mismatch"
    return True, "ok"


def model_scenario_policy_check(payload: dict[str, Any]) -> tuple[bool, str]:
    expected_dependency_digest = build_model_payload(0)["dependency_digest"]
    ok, reason = model_policy_check(
        payload,
        expected_accelerator="Ascend-910B",
        expected_dependency_digest=expected_dependency_digest,
    )
    if not ok:
        return ok, reason
    index = _parse_index(str(payload.get("model_id", "")), "cm-llm-")
    expected = build_model_payload(index)["weight_digest"]
    if payload.get("weight_digest") != expected:
        return False, "weight_digest_registry_mismatch"
    return True, "ok"


def scenario_definitions() -> list[dict[str, Any]]:
    return [
        {
            "scenario_name": "量子计算网络节点准入",
            "scenario_code": "quantum_network_node_admission",
            "deployment_entry": "节点准入控制器",
            "mapped_scheme": "titan-n8-r16",
            "build_payload": build_node_payload,
            "checker": node_scenario_policy_check,
            "checker_kwargs": {},
            "tamper_cases": [
                {"field": "scheduling_domain", "name": "调度域篡改", "mutator": node_tamper_domain},
                {"field": "node_role", "name": "节点角色篡改", "mutator": node_tamper_role},
                {"field": "certificate_digest", "name": "证书摘要篡改", "mutator": node_tamper_certificate},
            ],
        },
        {
            "scenario_name": "AI加速设备固件升级",
            "scenario_code": "ai_accelerator_firmware_upgrade",
            "deployment_entry": "可信启动链/升级代理",
            "mapped_scheme": "titan-n10-r32",
            "build_payload": build_firmware_payload,
            "checker": firmware_scenario_policy_check,
            "checker_kwargs": {},
            "tamper_cases": [
                {"field": "device_model", "name": "设备型号篡改", "mutator": firmware_tamper_model},
                {"field": "rollback_counter", "name": "回滚计数器篡改", "mutator": firmware_tamper_counter},
                {"field": "image_digest", "name": "镜像摘要篡改", "mutator": firmware_tamper_digest},
            ],
        },
        {
            "scenario_name": "模型发布完整性校验",
            "scenario_code": "model_release_integrity",
            "deployment_entry": "模型仓库发布/下载校验代理",
            "mapped_scheme": "titan-n12-r32",
            "build_payload": build_model_payload,
            "checker": model_scenario_policy_check,
            "checker_kwargs": {},
            "tamper_cases": [
                {"field": "target_accelerator", "name": "目标加速器篡改", "mutator": model_tamper_accelerator},
                {"field": "dependency_digest", "name": "依赖摘要篡改", "mutator": model_tamper_dependency},
                {"field": "weight_digest", "name": "权重摘要篡改", "mutator": model_tamper_weight},
            ],
        },
    ]


def evaluate_scenario(defn: dict[str, Any], imported_summary: dict[str, Any], iterations: int = 50) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    scheme = imported_summary["schemes"][defn["mapped_scheme"]]
    rows: list[dict[str, Any]] = []
    payload_sizes: list[int] = []
    valid_accept_count = 0
    valid_signature_verify_count = scheme["correctness"]["verify_success_count"]
    valid_signature_verify_total = scheme["correctness"]["verify_total"]
    tampered_signature_reject_count = scheme["correctness"]["tampered_msg_reject_count"]
    tampered_signature_reject_total = scheme["correctness"]["verify_total"]

    tamper_summary: dict[str, dict[str, Any]] = {}
    for tamper_case in defn["tamper_cases"]:
        tamper_summary[tamper_case["field"]] = {
            "field": tamper_case["field"],
            "tamper_name": tamper_case["name"],
            "reject_count": 0,
            "total": 0,
            "reasons": {},
            "sample_payload": None,
        }

    for index in range(iterations):
        payload = defn["build_payload"](index)
        payload_bytes = len(canonical_serialize(payload))
        payload_sizes.append(payload_bytes)
        ok, reason = defn["checker"](payload, **defn["checker_kwargs"])
        valid_accept_count += int(ok)
        rows.append(
            {
                "scenario": defn["scenario_name"],
                "scenario_code": defn["scenario_code"],
                "deployment_entry": defn["deployment_entry"],
                "mapped_scheme": defn["mapped_scheme"],
                "record_type": "valid",
                "iteration": index + 1,
                "tamper_field": "",
                "tamper_name": "",
                "payload_bytes": payload_bytes,
                "policy_accept": int(ok),
                "policy_reason": reason,
                "verify_success_baseline": scheme["correctness"]["verify_success_count"],
                "verify_total_baseline": scheme["correctness"]["verify_total"],
                "tampered_message_reject_baseline": scheme["correctness"]["tampered_msg_reject_count"],
                "tampered_signature_reject_baseline": scheme["correctness"]["tampered_sig_reject_count"],
                "sign_mean_ms": scheme["sign"]["mean_ms"],
                "verify_mean_ms": scheme["verify"]["mean_ms"],
                "verify_p95_ms": scheme["verify"]["p95_ms"],
                "verify_throughput_sig_s": scheme["verify_throughput_sig_s"],
                "pk_bytes": scheme["sizes"]["pk_bytes"],
                "sig_bytes": scheme["sizes"]["sig_bytes"],
            }
        )

        for tamper_case in defn["tamper_cases"]:
            tampered_payload = tamper_case["mutator"](payload, index)
            tampered_bytes = len(canonical_serialize(tampered_payload))
            ok_bad, reason_bad = defn["checker"](tampered_payload, **defn["checker_kwargs"])
            summary_item = tamper_summary[tamper_case["field"]]
            summary_item["reject_count"] += int(not ok_bad)
            summary_item["total"] += 1
            summary_item["reasons"][reason_bad] = summary_item["reasons"].get(reason_bad, 0) + 1
            if summary_item["sample_payload"] is None:
                summary_item["sample_payload"] = tampered_payload
            rows.append(
                {
                    "scenario": defn["scenario_name"],
                    "scenario_code": defn["scenario_code"],
                    "deployment_entry": defn["deployment_entry"],
                    "mapped_scheme": defn["mapped_scheme"],
                    "record_type": "tampered",
                    "iteration": index + 1,
                    "tamper_field": tamper_case["field"],
                    "tamper_name": tamper_case["name"],
                    "payload_bytes": tampered_bytes,
                    "policy_accept": int(ok_bad),
                    "policy_reason": reason_bad,
                    "verify_success_baseline": scheme["correctness"]["verify_success_count"],
                    "verify_total_baseline": scheme["correctness"]["verify_total"],
                    "tampered_message_reject_baseline": scheme["correctness"]["tampered_msg_reject_count"],
                    "tampered_signature_reject_baseline": scheme["correctness"]["tampered_sig_reject_count"],
                    "sign_mean_ms": scheme["sign"]["mean_ms"],
                    "verify_mean_ms": scheme["verify"]["mean_ms"],
                    "verify_p95_ms": scheme["verify"]["p95_ms"],
                    "verify_throughput_sig_s": scheme["verify_throughput_sig_s"],
                    "pk_bytes": scheme["sizes"]["pk_bytes"],
                    "sig_bytes": scheme["sizes"]["sig_bytes"],
                }
            )

    total_tampered = sum(item["total"] for item in tamper_summary.values())
    total_tampered_reject = sum(item["reject_count"] for item in tamper_summary.values())
    breakdown = []
    for item in tamper_summary.values():
        dominant_reason = max(item["reasons"], key=item["reasons"].get) if item["reasons"] else ""
        breakdown.append(
            {
                "field": item["field"],
                "tamper_name": item["tamper_name"],
                "reject_count": item["reject_count"],
                "total": item["total"],
                "reject_rate_pct": _pct(item["reject_count"], item["total"]),
                "dominant_reason": dominant_reason,
                "sample_payload": item["sample_payload"],
            }
        )

    breakdown.sort(key=lambda item: item["field"])
    scenario_summary = {
        "scenario": defn["scenario_name"],
        "scenario_code": defn["scenario_code"],
        "deployment_entry": defn["deployment_entry"],
        "mapped_scheme": defn["mapped_scheme"],
        "iterations": iterations,
        "structured_payload_bytes": {
            "min": min(payload_sizes),
            "max": max(payload_sizes),
            "mean": round(mean(payload_sizes), 2),
        },
        "valid_payload_policy_experiment": {
            "accept_count": valid_accept_count,
            "total": iterations,
            "accept_rate_pct": _pct(valid_accept_count, iterations),
        },
        "field_tampering_policy_experiment": {
            "reject_count": total_tampered_reject,
            "total": total_tampered,
            "reject_rate_pct": _pct(total_tampered_reject, total_tampered),
            "breakdown": breakdown,
        },
        "imported_signature_benchmark": {
            "source_summary": str(SUMMARY_PATH),
            "verify_success_count": valid_signature_verify_count,
            "verify_total": valid_signature_verify_total,
            "verify_success_rate_pct": _pct(valid_signature_verify_count, valid_signature_verify_total),
            "tampered_message_reject_count": tampered_signature_reject_count,
            "tampered_message_reject_total": tampered_signature_reject_total,
            "tampered_message_reject_rate_pct": _pct(tampered_signature_reject_count, tampered_signature_reject_total),
            "tampered_signature_reject_count": scheme["correctness"]["tampered_sig_reject_count"],
            "tampered_signature_reject_rate_pct": _pct(scheme["correctness"]["tampered_sig_reject_count"], valid_signature_verify_total),
            "sign_mean_ms": scheme["sign"]["mean_ms"],
            "sign_p95_ms": scheme["sign"]["p95_ms"],
            "verify_mean_ms": scheme["verify"]["mean_ms"],
            "verify_p95_ms": scheme["verify"]["p95_ms"],
            "verify_throughput_sig_s": scheme["verify_throughput_sig_s"],
            "pk_bytes": scheme["sizes"]["pk_bytes"],
            "sig_bytes": scheme["sizes"]["sig_bytes"],
        },
        "sample_valid_payload": defn["build_payload"](0),
    }
    return scenario_summary, rows


def write_csv(rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "scenario",
        "scenario_code",
        "deployment_entry",
        "mapped_scheme",
        "record_type",
        "iteration",
        "tamper_field",
        "tamper_name",
        "payload_bytes",
        "policy_accept",
        "policy_reason",
        "verify_success_baseline",
        "verify_total_baseline",
        "tampered_message_reject_baseline",
        "tampered_signature_reject_baseline",
        "sign_mean_ms",
        "verify_mean_ms",
        "verify_p95_ms",
        "verify_throughput_sig_s",
        "pk_bytes",
        "sig_bytes",
    ]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def render_correctness_chart(summary: dict[str, Any]) -> None:
    scenarios = summary["scenarios"]
    bar_colors = ["blue!55", "green!60!black", "orange!75", "red!65"]
    legend_labels = [
        "有效载荷策略放行率",
        "字段级篡改策略拒绝率",
        "原始签名验证成功率",
        "篡改消息验签拒绝率",
    ]
    label_map = {
        "quantum_network_node_admission": r"\shortstack{量子计算网络\\节点准入}",
        "ai_accelerator_firmware_upgrade": r"\shortstack{AI加速设备\\固件升级}",
        "model_release_integrity": r"\shortstack{模型发布\\完整性校验}",
    }
    group_starts = [1.1, 5.1, 9.1]
    bar_width = 0.34
    bar_gap = 0.12
    group_span = 4 * bar_width + 3 * bar_gap
    metric_extractors = [
        lambda item: item["valid_payload_policy_experiment"]["accept_rate_pct"],
        lambda item: item["field_tampering_policy_experiment"]["reject_rate_pct"],
        lambda item: item["imported_signature_benchmark"]["verify_success_rate_pct"],
        lambda item: item["imported_signature_benchmark"]["tampered_message_reject_rate_pct"],
    ]
    body = []
    for idx, item in enumerate(scenarios):
        start = group_starts[idx]
        for metric_idx, extractor in enumerate(metric_extractors):
            value = float(extractor(item))
            x0 = start + metric_idx * (bar_width + bar_gap)
            x1 = x0 + bar_width
            body.append(
                f"\\filldraw[fill={bar_colors[metric_idx]}, draw=black!35] ({x0:.2f},0) rectangle ({x1:.2f},{value:.2f});"
            )
            body.append(
                f"\\node[font=\scriptsize, rotate=90] at ({(x0+x1)/2:.2f},{min(value + 4.0, 103.0):.2f}) {{{value:.1f}}};"
            )
        body.append(
            f"\\node[align=center, font=\small] at ({start + group_span/2:.2f},-11.5) {{{label_map.get(item['scenario_code'], item['scenario'])}}};"
        )
    legend = []
    legend_x = 0.6
    for i, label in enumerate(legend_labels):
        y = -18 - i * 4.2
        legend.append(f"\\filldraw[fill={bar_colors[i]}, draw=black!35] ({legend_x:.2f},{y:.2f}) rectangle ({legend_x+0.45:.2f},{y+1.2:.2f});")
        legend.append(f"\\node[anchor=west, font=\small] at ({legend_x+0.65:.2f},{y+0.6:.2f}) {{{label}}};")
    tex = rf"""
\documentclass[12pt]{{article}}
\usepackage[UTF8]{{ctex}}
\usepackage[paperwidth=18cm,paperheight=10.5cm,margin=0.4cm]{{geometry}}
\usepackage{{tikz}}
\begin{{document}}
\pagestyle{{empty}}
\begin{{tikzpicture}}[x=1cm,y=0.07cm]
\draw[->, line width=0.5pt] (0,0) -- (13.1,0) node[below right, font=\small] {{具体部署场景}};
\draw[->, line width=0.5pt] (0,0) -- (0,108) node[above left, font=\small] {{通过率/拒绝率(\%)}};
\foreach \y in {{0,20,40,60,80,100}} {{
    \draw[gray!35, dashed] (0,\y) -- (12.7,\y);
    \node[anchor=east, font=\small] at (-0.08,\y) {{\y}};
}}
{chr(10).join(body)}
{chr(10).join(legend)}
\end{{tikzpicture}}
\end{{document}}
"""
    CORRECTNESS_TEX.write_text(tex.strip() + "\n", encoding="utf-8")


def render_metrics_chart(summary: dict[str, Any]) -> None:
    scenarios = summary["scenarios"]
    label_map = {
        "quantum_network_node_admission": r"\shortstack{量子计算网络\\节点准入}",
        "ai_accelerator_firmware_upgrade": r"\shortstack{AI加速设备\\固件升级}",
        "model_release_integrity": r"\shortstack{模型发布\\完整性校验}",
    }
    payload_starts = [0.9, 2.2, 3.5]
    latency_starts = [0.9, 2.0, 3.1]
    payload_width = 0.62
    latency_width = 0.24
    payload_body = []
    latency_body = []
    for idx, item in enumerate(scenarios):
        payload = float(item["structured_payload_bytes"]["mean"])
        vmean = float(item["imported_signature_benchmark"]["verify_mean_ms"])
        vp95 = float(item["imported_signature_benchmark"]["verify_p95_ms"])
        px0 = payload_starts[idx]
        px1 = px0 + payload_width
        payload_body.append(f"\\filldraw[fill=blue!55, draw=black!35] ({px0:.2f},0) rectangle ({px1:.2f},{payload:.2f});")
        payload_body.append(f"\\node[font=\scriptsize, rotate=90] at ({(px0+px1)/2:.2f},{payload+15:.2f}) {{{payload:.1f}}};")
        payload_body.append(f"\\node[align=center, font=\scriptsize] at ({(px0+px1)/2:.2f},-28) {{{label_map.get(item['scenario_code'], item['scenario'])}}};")
        lx0 = latency_starts[idx]
        lx1 = lx0 + latency_width
        lx2 = lx1 + 0.10
        lx3 = lx2 + latency_width
        latency_body.append(f"\\filldraw[fill=orange!75, draw=black!35] ({lx0:.2f},0) rectangle ({lx1:.2f},{vmean:.3f});")
        latency_body.append(f"\\filldraw[fill=red!65, draw=black!35] ({lx2:.2f},0) rectangle ({lx3:.2f},{vp95:.3f});")
        latency_body.append(f"\\node[font=\scriptsize, rotate=90] at ({(lx0+lx1)/2:.2f},{vmean+0.14:.3f}) {{{vmean:.3f}}};")
        latency_body.append(f"\\node[font=\scriptsize, rotate=90] at ({(lx2+lx3)/2:.2f},{vp95+0.14:.3f}) {{{vp95:.3f}}};")
        latency_body.append(f"\\node[align=center, font=\scriptsize] at ({(lx0+lx3)/2:.2f},-0.9) {{{label_map.get(item['scenario_code'], item['scenario'])}}};")
    sig_bytes = scenarios[0]["imported_signature_benchmark"]["sig_bytes"] if scenarios else 0
    pk_bytes = scenarios[0]["imported_signature_benchmark"]["pk_bytes"] if scenarios else 0
    tex = rf"""
\documentclass[12pt]{{article}}
\usepackage[UTF8]{{ctex}}
\usepackage[paperwidth=17.5cm,paperheight=9.8cm,margin=0.4cm]{{geometry}}
\usepackage{{tikz}}
\begin{{document}}
\pagestyle{{empty}}
\begin{{tikzpicture}}[font=\small]
\begin{{scope}}[xshift=0cm, yshift=0cm, x=1.35cm, y=0.02cm]
\draw[->, line width=0.5pt] (0,0) -- (4.7,0) node[below right, font=\small] {{场景}};
\draw[->, line width=0.5pt] (0,0) -- (0,340) node[above left, font=\small] {{结构化载荷字节数(B)}};
\foreach \y in {{0,80,160,240,320}} {{
    \draw[gray!35, dashed] (0,\y) -- (4.4,\y);
    \node[anchor=east, font=\scriptsize] at (-0.05,\y) {{\y}};
}}
{chr(10).join(payload_body)}
\node[font=\small] at (2.1,356) {{结构化场景载荷长度}};
\end{{scope}}

\begin{{scope}}[xshift=8.6cm, yshift=1.55cm, x=1.25cm, y=1.8cm]
\draw[->, line width=0.5pt] (0,0) -- (4.1,0) node[below right, font=\small] {{场景}};
\draw[->, line width=0.5pt] (0,0) -- (0,3.4) node[above left, font=\small] {{验签时延(ms)}};
\foreach \y/\label in {{0/0,1/1,2/2,3/3}} {{
    \draw[gray!35, dashed] (0,\y) -- (3.8,\y);
    \node[anchor=east, font=\scriptsize] at (-0.04,\y) {{\label}};
}}
{chr(10).join(latency_body)}
\node[font=\small] at (1.9,3.58) {{导入真实验签时延}};
\filldraw[fill=orange!75, draw=black!35] (0.1,-1.45) rectangle (0.32,-1.23);
\node[anchor=west, font=\scriptsize] at (0.42,-1.34) {{均值}};
\filldraw[fill=red!65, draw=black!35] (1.2,-1.45) rectangle (1.42,-1.23);
\node[anchor=west, font=\scriptsize] at (1.52,-1.34) {{P95}};
\end{{scope}}

\node[draw, rounded corners=2pt, fill=green!8, align=left, font=\small, anchor=north west] at (0.2,-0.15) {{导入真实基准尺寸：公钥 {pk_bytes} B；签名 {sig_bytes} B\\来源：experiments/results/summary.json}};
\end{{tikzpicture}}
\end{{document}}
"""
    METRICS_TEX.write_text(tex.strip() + "\n", encoding="utf-8")


def compile_tex(tex_path: Path) -> None:
    subprocess.run(
        [
            "xelatex",
            "-interaction=nonstopmode",
            "-halt-on-error",
            f"-output-directory={RESULTS}",
            str(tex_path),
        ],
        check=True,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def write_markdown(summary: dict[str, Any]) -> None:
    lines = [
        "# Scenario Summary",
        "",
        summary["note"],
        "",
    ]
    for item in summary["scenarios"]:
        imported = item["imported_signature_benchmark"]
        policy = item["valid_payload_policy_experiment"]
        tamper = item["field_tampering_policy_experiment"]
        lines.extend(
            [
                f"## {item['scenario']}",
                f"- 部署入口：{item['deployment_entry']}",
                f"- 绑定参数点：{item['mapped_scheme']}",
                f"- 有效载荷长度：min={item['structured_payload_bytes']['min']} B, max={item['structured_payload_bytes']['max']} B, mean={item['structured_payload_bytes']['mean']} B",
                f"- 有效载荷策略放行：{policy['accept_count']}/{policy['total']} ({policy['accept_rate_pct']}%)",
                f"- 字段级篡改策略拒绝：{tamper['reject_count']}/{tamper['total']} ({tamper['reject_rate_pct']}%)",
                f"- 导入的原始签名验证成功：{imported['verify_success_count']}/{imported['verify_total']} ({imported['verify_success_rate_pct']}%)",
                f"- 导入的篡改消息验签拒绝：{imported['tampered_message_reject_count']}/{imported['tampered_message_reject_total']} ({imported['tampered_message_reject_rate_pct']}%)",
                f"- 验签延迟：mean={imported['verify_mean_ms']} ms, p95={imported['verify_p95_ms']} ms, throughput={imported['verify_throughput_sig_s']} sig/s",
                "",
            ]
        )
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    imported_summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    scenarios = []
    rows: list[dict[str, Any]] = []
    for definition in scenario_definitions():
        scenario_summary, scenario_rows = evaluate_scenario(definition, imported_summary)
        scenarios.append(scenario_summary)
        rows.extend(scenario_rows)

    summary = {
        "source_summary": str(SUMMARY_PATH),
        "note": "Policy-side scenario experiment executed locally with Python standard library; signature latency/correctness metrics are imported from the repository's existing real benchmark summary.json and mapped to the corresponding deployment scenario.",
        "scenario_count": len(scenarios),
        "record_count": len(rows),
        "scenarios": scenarios,
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(rows)
    write_markdown(summary)
    render_correctness_chart(summary)
    render_metrics_chart(summary)
    compile_tex(CORRECTNESS_TEX)
    compile_tex(METRICS_TEX)
    print(f"[OK] wrote {OUT_JSON}")
    print(f"[OK] wrote {OUT_CSV}")
    print(f"[OK] wrote {OUT_MD}")
    print(f"[OK] wrote {CORRECTNESS_PDF}")
    print(f"[OK] wrote {METRICS_PDF}")


if __name__ == "__main__":
    main()
