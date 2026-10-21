#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
cd "$PROJECT_ROOT"

export PYTORCH_NPU_ALLOC_CONF="${PYTORCH_NPU_ALLOC_CONF:-max_split_size_mb:256}"
export HCCL_CONNECT_TIMEOUT="${HCCL_CONNECT_TIMEOUT:-1800}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"

MODEL_DIR="${MODEL_DIR:-/vllm-workspace/models/Qwen2.5-1.5B-Instruct}"
CHECKPOINT="${CHECKPOINT:-results/asi3_layer16_recovery_20260525T102958Z/layer16/checkpoints/mwg_expert_residual_r384_belle_lmce_cal_1200.pt}"
MANIFEST="${MANIFEST:-data/heldout/router_broad_splits/manifest.json}"
LAYER="${LAYER:-16}"
SEQ="${SEQ:-256}"
TRAIN_EXAMPLES="${TRAIN_EXAMPLES:-384}"
EVAL_EXAMPLES="${EVAL_EXAMPLES:-384}"
SEEDS="${ASI2_ROUTER_SEEDS:-0 1 2 3 4}"
RISKS="${ASI2_ROUTER_RISK_BUDGETS:-0.05,0.10,0.15,0.20}"
MAX_DELTA="${ASI2_ROUTER_MAX_PREDICTED_DELTA:-0.0}"

mkdir -p results logs
TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="ASI2_risk_router_sweep_${TS}"
OUTDIR="results/${RUN_ID}"
LOG="logs/${RUN_ID}.log"
STATUS="logs/${RUN_ID}.status.json"
mkdir -p "$OUTDIR"

write_status() {
  local state="$1"
  local detail="${2:-}"
  python3 - "$STATUS" "$state" "$RUN_ID" "$LOG" "$OUTDIR" "$detail" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status_path = Path(sys.argv[1])
state, run_id, log_path, outdir, detail = sys.argv[2:7]
payload = {
    "run_id": run_id,
    "state": state,
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "log": log_path,
    "outdir": outdir,
    "result_json": sorted(str(path) for path in Path(outdir).glob("*.json")),
}
if detail:
    payload["detail"] = detail
status_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
}

on_exit() {
  local rc=$?
  if [[ "$rc" -eq 0 ]]; then
    write_status "done"
  else
    write_status "failed" "exit_code=${rc}"
  fi
  return "$rc"
}
trap on_exit EXIT

write_status "running" "starting"

{
  echo "ASI2 MWG-EW risk-controlled router sweep"
  echo "run_id=$RUN_ID"
  echo "project_root=$PROJECT_ROOT"
  echo "model_dir=$MODEL_DIR"
  echo "checkpoint=$CHECKPOINT"
  echo "manifest=$MANIFEST"
  echo "seeds=$SEEDS"
  echo "risk_budgets=$RISKS"
  echo "max_predicted_delta=$MAX_DELTA"
  date -u
  python3 -c "import torch; print('torch', torch.__version__); import torch_npu; print('torch_npu', getattr(torch_npu, '__version__', 'unknown')); print('npu_count', torch.npu.device_count())"

  for seed in $SEEDS; do
    write_status "running" "seed=${seed}"
    python3 experiments/mwg_token_router_gate_eval.py \
      --model-dir "$MODEL_DIR" \
      --checkpoint "$CHECKPOINT" \
      --layer "$LAYER" \
      --seq "$SEQ" \
      --suite-split-manifest "$MANIFEST" \
      --suite-balanced-sampling \
      --suite-balanced-ridge \
      --fail-on-suite-overlap \
      --require-texts \
      --train-examples "$TRAIN_EXAMPLES" \
      --eval-examples "$EVAL_EXAMPLES" \
      --threshold-policy suite_local \
      --risk-budgets "$RISKS" \
      --risk-max-predicted-delta "$MAX_DELTA" \
      --seed "$seed" \
      --out-json "${OUTDIR}/${RUN_ID}_seed${seed}.json"
  done

  python3 - "$OUTDIR" "${RUN_ID}" <<'PY'
import json
import statistics
import sys
from pathlib import Path

outdir = Path(sys.argv[1])
run_id = sys.argv[2]
rows = []
for path in sorted(outdir.glob(f"{run_id}_seed*.json")):
    payload = json.loads(path.read_text(encoding="utf-8"))
    seed = payload.get("args", {}).get("seed")
    for item in payload.get("mixed_frontier", []):
        rows.append({
            "seed": seed,
            "target_patch_fraction": item["target_patch_fraction"],
            "actual_patch_token_fraction": item["actual_patch_token_fraction"],
            "ppl_ratio": item["ppl_ratio"],
            "delta_loss": item["delta_loss"],
        })

summary = {}
for target in sorted({row["target_patch_fraction"] for row in rows}):
    subset = [row for row in rows if row["target_patch_fraction"] == target]
    summary[str(target)] = {
        "seeds": len(subset),
        "actual_patch_token_fraction_mean": statistics.fmean(row["actual_patch_token_fraction"] for row in subset),
        "actual_patch_token_fraction_min": min(row["actual_patch_token_fraction"] for row in subset),
        "actual_patch_token_fraction_max": max(row["actual_patch_token_fraction"] for row in subset),
        "ppl_ratio_mean": statistics.fmean(row["ppl_ratio"] for row in subset),
        "ppl_ratio_min": min(row["ppl_ratio"] for row in subset),
        "ppl_ratio_max": max(row["ppl_ratio"] for row in subset),
        "wins_vs_dense": sum(1 for row in subset if row["ppl_ratio"] <= 1.0),
    }

payload = {"run_id": run_id, "rows": rows, "summary": summary}
(outdir / f"{run_id}_summary.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
lines = [f"# {run_id}", "", "| Target | Seeds | Actual patch mean | PPL ratio mean | Wins |", "|---:|---:|---:|---:|---:|"]
for target, item in summary.items():
    lines.append(
        f"| {float(target):.2f} | {item['seeds']} | {item['actual_patch_token_fraction_mean']:.4f} "
        f"({item['actual_patch_token_fraction_min']:.4f}-{item['actual_patch_token_fraction_max']:.4f}) | "
        f"{item['ppl_ratio_mean']:.4f} ({item['ppl_ratio_min']:.4f}-{item['ppl_ratio_max']:.4f}) | "
        f"{item['wins_vs_dense']}/{item['seeds']} |"
    )
(outdir / f"{run_id}_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
  write_status "running" "summary_done"
  date -u
} 2>&1 | tee "$LOG"
