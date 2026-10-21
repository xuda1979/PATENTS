#!/usr/bin/env bash
set -Eeuo pipefail

# Shuffled-context control experiment for MWG-EW.
#
# This experiment trains the token_diag_core generator with SHUFFLED context
# (the generator sees a random token's hidden state instead of the actual one).
# If the shuffled control matches the causal core, the generator is just learning
# a fixed correction. If it degrades toward persistent-low-rank, context matters.
#
# Controls: persistent_low_rank (same rank), shuffled_diag_core (same rank),
#           token_diag_core (same rank, for direct comparison)
# Ranks: 384 (base), 401 (parameter-matched)
# Seeds: 2026, 2027, 2028, 2029 (same as closing test)

PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"
LAYER="${LAYER:-16}"
BASE_RANK="${BASE_RANK:-384}"
MATCHED_RANK="${MATCHED_RANK:-401}"
STEPS="${STEPS:-5000}"
BATCH="${BATCH:-1}"
LR="${LR:-0.0002}"
DTYPE="${DTYPE:-fp32}"
SEEDS="${SEEDS:-2026 2027 2028 2029}"
ACTIVATION_MAX_BATCHES="${ACTIVATION_MAX_BATCHES:-315}"
ACTIVATION_TEXT_BATCH="${ACTIVATION_TEXT_BATCH:-2}"
ACTIVATION_SEQ="${ACTIVATION_SEQ:-256}"
ACTIVATION_SEED="${ACTIVATION_SEED:-1729}"
FACTOR_SEED="${FACTOR_SEED:-4242}"
EVAL_BATCHES="${EVAL_BATCHES:-128}"
NEAR_DUPLICATE_THRESHOLD="${NEAR_DUPLICATE_THRESHOLD:-0.82}"
RUN_ID="asi2_shuffled_context_$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="${RUN_DIR:-$PROJECT_ROOT/results/$RUN_ID}"

STUDENT_SPECS="persistent:${BASE_RANK},token_diag_core:${BASE_RANK},shuffled_diag_core:${BASE_RANK},persistent:${MATCHED_RANK},token_diag_core:${MATCHED_RANK},shuffled_diag_core:${MATCHED_RANK}"

mkdir -p "$RUN_DIR"
echo "=== Shuffled-Context Control Experiment ==="
echo "run_id: $RUN_ID"
echo "run_dir: $RUN_DIR"
echo "student_specs: $STUDENT_SPECS"
echo "seeds: $SEEDS"

cd "$PROJECT_ROOT"

for seed in $SEEDS; do
    outdir="$RUN_DIR/seed_${seed}"
    mkdir -p "$outdir"
    echo ""
    echo "=== Training seed $seed ==="
    python3 experiments/mwg_quality_distillation.py \
      --teacher-source hf-layer \
      --model-dir "$MODEL_DIR" \
      --layer "$LAYER" \
      --student-specs "$STUDENT_SPECS" \
      --steps "$STEPS" \
      --batch "$BATCH" \
      --lr "$LR" \
      --dtype "$DTYPE" \
      --seed "$seed" \
      --factor-seed "$FACTOR_SEED" \
      --activation-text-batch "$ACTIVATION_TEXT_BATCH" \
      --activation-seq "$ACTIVATION_SEQ" \
      --activation-seed "$ACTIVATION_SEED" \
      --activation-max-batches "$ACTIVATION_MAX_BATCHES" \
      --activation-log-every 25 \
      --eval-batches "$EVAL_BATCHES" \
      --near-duplicate-threshold "$NEAR_DUPLICATE_THRESHOLD" \
      --save-students \
      --checkpoint-every 1000 \
      --resume auto \
      --cache-dir "$RUN_DIR/cache" \
      --progress-json "$outdir/progress.json" \
      --outdir "$outdir" \
      2>&1 | tee "$outdir/train.log"
    echo "Seed $seed complete"
done

echo ""
echo "=== All seeds complete ==="
echo "Results in: $RUN_DIR"
