#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
S3_ROOT="${MWG_EW_ASI2_S3_ROOT:-iner-aihuanxin:jtdlp-21b4208dde424e96b159362ef49c9c96/mwg-ew-patent/research_paper_mwg_ew_transformer}"
RCLONE_BIN="${RCLONE_BIN:-$(command -v rclone || true)}"

if [[ -z "$RCLONE_BIN" || ! -x "$RCLONE_BIN" ]]; then
  echo "rclone not found. Set RCLONE_BIN or install rclone." >&2
  exit 1
fi

cd "$PROJECT_ROOT"

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
  shift
fi

PATHS=("$@")
if [[ ${#PATHS[@]} -eq 0 ]]; then
  PATHS=(results logs)
fi

ARGS=(--progress --transfers 8 --s3-no-check-bucket)
if [[ $DRY_RUN -eq 1 ]]; then
  ARGS+=(--dry-run)
fi

for source_path in "${PATHS[@]}"; do
  [[ -e "$source_path" ]] || { echo "missing path: $source_path" >&2; exit 1; }
  if [[ -d "$source_path" ]]; then
    "$RCLONE_BIN" copy "$source_path" "$S3_ROOT/$source_path" "${ARGS[@]}"
  else
    parent_dir="$(dirname "$source_path")"
    if [[ "$parent_dir" == "." ]]; then
      dest="$S3_ROOT"
    else
      dest="$S3_ROOT/$parent_dir"
    fi
    "$RCLONE_BIN" copy "$source_path" "$dest" "${ARGS[@]}"
  fi
done

echo "pushed ASI2 results to $S3_ROOT"
