#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
cd "$PROJECT_ROOT"

mkdir -p logs results
TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="asi3_quality_distillation_${TS}"
WRAPPER_LOG="logs/${RUN_ID}_detached.log"
STATUS="logs/${RUN_ID}.status.json"

cat > "$STATUS" <<JSON
{
  "run_id": "$RUN_ID",
  "state": "launching",
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "wrapper_log": "$WRAPPER_LOG"
}
JSON

nohup bash -lc '
  set -euo pipefail
  PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
  cd "$PROJECT_ROOT"

  RUN_ID="'"$RUN_ID"'"
  STATUS="logs/${RUN_ID}.status.json"
  OUTDIR="results/${RUN_ID}"
  mkdir -p "$OUTDIR"

  write_status() {
    local state="$1"
    local detail="${2:-}"
    python3 - "$STATUS" "$state" "$RUN_ID" "$OUTDIR" "$detail" <<'"'"'PY'"'"'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status_path = Path(sys.argv[1])
state, run_id, outdir, detail = sys.argv[2:6]
payload = {
    "run_id": run_id,
    "state": state,
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "outdir": outdir,
    "result_json": sorted(str(path) for path in Path(outdir).glob("*.json")),
    "result_md": sorted(str(path) for path in Path(outdir).glob("*.md")),
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

  write_status running starting
  echo "ASI3 MWG-EW quality distillation"
  echo "run_id=$RUN_ID"
  echo "project_root=$PROJECT_ROOT"
  echo "outdir=$OUTDIR"
  date -u
  python3 -c "import torch; print(\"torch\", torch.__version__); import torch_npu; print(\"torch_npu\", getattr(torch_npu, \"__version__\", \"unknown\")); print(\"npu_count\", torch.npu.device_count())"

  PROJECT_ROOT="$PROJECT_ROOT" OUTDIR="$OUTDIR" \
    RANKS="${RANKS:-128,256,384}" \
    STEPS="${STEPS:-5000}" \
    EVAL_BATCHES="${EVAL_BATCHES:-128}" \
    BATCH="${BATCH:-1}" \
    SEQ="${SEQ:-128}" \
    LOG_EVERY="${LOG_EVERY:-250}" \
    STUDENTS="${STUDENTS:-persistent,rank_scale,token_residual,mixture}" \
    RESIDUAL_RANK="${RESIDUAL_RANK:-32}" \
    SCALE_AMPLITUDE="${SCALE_AMPLITUDE:-0.10}" \
    BASIS_COUNT="${BASIS_COUNT:-4}" \
    BASIS_NOISE="${BASIS_NOISE:-0.01}" \
    ACTIVATION_SOURCE="${ACTIVATION_SOURCE:-text}" \
    ACTIVATION_MAX_BATCHES="${ACTIVATION_MAX_BATCHES:-128}" \
    ACTIVATION_TEXT_BATCH="${ACTIVATION_TEXT_BATCH:-2}" \
    ACTIVATION_SEQ="${ACTIVATION_SEQ:-256}" \
    LR="${LR:-0.0002}" \
    DTYPE="${DTYPE:-fp32}" \
    bash scripts/run_asi1_quality_distillation.sh

  write_status running quality_done
  date -u
' > "$WRAPPER_LOG" 2>&1 < /dev/null &
PID="$!"

python3 - "$STATUS" "$RUN_ID" "$PID" "$WRAPPER_LOG" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status_path = Path(sys.argv[1])
run_id, pid, wrapper_log = sys.argv[2:5]
status_path.write_text(json.dumps({
    "run_id": run_id,
    "state": "running",
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "pid": int(pid),
    "wrapper_log": wrapper_log,
}, indent=2) + "\n", encoding="utf-8")
PY

echo "ASI3 quality distillation detached"
echo "pid=$PID"
echo "project_root=$PROJECT_ROOT"
echo "run_id=$RUN_ID"
echo "wrapper_log=$WRAPPER_LOG"
echo "status=$STATUS"
