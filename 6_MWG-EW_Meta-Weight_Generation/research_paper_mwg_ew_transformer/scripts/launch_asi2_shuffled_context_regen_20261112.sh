#!/usr/bin/env bash
set -Eeuo pipefail

# Shuffled-context control on the 2026-11-10 regeneration artifacts
# (run on ASI2, 2026-11-12).
#
# Purpose: the manuscript's generated-minus-shuffled contrasts
# (approximately -0.0002 at ranks 384/401) rest on the ORIGINAL archive,
# while the token/persistent cells were re-verified by the 2026-11-10
# regeneration.  This run re-establishes the shuffled-context control
# against the SAME regenerated artifacts: identical teacher, activation
# caches, splits, hyperparameters, and code as
# asi2_causal_quality_closing_20261110T155855Z, with
# STUDENT_SPECS=shuffled_diag_core:384,shuffled_diag_core:401 only
# (the regenerated reports already carry token/persistent cells, which
# are NOT retrained here).
#
# The activation cache from the regeneration run is reused via
# --cache-dir so the cache fingerprints (model digest, code digest,
# split metadata, activation parameters) match and no activation
# rebuild is triggered.  Training the two shuffled students takes
# roughly 3-5 minutes per seed on ASI2 CPU.

PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
ENV_LABEL="${ENV_LABEL:-ASI2}"
MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"
TRAIN_TEXTS="${TRAIN_TEXTS:-$PROJECT_ROOT/data/quality/train.txt}"
EVAL_TEXTS="${EVAL_TEXTS:-$PROJECT_ROOT/data/quality/dev.txt}"
SPLIT_MANIFEST="${SPLIT_MANIFEST:-$PROJECT_ROOT/data/quality/manifest.json}"
REGEN_DIR="${REGEN_DIR:-$PROJECT_ROOT/results/asi2_causal_quality_closing_20261110T155855Z}"
CACHE_DIR="${CACHE_DIR:-$REGEN_DIR/cache}"
LAYER="${LAYER:-16}"
NPROC_PER_NODE="${NPROC_PER_NODE:-4}"
STEPS="${STEPS:-5000}"
EVAL_BATCHES="${EVAL_BATCHES:-128}"
BATCH="${BATCH:-1}"
SEQ="${SEQ:-128}"
LOG_EVERY="${LOG_EVERY:-100}"
CHECKPOINT_EVERY="${CHECKPOINT_EVERY:-250}"
ACTIVATION_MAX_BATCHES="${ACTIVATION_MAX_BATCHES:-315}"
ACTIVATION_TEXT_BATCH="${ACTIVATION_TEXT_BATCH:-2}"
ACTIVATION_SEQ="${ACTIVATION_SEQ:-256}"
ACTIVATION_SEED="${ACTIVATION_SEED:-1729}"
FACTOR_SEED="${FACTOR_SEED:-1729}"
LR="${LR:-0.0002}"
DTYPE="${DTYPE:-fp32}"
NEAR_DUPLICATE_THRESHOLD="${NEAR_DUPLICATE_THRESHOLD:-0.82}"
STUDENT_SPECS="${STUDENT_SPECS:-shuffled_diag_core:384,shuffled_diag_core:401}"
SEEDS="${SEEDS:-2026 2027 2028 2029}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="${RUN_ID:-asi2_shuffled_context_regen_${TS}}"
RUN_DIR="${RUN_DIR:-$PROJECT_ROOT/results/$RUN_ID}"
LOG="${LOG:-$PROJECT_ROOT/logs/${RUN_ID}.log}"

mkdir -p "$RUN_DIR" "$(dirname "$LOG")"

fail() {
  echo "ERROR: $*" >&2
  exit 2
}

