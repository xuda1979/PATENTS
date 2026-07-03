#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/work/filestorage/mwg-ew-transformer-research}"
MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"
SPLIT_MANIFEST="${SPLIT_MANIFEST:-data/heldout/combined_extra_splits/manifest.json}"
PATCH="${PATCH:?PATCH must point to the exact MWG checkpoint to evaluate}"
LAYER="${LAYER:-16}"
SEEDS="${SEEDS:-0,1,2}"
POLICIES="${POLICIES:-suite_min,suite_mean,suite_median,global}"
RISK_BUDGETS="${RISK_BUDGETS:-0.05,0.10,0.25}"
RISK_MAX_PREDICTED_DELTA="${RISK_MAX_PREDICTED_DELTA:-0.0}"
RUN_PREFIX="${RUN_PREFIX:-asi3_five_suite_risk_policy_sweep}"
cd "$PROJECT_ROOT"

if [[ ! -f "$SPLIT_MANIFEST" ]]; then
  echo "ERROR: split manifest not found: $SPLIT_MANIFEST" >&2
  exit 2
fi
if [[ ! -f "$PATCH" ]]; then
  echo "ERROR: patch checkpoint not found: $PATCH" >&2
  exit 2
fi

mkdir -p logs results
TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="${RUN_PREFIX}_${TS}"
OUTDIR="results/${RUN_ID}"
WRAPPER_LOG="logs/${RUN_ID}.log"
STATUS="logs/${RUN_ID}.status.json"

cat > "$STATUS" <<JSON
{
  "run_id": "$RUN_ID",
  "state": "launching",
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "split_manifest": "$SPLIT_MANIFEST",
  "patch": "$PATCH",
  "seeds": "$SEEDS",
  "policies": "$POLICIES",
  "risk_budgets": "$RISK_BUDGETS",
  "risk_max_predicted_delta": "$RISK_MAX_PREDICTED_DELTA",
  "outdir": "$OUTDIR",
  "wrapper_log": "$WRAPPER_LOG"
}
JSON

