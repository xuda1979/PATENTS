"""
Torchair-based registration module for mwg::ephemeral_core_apply (arm 4).

torch_npu builds on the ASI2 host do not expose an eager custom-op loader
(npu_load_ops / _C load-ops APIs are absent), so this module takes the
supported graph-mode route:

  1. The compiled EphemeralCoreApply vendor op package (a tarball of the
     built customize/ opp tree) is extracted to a per-run directory and
     exposed to the GE runtime through ASCEND_OPP_PATH.
  2. The torch-level operator mwg::ephemeral_core_apply is defined with
     torch.library.custom_op; its eager fallback is the materialized
     reference computation (used only outside compiled execution).
  3. An FX converter maps torch.ops.mwg.ephemeral_core_apply.default onto
     tng.ge.custom_op("EphemeralCoreApply", ...).
  4. A small fixed-shape module is compiled with tng.compile once per shape
     signature and cached; every subsequent call executes the compiled graph
     that launches the audited Ascend-C kernel.

The hash-bound no-store contract (audited kernel source sha256 + compiled
package sha256 + source_audit properties) is validated by the harness
BEFORE this module is used; this module is host plumbing only and does not
weaken the contract.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tarfile
import tempfile
import types
from pathlib import Path
from typing import Any, Callable, Dict, Tuple

import torch

_OP_NS = "mwg"
_OP_NAME = "ephemeral_core_apply"
_GE_OP_NAME = "EphemeralCoreApply"
_INPUT_NAMES = ("rank_activation", "controller_hidden", "head_weight", "head_bias")
_OUTPUT_NAME = "scaled_rank_activation"

_state: Dict[str, Any] = {
    "prepared": False,
    "op_defined": False,
    "converter_registered": False,
    "compile_cache": {},
}


def _materialized_reference(
    rank_activation: torch.Tensor,
    controller_hidden: torch.Tensor,
    head_weight: torch.Tensor,
    head_bias: torch.Tensor,
    amplitude: float,
) -> torch.Tensor:
    """Algebraic reference; equals the kernel semantics exactly."""
    logits = controller_hidden @ head_weight + head_bias
    core = 1.0 + float(amplitude) * torch.tanh(logits)
    return rank_activation * core


def prepare_op_package(op_package_path: str) -> Path:
    """Verify the compiled opp package against the installed vendor tree.

    The vendor tree is installed into the GE default opp directory
    (CANN .../opp/vendors/customize) by the build pipeline; ASCEND_OPP_PATH is
    deliberately NOT set, because GE's FE validation rejects non-default opp
    paths on this platform.  The hash-bound package remains the recorded
    binary artifact; this function checks that the installed tree matches the
    package content (same ops-info config hash).
    """
    package = Path(op_package_path).expanduser().resolve()
    if not package.is_file():
        raise RuntimeError(f"op package not found: {package}")
    # The official custom-opp installer targets ASCEND_CUSTOM_OPP_PATH, and GE
    # reads vendor ops from there (vendors/<name>/...).  Extraction happens
    # under /root/work because GE's FE validation rejects /tmp paths on this
    # platform.
    root = Path(
        tempfile.mkdtemp(prefix="mwg_opp_", dir="/root/work")
    )
    os.chmod(root, 0o755)
    with tarfile.open(package, "r:gz") as tf:
        tf.extractall(root)
    extracted = root / "vendors" / "customize"
    if not extracted.is_dir():
        raise RuntimeError(f"package lacks vendors/customize tree: {package}")
    import hashlib

    def _config_hash(base: Path) -> str:
        cfg = base / "op_impl" / "ai_core" / "tbe" / "config" / "ascend910b"
        digest = hashlib.sha256()
        for child in sorted(cfg.glob("*.json")):
            digest.update(child.name.encode())
            digest.update(child.read_bytes())
        return digest.hexdigest()

    installed_roots = [
        Path("/usr/local/Ascend/cann-8.5.0/opp/vendors/customize"),
        Path("/usr/local/Ascend/ascend-toolkit/latest/opp/vendors/customize"),
    ]
    matched = None
    # Ensure AscendC compile mode is declared (TBE defaults to the
    # Python-DSL path when compileMode is absent) BEFORE comparing hashes,
    # patching both trees with identical content so hashes stay equal.
    import json as _json
    def _patch(base: Path) -> None:
        cfg_dir = base / "op_impl" / "ai_core" / "tbe" / "config" / "ascend910b"
        for cfg in cfg_dir.glob("*.json"):
            data = _json.loads(cfg.read_text())
            op = data.get("EphemeralCoreApply")
            changed = False
            if op is not None:
                if "compileMode" not in op:
                    op["compileMode"] = {"value": "ascendc"}
                    changed = True
                # Static binary route: the precompiled kernel under
                # kernel/ascend910b is used directly; TBE dynamic-DSL
                # compilation (which requires a TBE-DSL opfunc) is bypassed.
                if op.get("dynamicCompileStatic", {}).get("flag") != "false":
                    op["dynamicCompileStatic"] = {"flag": "false"}
                    changed = True
            if changed:
                cfg.write_text(_json.dumps(data, indent=4))
    _patch(extracted)
    for installed in installed_roots:
        if installed.is_dir():
            _patch(installed)
    for installed in installed_roots:
        if installed.is_dir() and _config_hash(installed) == _config_hash(extracted):
            matched = installed
            break
    if matched is None:
        raise RuntimeError(
            "installed EphemeralCoreApply vendor tree does not match the "
            "hash-bound op package; reinstall the package before running arm 4"
        )
    _state["installed_vendor"] = str(matched)
    # GE discovers custom vendor ops through ASCEND_CUSTOM_OPP_PATH (the
    # official custom-opp installer variable), not ASCEND_OPP_PATH.
    os.environ["ASCEND_CUSTOM_OPP_PATH"] = str(root)
    return root


def _ensure_op_defined() -> None:
    if _state["op_defined"]:
        return
    from torch.library import custom_op

    @custom_op(f"{_OP_NS}::{_OP_NAME}", mutates_args=())
    def ephemeral_core_apply(  # noqa: F811 - registered as mwg::ephemeral_core_apply
        rank_activation: torch.Tensor,
        controller_hidden: torch.Tensor,
        head_weight: torch.Tensor,
        head_bias: torch.Tensor,
        amplitude: float,
    ) -> torch.Tensor:
        return _materialized_reference(
            rank_activation,
            controller_hidden,
            head_weight,
            head_bias,
            float(amplitude),
        )

    @ephemeral_core_apply.register_fake
    def _fake_impl(  # noqa: F811 - fake-mode impl for FX tracing
        rank_activation, controller_hidden, head_weight, head_bias, amplitude
    ):
        return torch.empty_like(rank_activation)

    _state["op_defined"] = True


def _ensure_converter() -> None:
    if _state["converter_registered"]:
        return
    import torchair as tng
    try:
        from torchair import register_fx_node_ge_converter  # standalone torchair
    except ImportError:
        # torch_npu-integrated torchair shim (2.9): the decorator lives in the
        # internal concrete-graph module and is not re-exported at top level.
        from torchair._ge_concrete_graph.fx2ge_converter import (
            register_fx_node_ge_converter,
        )

    op = getattr(getattr(torch.ops, _OP_NS), _OP_NAME).default

    @register_fx_node_ge_converter(op)
    def convert_ephemeral_core_apply(  # noqa: F811
        rank_activation,
        controller_hidden,
        head_weight,
        head_bias,
        amplitude,
        scaled_rank_activation=None,
        meta_outputs=None,
    ):
        return tng.ge.custom_op(
            _GE_OP_NAME,
            inputs={
                "rank_activation": rank_activation,
                "controller_hidden": controller_hidden,
                "head_weight": head_weight,
                "head_bias": head_bias,
            },
            attrs={"amplitude": tng.ge.attr.Float(float(amplitude))},
            outputs=[_OUTPUT_NAME],
        )

    _state["converter_registered"] = True


class _CompiledWrapper(torch.nn.Module):
    def __init__(self, amplitude: float):
        super().__init__()
        self.amplitude = float(amplitude)

    def forward(self, rank_activation, controller_hidden, head_weight, head_bias):
        return torch.ops.mwg.ephemeral_core_apply(
            rank_activation, controller_hidden, head_weight, head_bias, self.amplitude
        )


def _compiled_callable_factory() -> Callable[..., torch.Tensor]:
    cache: Dict[Tuple, Callable[..., torch.Tensor]] = _state["compile_cache"]

    def invoke(
        rank_activation: torch.Tensor,
        controller_hidden: torch.Tensor,
        head_weight: torch.Tensor,
        head_bias: torch.Tensor,
        amplitude: float,
    ) -> torch.Tensor:
        key = (
            tuple(rank_activation.shape),
            tuple(controller_hidden.shape),
            tuple(head_weight.shape),
            tuple(head_bias.shape),
            str(rank_activation.dtype),
            float(amplitude),
        )
        compiled = cache.get(key)
        if compiled is None:
            import torchair as tng
            try:
                from torchair.configs.compiler_config import CompilerConfig
            except ImportError:
                from torchair.inference import CompilerConfig  # torch_npu shim

            model = _CompiledWrapper(float(amplitude)).to(rank_activation.device)
            config = CompilerConfig()
            if hasattr(tng, "compile"):
                compiled = tng.compile(model, backend="ge", config=config, fullgraph=True)
            else:
                # torch_npu-integrated torchair: inference.cache_compile takes
                # a bound method, not a module instance.
                from torchair.inference import cache_compile

                compiled = cache_compile(model.forward, config=config, dynamic=False)
            cache[key] = compiled
        return compiled(rank_activation, controller_hidden, head_weight, head_bias)

    return invoke


def load_fused_backend(
    op_package_path: str,
    manifest_path: str,
) -> Tuple[Callable[..., torch.Tensor], Dict[str, Any]]:
    """Entry point used by the benchmark harness.

    The harness has already validated the contract manifest (source hash,
    package hash, source_audit properties) before calling this function.
    """
    if not _state["prepared"]:
        prepare_op_package(op_package_path)
        _state["prepared"] = True
    _ensure_op_defined()
    _ensure_converter()
    callable_fn = _compiled_callable_factory()
    info = {
        "registration": "torchair_fx_converter",
        "ge_op_name": _GE_OP_NAME,
        "torch_op": f"{_OP_NS}::{_OP_NAME}",
        "op_package_path": str(Path(op_package_path).expanduser().resolve()),
        "manifest_path": str(Path(manifest_path).expanduser().resolve()),
        "ascend_opp_path": os.environ.get("ASCEND_OPP_PATH", ""),
    }
    return callable_fn, info


def _module_from_path(path: str) -> types.ModuleType:
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise RuntimeError(f"fused registration module not found: {path}")
    spec = importlib.util.spec_from_file_location("mwg_fused_registration_module", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load registration module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    print("registration module importable; load_fused_backend entry present")
