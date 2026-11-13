#!/usr/bin/env bash
# Complete-FFN v4 latency sweep on ASI3 (2026-11-12).
#
# Purpose: close the "complete-FFN v4 sweep across T=128--4096 alongside
# persistent, materialized, and dense arms" gap from the journal revision
# list. Runs the five-arm benchmark (dense, persistent, materialized,
# fused v1, fused_v4 multicore) at five token geometries, on the same
# runtime and operator boundary as the archived v1 four-arm record.
#
# Both operator libraries are the binaries validated by the 2026-11-08
# hardened sweep (v1: /root/work/mwg_torch_ext, Oct 2 build;
# v4: /root/work/mwg_v4_torch_ext, Nov 8 build).
set -uo pipefail
PROJECT_ROOT=/root/work/filestorage/mwg-ew-transformer-research
RUN_LOG="$PROJECT_ROOT/results/asi3_complete_ffn_v4_sweep_20261112.log"
OUT_DIR="$PROJECT_ROOT/results/asi3_complete_ffn_v4_sweep_20261112"
mkdir -p "$OUT_DIR"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$RUN_LOG"; }

# --- Gate 0: device idle ---
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

V1_SO=/root/work/mwg_torch_ext/build/libcustom_ops.so
V1_MANIFEST=/root/work/mwg_torch_ext/contract.json
V4_SO=/root/work/mwg_v4_torch_ext/build/libcustom_ops_v4.so

for f in "$V1_SO" "$V1_MANIFEST" "$V4_SO"; do
  if [ ! -f "$f" ]; then
    log "MISSING_ARTIFACT: $f"
    exit 5
  fi
done
log "operator artifacts present (v1 $(md5sum "$V1_SO" | cut -c1-8), v4 $(md5sum "$V4_SO" | cut -c1-8))"

# Geometries: label batch seq
# T=128  (archived probe geometry: batch 1, seq 128, L2-resident)
# T=512, 1024, 2048, 4096 (batch 16, seq 32..256 mirrors the large-T family:
#   the archived large-T used batch 16 seq 256 -> T=4096)
run_geometry() {
  local label="$1" batch="$2" seq="$3"
  log "=== geometry $label (batch=$batch seq=$seq) ==="
  python3 "$PROJECT_ROOT/experiments/mwg_four_arm_lifetime_benchmark.py" \
    --arms dense,persistent,materialized,fused,fused_v4 --device npu:0 \
    --d 4096 --m 14336 --rank 128 --controller-hidden 128 \
    --batch "$batch" --seq "$seq" --dtype fp16 --amplitude 0.05 \
    --warmup 30 --iters 200 --repeats 5 --seed 1234 \
    --fused-contract-manifest "$V1_MANIFEST" \
    --op-library "$V1_SO" \
    --v4-op-library "$V4_SO" \
    --output "$OUT_DIR/five_arm_${label}.json" \
    --overwrite \
    --run-label "ASI3-complete-ffn-v4-sweep-${label}-$(date -u +%Y%m%dT%H%M%SZ)" \
    >> "$RUN_LOG" 2>&1
  local rc=$?
  log "geometry $label rc=$rc"
  return $rc
}

FAIL=0
run_geometry T128 1 128 || FAIL=1
run_geometry T512 16 32 || FAIL=1
run_geometry T1024 16 64 || FAIL=1
run_geometry T2048 16 128 || FAIL=1
run_geometry T4096 16 256 || FAIL=1

if [ "$FAIL" -ne 0 ]; then
  log "SWEEP INCOMPLETE: one or more geometries failed"
  exit 6
fi

python3 - <<'PY' >> "$RUN_LOG" 2>&1
import json
from pathlib import Path

out_dir = Path("/root/work/filestorage/mwg-ew-transformer-research/results/asi3_complete_ffn_v4_sweep_20261112")
summary = []
for label in ("T128", "T512", "T1024", "T2048", "T4096"):
    payload = json.loads((out_dir / f"five_arm_{label}.json").read_text())
    row = {"geometry": label, "batch": payload["config"]["batch"],
           "seq": payload["config"]["seq"],
           "tokens": payload["config"]["batch"] * payload["config"]["seq"]}
    for arm, record in payload["arms"].items():
        row[arm] = record["timing"]["median_ms"]
    row["validations"] = {
        k: v.get("passed") for k, v in payload.get("validations", {}).items()
    }
    summary.append(row)
(out_dir / "sweep_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
PY
log "=== complete-FFN v4 sweep done ==="
