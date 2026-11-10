#!/usr/bin/env python3
"""Recompute the mwg_quality_distillation model digest for a model dir.

Replicates build_run_provenance()'s model_payload logic:
  - state files: *.safetensors (or pytorch_model*.bin/*.bin fallback)
  - plus: config.json, generation_config.json, tokenizer.json,
          tokenizer_config.json, tokenizer.model, vocab.json, merges.txt,
          added_tokens.json, special_tokens_map.json, *.py
  - digest = sha256(canonical_json(sorted file rows: path,bytes,sha256))
"""
import hashlib
import json
import sys
from pathlib import Path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(payload) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def iter_state_files(model_dir: Path):
    safes = sorted(model_dir.glob("*.safetensors"))
    if safes:
        return safes
    bins = sorted(model_dir.glob("pytorch_model*.bin")) + sorted(model_dir.glob("*.bin"))
    return list(dict.fromkeys(bins))


def main():
    model_dir = Path(sys.argv[1]).expanduser().resolve()
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
        "*.py",
    ):
        model_files.extend(sorted(model_dir.glob(pattern)))
    model_files = list(dict.fromkeys(p.resolve() for p in model_files if p.is_file()))
    rows = []
    for p in model_files:
        rows.append({
            "path": str(p.relative_to(model_dir)),
            "bytes": p.stat().st_size,
            "sha256": file_sha256(p),
        })
    print(json.dumps({
        "model_dir": str(model_dir),
        "n_files": len(rows),
        "digest": canonical_sha256(rows),
        "files": rows,
    }, indent=1))


if __name__ == "__main__":
    main()
