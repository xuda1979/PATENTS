#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
RUN_ID="${RUN_ID:-asi3_layer16_recovery_20260525T102958Z}"
MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"

PATCH="$PROJECT_ROOT/results/$RUN_ID/layer16/checkpoints/mwg_expert_residual_r384_belle_lmce_cal_1200.pt"
TRAIN_TEXTS="$PROJECT_ROOT/data/heldout/router_train.txt"
EVAL_TEXTS="$PROJECT_ROOT/data/heldout/router_eval.txt"
STATUS="$PROJECT_ROOT/logs/extra_router_${RUN_ID}.status.json"
LOG="$PROJECT_ROOT/logs/extra_router_${RUN_ID}.log"

cd "$PROJECT_ROOT"
mkdir -p logs results

write_status() {
  local state="$1"
  local detail="${2:-}"
  python3 - "$STATUS" "$state" "$detail" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status, state, detail = sys.argv[1:4]
root = Path("/vllm-workspace/mwg-ew-transformer-research")
payload = {
    "state": state,
    "detail": detail,
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "router_status": sorted(str(path) for path in (root / "logs").glob("asi3_router_validation_*.status.json"))[-10:],
}
Path(status).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
}

wait_for_router_idle() {
  while pgrep -f "experiments/mwg_router_gate_eval.py" >/dev/null 2>&1; do
    write_status waiting_for_router_idle
    sleep 60
  done
}

{
  if [[ ! -f "$PATCH" ]]; then
    write_status failed "missing_patch=$PATCH"
    exit 2
  fi

  for seed in 1 2; do
    wait_for_router_idle
    write_status "launching_router_seed${seed}"
    TRAIN_TEXTS="$TRAIN_TEXTS" EVAL_TEXTS="$EVAL_TEXTS" PATCH="$PATCH" \
      SEED="$seed" MODEL_DIR="$MODEL_DIR" \
      bash scripts/launch_asi3_router_validation_detached.sh
    sleep 2
  done
  write_status launched_extra_router_seeds
} > "$LOG" 2>&1 &

echo "extra-router launcher pid=$!"
echo "status=$STATUS"
echo "log=$LOG"
