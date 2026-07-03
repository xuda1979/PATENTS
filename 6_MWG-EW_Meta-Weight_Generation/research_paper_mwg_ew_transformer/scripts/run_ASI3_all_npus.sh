#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"
cd "$PROJECT_ROOT"

export ASCEND_RT_VISIBLE_DEVICES="${ASCEND_RT_VISIBLE_DEVICES:-0,1,2,3,4,5,6,7}"
export PYTORCH_NPU_ALLOC_CONF="${PYTORCH_NPU_ALLOC_CONF:-max_split_size_mb:256}"
export HCCL_CONNECT_TIMEOUT="${HCCL_CONNECT_TIMEOUT:-1800}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"

NPROC="$(python3 - <<'PY'
import os
ids = [x for x in os.environ.get("ASCEND_RT_VISIBLE_DEVICES", "").split(",") if x.strip()]
print(max(1, len(ids)))
PY
)"

mkdir -p results logs
TS="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="logs/ASI3_all_npus_${TS}.log"

echo "ASI3 MWG-EW all-NPU run"
echo "project_root=$PROJECT_ROOT"
echo "ASCEND_RT_VISIBLE_DEVICES=$ASCEND_RT_VISIBLE_DEVICES"
echo "nproc=$NPROC"
echo "log=$LOG"

python3 -c "import torch; print('torch', torch.__version__); import torch_npu; print('torch_npu', getattr(torch_npu, '__version__', 'unknown')); print('npu_count', torch.npu.device_count())"

python3 -m torch.distributed.run \
  --nproc_per_node="$NPROC" \
  experiments/mwg_transformer_ASI3_benchmark.py \
  --preset ASI3_large \
  --ranks 64,128,256 \
  --warmup 4 \
  --iters 12 \
  --train-iters 4 \
  --comm-iters 4 \
  --outdir results 2>&1 | tee "$LOG"
