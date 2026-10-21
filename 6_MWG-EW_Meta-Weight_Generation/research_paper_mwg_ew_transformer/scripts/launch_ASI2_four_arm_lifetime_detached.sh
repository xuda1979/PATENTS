#!/usr/bin/env bash
set -euo pipefail

# Background-only ASI2 launcher.  FULL_EVIDENCE=0 runs arms 1--3 and labels
# every byte count analytical.  FULL_EVIDENCE=1 is fail-closed: the launcher
# first requires the Ascend-C toolchain, a hash-bound no-store op manifest, a
# registered compiled op, torch_npu NPU profiling, and msprof counter flags.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$PROJECT_ROOT"

FULL_EVIDENCE="${FULL_EVIDENCE:-0}"
ARMS="${ARMS:-dense,persistent,materialized}"
DEVICE="${DEVICE:-npu:0}"
D="${D:-4096}"
M="${M:-14336}"
# MWG_RANK avoids collision with the platform RANK env var (torchrun/Ascend
# containers commonly export RANK=0, which previously leaked into --rank).
RANK="${MWG_RANK:-128}"
CONTROLLER_HIDDEN="${CONTROLLER_HIDDEN:-256}"
BATCH="${BATCH:-1}"
SEQ="${SEQ:-128}"
DTYPE="${DTYPE:-fp16}"
AMPLITUDE="${AMPLITUDE:-0.05}"
WARMUP="${WARMUP:-30}"
ITERS="${ITERS:-200}"
REPEATS="${REPEATS:-5}"
SEED="${SEED:-1234}"
COUNTER_METRICS="${COUNTER_METRICS:-Memory,L2Cache,PipeUtilization,ArithmeticUtilization}"
ASCEND_RT_VISIBLE_DEVICES="${ASCEND_RT_VISIBLE_DEVICES:-0}"
export ASCEND_RT_VISIBLE_DEVICES

if [[ "$FULL_EVIDENCE" != "0" && "$FULL_EVIDENCE" != "1" ]]; then
  echo "FULL_EVIDENCE must be 0 or 1" >&2
  exit 2
fi

if [[ ( "$ARMS" == *fused* || "$ARMS" == "all" ) && "$FULL_EVIDENCE" != "1" ]]; then
  echo "refusing fused arm without FULL_EVIDENCE=1 prerequisite enforcement" >&2
  exit 2
fi

if [[ "$FULL_EVIDENCE" == "1" ]]; then
  ARMS="dense,persistent,materialized,fused"
  if [[ -z "${MWG_FUSED_OP_LIBRARY:-}" || -z "${MWG_FUSED_CONTRACT_MANIFEST:-}" || -z "${MWG_FUSED_REGISTRATION_MODULE:-}" ]]; then
    echo "FULL_EVIDENCE=1 requires MWG_FUSED_OP_LIBRARY (op package tarball)," >&2
    echo "MWG_FUSED_CONTRACT_MANIFEST, and MWG_FUSED_REGISTRATION_MODULE" >&2
    exit 2
  fi
  export MWG_FUSED_OP_LIBRARY MWG_FUSED_CONTRACT_MANIFEST MWG_FUSED_REGISTRATION_MODULE
fi

write_status() {
  local status_path="$1"
  local run_id="$2"
  local state="$3"
  local outdir="$4"
  local detail="${5:-}"
  local pid="${6:-}"
  python3 - "$status_path" "$run_id" "$state" "$outdir" "$detail" "$pid" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status_path, run_id, state, outdir, detail, pid = sys.argv[1:7]
payload = {
    "schema_version": "mwg-four-arm-launch-status-v1",
    "run_id": run_id,
    "state": state,
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "outdir": outdir,
    "detail": detail,
}
if pid:
    payload["pid"] = int(pid)
path = Path(status_path)
path.parent.mkdir(parents=True, exist_ok=True)
tmp = path.with_suffix(path.suffix + ".tmp")
tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
tmp.replace(path)
PY
}

if [[ "${1:-}" != "--internal" ]]; then
  TS="$(date -u +%Y%m%dT%H%M%SZ)"
  RUN_ID="${RUN_ID:-ASI2_four_arm_lifetime_${TS}}"
  OUTDIR="${OUTDIR:-results/${RUN_ID}}"
  WRAPPER_LOG="${WRAPPER_LOG:-logs/${RUN_ID}.log}"
  STATUS="${STATUS:-logs/${RUN_ID}.status.json}"
  mkdir -p "$OUTDIR" "$(dirname "$WRAPPER_LOG")" "$(dirname "$STATUS")"

  PROBE_ARGS=(--output "$OUTDIR/toolchain_probe.json")
  if [[ "$FULL_EVIDENCE" == "1" ]]; then
    PROBE_ARGS+=(
      --require-all
      --op-library "$MWG_FUSED_OP_LIBRARY"
      --contract-manifest "$MWG_FUSED_CONTRACT_MANIFEST"
    )
  fi
  set +e
  bash scripts/probe_ascend_custom_op_toolchain.sh "${PROBE_ARGS[@]}" \
    >"$OUTDIR/toolchain_probe.stdout.json" 2>"$OUTDIR/toolchain_probe.stderr.log"
  PROBE_RC=$?
  set -e
  if [[ "$FULL_EVIDENCE" == "1" && "$PROBE_RC" -ne 0 ]]; then
    write_status "$STATUS" "$RUN_ID" "refused" "$OUTDIR" \
      "full evidence prerequisites failed; see toolchain_probe.json"
    echo "refusing FULL_EVIDENCE launch: prerequisite probe failed" >&2
    exit 2
  fi

  write_status "$STATUS" "$RUN_ID" "launching" "$OUTDIR" \
    "background process not started yet"
  export RUN_ID OUTDIR WRAPPER_LOG STATUS FULL_EVIDENCE ARMS DEVICE D M RANK
  export CONTROLLER_HIDDEN BATCH SEQ DTYPE AMPLITUDE WARMUP ITERS REPEATS SEED
  export COUNTER_METRICS PROJECT_ROOT
  nohup bash "$0" --internal >"$WRAPPER_LOG" 2>&1 < /dev/null &
  PID=$!
  write_status "$STATUS" "$RUN_ID" "running" "$OUTDIR" "detached" "$PID"
  echo "ASI2 four-arm lifetime benchmark detached"
  echo "pid=$PID"
  echo "run_id=$RUN_ID"
  echo "outdir=$OUTDIR"
  echo "wrapper_log=$WRAPPER_LOG"
  echo "status=$STATUS"
  echo "full_evidence=$FULL_EVIDENCE"
  exit 0
