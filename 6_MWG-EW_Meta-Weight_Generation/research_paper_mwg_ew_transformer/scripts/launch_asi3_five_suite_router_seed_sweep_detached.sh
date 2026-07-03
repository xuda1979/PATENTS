#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"
SPLIT_MANIFEST="${SPLIT_MANIFEST:-data/heldout/combined_extra_splits/manifest.json}"
PATCH="${PATCH:?PATCH must point to the exact MWG checkpoint to evaluate}"
LAYER="${LAYER:-16}"
SEEDS="${SEEDS:-0,1,2}"
RUN_PREFIX="${RUN_PREFIX:-asi3_five_suite_router_seed_sweep}"
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
  "outdir": "$OUTDIR",
  "wrapper_log": "$WRAPPER_LOG"
}
JSON

nohup bash -lc '
  set -euo pipefail
  PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
  MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"
  RUN_ID="'"$RUN_ID"'"
  SPLIT_MANIFEST="'"$SPLIT_MANIFEST"'"
  PATCH="'"$PATCH"'"
  LAYER="'"$LAYER"'"
  SEEDS="'"$SEEDS"'"
  OUTDIR="results/${RUN_ID}"
  STATUS="logs/${RUN_ID}.status.json"
  cd "$PROJECT_ROOT"

  write_status() {
    local state="$1"
    local detail="${2:-}"
    python3 - "$STATUS" "$state" "$RUN_ID" "$SPLIT_MANIFEST" "$PATCH" "$SEEDS" "$OUTDIR" "$detail" <<'"'"'PY'"'"'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status_path = Path(sys.argv[1])
state, run_id, split_manifest, patch, seeds, outdir, detail = sys.argv[2:9]
out = Path(outdir)
payload = {
    "run_id": run_id,
    "state": state,
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "split_manifest": split_manifest,
    "patch": patch,
    "seeds": seeds,
    "outdir": outdir,
    "seed_jsons": sorted(str(path) for path in out.glob("seed*/token_router_five_suite.json")),
    "summary_json": str(out / "five_suite_router_seed_sweep_summary.json")
    if (out / "five_suite_router_seed_sweep_summary.json").exists()
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
  for seed in "${seed_array[@]}"; do
    seed="${seed//[[:space:]]/}"
    [[ -n "$seed" ]] || continue
    seed_outdir="$OUTDIR/seed${seed}"
    mkdir -p "$seed_outdir"
    write_status running "seed=${seed}"
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
      --joint-budgets "${JOINT_BUDGETS:-0.05,0.10,0.25}" \
      --threshold-policy "${THRESHOLD_POLICY:-suite_local}" \
      --seed "$seed" \
      --ridge-l2 "${RIDGE_L2:-1.0}" \
      --dtype "${DTYPE:-fp32}" \
      --out-json "$seed_outdir/token_router_five_suite.json" \
      --require-texts
  done

  python3 - "$OUTDIR" <<'"'"'PY'"'"'
import json
import math
import sys
from pathlib import Path

outdir = Path(sys.argv[1])
seed_payloads = []
for path in sorted(outdir.glob("seed*/token_router_five_suite.json")):
    data = json.loads(path.read_text())
    seed_payloads.append({"seed": int(path.parent.name.replace("seed", "")), "path": str(path), "data": data})

targets = sorted({row["target_patch_fraction"] for item in seed_payloads for row in item["data"].get("mixed_frontier", [])})
frontier = []
for target in targets:
    rows = [
        row
        for item in seed_payloads
        for row in item["data"].get("mixed_frontier", [])
        if row["target_patch_fraction"] == target
    ]
    frontier.append({
        "target_patch_fraction": target,
        "mean_actual_patch_token_fraction": sum(row["actual_patch_token_fraction"] for row in rows) / max(len(rows), 1),
        "mean_ppl_ratio": sum(row["ppl_ratio"] for row in rows) / max(len(rows), 1),
        "min_ppl_ratio": min(row["ppl_ratio"] for row in rows),
        "max_ppl_ratio": max(row["ppl_ratio"] for row in rows),
        "seed_count": len(rows),
    })

suite_names = sorted({
    suite
    for item in seed_payloads
    for suite in item["data"].get("eval_summary", {}).get("suite_metrics", {})
})
suite_summary = {}
for suite in suite_names:
    ratios = [
        item["data"]["eval_summary"]["suite_metrics"][suite]["patched_ppl_ratio"]
        for item in seed_payloads
        if suite in item["data"].get("eval_summary", {}).get("suite_metrics", {})
    ]
    suite_summary[suite] = {
        "mean_always_patched_ppl_ratio": sum(ratios) / max(len(ratios), 1),
        "min_always_patched_ppl_ratio": min(ratios),
        "max_always_patched_ppl_ratio": max(ratios),
        "seed_count": len(ratios),
    }

always = [item["data"]["patched"]["ppl_ratio"] for item in seed_payloads]
summary = {
    "seed_count": len(seed_payloads),
    "seeds": [item["seed"] for item in seed_payloads],
    "paths": [item["path"] for item in seed_payloads],
    "always_patched": {
        "mean_ppl_ratio": sum(always) / max(len(always), 1),
        "min_ppl_ratio": min(always),
        "max_ppl_ratio": max(always),
    },
    "suite_summary": suite_summary,
    "mixed_frontier": frontier,
}
(outdir / "five_suite_router_seed_sweep_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
PY
  write_status running summary_done
' > "$WRAPPER_LOG" 2>&1 < /dev/null &
PID="$!"

python3 - "$STATUS" "$RUN_ID" "$PID" "$SPLIT_MANIFEST" "$PATCH" "$SEEDS" "$OUTDIR" "$WRAPPER_LOG" <<'PY'
import json
import sys
from datetime import datetime, timezone

status_path = sys.argv[1]
run_id, pid, split_manifest, patch, seeds, outdir, wrapper_log = sys.argv[2:9]
with open(status_path, "w", encoding="utf-8") as f:
    json.dump({
        "run_id": run_id,
        "state": "running",
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pid": int(pid),
        "split_manifest": split_manifest,
        "patch": patch,
        "seeds": seeds,
        "outdir": outdir,
        "wrapper_log": wrapper_log,
    }, f, indent=2)
    f.write("\n")
PY

echo "ASI3 five-suite router seed sweep detached"
echo "pid=$PID"
echo "run_id=$RUN_ID"
echo "split_manifest=$SPLIT_MANIFEST"
echo "patch=$PATCH"
echo "seeds=$SEEDS"
echo "outdir=$OUTDIR"
echo "wrapper_log=$WRAPPER_LOG"
echo "status=$STATUS"
