#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
cd "$PROJECT_ROOT"

export ASCEND_RT_VISIBLE_DEVICES="${ASCEND_RT_VISIBLE_DEVICES:-0,1,2,3,4,5,6,7}"
export PYTORCH_NPU_ALLOC_CONF="${PYTORCH_NPU_ALLOC_CONF:-max_split_size_mb:256}"
export HCCL_CONNECT_TIMEOUT="${HCCL_CONNECT_TIMEOUT:-1800}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"

NPROC="$(python3 - <<'PY'
import os
ids = [x for x in os.environ.get("ASCEND_RT_VISIBLE_DEVICES", "").split(",") if x.strip()]
print(max(1, len(ids)))
PY
)"

mkdir -p results logs
TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="ASI3_scaled_sweep_${TS}"
LOG="logs/${RUN_ID}.log"
STATUS="logs/${RUN_ID}.status.json"

write_status() {
  local state="$1"
  local detail="${2:-}"
  python3 - "$STATUS" "$state" "$RUN_ID" "$LOG" "$detail" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status_path = Path(sys.argv[1])
state = sys.argv[2]
run_id = sys.argv[3]
log_path = sys.argv[4]
detail = sys.argv[5]
payload = {
    "run_id": run_id,
    "state": state,
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "log": log_path,
}
if detail:
    payload["detail"] = detail
payload["results"] = sorted(str(path) for path in Path("results").glob("ASI3_mwg_transformer_*.json"))
status_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
}

on_exit() {
  local rc=$?
  if [[ "$rc" -eq 0 ]]; then
    write_status "done"
  else
    write_status "failed" "exit_code=${rc}"
  fi
  return "$rc"
}
trap on_exit EXIT

write_status "running" "starting"

{
  echo "ASI3 MWG-EW scaled sweep"
  echo "run_id=$RUN_ID"
  echo "project_root=$PROJECT_ROOT"
  echo "ASCEND_RT_VISIBLE_DEVICES=$ASCEND_RT_VISIBLE_DEVICES"
  echo "nproc=$NPROC"
  echo "log=$LOG"
  echo "status=$STATUS"
  date -u
  python3 -c "import torch; print('torch', torch.__version__); import torch_npu; print('torch_npu', getattr(torch_npu, '__version__', 'unknown')); print('npu_count', torch.npu.device_count())"

  echo "== remote smoke =="
  python3 -m torch.distributed.run \
    --nproc_per_node="$NPROC" \
    experiments/mwg_transformer_ASI3_benchmark.py \
    --preset ASI3_smoke \
    --outdir results

  write_status "running" "smoke_done"

  echo "== scaled rank sweep =="
  python3 -m torch.distributed.run \
    --nproc_per_node="$NPROC" \
    experiments/mwg_transformer_ASI3_benchmark.py \
    --preset ASI3_sweep \
    --outdir results

  write_status "running" "sweep_done"
  date -u
} 2>&1 | tee "$LOG"
