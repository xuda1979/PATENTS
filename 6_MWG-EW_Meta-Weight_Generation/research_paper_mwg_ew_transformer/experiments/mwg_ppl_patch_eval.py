"""Patch Qwen FFN layers with trained MWG students and measure perplexity."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn

from mwg_quality_distillation import DEFAULT_TEXTS, LowRankFFN, dtype_from_name, parse_texts

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


class PatchedMLP(nn.Module):
    def __init__(self, student: LowRankFFN):
        super().__init__()
        self.student = student

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.student(x)


def setup_device() -> torch.device:
    if HAS_NPU:
        torch.npu.set_device(0)
        return torch.device("npu:0")
    if HAS_CUDA:
        torch.cuda.set_device(0)
        return torch.device("cuda:0")
    return torch.device("cpu")


def sync_device() -> None:
    if HAS_NPU:
        torch.npu.synchronize()
    elif HAS_CUDA:
        torch.cuda.synchronize()


def dummy_factors(d: int, m: int, rank: int) -> dict[str, tuple[torch.Tensor, torch.Tensor]]:
    zeros_dm = (torch.zeros(d, rank), torch.zeros(rank, m))
    zeros_md = (torch.zeros(m, rank), torch.zeros(rank, d))
    return {"up": zeros_dm, "gate": zeros_dm, "down": zeros_md}


def load_student(path: Path, device: torch.device, dtype: torch.dtype) -> tuple[LowRankFFN, dict[str, Any]]:
    try:
        payload = torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:
        payload = torch.load(path, map_location="cpu")
    init = payload["init"]
    model = LowRankFFN(
        dummy_factors(init["d"], init["m"], init["rank"]),
        dtype=dtype,
        generator=init["generator_mode"],
        residual_rank=init["residual_rank"],
        scale_amplitude=init["scale_amplitude"],
        basis_count=init["basis_count"],
    )
    model.load_state_dict(payload["state_dict"])
    model.to(device=device, dtype=dtype)
    model.eval()
    return model, payload


@torch.no_grad()
def evaluate_ppl(model: nn.Module, tokenizer: Any, texts: list[str], args: argparse.Namespace, device: torch.device) -> dict[str, float]:
    losses = []
    token_count = 0
    for index in range(args.eval_batches):
        offset = (index * args.text_batch) % len(texts)
        batch_texts = [texts[(offset + j) % len(texts)] for j in range(args.text_batch)]
        encoded = tokenizer(
            batch_texts,
            return_tensors="pt",
            padding="max_length",
            truncation=True,
            max_length=args.seq,
        )
        encoded = {key: value.to(device) for key, value in encoded.items()}
        labels = encoded["input_ids"].clone()
        labels[encoded["attention_mask"] == 0] = -100
        output = model(**encoded, labels=labels)
        valid = int((labels != -100).sum().item())
        losses.append(float(output.loss.item()) * valid)
        token_count += valid
    loss = sum(losses) / max(token_count, 1)
    return {"loss": loss, "ppl": math.exp(min(20.0, loss)), "tokens": token_count}


def parse_patch_spec(values: list[str]) -> dict[int, Path]:
    patches: dict[int, Path] = {}
    for item in values:
        layer_text, path_text = item.split(":", 1)
        patches[int(layer_text)] = Path(path_text)
    return patches


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--patch", action="append", default=[], help="layer:/path/to/checkpoint.pt")
    parser.add_argument("--texts", type=parse_texts, default=[])
    parser.add_argument("--require-texts", action="store_true")
    parser.add_argument("--seq", type=int, default=256)
    parser.add_argument("--text-batch", type=int, default=2)
    parser.add_argument("--eval-batches", type=int, default=32)
    parser.add_argument("--dtype", choices=["auto", "fp16", "bf16", "fp32"], default="auto")
    parser.add_argument("--out-json", required=True)
    args = parser.parse_args()

    from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore

    device = setup_device()
    dtype = dtype_from_name(args.dtype, device)
    model_dtype = dtype if device.type in {"npu", "cuda"} else torch.float32
    tokenizer = AutoTokenizer.from_pretrained(args.model_dir, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        args.model_dir,
        torch_dtype=model_dtype,
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    ).to(device)
    model.eval()

    if args.require_texts and not args.texts:
        raise SystemExit("explicit --texts is required for this eval path; refusing DEFAULT_TEXTS fallback")
    texts = args.texts or DEFAULT_TEXTS
    dense = evaluate_ppl(model, tokenizer, texts, args, device)
    patch_payloads = {}
    for layer, path in parse_patch_spec(args.patch).items():
        student, payload = load_student(path, device, dtype)
        model.model.layers[layer].mlp = PatchedMLP(student)  # type: ignore[attr-defined]
        patch_payloads[str(layer)] = {"path": str(path), "student": payload.get("student"), "metrics": payload.get("metrics")}
    sync_device()
    patched = evaluate_ppl(model, tokenizer, texts, args, device)
    result = {"dense": dense, "patched": patched, "patches": patch_payloads, "config": vars(args)}
    Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_json).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
