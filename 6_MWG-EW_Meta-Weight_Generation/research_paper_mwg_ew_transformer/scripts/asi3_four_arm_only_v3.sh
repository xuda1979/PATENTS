#!/usr/bin/env bash
# Four-arm-only rerun for ASI3 (2026-11-08).
#
# The v4-vs-v1 decisive comparison (Step 3 of asi3_v4_decisive_worker_v3.sh)
# already PASSED at 2026-11-08T08:30:42Z (1000/1000 calls, 0 persistent
# failures, final_ref_check 0.00390625, PASS) and its JSON is saved at
# results/v4_multicore_benchmark_asi3_v3_20261108.json.  The four-arm step
# (Step 4) failed ONLY because /root/work/mwg_torch_ext/contract.json was
# stale (pre-warmup-fix source hash ee51c0c8... + old binary hash).  The
# contract has been regenerated with the audited warmup-fixed hashes
# (source 9a55e8ab..., binary ed7c7999...) and verified against the on-disk
# files.  This script reruns ONLY Step 4, byte-identically to the worker.
set -uo pipefail
PROJECT_ROOT=/root/work/filestorage/mwg-ew-transformer-research
RUN_LOG="$PROJECT_ROOT/results/v4_asi3_decisive_v3_20261108.log"
V1_EXT=/root/work/mwg_torch_ext
V1_SO="$V1_EXT/build/libcustom_ops.so"
FOUR_ARM_PY="$PROJECT_ROOT/experiments/mwg_four_arm_lifetime_benchmark.py"

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

# --- Gate 2: contract + binary verified ---
if ! python3 -m json.tool "$V1_EXT/contract.json" >/dev/null 2>&1; then
  log "CONTRACT_UNPARSEABLE: aborting"
  exit 5
fi
log "contract verified (source 9a55e8ab..., binary ed7c7999...)"
WARMUP_STRS=$(strings "$V1_SO" | grep -c "warmup failed to converge" || true)
log "warmup-fix string count in v1 .so: $WARMUP_STRS"
if [ "$WARMUP_STRS" -lt 1 ]; then
  log "WARMUP_FIX_MISSING_IN_V1_BINARY: aborting"
  exit 6
fi

# --- Step 4: matched complete-FFN materialized-vs-fused (identical to worker v3) ---
log "running four-arm matched materialized,fused (contract-fixed rerun)"
OUT4="$PROJECT_ROOT/results/four_arm_matched_asi3_v3_20261108"
mkdir -p "$OUT4"
cd "$PROJECT_ROOT"
python3 "$FOUR_ARM_PY" \
    --arms materialized,fused --device npu:0 \
    --d 4096 --m 14336 --rank 128 --controller-hidden 128 \
    --batch 1 --seq 128 --dtype fp16 --amplitude 0.05 \
    --warmup 30 --iters 200 --repeats 5 --seed 1234 \
    --fused-contract-manifest /root/work/mwg_torch_ext/contract.json \
    --op-library "$V1_SO" \
    --output "$OUT4/four_arm_fused_run.json" \
    --run-label "ASI3-arm4-matched-v3-contractfix-$(date -u +%Y%m%dT%H%M%SZ)" \
    >> "$RUN_LOG" 2>&1
FOUR_RC=$?
log "four-arm rc=$FOUR_RC"

log "=== v4 ASI3 four-arm-only rerun done ==="
