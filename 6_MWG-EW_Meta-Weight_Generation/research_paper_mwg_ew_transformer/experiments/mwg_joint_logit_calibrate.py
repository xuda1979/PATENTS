"""Joint end-to-end logit calibration for multiple patched MWG FFN layers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F

from mwg_logit_calibrate import cycle_texts, encode, masked_centered_logit_mse, masked_kl
from mwg_ppl_patch_eval import PatchedMLP, evaluate_ppl, load_student, parse_patch_spec, setup_device, sync_device
from mwg_quality_distillation import DEFAULT_TEXTS, dtype_from_name, parse_texts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--patch", action="append", default=[], help="layer:/path/to/checkpoint.pt")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--texts", type=parse_texts, default=[])
    parser.add_argument("--seq", type=int, default=128)
    parser.add_argument("--text-batch", type=int, default=1)
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--lr", type=float, default=1e-6)
    parser.add_argument("--temperature", type=float, default=2.0)
    parser.add_argument("--objective", choices=["kl", "logit_mse"], default="logit_mse")
    parser.add_argument("--logit-clip", type=float, default=20.0)
    parser.add_argument("--log-every", type=int, default=10)
    parser.add_argument("--eval-batches", type=int, default=32)
    parser.add_argument("--dtype", choices=["auto", "fp16", "bf16", "fp32"], default="fp32")
    args = parser.parse_args()

    from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore

    if not args.patch:
        raise RuntimeError("at least one --patch layer:path is required")

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
    for param in model.parameters():
        param.requires_grad_(False)

    patches = parse_patch_spec(args.patch)
    dense_mlps: dict[int, Any] = {}
    students: dict[int, Any] = {}
    payloads: dict[int, dict[str, Any]] = {}
    trainable: list[torch.nn.Parameter] = []
    for layer, path in patches.items():
        student, payload = load_student(path, device, dtype)
        for param in student.parameters():
            param.requires_grad_(True)
            trainable.append(param)
        dense_mlps[layer] = model.model.layers[layer].mlp  # type: ignore[attr-defined]
        students[layer] = student
        payloads[layer] = payload
        model.model.layers[layer].mlp = PatchedMLP(student)  # type: ignore[attr-defined]

    optimizer = torch.optim.AdamW(trainable, lr=args.lr)
    texts = args.texts or DEFAULT_TEXTS
    history: list[dict[str, float]] = []

    for step in range(args.steps):
        batch_texts = cycle_texts(texts, step, args.text_batch)
        encoded = encode(tokenizer, batch_texts, args.seq, device)
        mask = encoded["attention_mask"]

        with torch.no_grad():
            for layer, dense_mlp in dense_mlps.items():
                model.model.layers[layer].mlp = dense_mlp  # type: ignore[attr-defined]
            teacher_logits = model(**encoded).logits.detach()

        for layer, student in students.items():
            model.model.layers[layer].mlp = PatchedMLP(student)  # type: ignore[attr-defined]
        output = model(**encoded)
        if args.objective == "kl":
            loss = masked_kl(output.logits, teacher_logits, mask, args.temperature)
        else:
            loss = masked_centered_logit_mse(output.logits, teacher_logits, mask, args.logit_clip)
        if not torch.isfinite(loss):
            raise RuntimeError(f"non-finite calibration loss at step {step + 1}: {loss.detach().item()}")
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(trainable, 1.0)
        optimizer.step()

        if step == 0 or (step + 1) % args.log_every == 0:
            item = {"step": float(step + 1), "loss": float(loss.detach().item())}
            history.append(item)
            print(json.dumps({"event": "joint_logit_calibrate", **item}), flush=True)

    sync_device()
    for layer, dense_mlp in dense_mlps.items():
        model.model.layers[layer].mlp = dense_mlp  # type: ignore[attr-defined]
    dense = evaluate_ppl(model, tokenizer, texts, args, device)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    out_checkpoints: dict[str, str] = {}
    for layer, student in students.items():
        model.model.layers[layer].mlp = PatchedMLP(student)  # type: ignore[attr-defined]
        payload = dict(payloads[layer])
        payload["state_dict"] = student.state_dict()
        payload["joint_calibration"] = {
            "kind": "joint_logit",
            "layers": sorted(patches),
            "steps": args.steps,
            "lr": args.lr,
            "objective": args.objective,
            "logit_clip": args.logit_clip,
            "history": history,
        }
        out_path = out_dir / f"layer{layer}_joint_cal.pt"
        torch.save(payload, out_path)
        out_checkpoints[str(layer)] = str(out_path)

    patched = evaluate_ppl(model, tokenizer, texts, args, device)
    result = {
        "dense": dense,
        "patched": patched,
        "delta_loss": patched["loss"] - dense["loss"],
        "ppl_ratio": patched["ppl"] / max(dense["ppl"], 1e-12),
        "checkpoints": out_checkpoints,
        "source_patches": {str(layer): str(path) for layer, path in patches.items()},
        "config": vars(args),
        "history": history,
    }
    Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_json).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
