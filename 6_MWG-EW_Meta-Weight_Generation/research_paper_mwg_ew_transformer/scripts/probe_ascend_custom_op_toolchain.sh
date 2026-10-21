#!/usr/bin/env bash
set -euo pipefail

# Read-only ASI2 prerequisite probe.  It does not log in, open a browser,
# compile an operator, allocate a test tensor, or launch a benchmark.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export MWG_PROJECT_ROOT="$PROJECT_ROOT"

python3 - "$@" <<'PY'
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def first_tool(name: str, patterns: list[str]) -> str | None:
    direct = shutil.which(name)
    if direct:
        return str(Path(direct).resolve())
    for pattern in patterns:
        for candidate in sorted(glob.glob(pattern, recursive=True)):
            path = Path(candidate)
            if path.is_file() and os.access(path, os.X_OK):
                return str(path.resolve())
    return None


def command_output(command: list[str], timeout: int = 15) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "returncode": completed.returncode,
            "output": completed.stdout[:100_000],
        }
    except Exception as exc:
        return {"error": repr(exc), "output": ""}


parser = argparse.ArgumentParser()
parser.add_argument("--output")
parser.add_argument("--require-all", action="store_true")
parser.add_argument("--op-library")
parser.add_argument("--contract-manifest")
args = parser.parse_args()

project_root = Path(os.environ["MWG_PROJECT_ROOT"]).resolve()
sys.path.insert(0, str(project_root / "experiments"))

patterns = {
    "msprof": [
        "/usr/local/Ascend/*/bin/msprof",
        "/usr/local/Ascend/ascend-toolkit/latest/bin/msprof",
    ],
    "msopgen": [
        "/usr/local/Ascend/*/bin/msopgen",
        "/usr/local/Ascend/ascend-toolkit/latest/bin/msopgen",
        "/usr/local/Ascend/**/msopgen",
    ],
    "ccec": [
        "/usr/local/Ascend/**/ccec",
        "/usr/local/Ascend/**/ccec_compiler/bin/ccec",
    ],
    "bisheng": [
        "/usr/local/Ascend/**/bisheng",
        "/usr/local/Ascend/**/compiler/bin/bisheng",
    ],
}
tools = {
    "python3": shutil.which("python3"),
    "npu-smi": shutil.which("npu-smi"),
    "cmake": shutil.which("cmake"),
    "c++": shutil.which("c++") or shutil.which("g++"),
    "msprof": first_tool("msprof", patterns["msprof"]),
    "msopgen": first_tool("msopgen", patterns["msopgen"]),
    "ccec": first_tool("ccec", patterns["ccec"]),
    "bisheng": first_tool("bisheng", patterns["bisheng"]),
}

runtime: dict[str, Any] = {
    "torch_importable": False,
    "torch_npu_importable": False,
    "npu_available": False,
    "npu_count": 0,
    "device_names": [],
    "torch_npu_profiler_npu_activity": False,
}
try:
    import torch

    runtime["torch_importable"] = True
    runtime["torch"] = torch.__version__
    import torch_npu

    runtime["torch_npu_importable"] = True
    runtime["torch_npu"] = getattr(torch_npu, "__version__", "unknown")
    runtime["npu_available"] = bool(hasattr(torch, "npu") and torch.npu.is_available())
    if hasattr(torch, "npu"):
        runtime["npu_count"] = int(torch.npu.device_count())
        for index in range(runtime["npu_count"]):
            try:
                runtime["device_names"].append(torch.npu.get_device_name(index))
            except Exception as exc:
                runtime["device_names"].append(f"error:{exc!r}")
    try:
        import torch_npu.profiler as npu_profiler

        activity = getattr(npu_profiler, "ProfilerActivity", None)
        runtime["torch_npu_profiler_npu_activity"] = bool(
            activity is not None and hasattr(activity, "NPU")
        )
        runtime["torch_npu_profiler_symbols"] = sorted(
            name
            for name in ("ProfilerActivity", "AiCMetrics", "ProfilerLevel", "ExportType", "profile")
            if hasattr(npu_profiler, name)
        )
    except Exception as exc:
        runtime["torch_npu_profiler_error"] = repr(exc)
