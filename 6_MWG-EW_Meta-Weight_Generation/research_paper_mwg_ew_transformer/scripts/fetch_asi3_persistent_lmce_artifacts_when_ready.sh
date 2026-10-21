#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
LOCAL_OUT_DIR="${LOCAL_OUT_DIR:-$ROOT_DIR/results/pulled_asi3/asi3_validation_20260525}"

BROAD_RUN_ID="${BROAD_RUN_ID:-asi3_broad_validation_20260526T024509Z}"
CAL_RUN_ID="${CAL_RUN_ID:-asi3_persistent_lmce_baseline_20260526T024239Z}"

REMOTE_BROAD_STATUS="${REMOTE_BROAD_STATUS:-$PROJECT_ROOT/logs/${BROAD_RUN_ID}.status.json}"
REMOTE_BROAD_SUMMARY="${REMOTE_BROAD_SUMMARY:-$PROJECT_ROOT/results/${BROAD_RUN_ID}/summary_broad_eval.json}"
REMOTE_CAL_JSON="${REMOTE_CAL_JSON:-$PROJECT_ROOT/results/${CAL_RUN_ID}/persistent_low_rank_r384_lmce.json}"

LOCAL_BROAD_STATUS="${LOCAL_BROAD_STATUS:-$LOCAL_OUT_DIR/${BROAD_RUN_ID}.status.json}"
LOCAL_BROAD_SUMMARY="${LOCAL_BROAD_SUMMARY:-$LOCAL_OUT_DIR/summary_broad_eval_persistent_lmce_20260526T024509Z.json}"
LOCAL_CAL_JSON="${LOCAL_CAL_JSON:-$LOCAL_OUT_DIR/persistent_low_rank_r384_lmce_20260526T024239Z.json}"

export ASI3_ALLOW_BROWSER="${ASI3_ALLOW_BROWSER:-0}"
export HUANXIN_ALLOW_STANDALONE_FALLBACK="${HUANXIN_ALLOW_STANDALONE_FALLBACK:-0}"
export HUANXIN_WAIT_MS="${HUANXIN_WAIT_MS:-15000}"
export HUANXIN_DAEMON_HARD_TIMEOUT_MS="${HUANXIN_DAEMON_HARD_TIMEOUT_MS:-30000}"
HEALTH_RETRIES="${HEALTH_RETRIES:-3}"

if [[ "$ASI3_ALLOW_BROWSER" == "1" ]]; then
  echo "ERROR: refusing browser fallback; unset ASI3_ALLOW_BROWSER for daemon-only fetch." >&2
  exit 2
fi

if ps -axo pid=,command= | awk '
  /huanxin_shell_exec\.js ASI3 --require-daemon/ && !/awk / {
    print
    found = 1
  }
  END { exit found ? 0 : 1 }
'; then
  echo "ERROR: another local ASI3 daemon shell command is already running; refusing to queue fetch." >&2
  exit 3
fi

cd "$ROOT_DIR"

echo "Checking daemon-only ASI3 health..."
health_ok=0
for attempt in $(seq 1 "$HEALTH_RETRIES"); do
  health_output="$(bash scripts/ASI3_shell.sh "printf ASI3_HEALTH_OK" 2>&1)" && {
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
  echo "ERROR: ASI3 health check did not succeed." >&2
  exit 1
fi

if ps -axo pid=,command= | awk '
  /huanxin_shell_exec\.js ASI3 --require-daemon/ && !/awk / {
    print
    found = 1
  }
  END { exit found ? 0 : 1 }
'; then
  echo "ERROR: ASI3 daemon shell became busy after health probe; refusing fetch." >&2
  exit 3
fi

mkdir -p "$LOCAL_OUT_DIR"
node scripts/ASI3_daemon_fetch_files.js \
  --file "$REMOTE_BROAD_STATUS" "$LOCAL_BROAD_STATUS" \
  --file "$REMOTE_BROAD_SUMMARY" "$LOCAL_BROAD_SUMMARY" \
  --file "$REMOTE_CAL_JSON" "$LOCAL_CAL_JSON"
