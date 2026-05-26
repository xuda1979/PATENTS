#!/usr/bin/env bash
set -euo pipefail

export S3_ENDPOINT="${S3_ENDPOINT:-https://iner.aihuanxin.cn}"
export S3_BUCKET="${S3_BUCKET:-jtdlp-21b4208dde424e96b159362ef49c9c96}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
export PROJECT_ROOT="${PROJECT_ROOT:-/workspace/software/6_MWG-EW_Meta-Weight_Generation/research_paper_mwg_ew_transformer}"
export S3_CODE_ROOT="${S3_CODE_ROOT:-iner-aihuanxin:${S3_BUCKET}/software/6_MWG-EW_Meta-Weight_Generation/research_paper_mwg_ew_transformer}"

export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-OXF5ar4y}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-tSd2jD1eRx}"

mkdir -p "$HOME/.config/rclone" "$PROJECT_ROOT"
cat > "$HOME/.config/rclone/rclone.conf" <<EOF
[iner-aihuanxin]
type = s3
provider = Other
access_key_id = ${AWS_ACCESS_KEY_ID}
secret_access_key = ${AWS_SECRET_ACCESS_KEY}
endpoint = ${S3_ENDPOINT}
region = ${AWS_DEFAULT_REGION}
acl = private
EOF

rclone sync "$S3_CODE_ROOT" "$PROJECT_ROOT" \
  --exclude "__pycache__/**" \
  --exclude ".pytest_cache/**" \
  --exclude "*.pyc" \
  --exclude "node_modules/**" \
  --exclude ".venv/**" \
  --exclude "venv/**" \
  --exclude "logs/**" \
  --exclude "*.pt" \
  --exclude "*.pth" \
  --exclude "*.bin" \
  --exclude "*.safetensors" \
  --exclude "*.ckpt" \
  --s3-no-check-bucket \
  --progress

chmod +x "$PROJECT_ROOT"/scripts/*.sh || true

cd "$PROJECT_ROOT"
export ASCEND_RT_VISIBLE_DEVICES="${ASCEND_RT_VISIBLE_DEVICES:-0,1,2,3,4,5,6,7}"
export NPROC_PER_NODE="${NPROC_PER_NODE:-8}"
export MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"
export RANKS="${RANKS:-128,256,512}"
export STEPS="${STEPS:-240}"
export EVAL_BATCHES="${EVAL_BATCHES:-24}"
export BATCH="${BATCH:-1}"
export SEQ="${SEQ:-64}"
export LR="${LR:-0.0002}"
export STUDENTS="${STUDENTS:-persistent,rank_scale,token_residual}"
export RESIDUAL_RANK="${RESIDUAL_RANK:-16}"
export DTYPE="${DTYPE:-fp32}"

RUN_TAG="$(date -u +%Y%m%dT%H%M%SZ)"
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR" "$PROJECT_ROOT/results/asi1_quality_distillation"

bash "$PROJECT_ROOT/scripts/run_asi1_quality_distillation.sh" 2>&1 | tee "$LOG_DIR/asi1_quality_${RUN_TAG}.log"

rclone copy "$PROJECT_ROOT/results/asi1_quality_distillation" \
  "iner-aihuanxin:${S3_BUCKET}/software/6_MWG-EW_Meta-Weight_Generation/research_paper_mwg_ew_transformer/results/asi1_quality_distillation" \
  --s3-no-check-bucket \
  --progress
rclone copy "$LOG_DIR/asi1_quality_${RUN_TAG}.log" \
  "iner-aihuanxin:${S3_BUCKET}/software/6_MWG-EW_Meta-Weight_Generation/research_paper_mwg_ew_transformer/logs" \
  --s3-no-check-bucket \
  --progress

echo "ASI1 quality experiment complete: ${RUN_TAG}"
