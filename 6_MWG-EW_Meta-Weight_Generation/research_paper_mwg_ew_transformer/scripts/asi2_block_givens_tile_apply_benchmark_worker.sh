#!/usr/bin/env bash
set -euo pipefail

# Compile-and-benchmark harness: tile-local block-Givens kernel (block_givens_tile_apply).
#
# RUNS ON THE NPU HOST (ASI2).  Single-command execution of the pre-declared
# Q4 open path: compile the Ascend-C kernel
# (custom_ops/block_givens_tile_apply/block_givens_tile_apply_kernel.cpp),
# verify its outputs against the CPU numeric model shipped in the repo
# (simulate_kernel_numeric_model; see tests/test_tile_kernel_numeric_model.py,
# 10 tests, algorithm correctness closed on CPU), then benchmark it against
# the persistent arm on the SAME trained checkpoints as the 2026-11-13 Q4 run.
#
# PRE-REGISTERED ACCEPTANCE GATE (versioned in this header BEFORE any
# measurement; thresholds, not predictions):
#   * Speed:   median tile-apply path latency >= 20% lower than the matched
#              persistent arm (i.e. tile_ms <= 0.80 * persistent_ms) at
#              batch 1, S=128, fp16, single device, single layer — the same
#              measurement shape as Q4's timing boundary.  This matches
#              Q4's pre-declared >=20% threshold; the reference block-Givens
#              arm failed it (4.48x persistent), so the compiled tile-local
#              path is the last open realization that could pass.
#   * Quality: outputs numerically equal to the CPU kernel model within
#              fp16 tolerance (max abs diff <= 2e-2 scale-relative) on the
#              verification fixture; any divergence is a correctness FAIL
#              and voids the timing numbers.
#   * Verdict: PASS only if both hold.  A failed or negative outcome is
#              recorded as a first-class negative result, never promoted;
#              submission_ready is unaffected by a PASS here (the gate list
#              decides that).
#
# The gate is enforced by experiments/verify_tile_apply_benchmark.py, which
# this harness invokes; the thresholds live in that script's TILE_GATE
# constant, mirroring this header, and any mismatch between the two aborts.
#
# Usage:  bash scripts/asi2_block_givens_tile_apply_benchmark_worker.sh [--check|--worker]
#   default: preflight, then run compile + verify + benchmark + gate, writing
#            results/tile_apply_benchmark_<ts>/report.json
#   --check : preflight only (no device work)

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_ID="tile_apply_benchmark_$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="${RUN_DIR:-$PROJECT_ROOT/results/$RUN_ID}"
LOG="$RUN_DIR/harness.log"
DEVICES="${ASCEND_RT_VISIBLE_DEVICES:-0}"
SEEDS="${SEEDS:-2026 2027 2028}"
BATCH=1
SEQ=128
OP="${OP:-block_givens_tile_apply}"

mkdir -p "$RUN_DIR"
log() { printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$LOG"; }

die() { log "FATAL: $*"; exit 1; }

preflight() {
  log "preflight: ASCEND tools"
  python3 scripts/probe_ascend_custom_op_toolchain.sh >/dev/null 2>&1 \
    || python3 "$PROJECT_ROOT/scripts/probe_ascend_custom_op_toolchain.sh" --json \
       > "$RUN_DIR/toolchain_probe.json" 2>"$RUN_DIR/toolchain_probe.err" \
    || true
  for tool in msprof; do
    command -v "$tool" >/dev/null 2>&1 || log "WARN: $tool not on PATH (device may still work via torch)"
  done
  [ -f "$PROJECT_ROOT/custom_ops/block_givens_tile_apply/block_givens_tile_apply_kernel.cpp" ] \
    || die "kernel source missing"
  python3 - <<PY
import sys
sys.path.insert(0, "$PROJECT_ROOT/custom_ops/block_givens_tile_apply")
sys.path.insert(0, "$PROJECT_ROOT/experiments")
import torch
from sim_block_givens_tile_apply import simulate_kernel_numeric_model
out, stats = simulate_kernel_numeric_model(
    torch.randn(4, 256, dtype=torch.float32),
    torch.randn(256, 32, dtype=torch.float32),
    torch.randn(32, 256, dtype=torch.float32),
    torch.zeros(4, 128, dtype=torch.float32),
)
assert stats["n_tiles"] == 2 and torch.isfinite(out).all()
print("cpu model smoke: OK")
PY
  log "preflight passed"
}

worker() {
  cd "$PROJECT_ROOT"
  log "worker start: run_id=$RUN_ID seeds=$SEEDS op=$OP devices=$DEVICES"

  # ---- Stage 1: compile the Ascend-C kernel via the vendor build path.
  log "stage 1: compile $OP"
  python3 custom_ops/ephemeral_core_apply/make_op_package_and_manifest.py --help \
    >/dev/null 2>&1 || log "note: ephemeral packaging script present-check skipped"
  # The compile proper is the CANN vendor flow (build.sh -> vendor install).
  # It is invoked here; failure aborts before any timing is collected.
  if [ -x "$PROJECT_ROOT/custom_ops/block_givens_tile_apply/build.sh" ]; then
    bash "$PROJECT_ROOT/custom_ops/block_givens_tile_apply/build.sh" \
      || die "kernel compile failed"
  else
    die "build.sh not present: the vendor build flow must be authored on the \
NPU host per the ephemeral_core_apply precedent before this harness runs"
  fi

  # ---- Stage 2: correctness verification against the CPU model.
  log "stage 2: verify compiled outputs against CPU numeric model"
  python3 experiments/verify_tile_apply_benchmark.py --verify-only \
    --out "$RUN_DIR/verification.json" \
    || die "compiled kernel failed numeric verification; timing voided"

  # ---- Stage 3: benchmark vs persistent on the trained checkpoints.
  log "stage 3: benchmark tile-apply vs persistent (seeds=$SEEDS)"
  for seed in $SEEDS; do
    python3 experiments/verify_tile_apply_benchmark.py --benchmark \
      --seed "$seed" --batch "$BATCH" --seq "$SEQ" --op "$OP" \
      --out "$RUN_DIR/seed_${seed}_benchmark.json" \
      || die "benchmark failed at seed $seed"
  done

  # ---- Stage 4: gate evaluation (thresholds pinned in the verifier).
  log "stage 4: evaluate pre-declared acceptance gate"
  python3 experiments/verify_tile_apply_benchmark.py --gate \
    --run-dir "$RUN_DIR" --out "$RUN_DIR/report.json" \
    || die "gate evaluation failed (see report.json)"

  log "done: $RUN_DIR/report.json"
}

case "${1:-}" in
  --check) preflight ;;
  --worker) worker ;;
  "") preflight; worker ;;
  *) die "unknown arg: $1 (use --check or --worker)" ;;
esac
