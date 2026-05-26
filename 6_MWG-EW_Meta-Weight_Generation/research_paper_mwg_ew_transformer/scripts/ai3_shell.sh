#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
QUANTUM_GPT_DIR="${QUANTUM_GPT_DIR:-/Users/daxu/software/quantum-gpt}"

export HUANXIN_TRAIN_DEV_URL="${HUANXIN_TRAIN_DEV_URL:-https://aihuanxin.cn/kunlun/kl-web?poolId=6&projectId=21b4208dde424e96b159362ef49c9c96#/train-dev/environment/dl-c72bd81a96e33134bbe0ae4a478fbab0?name=ai3}"
export HUANXIN_PROFILE_COPY_NAME="${HUANXIN_PROFILE_COPY_NAME:-mwg-ew-ai3}"
export HUANXIN_ALLOW_STANDALONE_FALLBACK="${HUANXIN_ALLOW_STANDALONE_FALLBACK:-0}"
export HUANXIN_HEADLESS="${HUANXIN_HEADLESS:-1}"

WAIT_MS="${HUANXIN_WAIT_MS:-180000}"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 \"<remote command>\"" >&2
  exit 1
fi

cd "$ROOT_DIR"
if [[ "${AI3_ALLOW_BROWSER:-0}" == "1" ]]; then
  exec node "$QUANTUM_GPT_DIR/browser-automation/huanxin_shell_exec.js" \
    ai3 --skip-daemon --wait-ms "$WAIT_MS" --command "$*"
fi

export HUANXIN_WAIT_MS="$WAIT_MS"
exec bash "$QUANTUM_GPT_DIR/scripts/huanxin_shell.sh" ai3 "$*"
