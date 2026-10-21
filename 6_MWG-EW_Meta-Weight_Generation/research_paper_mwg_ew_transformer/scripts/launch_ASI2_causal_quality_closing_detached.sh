#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
ENV_LABEL="${ENV_LABEL:-ASI2}"
MODEL_DIR="${MODEL_DIR:-/root/work/filestorage/Qwen2.5-1.5B-Instruct}"
TRAIN_TEXTS="${TRAIN_TEXTS:-$PROJECT_ROOT/data/quality/train.txt}"
EVAL_TEXTS="${EVAL_TEXTS:-$PROJECT_ROOT/data/quality/dev.txt}"
SPLIT_MANIFEST="${SPLIT_MANIFEST:-$PROJECT_ROOT/data/quality/manifest.json}"
DEVICES="${ASCEND_RT_VISIBLE_DEVICES:-0,1,2,3}"
NPROC_PER_NODE="${NPROC_PER_NODE:-4}"
SEEDS="${SEEDS:-2026 2027 2028}"
LAYER="${LAYER:-16}"
BASE_RANK="${BASE_RANK:-384}"
MATCHED_RANK="${MATCHED_RANK:-401}"
EFFECTIVE_RANK="${EFFECTIVE_RANK:-512}"
STUDENT_SPECS="${STUDENT_SPECS:-persistent:${BASE_RANK},token_diag_core:${BASE_RANK},persistent:${MATCHED_RANK},token_diag_core:${MATCHED_RANK},persistent:${EFFECTIVE_RANK}}"
STEPS="${STEPS:-5000}"
EVAL_BATCHES="${EVAL_BATCHES:-128}"
BATCH="${BATCH:-1}"
SEQ="${SEQ:-128}"
LOG_EVERY="${LOG_EVERY:-100}"
CHECKPOINT_EVERY="${CHECKPOINT_EVERY:-250}"
ACTIVATION_MAX_BATCHES="${ACTIVATION_MAX_BATCHES:-315}"
ACTIVATION_TEXT_BATCH="${ACTIVATION_TEXT_BATCH:-2}"
ACTIVATION_SEQ="${ACTIVATION_SEQ:-256}"
ACTIVATION_SEED="${ACTIVATION_SEED:-1729}"
FACTOR_SEED="${FACTOR_SEED:-1729}"
LR="${LR:-0.0002}"
DTYPE="${DTYPE:-fp32}"
NEAR_DUPLICATE_THRESHOLD="${NEAR_DUPLICATE_THRESHOLD:-0.82}"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="${RUN_ID:-asi2_causal_quality_closing_${TS}}"
RUN_DIR="${RUN_DIR:-$PROJECT_ROOT/results/$RUN_ID}"
LOG="${LOG:-$PROJECT_ROOT/logs/${RUN_ID}.log}"
STATUS="${STATUS:-$RUN_DIR/status.json}"
ARTIFACT_MANIFEST="${ARTIFACT_MANIFEST:-$RUN_DIR/artifact_manifest.json}"
CACHE_DIR="${CACHE_DIR:-$RUN_DIR/cache}"

usage() {
  cat <<'EOF'
Usage: bash scripts/launch_ASI2_causal_quality_detached.sh [--check|--worker]

The default mode validates explicit frozen train/dev inputs and starts one
detached ASI2 worker. --check performs only local file/configuration gates.
--worker is internal and runs the configured seed sweep in the foreground.
EOF
}

atomic_status() {
  local state="$1"
  local stage="$2"
  local detail="${3:-}"
  local pid="${4:-$$}"
  python3 - "$STATUS" "$state" "$stage" "$detail" "$pid" "$RUN_ID" "$RUN_DIR" "$LOG" "$ARTIFACT_MANIFEST" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
state, stage, detail, pid, run_id, run_dir, log, artifact_manifest = sys.argv[2:10]
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except (FileNotFoundError, json.JSONDecodeError):
    payload = {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": now,
        "history": [],
    }
event = {"at": now, "state": state, "stage": stage}
if detail:
    event["detail"] = detail
payload["history"] = (payload.get("history", []) + [event])[-200:]
payload.update({
    "state": state,
    "stage": stage,
    "detail": detail,
    "updated_at": now,
    "pid": int(pid),
    "run_dir": run_dir,
    "log": log,
    "artifact_manifest": artifact_manifest,
})
path.parent.mkdir(parents=True, exist_ok=True)
tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.replace(tmp, path)
PY
}

