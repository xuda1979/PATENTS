#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"
MANIFEST="${MANIFEST:?MANIFEST must point to an explicit held-out corpus manifest}"
PATCH="${PATCH:?PATCH must point to the exact MWG checkpoint to evaluate}"
LAYER="${LAYER:-16}"
cd "$PROJECT_ROOT"

if [[ ! -f "$MANIFEST" ]]; then
  echo "ERROR: manifest not found: $MANIFEST" >&2
  exit 2
fi
if [[ ! -f "$PATCH" ]]; then
  echo "ERROR: patch checkpoint not found: $PATCH" >&2
  exit 2
fi

mkdir -p logs results
TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="asi3_broad_validation_${TS}"
OUTDIR="results/${RUN_ID}"
WRAPPER_LOG="logs/${RUN_ID}.log"
STATUS="logs/${RUN_ID}.status.json"

cat > "$STATUS" <<JSON
{
  "run_id": "$RUN_ID",
  "state": "launching",
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "manifest": "$MANIFEST",
  "patch": "$PATCH",
  "outdir": "$OUTDIR",
  "wrapper_log": "$WRAPPER_LOG"
}
JSON

nohup bash -lc '
  set -euo pipefail
  PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
  MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"
  RUN_ID="'"$RUN_ID"'"
  MANIFEST="'"$MANIFEST"'"
  PATCH="'"$PATCH"'"
  LAYER="'"$LAYER"'"
  OUTDIR="results/${RUN_ID}"
  STATUS="logs/${RUN_ID}.status.json"
  cd "$PROJECT_ROOT"

  write_status() {
    local state="$1"
    local detail="${2:-}"
    python3 - "$STATUS" "$state" "$RUN_ID" "$MANIFEST" "$PATCH" "$OUTDIR" "$detail" <<'"'"'PY'"'"'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status_path = Path(sys.argv[1])
state, run_id, manifest, patch, outdir, detail = sys.argv[2:8]
payload = {
    "run_id": run_id,
    "state": state,
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "manifest": manifest,
    "patch": patch,
    "outdir": outdir,
    "result_json": sorted(str(path) for path in Path(outdir).glob("**/*.json")),
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

  write_status running
  python3 experiments/mwg_broad_eval_manifest.py \
    --manifest "$MANIFEST" \
    --model-dir "$MODEL_DIR" \
    --patch "${LAYER}:${PATCH}" \
    --outdir "$OUTDIR" \
    --seq "${SEQ:-256}" \
    --text-batch "${TEXT_BATCH:-2}" \
    --eval-batches "${EVAL_BATCHES:-128}" \
    --dtype "${DTYPE:-fp32}" \
    --min-texts "${MIN_TEXTS:-8}" \
    --min-chars "${MIN_CHARS:-4000}"
' > "$WRAPPER_LOG" 2>&1 < /dev/null &
PID="$!"

python3 - "$STATUS" "$RUN_ID" "$PID" "$MANIFEST" "$PATCH" "$OUTDIR" "$WRAPPER_LOG" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status_path = Path(sys.argv[1])
run_id, pid, manifest, patch, outdir, wrapper_log = sys.argv[2:8]
status_path.write_text(json.dumps({
    "run_id": run_id,
    "state": "running",
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "pid": int(pid),
    "manifest": manifest,
    "patch": patch,
    "outdir": outdir,
    "wrapper_log": wrapper_log,
}, indent=2) + "\n", encoding="utf-8")
PY

echo "ASI3 broad validation detached"
echo "pid=$PID"
echo "run_id=$RUN_ID"
echo "manifest=$MANIFEST"
echo "patch=$PATCH"
echo "outdir=$OUTDIR"
echo "wrapper_log=$WRAPPER_LOG"
echo "status=$STATUS"
