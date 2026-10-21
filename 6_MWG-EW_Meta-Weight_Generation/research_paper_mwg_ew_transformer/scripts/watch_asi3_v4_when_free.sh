#!/usr/bin/env bash
# Auto-retry watcher: waits for the ASI3 NPU to be free of the qwen SFT
# trainer (and any tenant processes), then launches the v4 build+benchmark
# worker.  Deployed detached on ASI3 via nohup; progress goes to the same
# run log the worker uses.
#
# Why: the decisive fused-arm-4 measurement (review R1) is blocked on device
# contention -- the qwen SFT trainer holds all 8 NPUs for hours.  Manual
# polling risks missing the free window (e.g. overnight).  This watcher
# polls every 5 minutes, for up to 48 hours, and fires exactly once.
#
# Usage (on ASI3):
#   nohup bash scripts/watch_asi3_v4_when_free.sh >> results/v4_watch.log 2>&1 &
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LAUNCHER="$SCRIPT_DIR/launch_asi3_v4_build_benchmark_detached.sh"

MAX_HOURS="${MWG_V4_WATCH_HOURS:-48}"
POLL_SECONDS="${MWG_V4_WATCH_POLL:-300}"

deadline=$(( $(date +%s) + MAX_HOURS * 3600 ))

while [ "$(date +%s)" -lt "$deadline" ]; do
  if pgrep -f 'qwen_sft_peft|torchrun.*qwen_sft' >/dev/null; then
    echo "[$(date -u +%FT%TZ)] trainer still running; sleeping ${POLL_SECONDS}s"
    sleep "$POLL_SECONDS"
    continue
  fi
  NPU_PROCS=$(npu-smi info 2>/dev/null | grep -c 'python\|torchrun' || true)
  if [ "${NPU_PROCS:-0}" -gt 0 ]; then
    echo "[$(date -u +%FT%TZ)] $NPU_PROCS tenant processes on NPU; sleeping ${POLL_SECONDS}s"
    sleep "$POLL_SECONDS"
    continue
  fi
  echo "[$(date -u +%FT%TZ)] device free; launching v4 build+benchmark"
  bash "$LAUNCHER"
  rc=$?
  echo "[$(date -u +%FT%TZ)] launcher rc=$rc; watcher exiting (fires once)"
  exit "$rc"
done

echo "[$(date -u +%FT%TZ)] watcher deadline (${MAX_HOURS}h) exceeded without a free window"
exit 5
