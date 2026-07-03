#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"

REMOTE_LAUNCHER="$PROJECT_ROOT/scripts/launch_asi3_token_router_global_suite_balanced_detached.sh"
LOCAL_LAUNCHER="$ROOT_DIR/scripts/launch_asi3_token_router_global_suite_balanced_detached.sh"
REMOTE_EVALUATOR="$PROJECT_ROOT/experiments/mwg_token_router_gate_eval.py"
LOCAL_EVALUATOR="$ROOT_DIR/experiments/mwg_token_router_gate_eval.py"
LOCAL_SPLIT_MANIFEST="$ROOT_DIR/data/heldout/router_global_splits/manifest.json"

SPLIT_MANIFEST="${SPLIT_MANIFEST:-$PROJECT_ROOT/data/heldout/router_global_splits/manifest.json}"
PATCH="${PATCH:-$PROJECT_ROOT/results/asi3_layer16_recovery_20260525T102958Z/layer16/checkpoints/mwg_expert_residual_r384_belle_lmce_cal_1200.pt}"
LAYER="${LAYER:-16}"

export ASI3_ALLOW_BROWSER="${ASI3_ALLOW_BROWSER:-0}"
export HUANXIN_ALLOW_STANDALONE_FALLBACK="${HUANXIN_ALLOW_STANDALONE_FALLBACK:-0}"
export HUANXIN_WAIT_MS="${HUANXIN_WAIT_MS:-15000}"
export HUANXIN_DAEMON_HARD_TIMEOUT_MS="${HUANXIN_DAEMON_HARD_TIMEOUT_MS:-30000}"
HEALTH_RETRIES="${HEALTH_RETRIES:-3}"

if [[ "$ASI3_ALLOW_BROWSER" == "1" ]]; then
  echo "ERROR: refusing browser fallback; unset ASI3_ALLOW_BROWSER for daemon-only launch." >&2
  exit 2
fi
if [[ ! -f "$LOCAL_LAUNCHER" ]]; then
  echo "ERROR: local launcher missing: $LOCAL_LAUNCHER" >&2
  exit 2
fi
if [[ ! -f "$LOCAL_EVALUATOR" ]]; then
  echo "ERROR: local evaluator missing: $LOCAL_EVALUATOR" >&2
  exit 2
fi
if [[ ! -f "$LOCAL_SPLIT_MANIFEST" ]]; then
  echo "ERROR: local global split manifest missing: $LOCAL_SPLIT_MANIFEST" >&2
  exit 2
fi

SPLIT_TEXT_REL_PATHS=()
while IFS= read -r rel_path; do
  [[ -n "$rel_path" ]] && SPLIT_TEXT_REL_PATHS+=("$rel_path")
done < <(
  python3 - "$LOCAL_SPLIT_MANIFEST" <<'PY'
import json
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for suite in manifest.get("suites", []):
    for key in ("train_texts", "eval_texts"):
        value = suite.get(key)
        if value:
            print(value)
PY
)
if [[ "${#SPLIT_TEXT_REL_PATHS[@]}" -eq 0 ]]; then
  echo "ERROR: global split manifest does not list train/eval text files." >&2
  exit 2
fi
for rel_path in "${SPLIT_TEXT_REL_PATHS[@]}"; do
  if [[ ! -f "$ROOT_DIR/$rel_path" ]]; then
    echo "ERROR: local split text missing: $ROOT_DIR/$rel_path" >&2
    exit 2
  fi
done

if ps -axo pid=,command= | awk '
  /huanxin_shell_exec\.js ASI3 --require-daemon/ && !/awk / {
    print
    found = 1
  }
  END { exit found ? 0 : 1 }
'; then
  echo "ERROR: another local ASI3 daemon shell command is already running; refusing to queue launch." >&2
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
  echo "ERROR: ASI3 daemon shell became busy after health probe; refusing upload/launch." >&2
  exit 3
fi

echo "Uploading global suite-balanced token-router launcher via daemon transport..."
upload_args=(
  --file "$LOCAL_LAUNCHER" "$REMOTE_LAUNCHER"
  --file "$LOCAL_EVALUATOR" "$REMOTE_EVALUATOR"
  --file "$LOCAL_SPLIT_MANIFEST" "$SPLIT_MANIFEST"
)
for rel_path in "${SPLIT_TEXT_REL_PATHS[@]}"; do
  upload_args+=(--file "$ROOT_DIR/$rel_path" "$PROJECT_ROOT/$rel_path")
done
node scripts/ASI3_daemon_upload_files.js "${upload_args[@]}"

echo "Launching global suite-balanced token-router run on ASI3..."
REMOTE_CMD=$(cat <<EOF
cd "$PROJECT_ROOT" && \
chmod +x "$REMOTE_LAUNCHER" && \
SPLIT_MANIFEST="$SPLIT_MANIFEST" \
PATCH="$PATCH" \
LAYER="$LAYER" \
bash "$REMOTE_LAUNCHER"
EOF
)
bash scripts/ASI3_shell.sh "$REMOTE_CMD"
