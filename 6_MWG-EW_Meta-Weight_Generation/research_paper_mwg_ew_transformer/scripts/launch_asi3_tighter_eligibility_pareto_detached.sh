#!/usr/bin/env bash
set -euo pipefail

# Launch a tighter-eligibility Pareto sweep on ASI3 (single NPU, device 0).
# Sweeps risk_max_predicted_delta over a fine grid and aggregates per-cell
# token_router_five_suite.json files into a Pareto summary JSON.
#
# Usage:
#   PATCH=results/asi3_layer16_recovery_20260624T110725Z/layer16/checkpoints/mwg_expert_residual_r384_belle_lmce_cal_1200.pt \
#   bash scripts/launch_asi3_tighter_eligibility_pareto_detached.sh

PROJECT_ROOT="${PROJECT_ROOT:-/root/work/filestorage/mwg-ew-transformer-research}"
MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"
SPLIT_MANIFEST="${SPLIT_MANIFEST:-data/heldout/combined_extra_splits/manifest.json}"
PATCH="${PATCH:?PATCH must point to the exact MWG checkpoint to evaluate}"
LAYER="${LAYER:-16}"
SEEDS="${SEEDS:-0,1,2}"
POLICIES="${POLICIES:-suite_min,suite_mean,suite_median,global}"
RISK_BUDGETS="${RISK_BUDGETS:-0.05,0.10,0.25}"
MAX_DELTAS="${MAX_DELTAS:--0.30,-0.25,-0.20,-0.15,-0.12,-0.10,-0.08,-0.05}"
RUN_PREFIX="${RUN_PREFIX:-asi3_tighter_eligibility_pareto}"
ASCEND_RT_VISIBLE_DEVICES="${ASCEND_RT_VISIBLE_DEVICES:-0}"
cd "$PROJECT_ROOT"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="${RUN_PREFIX}_${TS}"
OUTDIR="results/${RUN_ID}"
WRAPPER_LOG="logs/${RUN_ID}.log"
STATUS="logs/${RUN_ID}.status.json"

mkdir -p logs results "$OUTDIR"

cat > "$STATUS" <<JSON
{
  "run_id": "$RUN_ID",
  "state": "launching",
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "split_manifest": "$SPLIT_MANIFEST",
  "patch": "$PATCH",
  "layer": $LAYER,
  "seeds": "$SEEDS",
  "policies": "$POLICIES",
  "risk_budgets": "$RISK_BUDGETS",
  "max_deltas": "$MAX_DELTAS",
  "outdir": "$OUTDIR",
  "wrapper_log": "$WRAPPER_LOG"
}
JSON

