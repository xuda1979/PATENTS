#!/usr/bin/env bash
# Auto-retry watcher (recovery variant): waits for the ASI3 NPU to be free
# of the qwen SFT trainer (and any tenant processes), then fires the
# 2026-10-08 recovery worker (asi3_v4_recovery_worker.sh) exactly once.
#
# Differs from watch_asi3_v4_when_free.sh only in the fired script: the
# recovery worker takes no S3 dependency (the detached launcher's S3 pull
# is chronically Forbidden from ASI3) and guards the fixed-source md5
# before rebuilding.
#
# Usage (on ASI3):
#   nohup bash scripts/watch_asi3_v4_recovery_when_free.sh >> results/v4_recovery_watch.log 2>&1 &
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKER="$SCRIPT_DIR/asi3_v4_recovery_worker.sh"

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
  echo "[$(date -u +%FT%TZ)] device free; launching v4 recovery worker"
  bash "$WORKER"
  rc=$?
  echo "[$(date -u +%FT%TZ)] worker rc=$rc; watcher exiting (fires once)"
  exit "$rc"
done

echo "[$(date -u +%FT%TZ)] watcher deadline (${MAX_HOURS}h) exceeded without a free window"
exit 5
