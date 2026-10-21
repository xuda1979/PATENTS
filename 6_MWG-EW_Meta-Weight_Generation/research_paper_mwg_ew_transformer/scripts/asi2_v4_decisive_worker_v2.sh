#!/usr/bin/env bash
# Decisive v4-vs-v1 benchmark worker v2 for ASI2 (2026-10-08).
#
# Identical to asi2_v4_decisive_worker.sh except:
#   1. runs the HARDENED test_v4_multicore_v2.py (H1 gated ref,
#      H2 NaN attribution, H3 per-config retry; abort only on
#      persistent op-attributed failure)
#   2. 60s settle sleep after the rebuild, before the test (all 3
#      T512-NaN aborts occurred <60s after a heavy v4 rebuild; the
#      8 isolated probes that all passed ran hours after builds)
#   3. output/log names suffixed _v2
# Same source-verification gates, same CMake rebuild, same binary
# checks. Runs on ASI2 detached via nohup.
set -uo pipefail
PROJECT_ROOT=/root/work/filestorage/mwg-ew-transformer-research
RUN_LOG="$PROJECT_ROOT/results/v4_asi2_decisive_v2_20261008.log"
SRC_FIXED="$PROJECT_ROOT/custom_ops/ephemeral_core_apply/torch_ext/v4_multicore/ephemeral_core_apply_v4_multicore.asc"
SRC_V1="$PROJECT_ROOT/custom_ops/ephemeral_core_apply/torch_ext/ephemeral_core_apply.asc"
TEST_PY=/tmp/test_v4_multicore_v2.py
CMAKE_V4="$PROJECT_ROOT/custom_ops/ephemeral_core_apply/torch_ext/CMakeLists_v4.txt"
V4_EXT=/root/work/mwg_v4_torch_ext
V1_EXT=/root/work/mwg_torch_ext
V1_SO="$V1_EXT/build/libcustom_ops.so"
V4_SO="$V4_EXT/build/libcustom_ops_v4.so"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$RUN_LOG"; }

# --- Gate 1: device free ---
if pgrep -f 'qwen_sft|torchrun' >/dev/null; then
  log "TRAINER_RUNNING: aborting"
  exit 4
fi
NPU_PROCS=$(npu-smi info 2>/dev/null | grep -c 'python\|torchrun' || true)
if [ "$NPU_PROCS" -gt 0 ]; then
  log "NPU_BUSY: $NPU_PROCS tenant processes; aborting"
  exit 4
fi
log "device-gate: no trainer/tenant processes detected"

# --- Gate 2: fixed sources present and correct ---
SRC_MD5=$(md5sum "$SRC_FIXED" 2>/dev/null | awk '{print $1}')
if [ "$SRC_MD5" != "701e9be098b51b13ac89409384735e2d" ]; then
  log "SRC_MD5_MISMATCH: got $SRC_MD5, expected 701e9be0...; aborting"
  exit 5
fi
log "fixed v4 source verified: $SRC_MD5"
V1_MD5=$(md5sum "$SRC_V1" 2>/dev/null | awk '{print $1}')
if [ "$V1_MD5" != "59cf1751d920f5f90851b117f7483d6c" ]; then
  log "V1_SRC_MD5_MISMATCH: got $V1_MD5, expected 59cf1751...; aborting"
  exit 5
fi
log "v1 baseline verified (source $V1_MD5, $V1_SO)"

# --- Step 1: stage the ext dir from the verified fixed sources ---
mkdir -p "$V4_EXT"
cp "$CMAKE_V4" "$V4_EXT/CMakeLists.txt"
cp "$SRC_FIXED" "$V4_EXT/ephemeral_core_apply_v4_multicore.asc"
log "staged $V4_EXT from fixed sources"

# --- Step 2: rebuild via the proven CMake/ASC flow ---
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || true
cd "$V4_EXT"
log "cmake configure"
rm -rf build && mkdir -p build && cd build
cmake .. > cmake_v4.log 2>&1
CMAKE_RC=$?
log "cmake rc=$CMAKE_RC"
if [ "$CMAKE_RC" -ne 0 ]; then
  log "CMAKE_FAILED"
  exit 6
fi
log "make"
make -j"$(nproc)" > make_v4.log 2>&1
MAKE_RC=$?
log "make rc=$MAKE_RC"
if [ "$MAKE_RC" -ne 0 ]; then
  log "MAKE_FAILED"
  exit 6
fi
log "V4_SO=$V4_SO"
WARMUP_STRS=$(strings "$V4_SO" | grep -c "warmup failed to converge" || true)
log "warmup-fix string count in v4 .so: $WARMUP_STRS"
if [ "$WARMUP_STRS" -lt 1 ]; then
  log "WARMUP_FIX_MISSING_IN_BINARY: rebuilt .so lacks the verified-warmup probe; aborting"
  exit 6
fi

# --- Step 2.5 (v2): settle after rebuild ---
log "settling 60s post-build"
sleep 60

# --- Step 3: run the hardened decisive v4-vs-v1 comparison ---
cd "$PROJECT_ROOT"
log "running test_v4_multicore_v2.py"
python3 "$TEST_PY" \
    --op-library "$V4_SO" \
    --v1-library "$V1_SO" \
    --output "$PROJECT_ROOT/results/v4_multicore_benchmark_asi2_v2_20261008.json" \
    --warmup 30 --iters 200 --repeats 5 \
    >> "$RUN_LOG" 2>&1
TEST_RC=$?
log "test rc=$TEST_RC"

log "=== v4 ASI2 decisive worker v2 done ==="
