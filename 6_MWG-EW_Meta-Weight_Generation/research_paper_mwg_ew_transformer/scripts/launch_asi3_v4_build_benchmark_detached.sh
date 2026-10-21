#!/usr/bin/env bash
# Detached ASI3 v4 build+benchmark launcher.
#
# Runs ON ASI3 (via scripts/ASI3_shell.sh).  Because the ASI3 daemon file
# channel times out long-running commands, this launcher starts the real
# work with nohup and returns immediately; progress is appended to the
# log file and the run's status can be polled separately.
#
# Prerequisites (already on ASI3):
#   /root/work/filestorage/rclone-bin           - rclone binary
#   /root/work/filestorage/mwg-ew-transformer-research - research tree
#   /root/work/mwg_torch_ext/build/libcustom_ops.so    - v1 .so (baseline)
#
# Usage:
#   bash scripts/launch_asi3_v4_build_benchmark_detached.sh
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/work/filestorage/mwg-ew-transformer-research}"
RCLONE_BIN="${RCLONE_BIN:-/root/work/filestorage/rclone-bin}"
RUN_LOG="${RUN_LOG:-$PROJECT_ROOT/results/v4_asi3_run.log}"
RUN_ID="v4_asi3_$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "$PROJECT_ROOT/results"

# S3 credentials via env-var remote (name: iner_aihuanxin)
export RCLONE_CONFIG_INER_AIHUANXIN_TYPE=s3
export RCLONE_CONFIG_INER_AIHUANXIN_PROVIDER=Other
export RCLONE_CONFIG_INER_AIHUANXIN_ACCESS_KEY_ID="${MWG_S3_ACCESS_KEY_ID:-OXF5ar4y}"
export RCLONE_CONFIG_INER_AIHUANXIN_SECRET_ACCESS_KEY="${MWG_S3_SECRET_ACCESS_KEY:-tSd2jD1eRx}"
export RCLONE_CONFIG_INER_AIHUANXIN_ENDPOINT="${MWG_S3_ENDPOINT:-https://iner.aihuanxin.cn}"

S3_TORCH_EXT='iner_aihuanxin:jtdlp-21b4208dde424e96b159362ef49c9c96/mwg-ew-patent/research_paper_mwg_ew_transformer/custom_ops/ephemeral_core_apply/torch_ext'

cat > /tmp/mwg_v4_worker.sh <<'WORKER'
#!/usr/bin/env bash
set -uo pipefail
PROJECT_ROOT="__PROJECT_ROOT__"
RCLONE_BIN="__RCLONE_BIN__"
RUN_LOG="__RUN_LOG__"
S3_TORCH_EXT="__S3_TORCH_EXT__"
export RCLONE_CONFIG_INER_AIHUANXIN_TYPE=s3
export RCLONE_CONFIG_INER_AIHUANXIN_PROVIDER=Other
export RCLONE_CONFIG_INER_AIHUANXIN_ACCESS_KEY_ID="__S3_AK__"
export RCLONE_CONFIG_INER_AIHUANXIN_SECRET_ACCESS_KEY="__S3_SK__"
export RCLONE_CONFIG_INER_AIHUANXIN_ENDPOINT="__S3_EP__"

log() { echo "[$(date -u +%FT%TZ)] $*" >> "$RUN_LOG"; }

log "=== v4 ASI3 worker start ==="

# --- Step 0: refuse to run against a contended/wedged device ---
# Evidence: the 2026-09-29 16:26 run's shipped-v1 control returned NaN
# while a qwen SFT trainer held the NPU; v4 was blamed for the resulting
# aicore timeout.  Gate on the trainer and on npu-smi process count.
if pgrep -f 'qwen_sft_peft|torchrun.*qwen_sft' >/dev/null; then
  log "TRAINER_RUNNING: qwen SFT holds the NPU; aborting before launch"
  exit 4
fi
NPU_PROCS=$(npu-smi info 2>/dev/null | grep -c 'python\|torchrun' || true)
if [ "$NPU_PROCS" -gt 0 ]; then
  log "NPU_BUSY: $NPU_PROCS tenant processes on device; aborting before launch"
  exit 4
fi
log "device-gate: no trainer/tenant processes detected"

