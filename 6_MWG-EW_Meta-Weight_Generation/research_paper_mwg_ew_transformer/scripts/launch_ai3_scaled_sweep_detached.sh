#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
cd "$PROJECT_ROOT"

mkdir -p logs
TS="$(date -u +%Y%m%dT%H%M%SZ)"
WRAPPER_LOG="logs/ai3_scaled_sweep_detached_${TS}.log"

nohup bash scripts/run_ai3_scaled_sweep.sh > "$WRAPPER_LOG" 2>&1 < /dev/null &
PID="$!"

echo "AI3 scaled sweep detached"
echo "pid=$PID"
echo "project_root=$PROJECT_ROOT"
echo "wrapper_log=$WRAPPER_LOG"
echo "status_pattern=logs/ai3_scaled_sweep_*.status.json"
