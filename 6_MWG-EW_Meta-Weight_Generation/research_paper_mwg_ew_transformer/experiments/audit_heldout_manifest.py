"""Audit held-out corpus manifest coverage for MWG paper readiness.

This is a local/offline helper. It does not prepare new corpora or contact
Huanxin. Its job is to make benchmark-family coverage and provenance gaps
explicit so the paper cannot accidentally treat a narrow manifest as broad.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


FAMILY_BY_SUITE = {
    "gsm8k_test": "math_reasoning",
    "mbpp_test": "code_generation",
    "alpaca_cleaned_train_tail": "instruction_following",
    "wikitext103_validation": "general_language_modeling",
}

RECOMMENDED_FAMILIES = [
    "general_language_modeling",
    "math_reasoning",
    "code_generation",
    "instruction_following",
    "commonsense_reasoning",
    "multi_turn_dialogue",
    "long_context",
]


def read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def suite_path(heldout_dir: Path, text_spec: str) -> Path:
    path = Path(text_spec)
    if path.is_absolute():
        return path
    return heldout_dir / path


def manifest_sources(args: argparse.Namespace) -> list[dict[str, Path | str]]:
    sources: list[dict[str, Path | str]] = [
        {
            "label": "main",
            "heldout_dir": Path(args.heldout_dir),
            "manifest": Path(args.manifest),
            "provenance": Path(args.provenance),
        }
    ]
    if args.include_extra:
        sources.append(
            {
                "label": "extra",
                "heldout_dir": Path(args.extra_heldout_dir),
                "manifest": Path(args.extra_manifest),
                "provenance": Path(args.extra_provenance),
            }
        )
    return sources


def audit(args: argparse.Namespace) -> dict[str, Any]:
    suites = []
    families: dict[str, dict[str, Any]] = {}
    all_eval_lines: dict[str, set[str]] = {}
    failures = []
    router = {}
    source_rows = []

    for source in manifest_sources(args):
        label = str(source["label"])
        heldout_dir = Path(source["heldout_dir"])
        manifest_path = Path(source["manifest"])
        provenance_path = Path(source["provenance"])
        manifest = load_json(manifest_path)
        provenance = load_json(provenance_path) if provenance_path.exists() else {"suites": [], "failures": []}
        provenance_by_name = {item.get("name"): item for item in provenance.get("suites", [])}
        source_rows.append(
            {
                "label": label,
                "manifest": str(manifest_path),
                "provenance": str(provenance_path),
                "heldout_dir": str(heldout_dir),
                "suite_count": len(manifest.get("suites", [])),
                "failure_count": len(provenance.get("failures", [])),
            }
        )
        for failure in provenance.get("failures", []):
            failures.append({"source": label, **failure})
        if provenance.get("router"):
            router[label] = provenance.get("router")

        for suite in manifest.get("suites", []):
            name = suite["name"]
            path = suite_path(heldout_dir, suite["texts"])
            lines = read_lines(path)
            chars = sum(len(line) for line in lines)
            family = suite.get("family") or FAMILY_BY_SUITE.get(name, "unknown")
            prov = provenance_by_name.get(name, {})
            row = {
                "source": label,
                "name": name,
                "family": family,
                "path": str(path),
                "exists": path.exists(),
                "line_count": len(lines),
                "characters": chars,
                "dataset": prov.get("dataset"),
                "config": prov.get("config"),
                "split": prov.get("split"),
                "source_type": prov.get("source_type"),
                "source_path": prov.get("source_path"),
            }
            suites.append(row)
            all_eval_lines[f"{label}:{name}"] = set(lines)
            family_row = families.setdefault(
                family, {"suite_count": 0, "line_count": 0, "characters": 0, "suites": []}
            )
            family_row["suite_count"] += 1
            family_row["line_count"] += len(lines)
            family_row["characters"] += chars
            family_row["suites"].append(f"{label}:{name}")

    overlap_pairs = []
    names = list(all_eval_lines)
    for i, left in enumerate(names):
        for right in names[i + 1 :]:
            overlap = all_eval_lines[left] & all_eval_lines[right]
            if overlap:
                overlap_pairs.append({"left": left, "right": right, "overlap_count": len(overlap)})

    present_families = sorted(families)
    missing_recommended = [family for family in RECOMMENDED_FAMILIES if family not in families]
    ready_for_broad_claim = not missing_recommended and not failures and not overlap_pairs
    return {
        "manifest": args.manifest,
        "provenance": args.provenance,
        "heldout_dir": args.heldout_dir,
        "sources": source_rows,
        "suite_count": len(suites),
        "families_present": present_families,
        "families_missing_recommended": missing_recommended,
        "suites": suites,
        "families": families,
        "failures": failures,
        "router": router,
        "eval_overlap_pairs": overlap_pairs,
        "claim_boundary": {
            "ready_for_broad_family_claim": ready_for_broad_claim,
            "reason": (
                "Current manifest is useful for broad stress testing, but top-journal broad-family claims "
                "need the missing recommended families and resolved dataset failures."
            ),
        },
    }


def write_markdown(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Held-Out Manifest Coverage Audit",
        "",
        f"Manifest: `{payload['manifest']}`",
        f"Provenance: `{payload['provenance']}`",
        "",
        "## Sources",
        "",
        "| Label | Manifest | Suites | Failures |",
        "| --- | --- | ---: | ---: |",
    ]
    for source in payload["sources"]:
        lines.append(
            f"| {source['label']} | `{source['manifest']}` | {int(source['suite_count']):,} | "
            f"{int(source['failure_count']):,} |"
        )
    lines.extend(
        [
            "",
        "## Family Coverage",
        "",
        "| Family | Suites | Lines | Characters |",
        "| --- | --- | ---: | ---: |",
        ]
    )
    for family, row in sorted(payload["families"].items()):
        lines.append(
            f"| {family} | {', '.join(row['suites'])} | {int(row['line_count']):,} | {int(row['characters']):,} |"
        )
    lines.extend(
        [
            "",
            "Missing recommended families: "
            + (", ".join(payload["families_missing_recommended"]) or "none"),
            "",
            "## Dataset Failures",
            "",
        ]
    )
    if payload["failures"]:
        for failure in payload["failures"]:
            source = failure.get("source", "unknown")
            origin = failure.get("dataset") or failure.get("source_path") or failure.get("source_type") or "unknown"
            lines.append(f"- `{source}:{failure.get('name')}` from `{origin}`: {failure.get('error')}")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            f"Ready for broad-family claim: `{str(payload['claim_boundary']['ready_for_broad_family_claim']).lower()}`",
            "",
            payload["claim_boundary"]["reason"],
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--heldout-dir", default="data/heldout")
    parser.add_argument("--manifest", default="data/heldout/manifest.json")
    parser.add_argument("--provenance", default="data/heldout/provenance.json")
    parser.add_argument("--include-extra", action="store_true")
    parser.add_argument("--extra-heldout-dir", default="data/heldout_extra")
    parser.add_argument("--extra-manifest", default="data/heldout_extra/manifest_extra.json")
    parser.add_argument("--extra-provenance", default="data/heldout_extra/provenance_extra.json")
    parser.add_argument("--out-json", default="results/heldout_manifest_audit_20260525.json")
    parser.add_argument("--out-md", default="results/heldout_manifest_audit_20260525.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = audit(args)
    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    write_markdown(payload, Path(args.out_md))
    print(json.dumps(payload, indent=2), flush=True)


if __name__ == "__main__":
    main()
