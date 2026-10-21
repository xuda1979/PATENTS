#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"
TRAIN_TEXTS="${TRAIN_TEXTS:?TRAIN_TEXTS must point to an explicit router-training corpus file}"
EVAL_TEXTS="${EVAL_TEXTS:?EVAL_TEXTS must point to an explicit held-out router-evaluation corpus file}"
PATCH="${PATCH:?PATCH must point to the exact MWG checkpoint to evaluate}"
LAYER="${LAYER:-16}"
cd "$PROJECT_ROOT"

if [[ ! -f "$TRAIN_TEXTS" ]]; then
  echo "ERROR: train texts not found: $TRAIN_TEXTS" >&2
  exit 2
fi
if [[ ! -f "$EVAL_TEXTS" ]]; then
  echo "ERROR: eval texts not found: $EVAL_TEXTS" >&2
  exit 2
fi
if [[ ! -f "$PATCH" ]]; then
  echo "ERROR: patch checkpoint not found: $PATCH" >&2
  exit 2
fi
if [[ "$TRAIN_TEXTS" == "$EVAL_TEXTS" ]]; then
  echo "ERROR: TRAIN_TEXTS and EVAL_TEXTS must be different files" >&2
  exit 2
fi

mkdir -p logs results
TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="asi3_router_validation_${TS}"
OUTDIR="results/${RUN_ID}"
OUT_JSON="${OUTDIR}/router_validation.json"
WRAPPER_LOG="logs/${RUN_ID}.log"
STATUS="logs/${RUN_ID}.status.json"

cat > "$STATUS" <<JSON
{
  "run_id": "$RUN_ID",
  "state": "launching",
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "train_texts": "$TRAIN_TEXTS",
  "eval_texts": "$EVAL_TEXTS",
  "patch": "$PATCH",
  "out_json": "$OUT_JSON",
  "wrapper_log": "$WRAPPER_LOG"
}
JSON

nohup bash -lc '
  set -euo pipefail
  PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
  MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"
  RUN_ID="'"$RUN_ID"'"
  TRAIN_TEXTS="'"$TRAIN_TEXTS"'"
  EVAL_TEXTS="'"$EVAL_TEXTS"'"
  PATCH="'"$PATCH"'"
  LAYER="'"$LAYER"'"
  OUTDIR="results/${RUN_ID}"
  OUT_JSON="${OUTDIR}/router_validation.json"
  STATUS="logs/${RUN_ID}.status.json"
  cd "$PROJECT_ROOT"

  write_status() {
    local state="$1"
    local detail="${2:-}"
    python3 - "$STATUS" "$state" "$RUN_ID" "$TRAIN_TEXTS" "$EVAL_TEXTS" "$PATCH" "$OUT_JSON" "$detail" <<'"'"'PY'"'"'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status_path = Path(sys.argv[1])
state, run_id, train_texts, eval_texts, patch, out_json, detail = sys.argv[2:9]
payload = {
    "run_id": run_id,
    "state": state,
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "train_texts": train_texts,
    "eval_texts": eval_texts,
    "patch": patch,
    "out_json": out_json,
    "result_json": str(Path(out_json)) if Path(out_json).exists() else "",
}
if detail:
    payload["detail"] = detail
status_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
  }

  on_exit() {
    local rc=$?
    if [[ "$rc" -eq 0 ]]; then
      write_status done
    else
      write_status failed "exit_code=${rc}"
    fi
    return "$rc"
  }
  trap on_exit EXIT

  mkdir -p "$OUTDIR"
  write_status running
  python3 experiments/mwg_router_gate_eval.py \
    --model-dir "$MODEL_DIR" \
    --layer "$LAYER" \
    --checkpoint "$PATCH" \
    --train-texts "$TRAIN_TEXTS" \
    --eval-texts "$EVAL_TEXTS" \
    --seq "${SEQ:-256}" \
    --train-examples "${TRAIN_EXAMPLES:-256}" \
    --eval-examples "${EVAL_EXAMPLES:-256}" \
    --fractions "${FRACTIONS:-0.10,0.25,0.50,0.75,1.0}" \
    --seed "${SEED:-0}" \
    --ridge-l2 "${RIDGE_L2:-1.0}" \
    --dtype "${DTYPE:-fp32}" \
    --out-json "$OUT_JSON" \
    --require-texts
' > "$WRAPPER_LOG" 2>&1 < /dev/null &
PID="$!"

python3 - "$STATUS" "$RUN_ID" "$PID" "$TRAIN_TEXTS" "$EVAL_TEXTS" "$PATCH" "$OUT_JSON" "$WRAPPER_LOG" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status_path = Path(sys.argv[1])
run_id, pid, train_texts, eval_texts, patch, out_json, wrapper_log = sys.argv[2:9]
status_path.write_text(json.dumps({
    "run_id": run_id,
    "state": "running",
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "pid": int(pid),
    "train_texts": train_texts,
    "eval_texts": eval_texts,
    "patch": patch,
    "out_json": out_json,
    "wrapper_log": wrapper_log,
}, indent=2) + "\n", encoding="utf-8")
PY

echo "ASI3 router validation detached"
echo "pid=$PID"
echo "run_id=$RUN_ID"
echo "train_texts=$TRAIN_TEXTS"
echo "eval_texts=$EVAL_TEXTS"
echo "patch=$PATCH"
echo "out_json=$OUT_JSON"
echo "wrapper_log=$WRAPPER_LOG"
echo "status=$STATUS"
