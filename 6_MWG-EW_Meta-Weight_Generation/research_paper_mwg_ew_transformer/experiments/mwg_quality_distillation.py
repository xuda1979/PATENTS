"""Quality/distillation experiment for MWG-EW FFN replacements.

This script complements the latency/communication benchmark. It asks a
different question: given a dense gated FFN teacher, how well do low-rank
student families recover the teacher's outputs after distillation?

It supports two teacher sources:
  * synthetic: reproducible random dense FFN weights
  * checkpoint: Hugging Face-style model folders with safetensors or .bin files

The main comparison is between:
  * static_svd: truncated-SVD factors with no training
  * persistent_low_rank: trainable low-rank factors, equivalent to a durable
    low-rank FFN baseline
  * mwg_ephemeral: legacy artifact label for persistent factors plus a
    full-call paired rank-scale generator. The label does not imply no-store
    execution and is retained only for historical checkpoint/result compatibility
  * mwg_token_diag_core: per-token diagonal cores over persistent low-rank
    bases. This is the canonical causal prototype: each projection uses one
    generated rank vector z in ((xU) * z)V
  * mwg_token_scale: a legacy paired-scale mode retained for checkpoint
    compatibility; its two scales per projection are algebraically redundant
  * mwg_token_rank_mixer: per-token generated rank-channel mixers, testing
    whether descriptors need cross-rank interactions rather than diagonal scales
  * mwg_token_residual: the rank-scale generator plus a token-conditioned
    low-rank residual descriptor, testing a more expressive generated path
  * mwg_mixture: a token-group router over multiple low-rank basis banks plus
    token residuals, testing whether conditional generation can beat a durable
    low-rank baseline at the same rank
  * mwg_expert_residual: the same low-rank base with a context-routed bank of
    small residual experts, designed to improve quality without storing several
    full rank-r basis banks

When launched with torch.distributed.run, each rank trains on independent
activation batches and gradients are synchronized with DDP.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import random
import re
import socket
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import torch.distributed as dist
import torch.nn as nn

try:
    import torch_npu  # type: ignore

    HAS_NPU = hasattr(torch, "npu") and torch.npu.is_available()
    if HAS_NPU:
        try:
            torch.serialization.add_safe_globals(
                [
                    torch_npu.utils.storage._rebuild_npu_tensor,
                    torch_npu.npu._format.Format,
                ]
            )
        except Exception:
            pass
except Exception:
    torch_npu = None  # type: ignore
    HAS_NPU = False

HAS_CUDA = torch.cuda.is_available() and not HAS_NPU
MIB = 1024**2


def now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_ints(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


STUDENT_MODES = {
    "persistent",
    "rank_scale",
    "token_diag_core",
    "shuffled_diag_core",
    "token_scale",
    "token_rank_mixer",
    "token_residual",
    "mixture",
    "expert_residual",
    "token_expert_residual",
}


def parse_students(value: str) -> list[str]:
    students = [item.strip() for item in value.split(",") if item.strip()]
    unknown = sorted(set(students) - STUDENT_MODES)
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown student mode(s): {', '.join(unknown)}")
    if not students:
        raise argparse.ArgumentTypeError("at least one student mode is required")
    return students


def parse_student_specs(value: str) -> list[tuple[str, int]]:
    specs: list[tuple[str, int]] = []
    for item in (part.strip() for part in value.split(",")):
        if not item:
            continue
        try:
            mode, rank_text = item.split(":", 1)
            rank = int(rank_text)
        except (ValueError, TypeError) as exc:
            raise argparse.ArgumentTypeError(f"invalid student spec {item!r}; expected mode:rank") from exc
        if mode not in STUDENT_MODES:
            raise argparse.ArgumentTypeError(f"unknown student mode in spec: {mode}")
        if rank <= 0:
            raise argparse.ArgumentTypeError(f"student rank must be positive: {item}")
        specs.append((mode, rank))
    if len(specs) != len(set(specs)):
        raise argparse.ArgumentTypeError("duplicate --student-specs entries")
    return specs


def student_enabled(args: argparse.Namespace, mode: str, rank: int) -> bool:
    if args.student_specs:
        return (mode, rank) in set(args.student_specs)
    return mode in args.students


def parse_texts(value: str) -> list[str]:
    path = Path(value)
    if path.exists():
        return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [item.strip() for item in value.split("||") if item.strip()]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_explicit_text_file(value: str, split: str) -> tuple[list[str], dict[str, Any]]:
    path = Path(value).expanduser()
    if not path.is_file():
        raise ValueError(f"--{split}-texts-file must name an existing file: {path}")
    rows = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        raise ValueError(f"{split} text file is empty: {path}")
    if len(rows) != len(set(rows)):
        raise ValueError(f"{split} text file contains exact duplicate rows: {path}")
    resolved = path.resolve()
    return rows, {
        "split": split,
        "path": str(resolved),
        "sha256": file_sha256(resolved),
        "rows": len(rows),
        "characters": sum(len(row) for row in rows),
    }


def _masked_character_ngrams(text: str, n: int = 4) -> set[str]:
    normalized = re.sub(r"-?\d+(?:\.\d+)?", "#", text.lower())
    normalized = re.sub(r"\s+", "", normalized)
    if len(normalized) < n:
        return {normalized} if normalized else set()
    return {normalized[index : index + n] for index in range(len(normalized) - n + 1)}


def first_cross_split_near_duplicate(
    train_texts: list[str],
    eval_texts: list[str],
    threshold: float,
) -> dict[str, Any] | None:
    if threshold <= 0:
        return None
    eval_ngrams = [_masked_character_ngrams(text) for text in eval_texts]
    for train_index, train_text in enumerate(train_texts):
        left = _masked_character_ngrams(train_text)
        for eval_index, right in enumerate(eval_ngrams):
            union = left | right
            similarity = len(left & right) / len(union) if union else 1.0
            if similarity >= threshold:
                return {
                    "train_index": train_index,
                    "eval_index": eval_index,
                    "similarity": similarity,
                }
    return None


def prepare_text_splits(args: argparse.Namespace) -> tuple[dict[str, list[str]], dict[str, Any]]:
    explicit = bool(args.train_texts_file or args.eval_texts_file)
    if args.evidence_mode and args.activation_source != "text":
        raise ValueError("--evidence-mode requires --activation-source text")
    if args.evidence_mode or explicit:
        if not args.train_texts_file or not args.eval_texts_file:
            raise ValueError("explicit quality runs require both --train-texts-file and --eval-texts-file")
        train_texts, train_meta = load_explicit_text_file(args.train_texts_file, "train")
        eval_texts, eval_meta = load_explicit_text_file(args.eval_texts_file, "eval")
        exact_overlap = set(train_texts) & set(eval_texts)
        if exact_overlap:
            raise ValueError(f"train/eval exact overlap detected: {len(exact_overlap)} row(s)")
        near_duplicate = first_cross_split_near_duplicate(
            train_texts,
            eval_texts,
            args.near_duplicate_threshold,
        )
        if near_duplicate is not None:
            raise ValueError(
                "train/eval near-duplicate detected: "
                f"train[{near_duplicate['train_index']}] vs eval[{near_duplicate['eval_index']}] "
                f"similarity={near_duplicate['similarity']:.4f} "
                f">= {args.near_duplicate_threshold:.4f}"
            )
        return {"train": train_texts, "eval": eval_texts}, {
            "mode": "explicit_disjoint",
            "near_duplicate_threshold": args.near_duplicate_threshold,
            "exact_overlap": 0,
            "near_duplicate_overlap": 0,
            "train": train_meta,
            "eval": eval_meta,
        }

    texts = args.texts or DEFAULT_TEXTS
    source = "--texts" if args.texts else "DEFAULT_TEXTS"
    digest = hashlib.sha256(("\n".join(texts) + "\n").encode("utf-8")).hexdigest()
    return {"train": texts, "eval": texts}, {
        "mode": "legacy_shared_support",
        "source": source,
        "sha256": digest,
        "rows": len(texts),
    }


def setup_runtime() -> tuple[torch.device, int, int, int, str]:
    rank = int(os.environ.get("RANK", "0"))
    local_rank = int(os.environ.get("LOCAL_RANK", "0"))
    world_size = int(os.environ.get("WORLD_SIZE", "1"))
    if HAS_NPU:
        torch.npu.set_device(local_rank)
        device = torch.device(f"npu:{local_rank}")
        backend = "hccl"
    elif HAS_CUDA:
        torch.cuda.set_device(local_rank)
        device = torch.device(f"cuda:{local_rank}")
        backend = "nccl"
    else:
        device = torch.device("cpu")
        backend = "gloo"
    if world_size > 1 and not dist.is_initialized():
        dist.init_process_group(backend=backend)
    return device, rank, local_rank, world_size, backend


def sync_device() -> None:
    if HAS_NPU:
        torch.npu.synchronize()
    elif HAS_CUDA:
        torch.cuda.synchronize()


def barrier() -> None:
    if dist.is_initialized():
        dist.barrier()


def env_payload(device: torch.device, local_rank: int, world_size: int, backend: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "hostname": socket.gethostname(),
        "python": sys.version.split()[0],
        "torch": torch.__version__,
        "backend": backend,
        "device_type": device.type,
        "local_rank": local_rank,
        "world_size": world_size,
        "ascend_rt_visible_devices": os.environ.get("ASCEND_RT_VISIBLE_DEVICES", ""),
    }
    if HAS_NPU:
        payload["torch_npu"] = getattr(torch_npu, "__version__", "unknown")
        payload["npu_count"] = torch.npu.device_count()
        try:
            payload["device_name"] = torch.npu.get_device_name(local_rank)
        except Exception:
            payload["device_name"] = "npu"
    elif HAS_CUDA:
        payload["cuda"] = torch.version.cuda
        payload["device_name"] = torch.cuda.get_device_name(local_rank)
    else:
        payload["device_name"] = "cpu"
    return payload


def elem_bytes(dtype: torch.dtype) -> int:
    return torch.empty((), dtype=dtype).element_size()


def parameter_bytes(module: nn.Module) -> int:
    return sum(p.numel() * p.element_size() for p in module.parameters())


def dense_bytes(d: int, m: int, dtype: torch.dtype) -> int:
    return 3 * d * m * elem_bytes(dtype)


def descriptor_bytes(d: int, m: int, rank: int, dtype: torch.dtype) -> int:
    return 3 * rank * (d + m) * elem_bytes(dtype)


def diagonal_core_bytes(rank: int, dtype: torch.dtype, groups: int = 1) -> int:
    """Payload size for three rank-r diagonal cores; not measured HBM traffic."""
    return groups * 3 * rank * elem_bytes(dtype)


def dtype_from_name(name: str, device: torch.device) -> torch.dtype:
    if name == "auto":
        return torch.float16 if device.type in {"npu", "cuda"} else torch.float32
    return {"fp16": torch.float16, "bf16": torch.bfloat16, "fp32": torch.float32}[name]


def safe_torch_load(path: Path) -> dict[str, torch.Tensor]:
    if HAS_NPU:
        try:
            return torch.load(path, map_location="cpu", weights_only=False)
        except TypeError:
            return torch.load(path, map_location="cpu")
    try:
        return torch.load(path, map_location="cpu", weights_only=True)
    except Exception:
        try:
            return torch.load(path, map_location="cpu", weights_only=False)
        except TypeError:
            return torch.load(path, map_location="cpu")


def iter_state_files(model_dir: Path) -> list[Path]:
    safes = sorted(model_dir.glob("*.safetensors"))
    if safes:
        return safes
    bins = sorted(model_dir.glob("pytorch_model*.bin")) + sorted(model_dir.glob("*.bin"))
    return list(dict.fromkeys(bins))


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def build_run_provenance(args: argparse.Namespace, split_meta: dict[str, Any]) -> dict[str, Any]:
    source_path = Path(__file__).resolve()
    project_root = source_path.parents[1]
    code_files = [source_path]
    code_manifest = [
        {"path": str(path), "bytes": path.stat().st_size, "sha256": file_sha256(path)}
        for path in code_files
    ]
    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        git_commit = None

    model_payload: dict[str, Any]
    if args.model_dir:
        model_dir = Path(args.model_dir).expanduser().resolve()
        if not model_dir.is_dir():
            raise ValueError(f"model directory does not exist: {model_dir}")
        model_files = iter_state_files(model_dir)
        for pattern in (
            "config.json",
            "generation_config.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "tokenizer.model",
            "vocab.json",
            "merges.txt",
            "added_tokens.json",
            "special_tokens_map.json",
            "*.tiktoken",
            "*.py",
        ):
            model_files.extend(sorted(model_dir.glob(pattern)))
        model_files = list(dict.fromkeys(path.resolve() for path in model_files if path.is_file()))
        if not iter_state_files(model_dir):
            raise ValueError(f"model directory has no safetensors or .bin state file: {model_dir}")
        file_rows = []
        for path in model_files:
            file_rows.append(
                {
                    "path": str(path.relative_to(model_dir)),
                    "bytes": path.stat().st_size,
                    "sha256": file_sha256(path),
                }
            )
        model_payload = {
            "path": str(model_dir),
            "files": file_rows,
            "digest": canonical_sha256(file_rows),
        }
    else:
        model_payload = {
            "path": None,
            "source": "synthetic",
            "digest": canonical_sha256({"d": args.d, "m": args.m, "seed": args.seed}),
        }

    payload = {
        "schema_version": 1,
        "argv": list(sys.argv),
        "git_commit": git_commit,
        "code": code_manifest,
        "code_digest": canonical_sha256(code_manifest),
        "model": model_payload,
        "data": split_meta,
        "packages": {
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "torch_npu": None if torch_npu is None else getattr(torch_npu, "__version__", "unknown"),
            "transformers": _package_version("transformers"),
            "safetensors": _package_version("safetensors"),
        },
    }
    payload["run_input_digest"] = canonical_sha256(
        {
            "model": model_payload["digest"],
            "data": split_meta,
            "code": payload["code_digest"],
            "argv": payload["argv"],
        }
    )
    return payload


def broadcast_provenance(payload: dict[str, Any] | None, rank: int) -> dict[str, Any]:
    if not dist.is_initialized():
        assert payload is not None
        return payload
    values: list[Any] = [payload if rank == 0 else None]
    dist.broadcast_object_list(values, src=0)
    if not isinstance(values[0], dict):
        raise RuntimeError("rank 0 did not broadcast run provenance")
    return values[0]


def load_state_file(path: Path) -> dict[str, torch.Tensor]:
    if path.suffix == ".safetensors":
        from safetensors.torch import load_file  # type: ignore

        return load_file(str(path), device="cpu")
    return safe_torch_load(path)


def find_ffn_triplet(model_dir: Path, layer: int | None) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, dict[str, str]]:
    names = {
        "gate": [
            r"model\.layers\.(\d+)\.mlp\.gate_proj\.weight",
            r"layers\.(\d+)\.mlp\.gate_proj\.weight",
        ],
        "up": [
            r"model\.layers\.(\d+)\.mlp\.up_proj\.weight",
            r"layers\.(\d+)\.mlp\.up_proj\.weight",
        ],
        "down": [
            r"model\.layers\.(\d+)\.mlp\.down_proj\.weight",
            r"layers\.(\d+)\.mlp\.down_proj\.weight",
        ],
    }
    found: dict[int, dict[str, tuple[str, torch.Tensor]]] = {}
    # Fast path: when a specific layer is requested and the model is stored
    # in safetensors shards, read only the target layer's three tensors
    # lazily instead of loading every shard fully (matters for large models
    # on slow filesystems; results are identical to the full-scan path).
    if layer is not None:
        safes = sorted(model_dir.glob("*.safetensors"))
        if safes:
            try:
                from safetensors import safe_open  # type: ignore

                for state_path in safes:
                    with safe_open(str(state_path), framework="pt", device="cpu") as f:
                        for key in f.keys():
                            for kind, patterns in names.items():
                                for pattern in patterns:
                                    match = re.fullmatch(pattern, key)
                                    if match and int(match.group(1)) == layer:
                                        found.setdefault(layer, {})[kind] = (
                                            key,
                                            f.get_tensor(key).float().cpu(),
                                        )
                    if {"gate", "up", "down"} <= set(found.get(layer, {})):
                        parts = found[layer]
                        gate = parts["gate"][1].t().contiguous()
                        up = parts["up"][1].t().contiguous()
                        down = parts["down"][1].t().contiguous()
                        return gate, up, down, {
                            "gate": parts["gate"][0],
                            "up": parts["up"][0],
                            "down": parts["down"][0],
                            "state_file": str(state_path),
                            "layer": str(layer),
                        }
            except Exception:
                found.clear()  # fall back to the full-scan path below
    for state_path in iter_state_files(model_dir):
        state = load_state_file(state_path)
        for key, tensor in state.items():
            if not torch.is_tensor(tensor) or tensor.ndim != 2:
                continue
            for kind, patterns in names.items():
                for pattern in patterns:
                    match = re.fullmatch(pattern, key)
                    if match:
                        idx = int(match.group(1))
                        found.setdefault(idx, {})[kind] = (key, tensor.float().cpu())
        complete = [idx for idx, parts in found.items() if {"gate", "up", "down"} <= set(parts)]
        if complete:
            chosen = layer if layer is not None else min(complete)
            if chosen in complete:
                parts = found[chosen]
                gate = parts["gate"][1].t().contiguous()
                up = parts["up"][1].t().contiguous()
                down = parts["down"][1].t().contiguous()
                return gate, up, down, {
                    "gate": parts["gate"][0],
                    "up": parts["up"][0],
                    "down": parts["down"][0],
                    "state_file": str(state_path),
                    "layer": str(chosen),
                }
    raise RuntimeError(f"could not find Qwen/LLaMA-style gate/up/down FFN weights in {model_dir}")


def make_synthetic_teacher(d: int, m: int, seed: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, dict[str, str]]:
    gen = torch.Generator(device="cpu").manual_seed(seed)
    scale_d = 1.0 / math.sqrt(d)
    scale_m = 1.0 / math.sqrt(m)
    gate = torch.randn(d, m, generator=gen) * scale_d
    up = torch.randn(d, m, generator=gen) * scale_d
    down = torch.randn(m, d, generator=gen) * scale_m
    return gate, up, down, {"source": "synthetic", "layer": "none"}


DEFAULT_TEXTS = [
    "Transformer feed-forward layers dominate parameter movement in large language model inference.",
    "Efficient systems research should measure latency, memory traffic, communication, and model quality together.",
    "A conditional generator can select different low-rank subspaces for code, mathematics, dialogue, and factual prose.",
    "Bandwidth-aware neural architecture design changes where weights live during execution.",
    "The quick brown fox writes a compiler pass for a matrix multiplication kernel.",
    "In distributed training, gradient synchronization can become the bottleneck when layers contain huge dense matrices.",
    "Scientific evidence improves when negative baselines are shown beside positive systems measurements.",
    "Low-rank approximation alone is not enough when pretrained feed-forward matrices have slowly decaying spectra.",
    "A robust experiment should compare static SVD, persistent low-rank factors, and generated ephemeral factors.",
    "Careful ablation studies distinguish an architectural contribution from an implementation artifact.",
    "Machine learning papers need clear claims, strong baselines, and reproducible artifacts.",
    "The model solves a small algebra problem by composing several intermediate facts.",
    "During long-context decoding, attention cache storage and feed-forward weight bandwidth are different resources.",
    "A top journal submission needs evidence that quality survives the proposed systems optimization.",
    "Routing among basis banks can give token groups specialized descriptor subspaces.",
    "The generated descriptors are consumed by the kernel and should not become durable model tensors.",
]


def atomic_json_write(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


def atomic_torch_save(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    torch.save(payload, tmp_path)
    os.replace(tmp_path, path)


def cache_root(args: argparse.Namespace) -> Path:
    if args.cache_dir:
        return Path(args.cache_dir)
    if args.evidence_mode:
        return Path(args.outdir) / "cache"
    return Path(tempfile.gettempdir())


def cache_marker_path(cache_path: Path) -> Path:
    return cache_path.with_suffix(cache_path.suffix + ".ready.json")


def load_fingerprinted_cache(cache_path: Path, fingerprint: str) -> dict[str, Any] | None:
    marker_path = cache_marker_path(cache_path)
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        if marker.get("fingerprint") != fingerprint or marker.get("cache") != str(cache_path):
            return None
        payload = safe_torch_load(cache_path)
        if payload.get("fingerprint") != fingerprint:
            return None
        return payload
    except (FileNotFoundError, json.JSONDecodeError, OSError, RuntimeError, EOFError):
        return None


def publish_fingerprinted_cache(payload: dict[str, Any], cache_path: Path, fingerprint: str) -> None:
    marker_path = cache_marker_path(cache_path)
    marker_path.unlink(missing_ok=True)
    atomic_torch_save({**payload, "fingerprint": fingerprint}, cache_path)
    atomic_json_write(
        {
            "schema_version": 1,
            "cache": str(cache_path),
            "fingerprint": fingerprint,
            "published_at": now_tag(),
        },
        marker_path,
    )


def wait_for_fingerprinted_cache(
    cache_path: Path,
    fingerprint: str,
    timeout_s: int,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        payload = load_fingerprinted_cache(cache_path, fingerprint)
        if payload is not None:
            return payload
        time.sleep(1.0)
    raise TimeoutError(f"timed out waiting for cache {cache_path} fingerprint={fingerprint}")


def select_valid_activations(activations: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    if activations.shape[:2] != attention_mask.shape:
        raise ValueError(
            f"activation/mask shape mismatch: {tuple(activations.shape)} vs {tuple(attention_mask.shape)}"
        )
    valid = attention_mask.detach().to(device="cpu", dtype=torch.bool)
    selected = activations.detach().float().cpu()[valid]
    if selected.numel() == 0:
        raise ValueError("activation batch contains no attention-mask-valid tokens")
    return selected.contiguous()


def activation_cache_fingerprint(args: argparse.Namespace, split: str) -> str:
    provenance = getattr(args, "_provenance")
    split_meta = getattr(args, "_split_meta")
    return canonical_sha256(
        {
            "kind": "valid_token_activation_cache_v2",
            "model": provenance["model"]["digest"],
            "code": provenance["code_digest"],
            "split": split,
            "split_meta": split_meta.get(split, split_meta),
            "layer": args.layer,
            "activation_seed": args.activation_seed,
            "activation_max_batches": args.activation_max_batches,
            "activation_text_batch": args.activation_text_batch,
            "activation_seq": args.activation_seq,
        }
    )


def activation_cache_path(args: argparse.Namespace, split: str, fingerprint: str) -> Path:
    return cache_root(args) / f"mwg_valid_activations_{split}_{fingerprint[:20]}.pt"


def _capture_activation_split(
    model: nn.Module,
    tokenizer: Any,
    args: argparse.Namespace,
    device: torch.device,
    split: str,
    texts: list[str],
) -> torch.Tensor:
    layer = 0 if args.layer is None else args.layer
    captured: list[torch.Tensor] = []

    def hook(_module: nn.Module, inputs: tuple[torch.Tensor, ...], _output: Any) -> None:
        captured.append(inputs[0].detach())

    handle = model.model.layers[layer].mlp.register_forward_hook(hook)  # type: ignore[attr-defined]
    order = list(range(len(texts)))
    random.Random(args.activation_seed + (17 if split == "train" else 104729)).shuffle(order)
    max_texts = args.activation_max_batches * args.activation_text_batch
    order = order[:max_texts]
    batches: list[torch.Tensor] = []
    try:
        with torch.no_grad():
            for batch_index, start in enumerate(range(0, len(order), args.activation_text_batch)):
                indices = order[start : start + args.activation_text_batch]
                batch_texts = [texts[index] for index in indices]
                encoded = tokenizer(
                    batch_texts,
                    return_tensors="pt",
                    padding="max_length",
                    truncation=True,
                    max_length=args.activation_seq,
                )
                encoded = {key: value.to(device) for key, value in encoded.items()}
                captured.clear()
                _ = model(**encoded, use_cache=False)
                if not captured:
                    raise RuntimeError(f"MLP hook did not capture activations for layer {layer}")
                batches.append(select_valid_activations(captured[0], encoded["attention_mask"]))
                if batch_index == 0 or (batch_index + 1) % max(1, args.activation_log_every) == 0:
                    print(
                        json.dumps(
                            {
                                "event": "activation_capture",
                                "split": split,
                                "batch": batch_index + 1,
                                "valid_tokens": int(batches[-1].shape[0]),
                            }
                        ),
                        flush=True,
                    )
    finally:
        handle.remove()
    if not batches:
        raise RuntimeError(f"no activation batches captured for {split}")
    return torch.cat(batches, dim=0).contiguous()


def capture_text_activation_splits(
    args: argparse.Namespace,
    device: torch.device,
    rank: int,
    world_size: int,
) -> dict[str, torch.Tensor | None]:
    if args.activation_source != "text":
        return {"train": None, "eval": None}
    if not args.model_dir:
        raise RuntimeError("--activation-source text requires --model-dir")

    text_splits: dict[str, list[str]] = getattr(args, "_text_splits")
    capture_names = ["train", "eval"] if args.evidence_mode or text_splits["train"] != text_splits["eval"] else ["train"]
    cache_specs = {
        split: (
            activation_cache_fingerprint(args, split),
            None,
        )
        for split in capture_names
    }
    cache_specs = {
        split: (fingerprint, activation_cache_path(args, split, fingerprint))
        for split, (fingerprint, _unused) in cache_specs.items()
    }

    payloads: dict[str, dict[str, Any]] = {}
    if rank == 0:
        missing = []
        for split, (fingerprint, path) in cache_specs.items():
            payload = load_fingerprinted_cache(path, fingerprint)
            if payload is None:
                missing.append(split)
            else:
                payloads[split] = payload
        if missing:
            try:
                from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore
            except Exception as exc:
                raise RuntimeError("text activation capture requires transformers") from exc
            model_dir = Path(args.model_dir)
            tokenizer = AutoTokenizer.from_pretrained(str(model_dir), trust_remote_code=True)
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
            model_dtype = torch.float16 if device.type in {"npu", "cuda"} else torch.float32
            model = AutoModelForCausalLM.from_pretrained(
                str(model_dir),
                torch_dtype=model_dtype,
                trust_remote_code=True,
                low_cpu_mem_usage=True,
            ).to(device)
            model.eval()
            try:
                for split in missing:
                    fingerprint, path = cache_specs[split]
                    activations = _capture_activation_split(
                        model,
                        tokenizer,
                        args,
                        device,
                        split,
                        text_splits[split],
                    )
                    publish_fingerprinted_cache(
                        {
                            "split": split,
                            "activations": activations.half(),
                            "shape": tuple(activations.shape),
                            "valid_tokens": int(activations.shape[0]),
                        },
                        path,
                        fingerprint,
                    )
                    payloads[split] = load_fingerprinted_cache(path, fingerprint) or {}
                    if not payloads[split]:
                        raise RuntimeError(f"failed to validate freshly written activation cache: {path}")
                    print(
                        json.dumps(
                            {
                                "event": "activation_cache_ready",
                                "split": split,
                                "path": str(path),
                                "shape": list(activations.shape),
                            }
                        ),
                        flush=True,
                    )
            finally:
                del model
                if HAS_NPU:
                    torch.npu.empty_cache()
                elif HAS_CUDA:
                    torch.cuda.empty_cache()
    else:
        for split, (fingerprint, path) in cache_specs.items():
            payloads[split] = wait_for_fingerprinted_cache(path, fingerprint, args.cache_wait_timeout)

    barrier()
    result = {split: payloads[split]["activations"].float() for split in capture_names}
    if "eval" not in result:
        result["eval"] = result["train"]
    return {"train": result["train"], "eval": result["eval"]}


def svd_factor_sweep(
    weight: torch.Tensor,
    ranks: list[int],
    method: str = "exact",
    oversample: int = 16,
    niter: int = 2,
) -> dict[int, tuple[torch.Tensor, torch.Tensor, float]]:
    unique_ranks = sorted(set(ranks))
    if not unique_ranks or unique_ranks[0] <= 0:
        raise ValueError("SVD ranks must be positive")
    matrix = weight.float()
    maximum_rank = unique_ranks[-1]
    available_rank = min(matrix.shape)
    if maximum_rank > available_rank:
        raise ValueError(
            f"requested rank {maximum_rank} exceeds matrix rank bound {available_rank} "
            f"for shape {tuple(matrix.shape)}"
        )
    if method == "pca_lowrank":
        q = min(available_rank, maximum_rank + max(0, oversample))
        u, s, v = torch.pca_lowrank(matrix, q=q, center=False, niter=niter)
        vh = v.t()
    else:
        u, s, vh = torch.linalg.svd(matrix, full_matrices=False)
    # Use the full matrix Frobenius energy even when pca_lowrank returns only
    # q singular values; otherwise the retained-energy ratio omits the tail.
    total = torch.sum(matrix.square()).clamp_min(1e-12)
    output: dict[int, tuple[torch.Tensor, torch.Tensor, float]] = {}
    for rank in unique_ranks:
        kept = torch.sum(s[:rank].square())
        root = torch.sqrt(s[:rank])
        left = u[:, :rank] * root.view(1, -1)
        right = root.view(-1, 1) * vh[:rank, :]
        output[rank] = (
            left.contiguous(),
            right.contiguous(),
            float((kept / total).item()),
        )
    return output


def svd_factors(
    weight: torch.Tensor,
    rank: int,
    method: str = "exact",
    oversample: int = 16,
    niter: int = 2,
) -> tuple[torch.Tensor, torch.Tensor, float]:
    return svd_factor_sweep(
        weight,
        [rank],
        method=method,
        oversample=oversample,
        niter=niter,
    )[rank]


class DenseTeacher(nn.Module):
    def __init__(self, gate: torch.Tensor, up: torch.Tensor, down: torch.Tensor, dtype: torch.dtype):
        super().__init__()
        self.register_buffer("gate", gate.to(dtype=dtype))
        self.register_buffer("up", up.to(dtype=dtype))
        self.register_buffer("down", down.to(dtype=dtype))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return (torch.nn.functional.silu(x @ self.gate) * (x @ self.up)) @ self.down


class LowRankFFN(nn.Module):
    def __init__(
        self,
        factors: dict[str, tuple[torch.Tensor, torch.Tensor]],
        dtype: torch.dtype,
        generator: str = "none",
        generator_hidden: int | None = None,
        residual_rank: int = 8,
        scale_amplitude: float = 0.05,
        basis_count: int = 4,
        basis_noise: float = 0.01,
    ):
        super().__init__()
        if generator not in {
            "none",
            "rank_scale",
            "token_diag_core",
            "shuffled_diag_core",
            "token_scale",
            "token_rank_mixer",
            "token_residual",
            "mixture",
            "expert_residual",
            "token_expert_residual",
        }:
            raise ValueError(f"unknown generator mode: {generator}")
        self.generator_mode = generator
        self.rank = factors["up"][0].shape[1]
        self.d = factors["up"][0].shape[0]
        self.m = factors["up"][1].shape[1]
        self.residual_rank = min(max(1, residual_rank), self.rank)
        self.scale_amplitude = scale_amplitude
        self.basis_count = max(
            1,
            basis_count if generator in {"mixture", "expert_residual", "token_expert_residual"} else 1,
        )

        def make_bank(name: str, side: int) -> nn.Parameter:
            base = factors[name][side].to(dtype=dtype)
            if generator != "mixture" or self.basis_count == 1:
                return nn.Parameter(base)
            gen = torch.Generator(device="cpu").manual_seed(17 + len(name) * 31 + side)
            banks = []
            for index in range(self.basis_count):
                noise = torch.randn(base.shape, generator=gen, dtype=torch.float32).to(dtype=dtype)
                banks.append(base + (basis_noise * (index + 1)) * noise)
            return nn.Parameter(torch.stack(banks, dim=0))

        self.up_u = make_bank("up", 0)
        self.up_v = make_bank("up", 1)
        self.gate_u = make_bank("gate", 0)
        self.gate_v = make_bank("gate", 1)
        self.down_u = make_bank("down", 0)
        self.down_v = make_bank("down", 1)
        hidden = generator_hidden or min(256, max(32, self.d // 8))
        self.generator_hidden = hidden
        if generator != "none":
            if generator == "token_rank_mixer":
                out_dim = 3 * self.rank * self.rank
            elif generator in ("token_diag_core", "shuffled_diag_core"):
                out_dim = 3 * self.rank
            else:
                out_dim = 6 * self.rank + (
                    self.basis_count
                    if generator in {"mixture", "expert_residual", "token_expert_residual"}
                    else 0
                )
            self.generator = nn.Sequential(
                nn.Linear(self.d, hidden, dtype=torch.float32),
                nn.SiLU(),
                nn.Linear(hidden, out_dim, dtype=torch.float32),
            )
        else:
            self.generator = None
        if generator in {"token_residual", "mixture"}:
            self.residual_gate_a = nn.Linear(self.d, self.residual_rank, bias=False, dtype=dtype)
            self.residual_gate_b = nn.Linear(self.residual_rank, self.m, bias=False, dtype=dtype)
            self.residual_up_a = nn.Linear(self.d, self.residual_rank, bias=False, dtype=dtype)
            self.residual_up_b = nn.Linear(self.residual_rank, self.m, bias=False, dtype=dtype)
            self.residual_down_a = nn.Linear(self.m, self.residual_rank, bias=False, dtype=dtype)
            self.residual_down_b = nn.Linear(self.residual_rank, self.d, bias=False, dtype=dtype)
            self._init_residual()
        else:
            self.residual_gate_a = None
            self.residual_gate_b = None
            self.residual_up_a = None
            self.residual_up_b = None
            self.residual_down_a = None
            self.residual_down_b = None
        if generator in {"expert_residual", "token_expert_residual"}:
            self.expert_gate_a = nn.Parameter(torch.empty(self.basis_count, self.d, self.residual_rank, dtype=dtype))
            self.expert_gate_b = nn.Parameter(torch.empty(self.basis_count, self.residual_rank, self.m, dtype=dtype))
            self.expert_up_a = nn.Parameter(torch.empty(self.basis_count, self.d, self.residual_rank, dtype=dtype))
            self.expert_up_b = nn.Parameter(torch.empty(self.basis_count, self.residual_rank, self.m, dtype=dtype))
            self.expert_down_a = nn.Parameter(torch.empty(self.basis_count, self.m, self.residual_rank, dtype=dtype))
            self.expert_down_b = nn.Parameter(torch.empty(self.basis_count, self.residual_rank, self.d, dtype=dtype))
            self._init_experts()
        else:
            self.expert_gate_a = None
            self.expert_gate_b = None
            self.expert_up_a = None
            self.expert_up_b = None
            self.expert_down_a = None
            self.expert_down_b = None

    def _init_residual(self) -> None:
        modules = [
            self.residual_gate_a,
            self.residual_gate_b,
            self.residual_up_a,
            self.residual_up_b,
            self.residual_down_a,
            self.residual_down_b,
        ]
        for module in modules:
            assert module is not None
            nn.init.normal_(module.weight, mean=0.0, std=1e-3)

    def _init_experts(self) -> None:
        for param in [
            self.expert_gate_a,
            self.expert_gate_b,
            self.expert_up_a,
            self.expert_up_b,
            self.expert_down_a,
            self.expert_down_b,
        ]:
            assert param is not None
            nn.init.normal_(param, mean=0.0, std=1e-3)

    def _factors(self, x: torch.Tensor) -> tuple[torch.Tensor, ...]:
        if self.generator is None:
            return self.up_u, self.up_v, self.gate_u, self.gate_v, self.down_u, self.down_v
        context = x.float() if self.generator_mode == "token_scale" else x.float().mean(dim=(0, 1))
        generated = self.generator(context)
        if self.generator_mode in {"mixture", "expert_residual"}:
            scale_logits = generated[: 6 * self.rank]
            route_logits = generated[6 * self.rank :]
            alpha = torch.softmax(route_logits.float(), dim=0).to(dtype=x.dtype)
            self._last_alpha = alpha

            if self.generator_mode == "mixture":
                def blend(bank: torch.Tensor) -> torch.Tensor:
                    view_shape = (self.basis_count,) + (1,) * (bank.ndim - 1)
                    return torch.sum(bank * alpha.view(view_shape), dim=0)

                up_u = blend(self.up_u)
                up_v = blend(self.up_v)
                gate_u = blend(self.gate_u)
                gate_v = blend(self.gate_v)
                down_u = blend(self.down_u)
                down_v = blend(self.down_v)
            else:
                up_u, up_v, gate_u, gate_v, down_u, down_v = (
                    self.up_u,
                    self.up_v,
                    self.gate_u,
                    self.gate_v,
                    self.down_u,
                    self.down_v,
                )
        else:
            scale_logits = generated
            up_u, up_v, gate_u, gate_v, down_u, down_v = (
                self.up_u,
                self.up_v,
                self.gate_u,
                self.gate_v,
                self.down_u,
                self.down_v,
            )
        scales = 1.0 + self.scale_amplitude * torch.tanh(scale_logits).to(dtype=x.dtype)
        su, sv, sg, sgv, sd, sdv = scales.chunk(6, dim=-1)
        if self.generator_mode == "token_scale":
            return (
                self.up_u.unsqueeze(0).unsqueeze(0) * su.unsqueeze(-2),
                self.up_v.unsqueeze(0).unsqueeze(0) * sv.unsqueeze(-1),
                self.gate_u.unsqueeze(0).unsqueeze(0) * sg.unsqueeze(-2),
                self.gate_v.unsqueeze(0).unsqueeze(0) * sgv.unsqueeze(-1),
                self.down_u.unsqueeze(0).unsqueeze(0) * sd.unsqueeze(-2),
                self.down_v.unsqueeze(0).unsqueeze(0) * sdv.unsqueeze(-1),
            )
        return (
            up_u * su.view(1, -1),
            up_v * sv.view(-1, 1),
            gate_u * sg.view(1, -1),
            gate_v * sgv.view(-1, 1),
            down_u * sd.view(1, -1),
            down_v * sdv.view(-1, 1),
        )

    def _expert_project(self, x: torch.Tensor, a: torch.Tensor, b: torch.Tensor, alpha: torch.Tensor) -> torch.Tensor:
        expert_outputs = []
        for index in range(self.basis_count):
            expert_outputs.append((x @ a[index]) @ b[index])
        stacked = torch.stack(expert_outputs, dim=0)
        return torch.sum(stacked * alpha.view(self.basis_count, 1, 1, 1), dim=0)

    def _token_controls(self, x: torch.Tensor) -> tuple[torch.Tensor, ...]:
        assert self.generator is not None
        generated = self.generator(x.float())
        scale_logits = generated[..., : 6 * self.rank]
        route_logits = generated[..., 6 * self.rank :]
        scales = 1.0 + self.scale_amplitude * torch.tanh(scale_logits).to(dtype=x.dtype)
        alpha = torch.softmax(route_logits.float(), dim=-1).to(dtype=x.dtype)
        return (*scales.chunk(6, dim=-1), alpha)

    def _token_diag_cores(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Generate one diagonal core for each FFN projection."""
        assert self.generator is not None
        logits = self.generator(x.float())
        cores = 1.0 + self.scale_amplitude * torch.tanh(logits).to(dtype=x.dtype)
        return cores.chunk(3, dim=-1)

    @staticmethod
    def _token_diag_project(
        x: torch.Tensor,
        u: torch.Tensor,
        v: torch.Tensor,
        core: torch.Tensor,
    ) -> torch.Tensor:
        return ((x @ u) * core) @ v

    @staticmethod
    def _token_scaled_project(
        x: torch.Tensor,
        u: torch.Tensor,
        v: torch.Tensor,
        left_scale: torch.Tensor,
        right_scale: torch.Tensor,
    ) -> torch.Tensor:
        return ((x @ u) * left_scale * right_scale) @ v

    def _token_expert_project(
        self,
        x: torch.Tensor,
        a: torch.Tensor,
        b: torch.Tensor,
        alpha: torch.Tensor,
    ) -> torch.Tensor:
        out: torch.Tensor | None = None
        for index in range(self.basis_count):
            contribution = ((x @ a[index]) @ b[index]) * alpha[..., index : index + 1]
            out = contribution if out is None else out + contribution
        assert out is not None
        return out

    def _forward_token_expert_residual(self, x: torch.Tensor) -> torch.Tensor:
        su, sv, sg, sgv, sd, sdv, alpha = self._token_controls(x)
        assert self.expert_gate_a is not None
        assert self.expert_gate_b is not None
        assert self.expert_up_a is not None
        assert self.expert_up_b is not None
        assert self.expert_down_a is not None
        assert self.expert_down_b is not None

        up = self._token_scaled_project(x, self.up_u, self.up_v, su, sv)
        gate = self._token_scaled_project(x, self.gate_u, self.gate_v, sg, sgv)
        up = up + self._token_expert_project(x, self.expert_up_a, self.expert_up_b, alpha)
        gate = gate + self._token_expert_project(x, self.expert_gate_a, self.expert_gate_b, alpha)
        hidden = torch.nn.functional.silu(gate) * up
        out = self._token_scaled_project(hidden, self.down_u, self.down_v, sd, sdv)
        return out + self._token_expert_project(hidden, self.expert_down_a, self.expert_down_b, alpha)

    def _forward_token_diag_core(self, x: torch.Tensor) -> torch.Tensor:
        core_up, core_gate, core_down = self._token_diag_cores(x)
        up = self._token_diag_project(x, self.up_u, self.up_v, core_up)
        gate = self._token_diag_project(x, self.gate_u, self.gate_v, core_gate)
        hidden = torch.nn.functional.silu(gate) * up
        return self._token_diag_project(hidden, self.down_u, self.down_v, core_down)

    def _forward_shuffled_diag_core(self, x: torch.Tensor) -> torch.Tensor:
        """Shuffled-context control: the generator sees a randomly permuted
        token's context, but the actual projection still uses the real x.

        If the generated core's quality depends on context-conditioning, this
        control should degrade toward the persistent-low-rank baseline (no
        context signal).  If it matches the causal core, the generator is
        effectively learning a fixed (context-independent) correction.
        """
        batch_size = x.shape[0]
        if batch_size > 1:
            perm = torch.randperm(batch_size, device=x.device)
            shuffled_x = x[perm]
        else:
            # Single-sample batch: shuffle across the sequence dimension
            seq_len = x.shape[1]
            if seq_len > 1:
                perm = torch.randperm(seq_len, device=x.device)
                shuffled_x = x[:, perm]
            else:
                shuffled_x = x  # degenerate case, no shuffle possible
        core_up, core_gate, core_down = self._token_diag_cores(shuffled_x)
        up = self._token_diag_project(x, self.up_u, self.up_v, core_up)
        gate = self._token_diag_project(x, self.gate_u, self.gate_v, core_gate)
        hidden = torch.nn.functional.silu(gate) * up
        return self._token_diag_project(hidden, self.down_u, self.down_v, core_down)

    def _rank_mixers(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        assert self.generator is not None
        logits = self.generator(x.float()).view(*x.shape[:2], 3, self.rank, self.rank)
        delta = self.scale_amplitude * torch.tanh(logits).to(dtype=x.dtype)
        eye = torch.eye(self.rank, device=x.device, dtype=x.dtype).view(1, 1, 1, self.rank, self.rank)
        mixers = eye + delta
        return mixers[:, :, 0], mixers[:, :, 1], mixers[:, :, 2]

    def _mix_rank(self, z: torch.Tensor, mixer: torch.Tensor) -> torch.Tensor:
        return torch.matmul(z.unsqueeze(-2), mixer).squeeze(-2)

    def _forward_token_rank_mixer(self, x: torch.Tensor) -> torch.Tensor:
        mix_up, mix_gate, mix_down = self._rank_mixers(x)
        up = self._mix_rank(x @ self.up_u, mix_up) @ self.up_v
        gate = self._mix_rank(x @ self.gate_u, mix_gate) @ self.gate_v
        hidden = torch.nn.functional.silu(gate) * up
        return self._mix_rank(hidden @ self.down_u, mix_down) @ self.down_v

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.generator_mode == "token_diag_core":
            return self._forward_token_diag_core(x)
        if self.generator_mode == "shuffled_diag_core":
            return self._forward_shuffled_diag_core(x)
        if self.generator_mode == "token_rank_mixer":
            return self._forward_token_rank_mixer(x)
        if self.generator_mode == "token_expert_residual":
            return self._forward_token_expert_residual(x)
        up_u, up_v, gate_u, gate_v, down_u, down_v = self._factors(x)
        if self.generator_mode == "token_scale":
            up = torch.matmul(torch.matmul(x.unsqueeze(-2), up_u), up_v).squeeze(-2)
            gate = torch.matmul(torch.matmul(x.unsqueeze(-2), gate_u), gate_v).squeeze(-2)
        else:
            up = (x @ up_u) @ up_v
            gate = (x @ gate_u) @ gate_v
        if self.generator_mode in {"token_residual", "mixture"}:
            assert self.residual_gate_a is not None
            assert self.residual_gate_b is not None
            assert self.residual_up_a is not None
            assert self.residual_up_b is not None
            gate = gate + self.residual_gate_b(torch.nn.functional.silu(self.residual_gate_a(x)))
            up = up + self.residual_up_b(torch.nn.functional.silu(self.residual_up_a(x)))
        if self.generator_mode == "expert_residual":
            alpha = getattr(self, "_last_alpha")
            assert self.expert_gate_a is not None
            assert self.expert_gate_b is not None
            assert self.expert_up_a is not None
            assert self.expert_up_b is not None
            gate = gate + self._expert_project(x, self.expert_gate_a, self.expert_gate_b, alpha)
            up = up + self._expert_project(x, self.expert_up_a, self.expert_up_b, alpha)
        hidden = torch.nn.functional.silu(gate) * up
        if self.generator_mode == "token_scale":
            out = torch.matmul(torch.matmul(hidden.unsqueeze(-2), down_u), down_v).squeeze(-2)
        else:
            out = (hidden @ down_u) @ down_v
        if self.generator_mode in {"token_residual", "mixture"}:
            assert self.residual_down_a is not None
            assert self.residual_down_b is not None
            out = out + self.residual_down_b(torch.nn.functional.silu(self.residual_down_a(hidden)))
        if self.generator_mode == "expert_residual":
            alpha = getattr(self, "_last_alpha")
            assert self.expert_down_a is not None
            assert self.expert_down_b is not None
            out = out + self._expert_project(hidden, self.expert_down_a, self.expert_down_b, alpha)
        return out


@dataclass
class Metrics:
    mse: float
    relative_mse: float
    cosine: float
    token_relative_mse_p50: float
    token_relative_mse_p90: float
    token_relative_mse_p95: float
    token_relative_mse_p99: float
    token_relative_mse_max: float


def reduce_mean(value: torch.Tensor) -> torch.Tensor:
    if dist.is_initialized():
        dist.all_reduce(value, op=dist.ReduceOp.SUM)
        value /= dist.get_world_size()
    return value


def make_batch(batch: int, seq: int, d: int, device: torch.device, dtype: torch.dtype, seed: int) -> torch.Tensor:
    gen = torch.Generator(device="cpu").manual_seed(seed)
    x = torch.randn(batch, seq, d, generator=gen, dtype=torch.float32)
    # Mixture amplitudes make the quality test less tied to a single Gaussian shell.
    scales = torch.empty(batch, seq, 1).uniform_(0.5, 1.5, generator=gen)
    return (x * scales).to(device=device, dtype=dtype)


def sample_batch(
    args: argparse.Namespace,
    device: torch.device,
    dtype: torch.dtype,
    seed: int,
    split: str = "train",
) -> torch.Tensor:
    activation_cache = getattr(args, f"_{split}_activation_cache", None)
    if activation_cache is None:
        return make_batch(args.batch, args.seq, args.d, device, dtype, seed)

    gen = torch.Generator(device="cpu").manual_seed(seed)
    if activation_cache.ndim == 2:
        total, width = activation_cache.shape
        if width != args.d:
            raise ValueError(f"activation width {width} does not match d={args.d}")
        indices = torch.randint(0, total, (args.batch * args.seq,), generator=gen)
        x = activation_cache.index_select(0, indices).view(args.batch, args.seq, args.d)
        return x.to(device=device, dtype=dtype)
    if activation_cache.ndim != 3:
        raise ValueError(f"activation cache must be 2-D or 3-D, got {activation_cache.ndim}-D")
    total, cache_seq, _ = activation_cache.shape
    indices = torch.randint(0, total, (args.batch,), generator=gen)
    x = activation_cache.index_select(0, indices)
    if args.seq < cache_seq:
        start = int(torch.randint(0, cache_seq - args.seq + 1, (1,), generator=gen).item())
        x = x[:, start : start + args.seq, :]
    elif args.seq > cache_seq:
        repeats = math.ceil(args.seq / cache_seq)
        x = x.repeat(1, repeats, 1)[:, : args.seq, :]
    return x.to(device=device, dtype=dtype)


@torch.no_grad()
def evaluate(model: nn.Module, teacher: DenseTeacher, args: argparse.Namespace, device: torch.device, dtype: torch.dtype, rank: int) -> Metrics:
    model.eval()
    sum_mse = torch.zeros((), device=device, dtype=torch.float32)
    sum_target = torch.zeros((), device=device, dtype=torch.float32)
    sum_dot = torch.zeros((), device=device, dtype=torch.float32)
    sum_pred_norm = torch.zeros((), device=device, dtype=torch.float32)
    sum_target_norm = torch.zeros((), device=device, dtype=torch.float32)
    token_relative_errors: list[torch.Tensor] = []
    for step in range(args.eval_batches):
        x = sample_batch(
            args,
            device,
            dtype,
            args.seed + 100_000 + step * 997 + rank * 17,
            split="eval",
        )
        target = teacher(x).float()
        pred = model(x).float()
        diff = pred - target
        sum_mse += diff.square().mean()
        sum_target += target.square().mean()
        sum_dot += (pred * target).sum()
        sum_pred_norm += pred.square().sum()
        sum_target_norm += target.square().sum()
        token_relative_errors.append(
            diff.square().mean(dim=-1)
            / target.square().mean(dim=-1).clamp_min(1e-12)
        )
    values = torch.stack([sum_mse, sum_target, sum_dot, sum_pred_norm, sum_target_norm])
    values = reduce_mean(values)
    mse = values[0] / args.eval_batches
    target_power = (values[1] / args.eval_batches).clamp_min(1e-12)
    cosine = values[2] / (torch.sqrt(values[3].clamp_min(1e-12)) * torch.sqrt(values[4].clamp_min(1e-12)))
    tail_values = torch.cat([value.reshape(-1) for value in token_relative_errors])
    if dist.is_initialized():
        gathered = [torch.empty_like(tail_values) for _ in range(dist.get_world_size())]
        dist.all_gather(gathered, tail_values)
        tail_values = torch.cat(gathered)
    tail_values = tail_values.float().cpu()
    quantiles = torch.quantile(
        tail_values,
        torch.tensor([0.50, 0.90, 0.95, 0.99]),
    )
    return Metrics(
        mse=float(mse.item()),
        relative_mse=float((mse / target_power).item()),
        cosine=float(cosine.item()),
        token_relative_mse_p50=float(quantiles[0].item()),
        token_relative_mse_p90=float(quantiles[1].item()),
        token_relative_mse_p95=float(quantiles[2].item()),
        token_relative_mse_p99=float(quantiles[3].item()),
        token_relative_mse_max=float(tail_values.max().item()),
    )


def _to_cpu_tree(value: Any) -> Any:
    if isinstance(value, torch.Tensor):
        return value.detach().cpu()
    if isinstance(value, dict):
        return {key: _to_cpu_tree(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_cpu_tree(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_cpu_tree(item) for item in value)
    return value


def capture_rng_state() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "python": random.getstate(),
        "torch_cpu": torch.get_rng_state().cpu(),
    }
    if HAS_NPU:
        try:
            payload["npu"] = [state.cpu() for state in torch.npu.get_rng_state_all()]
        except Exception:
            payload["npu"] = None
    elif HAS_CUDA:
        payload["cuda"] = [state.cpu() for state in torch.cuda.get_rng_state_all()]
    return payload


def restore_rng_state(payload: dict[str, Any]) -> None:
    if payload.get("python") is not None:
        random.setstate(payload["python"])
    if payload.get("torch_cpu") is not None:
        torch.set_rng_state(payload["torch_cpu"])
    if HAS_NPU and payload.get("npu") is not None:
        try:
            torch.npu.set_rng_state_all(payload["npu"])
        except Exception:
            pass
    elif HAS_CUDA and payload.get("cuda") is not None:
        torch.cuda.set_rng_state_all(payload["cuda"])


def student_init_payload(model: "LowRankFFN") -> dict[str, Any]:
    return {
        "d": model.d,
        "m": model.m,
        "rank": model.rank,
        "generator_mode": model.generator_mode,
        "generator_hidden": model.generator_hidden,
        "residual_rank": model.residual_rank,
        "scale_amplitude": model.scale_amplitude,
        "basis_count": model.basis_count,
    }


def training_fingerprint(
    name: str,
    model: "LowRankFFN",
    args: argparse.Namespace,
    dtype: torch.dtype,
) -> str:
    provenance = getattr(args, "_provenance")
    return canonical_sha256(
        {
            "schema_version": 1,
            "student": name,
            "init": student_init_payload(model),
            "run_input_digest": provenance["run_input_digest"],
            "training": {
                "layer": args.layer,
                "dtype": str(dtype).replace("torch.", ""),
                "batch": args.batch,
                "seq": args.seq,
                "steps": args.steps,
                "eval_batches": args.eval_batches,
                "lr": args.lr,
                "weight_decay": args.weight_decay,
                "grad_clip": args.grad_clip,
                "seed": args.seed,
                "activation_source": args.activation_source,
            },
        }
    )


def resume_checkpoint_path(args: argparse.Namespace, name: str) -> Path:
    default = Path(args.outdir) / "checkpoints" / f"{name}.resume.pt"
    if not args.resume or args.resume == "auto":
        return default
    requested = Path(args.resume)
    if requested.suffix == ".pt":
        return requested
    return requested / f"{name}.resume.pt"


def write_progress(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    progress_path = Path(args.progress_json) if args.progress_json else Path(args.outdir) / "progress.json"
    atomic_json_write({"updated_at": now_tag(), **payload}, progress_path)


def save_training_state(
    path: Path,
    name: str,
    model: "LowRankFFN",
    optimizer: torch.optim.Optimizer,
    global_step: int,
    losses: list[float],
    fingerprint: str,
    args: argparse.Namespace,
    dtype: torch.dtype,
    completed: bool,
) -> None:
    atomic_torch_save(
        {
            "schema_version": 1,
            "student": name,
            "state_dict": {key: value.detach().cpu() for key, value in model.state_dict().items()},
            "optimizer_state_dict": _to_cpu_tree(optimizer.state_dict()),
            "global_step": global_step,
            "train_loss_trace": losses,
            "rng_state": capture_rng_state(),
            "rng_state_scope": "rank0; the current training loop is deterministic per rank",
            "config_fingerprint": fingerprint,
            "completed": completed,
            "init": student_init_payload(model),
            "config": {
                "layer": args.layer,
                "dtype": str(dtype).replace("torch.", ""),
                "activation_source": args.activation_source,
                "steps": args.steps,
                "eval_batches": args.eval_batches,
                "seed": args.seed,
            },
            "provenance": getattr(args, "_provenance"),
        },
        path,
    )


def train_student(name: str, model: nn.Module, teacher: DenseTeacher, args: argparse.Namespace, device: torch.device, dtype: torch.dtype, rank: int) -> dict[str, Any]:
    if dist.is_initialized():
        model = torch.nn.parallel.DistributedDataParallel(
            model,
            device_ids=[int(os.environ["LOCAL_RANK"])] if device.type in {"npu", "cuda"} else None,
            find_unused_parameters=False,
        )
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    raw_model = model.module if hasattr(model, "module") else model
    fingerprint = training_fingerprint(name, raw_model, args, dtype)
    resume_path = resume_checkpoint_path(args, name)
    losses: list[float] = []
    start_step = 0
    resumed = False
    if args.resume and resume_path.is_file():
        resume_payload = safe_torch_load(resume_path)
        if resume_payload.get("config_fingerprint") != fingerprint:
            raise RuntimeError(
                f"resume fingerprint mismatch for {name}: {resume_path}; refusing incompatible checkpoint"
            )
        if resume_payload.get("student") != name:
            raise RuntimeError(f"resume student mismatch in {resume_path}")
        raw_model.load_state_dict(resume_payload["state_dict"])
        opt.load_state_dict(resume_payload["optimizer_state_dict"])
        restore_rng_state(resume_payload.get("rng_state", {}))
        start_step = int(resume_payload.get("global_step", 0))
        losses = [float(value) for value in resume_payload.get("train_loss_trace", [])]
        resumed = True
        if rank == 0:
            print(
                json.dumps(
                    {"event": "resume", "student": name, "step": start_step, "path": str(resume_path)}
                ),
                flush=True,
            )
            write_progress(
                args,
                {"state": "running", "student": name, "step": start_step, "steps": args.steps, "resumed": True},
            )
    if start_step > args.steps:
        raise RuntimeError(f"resume step {start_step} exceeds configured steps {args.steps}")
    t0 = datetime.now(timezone.utc)
    for step in range(start_step, args.steps):
        model.train()
        x = sample_batch(args, device, dtype, args.seed + step * 1297 + rank * 53, split="train")
        with torch.no_grad():
            target = teacher(x).float()
        pred = model(x).float()
        loss = torch.nn.functional.mse_loss(pred, target)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
        opt.step()
        reduced = reduce_mean(loss.detach().float().clone())
        if rank == 0 and (step == 0 or (step + 1) % args.log_every == 0 or step + 1 == args.steps):
            losses.append(float(reduced.item()))
            print(json.dumps({"event": "train", "student": name, "step": step + 1, "loss": losses[-1]}), flush=True)
            write_progress(
                args,
                {
                    "state": "running",
                    "student": name,
                    "step": step + 1,
                    "steps": args.steps,
                    "loss": losses[-1],
                    "resumed": resumed,
                },
            )
        if args.checkpoint_every > 0 and ((step + 1) % args.checkpoint_every == 0 or step + 1 == args.steps):
            sync_device()
            if rank == 0:
                save_training_state(
                    resume_path,
                    name,
                    raw_model,
                    opt,
                    step + 1,
                    losses,
                    fingerprint,
                    args,
                    dtype,
                    completed=step + 1 == args.steps,
                )
            barrier()
    sync_device()
    elapsed = (datetime.now(timezone.utc) - t0).total_seconds()
    metrics = evaluate(raw_model, teacher, args, device, dtype, rank)
    if rank == 0 and (args.resume or args.checkpoint_every > 0):
        save_training_state(
            resume_path,
            name,
            raw_model,
            opt,
            args.steps,
            losses,
            fingerprint,
            args,
            dtype,
            completed=True,
        )
        write_progress(
            args,
            {
                "state": "student_complete",
                "student": name,
                "step": args.steps,
                "steps": args.steps,
                "metrics": asdict(metrics),
                "resume_checkpoint": str(resume_path),
            },
        )
    barrier()
    row = {
        "student": name,
        "generator_mode": raw_model.generator_mode,
        "mode_status": (
            "canonical_causal_prototype"
            if raw_model.generator_mode in {"none", "token_diag_core"}
            else "shuffled_context_control"
            if raw_model.generator_mode == "shuffled_diag_core"
            else "legacy_or_expressivity_control"
        ),
        "lifecycle_evidence": "ordinary_framework_tensors_no_no_store_claim",
        "train_loss_trace": losses,
        "elapsed_s": round(elapsed, 3),
        "metrics": asdict(metrics),
        "parameter_bytes": parameter_bytes(raw_model),
        "parameter_mib": round(parameter_bytes(raw_model) / MIB, 3),
        "config_fingerprint": fingerprint,
        "resumed": resumed,
        "start_step": start_step,
        "resume_checkpoint": str(resume_path) if args.resume or args.checkpoint_every > 0 else None,
    }
    if rank == 0 and args.save_students:
        checkpoint_dir = Path(args.outdir) / "checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = checkpoint_dir / f"{name}.pt"
        atomic_torch_save(
            {
                "schema_version": 2,
                "student": name,
                "state_dict": {key: value.detach().cpu() for key, value in raw_model.state_dict().items()},
                "optimizer_state_dict": _to_cpu_tree(opt.state_dict()),
                "global_step": args.steps,
                "rng_state": capture_rng_state(),
                "config_fingerprint": fingerprint,
                "init": student_init_payload(raw_model),
                "config": {
                    "layer": args.layer,
                    "dtype": str(dtype).replace("torch.", ""),
                    "activation_source": args.activation_source,
                    "steps": args.steps,
                    "eval_batches": args.eval_batches,
                    "seed": args.seed,
                },
                "metrics": asdict(metrics),
                "provenance": getattr(args, "_provenance"),
            },
            checkpoint_path,
        )
        row["checkpoint"] = str(checkpoint_path)
    return row


def factor_cache_fingerprint(args: argparse.Namespace) -> str:
    provenance = getattr(args, "_provenance")
    return canonical_sha256(
        {
            "kind": "teacher_and_svd_factors_v4",
            "model": provenance["model"]["digest"],
            "code": provenance["code_digest"],
            "layer": args.layer,
            "d": args.d,
            "m": args.m,
            "env_label": args.env_label,
            "ranks": args.ranks,
            "factor_seed": args.factor_seed,
            "svd_method": args.svd_method,
            "svd_oversample": args.svd_oversample,
            "svd_niter": args.svd_niter,
        }
    )


def cache_key(args: argparse.Namespace, world_size: int) -> Path:
    del world_size
    fingerprint = factor_cache_fingerprint(args)
    return cache_root(args) / f"mwg_teacher_factors_{fingerprint[:20]}.pt"


def load_or_build_teacher_and_factors(args: argparse.Namespace, rank: int, world_size: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, dict[str, str], dict[int, dict[str, tuple[torch.Tensor, torch.Tensor]]], dict[int, dict[str, float]]]:
    cache_path = cache_key(args, world_size)
    fingerprint = factor_cache_fingerprint(args)
    if rank != 0:
        payload = wait_for_fingerprinted_cache(cache_path, fingerprint, args.cache_wait_timeout)
        args.d = int(payload["d"])
        args.m = int(payload["m"])
        barrier()
        return (
            payload["gate"],
            payload["up"],
            payload["down"],
            payload["teacher_meta"],
            payload["factors_by_rank"],
            payload["energy_by_rank"],
        )

    cached = load_fingerprinted_cache(cache_path, fingerprint)
    if cached is not None:
        args.d = int(cached["d"])
        args.m = int(cached["m"])
        barrier()
        return (
            cached["gate"],
            cached["up"],
            cached["down"],
            cached["teacher_meta"],
            cached["factors_by_rank"],
            cached["energy_by_rank"],
        )

    if args.model_dir:
        gate, up, down, teacher_meta = find_ffn_triplet(Path(args.model_dir), args.layer)
        args.d = up.shape[0]
        args.m = up.shape[1]
    else:
        gate, up, down, teacher_meta = make_synthetic_teacher(args.d, args.m, args.seed)

    factors_by_rank: dict[int, dict[str, tuple[torch.Tensor, torch.Tensor]]] = {
        r: {} for r in args.ranks
    }
    energy_by_rank: dict[int, dict[str, float]] = {r: {} for r in args.ranks}
    # Decompose each projection once at the largest requested rank. Lower-rank
    # controls are exact prefixes of that decomposition, avoiding one expensive
    # full SVD per (projection, rank) pair.
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(args.factor_seed)
        for name, weight in [("gate", gate), ("up", up), ("down", down)]:
            sweep = svd_factor_sweep(
                weight,
                args.ranks,
                method=args.svd_method,
                oversample=args.svd_oversample,
                niter=args.svd_niter,
            )
            for r, (left, right, energy) in sweep.items():
                factors_by_rank[r][name] = (left, right)
                energy_by_rank[r][name] = round(energy, 6)
    if rank == 0:
        for r in args.ranks:
            print(json.dumps({"event": "svd_done", "rank": r, "energy": energy_by_rank[r]}), flush=True)

    publish_fingerprinted_cache(
        {
            "d": args.d,
            "m": args.m,
            "gate": gate,
            "up": up,
            "down": down,
            "teacher_meta": teacher_meta,
            "factors_by_rank": factors_by_rank,
            "energy_by_rank": energy_by_rank,
        },
        cache_path,
        fingerprint,
    )
    barrier()
    return gate, up, down, teacher_meta, factors_by_rank, energy_by_rank


def run(args: argparse.Namespace) -> dict[str, Any] | None:
    validate_args(args)
    device, rank, local_rank, world_size, backend = setup_runtime()
    dtype = dtype_from_name(args.dtype, device)
    torch.manual_seed(args.seed + rank)

    text_splits, split_meta = prepare_text_splits(args)
    setattr(args, "_text_splits", text_splits)
    setattr(args, "_split_meta", split_meta)
    provenance = build_run_provenance(args, split_meta) if rank == 0 else None
    provenance = broadcast_provenance(provenance, rank)
    setattr(args, "_provenance", provenance)

    gate, up, down, teacher_meta, factors_by_rank, energy_by_rank = load_or_build_teacher_and_factors(args, rank, world_size)
    teacher_meta = {**teacher_meta, "model_digest": provenance["model"]["digest"]}

    teacher = DenseTeacher(gate, up, down, dtype=dtype).to(device).eval()
    activation_caches = capture_text_activation_splits(args, device, rank, world_size)
    setattr(args, "_train_activation_cache", activation_caches["train"])
    setattr(args, "_eval_activation_cache", activation_caches["eval"])
    if rank == 0:
        print(json.dumps({"event": "teacher_loaded", "d": args.d, "m": args.m, "meta": teacher_meta}), flush=True)
    output: dict[str, Any] = {
        "created_at": now_tag(),
        "env": env_payload(device, local_rank, world_size, backend),
        "teacher": teacher_meta,
        "provenance": provenance,
        "config": {
            "env_label": args.env_label,
            "d": args.d,
            "m": args.m,
            "ranks": args.ranks,
            "batch": args.batch,
            "seq": args.seq,
            "steps": args.steps,
            "eval_batches": args.eval_batches,
            "dtype": str(dtype).replace("torch.", ""),
            "lr": args.lr,
            "weight_decay": args.weight_decay,
            "grad_clip": args.grad_clip,
            "seed": args.seed,
            "students": args.students,
            "student_specs": args.student_specs,
            "generator_hidden": args.generator_hidden,
            "residual_rank": args.residual_rank,
            "scale_amplitude": args.scale_amplitude,
            "activation_source": args.activation_source,
            "activation_cache_shapes": {
                name: None if cache is None else list(cache.shape)
                for name, cache in activation_caches.items()
            },
            "activation_max_batches": args.activation_max_batches,
            "activation_text_batch": args.activation_text_batch,
            "activation_seq": args.activation_seq,
            "activation_seed": args.activation_seed,
            "evidence_mode": args.evidence_mode,
            "split_meta": split_meta,
            "svd_method": args.svd_method,
            "svd_oversample": args.svd_oversample,
            "svd_niter": args.svd_niter,
            "factor_seed": args.factor_seed,
            "basis_count": args.basis_count,
            "basis_noise": args.basis_noise,
            "checkpoint_every": args.checkpoint_every,
            "resume": args.resume,
        },
        "dense_parameter_mib": round(dense_bytes(args.d, args.m, dtype) / MIB, 3),
        "results": {
            "dense_teacher": {
                "rank": None,
                "control": "dense_reference",
                "metrics": {
                    "mse": 0.0,
                    "relative_mse": 0.0,
                    "cosine": 1.0,
                    "token_relative_mse_p50": 0.0,
                    "token_relative_mse_p90": 0.0,
                    "token_relative_mse_p95": 0.0,
                    "token_relative_mse_p99": 0.0,
                    "token_relative_mse_max": 0.0,
                },
                "parameter_bytes": dense_bytes(args.d, args.m, dtype),
                "parameter_mib": round(dense_bytes(args.d, args.m, dtype) / MIB, 3),
                "persistent_factor_mib": None,
                "analytic_dense_to_factor_payload_ratio": None,
            }
        },
    }

    for r in args.ranks:
        static = LowRankFFN(factors_by_rank[r], dtype=dtype, generator="none").to(device)
        for param in static.parameters():
            param.requires_grad_(False)
        static_metrics = evaluate(static, teacher, args, device, dtype, rank)
        if rank == 0:
            factor_payload = descriptor_bytes(args.d, args.m, r, dtype)
            output["results"][f"static_svd_r{r}"] = {
                "rank": r,
                "svd_energy": energy_by_rank[r],
                "metrics": asdict(static_metrics),
                "persistent_factor_elements": 3 * r * (args.d + args.m),
                "persistent_factor_mib": round(factor_payload / MIB, 3),
                "analytic_dense_to_factor_payload_ratio": round(
                    dense_bytes(args.d, args.m, dtype) / max(factor_payload, 1), 3
                ),
            }
        del static

        rows: list[dict[str, Any]] = []
        if student_enabled(args, "persistent", r):
            persistent = LowRankFFN(factors_by_rank[r], dtype=dtype, generator="none").to(device)
            rows.append(train_student(f"persistent_low_rank_r{r}", persistent, teacher, args, device, dtype, rank))
            del persistent
            barrier()
        if student_enabled(args, "rank_scale", r):
            mwg = LowRankFFN(
                factors_by_rank[r],
                dtype=dtype,
                generator="rank_scale",
                generator_hidden=args.generator_hidden,
                scale_amplitude=args.scale_amplitude,
            ).to(device)
            rows.append(train_student(f"mwg_ephemeral_r{r}", mwg, teacher, args, device, dtype, rank))
            del mwg
            barrier()
        if student_enabled(args, "token_scale", r):
            token_scale = LowRankFFN(
                factors_by_rank[r],
                dtype=dtype,
                generator="token_scale",
                generator_hidden=args.generator_hidden,
                scale_amplitude=args.scale_amplitude,
            ).to(device)
            rows.append(train_student(f"mwg_token_scale_r{r}", token_scale, teacher, args, device, dtype, rank))
            del token_scale
            barrier()
        if student_enabled(args, "token_diag_core", r):
            token_diag_core = LowRankFFN(
                factors_by_rank[r],
                dtype=dtype,
                generator="token_diag_core",
                generator_hidden=args.generator_hidden,
                scale_amplitude=args.scale_amplitude,
            ).to(device)
            rows.append(
                train_student(
                    f"mwg_token_diag_core_r{r}",
                    token_diag_core,
                    teacher,
                    args,
                    device,
                    dtype,
                    rank,
                )
            )
            del token_diag_core
            barrier()
        if student_enabled(args, "shuffled_diag_core", r):
            shuffled_diag_core = LowRankFFN(
                factors_by_rank[r],
                dtype=dtype,
                generator="shuffled_diag_core",
                generator_hidden=args.generator_hidden,
                scale_amplitude=args.scale_amplitude,
            ).to(device)
            rows.append(
                train_student(
                    f"mwg_shuffled_diag_core_r{r}",
                    shuffled_diag_core,
                    teacher,
                    args,
                    device,
                    dtype,
                    rank,
                )
            )
            del shuffled_diag_core
            barrier()
        if student_enabled(args, "token_rank_mixer", r):
            token_rank_mixer = LowRankFFN(
                factors_by_rank[r],
                dtype=dtype,
                generator="token_rank_mixer",
                generator_hidden=args.generator_hidden,
                scale_amplitude=args.scale_amplitude,
            ).to(device)
            rows.append(train_student(f"mwg_token_rank_mixer_r{r}", token_rank_mixer, teacher, args, device, dtype, rank))
            del token_rank_mixer
            barrier()
        if student_enabled(args, "token_residual", r):
            residual = LowRankFFN(
                factors_by_rank[r],
                dtype=dtype,
                generator="token_residual",
                generator_hidden=args.generator_hidden,
                residual_rank=args.residual_rank,
                scale_amplitude=args.scale_amplitude,
            ).to(device)
            rows.append(train_student(f"mwg_token_residual_r{r}", residual, teacher, args, device, dtype, rank))
            del residual
            barrier()
        if student_enabled(args, "mixture", r):
            mixture = LowRankFFN(
                factors_by_rank[r],
                dtype=dtype,
                generator="mixture",
                generator_hidden=args.generator_hidden,
                residual_rank=args.residual_rank,
                scale_amplitude=args.scale_amplitude,
                basis_count=args.basis_count,
                basis_noise=args.basis_noise,
            ).to(device)
            rows.append(train_student(f"mwg_mixture_r{r}", mixture, teacher, args, device, dtype, rank))
            del mixture
            barrier()
        if student_enabled(args, "expert_residual", r):
            expert = LowRankFFN(
                factors_by_rank[r],
                dtype=dtype,
                generator="expert_residual",
                generator_hidden=args.generator_hidden,
                residual_rank=args.residual_rank,
                scale_amplitude=args.scale_amplitude,
                basis_count=args.basis_count,
                basis_noise=args.basis_noise,
            ).to(device)
            rows.append(train_student(f"mwg_expert_residual_r{r}", expert, teacher, args, device, dtype, rank))
            del expert
            barrier()
        if student_enabled(args, "token_expert_residual", r):
            token_expert = LowRankFFN(
                factors_by_rank[r],
                dtype=dtype,
                generator="token_expert_residual",
                generator_hidden=args.generator_hidden,
                residual_rank=args.residual_rank,
                scale_amplitude=args.scale_amplitude,
                basis_count=args.basis_count,
                basis_noise=args.basis_noise,
            ).to(device)
            rows.append(
                train_student(
                    f"mwg_token_expert_residual_r{r}",
                    token_expert,
                    teacher,
                    args,
                    device,
                    dtype,
                    rank,
                )
            )
            del token_expert
            barrier()
        if rank == 0:
            for row in rows:
                row["rank"] = r
                factor_payload = descriptor_bytes(args.d, args.m, r, dtype)
                row["persistent_factor_elements"] = 3 * r * (args.d + args.m)
                row["persistent_factor_mib"] = round(factor_payload / MIB, 3)
                row["analytic_dense_to_factor_payload_ratio"] = round(
                    dense_bytes(args.d, args.m, dtype) / max(factor_payload, 1), 3
                )
                if row["student"].startswith("mwg_token_diag_core_"):
                    row["ephemeral_core_elements_per_token"] = 3 * r
                    row["ephemeral_core_mib_per_token"] = round(diagonal_core_bytes(r, dtype) / MIB, 6)
                    per_rank_bytes = 3 * (args.d + args.m) * elem_bytes(dtype)
                    row["parameter_matched_persistent_rank_ceil"] = math.ceil(
                        int(row["parameter_bytes"]) / max(per_rank_bytes, 1)
                    )
                output["results"][row["student"]] = row
        barrier()

    if rank == 0:
        write_progress(
            args,
            {
                "state": "run_complete",
                "students": sorted(output["results"]),
                "run_input_digest": provenance["run_input_digest"],
            },
        )
    if dist.is_initialized():
        dist.destroy_process_group()
    return output if rank == 0 else None


def write_outputs(payload: dict[str, Any], outdir: Path) -> tuple[Path, Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    tag = payload["created_at"]
    json_path = outdir / f"mwg_quality_distillation_{tag}.json"
    md_path = outdir / f"mwg_quality_distillation_{tag}.md"
    atomic_json_write(payload, json_path)

    lines = [
        "# MWG-EW Quality Distillation",
        "",
        f"Created: `{tag}`",
        f"World size: `{payload['env'].get('world_size')}`",
        f"Device: `{payload['env'].get('device_type')}`",
        f"Teacher: `{payload['teacher']}`",
        "",
        "| Method | Rank | Rel. MSE | Cosine | Params MiB | Persistent-factor MiB | Analytic dense/factor payload |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for key, row in payload["results"].items():
        metrics = row["metrics"]
        lines.append(
            f"| {key} | {row.get('rank')} | {metrics['relative_mse']:.6g} | "
            f"{metrics['cosine']:.6f} | {row.get('parameter_mib', '')} | "
            f"{row.get('persistent_factor_mib')} | "
            f"{row.get('analytic_dense_to_factor_payload_ratio')} |"
        )
    tmp_md = md_path.with_name(f".{md_path.name}.{os.getpid()}.tmp")
    tmp_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp_md, md_path)
    return json_path, md_path


def validate_args(args: argparse.Namespace) -> None:
    if args.student_specs:
        args.ranks = sorted({rank for _mode, rank in args.student_specs})
        args.students = sorted({mode for mode, _rank in args.student_specs})
    if not args.ranks or any(rank <= 0 for rank in args.ranks):
        raise ValueError("--ranks must contain positive integers")
    for name in (
        "batch",
        "seq",
        "eval_batches",
        "log_every",
        "activation_max_batches",
        "activation_text_batch",
        "activation_seq",
        "cache_wait_timeout",
    ):
        if int(getattr(args, name)) <= 0:
            raise ValueError(f"--{name.replace('_', '-')} must be positive")
    if args.steps < 0 or args.checkpoint_every < 0 or args.activation_seed < 0 or args.factor_seed < 0:
        raise ValueError(
            "--steps, --checkpoint-every, --activation-seed, and --factor-seed must be non-negative"
        )
    if not 0.0 <= args.near_duplicate_threshold <= 1.0:
        raise ValueError("--near-duplicate-threshold must be in [0, 1]")
    if args.evidence_mode:
        if not args.model_dir:
            raise ValueError("--evidence-mode requires --model-dir")
        if not args.save_students:
            raise ValueError("--evidence-mode requires --save-students")
        if args.checkpoint_every <= 0:
            raise ValueError("--evidence-mode requires positive --checkpoint-every")
        invalid = sorted(set(args.students) - {"persistent", "token_diag_core", "shuffled_diag_core"})
        if invalid:
            raise ValueError(
                "--evidence-mode accepts only causal canonical controls "
                f"(persistent,token_diag_core,shuffled_diag_core); got {','.join(invalid)}"
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default="")
    parser.add_argument("--env-label", default="")
    parser.add_argument("--layer", type=int, default=None)
    parser.add_argument("--d", type=int, default=256)
    parser.add_argument("--m", type=int, default=768)
    parser.add_argument("--ranks", type=parse_ints, default=[16, 32, 64])
    parser.add_argument("--svd-method", choices=["exact", "pca_lowrank"], default="exact")
    parser.add_argument("--svd-oversample", type=int, default=16)
    parser.add_argument("--svd-niter", type=int, default=2)
    parser.add_argument("--factor-seed", type=int, default=1729)
    parser.add_argument("--batch", type=int, default=2)
    parser.add_argument("--seq", type=int, default=64)
    parser.add_argument("--steps", type=int, default=80)
    parser.add_argument("--eval-batches", type=int, default=8)
    parser.add_argument("--log-every", type=int, default=20)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument(
        "--students",
        type=parse_students,
        default=["persistent", "token_diag_core"],
        help=(
            "comma-separated student modes; persistent and token_diag_core are "
            "canonical, while rank_scale/token_scale and expert variants are "
            "legacy compatibility controls"
        ),
    )
    parser.add_argument(
        "--student-specs",
        type=parse_student_specs,
        default=[],
        help="optional comma-separated mode:rank controls; overrides --students/--ranks pairings",
    )
    parser.add_argument("--generator-hidden", type=int, default=None)
    parser.add_argument("--residual-rank", type=int, default=8)
    parser.add_argument("--scale-amplitude", type=float, default=0.05)
    parser.add_argument("--basis-count", type=int, default=4)
    parser.add_argument("--basis-noise", type=float, default=0.01)
    parser.add_argument("--activation-source", choices=["gaussian", "text"], default="gaussian")
    parser.add_argument("--texts", type=parse_texts, default=[])
    parser.add_argument("--train-texts-file", default="")
    parser.add_argument("--eval-texts-file", default="")
    parser.add_argument("--evidence-mode", action="store_true")
    parser.add_argument("--near-duplicate-threshold", type=float, default=0.82)
    parser.add_argument("--activation-max-batches", type=int, default=32)
    parser.add_argument("--activation-text-batch", type=int, default=2)
    parser.add_argument("--activation-seq", type=int, default=256)
    parser.add_argument("--activation-seed", type=int, default=1729)
    parser.add_argument("--activation-log-every", type=int, default=8)
    parser.add_argument("--save-students", action="store_true")
    parser.add_argument("--checkpoint-every", type=int, default=0)
    parser.add_argument("--resume", default="", help="auto, a checkpoint file, or a checkpoint directory")
    parser.add_argument("--progress-json", default="")
    parser.add_argument("--cache-dir", default="")
    parser.add_argument("--cache-wait-timeout", type=int, default=1800)
    parser.add_argument("--dtype", choices=["auto", "fp16", "bf16", "fp32"], default="auto")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--outdir", default="results")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    payload = run(args)
    if payload is not None:
        json_path, md_path = write_outputs(payload, Path(args.outdir))
        print(json.dumps({"event": "saved", "json": str(json_path), "markdown": str(md_path)}, indent=2), flush=True)


if __name__ == "__main__":
    main()
