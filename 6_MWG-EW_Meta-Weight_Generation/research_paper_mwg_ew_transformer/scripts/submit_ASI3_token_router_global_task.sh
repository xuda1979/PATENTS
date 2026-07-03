#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_NAME="${HUANXIN_ASI3_ENV:-ASI3}"
TRAIN_DEV_URL="${HUANXIN_ASI3_URL:-https://aihuanxin.cn/kunlun/kl-web?poolId=6&projectId=21b4208dde424e96b159362ef49c9c96#/train-dev/environment/dl-c72bd81a96e33134bbe0ae4a478fbab0?name=ASI3}"
TASK_NAME="${HUANXIN_ASI3_TASK_NAME:-asi3-router-0606a}"
IMAGE_NAME="${HUANXIN_ASI3_IMAGE_NAME:-qwen3.5-27B-35B-122B-397B-031626-zx}"
RESOURCE_GROUP="${HUANXIN_ASI3_RESOURCE_GROUP:-huanxin-all-resource}"
RESOURCE_GROUP_TYPE="${HUANXIN_ASI3_RESOURCE_GROUP_TYPE:-公共资源组}"
INSTANCE_COUNT="${HUANXIN_ASI3_INSTANCE_COUNT:-1}"
ACCELERATOR_CARDS="${HUANXIN_ASI3_ACCELERATOR_CARDS:-2}"
CPU_CORES="${HUANXIN_ASI3_CPU_CORES:-40}"
MEMORY_GB="${HUANXIN_ASI3_MEMORY_GB:-480}"
WAIT_MS="${HUANXIN_ASI3_WAIT_MS:-15000}"
ARTIFACT_STEM="${HUANXIN_ASI3_ARTIFACT_STEM:-asi3-token-router-global-0606a}"
REMOTE_ROOT="${HUANXIN_ASI3_REMOTE_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
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
S3_ENDPOINT="${S3_ENDPOINT:-https://iner.aihuanxin.cn}"
S3_BUCKET="${S3_BUCKET:-jtdlp-21b4208dde424e96b159362ef49c9c96}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
if [[ -z "${AWS_ACCESS_KEY_ID:-}" || -z "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
  RCLONE_CONFIG_FILE="${RCLONE_CONFIG_FILE:-$(rclone config file 2>/dev/null | awk 'NF {line=$0} END {print line}')}"
  read -r AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY < <(
    python3 - "$RCLONE_CONFIG_FILE" <<'PY'
import configparser
import sys

config_path = sys.argv[1]
parser = configparser.ConfigParser(interpolation=None)
parser.read(config_path)
section = "iner-aihuanxin"
if section not in parser:
    raise SystemExit(f"missing rclone remote: {section}")
access_key = parser[section].get("access_key_id", "").strip()
secret_key = parser[section].get("secret_access_key", "").strip()
if not access_key or not secret_key:
    raise SystemExit(f"missing S3 credentials in rclone remote: {section}")
print(access_key, secret_key)
PY
  )
fi
AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID must be set in the environment or rclone config}"
AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY must be set in the environment or rclone config}"
S3_CODE_ROOT="${HUANXIN_ASI3_S3_CODE_ROOT:-iner-aihuanxin:${S3_BUCKET}/mwg-ew-patent/research_paper_mwg_ew_transformer}"
PRINT_ONLY=0
SUBMIT=0
DIRECT_ONLY=1

usage() {
  cat <<'EOF'
Usage:
  scripts/submit_ASI3_token_router_global_task.sh [--submit] [--dry-run] [--task-name <name>]
EOF
}

