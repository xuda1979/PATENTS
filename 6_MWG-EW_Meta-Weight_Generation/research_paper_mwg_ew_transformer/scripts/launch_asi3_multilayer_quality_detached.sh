#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
cd "$PROJECT_ROOT"

mkdir -p logs results
TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="asi3_multilayer_quality_${TS}"
WRAPPER_LOG="logs/${RUN_ID}_detached.log"
STATUS="logs/${RUN_ID}.status.json"
LAYERS="${LAYERS:-0,4,8,12}"

cat > "$STATUS" <<JSON
{
  "run_id": "$RUN_ID",
  "state": "launching",
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "wrapper_log": "$WRAPPER_LOG",
  "layers": "$LAYERS"
}
JSON

nohup bash -lc '
  set -euo pipefail
  PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
  cd "$PROJECT_ROOT"
  RUN_ID="'"$RUN_ID"'"
  STATUS="logs/${RUN_ID}.status.json"
  OUTDIR="results/${RUN_ID}"
  LAYERS="'"$LAYERS"'"
  mkdir -p "$OUTDIR"

  write_status() {
    local state="$1"
    local detail="${2:-}"
    python3 - "$STATUS" "$state" "$RUN_ID" "$OUTDIR" "$LAYERS" "$detail" <<'"'"'PY'"'"'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status_path = Path(sys.argv[1])
state, run_id, outdir, layers, detail = sys.argv[2:7]
payload = {
    "run_id": run_id,
    "state": state,
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "outdir": outdir,
    "layers": layers,
    "result_json": sorted(str(path) for path in Path(outdir).glob("layer*/mwg_quality_distillation_*.json")),
    "result_md": sorted(str(path) for path in Path(outdir).glob("layer*/mwg_quality_distillation_*.md")),
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
  echo "ASI3 MWG-EW multi-layer quality"
  echo "run_id=$RUN_ID"
  echo "layers=$LAYERS"
  date -u
  python3 -c "import torch; import torch_npu; print(\"torch\", torch.__version__); print(\"torch_npu\", getattr(torch_npu, \"__version__\", \"unknown\")); print(\"npu_count\", torch.npu.device_count())"

  IFS=, read -r -a layer_array <<< "$LAYERS"
  for layer in "${layer_array[@]}"; do
    layer="$(echo "$layer" | xargs)"
    [[ -n "$layer" ]] || continue
    write_status running "layer=${layer}"
    layer_out="$OUTDIR/layer${layer}"
    mkdir -p "$layer_out"
    PROJECT_ROOT="$PROJECT_ROOT" OUTDIR="$layer_out" LAYER="$layer" \
      RANKS="${RANKS:-128,256}" \
      STEPS="${STEPS:-4000}" \
      EVAL_BATCHES="${EVAL_BATCHES:-96}" \
      BATCH="${BATCH:-1}" \
      SEQ="${SEQ:-128}" \
      LOG_EVERY="${LOG_EVERY:-250}" \
      STUDENTS="${STUDENTS:-persistent,token_residual,expert_residual}" \
      RESIDUAL_RANK="${RESIDUAL_RANK:-48}" \
      SCALE_AMPLITUDE="${SCALE_AMPLITUDE:-0.12}" \
      BASIS_COUNT="${BASIS_COUNT:-4}" \
      BASIS_NOISE="${BASIS_NOISE:-0.01}" \
      ACTIVATION_SOURCE="${ACTIVATION_SOURCE:-text}" \
      ACTIVATION_MAX_BATCHES="${ACTIVATION_MAX_BATCHES:-96}" \
      ACTIVATION_TEXT_BATCH="${ACTIVATION_TEXT_BATCH:-2}" \
      ACTIVATION_SEQ="${ACTIVATION_SEQ:-256}" \
      LR="${LR:-0.00025}" \
      DTYPE="${DTYPE:-fp32}" \
      SAVE_STUDENTS="${SAVE_STUDENTS:-}" \
      bash scripts/run_asi1_quality_distillation.sh
  done
  write_status running layers_done
  date -u
' > "$WRAPPER_LOG" 2>&1 < /dev/null &
PID="$!"

python3 - "$STATUS" "$RUN_ID" "$PID" "$WRAPPER_LOG" "$LAYERS" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status_path = Path(sys.argv[1])
run_id, pid, wrapper_log, layers = sys.argv[2:6]
status_path.write_text(json.dumps({
    "run_id": run_id,
    "state": "running",
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "pid": int(pid),
    "wrapper_log": wrapper_log,
    "layers": layers,
}, indent=2) + "\n", encoding="utf-8")
PY

echo "ASI3 multi-layer quality detached"
echo "pid=$PID"
echo "project_root=$PROJECT_ROOT"
echo "run_id=$RUN_ID"
echo "wrapper_log=$WRAPPER_LOG"
echo "status=$STATUS"
