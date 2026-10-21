#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"
MANIFEST="${MANIFEST:-$PROJECT_ROOT/data/heldout/manifest.json}"
TRAIN_TEXTS="${TRAIN_TEXTS:-$PROJECT_ROOT/data/heldout/router_train.txt}"
LAYER="${LAYER:-16}"
BASELINE_RANK="${BASELINE_RANK:-384}"
BASE_CKPT="${BASE_CKPT:-$PROJECT_ROOT/results/asi3_persistent_broad_baseline_20260525T114920Z/checkpoints/persistent_low_rank_r384.pt}"

cd "$PROJECT_ROOT"

if [[ ! -f "$MANIFEST" ]]; then
  echo "ERROR: manifest not found: $MANIFEST" >&2
  exit 2
fi
if [[ ! -f "$TRAIN_TEXTS" ]]; then
  echo "ERROR: train texts not found: $TRAIN_TEXTS" >&2
  exit 2
fi
if [[ ! -f "$BASE_CKPT" ]]; then
  echo "ERROR: base persistent checkpoint not found: $BASE_CKPT" >&2
  exit 2
fi

mkdir -p logs results
TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="asi3_persistent_lmce_baseline_${TS}"
OUTDIR="results/${RUN_ID}"
WRAPPER_LOG="logs/${RUN_ID}.log"
STATUS="logs/${RUN_ID}.status.json"

cat > "$STATUS" <<JSON
{
  "run_id": "$RUN_ID",
  "state": "launching",
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "outdir": "$OUTDIR",
  "wrapper_log": "$WRAPPER_LOG",
  "manifest": "$MANIFEST",
  "train_texts": "$TRAIN_TEXTS",
  "layer": $LAYER,
  "rank": $BASELINE_RANK,
  "base_checkpoint": "$BASE_CKPT"
}
JSON

nohup bash -lc '
  set -euo pipefail
  PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
  MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"
  RUN_ID="'"$RUN_ID"'"
  OUTDIR="results/${RUN_ID}"
  STATUS="logs/${RUN_ID}.status.json"
  MANIFEST="'"$MANIFEST"'"
  TRAIN_TEXTS="'"$TRAIN_TEXTS"'"
  LAYER="'"$LAYER"'"
  BASELINE_RANK="'"$BASELINE_RANK"'"
  BASE_CKPT="'"$BASE_CKPT"'"
  LMCE_CKPT="$OUTDIR/checkpoints/persistent_low_rank_r${BASELINE_RANK}_lmce.pt"
  LMCE_JSON="$OUTDIR/persistent_low_rank_r${BASELINE_RANK}_lmce.json"
  cd "$PROJECT_ROOT"
  mkdir -p "$OUTDIR/checkpoints"

  write_status() {
    local state="$1"
    local detail="${2:-}"
    python3 - "$STATUS" "$state" "$RUN_ID" "$OUTDIR" "$MANIFEST" "$TRAIN_TEXTS" "$LAYER" "$BASELINE_RANK" "$BASE_CKPT" "$LMCE_CKPT" "$detail" <<'"'"'PY'"'"'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status_path = Path(sys.argv[1])
state, run_id, outdir, manifest, train_texts, layer, baseline_rank, base_ckpt, lmce_ckpt, detail = sys.argv[2:12]
payload = {
    "run_id": run_id,
    "state": state,
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "outdir": outdir,
    "manifest": manifest,
    "train_texts": train_texts,
    "layer": int(layer),
    "rank": int(baseline_rank),
    "base_checkpoint": base_ckpt,
    "lmce_checkpoint": lmce_ckpt,
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

  echo "ASI3 persistent low-rank LM-CE broad baseline"
  echo "run_id=$RUN_ID"
  echo "base_checkpoint=$BASE_CKPT"
  echo "train_texts=$TRAIN_TEXTS"
  echo "manifest=$MANIFEST"
  date -u
  python3 -c "import torch; print(\"torch\", torch.__version__); import torch_npu; print(\"torch_npu\", getattr(torch_npu, \"__version__\", \"unknown\")); print(\"npu_count\", torch.npu.device_count())"

  write_status running lmce_calibrate_persistent_baseline
  python3 experiments/mwg_logit_calibrate.py \
    --model-dir "$MODEL_DIR" \
    --layer "$LAYER" \
    --checkpoint "$BASE_CKPT" \
    --out-checkpoint "$LMCE_CKPT" \
    --out-json "$LMCE_JSON" \
    --texts "$TRAIN_TEXTS" \
    --steps "${LMCE_STEPS:-1200}" \
    --lr "${LMCE_LR:-0.00002}" \
    --seq "${LMCE_SEQ:-256}" \
    --text-batch "${LMCE_TEXT_BATCH:-2}" \
    --eval-batches "${LMCE_EVAL_BATCHES:-128}" \
    --dtype "${LMCE_DTYPE:-fp32}" \
    --objective lm_ce \
    --require-texts

  if [[ ! -f "$LMCE_CKPT" ]]; then
    write_status failed "missing_lmce_checkpoint=$LMCE_CKPT"
    echo "ERROR: calibrated persistent checkpoint missing: $LMCE_CKPT" >&2
    exit 3
  fi

  write_status running launch_broad_validation
  MANIFEST="$MANIFEST" PATCH="$PROJECT_ROOT/$LMCE_CKPT" LAYER="$LAYER" MODEL_DIR="$MODEL_DIR" \
    bash scripts/launch_asi3_broad_validation_detached.sh | tee "$OUTDIR/broad_validation_launch.txt"
  write_status broad_validation_launched
  date -u
' > "$WRAPPER_LOG" 2>&1 < /dev/null &
PID="$!"

python3 - "$STATUS" "$RUN_ID" "$PID" "$OUTDIR" "$WRAPPER_LOG" "$MANIFEST" "$TRAIN_TEXTS" "$LAYER" "$BASELINE_RANK" "$BASE_CKPT" <<'PY'
import json
import sys
from datetime import datetime, timezone

status_path = sys.argv[1]
run_id, pid, outdir, wrapper_log, manifest, train_texts, layer, baseline_rank, base_ckpt = sys.argv[2:11]
with open(status_path, "w", encoding="utf-8") as handle:
    json.dump({
        "run_id": run_id,
        "state": "running",
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pid": int(pid),
        "outdir": outdir,
        "wrapper_log": wrapper_log,
        "manifest": manifest,
        "train_texts": train_texts,
        "layer": int(layer),
        "rank": int(baseline_rank),
        "base_checkpoint": base_ckpt,
    }, handle, indent=2)
    handle.write("\n")
PY

echo "ASI3 persistent LM-CE broad baseline detached"
echo "pid=$PID"
echo "project_root=$PROJECT_ROOT"
echo "run_id=$RUN_ID"
echo "outdir=$OUTDIR"
echo "wrapper_log=$WRAPPER_LOG"
echo "status=$STATUS"
