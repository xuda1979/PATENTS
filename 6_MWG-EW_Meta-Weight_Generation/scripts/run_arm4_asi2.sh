#!/usr/bin/env bash
# Self-contained ASI2 arm-4 runner: builds the fused no-store kernel, validates it,
# runs the four-arm materialized-vs-fused comparison, and msprof counters.
set -uo pipefail
cd /root/work/mwg-ew-transformer-research 2>/dev/null || cd /vllm-workspace/mwg-ew-transformer-research
echo "WS=$(pwd)"

# source CANN env if present
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || true

EXT=/root/work/mwg_torch_ext
mkdir -p "$EXT"
cd "$EXT"
echo "=== kernel present ==="; ls -la ephemeral_core_apply.asc CMakeLists.txt 2>/dev/null

echo "=== CMAKE CONFIGURE ==="
rm -rf build && mkdir -p build && cd build
cmake .. > cmake2.log 2>&1; echo "CMAKE_RC=$?"
tail -15 cmake2.log

echo "=== MAKE ==="
make > make2.log 2>&1; echo "MAKE_RC=$?"
tail -30 make2.log
ls -la libcustom_ops.so 2>/dev/null || { echo "BUILD FAILED"; exit 2; }

echo "=== manifest + smoke ==="
if [ -f /root/work/mwg-ew-transformer-research/custom_ops/ephemeral_core_apply/mwg_smoke_test.py ]; then
  python3 /root/work/mwg-ew-transformer-research/custom_ops/ephemeral_core_apply/mwg_smoke_test.py 2>&1 | tail -25
else
  echo "smoke test not synced; SKIP"
fi

echo "=== FOUR-ARM materialized vs fused ==="
cd /root/work/mwg-ew-transformer-research
python3 experiments/mwg_four_arm_lifetime_benchmark.py \
  --arms materialized,fused --device npu:0 \
  --d 4096 --m 14336 --rank 128 --controller-hidden 128 \
  --batch 1 --seq 128 --dtype fp16 --amplitude 0.05 \
  --fused-contract-manifest /root/work/mwg_torch_ext/contract.json \
  --op-library /root/work/mwg_torch_ext/build/libcustom_ops.so \
  --output results/four_arm_asi2_fused_run.json \
  --run-label "ASI2-fused" 2>&1 | tail -40

echo "=== SUMMARY ==="
python3 experiments/summarize_four_arm_lifetime.py results \
  --output results/four_arm_asi2_summary.json \
  --markdown results/four_arm_asi2_summary.md --strict 2>&1 | tail -20

echo "=== DONE ==="
