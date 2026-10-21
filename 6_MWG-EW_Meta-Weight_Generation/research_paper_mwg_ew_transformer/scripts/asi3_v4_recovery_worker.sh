#!/usr/bin/env bash
# Recovery worker for the 2026-10-08 failed v4 ASI3 launch.
#
# Context: the detached launcher's S3 pull is chronically Forbidden from
# ASI3, so its 04:35Z run rebuilt v4 from a STALE pre-warmup-fix source
# (5d978761...) and the stale kernel aicore-crashed (EZ9999).  The run's
# rm -rf also destroyed the previously verified fixed build at
# /root/work/mwg_v4_torch_ext.
#
# This worker takes NO S3 dependency: the fixed v4 source was restored in
# the working tree via chunked upload (md5 701e9be0...).  It copies that
# source into the ext dir, rebuilds with the proven CMake/ASC flow, and
# runs test_v4_multicore.py against the surviving fixed v1 .so
# (built 2026-10-02 12:34 from source md5 59cf1751...).
#
# Runs ON ASI3 detached via nohup from ASI3_shell.sh.
set -uo pipefail

PROJECT_ROOT=/root/work/filestorage/mwg-ew-transformer-research
RUN_LOG="$PROJECT_ROOT/results/v4_asi3_recovery_20261008.log"
SRC_FIXED="$PROJECT_ROOT/custom_ops/ephemeral_core_apply/torch_ext/v4_multicore/ephemeral_core_apply_v4_multicore.asc"
TEST_PY="$PROJECT_ROOT/custom_ops/ephemeral_core_apply/torch_ext/v4_multicore/test_v4_multicore.py"
CMAKE_V4="$PROJECT_ROOT/custom_ops/ephemeral_core_apply/torch_ext/CMakeLists_v4.txt"
V4_EXT=/root/work/mwg_v4_torch_ext
V1_SO=/root/work/mwg_torch_ext/build/libcustom_ops.so

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
log "v1 baseline present: $V1_SO"

# --- Step 1: stage ext dir from the verified fixed sources ---
mkdir -p "$V4_EXT"
cp "$CMAKE_V4" "$V4_EXT/CMakeLists.txt"
cp "$SRC_FIXED" "$V4_EXT/"
cp "$TEST_PY" "$PROJECT_ROOT/custom_ops/ephemeral_core_apply/torch_ext/v4_multicore/test_v4_multicore.py.bak" 2>/dev/null || true

# --- Step 2: rebuild via the proven CMake/ASC flow ---
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || true
cd "$V4_EXT"
log "cmake configure (recovery)"
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
grep -c 'warmup failed to converge' "$V4_SO" >/dev/null 2>&1 && log "warmup-fix string present in .so" || log "WARN: warmup-fix string not found in .so"

# --- Step 3: run the decisive v4-vs-v1 comparison + stability test ---
cd "$PROJECT_ROOT"
log "running test_v4_multicore.py (recovery)"
python3 "$TEST_PY" \
    --op-library "$V4_SO" \
    --v1-library "$V1_SO" \
    --output "$PROJECT_ROOT/results/v4_multicore_benchmark_recovery_20261008.json" \
    --warmup 30 --iters 200 --repeats 5 \
    >> "$RUN_LOG" 2>&1
log "test rc=$?"

log "=== v4 recovery worker done ==="
