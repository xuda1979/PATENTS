#!/usr/bin/env bash
# Decisive v4-vs-v1 benchmark worker for ASI2 (2026-10-08).
#
# Context: the decisive v4-vs-v1 rerun is gated on the 2026-10-02 verified
# warmup fix (v4 source md5 701e9be0..., v1 source md5 59cf1751...).
# The ASI3 detached launcher is unusable for this (chronically-Forbidden S3
# pull from ASI3 silently rebuilt a STALE pre-fix v4 kernel, which then
# aicore-crashed), and ASI3 is reserved for another session's qwen SFT
# trainer.  ASI2 is free and is the canonical host for this benchmark
# (test_v4_multicore.py header: "must be run ON the NPU host (ASI2)").
#
# The fixed sources live on the shared filestorage NFS (reachable from
# ASI2), so this worker takes NO S3 dependency:
#   /root/work/filestorage/mwg-ew-transformer-research/custom_ops/...
# It rebuilds v4 into ASI2-local /root/work/mwg_v4_torch_ext from the
# verified fixed source, verifies the warmup-fix string in the binary,
# and runs test_v4_multicore.py against the surviving fixed v1 .so
# (AS2-local /root/work/mwg_torch_ext/build/libcustom_ops.so, built
# 2026-10-02 12:34 from source md5 59cf1751...).
#
# Runs ON ASI2 detached via nohup.
set -uo pipefail

PROJECT_ROOT=/root/work/filestorage/mwg-ew-transformer-research
RUN_LOG="$PROJECT_ROOT/results/v4_asi2_decisive_20261008.log"
SRC_FIXED="$PROJECT_ROOT/custom_ops/ephemeral_core_apply/torch_ext/v4_multicore/ephemeral_core_apply_v4_multicore.asc"
TEST_PY="$PROJECT_ROOT/custom_ops/ephemeral_core_apply/torch_ext/v4_multicore/test_v4_multicore.py"
CMAKE_V4="$PROJECT_ROOT/custom_ops/ephemeral_core_apply/torch_ext/CMakeLists_v4.txt"
V4_EXT=/root/work/mwg_v4_torch_ext
V1_EXT=/root/work/mwg_torch_ext
V1_SO="$V1_EXT/build/libcustom_ops.so"

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
if [ ! -f "$V1_SO" ]; then
  log "MISSING V1_SO: $V1_SO; aborting"
  exit 5
fi
V1_MD5=$(md5sum "$V1_EXT/ephemeral_core_apply.asc" 2>/dev/null | awk '{print $1}')
if [ "$V1_MD5" != "59cf1751d920f5f90851b117f7483d6c" ]; then
  log "V1_SRC_MD5_MISMATCH: got $V1_MD5, expected 59cf1751...; aborting"
  exit 5
fi
log "v1 baseline verified (source $V1_MD5, $V1_SO)"

# --- Step 1: stage the ext dir from the verified fixed sources ---
mkdir -p "$V4_EXT"
cp "$CMAKE_V4" "$V4_EXT/CMakeLists.txt"
cp "$SRC_FIXED" "$V4_EXT/"
log "staged $V4_EXT from fixed sources"

# --- Step 2: rebuild via the proven CMake/ASC flow ---
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || true
cd "$V4_EXT"
log "cmake configure"
rm -rf build && mkdir -p build && cd build
cmake .. > cmake_v4.log 2>&1; CMAKE_RC=$?
log "cmake rc=$CMAKE_RC"
[ "$CMAKE_RC" -ne 0 ] && { tail -15 cmake_v4.log >> "$RUN_LOG" 2>&1; log "CMAKE FAILED"; exit 1; }
make > make_v4.log 2>&1; MAKE_RC=$?
log "make rc=$MAKE_RC"
[ "$MAKE_RC" -ne 0 ] && { tail -40 make_v4.log >> "$RUN_LOG" 2>&1; log "MAKE FAILED"; exit 1; }

V4_SO=$(find "$V4_EXT/build" -name '*.so' -type f | head -1)
log "V4_SO=$V4_SO"
[ -z "$V4_SO" ] && { log "NO .so FOUND"; exit 1; }

WARMUP_STRS=$(grep -c 'warmup failed to converge' "$V4_SO" || true)
log "warmup-fix string count in v4 .so: $WARMUP_STRS"
if [ "$WARMUP_STRS" -lt 1 ]; then
  log "WARMUP_FIX_MISSING_IN_BINARY: rebuilt .so lacks the verified-warmup probe; aborting"
  exit 6
fi

# --- Step 3: run the decisive v4-vs-v1 comparison + stability test ---
cd "$PROJECT_ROOT"
log "running test_v4_multicore.py"
python3 "$TEST_PY" \
    --op-library "$V4_SO" \
    --v1-library "$V1_SO" \
    --output "$PROJECT_ROOT/results/v4_multicore_benchmark_asi2_20261008.json" \
    --warmup 30 --iters 200 --repeats 5 \
    >> "$RUN_LOG" 2>&1
TEST_RC=$?
log "test rc=$TEST_RC"

log "=== v4 ASI2 decisive worker done ==="
