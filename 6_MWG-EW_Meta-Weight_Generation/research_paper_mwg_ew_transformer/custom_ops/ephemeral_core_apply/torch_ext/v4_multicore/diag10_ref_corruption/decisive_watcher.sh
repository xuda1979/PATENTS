#!/bin/bash
# ASI2 decisive-run watcher (2026-10-08): waits for the device to free,
# then runs the decisive v4-vs-v1 worker. Max wait 12h.
WATCH_LOG=/tmp/asi2_decisive_watcher.log
WORKER=/root/work/filestorage/mwg-ew-transformer-research/scripts/asi2_v4_decisive_worker.sh
MAX_ITERS=1440  # 12h at 30s polls
echo "[watcher] started $(date -u +%FT%TZ)" >> "$WATCH_LOG"
for i in $(seq 1 $MAX_ITERS); do
  if pgrep -f 'qwen_sft|torchrun' >/dev/null 2>&1; then
    sleep 30; continue
  fi
  NPU_PROCS=$(npu-smi info 2>/dev/null | grep -c 'python\|torchrun' || true)
  if [ "$NPU_PROCS" -gt 0 ]; then
    if [ $((i % 40)) -eq 0 ]; then
      echo "[watcher] iter $i: still $NPU_PROCS tenant procs $(date -u +%FT%TZ)" >> "$WATCH_LOG"
    fi
    sleep 30; continue
  fi
  echo "[watcher] device free at iter $i $(date -u +%FT%TZ); launching worker" >> "$WATCH_LOG"
  bash "$WORKER" >> "$WATCH_LOG" 2>&1
  RC=$?
  echo "[watcher] worker finished rc=$RC $(date -u +%FT%TZ)" >> "$WATCH_LOG"
  exit 0
done
echo "[watcher] TIMEOUT after 12h; device never freed" >> "$WATCH_LOG"
exit 5
