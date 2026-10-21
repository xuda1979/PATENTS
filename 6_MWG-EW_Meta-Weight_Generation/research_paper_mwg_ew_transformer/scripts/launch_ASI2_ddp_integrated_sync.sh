#!/usr/bin/env bash
set -Eeuo pipefail

# DDP integrated-sync training benchmark (reviewer requirement R2).
#
# Times forward + loss + backward WITH DistributedDataParallel gradient
# synchronization (all-reduce of gradients) on 4x Ascend 910B2, at the
# paper's 8B-scale geometry (d,m)=(4096,14336), ranks 32-512.
#
# This measures a real synchronized training step (minus the optimizer
# update, which is elementwise and identical for both arms).

PROJECT_ROOT="/vllm-workspace/mwg-ew-transformer-research"
cd "$PROJECT_ROOT"

NPROC="${NPROC:-4}"
DEVICES="${DEVICES:-0,1,2,3}"
RANKS="${RANKS:-32,64,96,128,192,256,384,512}"
REPEATS="${REPEATS:-3}"
RUN_ID="asi2_ddp_integrated_sync_$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="$PROJECT_ROOT/results/$RUN_ID"
mkdir -p "$RUN_DIR"

echo "=== DDP Integrated-Sync Training Benchmark ==="
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
    --ddp-bucket-cap-mb 25 \
    --seed $((1234 + repeat)) \
    --outdir "$RUN_DIR" 2>&1 | tail -25
done

echo ""
echo "=== Aggregating DDP results ==="
python3 - << 'AGGREGATOR'
import json, glob, os, statistics
from pathlib import Path

run_dir = Path(sorted(glob.glob("/vllm-workspace/mwg-ew-transformer-research/results/asi2_ddp_integrated_sync_*"))[-1])
results = {}

for json_file in sorted(run_dir.glob("ASI2_mwg_transformer_*.json")):
    with open(json_file) as f:
        d = json.load(f)
    env = d.get("env", {})
    ws = env.get("world_size", 1)
    if ws == 1:
        continue
    for key, row in d.get("results", {}).items():
        if not isinstance(row, dict):
            continue
        tis = row.get("train_integrated_sync")
        if tis is None:
            continue
        label = key
        if label not in results:
            results[label] = {"train_sync_ms": [], "train_ms": [], "forward_ms": []}
        results[label]["train_sync_ms"].append(tis.get("mean_ms", 0.0))
        results[label]["train_ms"].append(row.get("train", {}).get("mean_ms", 0.0))
        results[label]["forward_ms"].append(row.get("forward", {}).get("mean_ms", 0.0))

print(f'{"method":14s} {"n":>2s}  {"train_ms":>12s}  {"train_sync_ms":>14s}  {"sync_overhead":>12s}')
dense_train = None
for label in sorted(results):
    r = results[label]
    n = len(r["train_sync_ms"])
    if n == 0:
        continue
    mt = statistics.mean(r["train_ms"]) if r["train_ms"] else 0
    ms = statistics.mean(r["train_sync_ms"])
    std = statistics.stdev(r["train_sync_ms"]) if n > 1 else 0
    overhead = (ms - mt) if mt else 0
    if label == "dense":
        dense_train = ms
    print(f'{label:14s} {n:2d}  {mt:12.4f}  {ms:10.4f}±{std:.4f}  {overhead:12.4f}')

if dense_train:
    print()
    print(f'DDP synchronized train-step speedup vs dense (world 4):')
    for label in sorted(results):
        r = results[label]
        if not r["train_sync_ms"] or label == "dense":
            continue
        ms = statistics.mean(r["train_sync_ms"])
        print(f'  {label:14s}: {dense_train/ms:.3f}x')

agg_path = run_dir / "aggregated_ddp_sync.json"
with open(agg_path, "w") as f:
    json.dump(results, f, indent=2)
print(f"\nSaved to: {agg_path}")
AGGREGATOR

echo "=== DONE ==="
