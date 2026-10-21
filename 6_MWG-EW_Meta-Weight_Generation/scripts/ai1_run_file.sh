#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo 'Usage: scripts/ai1_run_file.sh <relative-path-under-repo>' >&2
  exit 1
fi

FILE_PATH="$1"
ROOT_REMOTE="/root/work/mwg-ew-patent"

scripts/ai1_shell.sh "cd $ROOT_REMOTE && python3 $FILE_PATH"