nohup bash -lc '
  set -euo pipefail
  PROJECT_ROOT="'"$PROJECT_ROOT"'"
  MODEL_DIR="'"$MODEL_DIR"'"
  SPLIT_MANIFEST="'"$SPLIT_MANIFEST"'"
  PATCH="'"$PATCH"'"
  LAYER="'"$LAYER"'"
  SEEDS="'"$SEEDS"'"
  POLICIES="'"$POLICIES"'"
  RISK_BUDGETS="'"$RISK_BUDGETS"'"
  MAX_DELTAS="'"$MAX_DELTAS"'"
  RUN_ID="'"$RUN_ID"'"
  OUTDIR="'"$OUTDIR"'"
  STATUS="'"$STATUS"'"
  export ASCEND_RT_VISIBLE_DEVICES="'"$ASCEND_RT_VISIBLE_DEVICES"'"

  cd "$PROJECT_ROOT"

  write_status() {
    local state="$1"; local detail="${2:-}"
    python3 - "$STATUS" "$state" "$RUN_ID" "$OUTDIR" "$detail" <<'"'"'PY'"'"'
import json, sys
from datetime import datetime, timezone
from pathlib import Path
status_path, state, run_id, outdir, detail = sys.argv[1:6]
payload = {
    "run_id": run_id,
    "state": state,
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "outdir": outdir,
}
if detail:
    payload["detail"] = detail
Path(status_path).write_text(json.dumps(payload, indent=2) + "\n")
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

  echo "ASI3 tighter-eligibility Pareto sweep"
  echo "run_id=$RUN_ID"
  echo "outdir=$OUTDIR"
  echo "patch=$PATCH"
  echo "max_deltas=$MAX_DELTAS"
  echo "policies=$POLICIES"
  echo "risk_budgets=$RISK_BUDGETS"
  echo "seeds=$SEEDS"
  date -u

  python3 -c "import torch; import torch_npu; print(\"torch\", torch.__version__, \"torch_npu\", torch_npu.__version__, \"npu_count\", torch.npu.device_count())"
  echo "Using NPU: ${ASCEND_RT_VISIBLE_DEVICES}"

  IFS="," read -r -a delta_array <<< "$MAX_DELTAS"
  IFS="," read -r -a policy_array <<< "$POLICIES"
  IFS="," read -r -a seed_array <<< "$SEEDS"

  for delta in "${delta_array[@]}"; do
    delta_dir="$OUTDIR/max_delta=${delta}"
    mkdir -p "$delta_dir"
    for policy in "${policy_array[@]}"; do
      policy_dir="$delta_dir/policy=${policy}"
      mkdir -p "$policy_dir"
      for seed in "${seed_array[@]}"; do
        seed_dir="$policy_dir/seed${seed}"
        mkdir -p "$seed_dir"
        cell_log="$seed_dir/cell.log"
        echo "Running cell max_delta=$delta policy=$policy seed=$seed"
        write_status running "max_delta=${delta}/policy=${policy}/seed${seed}"
        python3 experiments/mwg_token_router_gate_eval.py \
          --model-dir "$MODEL_DIR" \
          --layer "$LAYER" \
          --checkpoint "$PATCH" \
          --suite-split-manifest "$SPLIT_MANIFEST" \
          --suite-balanced-sampling \
          --suite-balanced-ridge \
          --fail-on-suite-overlap \
          --seq 256 \
          --train-examples 0 \
          --eval-examples 0 \
          --risk-budgets "$RISK_BUDGETS" \
          --risk-max-predicted-delta "$delta" \
          --threshold-policy "$policy" \
          --seed "$seed" \
          --ridge-l2 1.0 \
          --dtype fp32 \
          --out-json "$seed_dir/token_router_five_suite.json" \
          --require-texts > "$cell_log" 2>&1 || {
            echo "  FAIL cell max_delta=$delta policy=$policy seed=$seed (see $cell_log)" >&2
            continue
          }
        # Extract mean ppl_ratio across risk_budgets from the mixed_frontier
        python3 - "$seed_dir/token_router_five_suite.json" <<'"'"'PY'"'"'
import json, sys
d=json.load(open(sys.argv[1]))
mf=d.get("mixed_frontier",[])
if mf:
    ratios=[c.get("ppl_ratio") for c in mf if c.get("ppl_ratio") is not None]
    if ratios:
        print(f"  Done cell. ppl_ratio={sum(ratios)/len(ratios):.10f}")
    else:
        print("  Done cell. ppl_ratio=NA")
else:
    print("  Done cell. ppl_ratio=NA")
PY
      done
    done
  done

  # Aggregate into Pareto summary
  write_status running summary
  python3 - "$OUTDIR" "$MAX_DELTAS" "$POLICIES" "$SEEDS" <<'"'"'PY'"'"'
import json, sys, glob
from pathlib import Path
from collections import defaultdict

outdir = Path(sys.argv[1])
max_deltas = sys.argv[2].split(",")
policies = sys.argv[3].split(",")
seeds = [int(s) for s in sys.argv[4].split(",")]

cells = []
for delta in max_deltas:
    for policy in policies:
        for seed in seeds:
            cell_path = outdir / f"max_delta={delta}" / f"policy={policy}" / f"seed{seed}" / "token_router_five_suite.json"
            if not cell_path.exists():
                continue
            try:
                d = json.loads(cell_path.read_text())
            except Exception as e:
                print(f"WARN: failed to parse {cell_path}: {e}")
                continue
            mf = d.get("mixed_frontier", [])
            es = d.get("eval_summary", {})
            for c in mf:
                cells.append({
                    "max_delta": delta,
                    "policy": policy,
                    "seed": seed,
                    "target_patch_fraction": c.get("target_patch_fraction"),
                    "actual_patch_token_fraction": c.get("actual_patch_token_fraction"),
                    "ppl_ratio": c.get("ppl_ratio"),
                    "delta_loss": c.get("delta_loss"),
                    "train_score_threshold": c.get("train_score_threshold"),
                    "path": str(cell_path),
                })
            # Always-patched from eval_summary
            ap = es.get("patched_ppl_ratio")
            if ap is not None:
                cells.append({
                    "max_delta": delta,
                    "policy": policy,
                    "seed": seed,
                    "target_patch_fraction": 1.0,
                    "actual_patch_token_fraction": 1.0,
                    "ppl_ratio": ap,
                    "delta_loss": es.get("patched_loss") - es.get("dense_loss"),
                    "train_score_threshold": None,
                    "path": str(cell_path),
                })

# Mixed frontier: aggregate across seeds
agg = defaultdict(list)
for c in cells:
    if c["target_patch_fraction"] == 1.0:
        continue
    key = (c["max_delta"], c["policy"], c["target_patch_fraction"])
    agg[key].append(c)

frontier = []
for (delta, policy, tgt), rows in sorted(agg.items()):
    ratios = [r["ppl_ratio"] for r in rows if r["ppl_ratio"] is not None]
    actuals = [r["actual_patch_token_fraction"] for r in rows if r["actual_patch_token_fraction"] is not None]
    if not ratios:
        continue
    frontier.append({
        "max_delta": delta,
        "policy": policy,
        "target_patch_fraction": tgt,
        "mean_actual_patch_token_fraction": sum(actuals)/len(actuals) if actuals else None,
        "mean_ppl_ratio": sum(ratios)/len(ratios),
        "min_ppl_ratio": min(ratios),
        "max_ppl_ratio": max(ratios),
        "seed_count": len(rows),
    })

# Always-patched aggregate
ap_ratios = [c["ppl_ratio"] for c in cells if c["target_patch_fraction"] == 1.0 and c["ppl_ratio"] is not None]
always_patched = {
    "mean_ppl_ratio": sum(ap_ratios)/len(ap_ratios) if ap_ratios else None,
    "min_ppl_ratio": min(ap_ratios) if ap_ratios else None,
    "max_ppl_ratio": max(ap_ratios) if ap_ratios else None,
    "count": len(ap_ratios),
}

# Pareto: sort by mean_ppl_ratio ascending
pareto = sorted(frontier, key=lambda x: x["mean_ppl_ratio"])
wins = [c for c in frontier if c["mean_ppl_ratio"] < 1.0]

summary = {
    "run_id": outdir.name,
    "cell_count": len(frontier),
    "max_deltas": max_deltas,
    "policies": policies,
    "seeds": seeds,
    "risk_budgets": [0.05, 0.10, 0.25],
    "always_patched": always_patched,
    "mixed_frontier": frontier,
    "pareto_sorted": pareto,
    "net_wins": wins,
    "net_win_count": len(wins),
    "cells": cells,
}
summary_path = outdir / "tighter_eligibility_pareto_summary.json"
summary_path.write_text(json.dumps(summary, indent=2) + "\n")
print("Wrote " + str(summary_path))
print("Cells: " + str(len(frontier)) + ", net wins: " + str(len(wins)))
if wins:
    best = sorted(wins, key=lambda x: x["mean_ppl_ratio"])[0]
    print("Best: max_delta=" + str(best["max_delta"]) + " policy=" + str(best["policy"]) + " tgt=" + str(best["target_patch_fraction"]) + " actual=" + ("%.4f" % best["mean_actual_patch_token_fraction"]) + " ppl_r=" + ("%.4f" % best["mean_ppl_ratio"]))
PY

  date -u
  write_status done
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

echo "ASI3 tighter-eligibility Pareto sweep detached"
echo "pid=$PID"
echo "run_id=$RUN_ID"
echo "max_deltas=$MAX_DELTAS"
echo "policies=$POLICIES"
echo "risk_budgets=$RISK_BUDGETS"
echo "seeds=$SEEDS"
echo "outdir=$OUTDIR"
echo "wrapper_log=$WRAPPER_LOG"
echo "status=$STATUS"
