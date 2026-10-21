#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"
SPLIT_MANIFEST="${SPLIT_MANIFEST:-data/heldout/router_global_splits/manifest.json}"
PATCH="${PATCH:?PATCH must point to the exact MWG checkpoint to evaluate}"
LAYER="${LAYER:-16}"
RUN_PREFIX="${RUN_PREFIX:-asi3_token_router_global_suite_balanced_1npu}"
cd "$PROJECT_ROOT"

if [[ ! -f "$SPLIT_MANIFEST" ]]; then
  echo "ERROR: split manifest not found: $SPLIT_MANIFEST" >&2
  exit 2
fi
if [[ ! -f "$PATCH" ]]; then
  echo "ERROR: patch checkpoint not found: $PATCH" >&2
  exit 2
fi

mkdir -p logs results
TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="${RUN_PREFIX}_${TS}"
OUTDIR="results/${RUN_ID}"
WRAPPER_LOG="logs/${RUN_ID}.log"
STATUS="logs/${RUN_ID}.status.json"
RESULT_JSON="${OUTDIR}/token_router_global_suite_balanced.json"

cat > "$STATUS" <<JSON
{
  "run_id": "$RUN_ID",
  "state": "launching",
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "split_manifest": "$SPLIT_MANIFEST",
  "patch": "$PATCH",
  "outdir": "$OUTDIR",
  "result_json": "$RESULT_JSON",
  "wrapper_log": "$WRAPPER_LOG",
  "ascend_rt_visible_devices": "${ASCEND_RT_VISIBLE_DEVICES:-0}"
}
JSON

nohup bash -lc '
  set -euo pipefail
  PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
  MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"
  RUN_ID="'"$RUN_ID"'"
  SPLIT_MANIFEST="'"$SPLIT_MANIFEST"'"
  PATCH="'"$PATCH"'"
  LAYER="'"$LAYER"'"
  OUTDIR="results/${RUN_ID}"
  STATUS="logs/${RUN_ID}.status.json"
  RESULT_JSON="${OUTDIR}/token_router_global_suite_balanced.json"
  export ASCEND_RT_VISIBLE_DEVICES="${ASCEND_RT_VISIBLE_DEVICES:-0}"
  cd "$PROJECT_ROOT"

  write_status() {
    local state="$1"
    local detail="${2:-}"
    python3 - "$STATUS" "$state" "$RUN_ID" "$SPLIT_MANIFEST" "$PATCH" "$OUTDIR" "$RESULT_JSON" "$detail" "$ASCEND_RT_VISIBLE_DEVICES" <<'"'"'PY'"'"'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status_path = Path(sys.argv[1])
state, run_id, split_manifest, patch, outdir, result_json, detail, devices = sys.argv[2:10]
payload = {
    "run_id": run_id,
    "state": state,
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "split_manifest": split_manifest,
    "patch": patch,
    "outdir": outdir,
    "result_json": result_json if Path(result_json).exists() else "",
    "ascend_rt_visible_devices": devices,
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
  write_status running evaluator
  python3 -c "import torch; print(\"torch\", torch.__version__); import torch_npu; print(\"torch_npu\", getattr(torch_npu, \"__version__\", \"unknown\")); print(\"npu_count\", torch.npu.device_count())"
  python3 experiments/mwg_token_router_gate_eval.py \
    --model-dir "$MODEL_DIR" \
    --layer "$LAYER" \
    --checkpoint "$PATCH" \
    --suite-split-manifest "$SPLIT_MANIFEST" \
    --suite-balanced-sampling \
    --suite-balanced-ridge \
    --fail-on-suite-overlap \
    --seq "${SEQ:-256}" \
    --train-examples "${TRAIN_EXAMPLES:-0}" \
    --eval-examples "${EVAL_EXAMPLES:-0}" \
    --joint-budgets "${JOINT_BUDGETS:-0.05,0.10,0.25}" \
    --risk-max-predicted-delta "${RISK_MAX_PREDICTED_DELTA:-0.0}" \
    --threshold-policy "${THRESHOLD_POLICY:-suite_local}" \
    --seed "${SEED:-0}" \
    --ridge-l2 "${RIDGE_L2:-1.0}" \
    --dtype "${DTYPE:-fp32}" \
    --out-json "$RESULT_JSON" \
    --require-texts
' > "$WRAPPER_LOG" 2>&1 < /dev/null &
PID="$!"

python3 - "$STATUS" "$RUN_ID" "$PID" "$SPLIT_MANIFEST" "$PATCH" "$OUTDIR" "$RESULT_JSON" "$WRAPPER_LOG" "${ASCEND_RT_VISIBLE_DEVICES:-0}" <<'PY'
import json
import sys
from datetime import datetime, timezone

status_path = sys.argv[1]
run_id, pid, split_manifest, patch, outdir, result_json, wrapper_log, devices = sys.argv[2:10]
with open(status_path, "w", encoding="utf-8") as f:
    json.dump({
        "run_id": run_id,
        "state": "running",
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pid": int(pid),
        "split_manifest": split_manifest,
        "patch": patch,
        "outdir": outdir,
        "result_json": result_json,
        "wrapper_log": wrapper_log,
        "ascend_rt_visible_devices": devices,
    }, f, indent=2)
    f.write("\n")
PY

echo "launched ${RUN_ID} pid=${PID}"
echo "status ${STATUS}"
echo "log ${WRAPPER_LOG}"
