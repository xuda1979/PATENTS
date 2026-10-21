#!/usr/bin/env bash
# Safe, bounded ASI3 integrity rerun.
#
# Remote detached launch (no browser or S3 dependency):
#   cd /root/work/filestorage/mwg-ew-transformer-research
#   nohup bash scripts/run_ASI3_integrity_rerun_when_free.sh \
#     >/tmp/mwg_asi3_integrity_launcher.log 2>&1 </dev/null &
#
# The script never resets an NPU or signals an unrelated process.  It waits for
# devices 0 and 1 to have an empty npu-smi process table for three consecutive
# checks and verifies their free-memory state with a tiny torch_npu allocation.

set -Eeuo pipefail
umask 077

if [[ "${1:-}" == "--help" ]]; then
  sed -n '2,12p' "$0"
  exit 0
elif [[ "$#" -ne 0 ]]; then
  echo "ERROR: unexpected argument: $1 (only --help is supported)" >&2
  exit 2
fi

PROJECT_ROOT="${PROJECT_ROOT:-/root/work/filestorage/mwg-ew-transformer-research}"
MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"
TRAIN_TEXTS="${TRAIN_TEXTS:-$PROJECT_ROOT/data/heldout/router_train.txt}"
EVAL_TEXTS="${EVAL_TEXTS:-$PROJECT_ROOT/data/heldout/router_eval.txt}"
OUTPUT_ROOT="${ASI3_INTEGRITY_OUTPUT_ROOT:-$PROJECT_ROOT/results}"

WAIT_SECONDS="${ASI3_MAX_WAIT_SECONDS:-43200}"
WAIT_CHECK_SECONDS="${ASI3_WAIT_CHECK_SECONDS:-60}"
CANARY_WAIT_SECONDS="${ASI3_CANARY_WAIT_SECONDS:-600}"
CANARY_CHECK_SECONDS="${ASI3_CANARY_CHECK_SECONDS:-10}"
NPU_QUERY_TIMEOUT="${ASI3_NPU_QUERY_TIMEOUT_SECONDS:-20}"
NPU_PROBE_TIMEOUT="${ASI3_NPU_PROBE_TIMEOUT_SECONDS:-90}"
MIN_FREE_FRACTION="${ASI3_MIN_FREE_FRACTION:-0.90}"
FREE_REQUIRED=3

PREFLIGHT_TIMEOUT="${ASI3_PREFLIGHT_TIMEOUT_SECONDS:-300}"
SYSTEMS_TIMEOUT="${ASI3_SYSTEMS_TIMEOUT_SECONDS:-600}"
CANARY_TIMEOUT="${ASI3_CANARY_TIMEOUT_SECONDS:-1200}"
EVAL_TIMEOUT="${ASI3_EVAL_TIMEOUT_SECONDS:-900}"

LAYER="${ASI3_CANARY_LAYER:-16}"
CANARY_RANK="${ASI3_CANARY_RANK:-32}"
CANARY_STEPS="${ASI3_CANARY_STEPS:-2}"
CANARY_EVAL_BATCHES="${ASI3_CANARY_EVAL_BATCHES:-2}"
CANARY_ACTIVATION_BATCHES="${ASI3_CANARY_ACTIVATION_BATCHES:-2}"
CANARY_SEED="${ASI3_CANARY_SEED:-20260823}"

validate_uint() {
  local name="$1"
  local value="$2"
  local minimum="$3"
  local maximum="$4"
  if [[ ! "$value" =~ ^[0-9]+$ ]] || (( value < minimum || value > maximum )); then
    echo "ERROR: $name must be an integer in [$minimum, $maximum], got: $value" >&2
    exit 2
  fi
}

validate_uint ASI3_MAX_WAIT_SECONDS "$WAIT_SECONDS" 60 86400
validate_uint ASI3_WAIT_CHECK_SECONDS "$WAIT_CHECK_SECONDS" 5 600
validate_uint ASI3_CANARY_WAIT_SECONDS "$CANARY_WAIT_SECONDS" 30 3600
validate_uint ASI3_CANARY_CHECK_SECONDS "$CANARY_CHECK_SECONDS" 2 120
validate_uint ASI3_NPU_QUERY_TIMEOUT_SECONDS "$NPU_QUERY_TIMEOUT" 5 120
validate_uint ASI3_NPU_PROBE_TIMEOUT_SECONDS "$NPU_PROBE_TIMEOUT" 10 300
validate_uint ASI3_PREFLIGHT_TIMEOUT_SECONDS "$PREFLIGHT_TIMEOUT" 30 900
validate_uint ASI3_SYSTEMS_TIMEOUT_SECONDS "$SYSTEMS_TIMEOUT" 60 1800
validate_uint ASI3_CANARY_TIMEOUT_SECONDS "$CANARY_TIMEOUT" 120 3600
validate_uint ASI3_EVAL_TIMEOUT_SECONDS "$EVAL_TIMEOUT" 120 3600
validate_uint ASI3_CANARY_LAYER "$LAYER" 0 255
validate_uint ASI3_CANARY_RANK "$CANARY_RANK" 4 128
# This hard cap is deliberate: this launcher is an integrity canary, never a
# substitute for the historical 5k-step quality run.
validate_uint ASI3_CANARY_STEPS "$CANARY_STEPS" 1 32
validate_uint ASI3_CANARY_EVAL_BATCHES "$CANARY_EVAL_BATCHES" 1 8
validate_uint ASI3_CANARY_ACTIVATION_BATCHES "$CANARY_ACTIVATION_BATCHES" 1 8
validate_uint ASI3_CANARY_SEED "$CANARY_SEED" 0 2147483647

