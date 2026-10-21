#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"
SPLIT_ROOT="${SPLIT_ROOT:?SPLIT_ROOT must point to explicit router CV split directory}"
PATCH="${PATCH:?PATCH must point to the exact MWG checkpoint to evaluate}"
LAYER="${LAYER:-16}"
SEEDS="${SEEDS:-0,1,2}"
cd "$PROJECT_ROOT"

if [[ ! -d "$SPLIT_ROOT" ]]; then
  echo "ERROR: split root not found: $SPLIT_ROOT" >&2
  exit 2
fi
if [[ ! -f "$PATCH" ]]; then
  echo "ERROR: patch checkpoint not found: $PATCH" >&2
  exit 2
fi

mkdir -p logs results
TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="asi3_token_router_cv_${TS}"
OUTDIR="results/${RUN_ID}"
WRAPPER_LOG="logs/${RUN_ID}.log"
STATUS="logs/${RUN_ID}.status.json"

cat > "$STATUS" <<JSON
{
  "run_id": "$RUN_ID",
  "state": "launching",
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "split_root": "$SPLIT_ROOT",
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
  SPLIT_ROOT="'"$SPLIT_ROOT"'"
  PATCH="'"$PATCH"'"
  LAYER="'"$LAYER"'"
  SEEDS="'"$SEEDS"'"
  OUTDIR="results/${RUN_ID}"
  STATUS="logs/${RUN_ID}.status.json"
  cd "$PROJECT_ROOT"

  write_status() {
    local state="$1"
    local detail="${2:-}"
    python3 - "$STATUS" "$state" "$RUN_ID" "$SPLIT_ROOT" "$PATCH" "$SEEDS" "$OUTDIR" "$detail" <<'"'"'PY'"'"'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status_path = Path(sys.argv[1])
state, run_id, split_root, patch, seeds, outdir, detail = sys.argv[2:9]
payload = {
    "run_id": run_id,
    "state": state,
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "split_root": split_root,
    "patch": patch,
    "seeds": seeds,
    "outdir": outdir,
    "result_json": sorted(str(path) for path in Path(outdir).glob("seed*/token_router_validation.json")),
    "summary_json": str(Path(outdir) / "token_router_cv_summary.json")
    if (Path(outdir) / "token_router_cv_summary.json").exists()
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
  IFS=, read -r -a seed_array <<< "$SEEDS"
  for seed in "${seed_array[@]}"; do
    seed="$(echo "$seed" | xargs)"
    [[ -n "$seed" ]] || continue
    train_texts="$SPLIT_ROOT/seed${seed}/router_train.txt"
    eval_texts="$SPLIT_ROOT/seed${seed}/router_eval.txt"
    if [[ ! -f "$train_texts" || ! -f "$eval_texts" ]]; then
      echo "ERROR: missing split files for seed ${seed}" >&2
      exit 2
    fi
    if [[ "$train_texts" == "$eval_texts" ]]; then
      echo "ERROR: train/eval paths match for seed ${seed}" >&2
      exit 2
    fi
    seed_outdir="$OUTDIR/seed${seed}"
    mkdir -p "$seed_outdir"
    write_status running "seed=${seed}"
    python3 experiments/mwg_token_router_gate_eval.py \
      --model-dir "$MODEL_DIR" \
      --layer "$LAYER" \
      --checkpoint "$PATCH" \
      --train-texts "$train_texts" \
      --eval-texts "$eval_texts" \
      --seq "${SEQ:-256}" \
      --train-examples "${TRAIN_EXAMPLES:-0}" \
      --eval-examples "${EVAL_EXAMPLES:-0}" \
      --fractions "${FRACTIONS:-0.01,0.03,0.05,0.10,0.25,0.50}" \
      --seed "$seed" \
      --ridge-l2 "${RIDGE_L2:-1.0}" \
      --dtype "${DTYPE:-fp32}" \
      --out-json "$seed_outdir/token_router_validation.json" \
      --require-texts
  done

  python3 - "$OUTDIR" <<'"'"'PY'"'"'
import json
import statistics
import sys
from pathlib import Path

outdir = Path(sys.argv[1])
runs = []
for path in sorted(outdir.glob("seed*/token_router_validation.json")):
    data = json.loads(path.read_text())
    runs.append({
        "seed": int(path.parent.name.replace("seed", "")),
        "path": str(path),
        "dense": data["dense"],
        "patched": data["patched"],
        "train_summary": data["train_summary"],
        "eval_summary": data["eval_summary"],
        "mixed_frontier": [
            {
                "target_patch_fraction": row["target_patch_fraction"],
                "actual_patch_token_fraction": row["actual_patch_token_fraction"],
                "ppl_ratio": row["ppl_ratio"],
            }
            for row in data["mixed_frontier"]
        ],
    })
targets = sorted({row["target_patch_fraction"] for run in runs for row in run["mixed_frontier"]})
aggregate = []
for target in targets:
    rows = [row for run in runs for row in run["mixed_frontier"] if row["target_patch_fraction"] == target]
    aggregate.append({
        "target_patch_fraction": target,
        "mean_actual_patch_token_fraction": statistics.fmean(row["actual_patch_token_fraction"] for row in rows),
        "mean_ppl_ratio": statistics.fmean(row["ppl_ratio"] for row in rows),
        "min_ppl_ratio": min(row["ppl_ratio"] for row in rows),
        "max_ppl_ratio": max(row["ppl_ratio"] for row in rows),
        "run_count": len(rows),
    })
summary = {
    "run_count": len(runs),
    "runs": runs,
    "aggregate_frontier": aggregate,
}
(outdir / "token_router_cv_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps({"summary": str(outdir / "token_router_cv_summary.json"), "aggregate_frontier": aggregate}, indent=2))
PY
  write_status running summary_done
' > "$WRAPPER_LOG" 2>&1 < /dev/null &
PID="$!"

python3 - "$STATUS" "$RUN_ID" "$PID" "$SPLIT_ROOT" "$PATCH" "$SEEDS" "$OUTDIR" "$WRAPPER_LOG" <<'PY'
import json
import sys
from datetime import datetime, timezone

status_path = sys.argv[1]
run_id, pid, split_root, patch, seeds, outdir, wrapper_log = sys.argv[2:9]
with open(status_path, "w", encoding="utf-8") as f:
    json.dump({
        "run_id": run_id,
        "state": "running",
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pid": int(pid),
        "split_root": split_root,
        "patch": patch,
        "seeds": seeds,
        "outdir": outdir,
        "wrapper_log": wrapper_log,
    }, f, indent=2)
    f.write("\n")
PY

echo "ASI3 token-router CV detached"
echo "pid=$PID"
echo "run_id=$RUN_ID"
echo "split_root=$SPLIT_ROOT"
echo "seeds=$SEEDS"
echo "patch=$PATCH"
echo "outdir=$OUTDIR"
echo "wrapper_log=$WRAPPER_LOG"
echo "status=$STATUS"