nohup bash -lc '
  set -euo pipefail
  PROJECT_ROOT="${PROJECT_ROOT:-/root/work/filestorage/mwg-ew-transformer-research}"
  MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"
  RUN_ID="'"$RUN_ID"'"
  SPLIT_MANIFEST="'"$SPLIT_MANIFEST"'"
  PATCH="'"$PATCH"'"
  LAYER="'"$LAYER"'"
  SEEDS="'"$SEEDS"'"
  POLICIES="'"$POLICIES"'"
  RISK_BUDGETS="'"$RISK_BUDGETS"'"
  RISK_MAX_PREDICTED_DELTA="'"$RISK_MAX_PREDICTED_DELTA"'"
  OUTDIR="results/${RUN_ID}"
  STATUS="logs/${RUN_ID}.status.json"
  cd "$PROJECT_ROOT"

  write_status() {
    local state="$1"
    local detail="${2:-}"
    python3 - "$STATUS" "$state" "$RUN_ID" "$SPLIT_MANIFEST" "$PATCH" "$SEEDS" "$POLICIES" "$OUTDIR" "$detail" <<'"'"'PY'"'"'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status_path = Path(sys.argv[1])
state, run_id, split_manifest, patch, seeds, policies, outdir, detail = sys.argv[2:10]
out = Path(outdir)
payload = {
    "run_id": run_id,
    "state": state,
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "split_manifest": split_manifest,
    "patch": patch,
    "seeds": seeds,
    "policies": policies,
    "outdir": outdir,
    "policy_seed_jsons": sorted(str(path) for path in out.glob("policy=*/seed*/token_router_five_suite.json")),
    "summary_json": str(out / "risk_policy_sweep_summary.json")
    if (out / "risk_policy_sweep_summary.json").exists()
    else "",
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
  IFS="," read -r -a seed_array <<< "$SEEDS"
  IFS="," read -r -a policy_array <<< "$POLICIES"
  for policy in "${policy_array[@]}"; do
    policy="${policy//[[:space:]]/}"
    [[ -n "$policy" ]] || continue
    for seed in "${seed_array[@]}"; do
      seed="${seed//[[:space:]]/}"
      [[ -n "$seed" ]] || continue
      cell_outdir="$OUTDIR/policy=${policy}/seed${seed}"
      mkdir -p "$cell_outdir"
      write_status running "policy=${policy} seed=${seed}"
      python3 experiments/mwg_token_router_gate_eval.py \
        --model-dir "$MODEL_DIR" \
        --layer "$LAYER" \
        --checkpoint "$PATCH" \
        --suite-split-manifest "$SPLIT_MANIFEST" \
        --suite-balanced-sampling \
        --suite-balanced-ridge \
        --fail-on-suite-overlap \
        --seq "${SEQ:-256}" \
        --train-examples "${TRAIN_EXAMPLES:-0}" \
        --eval-examples "${EVAL_EXAMPLES:-0}" \
        --risk-budgets "$RISK_BUDGETS" \
        --risk-max-predicted-delta "$RISK_MAX_PREDICTED_DELTA" \
        --threshold-policy "$policy" \
        --seed "$seed" \
        --ridge-l2 "${RIDGE_L2:-1.0}" \
        --dtype "${DTYPE:-fp32}" \
        --out-json "$cell_outdir/token_router_five_suite.json" \
        --require-texts
    done
  done

  python3 - "$OUTDIR" <<'"'"'PY'"'"'
import json
import sys
from pathlib import Path

outdir = Path(sys.argv[1])
cells = []
for path in sorted(outdir.glob("policy=*/seed*/token_router_five_suite.json")):
    parts = path.parts
    policy = next(p.split("=", 1)[1] for p in parts if p.startswith("policy="))
    seed = int(next(p.split("seed", 1)[1] for p in parts if p.startswith("seed")))
    data = json.loads(path.read_text())
    cells.append({"policy": policy, "seed": seed, "path": str(path), "data": data})

policies = sorted({c["policy"] for c in cells})
targets = sorted({row["target_patch_fraction"] for c in cells for row in c["data"].get("mixed_frontier", [])})

frontier = []
for policy in policies:
    for target in targets:
        rows = [
            row
            for c in cells
            if c["policy"] == policy
            for row in c["data"].get("mixed_frontier", [])
            if row["target_patch_fraction"] == target
        ]
        if not rows:
            continue
        frontier.append({
            "policy": policy,
            "target_patch_fraction": target,
            "mean_actual_patch_token_fraction": sum(row["actual_patch_token_fraction"] for row in rows) / len(rows),
            "mean_ppl_ratio": sum(row["ppl_ratio"] for row in rows) / len(rows),
            "min_ppl_ratio": min(row["ppl_ratio"] for row in rows),
            "max_ppl_ratio": max(row["ppl_ratio"] for row in rows),
            "seed_count": len(rows),
        })

suite_names = sorted({
    suite
    for c in cells
    for suite in c["data"].get("eval_summary", {}).get("suite_metrics", {})
})
suite_summary = {}
for suite in suite_names:
    ratios = [
        c["data"]["eval_summary"]["suite_metrics"][suite]["patched_ppl_ratio"]
        for c in cells
        if suite in c["data"].get("eval_summary", {}).get("suite_metrics", {})
    ]
    suite_summary[suite] = {
        "mean_always_patched_ppl_ratio": sum(ratios) / max(len(ratios), 1),
        "min_always_patched_ppl_ratio": min(ratios),
        "max_always_patched_ppl_ratio": max(ratios),
        "seed_count": len(ratios),
    }

always = [c["data"]["patched"]["ppl_ratio"] for c in cells]
summary = {
    "cell_count": len(cells),
    "policies": policies,
    "seeds": sorted({c["seed"] for c in cells}),
    "always_patched": {
        "mean_ppl_ratio": sum(always) / max(len(always), 1),
        "min_ppl_ratio": min(always),
        "max_ppl_ratio": max(always),
    },
    "suite_summary": suite_summary,
    "mixed_frontier": frontier,
    "cells": [{"policy": c["policy"], "seed": c["seed"], "path": c["path"]} for c in cells],
}
(outdir / "risk_policy_sweep_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
PY
  write_status running summary_done
' > "$WRAPPER_LOG" 2>&1 < /dev/null &
PID="$!"

python3 - "$STATUS" "$RUN_ID" "$PID" "$SPLIT_MANIFEST" "$PATCH" "$SEEDS" "$POLICIES" "$OUTDIR" "$WRAPPER_LOG" <<'PY'
import json
import sys
from datetime import datetime, timezone

status_path = sys.argv[1]
run_id, pid, split_manifest, patch, seeds, policies, outdir, wrapper_log = sys.argv[2:10]
with open(status_path, "w", encoding="utf-8") as f:
    json.dump({
        "run_id": run_id,
        "state": "running",
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pid": int(pid),
        "split_manifest": split_manifest,
        "patch": patch,
        "seeds": seeds,
        "policies": policies,
        "outdir": outdir,
        "wrapper_log": wrapper_log,
    }, f, indent=2)
    f.write("\n")
PY

echo "ASI3 five-suite risk-policy sweep detached"
echo "pid=$PID"
echo "run_id=$RUN_ID"
echo "split_manifest=$SPLIT_MANIFEST"
echo "patch=$PATCH"
echo "seeds=$SEEDS"
echo "policies=$POLICIES"
echo "risk_budgets=$RISK_BUDGETS"
echo "risk_max_predicted_delta=$RISK_MAX_PREDICTED_DELTA"
echo "outdir=$OUTDIR"
echo "wrapper_log=$WRAPPER_LOG"
echo "status=$STATUS"
