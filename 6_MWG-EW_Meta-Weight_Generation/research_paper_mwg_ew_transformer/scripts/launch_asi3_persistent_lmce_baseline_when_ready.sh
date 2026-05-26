#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"

REMOTE_LAUNCHER="$PROJECT_ROOT/scripts/launch_asi3_persistent_lmce_baseline_detached.sh"
LOCAL_LAUNCHER="$ROOT_DIR/scripts/launch_asi3_persistent_lmce_baseline_detached.sh"

TRAIN_TEXTS="${TRAIN_TEXTS:-$PROJECT_ROOT/data/heldout/router_train.txt}"
MANIFEST="${MANIFEST:-$PROJECT_ROOT/data/heldout/manifest.json}"
BASE_CKPT="${BASE_CKPT:-$PROJECT_ROOT/results/asi3_persistent_broad_baseline_20260525T114920Z/checkpoints/persistent_low_rank_r384.pt}"
LMCE_STEPS="${LMCE_STEPS:-1200}"

export AI3_ALLOW_BROWSER="${AI3_ALLOW_BROWSER:-0}"
export HUANXIN_ALLOW_STANDALONE_FALLBACK="${HUANXIN_ALLOW_STANDALONE_FALLBACK:-0}"
export HUANXIN_WAIT_MS="${HUANXIN_WAIT_MS:-15000}"
HEALTH_RETRIES="${HEALTH_RETRIES:-3}"

if [[ "$AI3_ALLOW_BROWSER" == "1" ]]; then
  echo "ERROR: refusing browser fallback; unset AI3_ALLOW_BROWSER for daemon-only launch." >&2
  exit 2
fi
if [[ ! -f "$LOCAL_LAUNCHER" ]]; then
  echo "ERROR: local launcher missing: $LOCAL_LAUNCHER" >&2
  exit 2
fi

if ps -axo pid=,command= | awk '
  /huanxin_shell_exec\.js ai3 --require-daemon/ && !/awk / {
    print
    found = 1
  }
  END { exit found ? 0 : 1 }
'; then
  echo "ERROR: another local ai3 daemon shell command is already running; refusing to queue launch." >&2
  exit 3
fi

cd "$ROOT_DIR"

echo "Checking daemon-only ai3 health..."
health_ok=0
for attempt in $(seq 1 "$HEALTH_RETRIES"); do
  health_output="$(bash scripts/ai3_shell.sh "printf AI3_HEALTH_OK" 2>&1)" && {
    printf '%s\n' "$health_output"
    health_ok=1
    break
  }
  printf '%s\n' "$health_output"
  if [[ "$health_output" != *"stale_daemon_state_recovered"* || "$attempt" -ge "$HEALTH_RETRIES" ]]; then
    exit 1
  fi
  sleep 2
done
if [[ "$health_ok" -ne 1 ]]; then
  echo "ERROR: ai3 health check did not succeed." >&2
  exit 1
fi

if ps -axo pid=,command= | awk '
  /huanxin_shell_exec\.js ai3 --require-daemon/ && !/awk / {
    print
    found = 1
  }
  END { exit found ? 0 : 1 }
'; then
  echo "ERROR: ai3 daemon shell became busy after health probe; refusing upload/launch." >&2
  exit 3
fi

echo "Uploading persistent LM-CE launcher via daemon transport..."
node scripts/ai3_daemon_upload_files.js --file "$LOCAL_LAUNCHER" "$REMOTE_LAUNCHER"

echo "Launching persistent LM-CE baseline on ai3..."
REMOTE_CMD=$(cat <<EOF
cd "$PROJECT_ROOT" && \
chmod +x "$REMOTE_LAUNCHER" && \
TRAIN_TEXTS="$TRAIN_TEXTS" \
MANIFEST="$MANIFEST" \
BASE_CKPT="$BASE_CKPT" \
LMCE_STEPS="$LMCE_STEPS" \
bash "$REMOTE_LAUNCHER"
EOF
)
bash scripts/ai3_shell.sh "$REMOTE_CMD"
