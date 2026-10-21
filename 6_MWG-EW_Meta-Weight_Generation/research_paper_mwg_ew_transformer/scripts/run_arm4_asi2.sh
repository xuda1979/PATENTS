#!/usr/bin/env bash
# ASI2 arm-4 runner: build the fused no-store kernel, smoke-test it, then run
# the decisive materialized-vs-fused comparison with contract validation.
# Usage (on ASI2, after ASI2_sync_code_from_s3.sh):
#   bash scripts/run_arm4_asi2.sh            # build + smoke + four-arm run
#   bash scripts/run_arm4_asi2.sh --smoke    # build + smoke test only
set -uo pipefail
WS=""
for c in /vllm-workspace/mwg-ew-transformer-research /root/work/mwg-ew-transformer-research; do
  [ -d "$c" ] && WS="$c" && break
done
[ -z "$WS" ] && { echo "workspace not found"; exit 2; }
echo "WS=$WS"
EXT=/root/work/mwg_torch_ext
mkdir -p "$EXT"
cp "$WS/custom_ops/ephemeral_core_apply/torch_ext/ephemeral_core_apply.asc" "$EXT/"
cp "$WS/custom_ops/ephemeral_core_apply/torch_ext/CMakeLists.txt" "$EXT/"

source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || true

cd "$EXT"
echo "=== CMAKE ==="
rm -rf build && mkdir -p build && cd build
cmake .. > cmake.log 2>&1; echo "CMAKE_RC=$?"
make > make.log 2>&1; echo "MAKE_RC=$?"
tail -20 make.log
[ -f libcustom_ops.so ] || { echo "BUILD FAILED"; exit 2; }
echo "SO=$(ls -la libcustom_ops.so)"

echo "=== SMOKE ==="
cd "$WS"
python3 custom_ops/ephemeral_core_apply/mwg_smoke_test.py 2>&1 | tail -20
SMOKE_RC=${PIPESTATUS[0]}
echo "SMOKE_RC=$SMOKE_RC"
if [ "${1:-}" = "--smoke" ]; then exit "$SMOKE_RC"; fi
if [ "$SMOKE_RC" != "0" ]; then echo "smoke failed; refusing four-arm run"; exit 3; fi

echo "=== FOUR-ARM materialized vs fused ==="
OUT="results/four_arm_asi2_$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT"
python3 experiments/mwg_four_arm_lifetime_benchmark.py \
  --arms materialized,fused --device npu:0 \
  --d 4096 --m 14336 --rank 128 --controller-hidden 128 \
  --batch 1 --seq 128 --dtype fp16 --amplitude 0.05 \
  --warmup 30 --iters 200 --repeats 5 --seed 1234 \
  --fused-contract-manifest /root/work/mwg_torch_ext/contract.json \
  --op-library /root/work/mwg_torch_ext/build/libcustom_ops.so \
  --output "$OUT/four_arm_fused_run.json" \
  --run-label "ASI2-arm4-$(date -u +%Y%m%dT%H%M%SZ)" 2>&1 | tail -45
echo "FOUR_ARM_RC=$?"
python3 - "$OUT/four_arm_fused_run.json" <<'PY'
import json, sys
try:
    p = json.load(open(sys.argv[1]))
    v = p.get("validations", {}).get("materialized_vs_fused", {})
    print("EQUIVALENCE PASSED:", v.get("passed"))
    for arm, m in p.get("arms", {}).items():
        lat = m.get("latency_ms_per_launch") or m.get("mean_ms") or m.get("latency_ms")
        print(arm, "latency:", lat)
except Exception as e:
    print("summary parse error", e)
PY
echo "=== DONE: $OUT ==="
