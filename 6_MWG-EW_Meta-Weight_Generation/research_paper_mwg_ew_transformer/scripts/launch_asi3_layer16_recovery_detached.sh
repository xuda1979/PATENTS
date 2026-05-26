#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"
cd "$PROJECT_ROOT"

mkdir -p logs results
TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="asi3_layer16_recovery_${TS}"
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
  MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"
  RUN_ID="'"$RUN_ID"'"
  OUTDIR="results/${RUN_ID}"
  RUN_OUTDIR="$OUTDIR"
  STATUS="logs/${RUN_ID}.status.json"
  cd "$PROJECT_ROOT"
  mkdir -p "$OUTDIR/layer16/checkpoints"

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
    "result_json": sorted(str(path) for path in Path(outdir).glob("**/*.json")),
    "checkpoints": sorted(str(path) for path in Path(outdir).glob("**/*.pt")),
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

  write_status running train_layer16_r384
  echo "ASI3 layer16 recovery"
  echo "run_id=$RUN_ID"
  echo "project_root=$PROJECT_ROOT"
  echo "model_dir=$MODEL_DIR"
  date -u
  python3 -c "import torch; print(\"torch\", torch.__version__); import torch_npu; print(\"torch_npu\", getattr(torch_npu, \"__version__\", \"unknown\")); print(\"npu_count\", torch.npu.device_count())"

  export ASCEND_RT_VISIBLE_DEVICES="${ASCEND_RT_VISIBLE_DEVICES:-0}"
  export NPROC_PER_NODE="${NPROC_PER_NODE:-1}"
  export PROJECT_ROOT MODEL_DIR
  export OUTDIR="$OUTDIR/layer16"
  export LAYER=16
  export RANKS="${RANKS:-384}"
  export STUDENTS="${STUDENTS:-expert_residual}"
  export STEPS="${STEPS:-5000}"
  export EVAL_BATCHES="${EVAL_BATCHES:-128}"
  export BATCH="${BATCH:-1}"
  export SEQ="${SEQ:-128}"
  export LOG_EVERY="${LOG_EVERY:-250}"
  export RESIDUAL_RANK="${RESIDUAL_RANK:-32}"
  export SCALE_AMPLITUDE="${SCALE_AMPLITUDE:-0.10}"
  export BASIS_COUNT="${BASIS_COUNT:-4}"
  export BASIS_NOISE="${BASIS_NOISE:-0.01}"
  export ACTIVATION_SOURCE="${ACTIVATION_SOURCE:-text}"
  export ACTIVATION_MAX_BATCHES="${ACTIVATION_MAX_BATCHES:-128}"
  export ACTIVATION_TEXT_BATCH="${ACTIVATION_TEXT_BATCH:-2}"
  export ACTIVATION_SEQ="${ACTIVATION_SEQ:-256}"
  export LR="${LR:-0.0002}"
  export DTYPE="${DTYPE:-fp32}"
  export SAVE_STUDENTS=1
  bash scripts/run_asi1_quality_distillation.sh

  BASE_CKPT="$RUN_OUTDIR/layer16/checkpoints/mwg_expert_residual_r384.pt"
  LMCE_CKPT="$RUN_OUTDIR/layer16/checkpoints/mwg_expert_residual_r384_belle_lmce_cal_1200.pt"
  LMCE_TEXTS="${LMCE_TEXTS:-}"
  HYBRID_TEXTS="${HYBRID_TEXTS:-$LMCE_TEXTS}"
  if [[ -z "$LMCE_TEXTS" ]]; then
    write_status failed "LMCE_TEXTS is required for recovery evaluation; refusing DEFAULT_TEXTS self-eval"
    echo "ERROR: LMCE_TEXTS must point to a held-out text file or ||-separated text list." >&2
    exit 2
  fi
  LMCE_TEXT_ARGS=(--texts "$LMCE_TEXTS")
  HYBRID_TEXT_ARGS=(--texts "$HYBRID_TEXTS")
  write_status running lmce_calibrate_1200
  python3 experiments/mwg_logit_calibrate.py \
    --model-dir "$MODEL_DIR" \
    --layer 16 \
    --checkpoint "$BASE_CKPT" \
    --out-checkpoint "$LMCE_CKPT" \
    --out-json "$RUN_OUTDIR/ppl_layer16_r384_belle_lmce_cal_1200_heldout256_eval128_tb2.json" \
    --objective lm_ce \
    --steps "${LMCE_STEPS:-1200}" \
    --lr "${LMCE_LR:-0.00002}" \
    --seq "${LMCE_SEQ:-256}" \
    --text-batch "${LMCE_TEXT_BATCH:-2}" \
    --eval-batches "${LMCE_EVAL_BATCHES:-128}" \
    --dtype "${LMCE_DTYPE:-fp32}" \
    --require-texts \
    "${LMCE_TEXT_ARGS[@]}"

  write_status running hybrid_oracle_belle256
  python3 experiments/mwg_hybrid_gate_eval.py \
    --model-dir "$MODEL_DIR" \
    --layer 16 \
    --checkpoint "$LMCE_CKPT" \
    --seq "${HYBRID_SEQ:-256}" \
    --eval-examples "${HYBRID_EVAL_EXAMPLES:-256}" \
    --fractions "${HYBRID_FRACTIONS:-0.25,0.5,0.75,1.0}" \
    --dtype "${HYBRID_DTYPE:-fp32}" \
    --out-json "$RUN_OUTDIR/hybrid_oracle_layer16_r384_lmce1200_belle256.json" \
    --require-texts \
    "${HYBRID_TEXT_ARGS[@]}"

  date -u
' > "$WRAPPER_LOG" 2>&1 < /dev/null &
PID="$!"

python3 - "$STATUS" "$RUN_ID" "$PID" "$OUTDIR" "$WRAPPER_LOG" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status_path = Path(sys.argv[1])
run_id, pid, outdir, wrapper_log = sys.argv[2:6]
status_path.write_text(json.dumps({
    "run_id": run_id,
    "state": "running",
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "pid": int(pid),
    "outdir": outdir,
    "wrapper_log": wrapper_log,
}, indent=2) + "\n", encoding="utf-8")
PY

echo "ASI3 layer16 recovery detached"
echo "pid=$PID"
echo "project_root=$PROJECT_ROOT"
echo "run_id=$RUN_ID"
echo "outdir=$OUTDIR"
echo "wrapper_log=$WRAPPER_LOG"
echo "status=$STATUS"
