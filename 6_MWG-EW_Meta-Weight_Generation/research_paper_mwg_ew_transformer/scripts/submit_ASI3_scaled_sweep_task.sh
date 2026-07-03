#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_NAME="${HUANXIN_ASI3_ENV:-ASI3}"
TRAIN_DEV_URL="${HUANXIN_ASI3_URL:-https://aihuanxin.cn/kunlun/kl-web?poolId=6&projectId=21b4208dde424e96b159362ef49c9c96#/train-dev/environment/dl-c72bd81a96e33134bbe0ae4a478fbab0?name=ASI3}"
TASK_NAME="${HUANXIN_ASI3_TASK_NAME:-asi3-mwg-sw0604a}"
IMAGE_NAME="${HUANXIN_ASI3_IMAGE_NAME:-qwen3.5-27B-35B-122B-397B-031626-zx}"
RESOURCE_GROUP="${HUANXIN_ASI3_RESOURCE_GROUP:-huanxin-all-resource}"
RESOURCE_GROUP_TYPE="${HUANXIN_ASI3_RESOURCE_GROUP_TYPE:-公共资源组}"
INSTANCE_COUNT="${HUANXIN_ASI3_INSTANCE_COUNT:-1}"
ACCELERATOR_CARDS="${HUANXIN_ASI3_ACCELERATOR_CARDS:-2}"
CPU_CORES="${HUANXIN_ASI3_CPU_CORES:-160}"
MEMORY_GB="${HUANXIN_ASI3_MEMORY_GB:-1920}"
WAIT_MS="${HUANXIN_ASI3_WAIT_MS:-15000}"
ARTIFACT_STEM="${HUANXIN_ASI3_ARTIFACT_STEM:-asi3-mwg-scaled-sweep-0604a}"
REMOTE_ROOT="${HUANXIN_ASI3_REMOTE_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
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
  scripts/submit_ASI3_scaled_sweep_task.sh [--submit] [--dry-run] [--task-name <name>]
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
    "$S3_CODE_ROOT"
import json
import shlex
import sys

(
    env_name,
    remote_root,
    s3_endpoint,
    s3_bucket,
    aws_default_region,
    aws_access_key_id,
    aws_secret_access_key,
    s3_code_root,
) = sys.argv[1:9]

run_id_var = "${RUN_ID}"
commands = [
    "set -euo pipefail",
    f"echo __{env_name}_MWG_SWEEP_BOOT__",
    "date -u",
    "python3 --version",
    "python3 - <<'PYPROBE'\nimport torch\nimport torch_npu\nprint('torch', torch.__version__)\nprint('torch_npu', getattr(torch_npu, '__version__', 'unknown'))\nprint('npu_count', torch.npu.device_count())\nprint('npu_available', torch.npu.is_available())\nPYPROBE",
    "umask 077",
    "cat > /tmp/iner-rclone.conf <<'__INER_RCLONE_CONF__'\n[iner-aihuanxin]\ntype = s3\nprovider = Other\naccess_key_id = "
    + aws_access_key_id
    + "\nsecret_access_key = "
    + aws_secret_access_key
    + "\nendpoint = "
    + s3_endpoint
    + "\nregion = "
    + aws_default_region
    + "\nacl = private\nforce_path_style = true\n__INER_RCLONE_CONF__",
    "command -v rclone >/dev/null",
    f"mkdir -p {shlex.quote(remote_root)}",
    f"rclone --config /tmp/iner-rclone.conf sync {shlex.quote(s3_code_root)} {shlex.quote(remote_root)} --s3-no-check-bucket --exclude '__pycache__/**' --exclude '.pytest_cache/**' --exclude '*.pyc' --exclude 'logs/**' --exclude 'results/**' --exclude '*.pt' --exclude '*.pth' --exclude '*.bin' --exclude '*.safetensors' --exclude '*.ckpt' --progress",
    f"chmod +x {shlex.quote(remote_root)}/scripts/*.sh || true",
    f"cd {shlex.quote(remote_root)}",
    "mkdir -p logs results",
    f"RUN_ID={shlex.quote(env_name.lower() + '-mwg-sweep-0604a')}-$(date -u +%Y%m%dT%H%M%SZ)",
    "export ASCEND_RT_VISIBLE_DEVICES=0,1",
    "export PYTORCH_NPU_ALLOC_CONF=max_split_size_mb:256",
    "export HCCL_CONNECT_TIMEOUT=1800",
    "export OMP_NUM_THREADS=1",
    "echo run_id=$RUN_ID",
    "bash scripts/run_ASI3_scaled_sweep.sh 2>&1 | tee logs/${RUN_ID}.task.log",
    "mkdir -p results/asi3_scaled_sweep_task_artifacts",
    "cp -f logs/${RUN_ID}.task.log results/asi3_scaled_sweep_task_artifacts/ 2>/dev/null || true",
    "cp -f logs/ASI3_scaled_sweep_*.status.json results/asi3_scaled_sweep_task_artifacts/ 2>/dev/null || true",
    "cp -f results/ASI3_mwg_transformer_*.json results/asi3_scaled_sweep_task_artifacts/ 2>/dev/null || true",
    "rclone --config /tmp/iner-rclone.conf copy results/asi3_scaled_sweep_task_artifacts iner-aihuanxin:"
    + s3_bucket
    + "/mwg-ew-patent/research_paper_mwg_ew_transformer/results/asi3_scaled_sweep_task_artifacts --s3-no-check-bucket --progress || true",
    "echo __"
    + env_name
    + "_MWG_SWEEP_DONE__",
]
execution_command = "\n".join(commands)
print(
    json.dumps(
        {
            "remote_root": remote_root,
            "output_dir": "",
            "log_path": "",
            "job_name": f"{env_name}-mwg-scaled-sweep",
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
  --launcher-script "$ROOT_DIR/scripts/submit_ASI3_scaled_sweep_task.sh"
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
