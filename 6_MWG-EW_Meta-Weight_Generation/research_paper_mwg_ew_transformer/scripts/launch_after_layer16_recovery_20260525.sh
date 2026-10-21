#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
RUN_ID="${RUN_ID:-asi3_layer16_recovery_20260525T102958Z}"
MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"

PATCH="$PROJECT_ROOT/results/$RUN_ID/layer16/checkpoints/mwg_expert_residual_r384_belle_lmce_cal_1200.pt"
MANIFEST="$PROJECT_ROOT/data/heldout/manifest.json"
TRAIN_TEXTS="$PROJECT_ROOT/data/heldout/router_train.txt"
EVAL_TEXTS="$PROJECT_ROOT/data/heldout/router_eval.txt"
STATUS="$PROJECT_ROOT/logs/after_${RUN_ID}.status.json"
LOG="$PROJECT_ROOT/logs/after_${RUN_ID}.log"

cd "$PROJECT_ROOT"
mkdir -p logs results

write_status() {
  local state="$1"
  local detail="${2:-}"
  python3 - "$STATUS" "$state" "$detail" "$PATCH" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status, state, detail, patch = sys.argv[1:5]
root = Path("/vllm-workspace/mwg-ew-transformer-research")
payload = {
    "state": state,
    "detail": detail,
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "patch": patch,
    "patch_exists": Path(patch).exists(),
    "broad_status": sorted(str(path) for path in (root / "logs").glob("asi3_broad_validation_*.status.json"))[-5:],
    "router_status": sorted(str(path) for path in (root / "logs").glob("asi3_router_validation_*.status.json"))[-10:],
}
Path(status).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
}

{
  write_status waiting_for_checkpoint
  echo "waiting for patch: $PATCH"
  for i in $(seq 1 2880); do
    if [[ -f "$PATCH" ]]; then
      break
    fi
    sleep 60
    if (( i % 10 == 0 )); then
      write_status waiting_for_checkpoint "minutes=$i"
    fi
  done
  if [[ ! -f "$PATCH" ]]; then
    write_status failed checkpoint_timeout
    echo "ERROR: checkpoint did not appear: $PATCH" >&2
    exit 2
  fi

  write_status launching_broad
  MANIFEST="$MANIFEST" PATCH="$PATCH" MODEL_DIR="$MODEL_DIR" \
    bash scripts/launch_asi3_broad_validation_detached.sh

  for seed in 0 1 2; do
    write_status "launching_router_seed${seed}"
    TRAIN_TEXTS="$TRAIN_TEXTS" EVAL_TEXTS="$EVAL_TEXTS" PATCH="$PATCH" \
      SEED="$seed" MODEL_DIR="$MODEL_DIR" \
      bash scripts/launch_asi3_router_validation_detached.sh
  done

  write_status launched_all
} > "$LOG" 2>&1 &

echo "after-recovery launcher pid=$!"
echo "status=$STATUS"
echo "log=$LOG"
