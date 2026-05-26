#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"
HELDOUT_DIR="${HELDOUT_DIR:-data/heldout}"
HELDOUT_MANIFEST="${HELDOUT_MANIFEST:-data/heldout/manifest.json}"
TRAIN_SOURCES="${TRAIN_SOURCES:-data/heldout/router_train.txt,data/heldout/router_eval.txt}"
PATCH="${PATCH:?PATCH must point to the exact MWG checkpoint to evaluate}"
LAYER="${LAYER:-16}"
SEEDS="${SEEDS:-0,1,2}"
TRAIN_FRACTION="${TRAIN_FRACTION:-0.75}"
MAX_TRAIN_COUNT="${MAX_TRAIN_COUNT:-0}"
SPLIT_PREP_SCRIPT="${SPLIT_PREP_SCRIPT:-experiments/prepare_router_broad_splits.py}"
RUN_PREFIX="${RUN_PREFIX:-asi3_token_router_broad_seed_sweep}"
cd "$PROJECT_ROOT"

if [[ ! -f "$HELDOUT_MANIFEST" ]]; then
  echo "ERROR: held-out manifest not found: $HELDOUT_MANIFEST" >&2
  exit 2
fi
if [[ ! -f "$SPLIT_PREP_SCRIPT" ]]; then
  echo "ERROR: split prep script not found: $SPLIT_PREP_SCRIPT" >&2
  exit 2
fi
if [[ ! -f "$PATCH" ]]; then
  echo "ERROR: patch checkpoint not found: $PATCH" >&2
  exit 2
fi

IFS=',' read -r -a TRAIN_SOURCE_ARRAY <<< "$TRAIN_SOURCES"
for train_source in "${TRAIN_SOURCE_ARRAY[@]}"; do
  if [[ ! -f "$train_source" ]]; then
    echo "ERROR: train source not found: $train_source" >&2
    exit 2
  fi
done

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
  "heldout_manifest": "$HELDOUT_MANIFEST",
  "train_sources": "$TRAIN_SOURCES",
  "split_prep_script": "$SPLIT_PREP_SCRIPT",
  "patch": "$PATCH",
  "seeds": "$SEEDS",
  "train_fraction": "$TRAIN_FRACTION",
  "max_train_count": "$MAX_TRAIN_COUNT",
  "outdir": "$OUTDIR",
  "wrapper_log": "$WRAPPER_LOG"
}
JSON