fi

RUN_ID="${RUN_ID:?RUN_ID is required for internal execution}"
OUTDIR="${OUTDIR:?OUTDIR is required for internal execution}"
WRAPPER_LOG="${WRAPPER_LOG:?WRAPPER_LOG is required for internal execution}"
STATUS="${STATUS:?STATUS is required for internal execution}"

on_exit() {
  local rc=$?
  if [[ "$rc" -eq 0 ]]; then
    write_status "$STATUS" "$RUN_ID" "done" "$OUTDIR" "all requested runs completed"
  else
    write_status "$STATUS" "$RUN_ID" "failed" "$OUTDIR" "exit_code=${rc}"
  fi
  return "$rc"
}
trap on_exit EXIT

write_status "$STATUS" "$RUN_ID" "running" "$OUTDIR" "baseline timing"

COMMON_ARGS=(
  --device "$DEVICE"
  --d "$D"
  --m "$M"
  --rank "$RANK"
  --controller-hidden "$CONTROLLER_HIDDEN"
  --batch "$BATCH"
  --seq "$SEQ"
  --dtype "$DTYPE"
  --amplitude "$AMPLITUDE"
  --warmup "$WARMUP"
  --iters "$ITERS"
  --repeats "$REPEATS"
  --seed "$SEED"
)
FUSED_ARGS=()
if [[ "$FULL_EVIDENCE" == "1" ]]; then
  FUSED_ARGS=(
    --op-library "$MWG_FUSED_OP_LIBRARY"
    --fused-contract-manifest "$MWG_FUSED_CONTRACT_MANIFEST"
    --fused-registration-module "$MWG_FUSED_REGISTRATION_MODULE"
  )
fi

python3 experiments/mwg_four_arm_lifetime_benchmark.py \
  "${COMMON_ARGS[@]}" \
  "${FUSED_ARGS[@]}" \
  --arms "$ARMS" \
  --run-label "$RUN_ID:baseline" \
  --output "$OUTDIR/four_arm_baseline.json"

if [[ "$FULL_EVIDENCE" == "1" ]]; then
  write_status "$STATUS" "$RUN_ID" "running" "$OUTDIR" "msprof counter passes"
  MSPROF="$(python3 - "$OUTDIR/toolchain_probe.json" <<'PY'
import json
import sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["tools"]["msprof"])
PY
)"
  if [[ -z "$MSPROF" || ! -x "$MSPROF" ]]; then
    echo "validated msprof path disappeared: $MSPROF" >&2
    exit 3
  fi

  mkdir -p "$OUTDIR/counter_bench" "$OUTDIR/msprof"
  IFS=',' read -r -a METRIC_ARRAY <<<"$COUNTER_METRICS"
  IFS=',' read -r -a ARM_ARRAY <<<"$ARMS"
  for metric in "${METRIC_ARRAY[@]}"; do
    metric="${metric//[[:space:]]/}"
    [[ -n "$metric" ]] || continue
    for arm in "${ARM_ARRAY[@]}"; do
      arm="${arm//[[:space:]]/}"
      [[ -n "$arm" ]] || continue
      PAIR_ID="${RUN_ID}:${metric}"
      BENCH_OUTPUT="$OUTDIR/counter_bench/${metric}_${arm}.json"
      PROFILE_OUTPUT="$OUTDIR/msprof/${metric}_${arm}"
      BENCH_COMMAND=(
        python3 experiments/mwg_four_arm_lifetime_benchmark.py
        "${COMMON_ARGS[@]}"
        "${FUSED_ARGS[@]}"
        --arms "$arm"
        --run-label "$RUN_ID:msprof:${metric}:${arm}"
        --counter-metric "$metric"
        --counter-pair-id "$PAIR_ID"
        --output "$BENCH_OUTPUT"
      )
      printf -v APPLICATION '%q ' "${BENCH_COMMAND[@]}"
      "$MSPROF" \
        --application="$APPLICATION" \
        --output="$PROFILE_OUTPUT" \
        --aic-metrics="$metric" \
        --task-time=on \
        --sys-hardware-mem=on
    done
  done
fi

write_status "$STATUS" "$RUN_ID" "running" "$OUTDIR" "summarization"
python3 experiments/summarize_four_arm_lifetime.py \
  "$OUTDIR" \
  --output "$OUTDIR/four_arm_summary.json" \
  --markdown "$OUTDIR/four_arm_summary.md" \
  --strict

echo "run_id=$RUN_ID complete"
echo "summary=$OUTDIR/four_arm_summary.json"
