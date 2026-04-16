#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
S3_ROOT="nm-aihuanxin:jtdlp-3ed7854b946a47b1a49ad754baa76cd3/mwg-ew-patent"
RCLONE_BIN="${RCLONE_BIN:-$(command -v rclone || true)}"
if [[ -z "$RCLONE_BIN" && -x /Users/daxu/homebrew/bin/rclone ]]; then
  RCLONE_BIN=/Users/daxu/homebrew/bin/rclone
fi

cd "$ROOT_DIR"

if [[ -z "$RCLONE_BIN" || ! -x "$RCLONE_BIN" ]]; then
  echo 'rclone not found. Set RCLONE_BIN or install rclone.' >&2
  exit 1
fi

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
  shift
fi

REMOTE_PATHS=("$@")
if [[ ${#REMOTE_PATHS[@]} -eq 0 ]]; then
  REMOTE_PATHS=(results)
fi

ARGS=(--progress --transfers 8)
if [[ $DRY_RUN -eq 1 ]]; then
  ARGS+=(--dry-run)
fi

for remote_path in "${REMOTE_PATHS[@]}"; do
  "$RCLONE_BIN" copy "$S3_ROOT/$remote_path" "$ROOT_DIR/$remote_path" "${ARGS[@]}"
done