nohup bash -lc '
  set -euo pipefail
  PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
  MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"
  RUN_ID="'"$RUN_ID"'"
  HELDOUT_DIR="'"$HELDOUT_DIR"'"
  HELDOUT_MANIFEST="'"$HELDOUT_MANIFEST"'"
  TRAIN_SOURCES="'"$TRAIN_SOURCES"'"
  SPLIT_PREP_SCRIPT="'"$SPLIT_PREP_SCRIPT"'"
  PATCH="'"$PATCH"'"
  LAYER="'"$LAYER"'"
  SEEDS="'"$SEEDS"'"
  TRAIN_FRACTION="'"$TRAIN_FRACTION"'"
  MAX_TRAIN_COUNT="'"$MAX_TRAIN_COUNT"'"
  OUTDIR="results/${RUN_ID}"
  STATUS="logs/${RUN_ID}.status.json"
  cd "$PROJECT_ROOT"

  write_status() {
    local state="$1"
    local detail="${2:-}"
    python3 - "$STATUS" "$state" "$RUN_ID" "$HELDOUT_MANIFEST" "$TRAIN_SOURCES" "$SPLIT_PREP_SCRIPT" "$PATCH" "$SEEDS" "$TRAIN_FRACTION" "$MAX_TRAIN_COUNT" "$OUTDIR" "$detail" <<'"'"'PY'"'"'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status_path = Path(sys.argv[1])
state, run_id, heldout_manifest, train_sources, split_prep_script, patch, seeds, train_fraction, max_train_count, outdir, detail = sys.argv[2:13]
payload = {
    "run_id": run_id,
    "state": state,
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "heldout_manifest": heldout_manifest,
    "train_sources": train_sources,
    "split_prep_script": split_prep_script,
    "patch": patch,
    "seeds": seeds,
    "train_fraction": train_fraction,
    "max_train_count": max_train_count,
    "outdir": outdir,
    "seed_summaries": sorted(str(path) for path in Path(outdir).glob("seed*/token_router_broad_summary.json")),
    "summary_json": str(Path(outdir) / "token_router_broad_seed_sweep_summary.json")
    if (Path(outdir) / "token_router_broad_seed_sweep_summary.json").exists()
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
  IFS="," read -r -a train_source_array <<< "$TRAIN_SOURCES"

  for seed in "${seed_array[@]}"; do
    seed="${seed//[[:space:]]/}"
    [[ -n "$seed" ]] || continue
    seed_outdir="$OUTDIR/seed${seed}"
    split_dir="$seed_outdir/splits"
    mkdir -p "$seed_outdir"
    split_args=()
    for train_source in "${train_source_array[@]}"; do
      train_source="${train_source//[[:space:]]/}"
      [[ -n "$train_source" ]] || continue
      split_args+=(--train-source "$train_source")
    done
    write_status running "prepare_splits_seed=${seed}"
    python3 "$SPLIT_PREP_SCRIPT" \
      "${split_args[@]}" \
      --heldout-dir "$HELDOUT_DIR" \
      --manifest "$HELDOUT_MANIFEST" \
      --outdir "$split_dir" \
      --seed "$seed" \
      --train-fraction "$TRAIN_FRACTION" \
      --max-train-count "$MAX_TRAIN_COUNT" \
      > "$seed_outdir/split_manifest_stdout.json"

    python3 - "$split_dir/manifest.json" <<'"'"'PY'"'"' > "$seed_outdir/suites.tsv"
import json
import sys

manifest = json.loads(open(sys.argv[1], encoding="utf-8").read())
for suite in manifest["suites"]:
    print("\t".join([suite["name"], suite["train_texts"], suite["eval_texts"], str(suite.get("overlap_removed", 0))]))
PY

    while IFS="$(printf \\t)" read -r name train_texts eval_texts overlap_removed; do
      [[ -n "$name" ]] || continue
      suite_outdir="$seed_outdir/$name"
      mkdir -p "$suite_outdir"
      write_status running "seed=${seed} suite=${name}"
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
        --out-json "$suite_outdir/token_router_validation.json" \
        --require-texts
    done < "$seed_outdir/suites.tsv"

    python3 - "$seed_outdir" "$split_dir/manifest.json" "$seed" <<'"'"'PY'"'"'
import json
import math
import sys
from pathlib import Path

outdir = Path(sys.argv[1])
split_manifest = json.loads(Path(sys.argv[2]).read_text())
seed = int(sys.argv[3])
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
    dense_loss_sum = 0.0
    mixed_loss_sum = 0.0
    actual_patch_weighted = 0.0
    tokens = 0.0
    ratios = []
    for run in runs:
        row = next(item for item in run["mixed_frontier"] if item["target_patch_fraction"] == target)
        suite_tokens = float(row["tokens"])
        dense_loss_sum += float(run["dense"]["loss"]) * suite_tokens
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
    "seed": seed,
    "run_count": len(runs),
    "split_manifest": split_manifest,
    "runs": runs,
    "aggregate_frontier": aggregate,
}
(outdir / "token_router_broad_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps({"seed": seed, "summary": str(outdir / "token_router_broad_summary.json"), "aggregate_frontier": aggregate}, indent=2))
PY
  done

  python3 - "$OUTDIR" <<'"'"'PY'"'"'
import json
import sys
from pathlib import Path

outdir = Path(sys.argv[1])
seed_summaries = [json.loads(path.read_text()) for path in sorted(outdir.glob("seed*/token_router_broad_summary.json"))]
targets = sorted({row["target_patch_fraction"] for summary in seed_summaries for row in summary["aggregate_frontier"]})
aggregate = []
for target in targets:
    rows = [
        row
        for summary in seed_summaries
        for row in summary["aggregate_frontier"]
        if row["target_patch_fraction"] == target
    ]
    aggregate.append({
        "target_patch_fraction": target,
        "mean_actual_patch_token_fraction": sum(row["token_weighted_actual_patch_fraction"] for row in rows) / max(len(rows), 1),
        "mean_token_weighted_ppl_ratio": sum(row["token_weighted_ppl_ratio"] for row in rows) / max(len(rows), 1),
        "min_token_weighted_ppl_ratio": min(row["token_weighted_ppl_ratio"] for row in rows),
        "max_token_weighted_ppl_ratio": max(row["token_weighted_ppl_ratio"] for row in rows),
        "seed_count": len(rows),
    })
summary = {
    "seed_count": len(seed_summaries),
    "seeds": [summary["seed"] for summary in seed_summaries],
    "seed_summaries": seed_summaries,
    "aggregate_frontier": aggregate,
}
(outdir / "token_router_broad_seed_sweep_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps({"summary": str(outdir / "token_router_broad_seed_sweep_summary.json"), "aggregate_frontier": aggregate}, indent=2))
PY
  write_status running summary_done
' > "$WRAPPER_LOG" 2>&1 < /dev/null &
PID="$!"

python3 - "$STATUS" "$RUN_ID" "$PID" "$HELDOUT_MANIFEST" "$TRAIN_SOURCES" "$SPLIT_PREP_SCRIPT" "$PATCH" "$SEEDS" "$TRAIN_FRACTION" "$MAX_TRAIN_COUNT" "$OUTDIR" "$WRAPPER_LOG" <<'PY'
import json
import sys
from datetime import datetime, timezone

status_path = sys.argv[1]
run_id, pid, heldout_manifest, train_sources, split_prep_script, patch, seeds, train_fraction, max_train_count, outdir, wrapper_log = sys.argv[2:13]
with open(status_path, "w", encoding="utf-8") as f:
    json.dump({
        "run_id": run_id,
        "state": "running",
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pid": int(pid),
        "heldout_manifest": heldout_manifest,
        "train_sources": train_sources,
        "split_prep_script": split_prep_script,
        "patch": patch,
        "seeds": seeds,
        "train_fraction": train_fraction,
        "max_train_count": max_train_count,
        "outdir": outdir,
        "wrapper_log": wrapper_log,
    }, f, indent=2)
    f.write("\n")
PY

echo "ASI3 token-router broad seed sweep detached"
echo "pid=$PID"
echo "run_id=$RUN_ID"
echo "heldout_manifest=$HELDOUT_MANIFEST"
echo "train_sources=$TRAIN_SOURCES"
echo "split_prep_script=$SPLIT_PREP_SCRIPT"
echo "patch=$PATCH"
echo "seeds=$SEEDS"
echo "train_fraction=$TRAIN_FRACTION"
echo "max_train_count=$MAX_TRAIN_COUNT"
echo "outdir=$OUTDIR"
echo "wrapper_log=$WRAPPER_LOG"
echo "status=$STATUS"
