#!/usr/bin/env bash
set -euo pipefail

# Launch tighter-eligibility Pareto sweeps for layers 17 and 18 sequentially
# on a single NPU, to test whether the layer-16 net selective win
# (max_delta=-0.20, ppl_r=0.9923) generalizes across FFN layers.
#
# Usage:
#   ASCEND_RT_VISIBLE_DEVICES=3 bash scripts/launch_asi3_multilayer_tighter_eligibility_detached.sh
#
# Each layer uses the calibrated checkpoint from the 2026-07-06 multilayer
# recovery run. The sweep grid matches the layer-16 pareto sweep:
# 8 max_delta x 4 policy x 3 risk_budget x 3 seeds = 96 cells per layer.

PROJECT_ROOT="${PROJECT_ROOT:-/root/work/filestorage/mwg-ew-transformer-research}"
MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"
MULTILAYER_ROOT="${MULTILAYER_ROOT:-results/asi3_multilayer_recovery_20260706T125106Z}"
ASCEND_RT_VISIBLE_DEVICES="${ASCEND_RT_VISIBLE_DEVICES:-3}"
LAYERS="${LAYERS:-17,18}"
SEEDS="${SEEDS:-0,1,2}"
POLICIES="${POLICIES:-suite_min,suite_mean,suite_median,global}"
RISK_BUDGETS="${RISK_BUDGETS:-0.05,0.10,0.25}"
MAX_DELTAS="${MAX_DELTAS:--0.30,-0.25,-0.20,-0.15,-0.12,-0.10,-0.08,-0.05}"

cd "$PROJECT_ROOT"
mkdir -p logs results

TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="asi3_multilayer_tighter_eligibility_${TS}"
WRAPPER_LOG="logs/${RUN_ID}.log"
STATUS="logs/${RUN_ID}.status.json"

cat > "$STATUS" <<JSON
{
  "run_id": "$RUN_ID",
  "state": "launching",
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "layers": "$LAYERS",
  "npu": "$ASCEND_RT_VISIBLE_DEVICES",
  "wrapper_log": "$WRAPPER_LOG"
}
JSON