validate_uint() {
  local name="$1"
  local value="$2"
  local minimum="$3"
  if [[ ! "$value" =~ ^[0-9]+$ ]] || (( value < minimum )); then
    echo "ERROR: $name must be an integer >= $minimum, got: $value" >&2
    return 2
  fi
}

preflight() {
  validate_uint NPROC_PER_NODE "$NPROC_PER_NODE" 1
  validate_uint LAYER "$LAYER" 0
  validate_uint BASE_RANK "$BASE_RANK" 1
  validate_uint MATCHED_RANK "$MATCHED_RANK" 1
  validate_uint EFFECTIVE_RANK "$EFFECTIVE_RANK" 1
  validate_uint STEPS "$STEPS" 1
  validate_uint EVAL_BATCHES "$EVAL_BATCHES" 1
  validate_uint BATCH "$BATCH" 1
  validate_uint SEQ "$SEQ" 1
  validate_uint LOG_EVERY "$LOG_EVERY" 1
  validate_uint CHECKPOINT_EVERY "$CHECKPOINT_EVERY" 1
  validate_uint ACTIVATION_MAX_BATCHES "$ACTIVATION_MAX_BATCHES" 1
  validate_uint ACTIVATION_TEXT_BATCH "$ACTIVATION_TEXT_BATCH" 1
  validate_uint ACTIVATION_SEQ "$ACTIVATION_SEQ" 1
  validate_uint ACTIVATION_SEED "$ACTIVATION_SEED" 0
  validate_uint FACTOR_SEED "$FACTOR_SEED" 0
  if (( BASE_RANK == MATCHED_RANK || BASE_RANK == EFFECTIVE_RANK || MATCHED_RANK == EFFECTIVE_RANK )); then
    echo "ERROR: BASE_RANK, MATCHED_RANK, and EFFECTIVE_RANK must be distinct" >&2
    return 2
  fi
  if [[ ! "$RUN_ID" =~ ^[A-Za-z0-9_.-]+$ ]]; then
    echo "ERROR: unsafe RUN_ID: $RUN_ID" >&2
    return 2
  fi
  if [[ "$ENV_LABEL" != "ASI2" ]]; then
    echo "ERROR: this launcher is restricted to ENV_LABEL=ASI2" >&2
    return 2
  fi
  if [[ ! -d "$PROJECT_ROOT" ]]; then
    echo "ERROR: project root missing: $PROJECT_ROOT" >&2
    return 2
  fi
  cd "$PROJECT_ROOT"
  for path in \
    "$MODEL_DIR/config.json" \
    "$TRAIN_TEXTS" \
    "$EVAL_TEXTS" \
    "$SPLIT_MANIFEST" \
    experiments/mwg_quality_distillation.py \
    experiments/audit_quality_threeway_split.py; do
    if [[ ! -s "$path" ]]; then
      echo "ERROR: required non-empty input missing: $path" >&2
      return 2
    fi
  done
  if [[ "$TRAIN_TEXTS" == "$EVAL_TEXTS" ]]; then
    echo "ERROR: TRAIN_TEXTS and EVAL_TEXTS must differ" >&2
    return 2
  fi
  if ! compgen -G "$MODEL_DIR/*.safetensors" >/dev/null && ! compgen -G "$MODEL_DIR/*.bin" >/dev/null; then
    echo "ERROR: no model state file in $MODEL_DIR" >&2
    return 2
  fi
  local visible_count
  visible_count="$(python3 - "$DEVICES" <<'PY'
import sys
print(len([item for item in sys.argv[1].split(",") if item.strip()]))
PY
)"
  if (( visible_count != NPROC_PER_NODE )); then
    echo "ERROR: $visible_count visible device(s), but NPROC_PER_NODE=$NPROC_PER_NODE" >&2
    return 2
  fi
  python3 -m py_compile \
    experiments/mwg_quality_distillation.py \
    experiments/audit_quality_threeway_split.py
  python3 - "$MODEL_DIR/config.json" "$LAYER" "$BASE_RANK" "$MATCHED_RANK" "$EFFECTIVE_RANK" "$STUDENT_SPECS" "$DTYPE" <<'PY'
import json
import math
import sys
from pathlib import Path

