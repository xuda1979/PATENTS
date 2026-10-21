"""Matched four-arm inference benchmark for the MWG-EW lifetime hypothesis.

The four arms are:

1. a dense gated FFN whose matrices are the products of the shared factors;
2. the same projections executed as persistent low-rank factors;
3. token-local diagonal cores generated as ordinary framework tensors; and
4. the same cores generated and consumed by an audited compiled custom op.

Arm 4 is deliberately fail-closed.  There is no Python fallback carrying the
``fused`` label.  It can run only on an NPU after a shared library and a
matching no-store contract manifest have both been validated.  The reference
function in this file exists for algebraic tests; it is not arm 4 evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import socket
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import torch
import torch.nn as nn


SCHEMA_VERSION = "mwg-four-arm-lifetime-v1"
CONTRACT_SCHEMA_VERSION = 1
FUSED_OP_QUALIFIED_NAME = "mwg::ephemeral_core_apply"
DEFAULT_ARMS = ("dense", "persistent", "materialized")
ALL_ARMS = (*DEFAULT_ARMS, "fused")


class FusedBackendUnavailable(RuntimeError):
    """Raised when arm 4 cannot satisfy its compiled no-store contract."""


def utc_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(character in "0123456789abcdefABCDEF" for character in value)


def _resolve_manifest_path(manifest_path: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = manifest_path.parent / path
    return path.resolve()


def validate_fused_contract_manifest(
    manifest_path: str | Path,
    op_library: str | Path,
) -> dict[str, Any]:
    """Validate static evidence required before the fused arm can be loaded.

    The manifest is intentionally strict.  It binds an audited Ascend-C source
    file and the compiled shared object by hash and declares that the operator
    has one global output, zero global workspace, and no global core tensor.
    This is static contract evidence; device counters remain separately
    required for a physical HBM-traffic claim.
    """

    manifest = Path(manifest_path).expanduser().resolve()
    library = Path(op_library).expanduser().resolve()
    if not manifest.is_file():
        raise FusedBackendUnavailable(f"fused contract manifest not found: {manifest}")
    if not library.is_file():
        raise FusedBackendUnavailable(f"compiled fused op library not found: {library}")

    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception as exc:
        raise FusedBackendUnavailable(
            f"cannot parse fused contract manifest {manifest}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise FusedBackendUnavailable("fused contract manifest must be a JSON object")

    required_exact = {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "op_qualified_name": FUSED_OP_QUALIFIED_NAME,
        "implementation": "ascendc",
        "core_residency": "ub_local_tensor",
        "global_core_output": False,
        "workspace_bytes": 0,
        "outputs": ["scaled_rank_activation"],
    }
    violations: list[str] = []
    for key, expected in required_exact.items():
        if payload.get(key) != expected:
            violations.append(f"{key} must equal {expected!r}")

    audit = payload.get("source_audit")
    if not isinstance(audit, dict):
        violations.append("source_audit must be an object")
    else:
        if audit.get("no_global_core_tensor") is not True:
            violations.append("source_audit.no_global_core_tensor must be true")
        if audit.get("no_core_datacopy_to_global") is not True:
            violations.append("source_audit.no_core_datacopy_to_global must be true")

    source_value = payload.get("audited_source_path")
    source_hash = payload.get("audited_source_sha256")
    binary_hash = payload.get("binary_sha256")
    if not isinstance(source_value, str) or not source_value:
        violations.append("audited_source_path must be a non-empty string")
        source_path = None
    else:
        source_path = _resolve_manifest_path(manifest, source_value)
        if not source_path.is_file():
            violations.append(f"audited source not found: {source_path}")
    if not _is_sha256(source_hash):
        violations.append("audited_source_sha256 must be a SHA-256 hex digest")
    if not _is_sha256(binary_hash):
        violations.append("binary_sha256 must be a SHA-256 hex digest")

    if source_path is not None and source_path.is_file() and _is_sha256(source_hash):
        observed = sha256_file(source_path)
        if observed.lower() != str(source_hash).lower():
            violations.append("audited source hash does not match the manifest")
    observed_binary_hash = sha256_file(library)
    if (
        _is_sha256(binary_hash)
        and observed_binary_hash.lower() != str(binary_hash).lower()
    ):
        violations.append("compiled op library hash does not match the manifest")

    if violations:
        raise FusedBackendUnavailable(
            "invalid fused no-store contract: " + "; ".join(violations)
        )

    return {
        "validated": True,
        "manifest_path": str(manifest),
        "manifest_sha256": sha256_file(manifest),
        "op_library": str(library),
        "binary_sha256": observed_binary_hash,
        "audited_source_path": str(source_path),
        "audited_source_sha256": str(source_hash).lower(),
        "op_qualified_name": payload["op_qualified_name"],
        "implementation": payload["implementation"],
        "core_residency": payload["core_residency"],
        "global_core_output": payload["global_core_output"],
        "workspace_bytes": payload["workspace_bytes"],
        "outputs": payload["outputs"],
        "source_audit": payload["source_audit"],
        "static_contract_only": True,
        "hardware_counter_validation": False,
    }


def resolve_registered_fused_op() -> Callable[..., torch.Tensor]:
    try:
        namespace = getattr(torch.ops, "mwg")
        packet = getattr(namespace, "ephemeral_core_apply")
        return getattr(packet, "default", packet)
    except (AttributeError, RuntimeError) as exc:
        raise FusedBackendUnavailable(
            f"compiled operator {FUSED_OP_QUALIFIED_NAME!r} is not registered"
        ) from exc


def prepare_fused_backend(
    device: torch.device,
    manifest_path: str | Path | None,
    op_library: str | Path | None,
    registration_module: str | Path | None = None,
) -> tuple[Callable[..., torch.Tensor], dict[str, Any]]:
    if device.type != "npu":
        raise FusedBackendUnavailable(
            "the fused no-store arm is restricted to an audited NPU custom op"
        )
    if manifest_path is None or op_library is None:
        raise FusedBackendUnavailable(
            "the fused arm requires both --fused-contract-manifest and --op-library"
        )
    contract = validate_fused_contract_manifest(manifest_path, op_library)
    if registration_module is not None:
        # Module route: torchair FX registration on torch_npu builds without an
        # eager custom-op loader.  The contract (source + binary hashes) is
        # validated above; the module is host plumbing only.
        import importlib.util as _importlib_util

        module_path = Path(registration_module).expanduser().resolve()
        if not module_path.is_file():
            raise FusedBackendUnavailable(
                f"fused registration module not found: {module_path}"
            )
        spec = _importlib_util.spec_from_file_location(
            "mwg_fused_registration_module", module_path
        )
        if spec is None or spec.loader is None:
            raise FusedBackendUnavailable(
                f"cannot load fused registration module: {module_path}"
            )
        module = _importlib_util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        fused_op, extra = module.load_fused_backend(op_library, manifest_path)
        if not callable(fused_op):
            raise FusedBackendUnavailable(
                "fused registration module returned a non-callable backend"
            )
        merged = dict(contract)
        merged["registration"] = extra.get("registration", "module")
        merged["ge_op_name"] = extra.get("ge_op_name")
        merged["torch_op"] = extra.get("torch_op")
        merged["ascend_opp_path"] = extra.get("ascend_opp_path", "")
        return fused_op, merged
    try:
        torch.ops.load_library(str(Path(op_library).expanduser().resolve()))
    except Exception as exc:
        raise FusedBackendUnavailable(
            f"failed to load compiled op library: {exc}"
        ) from exc
    return resolve_registered_fused_op(), contract


def parse_arms(value: str | Iterable[str]) -> tuple[str, ...]:
    if isinstance(value, str):
        raw = [item.strip().lower() for item in value.split(",") if item.strip()]
    else:
        raw = [str(item).strip().lower() for item in value if str(item).strip()]
    if raw == ["all"]:
        raw = list(ALL_ARMS)
    if not raw:
        raise ValueError("at least one arm is required")
    unknown = sorted(set(raw) - set(ALL_ARMS))
    if unknown:
        raise ValueError(f"unknown arms: {', '.join(unknown)}")
    return tuple(dict.fromkeys(raw))


def select_device(name: str) -> torch.device:
    if name != "auto":
        device = torch.device(name)
    else:
        try:
            import torch_npu  # type: ignore  # noqa: F401

            if hasattr(torch, "npu") and torch.npu.is_available():  # type: ignore[attr-defined]
                device = torch.device("npu:0")
            elif torch.cuda.is_available():
                device = torch.device("cuda:0")
            else:
                device = torch.device("cpu")
        except Exception:
            device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    if device.type == "npu":
        try:
            import torch_npu  # type: ignore  # noqa: F401
        except Exception as exc:
            raise RuntimeError(
                f"NPU requested but torch_npu cannot be imported: {exc}"
            ) from exc
        if not hasattr(torch, "npu") or not torch.npu.is_available():  # type: ignore[attr-defined]
            raise RuntimeError("NPU requested but torch.npu is unavailable")
        index = 0 if device.index is None else device.index
        torch.npu.set_device(index)  # type: ignore[attr-defined]
    elif device.type == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but unavailable")
        torch.cuda.set_device(0 if device.index is None else device.index)
    return device


def dtype_from_name(name: str, device: torch.device) -> torch.dtype:
    if name == "auto":
        return torch.float16 if device.type in {"npu", "cuda"} else torch.float32
    mapping = {"fp16": torch.float16, "bf16": torch.bfloat16, "fp32": torch.float32}
    return mapping[name]


def synchronize(device: torch.device) -> None:
    if device.type == "npu":
        torch.npu.synchronize()  # type: ignore[attr-defined]
    elif device.type == "cuda":
        torch.cuda.synchronize(device)


def empty_cache(device: torch.device) -> None:
    if device.type == "npu":
        torch.npu.empty_cache()  # type: ignore[attr-defined]
    elif device.type == "cuda":
        torch.cuda.empty_cache()


def reset_peak_memory(device: torch.device) -> None:
    try:
        if device.type == "npu":
            torch.npu.reset_peak_memory_stats()  # type: ignore[attr-defined]
        elif device.type == "cuda":
            torch.cuda.reset_peak_memory_stats(device)
    except Exception:
        pass


def current_memory(device: torch.device) -> dict[str, int | None]:
    try:
        if device.type == "npu":
            return {
                "allocated_bytes": int(torch.npu.memory_allocated()),  # type: ignore[attr-defined]
                "reserved_bytes": int(torch.npu.memory_reserved()),  # type: ignore[attr-defined]
            }
        if device.type == "cuda":
            return {
                "allocated_bytes": int(torch.cuda.memory_allocated(device)),
                "reserved_bytes": int(torch.cuda.memory_reserved(device)),
            }
    except Exception:
        pass
    return {"allocated_bytes": None, "reserved_bytes": None}


def peak_memory(device: torch.device) -> dict[str, int | None]:
    try:
        if device.type == "npu":
            return {
                "max_allocated_bytes": int(torch.npu.max_memory_allocated()),  # type: ignore[attr-defined]
                "max_reserved_bytes": int(torch.npu.max_memory_reserved()),  # type: ignore[attr-defined]
            }
        if device.type == "cuda":
            return {
                "max_allocated_bytes": int(torch.cuda.max_memory_allocated(device)),
                "max_reserved_bytes": int(torch.cuda.max_memory_reserved(device)),
            }
    except Exception:
        pass
    return {"max_allocated_bytes": None, "max_reserved_bytes": None}


@dataclass(frozen=True)
class BenchmarkConfig:
    d: int
    m: int
    rank: int
    controller_hidden: int
    batch: int
    seq: int
    amplitude: float
    dtype: str
    seed: int

    @property
    def tokens(self) -> int:
        return self.batch * self.seq


@dataclass
class MasterWeights:
    up_u: torch.Tensor
    up_v: torch.Tensor
    gate_u: torch.Tensor
    gate_v: torch.Tensor
    down_u: torch.Tensor
    down_v: torch.Tensor
    controller_w1: torch.Tensor
    controller_b1: torch.Tensor
    controller_w2_up: torch.Tensor
    controller_w2_gate: torch.Tensor
    controller_w2_down: torch.Tensor
    controller_b2_up: torch.Tensor
    controller_b2_gate: torch.Tensor
    controller_b2_down: torch.Tensor


def generate_master_weights(config: BenchmarkConfig) -> MasterWeights:
    generator = torch.Generator(device="cpu").manual_seed(config.seed)

    def normal(shape: Sequence[int], scale: float) -> torch.Tensor:
        return torch.randn(*shape, generator=generator, dtype=torch.float32) * scale

    d, m, rank, hidden = config.d, config.m, config.rank, config.controller_hidden
    return MasterWeights(
        up_u=normal((d, rank), 1.0 / math.sqrt(d)),
        up_v=normal((rank, m), 1.0 / math.sqrt(rank)),
        gate_u=normal((d, rank), 1.0 / math.sqrt(d)),
        gate_v=normal((rank, m), 1.0 / math.sqrt(rank)),
        down_u=normal((m, rank), 1.0 / math.sqrt(m)),
        down_v=normal((rank, d), 1.0 / math.sqrt(rank)),
        controller_w1=normal((d, hidden), 1.0 / math.sqrt(d)),
        controller_b1=normal((hidden,), 0.01),
        controller_w2_up=normal((hidden, rank), 1.0 / math.sqrt(hidden)),
        controller_w2_gate=normal((hidden, rank), 1.0 / math.sqrt(hidden)),
        controller_w2_down=normal((hidden, rank), 1.0 / math.sqrt(hidden)),
        controller_b2_up=normal((rank,), 0.01),
        controller_b2_gate=normal((rank,), 0.01),
        controller_b2_down=normal((rank,), 0.01),
    )


def make_input(
    config: BenchmarkConfig, dtype: torch.dtype, device: torch.device
) -> torch.Tensor:
    generator = torch.Generator(device="cpu").manual_seed(config.seed + 1)
    cpu = torch.randn(
        config.batch, config.seq, config.d, generator=generator, dtype=torch.float32
    )
    return cpu.to(device=device, dtype=dtype)


def reference_materialize_core(
    controller_hidden: torch.Tensor,
    head_weight: torch.Tensor,
    head_bias: torch.Tensor,
    amplitude: float,
    output_dtype: torch.dtype,
) -> torch.Tensor:
    logits = controller_hidden @ head_weight + head_bias
    return (1.0 + amplitude * torch.tanh(logits)).to(dtype=output_dtype)


def reference_ephemeral_core_apply(
    rank_activation: torch.Tensor,
    controller_hidden: torch.Tensor,
    head_weight: torch.Tensor,
    head_bias: torch.Tensor,
    amplitude: float,
) -> torch.Tensor:
    """Algebraic reference only; this function is never labeled fused."""

    core = reference_materialize_core(
        controller_hidden,
        head_weight,
        head_bias,
        amplitude,
        rank_activation.dtype,
    )
    return rank_activation * core


class BufferModule(nn.Module):
    def add(
        self, name: str, value: torch.Tensor, dtype: torch.dtype | None = None
    ) -> None:
        self.register_buffer(name, value.to(dtype=dtype or value.dtype).contiguous())


class DenseArm(BufferModule):
    def __init__(self, master: MasterWeights, dtype: torch.dtype):
        super().__init__()
        self.add("up", master.up_u @ master.up_v, dtype)
        self.add("gate", master.gate_u @ master.gate_v, dtype)
        self.add("down", master.down_u @ master.down_v, dtype)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return (torch.nn.functional.silu(x @ self.gate) * (x @ self.up)) @ self.down


class PersistentLowRankArm(BufferModule):
    def __init__(self, master: MasterWeights, dtype: torch.dtype):
        super().__init__()
        for name in ("up_u", "up_v", "gate_u", "gate_v", "down_u", "down_v"):
            self.add(name, getattr(master, name), dtype)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        up = (x @ self.up_u) @ self.up_v
        gate = (x @ self.gate_u) @ self.gate_v
        hidden = torch.nn.functional.silu(gate) * up
        return (hidden @ self.down_u) @ self.down_v


class GeneratedCoreBase(PersistentLowRankArm):
    def __init__(self, master: MasterWeights, dtype: torch.dtype, amplitude: float):
        super().__init__(master, dtype)
        self.amplitude = float(amplitude)
        for name in (
            "controller_w1",
            "controller_b1",
            "controller_w2_up",
            "controller_w2_gate",
            "controller_w2_down",
            "controller_b2_up",
            "controller_b2_gate",
            "controller_b2_down",
        ):
            self.add(name, getattr(master, name), torch.float32)

    def controller_hidden(self, x: torch.Tensor) -> torch.Tensor:
        return torch.nn.functional.silu(
            x.float() @ self.controller_w1 + self.controller_b1
        )


class MaterializedCoreArm(GeneratedCoreBase):
    def __init__(self, master: MasterWeights, dtype: torch.dtype, amplitude: float):
        super().__init__(master, dtype, amplitude)
        self.record_core_metadata = False
        self.last_core_metadata: list[dict[str, Any]] = []

    def apply(
        self,
        name: str,
        rank_activation: torch.Tensor,
        controller_hidden: torch.Tensor,
        weight: torch.Tensor,
        bias: torch.Tensor,
    ) -> torch.Tensor:
        core = reference_materialize_core(
            controller_hidden,
            weight,
            bias,
            self.amplitude,
            rank_activation.dtype,
        )
        if self.record_core_metadata:
            self.last_core_metadata.append(
                {
                    "projection": name,
                    "shape": list(core.shape),
                    "dtype": str(core.dtype).replace("torch.", ""),
                    "data_ptr": int(core.data_ptr()),
                    "bytes": int(core.numel() * core.element_size()),
                    "global_framework_tensor": True,
                }
            )
        return rank_activation * core

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.record_core_metadata:
            self.last_core_metadata = []
        controller_hidden = self.controller_hidden(x)
        up_rank = self.apply(
            "up",
            x @ self.up_u,
            controller_hidden,
            self.controller_w2_up,
            self.controller_b2_up,
        )
        gate_rank = self.apply(
            "gate",
            x @ self.gate_u,
            controller_hidden,
            self.controller_w2_gate,
            self.controller_b2_gate,
        )
        hidden = torch.nn.functional.silu(gate_rank @ self.gate_v) * (
            up_rank @ self.up_v
        )
        down_rank = self.apply(
            "down",
            hidden @ self.down_u,
            controller_hidden,
            self.controller_w2_down,
            self.controller_b2_down,
        )
        return down_rank @ self.down_v


class FusedNoStoreArm(GeneratedCoreBase):
    def __init__(
        self,
        master: MasterWeights,
        dtype: torch.dtype,
        amplitude: float,
        fused_op: Callable[..., torch.Tensor],
        contract: Mapping[str, Any],
    ):
        super().__init__(master, dtype, amplitude)
        self._fused_op = fused_op
        self.contract = dict(contract)

    def apply(
        self,
        rank_activation: torch.Tensor,
        controller_hidden: torch.Tensor,
        weight: torch.Tensor,
        bias: torch.Tensor,
    ) -> torch.Tensor:
        output = self._fused_op(
            rank_activation,
            controller_hidden,
            weight,
            bias,
            self.amplitude,
        )
        if not isinstance(output, torch.Tensor):
            raise RuntimeError("fused custom op must return exactly one Tensor")
        if output.shape != rank_activation.shape:
            raise RuntimeError(
                f"fused custom op returned shape {tuple(output.shape)}, expected {tuple(rank_activation.shape)}"
            )
        if (
            output.dtype != rank_activation.dtype
            or output.device != rank_activation.device
        ):
            raise RuntimeError(
                "fused custom op changed the rank activation dtype or device"
            )
        return output

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        controller_hidden = self.controller_hidden(x)
        up_rank = self.apply(
            x @ self.up_u,
            controller_hidden,
            self.controller_w2_up,
            self.controller_b2_up,
        )
        gate_rank = self.apply(
            x @ self.gate_u,
            controller_hidden,
            self.controller_w2_gate,
            self.controller_b2_gate,
        )
        hidden = torch.nn.functional.silu(gate_rank @ self.gate_v) * (
            up_rank @ self.up_v
        )
        down_rank = self.apply(
            hidden @ self.down_u,
            controller_hidden,
            self.controller_w2_down,
            self.controller_b2_down,
        )
        return down_rank @ self.down_v


def module_state_bytes(module: nn.Module) -> int:
    tensors = list(module.parameters()) + list(module.buffers())
    return sum(tensor.numel() * tensor.element_size() for tensor in tensors)


def summarize_samples(samples: Sequence[float]) -> dict[str, Any]:
    ordered = sorted(samples)

    def percentile(fraction: float) -> float:
        if len(ordered) == 1:
            return ordered[0]
        index = fraction * (len(ordered) - 1)
        low = math.floor(index)
        high = math.ceil(index)
        if low == high:
            return ordered[low]
        return ordered[low] + (ordered[high] - ordered[low]) * (index - low)

    return {
        "mean_ms": statistics.mean(samples),
        "median_ms": statistics.median(samples),
        "min_ms": min(samples),
        "max_ms": max(samples),
        "p05_ms": percentile(0.05),
        "p95_ms": percentile(0.95),
        "std_ms": statistics.stdev(samples) if len(samples) > 1 else 0.0,
        "samples_ms": list(samples),
        "sample_count": len(samples),
    }


@torch.no_grad()
def time_module(
    module: nn.Module,
    x: torch.Tensor,
    device: torch.device,
    warmup: int,
    iters: int,
    repeats: int,
) -> dict[str, Any]:
    module.eval()
    for _ in range(warmup):
        module(x)
    synchronize(device)
    memory_baseline = current_memory(device)
    reset_peak_memory(device)
    repeat_summaries: list[dict[str, Any]] = []
    flat_samples: list[float] = []
    for _ in range(repeats):
        samples: list[float] = []
        for _ in range(iters):
            synchronize(device)
            started = time.perf_counter_ns()
            output = module(x)
            synchronize(device)
            if output.numel() == 0:
                raise RuntimeError("empty benchmark output")
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000.0
            samples.append(elapsed_ms)
            flat_samples.append(elapsed_ms)
        repeat_summaries.append(summarize_samples(samples))
    result = summarize_samples(flat_samples)
    result["repeats"] = repeat_summaries
    result["timer"] = "host_perf_counter_ns_with_device_synchronize"
    result["warmup_iterations"] = warmup
    result["iterations_per_repeat"] = iters
    result["repeat_count"] = repeats
    memory_peak = peak_memory(device)
    baseline_allocated = memory_baseline.get("allocated_bytes")
    peak_allocated = memory_peak.get("max_allocated_bytes")
    result["memory"] = {
        "baseline": memory_baseline,
        "peak": memory_peak,
        "peak_allocated_delta_bytes": (
            int(peak_allocated) - int(baseline_allocated)
            if isinstance(peak_allocated, int) and isinstance(baseline_allocated, int)
            else None
        ),
    }
    return result


def tensor_fingerprint(tensor: torch.Tensor) -> str:
    cpu = tensor.detach().float().contiguous().cpu()
    return hashlib.sha256(cpu.numpy().tobytes()).hexdigest()


def error_metrics(
    actual: torch.Tensor, expected: torch.Tensor, rtol: float, atol: float
) -> dict[str, Any]:
    actual_f = actual.float()
    expected_f = expected.float()
    delta = (actual_f - expected_f).abs()
    relative = delta / expected_f.abs().clamp_min(atol)
    return {
        "passed": bool(torch.allclose(actual_f, expected_f, rtol=rtol, atol=atol)),
        "max_abs": float(delta.max().item()),
        "mean_abs": float(delta.mean().item()),
        "max_rel": float(relative.max().item()),
        "rtol": rtol,
        "atol": atol,
    }


def environment_snapshot(device: torch.device) -> dict[str, Any]:
    result: dict[str, Any] = {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "torch": torch.__version__,
        "device": str(device),
        "device_type": device.type,
        "ascend_rt_visible_devices": os.environ.get("ASCEND_RT_VISIBLE_DEVICES", ""),
        "tool_paths": {
            name: shutil.which(name)
            for name in ("npu-smi", "msprof", "msopgen", "ccec")
        },
    }
    if device.type == "npu":
        try:
            import torch_npu  # type: ignore

            result["torch_npu"] = getattr(torch_npu, "__version__", "unknown")
            result["npu_count"] = torch.npu.device_count()  # type: ignore[attr-defined]
            result["device_name"] = torch.npu.get_device_name(device.index or 0)  # type: ignore[attr-defined]
        except Exception as exc:
            result["npu_metadata_error"] = repr(exc)
    elif device.type == "cuda":
        result["cuda"] = torch.version.cuda
        result["device_name"] = torch.cuda.get_device_name(device)
    return result


def make_arm(
    name: str,
    master: MasterWeights,
    dtype: torch.dtype,
    amplitude: float,
    fused_backend: tuple[Callable[..., torch.Tensor], Mapping[str, Any]] | None,
) -> nn.Module:
    if name == "dense":
        return DenseArm(master, dtype)
    if name == "persistent":
        return PersistentLowRankArm(master, dtype)
    if name == "materialized":
        return MaterializedCoreArm(master, dtype, amplitude)
    if name == "fused":
        if fused_backend is None:
            raise FusedBackendUnavailable("fused backend was not prepared")
        op, contract = fused_backend
        return FusedNoStoreArm(master, dtype, amplitude, op, contract)
    raise ValueError(name)


@torch.no_grad()
def run_benchmark(
    config: BenchmarkConfig,
    arms: Sequence[str],
    device: torch.device,
    warmup: int,
    iters: int,
    repeats: int,
    rtol: float,
    atol: float,
    manifest_path: str | Path | None = None,
    op_library: str | Path | None = None,
    registration_module: str | Path | None = None,
    run_label: str = "",
    counter_metric: str = "",
    counter_pair_id: str = "",
) -> dict[str, Any]:
    selected_arms = parse_arms(arms)
    dtype = dtype_from_name(config.dtype, device)
    master = generate_master_weights(config)
    x = make_input(config, dtype, device)
    fused_backend = None
    contract: dict[str, Any] = {
        "validated": False,
        "arm4_executed": False,
        "reason": "fused arm not selected",
    }
    if "fused" in selected_arms:
        fused_backend = prepare_fused_backend(
            device, manifest_path, op_library, registration_module
        )
        contract = dict(fused_backend[1])
        contract["arm4_executed"] = False

    outputs: dict[str, torch.Tensor] = {}
    results: dict[str, Any] = {}

    # A fused-only counter pass still gets a materialized semantic reference,
    # but that reference is deleted before warmup and is never labeled an arm.
    if "fused" in selected_arms and "materialized" not in selected_arms:
        reference = (
            MaterializedCoreArm(master, dtype, config.amplitude).to(device).eval()
        )
        outputs["materialized_reference"] = reference(x).detach().float().cpu()
        del reference
        empty_cache(device)

    for arm_name in selected_arms:
        module = (
            make_arm(arm_name, master, dtype, config.amplitude, fused_backend)
            .to(device)
            .eval()
        )
        if isinstance(module, MaterializedCoreArm):
            module.record_core_metadata = True
        output = module(x)
        synchronize(device)
        outputs[arm_name] = output.detach().float().cpu()
        core_metadata: list[dict[str, Any]] = []
        if isinstance(module, MaterializedCoreArm):
            core_metadata = list(module.last_core_metadata)
            module.record_core_metadata = False
        timing = time_module(module, x, device, warmup, iters, repeats)
        result: dict[str, Any] = {
            "arm": arm_name,
            "timing": timing,
            "persistent_state_bytes": module_state_bytes(module),
            "output_shape": list(output.shape),
            "output_dtype": str(output.dtype).replace("torch.", ""),
            "output_sha256_fp32": tensor_fingerprint(output),
            "core_global_tensor_metadata": core_metadata,
        }
        if arm_name == "dense":
            result["lifetime"] = "durable_dense_weights"
            result["representation"] = (
                "dense_matrices_W_equal_UV_exact_factor_product_control"
            )
        elif arm_name == "persistent":
            result["lifetime"] = "durable_low_rank_factors_no_generated_core"
            result["representation"] = "associative_factors_for_the_same_W_as_dense"
        elif arm_name == "materialized":
            result["lifetime"] = "generated_core_ordinary_global_framework_tensor"
            result["representation"] = "persistent_UV_plus_token_local_diagonal_core"
        else:
            result["lifetime"] = "compiled_no_store_contract"
            result["representation"] = (
                "same_UV_controller_and_core_semantics_as_materialized"
            )
            result["backend_contract"] = contract
            contract["arm4_executed"] = True
        results[arm_name] = result
        del output, module
        empty_cache(device)

    validations: dict[str, Any] = {}
    if "dense" in outputs and "persistent" in outputs:
        validations["dense_vs_persistent_factorization"] = error_metrics(
            outputs["persistent"], outputs["dense"], rtol, atol
        )
    fused_reference = outputs.get("materialized", outputs.get("materialized_reference"))
    if "fused" in outputs and fused_reference is not None:
        validations["materialized_vs_fused"] = error_metrics(
            outputs["fused"], fused_reference, rtol, atol
        )
        if not validations["materialized_vs_fused"]["passed"]:
            raise RuntimeError(
                "compiled fused op failed materialized-core equivalence: "
                + json.dumps(validations["materialized_vs_fused"], sort_keys=True)
            )

    element_bytes = torch.empty((), dtype=dtype).element_size()
    core_elements = 3 * config.tokens * config.rank
    payload = {
        "schema_version": SCHEMA_VERSION,
        "created_at": utc_tag(),
        "run_label": run_label,
        "counter_metric": counter_metric,
        "counter_pair_id": counter_pair_id,
        "environment": environment_snapshot(device),
        "config": asdict(config),
        "execution": {
            "arms": list(selected_arms),
            "warmup": warmup,
            "iters": iters,
            "repeats": repeats,
            "inference_only": True,
            "dense_control_scope": (
                "dense matrices are exact products of the shared factors; this isolates "
                "representation/execution and is not an independent full-rank checkpoint baseline"
            ),
        },
        "logical_core_accounting": {
            "core_elements_all_three_projections": core_elements,
            "core_bytes_one_copy": core_elements * element_bytes,
            "materialized_store_plus_reload_bytes": 2 * core_elements * element_bytes,
            "fused_scheduled_core_store_plus_reload_bytes": 0
            if "fused" in selected_arms
            else None,
            "not_hardware_counter_measurement": True,
        },
        "backend_contract": contract,
        "arms": results,
        "validations": validations,
        "claim_boundary": {
            "arm4_implemented_in_repository": False,
            "arm4_execution_observed": bool(contract.get("arm4_executed")),
            "hardware_counter_complete": False,
            "no_store_claim_ready": False,
            "reason": (
                "A validated compiled-op execution is necessary but not sufficient. "
                "Parsed arm-3/arm-4 HBM and L2 counters are still required."
            ),
        },
    }
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arms", default=",".join(DEFAULT_ARMS))
    parser.add_argument("--device", default="auto")
    parser.add_argument("--d", type=int, default=512)
    parser.add_argument("--m", type=int, default=1408)
    parser.add_argument("--rank", type=int, default=128)
    parser.add_argument("--controller-hidden", type=int, default=128)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--seq", type=int, default=128)
    parser.add_argument("--amplitude", type=float, default=0.05)
    parser.add_argument(
        "--dtype", choices=("auto", "fp16", "bf16", "fp32"), default="auto"
    )
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--iters", type=int, default=50)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--rtol", type=float, default=5e-3)
    parser.add_argument("--atol", type=float, default=5e-3)
    parser.add_argument("--fused-contract-manifest")
    parser.add_argument("--op-library")
    parser.add_argument("--fused-registration-module")
    parser.add_argument("--run-label", default="")
    parser.add_argument("--counter-metric", default="")
    parser.add_argument("--counter-pair-id", default="")
    parser.add_argument("--output")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def validate_args(args: argparse.Namespace) -> None:
    for name in (
        "d",
        "m",
        "rank",
        "controller_hidden",
        "batch",
        "seq",
        "iters",
        "repeats",
    ):
        if getattr(args, name) <= 0:
            raise SystemExit(f"--{name.replace('_', '-')} must be positive")
    if args.warmup < 0:
        raise SystemExit("--warmup must be non-negative")
    if not (0.0 <= args.amplitude <= 1.0):
        raise SystemExit("--amplitude must lie in [0,1]")


def main() -> None:
    args = build_parser().parse_args()
    validate_args(args)
    arms = parse_arms(args.arms)
    device = select_device(args.device)
    config = BenchmarkConfig(
        d=args.d,
        m=args.m,
        rank=args.rank,
        controller_hidden=args.controller_hidden,
        batch=args.batch,
        seq=args.seq,
        amplitude=args.amplitude,
        dtype=args.dtype,
        seed=args.seed,
    )
    try:
        payload = run_benchmark(
            config=config,
            arms=arms,
            device=device,
            warmup=args.warmup,
            iters=args.iters,
            repeats=args.repeats,
            rtol=args.rtol,
            atol=args.atol,
            manifest_path=args.fused_contract_manifest,
            op_library=args.op_library,
            registration_module=args.fused_registration_module,
            run_label=args.run_label,
            counter_metric=args.counter_metric,
            counter_pair_id=args.counter_pair_id,
        )
    except FusedBackendUnavailable as exc:
        raise SystemExit(f"FUSED_BACKEND_UNAVAILABLE: {exc}") from exc

    output = (
        Path(args.output)
        if args.output
        else Path("results") / f"mwg_four_arm_lifetime_{utc_tag()}.json"
    )
    output = output.expanduser()
    if output.exists() and not args.overwrite:
        raise SystemExit(f"refusing to overwrite existing output: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "arms": list(arms),
                "arm4_execution_observed": payload["claim_boundary"][
                    "arm4_execution_observed"
                ],
                "no_store_claim_ready": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