python3 - "$MIN_FREE_FRACTION" <<'PY'
import sys

value = float(sys.argv[1])
if not 0.50 <= value <= 1.0:
    raise SystemExit("ASI3_MIN_FREE_FRACTION must be in [0.50, 1.0]")
PY

if [[ ! -d "$PROJECT_ROOT" ]]; then
  echo "ERROR: project root is absent: $PROJECT_ROOT" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_PATH="$SCRIPT_DIR/$(basename "${BASH_SOURCE[0]}")"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="ASI3_integrity_rerun_${TS}_pid$$"
RUN_DIR="$OUTPUT_ROOT/$RUN_ID"
STATUS="$RUN_DIR/status.json"
LOG="$RUN_DIR/run.log"
MANIFEST="$RUN_DIR/artifact_manifest.json"
AVAILABILITY_LOG="$RUN_DIR/availability_checks.jsonl"
SNAPSHOT_DIR="$RUN_DIR/npu_snapshots"
PREFLIGHT_JSON="$RUN_DIR/preflight.json"
SYSTEMS_OUT="$RUN_DIR/systems"
CANARY_OUT="$RUN_DIR/causal_train"
EVAL_OUT="$RUN_DIR/causal_eval"
RUN_TMP="$RUN_DIR/tmp"

mkdir -p "$RUN_DIR" "$SNAPSHOT_DIR" "$SYSTEMS_OUT" "$CANARY_OUT" "$EVAL_OUT" "$RUN_TMP"

CURRENT_STAGE="initializing"
FINALIZED=0