[[ -d "$PROJECT_ROOT" ]] || fail "project root missing: $PROJECT_ROOT"
[[ -d "$MODEL_DIR" ]] || fail "model dir missing: $MODEL_DIR"
[[ -s "$TRAIN_TEXTS" && -s "$EVAL_TEXTS" ]] || fail "split texts missing"
[[ "$TRAIN_TEXTS" != "$EVAL_TEXTS" ]] || fail "TRAIN_TEXTS and EVAL_TEXTS must differ"
[[ -s "$SPLIT_MANIFEST" ]] || fail "split manifest missing: $SPLIT_MANIFEST"
[[ -d "$CACHE_DIR" ]] || fail "regeneration cache missing: $CACHE_DIR"
for seed in $SEEDS; do
  [[ "$seed" =~ ^[0-9]+$ ]] || fail "non-numeric seed: $seed"
done

cd "$PROJECT_ROOT"
[[ -s "experiments/mwg_quality_distillation.py" ]] || fail "distillation harness missing"

{
  echo "=== shuffled-context control on regenerated artifacts ==="
  echo "run_id: $RUN_ID"
  echo "run_dir: $RUN_DIR"
  echo "student_specs: $STUDENT_SPECS"
  echo "seeds: $SEEDS"
  echo "cache_dir: $CACHE_DIR"
  echo "model_dir: $MODEL_DIR"
} | tee -a "$LOG"

for seed in $SEEDS; do
  outdir="$RUN_DIR/seed_${seed}"
  mkdir -p "$outdir"
  echo "--- seed ${seed} ---" | tee -a "$LOG"
  python3 experiments/mwg_quality_distillation.py \
    --model-dir "$MODEL_DIR" \
    --env-label "$ENV_LABEL" \
    --layer "$LAYER" \
    --student-specs "$STUDENT_SPECS" \
    --batch "$BATCH" \
    --seq "$SEQ" \
    --steps "$STEPS" \
    --eval-batches "$EVAL_BATCHES" \
    --log-every "$LOG_EVERY" \
    --lr "$LR" \
    --activation-source text \
    --train-texts-file "$TRAIN_TEXTS" \
    --eval-texts-file "$EVAL_TEXTS" \
    --evidence-mode \
    --near-duplicate-threshold "$NEAR_DUPLICATE_THRESHOLD" \
    --activation-max-batches "$ACTIVATION_MAX_BATCHES" \
    --activation-text-batch "$ACTIVATION_TEXT_BATCH" \
    --activation-seq "$ACTIVATION_SEQ" \
    --activation-seed "$ACTIVATION_SEED" \
    --activation-log-every 25 \
    --factor-seed "$FACTOR_SEED" \
    --dtype "$DTYPE" \
    --seed "$seed" \
    --save-students \
    --checkpoint-every "$CHECKPOINT_EVERY" \
    --resume auto \
    --cache-dir "$CACHE_DIR" \
    --progress-json "$outdir/progress.json" \
    --outdir "$outdir" \
    >> "$LOG" 2>&1
  echo "seed ${seed} done" | tee -a "$LOG"
done

echo "=== summary ==="
python3 - "$RUN_DIR" $SEEDS <<'PY'
import json, sys
from pathlib import Path

run_dir = Path(sys.argv[1])
seeds = sys.argv[2:]
rows = []
for seed in seeds:
    reports = sorted((run_dir / f"seed_{seed}").glob("mwg_quality_distillation_*.json"))
    if len(reports) != 1:
        print(f"WARN: expected one report for seed {seed}, found {len(reports)}")
        continue
    d = json.loads(reports[0].read_text())
    for key, cell in sorted(d["results"].items()):
        if key.startswith("mwg_shuffled_diag_core_r"):
            rows.append({
                "seed": int(seed),
                "name": key,
                "rank": int(key.rsplit("_r", 1)[1]),
                "relative_mse": cell["metrics"]["relative_mse"],
                "token_relative_mse_p95": cell["metrics"].get("token_relative_mse_p95"),
            })
out = run_dir / "shuffled_context_summary.json"
out.write_text(json.dumps({"kind": "shuffled_context_regen_summary_v1",
                           "source_run": str(run_dir), "rows": rows},
                          indent=1, sort_keys=True) + "\n")
print(json.dumps(rows, indent=1))
print(f"wrote {out}")
PY
echo "run_dir: $RUN_DIR"
echo "log: $LOG"
