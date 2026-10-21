#!/bin/bash
# ASI2 decisive-run v2 watcher (2026-10-08): waits for the device to free,
# then runs the hardened decisive v4-vs-v1 worker v2. Max wait 12h.
WATCH_LOG=/tmp/asi2_v2_watcher.log
WORKER=/tmp/asi2_v4_decisive_worker_v2.sh
MAX_ITERS=1440  # 12h at 30s polls
echo "[watcher-v2] started $(date -u +%FT%TZ)" >> "$WATCH_LOG"
for i in $(seq 1 $MAX_ITERS); do
  if pgrep -f 'qwen_sft|torchrun' >/dev/null 2>&1; then
    sleep 30; continue
  fi
  NPU_PROCS=$(npu-smi info 2>/dev/null | grep -c 'python\|torchrun' || true)
  if [ "$NPU_PROCS" -gt 0 ]; then
    if [ $((i % 40)) -eq 0 ]; then
      echo "[watcher-v2] iter $i: still $NPU_PROCS tenant procs $(date -u +%FT%TZ)" >> "$WATCH_LOG"
    fi
    sleep 30; continue
  fi
  echo "[watcher-v2] device free at iter $i $(date -u +%FT%TZ); launching worker v2" >> "$WATCH_LOG"
  bash "$WORKER" >> "$WATCH_LOG" 2>&1
  RC=$?
  echo "[watcher-v2] worker v2 finished rc=$RC $(date -u +%FT%TZ)" >> "$WATCH_LOG"
  exit 0
done
echo "[watcher-v2] TIMEOUT after 12h; device never freed" >> "$WATCH_LOG"
exit 5