write_status() {
  local state="$1"
  local stage="$2"
  local detail="${3:-}"
  python3 - "$STATUS" "$state" "$stage" "$detail" "$RUN_ID" "$RUN_DIR" "$LOG" "$MANIFEST" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
state, stage, detail, run_id, run_dir, log_path, manifest_path = sys.argv[2:9]
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except (FileNotFoundError, json.JSONDecodeError):
    payload = {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": now,
        "pid": os.getppid(),
        "run_dir": run_dir,
        "log": log_path,
        "artifact_manifest": manifest_path,
        "devices": [0, 1],
        "history": [],
    }
event = {"at": now, "state": state, "stage": stage}
if detail:
    event["detail"] = detail
payload["history"] = (payload.get("history", []) + [event])[-200:]
payload.update({"state": state, "stage": stage, "detail": detail, "updated_at": now})
tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
with tmp.open("w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)
    handle.write("\n")
    handle.flush()
    os.fsync(handle.fileno())
os.replace(tmp, path)
PY
}

init_manifest() {
  python3 - "$MANIFEST" "$RUN_ID" "$PROJECT_ROOT" "$MODEL_DIR" "$TRAIN_TEXTS" "$EVAL_TEXTS" "$SCRIPT_PATH" "$STATUS" "$LOG" <<'PY'
import hashlib
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
run_id, project_root, model_dir, train_texts, eval_texts, script_path, status, log = sys.argv[2:10]
script = Path(script_path)
payload = {
    "schema_version": 1,
    "run_id": run_id,
    "state": "created",
    "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "host": platform.node(),
    "project_root": project_root,
    "model_dir": model_dir,
    "train_texts": train_texts,
    "eval_texts": eval_texts,
    "status": status,
    "log": log,
    "launcher": {
        "path": script_path,
        "sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
        "pid": os.getppid(),
    },
    "commands": [],
    "inputs": {},
    "artifacts": [],
}
tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.replace(tmp, path)
PY
}

manifest_state() {
  local state="$1"
  local detail="${2:-}"
  python3 - "$MANIFEST" "$state" "$detail" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
payload["state"] = sys.argv[2]
payload["detail"] = sys.argv[3]
payload["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.replace(tmp, path)
PY
}

record_command() {
  local phase="$1"
  shift
  python3 - "$MANIFEST" "$phase" "$@" <<'PY'
import hashlib
import json
import os
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
phase = sys.argv[2]
argv = sys.argv[3:]
canonical = json.dumps(argv, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
entry = {
    "phase": phase,
    "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "argv": argv,
    "shell_escaped": shlex.join(argv),
    "argv_sha256": hashlib.sha256(canonical).hexdigest(),
}
payload = json.loads(path.read_text(encoding="utf-8"))
payload.setdefault("commands", []).append(entry)
tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.replace(tmp, path)
PY
}

record_input_hashes() {
  python3 - "$MANIFEST" "$PROJECT_ROOT" "$@" <<'PY'
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

manifest = Path(sys.argv[1])
root = Path(sys.argv[2])
files = [Path(value) for value in sys.argv[3:]]
payload = json.loads(manifest.read_text(encoding="utf-8"))
inputs = {}
for path in files:
    raw = path.read_bytes()
    try:
        display = str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        display = str(path)
    inputs[display] = {
        "path": str(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
payload["inputs"] = inputs
try:
    payload["git_commit"] = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
    ).strip()
except (OSError, subprocess.CalledProcessError):
    payload["git_commit"] = None
tmp = manifest.with_name(f".{manifest.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.replace(tmp, manifest)
PY
}

assert_inputs_unchanged() {
  python3 - "$MANIFEST" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
changed = []
for name, meta in payload.get("inputs", {}).items():
    path = Path(meta["path"])
    if not path.is_file():
        changed.append(f"missing:{name}")
        continue
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != meta["sha256"]:
        changed.append(f"sha256:{name}")
if changed:
    raise SystemExit("recorded inputs changed during run: " + ", ".join(changed))
PY
}

refresh_artifact_manifest() {
  python3 - "$MANIFEST" "$RUN_DIR" "$STATUS" "$LOG" <<'PY'
import hashlib
import json
import os
import sys
from pathlib import Path

manifest = Path(sys.argv[1])
run_dir = Path(sys.argv[2])
excluded = {manifest.resolve(), Path(sys.argv[3]).resolve(), Path(sys.argv[4]).resolve()}
artifacts = []
for path in sorted(run_dir.rglob("*")):
    if not path.is_file() or path.resolve() in excluded:
        continue
    if "pycache" in path.parts or path.name.endswith(".tmp"):
        continue
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    artifacts.append({
        "path": str(path.relative_to(run_dir)),
        "bytes": path.stat().st_size,
        "sha256": digest.hexdigest(),
    })
payload = json.loads(manifest.read_text(encoding="utf-8"))
payload["artifacts"] = artifacts
tmp = manifest.with_name(f".{manifest.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.replace(tmp, manifest)
PY
}

on_exit() {
  local rc=$?
  trap - EXIT INT TERM
  set +e
  if (( rc == 0 )); then
    if (( FINALIZED == 0 )); then
      write_status completed "$CURRENT_STAGE" "completed"
      manifest_state completed completed
    fi
  else
    write_status failed "$CURRENT_STAGE" "exit_code=$rc"
    manifest_state failed "stage=$CURRENT_STAGE;exit_code=$rc"
  fi
  refresh_artifact_manifest
  exit "$rc"
}
trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

init_manifest
write_status created "$CURRENT_STAGE" "run directory initialized"

echo "run_id=$RUN_ID"
echo "run_dir=$RUN_DIR"
echo "status=$STATUS"
echo "log=$LOG"
echo "artifact_manifest=$MANIFEST"
exec >>"$LOG" 2>&1

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ASI3 integrity rerun initialized"
echo "project_root=$PROJECT_ROOT"
echo "model_dir=$MODEL_DIR"
echo "train_texts=$TRAIN_TEXTS"
echo "eval_texts=$EVAL_TEXTS"
echo "wait_seconds=$WAIT_SECONDS"
echo "free_checks_required=$FREE_REQUIRED"

for required_command in python3 timeout npu-smi flock; do
  if ! command -v "$required_command" >/dev/null 2>&1; then
    echo "ERROR: required command is absent: $required_command" >&2
    exit 2
  fi
done

# Avoid two copies of this scheduler competing with each other.  This is only a
# cooperative launcher lock; NPU ownership still comes from the live probes.
exec 9>/tmp/mwg-ew-asi3-integrity-devices-0-1.lock
if ! flock -n 9; then
  echo "ERROR: another MWG-EW integrity scheduler holds the devices-0-1 lock" >&2
  exit 3
fi

parse_npu_processes() {
  local snapshot="$1"
  local parsed="$2"
  local device="$3"
  python3 - "$snapshot" "$parsed" "$device" <<'PY'
import json
import os
import re
import sys
from pathlib import Path

snapshot = Path(sys.argv[1])
parsed_path = Path(sys.argv[2])
device = int(sys.argv[3])
lines = snapshot.read_text(encoding="utf-8", errors="replace").splitlines()
header_seen = False
process_column = None
pids = set()
for line in lines:
    parts = line.split("|")
    header_column = next(
        (index for index, cell in enumerate(parts) if re.search(r"\bprocess\s*id\b", cell, re.I)),
        None,
    )
    if header_column is not None:
        header_seen = True
        process_column = header_column
        continue
    if process_column is not None and len(parts) > process_column:
        candidate = parts[process_column].strip()
        if re.fullmatch(r"[0-9]+", candidate) and int(candidate) > 0:
            pids.add(int(candidate))
    # Explicit fallback for ASI3 rows such as:
    #   | 0  0 | 25242 | python3 | ...
    match = re.match(r"^\s*\|\s*[0-9]+\s+[0-9]+\s*\|\s*([0-9]+)\s*\|", line)
    if match and int(match.group(1)) > 0:
        pids.add(int(match.group(1)))

no_process_phrase = any("no running processes" in line.lower() for line in lines)
parse_ok = header_seen or no_process_phrase
payload = {
    "device": device,
    "snapshot": str(snapshot),
    "process_header_seen": header_seen,
    "no_running_processes_phrase": no_process_phrase,
    "pids": sorted(pids),
    "free": bool(parse_ok and not pids),
}
tmp = parsed_path.with_name(f".{parsed_path.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.replace(tmp, parsed_path)
if not parse_ok:
    raise SystemExit(2)
raise SystemExit(0 if not pids else 1)
PY
}

probe_visible_devices() {
  local visible_devices="$1"
  local output_json="$2"
  timeout --signal=TERM --kill-after=10s "${NPU_PROBE_TIMEOUT}s" \
    env ASCEND_RT_VISIBLE_DEVICES="$visible_devices" \
    python3 - "$output_json" "$MIN_FREE_FRACTION" "$visible_devices" <<'PY'
import json
import os
import sys
from pathlib import Path

import torch
import torch_npu

output = Path(sys.argv[1])
minimum_free_fraction = float(sys.argv[2])
physical_devices = [int(item) for item in sys.argv[3].split(",") if item]
if not hasattr(torch, "npu") or not torch.npu.is_available():
    raise SystemExit("torch.npu is unavailable")
if torch.npu.device_count() < len(physical_devices):
    raise SystemExit(
        f"visible NPU count {torch.npu.device_count()} is smaller than requested {len(physical_devices)}"
    )
mem_get_info = getattr(torch.npu, "mem_get_info", None)
if mem_get_info is None:
    mem_get_info = getattr(getattr(torch_npu, "npu", object()), "mem_get_info", None)
if mem_get_info is None:
    raise SystemExit("torch_npu mem_get_info is unavailable; refusing an allocation-only free check")

devices = []
for logical_index, physical_index in enumerate(physical_devices):
    torch.npu.set_device(logical_index)
    free_bytes, total_bytes = mem_get_info(logical_index)
    fraction = float(free_bytes) / max(float(total_bytes), 1.0)
    if fraction < minimum_free_fraction:
        raise SystemExit(
            f"physical NPU {physical_index} free-memory fraction {fraction:.4f} "
            f"is below {minimum_free_fraction:.4f}"
        )
    tensor = torch.ones(1, device=f"npu:{logical_index}", dtype=torch.float32)
    tensor.add_(1.0)
    torch.npu.synchronize()
    if float(tensor.cpu().item()) != 2.0:
        raise SystemExit(f"tiny allocation check failed on physical NPU {physical_index}")
    del tensor
    torch.npu.empty_cache()
    devices.append({
        "logical_index": logical_index,
        "physical_index": physical_index,
        "free_bytes_before_probe": int(free_bytes),
        "total_bytes": int(total_bytes),
        "free_fraction_before_probe": fraction,
    })
payload = {"visible_devices": physical_devices, "devices": devices, "ok": True}
tmp = output.with_name(f".{output.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.replace(tmp, output)
PY
}

record_availability() {
  local label="$1"
  local attempt="$2"
  local free="$3"
  local consecutive="$4"
  local probe_json="${5:-}"
  shift 5 || true
  python3 - "$AVAILABILITY_LOG" "$label" "$attempt" "$free" "$consecutive" "$probe_json" "$@" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
label = sys.argv[2]
attempt = int(sys.argv[3])
is_free = sys.argv[4] == "1"
consecutive = int(sys.argv[5])
probe_path = Path(sys.argv[6]) if sys.argv[6] else None
parsed_paths = [Path(value) for value in sys.argv[7:]]
payload = {
    "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "label": label,
    "attempt": attempt,
    "free": is_free,
    "consecutive_free": consecutive,
    "npu_smi": [json.loads(item.read_text(encoding="utf-8")) for item in parsed_paths if item.exists()],
    "torch_probe": json.loads(probe_path.read_text(encoding="utf-8")) if probe_path and probe_path.exists() else None,
}
line = json.dumps(payload, sort_keys=True) + "\n"
with path.open("a", encoding="utf-8") as handle:
    handle.write(line)
    handle.flush()
    os.fsync(handle.fileno())
PY
}

wait_for_devices() {
  local label="$1"
  local timeout_seconds="$2"
  local check_seconds="$3"
  shift 3
  local -a devices=("$@")
  local visible
  visible="$(IFS=,; echo "${devices[*]}")"
  local start="$SECONDS"
  local deadline=$(( start + timeout_seconds ))
  local attempt=0
  local consecutive=0

  while (( SECONDS < deadline )); do
    attempt=$(( attempt + 1 ))
    local all_process_tables_free=1
    local -a parsed_paths=()
    local device
    for device in "${devices[@]}"; do
      local snapshot="$SNAPSHOT_DIR/${label}_device${device}.latest.txt"
      local snapshot_tmp="$snapshot.tmp.$$"
      local parsed="$SNAPSHOT_DIR/${label}_device${device}.latest.json"
      if timeout --signal=TERM --kill-after=5s "${NPU_QUERY_TIMEOUT}s" \
          npu-smi info -i "$device" >"$snapshot_tmp" 2>&1; then
        mv -f "$snapshot_tmp" "$snapshot"
        set +e
        parse_npu_processes "$snapshot" "$parsed" "$device"
        local parse_rc=$?
        set -e
        if (( parse_rc != 0 )); then
          all_process_tables_free=0
        fi
      else
        mv -f "$snapshot_tmp" "$snapshot"
        all_process_tables_free=0
      fi
      parsed_paths+=("$parsed")
    done

    local probe_json="$SNAPSHOT_DIR/${label}_torch_probe.latest.json"
    local free=0
    if (( all_process_tables_free == 1 )); then
      set +e
      probe_visible_devices "$visible" "$probe_json"
      local probe_rc=$?
      set -e
      if (( probe_rc == 0 )); then
        free=1
      fi
    fi

    if (( free == 1 )); then
      consecutive=$(( consecutive + 1 ))
      for device in "${devices[@]}"; do
        cp "$SNAPSHOT_DIR/${label}_device${device}.latest.txt" \
          "$SNAPSHOT_DIR/${label}_free${consecutive}_attempt${attempt}_device${device}.txt"
      done
      cp "$probe_json" "$SNAPSHOT_DIR/${label}_free${consecutive}_attempt${attempt}_torch_probe.json"
    else
      consecutive=0
    fi

    record_availability "$label" "$attempt" "$free" "$consecutive" "$probe_json" "${parsed_paths[@]}"
    local elapsed=$(( SECONDS - start ))
    local remaining=$(( deadline - SECONDS ))
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] availability label=$label attempt=$attempt free=$free consecutive=$consecutive elapsed_s=$elapsed remaining_s=$remaining"
    write_status waiting "$CURRENT_STAGE" "label=$label;attempt=$attempt;consecutive=$consecutive/$FREE_REQUIRED;remaining_s=$remaining"

    if (( consecutive >= FREE_REQUIRED )); then
      echo "devices $visible passed $FREE_REQUIRED consecutive free checks"
      return 0
    fi
    if (( remaining <= 0 )); then
      break
    fi
    local sleep_seconds="$check_seconds"
    if (( sleep_seconds > remaining )); then
      sleep_seconds="$remaining"
    fi
    sleep "$sleep_seconds"
  done
  echo "ERROR: timed out after ${timeout_seconds}s waiting for devices $visible" >&2
  return 4
}

CURRENT_STAGE="wait_devices_0_1"
manifest_state waiting "devices 0,1"
write_status waiting "$CURRENT_STAGE" "requiring three consecutive process-free and memory-free checks"
wait_for_devices initial "$WAIT_SECONDS" "$WAIT_CHECK_SECONDS" 0 1

# Do not import torch_npu while another job owns either device.  The scheduler
# reaches this probe only after the process table, free-memory threshold, and
# tiny allocation checks have all passed three times.
CURRENT_STAGE="initial_dependency_probe"
write_status running "$CURRENT_STAGE" "checking torch_npu after devices are confirmed free"
timeout --signal=TERM --kill-after=10s 60s env ASCEND_RT_VISIBLE_DEVICES=0,1 python3 - <<'PY'
import torch
import torch_npu

if not hasattr(torch, "npu") or not torch.npu.is_available():
    raise SystemExit("torch.npu is unavailable")
if torch.npu.device_count() < 2:
    raise SystemExit(f"need two visible NPUs, found {torch.npu.device_count()}")
print("torch", torch.__version__)
print("torch_npu", getattr(torch_npu, "__version__", "unknown"))
print("visible_npu_count", torch.npu.device_count())
PY

CURRENT_STAGE="preflight"
write_status running "$CURRENT_STAGE" "validating project/model/text/code/integrity/dependencies"
manifest_state running "$CURRENT_STAGE"
cd "$PROJECT_ROOT"

REQUIRED_FILES=(
  "$SCRIPT_PATH"
  "$PROJECT_ROOT/experiments/mwg_transformer_ASI3_benchmark.py"
  "$PROJECT_ROOT/experiments/mwg_quality_distillation.py"
  "$PROJECT_ROOT/experiments/mwg_ppl_patch_eval.py"
  "$TRAIN_TEXTS"
  "$EVAL_TEXTS"
  "$MODEL_DIR/config.json"
)
for required_file in "${REQUIRED_FILES[@]}"; do
  if [[ ! -s "$required_file" ]]; then
    echo "ERROR: required non-empty file is absent: $required_file" >&2
    exit 2
  fi
done

INPUT_FILES=("${REQUIRED_FILES[@]}")
for optional_model_file in \
  "$MODEL_DIR/model.safetensors.index.json" \
  "$MODEL_DIR/tokenizer.json" \
  "$MODEL_DIR/tokenizer_config.json" \
  "$MODEL_DIR/generation_config.json"; do
  if [[ -f "$optional_model_file" ]]; then
    INPUT_FILES+=("$optional_model_file")
  fi
done
record_input_hashes "${INPUT_FILES[@]}"

PYCOMPILE_CMD=(
  timeout --signal=TERM --kill-after=10s "${PREFLIGHT_TIMEOUT}s"
  env "PYTHONPYCACHEPREFIX=$RUN_DIR/pycache" python3 -m py_compile
  experiments/mwg_transformer_ASI3_benchmark.py
  experiments/mwg_quality_distillation.py
  experiments/mwg_ppl_patch_eval.py
)
record_command preflight_py_compile "${PYCOMPILE_CMD[@]}"
"${PYCOMPILE_CMD[@]}"

# Re-run the causal and checkpoint-loader invariants on ASI3 without requiring
# pytest in the training image.  The full pytest suite remains a local release
# gate; this is the dependency-free remote integrity counterpart.
record_command preflight_causal_integrity \
  timeout --signal=TERM --kill-after=10s "${PREFLIGHT_TIMEOUT}s" \
  env "PYTHONDONTWRITEBYTECODE=1" "TMPDIR=$RUN_TMP" python3 - "$PROJECT_ROOT"
timeout --signal=TERM --kill-after=10s "${PREFLIGHT_TIMEOUT}s" \
  env "PYTHONDONTWRITEBYTECODE=1" "TMPDIR=$RUN_TMP" \
  python3 - "$PROJECT_ROOT" <<'PY'
import json
import os
import sys
import tempfile
from pathlib import Path

import torch

project = Path(sys.argv[1])
sys.path.insert(0, str(project / "experiments"))
from mwg_ppl_patch_eval import load_student
from mwg_quality_distillation import LowRankFFN

generator = torch.Generator(device="cpu").manual_seed(7)

def matrix(*shape: int) -> torch.Tensor:
    return 0.1 * torch.randn(*shape, generator=generator)

factors = {
    "up": (matrix(8, 4), matrix(4, 12)),
    "gate": (matrix(8, 4), matrix(4, 12)),
    "down": (matrix(12, 4), matrix(4, 8)),
}
torch.manual_seed(11)
model = LowRankFFN(
    factors,
    dtype=torch.float32,
    generator="token_expert_residual",
    generator_hidden=10,
    residual_rank=3,
    scale_amplitude=0.2,
    basis_count=3,
).eval()

with torch.no_grad():
    x = torch.randn(2, 7, model.d)
    torch.testing.assert_close(model(x)[:, :4], model(x[:, :4]), rtol=1e-5, atol=1e-6)
    target = torch.randn(1, 6, model.d)
    unrelated = 20.0 * torch.randn(1, 6, model.d)
    torch.testing.assert_close(
        model(target), model(torch.cat([target, unrelated], dim=0))[:1], rtol=1e-5, atol=1e-6
    )

init = {
    "d": model.d,
    "m": model.m,
    "rank": model.rank,
    "generator_mode": model.generator_mode,
    "generator_hidden": model.generator_hidden,
    "residual_rank": model.residual_rank,
    "scale_amplitude": model.scale_amplitude,
    "basis_count": model.basis_count,
}
with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as tmp_dir:
    checkpoint = Path(tmp_dir) / "token_expert_residual.pt"
    torch.save({"init": init, "state_dict": model.state_dict()}, checkpoint)
    loaded, _payload = load_student(checkpoint, torch.device("cpu"), torch.float32)
    probe = torch.randn(2, 5, model.d)
    with torch.no_grad():
        torch.testing.assert_close(loaded(probe), model(probe), rtol=1e-5, atol=1e-6)

print(json.dumps({"event": "causal_integrity_ok", "student": model.generator_mode}))
PY

timeout --signal=TERM --kill-after=10s "${PREFLIGHT_TIMEOUT}s" \
  env ASCEND_RT_VISIBLE_DEVICES=0,1 \
  python3 - "$PREFLIGHT_JSON" "$PROJECT_ROOT" "$MODEL_DIR" "$TRAIN_TEXTS" "$EVAL_TEXTS" "$LAYER" <<'PY'
import hashlib
import importlib.metadata
import json
import os
import sys
from pathlib import Path

import torch
import torch_npu
from safetensors import safe_open
from transformers import AutoConfig, AutoTokenizer

out = Path(sys.argv[1])
project = Path(sys.argv[2])
model_dir = Path(sys.argv[3])
train_path = Path(sys.argv[4])
eval_path = Path(sys.argv[5])
layer = int(sys.argv[6])

def lines(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

train = lines(train_path)
evaluation = lines(eval_path)
overlap = sorted(set(train) & set(evaluation))
if not train or not evaluation:
    raise SystemExit("router train/eval text must both be non-empty")
if overlap:
    raise SystemExit(f"router train/eval exact-line overlap: {len(overlap)}")

config = AutoConfig.from_pretrained(str(model_dir), trust_remote_code=True, local_files_only=True)
tokenizer = AutoTokenizer.from_pretrained(str(model_dir), trust_remote_code=True, local_files_only=True)
num_layers = int(getattr(config, "num_hidden_layers", 0))
if layer >= num_layers:
    raise SystemExit(f"layer {layer} is outside model with {num_layers} layers")
weight_files = sorted(model_dir.glob("*.safetensors")) + sorted(model_dir.glob("pytorch_model*.bin"))
if not weight_files:
    raise SystemExit("no model weights found")
if not hasattr(torch, "npu") or not torch.npu.is_available() or torch.npu.device_count() < 2:
    raise SystemExit("two torch_npu devices are required")

payload = {
    "ok": True,
    "project_root": str(project),
    "model_dir": str(model_dir),
    "model_type": getattr(config, "model_type", None),
    "num_hidden_layers": num_layers,
    "tokenizer_class": type(tokenizer).__name__,
    "weight_files": [
        {"path": str(path), "bytes": path.stat().st_size, "mtime_ns": path.stat().st_mtime_ns}
        for path in weight_files
    ],
    "texts": {
        "train": {"path": str(train_path), "lines": len(train), "unique": len(set(train)), "sha256": hashlib.sha256(train_path.read_bytes()).hexdigest()},
        "eval": {"path": str(eval_path), "lines": len(evaluation), "unique": len(set(evaluation)), "sha256": hashlib.sha256(eval_path.read_bytes()).hexdigest()},
        "exact_line_overlap": len(overlap),
    },
    "dependencies": {
        "python": sys.version.split()[0],
        "torch": torch.__version__,
        "torch_npu": getattr(torch_npu, "__version__", "unknown"),
        "transformers": importlib.metadata.version("transformers"),
        "safetensors": importlib.metadata.version("safetensors"),
        "visible_npu_count": torch.npu.device_count(),
    },
}
tmp = out.with_name(f".{out.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.replace(tmp, out)
print(json.dumps({"event": "preflight_ok", "model_type": payload["model_type"], "train_lines": len(train), "eval_lines": len(evaluation)}))
PY

assert_inputs_unchanged
write_status running "$CURRENT_STAGE" "preflight passed"

run_logged_command() {
  local phase="$1"
  local phase_log="$2"
  shift 2
  CURRENT_STAGE="$phase"
  record_command "$phase" "$@"
  write_status running "$phase" "command started; log=$phase_log"
  set +e
  "$@" 2>&1 | tee -a "$phase_log"
  local -a pipeline_status=("${PIPESTATUS[@]}")
  set -e
  local rc="${pipeline_status[0]}"
  if (( rc == 0 && pipeline_status[1] != 0 )); then
    rc="${pipeline_status[1]}"
  fi
  if (( rc != 0 )); then
    echo "ERROR: phase $phase failed with exit code $rc" >&2
    return "$rc"
  fi
}

SYSTEMS_CMD=(
  timeout --signal=TERM --kill-after=30s "${SYSTEMS_TIMEOUT}s"
  env
  ASCEND_RT_VISIBLE_DEVICES=0,1
  PYTORCH_NPU_ALLOC_CONF=max_split_size_mb:256
  HCCL_CONNECT_TIMEOUT=300
  OMP_NUM_THREADS=1
  "TMPDIR=$RUN_TMP"
  python3 -m torch.distributed.run --standalone --nproc_per_node=2
  experiments/mwg_transformer_ASI3_benchmark.py
  --preset tiny
  --env-label ASI3_integrity
  --ranks 8
  --warmup 1
  --iters 1
  --train-iters 1
  --comm-iters 1
  --seed "$CANARY_SEED"
  --measure-integrated-sync
  --outdir "$SYSTEMS_OUT"
)
CURRENT_STAGE="wait_devices_0_1_prelaunch"
write_status waiting "$CURRENT_STAGE" "rechecking devices after preflight"
wait_for_devices systems_prelaunch "$CANARY_WAIT_SECONDS" "$CANARY_CHECK_SECONDS" 0 1
assert_inputs_unchanged
run_logged_command systems_ddp_integrated_sync "$RUN_DIR/systems.log" "${SYSTEMS_CMD[@]}"

SYSTEMS_VALIDATION="$SYSTEMS_OUT/schema_validation.json"
python3 - "$SYSTEMS_OUT" "$SYSTEMS_VALIDATION" <<'PY'
import json
import math
import os
import sys
from pathlib import Path

outdir = Path(sys.argv[1])
validation_path = Path(sys.argv[2])
files = [path for path in outdir.glob("ASI3_integrity_mwg_transformer_*.json") if path != validation_path]
if len(files) != 1:
    raise SystemExit(f"expected exactly one systems JSON, found {len(files)}: {files}")
source = files[0]
payload = json.loads(source.read_text(encoding="utf-8"))
if payload.get("env", {}).get("world_size") != 2:
    raise SystemExit("systems JSON world_size is not 2")
if payload.get("env", {}).get("backend") != "hccl":
    raise SystemExit("systems JSON backend is not hccl")
integrated = payload.get("config", {}).get("integrated_gradient_sync", {})
if integrated.get("enabled") is not True or integrated.get("optimizer_step_included") is not False:
    raise SystemExit("integrated-sync configuration is missing or incorrect")
rows = payload.get("results", {})
for name in ("dense", "mwg_r8"):
    row = rows.get(name)
    if not isinstance(row, dict):
        raise SystemExit(f"missing result row: {name}")
    timing = row.get("train_integrated_sync")
    if not isinstance(timing, dict):
        raise SystemExit(f"missing train_integrated_sync timing: {name}")
    mean_ms = timing.get("mean_ms")
    if not isinstance(mean_ms, (int, float)) or not math.isfinite(mean_ms) or mean_ms <= 0:
        raise SystemExit(f"invalid integrated-sync mean_ms for {name}: {mean_ms}")
result = {
    "ok": True,
    "source_json": str(source),
    "world_size": 2,
    "backend": "hccl",
    "dense_train_integrated_sync_ms": rows["dense"]["train_integrated_sync"]["mean_ms"],
    "mwg_r8_train_integrated_sync_ms": rows["mwg_r8"]["train_integrated_sync"]["mean_ms"],
    "mwg_r8_speedup_x": rows["mwg_r8"]["train_integrated_sync_speedup_x"],
}
tmp = validation_path.with_name(f".{validation_path.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.replace(tmp, validation_path)
print(json.dumps({"event": "systems_schema_valid", **result}))
PY
write_status running systems_validated "integrated DDP schema valid"

# The DDP process has exited, but re-check device 0 before loading a pretrained
# model.  This catches a competing job that starts between phases.
CURRENT_STAGE="wait_device_0_for_canary"
write_status waiting "$CURRENT_STAGE" "rechecking device 0 after systems smoke"
wait_for_devices canary "$CANARY_WAIT_SECONDS" "$CANARY_CHECK_SECONDS" 0

assert_inputs_unchanged
CANARY_CMD=(
  timeout --signal=TERM --kill-after=30s "${CANARY_TIMEOUT}s"
  env
  ASCEND_RT_VISIBLE_DEVICES=0
  PYTORCH_NPU_ALLOC_CONF=max_split_size_mb:256
  OMP_NUM_THREADS=1
  HF_HUB_OFFLINE=1
  TRANSFORMERS_OFFLINE=1
  TOKENIZERS_PARALLELISM=false
  "TMPDIR=$RUN_TMP"
  python3 experiments/mwg_quality_distillation.py
  --model-dir "$MODEL_DIR"
  --layer "$LAYER"
  --ranks "$CANARY_RANK"
  --svd-method pca_lowrank
  --svd-oversample 8
  --svd-niter 1
  --batch 1
  --seq 32
  --steps "$CANARY_STEPS"
  --eval-batches "$CANARY_EVAL_BATCHES"
  --log-every 1
  --lr 0.0003
  --students token_expert_residual
  --generator-hidden 64
  --residual-rank 4
  --scale-amplitude 0.05
  --basis-count 2
  --basis-noise 0.01
  --activation-source text
  --texts "$TRAIN_TEXTS"
  --activation-max-batches "$CANARY_ACTIVATION_BATCHES"
  --activation-text-batch 1
  --activation-seq 64
  --activation-log-every 1
  --save-students
  --dtype fp32
  --seed "$CANARY_SEED"
  --outdir "$CANARY_OUT"
)
run_logged_command causal_token_expert_residual_canary "$RUN_DIR/causal_train.log" "${CANARY_CMD[@]}"

CHECKPOINT="$CANARY_OUT/checkpoints/mwg_token_expert_residual_r${CANARY_RANK}.pt"
CANARY_VALIDATION="$CANARY_OUT/schema_validation.json"
python3 - "$CANARY_OUT" "$CHECKPOINT" "$CANARY_VALIDATION" "$CANARY_RANK" "$CANARY_STEPS" <<'PY'
import json
import math
import os
import sys
from pathlib import Path

import torch

outdir = Path(sys.argv[1])
checkpoint = Path(sys.argv[2])
validation_path = Path(sys.argv[3])
rank = int(sys.argv[4])
steps = int(sys.argv[5])
files = [path for path in outdir.glob("mwg_quality_distillation_*.json") if path != validation_path]
if len(files) != 1:
    raise SystemExit(f"expected exactly one canary JSON, found {len(files)}: {files}")
source = files[0]
payload = json.loads(source.read_text(encoding="utf-8"))
config = payload.get("config", {})
if config.get("students") != ["token_expert_residual"]:
    raise SystemExit(f"unexpected students: {config.get('students')}")
if config.get("activation_source") != "text" or config.get("steps") != steps:
    raise SystemExit("canary config does not record explicit text activation and bounded steps")
row_name = f"mwg_token_expert_residual_r{rank}"
row = payload.get("results", {}).get(row_name)
if not isinstance(row, dict):
    raise SystemExit(f"missing canary result: {row_name}")
for key in ("mse", "relative_mse", "cosine"):
    value = row.get("metrics", {}).get(key)
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise SystemExit(f"invalid metric {key}: {value}")
if not checkpoint.is_file():
    raise SystemExit(f"checkpoint is missing: {checkpoint}")
try:
    ckpt = torch.load(checkpoint, map_location="cpu", weights_only=False)
except TypeError:
    ckpt = torch.load(checkpoint, map_location="cpu")
if ckpt.get("init", {}).get("generator_mode") != "token_expert_residual":
    raise SystemExit("checkpoint generator_mode is not token_expert_residual")
if int(ckpt.get("init", {}).get("rank", -1)) != rank:
    raise SystemExit("checkpoint rank mismatch")
result = {
    "ok": True,
    "source_json": str(source),
    "checkpoint": str(checkpoint),
    "student": row_name,
    "steps": steps,
    "metrics": row["metrics"],
}
tmp = validation_path.with_name(f".{validation_path.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.replace(tmp, validation_path)
print(json.dumps({"event": "causal_canary_schema_valid", **result}))
PY
write_status running causal_canary_validated "token_expert_residual checkpoint schema valid"

# Loader compatibility was exercised by the focused preflight tests and the
# checkpoint schema above.  Evaluate only on the exact-line-disjoint router_eval
# file; do not use DEFAULT_TEXTS or the router_train activations here.
CURRENT_STAGE="wait_device_0_for_eval"
write_status waiting "$CURRENT_STAGE" "rechecking device 0 before held-out evaluation"
wait_for_devices eval "$CANARY_WAIT_SECONDS" "$CANARY_CHECK_SECONDS" 0
assert_inputs_unchanged
PPL_JSON="$EVAL_OUT/router_eval_ppl.json"
EVAL_CMD=(
  timeout --signal=TERM --kill-after=30s "${EVAL_TIMEOUT}s"
  env
  ASCEND_RT_VISIBLE_DEVICES=0
  PYTORCH_NPU_ALLOC_CONF=max_split_size_mb:256
  OMP_NUM_THREADS=1
  HF_HUB_OFFLINE=1
  TRANSFORMERS_OFFLINE=1
  TOKENIZERS_PARALLELISM=false
  "TMPDIR=$RUN_TMP"
  python3 experiments/mwg_ppl_patch_eval.py
  --model-dir "$MODEL_DIR"
  --patch "${LAYER}:${CHECKPOINT}"
  --texts "$EVAL_TEXTS"
  --require-texts
  --seq 64
  --text-batch 1
  --eval-batches 2
  --dtype fp32
  --out-json "$PPL_JSON"
)
run_logged_command causal_disjoint_router_eval "$RUN_DIR/causal_eval.log" "${EVAL_CMD[@]}"

EVAL_VALIDATION="$EVAL_OUT/schema_validation.json"
python3 - "$PPL_JSON" "$EVAL_VALIDATION" "$LAYER" "$CHECKPOINT" "$EVAL_TEXTS" "$CANARY_RANK" <<'PY'
import json
import math
import os
import sys
from pathlib import Path

source = Path(sys.argv[1])
validation = Path(sys.argv[2])
layer = sys.argv[3]
checkpoint = sys.argv[4]
eval_texts = sys.argv[5]
rank = int(sys.argv[6])
payload = json.loads(source.read_text(encoding="utf-8"))
for name in ("dense", "patched"):
    row = payload.get(name)
    if not isinstance(row, dict):
        raise SystemExit(f"missing PPL row: {name}")
    for key in ("loss", "ppl"):
        value = row.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise SystemExit(f"invalid {name}.{key}: {value}")
    if not isinstance(row.get("tokens"), int) or row["tokens"] <= 0:
        raise SystemExit(f"invalid {name}.tokens")
patch = payload.get("patches", {}).get(layer)
if not isinstance(patch, dict):
    raise SystemExit(f"missing patch metadata for layer {layer}")
if patch.get("path") != checkpoint or patch.get("student") != f"mwg_token_expert_residual_r{rank}":
    raise SystemExit(f"unexpected patch metadata: {patch}")
config = payload.get("config", {})
eval_lines = [line.strip() for line in Path(eval_texts).read_text(encoding="utf-8").splitlines() if line.strip()]
if config.get("texts") != eval_lines or config.get("require_texts") is not True:
    raise SystemExit("PPL config does not preserve explicit router_eval text")
result = {
    "ok": True,
    "source_json": str(source),
    "eval_texts": eval_texts,
    "patch": patch,
    "dense": payload["dense"],
    "patched": payload["patched"],
}
tmp = validation.with_name(f".{validation.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.replace(tmp, validation)
print(json.dumps({"event": "causal_router_eval_schema_valid", **result}))
PY

CURRENT_STAGE="completed"
manifest_state completed "all bounded integrity phases passed"
refresh_artifact_manifest
write_status completed "$CURRENT_STAGE" "all bounded integrity phases passed"
FINALIZED=1
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] completed"
echo "status=$STATUS"
echo "artifact_manifest=$MANIFEST"