nohup bash -c '
  set -euo pipefail
  PROJECT_ROOT="'"$PROJECT_ROOT"'"
  MODEL_DIR="'"$MODEL_DIR"'"
  MULTILAYER_ROOT="'"$MULTILAYER_ROOT"'"
  ASCEND_RT_VISIBLE_DEVICES="'"$ASCEND_RT_VISIBLE_DEVICES"'"
  LAYERS="'"$LAYERS"'"
  SEEDS="'"$SEEDS"'"
  POLICIES="'"$POLICIES"'"
  RISK_BUDGETS="'"$RISK_BUDGETS"'"
  MAX_DELTAS="'"$MAX_DELTAS"'"
  RUN_ID="'"$RUN_ID"'"
  STATUS="'"$STATUS"'"
  export ASCEND_RT_VISIBLE_DEVICES

  cd "$PROJECT_ROOT"

  write_status() {
    local state="$1"; local detail="${2:-}"
    python3 - "$STATUS" "$state" "$RUN_ID" "$detail" <<'"'"'PY'"'"'
import json, sys
from datetime import datetime, timezone
from pathlib import Path
status_path, state, run_id, detail = sys.argv[1:5]
payload = {
    "run_id": run_id,
    "state": state,
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
if detail:
    payload["detail"] = detail
existing = {}
if Path(status_path).exists():
    try:
        existing = json.loads(Path(status_path).read_text())
    except Exception:
        pass
existing.update(payload)
Path(status_path).write_text(json.dumps(existing, indent=2) + "\n")
PY
  }

  echo "ASI3 multi-layer tighter-eligibility sweep"
  echo "run_id=$RUN_ID"
  echo "layers=$LAYERS"
  echo "npu=$ASCEND_RT_VISIBLE_DEVICES"
  echo "max_deltas=$MAX_DELTAS"
  echo "policies=$POLICIES"
  echo "seeds=$SEEDS"

  IFS="," read -r -a layer_array <<< "$LAYERS"

  for LAYER in "${layer_array[@]}"; do
    LAYER_CKPT="${MULTILAYER_ROOT}/layer${LAYER}/checkpoints/mwg_expert_residual_r384_belle_lmce_cal_1200.pt"
    if [[ ! -f "$LAYER_CKPT" ]]; then
      echo "ERROR: missing checkpoint for layer ${LAYER}: $LAYER_CKPT" >&2
      write_status failed "missing_layer${LAYER}_checkpoint"
      exit 2
    fi
    LAYER_RUN_ID="asi3_tighter_eligibility_pareto_layer${LAYER}_$(date -u +%Y%m%dT%H%M%SZ)"
    LAYER_OUTDIR="results/${LAYER_RUN_ID}"
    LAYER_LOG="logs/${LAYER_RUN_ID}.log"
    mkdir -p "$LAYER_OUTDIR"

    echo "============================================================"
    echo "Starting layer ${LAYER} sweep"
    echo "  checkpoint: $LAYER_CKPT"
    echo "  outdir: $LAYER_OUTDIR"
    echo "  log: $LAYER_LOG"
    echo "============================================================"
    write_status running "layer${LAYER}_starting"

    LAYER_STATUS="logs/${LAYER_RUN_ID}.status.json"
    cat > "$LAYER_STATUS" <<JSONL
{
  "run_id": "$LAYER_RUN_ID",
  "state": "running",
  "layer": $LAYER,
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "outdir": "$LAYER_OUTDIR"
}
JSONL

    # Run the layer sweep inline (not detached) so we wait for it
    PATCH="$LAYER_CKPT" \
    LAYER="$LAYER" \
    SEEDS="$SEEDS" \
    POLICIES="$POLICIES" \
    RISK_BUDGETS="$RISK_BUDGETS" \
    MAX_DELTAS="$MAX_DELTAS" \
    RUN_PREFIX="asi3_tighter_eligibility_pareto_layer${LAYER}" \
    ASCEND_RT_VISIBLE_DEVICES="$ASCEND_RT_VISIBLE_DEVICES" \
    bash scripts/launch_asi3_tighter_eligibility_pareto_detached.sh \
      > "$LAYER_LOG" 2>&1 || {
        echo "Layer ${LAYER} sweep failed (see $LAYER_LOG)" >&2
        write_status failed "layer${LAYER}_failed"
        exit 3
      }

    echo "Layer ${LAYER} sweep completed. Summary:"
    if [[ -f "$LAYER_OUTDIR/tighter_eligibility_pareto_summary.json" ]]; then
      python3 - "$LAYER_OUTDIR/tighter_eligibility_pareto_summary.json" <<'"'"'PYSUM'"'"'
import json, sys
d = json.load(open(sys.argv[1]))
mf = d.get("mixed_frontier", [])
wins = [c for c in mf if c.get("mean_ppl_ratio", 1) < 1.0]
print(f"  cells: {d.get('cell_count')}, net wins: {len(wins)}")
if wins:
    best = sorted(wins, key=lambda c: c["mean_ppl_ratio"])[0]
    print(f"  best: max_delta={best['max_delta']} policy={best['policy']} tgt={best['target_patch_fraction']} actual={best['mean_actual_patch_token_fraction']:.4f} ppl_r={best['mean_ppl_ratio']:.6f}")
PYSUM
    fi
    write_status running "layer${LAYER}_done"
  done

  write_status done "all_layers_complete"
  echo "All layer sweeps completed."
  date -u
' > "$WRAPPER_LOG" 2>&1 < /dev/null &
PID="$!"

python3 - "$STATUS" "$RUN_ID" "$PID" "$WRAPPER_LOG" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path
status_path, run_id, pid, wrapper_log = sys.argv[1:5]
payload = {
    "run_id": run_id,
    "state": "running",
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "pid": int(pid),
    "wrapper_log": wrapper_log,
}
existing = {}
if Path(status_path).exists():
    try:
        existing = json.loads(Path(status_path).read_text())
    except Exception:
        pass
existing.update(payload)
Path(status_path).write_text(json.dumps(existing, indent=2) + "\n")
PY

echo "ASI3 multi-layer tighter-eligibility sweep detached"
echo "pid=$PID"
echo "run_id=$RUN_ID"
echo "layers=$LAYERS"
echo "npu=$ASCEND_RT_VISIBLE_DEVICES"
echo "wrapper_log=$WRAPPER_LOG"
echo "status=$STATUS"
