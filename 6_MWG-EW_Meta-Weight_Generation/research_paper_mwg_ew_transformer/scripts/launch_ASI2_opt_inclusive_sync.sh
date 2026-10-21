#!/usr/bin/env bash
set -Eeuo pipefail

# Optimizer-inclusive synchronized-DDP training benchmark (paper's last open
# systems measurement).
#
# Times zero-grad + forward + squared-loss + backward WITH
# DistributedDataParallel gradient all-reduce AND the elementwise AdamW
# optimizer update, all inside the timed region, on 4x Ascend 910B2 at the
# paper's 8B-scale geometry (d,m)=(4096,14336), ranks 32-512.
#
# This closes the open item stated in the paper: "the optimizer-inclusive
# synchronized-DDP measurement ... only the elementwise optimizer update ...
# remains outside the timed region."

PROJECT_ROOT="/vllm-workspace/mwg-ew-transformer-research"
cd "$PROJECT_ROOT"

NPROC="${NPROC:-4}"
DEVICES="${DEVICES:-0,1,2,3}"
RANKS="${RANKS:-32,64,96,128,192,256,384,512}"
REPEATS="${REPEATS:-3}"
RUN_ID="asi2_opt_inclusive_sync_$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="$PROJECT_ROOT/results/$RUN_ID"
mkdir -p "$RUN_DIR"

echo "=== Optimizer-Inclusive Sync DDP Training Benchmark ==="
echo "run_id: $RUN_ID"
echo "nproc: $NPROC devices: $DEVICES ranks: $RANKS repeats: $REPEATS"

export PYTORCH_NPU_ALLOC_CONF="${PYTORCH_NPU_ALLOC_CONF:-max_split_size_mb:256}"
export HCCL_CONNECT_TIMEOUT="${HCCL_CONNECT_TIMEOUT:-1800}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-8}"

for repeat in $(seq 1 "$REPEATS"); do
  echo ""
  echo "=== Repeat $repeat/$REPEATS ==="
  ASCEND_RT_VISIBLE_DEVICES="$DEVICES" python3 -m torch.distributed.run \
    --nproc_per_node="$NPROC" \
    experiments/mwg_transformer_ASI3_benchmark.py \
    --preset ASI2_sweep \
    --env-label ASI2 \
    --ranks "$RANKS" \
    --warmup 3 \
    --iters 10 \
    --train-iters 5 \
    --comm-iters 5 \
    --measure-integrated-sync \
    --measure-opt-inclusive-sync \
    --ddp-bucket-cap-mb 25 \
    --seed $((1234 + repeat)) \
    --outdir "$RUN_DIR" 2>&1 | tail -25
done

echo ""
echo "=== Aggregating optimizer-inclusive DDP results ==="
python3 - << 'AGGREGATOR'
import json, glob, statistics
from pathlib import Path

run_dir = Path(sorted(glob.glob("/vllm-workspace/mwg-ew-transformer-research/results/asi2_opt_inclusive_sync_*"))[-1])
results = {}

for json_file in sorted(run_dir.glob("ASI2_mwg_transformer_*.json")):
    data = json.loads(json_file.read_text())
    res = data["results"]
    for label in ["dense"] + [f"mwg_r{r}" for r in [32, 64, 96, 128, 192, 256, 384, 512]]:
        row = res.get(label)
        if not row:
            continue
        if label not in results:
            results[label] = {"train_sync_ms": [], "train_opt_sync_ms": [], "train_ms": []}
        tis = row.get("train_integrated_sync")
        tos = row.get("train_opt_inclusive_sync")
        tr = row.get("train")
        if tis:
            results[label]["train_sync_ms"].append(tis["mean_ms"])
        if tos:
            results[label]["train_opt_sync_ms"].append(tos["mean_ms"])
        if tr:
            results[label]["train_ms"].append(tr["mean_ms"])

print(f'{"method":14s} {"n":>2s}  {"train_ms":>12s}  {"sync_ms":>14s}  {"opt_sync_ms":>14s}  {"opt_overhead_ms":>16s}')
dense_opt = 0
dense_train = 0
for label in sorted(results):
    r = results[label]
    n = len(r["train_opt_sync_ms"])
    if n == 0:
        continue
    mt = statistics.mean(r["train_ms"]) if r["train_ms"] else 0
    ms = statistics.mean(r["train_sync_ms"]) if r["train_sync_ms"] else 0
    mo = statistics.mean(r["train_opt_sync_ms"])
    std = statistics.stdev(r["train_opt_sync_ms"]) if n > 1 else 0
    overhead = mo - ms
    if label == "dense":
        dense_opt = mo
        dense_train = mt
    print(f'{label:14s} {n:2d}  {mt:12.4f}  {ms:14.4f}  {mo:10.4f}±{std:.4f}  {overhead:16.4f}')

if dense_opt:
    print()
    print(f'Optimizer-inclusive synchronized train-step speedup vs dense (world 4):')
    for label in sorted(results):
        r = results[label]
        if not r["train_opt_sync_ms"] or label == "dense":
            continue
        mo = statistics.mean(r["train_opt_sync_ms"])
        print(f'  {label:14s}: {dense_opt/mo:.3f}x')

agg_path = run_dir / "aggregated_opt_inclusive_sync.json"
with open(agg_path, "w") as f:
    json.dump(results, f, indent=2)
print(f"\nSaved to: {agg_path}")
AGGREGATOR

echo "=== DONE ==="