# --- Step 1: pull the fixed v4 sources from S3 ---
cd "$PROJECT_ROOT"
DST=custom_ops/ephemeral_core_apply/torch_ext
log "pulling v4 sources from S3"
"$RCLONE_BIN" copy "$S3_TORCH_EXT/v4_multicore/" "$DST/v4_multicore/" \
    --s3-no-check-bucket >> "$RUN_LOG" 2>&1
log "v4_multicore pull rc=$?"
"$RCLONE_BIN" copy "$S3_TORCH_EXT/CMakeLists_v4.txt" "$DST/" \
    --s3-no-check-bucket >> "$RUN_LOG" 2>&1
log "CMakeLists_v4 pull rc=$?"
md5sum "$DST"/v4_multicore/ephemeral_core_apply_v4_multicore.asc \
       "$DST"/v4_multicore/test_v4_multicore.py \
       "$DST"/CMakeLists_v4.txt >> "$RUN_LOG" 2>&1

# --- Step 2: build via the proven CMake/ASC flow ---
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || true
V4_EXT=/root/work/mwg_v4_torch_ext
rm -rf "$V4_EXT"; mkdir -p "$V4_EXT"
cp "$DST/CMakeLists_v4.txt" "$V4_EXT/CMakeLists.txt"
cp "$DST/v4_multicore/ephemeral_core_apply_v4_multicore.asc" "$V4_EXT/"
log "cmake configure"
cd "$V4_EXT"
rm -rf build && mkdir -p build && cd build
cmake .. > cmake_v4.log 2>&1; CMAKE_RC=$?
log "cmake rc=$CMAKE_RC"
tail -15 cmake_v4.log >> "$RUN_LOG" 2>&1
[ "$CMAKE_RC" -ne 0 ] && { log "CMAKE FAILED"; exit 1; }
make > make_v4.log 2>&1; MAKE_RC=$?
log "make rc=$MAKE_RC"
tail -40 make_v4.log >> "$RUN_LOG" 2>&1
[ "$MAKE_RC" -ne 0 ] && { log "MAKE FAILED"; exit 1; }

V4_SO=$(find "$V4_EXT/build" -name '*.so' -type f | head -1)
V1_SO=/root/work/mwg_torch_ext/build/libcustom_ops.so
log "V4_SO=$V4_SO"
log "V1_SO=$V1_SO"
[ -z "$V4_SO" ] && { log "NO .so FOUND"; exit 1; }

# --- Step 3: run the v4-vs-v1 comparison + stability test ---
cd "$PROJECT_ROOT"
log "running test_v4_multicore.py"
python3 custom_ops/ephemeral_core_apply/torch_ext/v4_multicore/test_v4_multicore.py \
    --op-library "$V4_SO" \
    --v1-library "$V1_SO" \
    --output results/v4_multicore_benchmark.json \
    --warmup 30 --iters 200 --repeats 5 \
    >> "$RUN_LOG" 2>&1
log "test rc=$?"

log "=== v4 ASI3 worker done ==="
WORKER

sed -i \
    -e "s|__PROJECT_ROOT__|$PROJECT_ROOT|g" \
    -e "s|__RCLONE_BIN__|$RCLONE_BIN|g" \
    -e "s|__RUN_LOG__|$RUN_LOG|g" \
    -e "s|__S3_TORCH_EXT__|$S3_TORCH_EXT|g" \
    -e "s|__S3_AK__|${MWG_S3_ACCESS_KEY_ID:-OXF5ar4y}|g" \
    -e "s|__S3_SK__|${MWG_S3_SECRET_ACCESS_KEY:-tSd2jD1eRx}|g" \
    -e "s|__S3_EP__|${MWG_S3_ENDPOINT:-https://iner.aihuanxin.cn}|g" \
    /tmp/mwg_v4_worker.sh
chmod +x /tmp/mwg_v4_worker.sh

echo "=== v4 ASI3 launcher: starting detached worker (log: $RUN_LOG) ===" | tee -a "$RUN_LOG"
nohup bash /tmp/mwg_v4_worker.sh >> "$RUN_LOG" 2>&1 &
WORKER_PID=$!
echo "worker pid=$WORKER_PID run_id=$RUN_ID"
echo "$RUN_ID" > "$PROJECT_ROOT/results/v4_asi3_run_id.txt"
