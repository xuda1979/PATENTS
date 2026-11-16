#!/usr/bin/env bash
set -Eeuo pipefail
# Detached retry worker: block-Givens latency only (no retraining).
ROOT="/vllm-workspace/mwg-ew-transformer-research"
RUN_ID="asi2_q4_matched_quality_latency_20261113T134959Z"
RUN_DIR="$ROOT/results/$RUN_ID"
SEEDS="2026 2027 2028 2029"
STUDENT="mwg_block_givens_r384"
RANK=384
LOG="$ROOT/logs/asi2_block_givens_latency_retry_${RUN_ID}.log"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$LOG"; }

log "block-givens latency retry worker start"
cd "$ROOT"
for seed in $SEEDS; do
  outdir="$RUN_DIR/seed_${seed}"
  ckpt="$outdir/checkpoints/${STUDENT}.pt"
  if [[ ! -s "$ckpt" ]]; then
    log "seed ${seed}: checkpoint missing ($ckpt); skipping"
    continue
  fi
  rm -f "$outdir/latency_${STUDENT}.json"
  python3 experiments/mwg_four_arm_lifetime_benchmark.py \
    --d 1536 --m 8960 --rank "$RANK" --controller-hidden 384 \
    --batch 1 --seq 128 --amplitude 0.05 --dtype fp16 \
    --arms dense,persistent,block_givens \
    --device auto --warmup 10 --iters 50 --repeats 3 \
    --trained-checkpoint "$ckpt" \
    --run-label "q4_retry_${RUN_ID}_seed_${seed}_${STUDENT}" \
    --output "$outdir/latency_${STUDENT}.json" \
    >> "$LOG" 2>&1 || { log "seed ${seed}: retry latency FAILED (kept old state)"; continue; }
  log "seed ${seed}: retry latency measured (arms: dense,persistent,block_givens)"
done

# ---- Merge latency rows into q4_summary.json (timestamped backup first). ----
python3 - "$RUN_DIR" $SEEDS "$STUDENT" <<'PY' >> "$LOG" 2>&1
import json, shutil, sys
from datetime import datetime, timezone
from pathlib import Path

run_dir = Path(sys.argv[1])
seeds = [int(s) for s in sys.argv[2:-1]]
student = sys.argv[-1]
summary_path = run_dir / "q4_summary.json"
backup = run_dir / (
    "q4_summary.json.bak_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
)
shutil.copy2(summary_path, backup)
summary = json.loads(summary_path.read_text())
rows = summary["rows"]

# Drop any stale retry rows from a previous partial merge, then re-add.
merged = 0
for seed in seeds:
    lat_path = run_dir / f"seed_{seed}" / f"latency_{student}.json"
    if not lat_path.is_file():
        continue
    d = json.loads(lat_path.read_text())
    arms = d.get("arms", {})
    if student not in (arms or {}):
        continue
    rows[:] = [
        r
        for r in rows
        if not (r.get("student") == student and "latency_ms" in r and r.get("seed") == seed)
    ]
    row = {
        "seed": seed,
        "student": student,
        "latency_ms": {
            arm: res.get("timing", {}).get("median_ms") for arm, res in arms.items()
        },
        "trained_checkpoint_sha256": (d.get("trained_checkpoint") or {}).get("sha256"),
    }
    rows.append(row)
    merged += 1

summary_path.write_text(json.dumps(summary, indent=2) + "\n")
print(f"merged {merged} latency rows into {summary_path}; backup at {backup}")
PY
log "block-givens latency retry worker complete (merged summary)"
