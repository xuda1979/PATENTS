#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"
SPLIT_MANIFEST="${SPLIT_MANIFEST:?SPLIT_MANIFEST must point to explicit router broad split manifest}"
PATCH="${PATCH:?PATCH must point to the exact MWG checkpoint to evaluate}"
LAYER="${LAYER:-16}"
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
RUN_ID="asi3_token_router_broad_${TS}"
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
  OUTDIR="results/${RUN_ID}"
  STATUS="logs/${RUN_ID}.status.json"
  cd "$PROJECT_ROOT"

  write_status() {
    local state="$1"
    local detail="${2:-}"
    python3 - "$STATUS" "$state" "$RUN_ID" "$SPLIT_MANIFEST" "$PATCH" "$OUTDIR" "$detail" <<'"'"'PY'"'"'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status_path = Path(sys.argv[1])
state, run_id, split_manifest, patch, outdir, detail = sys.argv[2:8]
payload = {
    "run_id": run_id,
    "state": state,
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "split_manifest": split_manifest,
    "patch": patch,
    "outdir": outdir,
    "result_json": sorted(str(path) for path in Path(outdir).glob("*/token_router_validation.json")),
    "summary_json": str(Path(outdir) / "token_router_broad_summary.json")
    if (Path(outdir) / "token_router_broad_summary.json").exists()
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
  python3 - "$SPLIT_MANIFEST" <<'"'"'PY'"'"' > "$OUTDIR/suites.tsv"
import json
import sys

manifest = json.loads(open(sys.argv[1], encoding="utf-8").read())
for suite in manifest["suites"]:
    print("\t".join([suite["name"], suite["train_texts"], suite["eval_texts"], str(suite.get("overlap_removed", 0))]))
PY

  while IFS="$(printf \\t)" read -r name train_texts eval_texts overlap_removed; do
    [[ -n "$name" ]] || continue
    if [[ ! -f "$train_texts" || ! -f "$eval_texts" ]]; then
      echo "ERROR: missing train/eval texts for ${name}" >&2
      exit 2
    fi
    suite_outdir="$OUTDIR/$name"
    mkdir -p "$suite_outdir"
    write_status running "suite=${name}"
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
      --seed "${SEED:-0}" \
      --ridge-l2 "${RIDGE_L2:-1.0}" \
      --dtype "${DTYPE:-fp32}" \
      --out-json "$suite_outdir/token_router_validation.json" \
      --require-texts
  done < "$OUTDIR/suites.tsv"

  python3 - "$OUTDIR" "$SPLIT_MANIFEST" <<'"'"'PY'"'"'
import json
import math
import sys
from pathlib import Path

outdir = Path(sys.argv[1])
split_manifest = json.loads(Path(sys.argv[2]).read_text())
overlap = {suite["name"]: suite.get("overlap_removed", 0) for suite in split_manifest["suites"]}
runs = []
for path in sorted(outdir.glob("*/token_router_validation.json")):
    data = json.loads(path.read_text())
    name = path.parent.name
    runs.append({
        "suite": name,
        "path": str(path),
        "overlap_removed": overlap.get(name, 0),
        "dense": data["dense"],
        "patched": data["patched"],
        "train_summary": data["train_summary"],
        "eval_summary": data["eval_summary"],
        "mixed_frontier": [
            {
                "target_patch_fraction": row["target_patch_fraction"],
                "actual_patch_token_fraction": row["actual_patch_token_fraction"],
                "loss": row["loss"],
                "ppl_ratio": row["ppl_ratio"],
                "tokens": row["tokens"],
            }
            for row in data["mixed_frontier"]
        ],
    })
targets = sorted({row["target_patch_fraction"] for run in runs for row in run["mixed_frontier"]})
aggregate = []
for target in targets:
    rows = [row for run in runs for row in run["mixed_frontier"] if row["target_patch_fraction"] == target]
    dense_loss_sum = 0.0
    mixed_loss_sum = 0.0
    actual_patch_weighted = 0.0
    tokens = 0.0
    ratios = []
    for run in runs:
        row = next(item for item in run["mixed_frontier"] if item["target_patch_fraction"] == target)
        suite_tokens = float(row["tokens"])
        dense_loss = float(run["dense"]["loss"])
        dense_loss_sum += dense_loss * suite_tokens
        mixed_loss_sum += float(row["loss"]) * suite_tokens
        actual_patch_weighted += float(row["actual_patch_token_fraction"]) * suite_tokens
        tokens += suite_tokens
        ratios.append(float(row["ppl_ratio"]))
    dense_loss = dense_loss_sum / max(tokens, 1.0)
    mixed_loss = mixed_loss_sum / max(tokens, 1.0)
    aggregate.append({
        "target_patch_fraction": target,
        "token_weighted_actual_patch_fraction": actual_patch_weighted / max(tokens, 1.0),
        "token_weighted_ppl_ratio": math.exp(min(20.0, mixed_loss)) / math.exp(min(20.0, dense_loss)),
        "mean_suite_ppl_ratio": sum(ratios) / max(len(ratios), 1),
        "min_suite_ppl_ratio": min(ratios),
        "max_suite_ppl_ratio": max(ratios),
        "tokens": tokens,
        "suite_count": len(ratios),
    })
summary = {
    "run_count": len(runs),
    "split_manifest": split_manifest,
    "runs": runs,
    "aggregate_frontier": aggregate,
}
(outdir / "token_router_broad_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps({"summary": str(outdir / "token_router_broad_summary.json"), "aggregate_frontier": aggregate}, indent=2))
PY
  write_status running summary_done
' > "$WRAPPER_LOG" 2>&1 < /dev/null &
PID="$!"

python3 - "$STATUS" "$RUN_ID" "$PID" "$SPLIT_MANIFEST" "$PATCH" "$OUTDIR" "$WRAPPER_LOG" <<'PY'
import json
import sys
from datetime import datetime, timezone

status_path = sys.argv[1]
run_id, pid, split_manifest, patch, outdir, wrapper_log = sys.argv[2:8]
with open(status_path, "w", encoding="utf-8") as f:
    json.dump({
        "run_id": run_id,
        "state": "running",
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pid": int(pid),
        "split_manifest": split_manifest,
        "patch": patch,
        "outdir": outdir,
        "wrapper_log": wrapper_log,
    }, f, indent=2)
    f.write("\n")
PY

echo "ASI3 token-router broad detached"
echo "pid=$PID"
echo "run_id=$RUN_ID"
echo "split_manifest=$SPLIT_MANIFEST"
echo "patch=$PATCH"
echo "outdir=$OUTDIR"
echo "wrapper_log=$WRAPPER_LOG"
echo "status=$STATUS"
