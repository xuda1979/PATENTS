#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
cd "$PROJECT_ROOT"

export PYTORCH_NPU_ALLOC_CONF="${PYTORCH_NPU_ALLOC_CONF:-max_split_size_mb:256}"
export HCCL_CONNECT_TIMEOUT="${HCCL_CONNECT_TIMEOUT:-1800}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"

REPEATS="${AI3_RELIABILITY_REPEATS:-3}"
DEVICE_SETS="${AI3_RELIABILITY_DEVICE_SETS:-0 0,1 0,1,2,3}"
RANKS="${AI3_RELIABILITY_RANKS:-64,128,256}"

mkdir -p results logs
TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="ai3_reliability_scaling_${TS}"
LOG="logs/${RUN_ID}.log"
STATUS="logs/${RUN_ID}.status.json"
OUTDIR="results/${RUN_ID}"
mkdir -p "$OUTDIR"

write_status() {
  local state="$1"
  local detail="${2:-}"
  python3 - "$STATUS" "$state" "$RUN_ID" "$LOG" "$OUTDIR" "$detail" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status_path = Path(sys.argv[1])
state, run_id, log_path, outdir, detail = sys.argv[2:7]
payload = {
    "run_id": run_id,
    "state": state,
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "log": log_path,
    "outdir": outdir,
    "result_json": sorted(str(path) for path in Path(outdir).glob("*.json")),
}
if detail:
    payload["detail"] = detail
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
  echo "AI3 MWG-EW reliability scaling"
  echo "run_id=$RUN_ID"
  echo "project_root=$PROJECT_ROOT"
  echo "device_sets=$DEVICE_SETS"
  echo "repeats=$REPEATS"
  echo "ranks=$RANKS"
  echo "outdir=$OUTDIR"
  date -u
  python3 -c "import torch; print('torch', torch.__version__); import torch_npu; print('torch_npu', getattr(torch_npu, '__version__', 'unknown')); print('npu_count', torch.npu.device_count())"

  for devices in $DEVICE_SETS; do
    export ASCEND_RT_VISIBLE_DEVICES="$devices"
    nproc="$(python3 - <<'PY'
import os
ids = [x for x in os.environ["ASCEND_RT_VISIBLE_DEVICES"].split(",") if x.strip()]
print(len(ids))
PY
)"
    for repeat in $(seq 1 "$REPEATS"); do
      echo "== devices=$devices nproc=$nproc repeat=$repeat =="
      write_status "running" "devices=${devices};repeat=${repeat}"
      python3 -m torch.distributed.run \
        --nproc_per_node="$nproc" \
        experiments/mwg_transformer_ai3_benchmark.py \
        --preset ai3_sweep \
        --ranks "$RANKS" \
        --warmup 3 \
        --iters 10 \
        --train-iters 3 \
        --comm-iters 5 \
        --seed $((1234 + repeat)) \
        --outdir "$OUTDIR"
    done
  done

  python3 experiments/aggregate_ai3_scaling.py \
    --glob "${OUTDIR}/ai3_mwg_transformer_*.json" \
    --out-json "${OUTDIR}/${RUN_ID}_summary.json" \
    --out-md "${OUTDIR}/${RUN_ID}_summary.md"
  write_status "running" "summary_done"
  date -u
} 2>&1 | tee "$LOG"
