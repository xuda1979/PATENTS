#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/workspace/software/6_MWG-EW_Meta-Weight_Generation/research_paper_mwg_ew_transformer}"
OUTDIR="${OUTDIR:-$PROJECT_ROOT/results/asi1_quality_distillation}"
MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"
DEVICES="${ASCEND_RT_VISIBLE_DEVICES:-0,1,2,3,4,5,6,7}"
NPROC="${NPROC_PER_NODE:-8}"

export ASCEND_RT_VISIBLE_DEVICES="$DEVICES"
export PYTORCH_NPU_ALLOC_CONF="${PYTORCH_NPU_ALLOC_CONF:-max_split_size_mb:256}"
export HCCL_CONNECT_TIMEOUT="${HCCL_CONNECT_TIMEOUT:-1800}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"

cd "$PROJECT_ROOT"
mkdir -p "$OUTDIR"

TEXT_ARGS=()
if [[ -n "${TEXTS:-}" ]]; then
  TEXT_ARGS=(--texts "$TEXTS")
elif [[ -n "${REQUIRE_TEXTS:-}" ]]; then
  echo "ERROR: TEXTS is required when REQUIRE_TEXTS is set; refusing default text activation capture." >&2
  exit 2
fi

python3 -m torch.distributed.run \
  --nproc_per_node="$NPROC" \
  experiments/mwg_quality_distillation.py \
  --model-dir "$MODEL_DIR" \
  --layer "${LAYER:-0}" \
  --ranks "${RANKS:-128,256,512}" \
  --batch "${BATCH:-1}" \
  --seq "${SEQ:-64}" \
  --steps "${STEPS:-240}" \
  --eval-batches "${EVAL_BATCHES:-24}" \
  --log-every "${LOG_EVERY:-40}" \
  --lr "${LR:-0.0002}" \
  --students "${STUDENTS:-persistent,rank_scale,token_residual}" \
  --residual-rank "${RESIDUAL_RANK:-16}" \
  --scale-amplitude "${SCALE_AMPLITUDE:-0.08}" \
  --basis-count "${BASIS_COUNT:-4}" \
  --basis-noise "${BASIS_NOISE:-0.01}" \
  --activation-source "${ACTIVATION_SOURCE:-gaussian}" \
  --activation-max-batches "${ACTIVATION_MAX_BATCHES:-32}" \
  --activation-text-batch "${ACTIVATION_TEXT_BATCH:-2}" \
  --activation-seq "${ACTIVATION_SEQ:-256}" \
  --dtype "${DTYPE:-fp32}" \
  --outdir "$OUTDIR" \
  "${TEXT_ARGS[@]}" \
  ${SAVE_STUDENTS:+--save-students}
