#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
S3_ROOT="${MWG_EW_ASI2_S3_ROOT:-iner-aihuanxin:jtdlp-21b4208dde424e96b159362ef49c9c96/mwg-ew-patent/research_paper_mwg_ew_transformer}"
RCLONE_BIN="${RCLONE_BIN:-$(command -v rclone || true)}"
if [[ -z "$RCLONE_BIN" && -x /Users/daxu/homebrew/bin/rclone ]]; then
  RCLONE_BIN=/Users/daxu/homebrew/bin/rclone
fi

cd "$ROOT_DIR"

if [[ -z "$RCLONE_BIN" || ! -x "$RCLONE_BIN" ]]; then
  echo "rclone not found. Set RCLONE_BIN or install rclone." >&2
  exit 1
fi

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
  shift
fi

PATHS=("$@")
if [[ ${#PATHS[@]} -eq 0 ]]; then
  PATHS=(README.md experiments scripts paper)
fi

ARGS=(
  --exclude "__pycache__/**"
  --exclude ".pytest_cache/**"
  --exclude "*.pyc"
  --exclude "node_modules/**"
  --exclude ".venv/**"
  --exclude "venv/**"
  --exclude "results/**"
  --exclude "logs/**"
  --exclude "*.pt"
  --exclude "*.pth"
  --exclude "*.bin"
  --exclude "*.safetensors"
  --exclude "*.ckpt"
  --progress
  --transfers 8
  --s3-no-check-bucket
)
if [[ $DRY_RUN -eq 1 ]]; then
  ARGS+=(--dry-run)
fi

for source_path in "${PATHS[@]}"; do
  [[ -e "$source_path" ]] || { echo "missing path: $source_path" >&2; exit 1; }
  if [[ -d "$source_path" ]]; then
    "$RCLONE_BIN" copy "$source_path" "$S3_ROOT/$source_path" "${ARGS[@]}"
  else
    "$RCLONE_BIN" copy "$source_path" "$S3_ROOT" "${ARGS[@]}"
  fi
done

echo "pushed ASI2 code to $S3_ROOT"
