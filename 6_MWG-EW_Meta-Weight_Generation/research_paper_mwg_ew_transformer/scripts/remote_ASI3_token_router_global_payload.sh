#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="${HUANXIN_ASI3_ENV:-ASI3}"
REMOTE_ROOT="${HUANXIN_ASI3_REMOTE_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
S3_CODE_ROOT="${HUANXIN_ASI3_S3_CODE_ROOT:?HUANXIN_ASI3_S3_CODE_ROOT is required}"
S3_ARTIFACT_PREFIX="${HUANXIN_ASI3_ARTIFACT_PREFIX:?HUANXIN_ASI3_ARTIFACT_PREFIX is required}"
RCLONE_CONFIG_PATH="${HUANXIN_ASI3_RCLONE_CONFIG:-/tmp/iner-rclone.conf}"
PATCH="${HUANXIN_ASI3_ROUTER_PATCH:-$REMOTE_ROOT/results/asi3_layer16_recovery_20260605T085838Z/layer16/checkpoints/mwg_expert_residual_r384_belle_lmce_cal_1200.pt}"
SPLIT_MANIFEST="${HUANXIN_ASI3_ROUTER_SPLIT_MANIFEST:-data/heldout/router_global_splits/manifest.json}"
FRACTIONS="${HUANXIN_ASI3_ROUTER_FRACTIONS:-0.01,0.03,0.05,0.10,0.25,0.50}"
JOINT_BUDGETS="${HUANXIN_ASI3_ROUTER_JOINT_BUDGETS:-0.05,0.10,0.25}"
THRESHOLD_POLICY="${HUANXIN_ASI3_ROUTER_THRESHOLD_POLICY:-suite_min}"
RISK_MAX_PREDICTED_DELTA="${HUANXIN_ASI3_ROUTER_RISK_MAX_PREDICTED_DELTA:-0.0}"
TRAIN_EXAMPLES="${HUANXIN_ASI3_ROUTER_TRAIN_EXAMPLES:-0}"
EVAL_EXAMPLES="${HUANXIN_ASI3_ROUTER_EVAL_EXAMPLES:-0}"
SEQ="${HUANXIN_ASI3_ROUTER_SEQ:-256}"
SEEDS="${HUANXIN_ASI3_ROUTER_SEEDS:-0}"

echo "__${ENV_NAME}_TOKEN_ROUTER_BOOT__"
date -u
umask 077

if ! command -v rclone >/dev/null 2>&1; then
  if [[ -f /root/work/filestorage/rclone-bin ]]; then
    cp /root/work/filestorage/rclone-bin /tmp/rclone
    chmod 700 /tmp/rclone
    export PATH="/tmp:$PATH"
  elif [[ -f "$REMOTE_ROOT/tools/preseed/rclone-linux-arm64" ]]; then
    cp "$REMOTE_ROOT/tools/preseed/rclone-linux-arm64" /tmp/rclone
    chmod 700 /tmp/rclone
    export PATH="/tmp:$PATH"
  elif command -v curl >/dev/null 2>&1 && command -v python3 >/dev/null 2>&1; then
    tmpd="$(mktemp -d /tmp/asi3-rclone.XXXXXX)"
    if curl -fsSL --retry 3 https://downloads.rclone.org/rclone-current-linux-arm64.zip -o "$tmpd/rclone.zip"; then
      python3 -m zipfile -e "$tmpd/rclone.zip" "$tmpd/extract"
      found="$(find "$tmpd/extract" -type f -name rclone | head -n 1)"
      if [[ -n "$found" ]]; then
        cp "$found" /tmp/rclone
        chmod 700 /tmp/rclone
        export PATH="/tmp:$PATH"
      fi
    fi
  fi
fi
command -v rclone >/dev/null
rclone version | head -n 1

mkdir -p "$REMOTE_ROOT"
rclone --config "$RCLONE_CONFIG_PATH" sync "$S3_CODE_ROOT" "$REMOTE_ROOT" \
  --s3-no-check-bucket \
  --exclude "__pycache__/**" \
  --exclude ".pytest_cache/**" \
  --exclude "*.pyc" \
  --exclude "logs/**" \
  --exclude "results/**" \
  --exclude "*.pt" \
  --exclude "*.pth" \
  --exclude "*.bin" \
  --exclude "*.safetensors" \
  --exclude "*.ckpt" \
  --progress

