#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
cd "$PROJECT_ROOT"

mkdir -p logs results
TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="asi3_runtime_profiler_probe_${TS}"
OUTDIR="results/${RUN_ID}"
WRAPPER_LOG="logs/${RUN_ID}.log"
STATUS="logs/${RUN_ID}.status.json"

cat > "$STATUS" <<JSON
{
  "run_id": "$RUN_ID",
  "state": "launching",
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "outdir": "$OUTDIR",
  "wrapper_log": "$WRAPPER_LOG"
}
JSON

nohup bash -lc '
  set -euo pipefail
  PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
  RUN_ID="'"$RUN_ID"'"
  OUTDIR="results/${RUN_ID}"
  STATUS="logs/${RUN_ID}.status.json"
  cd "$PROJECT_ROOT"

  write_status() {
    local state="$1"
    local detail="${2:-}"
    python3 - "$STATUS" "$RUN_ID" "$state" "$OUTDIR" "$detail" <<'"'"'PY'"'"'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status_path = Path(sys.argv[1])
run_id, state, outdir, detail = sys.argv[2:6]
latest = Path(outdir) / "mwg_runtime_profiler_probe_latest.json"
payload = {
    "run_id": run_id,
    "state": state,
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "outdir": outdir,
    "summary_json": str(latest) if latest.exists() else "",
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
  write_status running "probe_start"
  timeout "${PROBE_TIMEOUT_SECONDS:-900}" python3 experiments/mwg_runtime_profiler_probe.py \
    --outdir "$OUTDIR" \
    --d "${D:-2048}" \
    --m "${M:-5504}" \
    --ranks "${RANKS:-128,256}" \
    --batch "${BATCH:-1}" \
    --seq "${SEQ:-128}" \
    --dtype "${DTYPE:-auto}" \
    --mode "${MODE:-forward}" \
    --warmup "${WARMUP:-3}" \
    --iters "${ITERS:-10}" \
    --profile-iters "${PROFILE_ITERS:-3}" \
    ${EXPORT_TRACES:+--export-traces}
  write_status running "probe_done"
' > "$WRAPPER_LOG" 2>&1 < /dev/null &
PID="$!"

python3 - "$STATUS" "$RUN_ID" "$PID" "$OUTDIR" "$WRAPPER_LOG" <<'PY'
import json
import sys
from datetime import datetime, timezone

status_path = sys.argv[1]
run_id, pid, outdir, wrapper_log = sys.argv[2:6]
with open(status_path, "w", encoding="utf-8") as f:
    json.dump({
        "run_id": run_id,
        "state": "running",
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pid": int(pid),
        "outdir": outdir,
        "wrapper_log": wrapper_log,
    }, f, indent=2)
    f.write("\n")
PY

echo "ASI3 runtime profiler probe detached"
echo "pid=$PID"
echo "run_id=$RUN_ID"
echo "outdir=$OUTDIR"
echo "wrapper_log=$WRAPPER_LOG"
echo "status=$STATUS"
