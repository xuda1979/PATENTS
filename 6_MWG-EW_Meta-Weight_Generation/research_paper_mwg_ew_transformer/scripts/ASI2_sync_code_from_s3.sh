#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
S3_ROOT="${MWG_EW_ASI2_S3_ROOT:-iner-aihuanxin:jtdlp-21b4208dde424e96b159362ef49c9c96/mwg-ew-patent/research_paper_mwg_ew_transformer}"
RCLONE_BIN="${RCLONE_BIN:-$(command -v rclone || true)}"

if [[ -z "$RCLONE_BIN" || ! -x "$RCLONE_BIN" ]]; then
  echo "rclone not found. Set RCLONE_BIN or install rclone." >&2
  exit 1
fi

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
  shift
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
  --s3-no-check-bucket
  --progress
)
if [[ $DRY_RUN -eq 1 ]]; then
  ARGS+=(--dry-run)
fi

mkdir -p "$PROJECT_ROOT"
"$RCLONE_BIN" sync "$S3_ROOT" "$PROJECT_ROOT" "${ARGS[@]}"
chmod +x "$PROJECT_ROOT"/scripts/*.sh || true

echo "synced ASI2 code from $S3_ROOT to $PROJECT_ROOT"
