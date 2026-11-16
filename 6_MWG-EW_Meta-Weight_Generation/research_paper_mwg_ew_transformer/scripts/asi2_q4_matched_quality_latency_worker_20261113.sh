#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# Q4 matched trained-model quality-latency worker (detached, ASI2, 2026-11-13).
#
# Purpose: close the manuscript's Q4 gate -- "a simultaneous quality-latency
# comparison from the same trained model and runtime" -- by (1) training
# matched students (persistent static baseline, token_diag_core conditional,
# and the new block_givens output-subspace student) under the frozen closing
# protocol, then (2) measuring NPU latency of the SAME trained checkpoints
# through the four-arm benchmark's --trained-checkpoint path, and (3)
# computing held-out patched-model perplexity of the same checkpoints.
#
# Acceptance targets (pre-registered, from the manuscript's engineering
# discussion; thresholds, not predictions): at least 20% lower end-to-end
# latency with no more than 1% relative perplexity degradation versus the
# strongest matched static baseline.  A failed target is recorded as a
# negative result, never promoted.
#
# Usage:  bash scripts/asi2_q4_matched_quality_latency_worker_20261113.sh [--check|--worker]
#   default: preflight then launch detached worker
#   --check: preflight only
#   --worker: run the seed sweep in the foreground (internal)

PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
ENV_LABEL="${ENV_LABEL:-ASI2}"
MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"
TRAIN_TEXTS="${TRAIN_TEXTS:-$PROJECT_ROOT/data/quality/train.txt}"
EVAL_TEXTS="${EVAL_TEXTS:-$PROJECT_ROOT/data/quality/dev.txt}"
SPLIT_MANIFEST="${SPLIT_MANIFEST:-$PROJECT_ROOT/data/quality/manifest.json}"
DEVICES="${ASCEND_RT_VISIBLE_DEVICES:-0,1,2,3}"
NPROC_PER_NODE="${NPROC_PER_NODE:-4}"
SEEDS="${SEEDS:-2026 2027 2028 2029}"
LAYER="${LAYER:-16}"
BASE_RANK="${BASE_RANK:-384}"
MATCHED_RANK="${MATCHED_RANK:-401}"
STUDENT_SPECS="${STUDENT_SPECS:-persistent:${BASE_RANK},persistent:${MATCHED_RANK},token_diag_core:${BASE_RANK},block_givens:${BASE_RANK}}"
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
RUN_ID="${RUN_ID:-asi2_q4_matched_quality_latency_$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="${RUN_DIR:-$PROJECT_ROOT/results/$RUN_ID}"
LOG="${LOG:-$PROJECT_ROOT/logs/${RUN_ID}.log}"
STATUS="$RUN_DIR/status.json"
ARTIFACT_MANIFEST="$RUN_DIR/artifact_manifest.json"
# Latency phase: benchmark geometry matching the closing run's teacher FFN
# (Qwen2.5-1.5B layer 16: d=1536, m=8960), trained rank, CPU-visible arms
# plus fused arms when the compiled op libraries are present.
BENCH_D="${BENCH_D:-1536}"
BENCH_M="${BENCH_M:-8960}"
BENCH_SEQ="${BENCH_SEQ:-128}"
BENCH_ITERS="${BENCH_ITERS:-50}"
BENCH_WARMUP="${BENCH_WARMUP:-10}"
BENCH_REPEATS="${BENCH_REPEATS:-3}"
BENCH_DTYPE="${BENCH_DTYPE:-fp16}"
V1_OP_LIBRARY="${V1_OP_LIBRARY:-}"
V4_OP_LIBRARY="${V4_OP_LIBRARY:-}"

mkdir -p "$RUN_DIR" "$(dirname "$LOG")"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$LOG"; }

die() { log "ERROR: $*"; exit 2; }

validate_uint() {
  local name="$1" value="$2" min="$3"
  if ! [[ "$value" =~ ^[0-9]+$ ]] || (( value < min )); then
    die "invalid $name: $value"
  fi
}

