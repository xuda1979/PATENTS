"""End-to-end logit calibration for a patched MWG FFN layer."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F

from mwg_ppl_patch_eval import PatchedMLP, evaluate_ppl, load_student, setup_device, sync_device
from mwg_quality_distillation import DEFAULT_TEXTS, dtype_from_name, parse_texts


def cycle_texts(texts: list[str], step: int, batch: int) -> list[str]:
    offset = (step * batch) % len(texts)
    return [texts[(offset + index) % len(texts)] for index in range(batch)]


def encode(tokenizer: Any, texts: list[str], seq: int, device: torch.device) -> dict[str, torch.Tensor]:
    encoded = tokenizer(
        texts,
        return_tensors="pt",
        padding="max_length",
        truncation=True,
        max_length=seq,
    )
    return {key: value.to(device) for key, value in encoded.items()}


def masked_kl(student_logits: torch.Tensor, teacher_logits: torch.Tensor, mask: torch.Tensor, temperature: float) -> torch.Tensor:
    student = student_logits.float() / temperature
    teacher = teacher_logits.float() / temperature
    per_token = F.kl_div(
        F.log_softmax(student, dim=-1),
        F.softmax(teacher, dim=-1),
        reduction="none",
    ).sum(dim=-1)
    valid = mask.float()
    return (per_token * valid).sum() / valid.sum().clamp_min(1.0) * (temperature * temperature)


def masked_centered_logit_mse(
    student_logits: torch.Tensor,
    teacher_logits: torch.Tensor,
    mask: torch.Tensor,
    clip: float,
) -> torch.Tensor:
    student = student_logits.float()
    teacher = teacher_logits.float()
    student = student - student.mean(dim=-1, keepdim=True)
    teacher = teacher - teacher.mean(dim=-1, keepdim=True)
    if clip > 0:
        student = student.clamp(-clip, clip)
        teacher = teacher.clamp(-clip, clip)
    per_token = (student - teacher).square().mean(dim=-1)
    valid = mask.float()
    return (per_token * valid).sum() / valid.sum().clamp_min(1.0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--layer", type=int, required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--out-checkpoint", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--texts", type=parse_texts, default=[])
    parser.add_argument("--require-texts", action="store_true")
    parser.add_argument("--seq", type=int, default=128)
    parser.add_argument("--text-batch", type=int, default=1)
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--temperature", type=float, default=2.0)
    parser.add_argument("--objective", choices=["kl", "logit_mse", "lm_ce"], default="logit_mse")
    parser.add_argument("--logit-clip", type=float, default=30.0)
    parser.add_argument("--log-every", type=int, default=20)
    parser.add_argument("--eval-batches", type=int, default=16)
    parser.add_argument("--dtype", choices=["auto", "fp16", "bf16", "fp32"], default="auto")
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore

    device = setup_device()
    torch.manual_seed(args.seed)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(args.seed)
    elif device.type == "npu" and hasattr(torch, "npu"):
        torch.npu.manual_seed_all(args.seed)  # type: ignore[attr-defined]
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
    for param in model.parameters():
        param.requires_grad_(False)

    if args.require_texts and not args.texts:
        raise SystemExit("explicit --texts is required for this calibration path; refusing DEFAULT_TEXTS fallback")
    student, payload = load_student(Path(args.checkpoint), device, dtype)
    for param in student.parameters():
        param.requires_grad_(True)
    patched = PatchedMLP(student)
    dense_mlp = model.model.layers[args.layer].mlp  # type: ignore[attr-defined]
    optimizer = torch.optim.AdamW(student.parameters(), lr=args.lr)
    texts = args.texts or DEFAULT_TEXTS

    history: list[dict[str, float]] = []
    for step in range(args.steps):
        batch_texts = cycle_texts(texts, step, args.text_batch)
        encoded = encode(tokenizer, batch_texts, args.seq, device)
        mask = encoded["attention_mask"]

        model.model.layers[args.layer].mlp = patched  # type: ignore[attr-defined]
        if args.objective == "lm_ce":
            labels = encoded["input_ids"].clone()
            labels[mask == 0] = -100
            output = model(**encoded, labels=labels)
            loss = output.loss
        else:
            with torch.no_grad():
                model.model.layers[args.layer].mlp = dense_mlp  # type: ignore[attr-defined]
                teacher_logits = model(**encoded).logits.detach()
            model.model.layers[args.layer].mlp = patched  # type: ignore[attr-defined]
            output = model(**encoded)
            if args.objective == "kl":
                loss = masked_kl(output.logits, teacher_logits, mask, args.temperature)
            else:
                loss = masked_centered_logit_mse(output.logits, teacher_logits, mask, args.logit_clip)
        if not torch.isfinite(loss):
            raise RuntimeError(f"non-finite calibration loss at step {step + 1}: {loss.detach().item()}")
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(student.parameters(), 1.0)
        optimizer.step()

        if step == 0 or (step + 1) % args.log_every == 0:
            item = {"step": float(step + 1), "kl": float(loss.detach().item())}
            history.append(item)
            print(json.dumps({"event": "logit_calibrate", **item}), flush=True)

    sync_device()
    model.model.layers[args.layer].mlp = dense_mlp  # type: ignore[attr-defined]
    dense = evaluate_ppl(model, tokenizer, texts, args, device)
    model.model.layers[args.layer].mlp = patched  # type: ignore[attr-defined]
    patched_ppl = evaluate_ppl(model, tokenizer, texts, args, device)

    payload = dict(payload)
    payload["state_dict"] = student.state_dict()
    payload["calibration"] = {
        "kind": "logit_kl",
        "layer": args.layer,
        "steps": args.steps,
        "lr": args.lr,
        "temperature": args.temperature,
        "objective": args.objective,
        "logit_clip": args.logit_clip,
        "history": history,
        "dense": dense,
        "patched": patched_ppl,
    }
    out_checkpoint = Path(args.out_checkpoint)
    out_checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, out_checkpoint)

    result = {
        "dense": dense,
        "patched": patched_ppl,
        "delta_loss": patched_ppl["loss"] - dense["loss"],
        "ppl_ratio": patched_ppl["ppl"] / max(dense["ppl"], 1e-12),
        "checkpoint": str(out_checkpoint),
        "source_checkpoint": args.checkpoint,
        "config": vars(args),
        "history": history,
    }
    Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_json).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
