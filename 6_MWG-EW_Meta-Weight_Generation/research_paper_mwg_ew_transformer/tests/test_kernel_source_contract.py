"""Static source-audit tests for the arm-4 Ascend-C kernel.

These checks codify the source_audit properties of the fused no-store
contract on the audited kernel source.  They are string-level audits, not a
compilation or counter validation: the NPU-host compile and the matched
arm-3/arm-4 msprof run remain mandatory before arm 4 can produce evidence.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from mwg_four_arm_lifetime_benchmark import FUSED_OP_QUALIFIED_NAME  # noqa: E402
KERNEL = (
    ROOT / "custom_ops" / "ephemeral_core_apply" / "ephemeral_core_apply_kernel.cpp"
)
CONTRACT = ROOT / "custom_ops" / "ephemeral_core_apply" / "contract.example.json"


def _source() -> str:
    assert KERNEL.is_file(), f"audited kernel source missing: {KERNEL}"
    return KERNEL.read_text(encoding="utf-8")


def _code_only(src: str) -> str:
    """Strip block and line comments so keyword checks see code, not prose."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", src)


def test_kernel_source_exists_and_defines_entry_symbol() -> None:
    src = _source()
    assert "ephemeral_core_apply_kernel" in src
    assert "KernelEphemeralCoreApply" in src


def test_no_core_global_tensor() -> None:
    declared = set(re.findall(r"GlobalTensor<\w+>\s+(\w+);", _source()))
    assert declared == {"aGm_", "bGm_", "biasGm_", "actGm_", "outGm_"}, declared


def test_no_core_datacopy_to_global() -> None:
    src = _source()
    # GM writes: exactly one DataCopy whose destination is outGm_ (the single
    # declared output); no DataCopy ever reads from outGm_.
    writes = len(re.findall(r"DataCopy\(outGm_", src))
    assert writes == 1, writes
    sources = re.findall(r"DataCopy\(\w+,\s*(\w+)", src)
    assert "outGm_" not in sources, sources
    # The core C-tile buffer never participates in a DataCopy at all.
    assert not re.search(r"DataCopy\([^)]*cLocal", src)


def test_one_global_output_and_no_workspace_api() -> None:
    src = _source()
    buffers = re.findall(r"(\w+)\.SetGlobalBuffer", src)
    assert buffers == ["aGm_", "bGm_", "biasGm_", "actGm_", "outGm_"], buffers
    code = _code_only(src)
    assert "SetWorkspace" not in code
    assert "workspace" not in code.lower()
    assert "zero global workspace" in src


def test_deterministic_no_rng_no_atomics() -> None:
    code = _code_only(_source()).lower()
    for forbidden in ("rand", "atomic", "tickcount", "clock"):
        assert forbidden not in code, forbidden


def test_contract_example_matches_audit_properties() -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert payload["op_qualified_name"] == FUSED_OP_QUALIFIED_NAME
    assert payload["global_core_output"] is False
    assert payload["workspace_bytes"] == 0
    assert payload["outputs"] == ["scaled_rank_activation"]
    assert payload["source_audit"]["no_global_core_tensor"] is True
    assert payload["source_audit"]["no_core_datacopy_to_global"] is True