atomic_status() {
  python3 - "$STATUS" "$1" "$2" "$3" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
state, stage, detail = sys.argv[2:5]
payload = {"state": state, "stage": stage, "detail": detail,
           "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
tmp = path.with_suffix(".tmp")
tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
tmp.replace(path)
PY
}

preflight() {
  [[ -d "$PROJECT_ROOT" ]] || die "project root missing: $PROJECT_ROOT"
  [[ -d "$MODEL_DIR" ]] || die "model dir missing: $MODEL_DIR"
  [[ -s "$TRAIN_TEXTS" && -s "$EVAL_TEXTS" ]] || die "split texts missing"
  [[ "$TRAIN_TEXTS" != "$EVAL_TEXTS" ]] || die "TRAIN_TEXTS and EVAL_TEXTS must differ"
  [[ -s "$SPLIT_MANIFEST" ]] || die "split manifest missing: $SPLIT_MANIFEST"
  for f in experiments/mwg_quality_distillation.py \
           experiments/mwg_block_givens.py \
           experiments/mwg_four_arm_lifetime_benchmark.py \
           experiments/mwg_ppl_patch_eval.py; do
    [[ -s "$PROJECT_ROOT/$f" ]] || die "required harness missing: $f"
  done
  validate_uint LAYER "$LAYER" 0
  for seed in $SEEDS; do validate_uint seed "$seed" 0; done
  python3 - "$STUDENT_SPECS" <<'PY'
import sys
specs = sys.argv[1].split(",")
modes = {"persistent", "token_diag_core", "block_givens"}
seen = set()
for spec in specs:
    mode, _, rank = spec.partition(":")
    if mode not in modes or not rank.isdigit() or int(rank) <= 0:
        raise SystemExit(f"invalid student spec: {spec!r}")
    if spec in seen:
        raise SystemExit(f"duplicate student spec: {spec!r}")
    seen.add(spec)
print("student_specs_ok", len(seen))
PY
  log "preflight passed"
}

worker() {
  cd "$PROJECT_ROOT"
  log "Q4 worker start: run_id=$RUN_ID specs=$STUDENT_SPECS seeds=$SEEDS"

  for seed in $SEEDS; do
    local outdir="$RUN_DIR/seed_${seed}"
    mkdir -p "$outdir"
    atomic_status running "seed_${seed}" "training matched students"
    python3 -m torch.distributed.run \
      --standalone \
      --nnodes=1 \
      --nproc_per_node="$NPROC_PER_NODE" \
      experiments/mwg_quality_distillation.py \
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
      --activation-seq "$ACTIVATION_SEED" \
      --activation-seed "$ACTIVATION_SEED" \
      --factor-seed "$FACTOR_SEED" \
      --dtype "$DTYPE" \
      --seed "$seed" \
      --save-students \
      --checkpoint-every "$CHECKPOINT_EVERY" \
      --resume auto \
      --cache-dir "$RUN_DIR/cache" \
      --progress-json "$outdir/progress.json" \
      --outdir "$outdir" \
      >> "$LOG" 2>&1
    log "seed ${seed}: training done"

    # ---- Latency phase: the SAME trained checkpoints through the benchmark.
    atomic_status running "seed_${seed}" "measuring trained-artifact latency"
    local ck
    for ck in persistent_low_rank_r"${BASE_RANK}" persistent_low_rank_r"${MATCHED_RANK}" \
              mwg_token_diag_core_r"${BASE_RANK}" mwg_block_givens_r"${BASE_RANK}"; do
      local ckpt="$outdir/checkpoints/${ck}.pt"
      [[ -s "$ckpt" ]] || { log "seed ${seed}: checkpoint absent, skipping: $ck"; continue; }
      # The benchmark's --rank must match the checkpoint's trained rank.
      local ck_rank="$BASE_RANK"
      if [[ "$ck" == persistent_low_rank_r"${MATCHED_RANK}" ]]; then ck_rank="$MATCHED_RANK"; fi
      # Arms follow the checkpoint's trained mechanism: block_givens
      # checkpoints have no token_diag_core controller, so the materialized
      # arm is replaced by the block_givens arm (the trained mechanism).
      local arms="dense,persistent,materialized"
      if [[ "$ck" == mwg_block_givens_r* ]]; then arms="dense,persistent,block_givens"; fi
      if [[ -n "$V1_OP_LIBRARY" && -s "$V1_OP_LIBRARY" ]] && [[ "$ck" != mwg_block_givens_r* ]]; then arms="$arms,fused"; fi
      if [[ -n "$V4_OP_LIBRARY" && -s "$V4_OP_LIBRARY" ]] && [[ "$ck" != mwg_block_givens_r* ]]; then arms="$arms,fused_v4"; fi
      local extra=()
      if [[ -n "$V1_OP_LIBRARY" ]]; then extra+=(--op-library "$V1_OP_LIBRARY"); fi
      if [[ -n "$V4_OP_LIBRARY" ]]; then extra+=(--v4-op-library "$V4_OP_LIBRARY"); fi
      python3 experiments/mwg_four_arm_lifetime_benchmark.py \
        --d "$BENCH_D" \
        --m "$BENCH_M" \
        --rank "$ck_rank" \
        --controller-hidden 384 \
        --batch 1 \
        --seq "$BENCH_SEQ" \
        --amplitude 0.05 \
        --dtype "$BENCH_DTYPE" \
        --arms "$arms" \
        --device auto \
        --warmup "$BENCH_WARMUP" \
        --iters "$BENCH_ITERS" \
        --repeats "$BENCH_REPEATS" \
        --trained-checkpoint "$ckpt" \
        --run-label "q4_${RUN_ID}_seed_${seed}_${ck}" \
        "${extra[@]}" \
        --output "$outdir/latency_${ck}.json" \
        >> "$LOG" 2>&1 || log "seed ${seed}: latency run failed for $ck (recorded, not fatal)"
      log "seed ${seed}: latency measured for $ck (arms: $arms)"
    done

    # ---- PPL phase: held-out patched-model perplexity of the same artifact.
    # One patched-model eval per student (the eval patches layer 16's MLP
    # with the trained student and computes held-out perplexity).
    atomic_status running "seed_${seed}" "held-out perplexity"
    local student_tag
    for student_tag in persistent_low_rank_r"${BASE_RANK}" \
                       mwg_token_diag_core_r"${BASE_RANK}" \
                       mwg_block_givens_r"${BASE_RANK}"; do
      local ckpt="$outdir/checkpoints/${student_tag}.pt"
      [[ -s "$ckpt" ]] || { log "seed ${seed}: ppl checkpoint absent, skipping: $student_tag"; continue; }
      python3 experiments/mwg_ppl_patch_eval.py \
        --model-dir "$MODEL_DIR" \
        --patch "${LAYER}:${ckpt}" \
        --texts "$EVAL_TEXTS" \
        --require-texts \
        --out-json "$outdir/ppl_${student_tag}.json" \
        >> "$LOG" 2>&1 || log "seed ${seed}: ppl patch eval failed for $student_tag (recorded, not fatal)"
      log "seed ${seed}: ppl patch done for $student_tag"
    done
    log "seed ${seed}: ppl patch done"
    atomic_status running "seed_${seed}" "done"
  done

  # ---- Aggregate: quality + latency + ppl per student, seeds pooled.
  atomic_status running "aggregate" "summarizing quality/latency/ppl"
  python3 - "$RUN_DIR" $SEEDS <<'PY' >> "$LOG" 2>&1
import json, statistics, sys
from pathlib import Path

run_dir = Path(sys.argv[1])
seeds = sys.argv[2:]
rows = []
for seed in seeds:
    seed_dir = run_dir / f"seed_{seed}"
    reports = sorted(seed_dir.glob("mwg_quality_distillation_*.json"))
    if not reports:
        continue
    d = json.loads(reports[0].read_text())
    for key, cell in d.get("results", {}).items():
        if key == "dense_teacher":
            continue
        metrics = cell.get("metrics", {})
        rows.append({
            "seed": int(seed),
            "student": key,
            "relative_mse": metrics.get("relative_mse"),
        })
    for lat in sorted(seed_dir.glob("latency_*.json")):
        dd = json.loads(lat.read_text())
        student = lat.stem.replace("latency_", "")
        arms = dd.get("arms", {})
        row = {"seed": int(seed), "student": student, "latency_ms": {}}
        for arm, res in arms.items():
            row["latency_ms"][arm] = res.get("timing", {}).get("median_ms")
        row["trained_checkpoint_sha256"] = (dd.get("trained_checkpoint") or {}).get("sha256")
        rows.append(row)
    for ppl_path in sorted(seed_dir.glob("ppl_*.json")):
        ppl = json.loads(ppl_path.read_text())
        student = ppl_path.stem.replace("ppl_", "")
        patches = ppl.get("patches") or {}
        patch = next(iter(patches.values()), {})
        rows.append({
            "seed": int(seed),
            "student": f"ppl:{student}",
            "dense_ppl": (ppl.get("dense") or {}).get("ppl"),
            "patched_ppl": (ppl.get("patched") or {}).get("ppl"),
            "patched_student": patch.get("student"),
        })
out = run_dir / "q4_summary.json"
out.write_text(json.dumps({"run_id": run_dir.name, "rows": rows}, indent=2) + "\n")
print("wrote", out)
PY
  atomic_status done "aggregate" "complete"
  log "Q4 worker complete"
}

case "${1:-}" in
  --check) preflight ;;
  --worker) worker ;;
  *)
    preflight
    exec bash "$0" --worker
    ;;
esac