chmod +x "$REMOTE_ROOT"/scripts/*.sh || true
cd "$REMOTE_ROOT"
mkdir -p logs results/asi3_token_router_global_task_artifacts

RUN_ID="asi3-token-router-global-task-$(date -u +%Y%m%dT%H%M%SZ)"
export RUN_ID
python3 - <<'PYBOOT' > "results/asi3_token_router_global_task_artifacts/${RUN_ID}.boot.json"
import json, os
from datetime import datetime, timezone
print(json.dumps({
    "run_id": os.environ.get("RUN_ID", ""),
    "event": "boot",
    "state": "remote_payload_started",
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}))
PYBOOT
rclone --config "$RCLONE_CONFIG_PATH" copy results/asi3_token_router_global_task_artifacts "$S3_ARTIFACT_PREFIX" --s3-no-check-bucket --progress || true

python3 - <<'PYPROBE'
import torch
import torch_npu
print("torch " + str(torch.__version__))
print("torch_npu " + str(getattr(torch_npu, "__version__", "unknown")))
print("npu_count " + str(torch.npu.device_count()))
print("npu_available " + str(torch.npu.is_available()))
PYPROBE

export ASCEND_RT_VISIBLE_DEVICES="${ASCEND_RT_VISIBLE_DEVICES:-0}"
export PYTORCH_NPU_ALLOC_CONF="${PYTORCH_NPU_ALLOC_CONF:-max_split_size_mb:256}"
export HCCL_CONNECT_TIMEOUT="${HCCL_CONNECT_TIMEOUT:-1800}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"

test -f "$PATCH"
test -f "$SPLIT_MANIFEST"
IFS=, read -r -a seed_array <<< "$SEEDS"
for seed in "${seed_array[@]}"; do
  seed="$(echo "$seed" | xargs)"
  [[ -n "$seed" ]] || continue
  seed_log="logs/${RUN_ID}.seed${seed}.launch.log"
  export ASCEND_RT_VISIBLE_DEVICES="${HUANXIN_ASI3_VISIBLE_DEVICES:-0}"
  RUN_PREFIX="asi3_token_router_global_task_seed${seed}" \
  SPLIT_MANIFEST="$SPLIT_MANIFEST" \
  FRACTIONS="$FRACTIONS" \
  JOINT_BUDGETS="$JOINT_BUDGETS" \
  THRESHOLD_POLICY="$THRESHOLD_POLICY" \
  RISK_MAX_PREDICTED_DELTA="$RISK_MAX_PREDICTED_DELTA" \
  TRAIN_EXAMPLES="$TRAIN_EXAMPLES" \
  EVAL_EXAMPLES="$EVAL_EXAMPLES" \
  SEQ="$SEQ" \
  PATCH="$PATCH" \
  SEED="$seed" \
  bash scripts/launch_asi3_token_router_global_suite_balanced_1npu_detached.sh 2>&1 | tee "$seed_log"

  sleep 5
  STATUS="$(ls -t "logs/asi3_token_router_global_task_seed${seed}_"*.status.json | head -n 1)"
  echo "seed=$seed status=$STATUS"
  cp -f "$STATUS" results/asi3_token_router_global_task_artifacts/ 2>/dev/null || true
  cp -f "$seed_log" results/asi3_token_router_global_task_artifacts/ 2>/dev/null || true
  rclone --config "$RCLONE_CONFIG_PATH" copy results/asi3_token_router_global_task_artifacts "$S3_ARTIFACT_PREFIX" --s3-no-check-bucket --progress || true

  for i in $(seq 1 180); do
    state="$(python3 -c 'import json, sys; data=json.load(open(sys.argv[1])); print(data.get("state") or "")' "$STATUS" 2>/dev/null || true)"
    echo "seed=$seed poll=$i state=$state"
    [[ "$state" == done || "$state" == failed ]] && break
    sleep 20
  done

  cat "$STATUS"
  OUTDIR="$(python3 -c 'import json, sys; data=json.load(open(sys.argv[1])); print(data.get("outdir") or "")' "$STATUS")"
  RESULT="$(python3 -c 'import json, sys; data=json.load(open(sys.argv[1])); print(data.get("result_json") or "")' "$STATUS")"
  cp -f "$STATUS" results/asi3_token_router_global_task_artifacts/ 2>/dev/null || true
  cp -f "$seed_log" results/asi3_token_router_global_task_artifacts/ 2>/dev/null || true
  cp -f logs/asi3_token_router_global_task_seed*.log results/asi3_token_router_global_task_artifacts/ 2>/dev/null || true
  cp -f "$RESULT" "results/asi3_token_router_global_task_artifacts/seed${seed}_token_router_global_suite_balanced.json" 2>/dev/null || true
  if [[ -n "$OUTDIR" ]]; then
    find "$OUTDIR" -maxdepth 2 -type f -name '*.json' -exec cp -f {} results/asi3_token_router_global_task_artifacts/ \; 2>/dev/null || true
  fi
  rclone --config "$RCLONE_CONFIG_PATH" copy results/asi3_token_router_global_task_artifacts "$S3_ARTIFACT_PREFIX" --s3-no-check-bucket --progress || true
done
rclone --config "$RCLONE_CONFIG_PATH" copy results/asi3_token_router_global_task_artifacts "$S3_ARTIFACT_PREFIX" --s3-no-check-bucket --progress || true
echo "__${ENV_NAME}_TOKEN_ROUTER_DONE__"