render_launch_spec() {
  python3 - <<'PY' \
    "$ENV_NAME" \
    "$REMOTE_ROOT" \
    "$S3_ENDPOINT" \
    "$S3_BUCKET" \
    "$AWS_DEFAULT_REGION" \
    "$AWS_ACCESS_KEY_ID" \
    "$AWS_SECRET_ACCESS_KEY" \
    "$S3_CODE_ROOT" \
    "$PATCH" \
    "$SPLIT_MANIFEST" \
    "$FRACTIONS" \
    "$JOINT_BUDGETS" \
    "$THRESHOLD_POLICY" \
    "$RISK_MAX_PREDICTED_DELTA" \
    "$TRAIN_EXAMPLES" \
    "$EVAL_EXAMPLES" \
    "$SEQ" \
    "$SEEDS"
import json
import base64
import shlex
import sys
import urllib.parse

(
    env_name,
    remote_root,
    s3_endpoint,
    s3_bucket,
    aws_default_region,
    aws_access_key_id,
    aws_secret_access_key,
    s3_code_root,
    patch,
    split_manifest,
    fractions,
    joint_budgets,
    threshold_policy,
    risk_max_predicted_delta,
    train_examples,
    eval_examples,
    seq,
    seeds,
) = sys.argv[1:19]

artifact_prefix = (
    f"iner-aihuanxin:{s3_bucket}/mwg-ew-patent/"
    "research_paper_mwg_ew_transformer/results/asi3_token_router_global_task_artifacts"
)

payload_commands = [
    "set -euo pipefail",
    "umask 077",
    "echo __ASI3_TASK_COMMAND_BOOT__",
    "printf '%s\\n' '[iner-aihuanxin]' 'type = s3' 'provider = Other' "
    + shlex.quote("access_key_id = " + aws_access_key_id)
    + " "
    + shlex.quote("secret_access_key = " + aws_secret_access_key)
    + " "
    + shlex.quote("endpoint = " + s3_endpoint)
    + " "
    + shlex.quote("region = " + aws_default_region)
    + " 'acl = private' 'force_path_style = true' > /tmp/iner-rclone.conf",
    'if ! command -v rclone >/dev/null 2>&1; then if [ -f /root/work/filestorage/rclone-bin ]; then cp /root/work/filestorage/rclone-bin /tmp/rclone && chmod 700 /tmp/rclone && export PATH=/tmp:$PATH; elif [ -f /vllm-workspace/mwg-ew-transformer-research/tools/preseed/rclone-linux-arm64 ]; then cp /vllm-workspace/mwg-ew-transformer-research/tools/preseed/rclone-linux-arm64 /tmp/rclone && chmod 700 /tmp/rclone && export PATH=/tmp:$PATH; elif command -v curl >/dev/null 2>&1 && command -v python3 >/dev/null 2>&1; then d=$(mktemp -d /tmp/rclone.XXXXXX) && curl -fsSL --retry 3 https://downloads.rclone.org/rclone-current-linux-arm64.zip -o $d/rclone.zip && python3 -m zipfile -e $d/rclone.zip $d/x && f=$(find $d/x -type f -name rclone | head -1) && cp $f /tmp/rclone && chmod 700 /tmp/rclone && export PATH=/tmp:$PATH; fi; fi; command -v rclone >/dev/null',
    f"rclone --config /tmp/iner-rclone.conf copyto {shlex.quote(s3_code_root + '/scripts/remote_ASI3_token_router_global_payload.sh')} /tmp/remote_ASI3_token_router_global_payload.sh --s3-no-check-bucket --progress",
    "chmod 700 /tmp/remote_ASI3_token_router_global_payload.sh",
    f"HUANXIN_ASI3_ENV={shlex.quote(env_name)} HUANXIN_ASI3_REMOTE_ROOT={shlex.quote(remote_root)} HUANXIN_ASI3_S3_CODE_ROOT={shlex.quote(s3_code_root)} HUANXIN_ASI3_ARTIFACT_PREFIX={shlex.quote(artifact_prefix)} HUANXIN_ASI3_RCLONE_CONFIG=/tmp/iner-rclone.conf ASCEND_RT_VISIBLE_DEVICES='0' HUANXIN_ASI3_VISIBLE_DEVICES='0' HUANXIN_ASI3_ROUTER_PATCH={shlex.quote(patch)} HUANXIN_ASI3_ROUTER_SPLIT_MANIFEST={shlex.quote(split_manifest)} HUANXIN_ASI3_ROUTER_FRACTIONS={shlex.quote(fractions)} HUANXIN_ASI3_ROUTER_JOINT_BUDGETS={shlex.quote(joint_budgets)} HUANXIN_ASI3_ROUTER_THRESHOLD_POLICY={shlex.quote(threshold_policy)} HUANXIN_ASI3_ROUTER_RISK_MAX_PREDICTED_DELTA={shlex.quote(risk_max_predicted_delta)} HUANXIN_ASI3_ROUTER_TRAIN_EXAMPLES={shlex.quote(train_examples)} HUANXIN_ASI3_ROUTER_EVAL_EXAMPLES={shlex.quote(eval_examples)} HUANXIN_ASI3_ROUTER_SEQ={shlex.quote(seq)} HUANXIN_ASI3_ROUTER_SEEDS={shlex.quote(seeds)} bash /tmp/remote_ASI3_token_router_global_payload.sh",
]
commands = payload_commands
execution_command = "\n".join(commands)
print(
    json.dumps(
        {
            "remote_root": remote_root,
            "output_dir": "",
            "log_path": "",
            "job_name": f"{env_name}-token-router-global",
            "remote_command": " && ".join(commands),
            "execution_command": execution_command,
        },
        indent=2,
    )
)
PY
}

if [[ "${1:-}" == "--dry-run" && "${2:-}" == "__launch-spec" ]]; then
  render_launch_spec
  exit 0
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --submit)
      SUBMIT=1
      shift
      ;;
    --dry-run)
      PRINT_ONLY=1
      shift
      ;;
    --task-name)
      TASK_NAME="${2:-}"
      shift 2
      ;;
    --ui-submit)
      DIRECT_ONLY=0
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

CMD=(
  node
  "$ROOT_DIR/../..//../software/quantum-gpt/browser-automation/huanxin_submit_task_run.js"
  --url "$TRAIN_DEV_URL"
  --wait-ms "$WAIT_MS"
  --task-name "$TASK_NAME"
  --image-name "$IMAGE_NAME"
  --resource-group "$RESOURCE_GROUP"
  --resource-group-type "$RESOURCE_GROUP_TYPE"
  --instance-count "$INSTANCE_COUNT"
  --accelerator-cards "$ACCELERATOR_CARDS"
  --cpu-cores "$CPU_CORES"
  --memory-gb "$MEMORY_GB"
  --remote-root "$REMOTE_ROOT"
  --launcher-script "$ROOT_DIR/scripts/submit_ASI3_token_router_global_task.sh"
  --launcher-arg "__launch-spec"
  --screenshot "$ROOT_DIR/browser-automation/${ARTIFACT_STEM}.png"
  --dump-html "$ROOT_DIR/browser-automation/${ARTIFACT_STEM}.html"
  --dump-json "$ROOT_DIR/browser-automation/${ARTIFACT_STEM}.json"
)

if [[ "$DIRECT_ONLY" == "1" ]]; then
  CMD+=(--direct-submit-only)
fi

if [[ "$SUBMIT" == "1" ]]; then
  CMD+=(--submit)
fi

if [[ "$PRINT_ONLY" == "1" ]]; then
  python3 -c 'import shlex,sys; print(" ".join(shlex.quote(x) for x in sys.argv[1:]))' "${CMD[@]}"
  exit 0
fi

cd "$ROOT_DIR"
exec "${CMD[@]}"