except Exception as exc:
    runtime["runtime_error"] = repr(exc)

msprof: dict[str, Any] = {"available": bool(tools["msprof"])}
if tools["msprof"]:
    help_result = command_output([tools["msprof"], "--help"])
    help_text = str(help_result.get("output", ""))
    lowered = help_text.lower()
    msprof.update(
        {
            "help_returncode": help_result.get("returncode"),
            "supports_application": "--application" in lowered,
            "supports_output": "--output" in lowered,
            "supports_aic_metrics": "--aic-metrics" in lowered,
            "supports_task_time": "--task-time" in lowered,
            "supports_sys_hardware_mem": "--sys-hardware-mem" in lowered,
            "mentions_memory_metric": "memory" in lowered,
            "mentions_l2_metric": "l2" in lowered,
            "help_sha256": __import__("hashlib").sha256(help_text.encode("utf-8")).hexdigest(),
        }
    )
    if "error" in help_result:
        msprof["help_error"] = help_result["error"]

toolchain_ready = bool(
    tools["msopgen"]
    and (tools["ccec"] or tools["bisheng"])
    and tools["cmake"]
    and tools["c++"]
)
counter_ready = bool(
    tools["npu-smi"]
    and msprof.get("supports_application")
    and msprof.get("supports_output")
    and msprof.get("supports_aic_metrics")
    and msprof.get("supports_task_time")
    and msprof.get("supports_sys_hardware_mem")
    and runtime.get("torch_npu_profiler_npu_activity")
)
runtime_ready = bool(
    runtime.get("torch_npu_importable")
    and runtime.get("npu_available")
    and int(runtime.get("npu_count", 0)) > 0
)

op: dict[str, Any] = {
    "library_supplied": bool(args.op_library),
    "manifest_supplied": bool(args.contract_manifest),
    "contract_validated": False,
    "registered": False,
}
if args.op_library and args.contract_manifest:
    try:
        from mwg_four_arm_lifetime_benchmark import (
            resolve_registered_fused_op,
            validate_fused_contract_manifest,
        )

        op["contract"] = validate_fused_contract_manifest(
            args.contract_manifest,
            args.op_library,
        )
        op["contract_validated"] = True
        import torch

        torch.ops.load_library(str(Path(args.op_library).expanduser().resolve()))
        resolve_registered_fused_op()
        op["registered"] = True
    except Exception as exc:
        op["error"] = repr(exc)

op_ready = bool(op["contract_validated"] and op["registered"])
ready = bool(toolchain_ready and counter_ready and runtime_ready and op_ready)
missing: list[str] = []
if not runtime_ready:
    missing.append("torch_npu NPU runtime")
if not toolchain_ready:
    missing.append("Ascend-C custom-op development toolchain")
if not counter_ready:
    missing.append("msprof/NPU counter prerequisites")
if not op_ready:
    missing.append("validated and registered mwg::ephemeral_core_apply")

payload = {
    "schema_version": "mwg-ascend-toolchain-probe-v1",
    "created_at": utc_tag(),
    "hostname": __import__("socket").gethostname(),
    "project_root": str(project_root),
    "tools": tools,
    "runtime": runtime,
    "msprof": msprof,
    "op": op,
    "readiness": {
        "runtime_ready": runtime_ready,
        "toolchain_ready": toolchain_ready,
        "counter_ready": counter_ready,
        "op_ready": op_ready,
        "full_evidence_ready": ready,
        "missing": missing,
    },
    "side_effects": "read_only_no_compile_no_device_allocation_no_browser_no_login",
}

rendered = json.dumps(payload, indent=2) + "\n"
if args.output:
    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
print(rendered, end="")
if args.require_all and not ready:
    raise SystemExit(2)
PY
