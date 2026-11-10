#!/usr/bin/env bash
# Decisive v4-vs-v1 benchmark worker v3 for ASI3 (2026-11-08).
#
# Derived from scripts/asi2_v4_decisive_worker_v3.sh (2026-11-06, md5
# fbb151308b2ac2e73d4888b0bf45c65d) with ONLY these changes:
#   1. output/log names use asi3 + today's date so results from the
#      shared filestorage results/ tree cannot collide with the armed
#      ASI2 v3 worker.
# All gates, fixed sources, CMake rebuild, binary checks, and test
# parameters are IDENTICAL to the ASI2 v3 worker.
set -uo pipefail
PROJECT_ROOT=/root/work/filestorage/mwg-ew-transformer-research
RUN_LOG="$PROJECT_ROOT/results/v4_asi3_decisive_v3_20261108.log"
SRC_FIXED="$PROJECT_ROOT/custom_ops/ephemeral_core_apply/torch_ext/v4_multicore/ephemeral_core_apply_v4_multicore.asc"
SRC_V1="$PROJECT_ROOT/custom_ops/ephemeral_core_apply/torch_ext/ephemeral_core_apply.asc"
TEST_PY=/tmp/test_v4_multicore_v3.py
FOUR_ARM_PY="$PROJECT_ROOT/experiments/mwg_four_arm_lifetime_benchmark.py"
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
log "verifying fixed kernel sources"
V4_MD5=$(md5sum "$SRC_FIXED" | cut -d' ' -f1)
V1_MD5=$(md5sum "$SRC_V1" | cut -d' ' -f1)
log "v4 source md5=$V4_MD5 v1 source md5=$V1_MD5"
if [ "$V4_MD5" != "701e9be098b51b13ac89409384735e2d" ]; then
  log "V4_SOURCE_MD5_MISMATCH: got $V4_MD5, expected 701e9be0...; aborting"
  exit 5
fi
[ -f "$SRC_FIXED" ] || { log "V4_SOURCE_MISSING"; exit 5; }
[ -f "$SRC_V1" ] || { log "V1_SOURCE_MISSING"; exit 5; }
[ -f "$TEST_PY" ] || { log "TEST_PY_MISSING: stage test_v4_multicore_v3.py at /tmp first"; exit 5; }
TEST_MD5=$(md5sum "$TEST_PY" | cut -d' ' -f1)
log "test harness md5=$TEST_MD5"
if [ "$TEST_MD5" != "526839744b6c2916822b3a1a9387609f" ]; then
  log "TEST_PY_MD5_MISMATCH: got $TEST_MD5, expected 52683974...; aborting"
  exit 5
fi
[ -f "$CMAKE_V4" ] || { log "CMAKE_V4_MISSING"; exit 5; }

# --- Step 1: stage the fixed v4 sources ---
log "staging fixed sources into $V4_EXT"
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

# --- Step 2.5 (kept from v2): settle after rebuild ---
log "settling 60s post-build"
sleep 60

# --- Step 3: run the hardened decisive v4-vs-v1 comparison (v3 harness) ---
cd "$PROJECT_ROOT"
log "running test_v4_multicore_v3.py"
python3 "$TEST_PY" \
    --op-library "$V4_SO" \
    --v1-library "$V1_SO" \
    --output "$PROJECT_ROOT/results/v4_multicore_benchmark_asi3_v3_20261108.json" \
    --warmup 30 --iters 200 --repeats 5 \
    >> "$RUN_LOG" 2>&1
TEST_RC=$?
log "test rc=$TEST_RC"
if [ "$TEST_RC" -ne 0 ]; then
  log "V4_COMPARISON_FAILED rc=$TEST_RC; skipping four-arm extension"
  exit 7
fi

# --- Step 4 (kept from ASI2 v3): matched complete-FFN materialized-vs-fused ---
# Same process family, same v1 .so, same geometry as the shipped
# 2026-08-28 four-arm decisive run, providing the matched
# v4-era four-arm extension evidence.
log "running four-arm matched materialized,fused"
OUT4="$PROJECT_ROOT/results/four_arm_matched_asi3_v3_20261108"
mkdir -p "$OUT4"
python3 "$FOUR_ARM_PY" \
    --arms materialized,fused --device npu:0 \
    --d 4096 --m 14336 --rank 128 --controller-hidden 128 \
    --batch 1 --seq 128 --dtype fp16 --amplitude 0.05 \
    --warmup 30 --iters 200 --repeats 5 --seed 1234 \
    --fused-contract-manifest /root/work/mwg_torch_ext/contract.json \
    --op-library "$V1_SO" \
    --output "$OUT4/four_arm_fused_run.json" \
    --run-label "ASI3-arm4-matched-v3-$(date -u +%Y%m%dT%H%M%SZ)" \
    >> "$RUN_LOG" 2>&1
FOUR_RC=$?
log "four-arm rc=$FOUR_RC"

log "=== v4 ASI3 decisive worker v3 done ==="
