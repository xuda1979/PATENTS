#!/usr/bin/env bash
set -Eeuo pipefail

# Rank-512 parameter-matched quality control experiment (R1 reviewer requirement).
#
# Trains persistent, token_diag_core, and shuffled_diag_core at ranks 384, 401,
# and 512 with identical hyperparameters. If token_diag_core at rank 384 beats
# persistent at rank 512, the advantage is from generation, not extra capacity.

PROJECT_ROOT="/vllm-workspace/mwg-ew-transformer-research"
MODEL_DIR="/root/work/filestorage/Qwen2.5-1.5B-Instruct"
LAYER="16"
RANKS="${RANKS:-384,401,512}"
STEPS="${STEPS:-5000}"
BATCH="1"
LR="0.0002"
DTYPE="fp32"
SEEDS="${SEEDS:-2026 2027 2028 2029}"
ACTIVATION_MAX_BATCHES="315"
ACTIVATION_TEXT_BATCH="2"
ACTIVATION_SEQ="256"
ACTIVATION_SEED="1729"
FACTOR_SEED="4242"
EVAL_BATCHES="128"
NEAR_DUPLICATE_THRESHOLD="0.82"
RUN_ID="asi2_rank512_control_$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="$PROJECT_ROOT/results/$RUN_ID"

# Build student specs for all ranks
STUDENT_SPECS=""
for r in $(echo "$RANKS" | tr ',' ' '); do
  if [ -n "$STUDENT_SPECS" ]; then STUDENT_SPECS="${STUDENT_SPECS},"; fi
  STUDENT_SPECS="${STUDENT_SPECS}persistent:${r},token_diag_core:${r},shuffled_diag_core:${r}"
done

mkdir -p "$RUN_DIR"
echo "=== Rank-512 Parameter-Matched Control Experiment ==="
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
      --model-dir "$MODEL_DIR" \
      --layer "$LAYER" \
      --student-specs "$STUDENT_SPECS" \
      --steps "$STEPS" \
      --batch "$BATCH" \
      --lr "$LR" \
      --dtype "$DTYPE" \
      --seed "$seed" \
      --factor-seed "$FACTOR_SEED" \
      --activation-source text \
      --train-texts-file "$PROJECT_ROOT/data/quality/train.txt" \
      --eval-texts-file "$PROJECT_ROOT/data/quality/test.txt" \
      --activation-text-batch "$ACTIVATION_TEXT_BATCH" \
      --activation-seq "$ACTIVATION_SEQ" \
      --activation-seed "$ACTIVATION_SEED" \
      --activation-max-batches "$ACTIVATION_MAX_BATCHES" \
      --activation-log-every 25 \
      --eval-batches "$EVAL_BATCHES" \
      --near-duplicate-threshold "$NEAR_DUPLICATE_THRESHOLD" \
      --evidence-mode \
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

# Aggregate
python3 - << 'AGGREGATOR'
import json, glob, os, statistics
from pathlib import Path

run_dir = Path(sorted(glob.glob("/vllm-workspace/mwg-ew-transformer-research/results/asi2_rank512_control_*"))[-1])
results = {}
for seed_dir in sorted(run_dir.glob("seed_*")):
    jsons = list(seed_dir.glob("mwg_quality_distillation_*.json"))
    if not jsons:
        continue
    with open(jsons[0]) as f:
        data = json.load(f)
    for key, val in data.get("results", {}).items():
        if isinstance(val, dict) and "metrics" in val:
            if key not in results:
                results[key] = {"rel_mse": [], "cosine": [], "seeds": []}
            m = val["metrics"]
            if "relative_mse" in m:
                results[key]["rel_mse"].append(m["relative_mse"])
                results[key]["cosine"].append(m.get("cosine", float("nan")))
                results[key]["seeds"].append(seed_dir.name)

print("=== Aggregated results over seeds ===")
for key in sorted(results):
    r = results[key]
    if len(r["rel_mse"]) == 0:
        continue
    if len(r["rel_mse"]) > 1:
        mm = statistics.mean(r["rel_mse"]); sm = statistics.stdev(r["rel_mse"])
        mc = statistics.mean(r["cosine"]); sc = statistics.stdev(r["cosine"])
        print(f'{key:44s} rel_mse={mm:.4f}+-{sm:.4f}  cosine={mc:.4f}+-{sc:.4f}  (n={len(r["rel_mse"])})')
    else:
        print(f'{key:44s} rel_mse={r["rel_mse"][0]:.4f}  cosine={r["cosine"][0]:.4f}  (n=1)')

agg_path = run_dir / "aggregated_results.json"
with open(agg_path, "w") as f:
    json.dump(results, f, indent=2)
print(f"\nSaved to: {agg_path}")
AGGREGATOR

echo "=== DONE ==="