config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
layer = int(sys.argv[2])
base, matched, effective = map(int, sys.argv[3:6])
spec_text, dtype = sys.argv[6:8]
if dtype not in {"fp16", "bf16", "fp32"}:
    raise SystemExit(f"unsupported fixed evidence dtype: {dtype}")
try:
    specs = {(mode, int(rank)) for mode, rank in (item.split(":", 1) for item in spec_text.split(","))}
except (TypeError, ValueError) as exc:
    raise SystemExit(f"invalid STUDENT_SPECS: {spec_text}") from exc
expected = {
    ("persistent", base),
    ("token_diag_core", base),
    ("persistent", matched),
    ("token_diag_core", matched),
    ("persistent", effective),
}
if specs != expected:
    raise SystemExit(f"STUDENT_SPECS must equal {sorted(expected)}, got {sorted(specs)}")
d = int(config["hidden_size"])
m = int(config["intermediate_size"])
layers = int(config["num_hidden_layers"])
if layer >= layers:
    raise SystemExit(f"LAYER={layer} is outside model range [0, {layers})")
if max(base, matched, effective) > min(d, m):
    raise SystemExit(f"requested rank exceeds matrix rank bound {min(d, m)}")
hidden = min(256, max(32, d // 8))
controller_elements = d * hidden + hidden + hidden * (3 * base) + 3 * base
factor_bytes = {"fp16": 2, "bf16": 2, "fp32": 4}[dtype]
matched_expected = base + math.ceil((controller_elements * 4) / (3 * (d + m) * factor_bytes))
if matched != matched_expected:
    raise SystemExit(
        f"MATCHED_RANK={matched} is not parameter-matched for dtype={dtype}; expected {matched_expected}"
    )
print(json.dumps({
    "event": "canonical_controls_verified",
    "d": d,
    "m": m,
    "dtype": dtype,
    "layer": layer,
    "base_rank": base,
    "matched_rank": matched,
    "effective_rank": effective,
}))
PY
  mkdir -p "$RUN_DIR" "$(dirname "$LOG")"
  python3 experiments/audit_quality_threeway_split.py \
    --manifest "$SPLIT_MANIFEST" \
    --out-json "$RUN_DIR/split_audit.json" \
    --out-md "$RUN_DIR/split_audit.md"
}

# Keep the strict path/hash binding separate from the generic split auditor.
verify_selected_splits() {
  python3 - "$SPLIT_MANIFEST" "$TRAIN_TEXTS" "$EVAL_TEXTS" "$NEAR_DUPLICATE_THRESHOLD" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
train_path = Path(sys.argv[2]).resolve()
eval_path = Path(sys.argv[3]).resolve()
threshold = float(sys.argv[4])
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
if abs(float(manifest["deduplication"]["near_duplicate_threshold"]) - threshold) > 1e-12:
    raise SystemExit("launcher near-duplicate threshold does not match frozen manifest")
for name, selected in (("train", train_path), ("dev", eval_path)):
    spec = manifest["outputs"][name]
    expected = Path(spec["path"])
    if not expected.is_absolute():
        expected = (Path.cwd() / expected).resolve()
    if selected != expected:
        raise SystemExit(f"{name} path mismatch: selected={selected} manifest={expected}")
    digest = hashlib.sha256(selected.read_bytes()).hexdigest()
    if digest != spec["sha256"]:
        raise SystemExit(f"{name} sha256 mismatch: {digest} != {spec['sha256']}")
print(json.dumps({"event": "selected_splits_verified", "train": str(train_path), "eval": str(eval_path)}))
PY
}

record_artifacts() {
  python3 - "$RUN_DIR" "$ARTIFACT_MANIFEST" "$RUN_ID" "$STATUS" <<'PY'
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

run_dir = Path(sys.argv[1])
out = Path(sys.argv[2])
run_id = sys.argv[3]
status = Path(sys.argv[4])
rows = []
for path in sorted(run_dir.rglob("*")):
    if not path.is_file() or path in {out, status} or "cache" in path.parts:
        continue
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    rows.append({
        "path": str(path.relative_to(run_dir)),
        "bytes": path.stat().st_size,
        "sha256": digest.hexdigest(),
    })
payload = {
    "schema_version": 1,
    "run_id": run_id,
    "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "artifacts": rows,
}
tmp = out.with_name(f".{out.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.replace(tmp, out)
PY
}

run_worker() {
  local rc=0
  trap 'rc=$?; trap - EXIT; if (( rc == 0 )); then atomic_status completed complete "all seeds complete"; else atomic_status failed worker "exit_code=$rc"; fi; exit "$rc"' EXIT
  atomic_status running preflight "validating ASI2 causal quality inputs"
  preflight
  verify_selected_splits
  cd "$PROJECT_ROOT"
  export ASCEND_RT_VISIBLE_DEVICES="$DEVICES"
  export PYTORCH_NPU_ALLOC_CONF="${PYTORCH_NPU_ALLOC_CONF:-max_split_size_mb:256}"
  export HCCL_CONNECT_TIMEOUT="${HCCL_CONNECT_TIMEOUT:-1800}"
  export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
  export HF_HUB_OFFLINE=1
  export TRANSFORMERS_OFFLINE=1
  export TOKENIZERS_PARALLELISM=false

  python3 - "$NPROC_PER_NODE" <<'PY'
import sys
import torch
import torch_npu

needed = int(sys.argv[1])
if not hasattr(torch, "npu") or not torch.npu.is_available():
    raise SystemExit("torch.npu is unavailable")
if torch.npu.device_count() < needed:
    raise SystemExit(f"need {needed} visible NPUs, found {torch.npu.device_count()}")
for index in range(needed):
    torch.npu.set_device(index)
    probe = torch.ones(1, device=f"npu:{index}")
    if float(probe.cpu().item()) != 1.0:
        raise SystemExit(f"NPU probe failed on visible index {index}")
print("torch", torch.__version__)
print("torch_npu", getattr(torch_npu, "__version__", "unknown"))
print("visible_npus", torch.npu.device_count())
PY

  local seed
  for seed in $SEEDS; do
    validate_uint seed "$seed" 0
    local outdir="$RUN_DIR/seed_${seed}"
    mkdir -p "$outdir"
    atomic_status running "seed_${seed}" "training canonical and matched persistent controls"
    python3 -m torch.distributed.run \
      --standalone \
      --nnodes=1 \
      --nproc_per_node="$NPROC_PER_NODE" \
      experiments/mwg_quality_distillation.py \
      --model-dir "$MODEL_DIR" \
      --env-label "$ENV_LABEL" \
      --layer "$LAYER" \
      --student-specs "$STUDENT_SPECS" \
      --batch "$BATCH" \
      --seq "$SEQ" \
      --steps "$STEPS" \
      --eval-batches "$EVAL_BATCHES" \
      --log-every "$LOG_EVERY" \
      --lr "$LR" \
      --activation-source text \
      --train-texts-file "$TRAIN_TEXTS" \
      --eval-texts-file "$EVAL_TEXTS" \
      --evidence-mode \
      --near-duplicate-threshold "$NEAR_DUPLICATE_THRESHOLD" \
      --activation-max-batches "$ACTIVATION_MAX_BATCHES" \
      --activation-text-batch "$ACTIVATION_TEXT_BATCH" \
      --activation-seq "$ACTIVATION_SEQ" \
      --activation-seed "$ACTIVATION_SEED" \
      --activation-log-every 25 \
      --factor-seed "$FACTOR_SEED" \
      --dtype "$DTYPE" \
      --seed "$seed" \
      --save-students \
      --checkpoint-every "$CHECKPOINT_EVERY" \
      --resume auto \
      --cache-dir "$CACHE_DIR" \
      --progress-json "$outdir/progress.json" \
      --outdir "$outdir"
    python3 - "$outdir" "$BASE_RANK" "$MATCHED_RANK" "$EFFECTIVE_RANK" <<'PY'
import json
import sys
from pathlib import Path

outdir = Path(sys.argv[1])
base, matched, effective = map(int, sys.argv[2:5])
reports = sorted(outdir.glob("mwg_quality_distillation_*.json"))
if not reports:
    raise SystemExit(f"missing quality report in {outdir}")
payload = json.loads(reports[-1].read_text(encoding="utf-8"))
expected = {
    f"persistent_low_rank_r{base}",
    f"mwg_token_diag_core_r{base}",
    f"persistent_low_rank_r{matched}",
    f"mwg_token_diag_core_r{matched}",
    f"persistent_low_rank_r{effective}",
}
static_expected = {f"static_svd_r{rank}" for rank in (base, matched, effective)}
required = expected | static_expected | {"dense_teacher"}
missing = required - set(payload.get("results", {}))
if missing:
    raise SystemExit(f"missing expected controls: {sorted(missing)}")
if payload.get("config", {}).get("evidence_mode") is not True:
    raise SystemExit("quality report is not marked evidence_mode")
if payload.get("config", {}).get("env_label") != "ASI2":
    raise SystemExit("quality report is not labeled ASI2")
dense_metrics = payload["results"]["dense_teacher"].get("metrics", {})
required_dense_metrics = {
    "mse": 0.0,
    "relative_mse": 0.0,
    "cosine": 1.0,
    "token_relative_mse_p50": 0.0,
    "token_relative_mse_p90": 0.0,
    "token_relative_mse_p95": 0.0,
    "token_relative_mse_p99": 0.0,
    "token_relative_mse_max": 0.0,
}
if dense_metrics != required_dense_metrics:
    raise SystemExit("dense teacher control is malformed")
unexpected = {
    name for name in payload.get("results", {})
    if name != "dense_teacher" and not name.startswith("static_svd_")
} - expected
if unexpected:
    raise SystemExit(f"unexpected trained controls: {sorted(unexpected)}")
provenance = payload.get("provenance", {})
for key in ("argv", "code_digest", "model", "data", "run_input_digest"):
    if not provenance.get(key):
        raise SystemExit(f"missing provenance field: {key}")
if provenance["data"].get("mode") != "explicit_disjoint":
    raise SystemExit("provenance does not record explicit disjoint data")
for name in expected:
    checkpoint = outdir / "checkpoints" / f"{name}.pt"
    if not checkpoint.is_file():
        raise SystemExit(f"missing checkpoint: {checkpoint}")
    resume = outdir / "checkpoints" / f"{name}.resume.pt"
    if not resume.is_file():
        raise SystemExit(f"missing resume checkpoint: {resume}")
    resume_payload = __import__("torch").load(resume, map_location="cpu", weights_only=False)
    if not resume_payload.get("completed") or resume_payload.get("global_step") != payload["config"]["steps"]:
        raise SystemExit(f"incomplete resume checkpoint: {resume}")
    if resume_payload.get("config_fingerprint") != payload["results"][name].get("config_fingerprint"):
        raise SystemExit(f"checkpoint/report fingerprint mismatch: {name}")
print(json.dumps({"event": "seed_validated", "outdir": str(outdir), "controls": sorted(expected)}))
PY
  done
  record_artifacts
}

case "${1:-}" in
  --help|-h)
    usage
    exit 0
    ;;
  --check)
    mkdir -p "$RUN_DIR" "$(dirname "$LOG")"
    preflight
    verify_selected_splits
    echo "ASI2 causal-quality preflight passed"
    echo "run_dir=$RUN_DIR"
    exit 0
    ;;
  --worker)
    run_worker
    exit 0
    ;;
  "")
    mkdir -p "$RUN_DIR" "$(dirname "$LOG")"
    preflight
    verify_selected_splits
    export PROJECT_ROOT ENV_LABEL MODEL_DIR TRAIN_TEXTS EVAL_TEXTS SPLIT_MANIFEST DEVICES
    export ASCEND_RT_VISIBLE_DEVICES="$DEVICES" NPROC_PER_NODE SEEDS LAYER BASE_RANK MATCHED_RANK EFFECTIVE_RANK
    export STUDENT_SPECS STEPS EVAL_BATCHES BATCH SEQ LOG_EVERY CHECKPOINT_EVERY
    export ACTIVATION_MAX_BATCHES ACTIVATION_TEXT_BATCH ACTIVATION_SEQ ACTIVATION_SEED FACTOR_SEED
    export LR DTYPE NEAR_DUPLICATE_THRESHOLD
    export RUN_ID RUN_DIR LOG STATUS ARTIFACT_MANIFEST CACHE_DIR
    nohup bash "$0" --worker >"$LOG" 2>&1 </dev/null &
    worker_pid="$!"
    atomic_status running detached "worker launched" "$worker_pid"
    echo "ASI2 causal quality worker launched"
    echo "pid=$worker_pid"
    echo "run_id=$RUN_ID"
    echo "status=$STATUS"
    echo "log=$LOG"
    ;;
  *)
    echo "ERROR: unknown argument: $1" >&2
    usage >&2
    exit 2
    ;;
esac
