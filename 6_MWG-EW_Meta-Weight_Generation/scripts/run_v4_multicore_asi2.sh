#!/usr/bin/env bash
# ASI2 v4 multi-core epilogue runner: builds the v4 kernel, validates it
# against the algebraic reference, and benchmarks v1 vs v4 at multiple
# geometries (L2-resident probe and beyond-L2 large-T).
#
# This script runs ON the ASI2 host.  Push it via S3, sync to ASI2, then:
#   bash scripts/run_v4_multicore_asi2.sh
set -uo pipefail
cd /root/work/mwg-ew-transformer-research 2>/dev/null || cd /vllm-workspace/mwg-ew-transformer-research
echo "=== PWD: $(pwd) ==="
echo "=== DATE: $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

# --- Step 1: Build the v4 kernel via the proven CMake/ASC toolchain ---
# The .asc source contains Ascend-C device code (__aicore__ intrinsics,
# kernel_operator.h) that plain torch cpp_extension/load_inline cannot
# compile; it requires the CANN ASC compiler (--cce-aicore-arch=dav-c220)
# via the same CMake enable_language(ASC) flow that built the shipped v1
# libcustom_ops.so (see scripts/run_arm4_asi2.sh).
echo "=== Building v4 multi-core kernel (CMake/ASC) ==="

V4_EXT=/root/work/mwg_v4_torch_ext
mkdir -p "$V4_EXT"
cp custom_ops/ephemeral_core_apply/torch_ext/v4_multicore/ephemeral_core_apply_v4_multicore.asc "$V4_EXT/"
cp custom_ops/ephemeral_core_apply/torch_ext/CMakeLists_v4.txt "$V4_EXT/CMakeLists.txt" 2>/dev/null || {
  # Fallback: derive the v4 CMakeLists from the shipped v1 one by
  # swapping the kernel source target (v4 registers only the v4 op).
  sed -e 's/ephemeral_core_apply\.asc/ephemeral_core_apply_v4_multicore.asc/' \
      custom_ops/ephemeral_core_apply/torch_ext/CMakeLists.txt > "$V4_EXT/CMakeLists.txt"
}

source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || true

echo "=== CMAKE CONFIGURE ==="
rm -rf "$V4_EXT/build" && mkdir -p "$V4_EXT/build" && cd "$V4_EXT/build"
cmake .. > cmake_v4.log 2>&1; echo "CMAKE_RC=$?"
tail -15 cmake_v4.log

echo "=== MAKE ==="
make > make_v4.log 2>&1; echo "MAKE_RC=$?"
tail -30 make_v4.log
cd - > /dev/null

# --- Step 2: Find the compiled library ---
V4_SO=$(find "$V4_EXT/build" -name "*.so" -type f | head -1)
V1_SO=$(find /root/work/mwg_torch_ext -name "*.so" -type f 2>/dev/null | head -1)

echo "=== v4 .so: $V4_SO ==="
echo "=== v1 .so: $V1_SO ==="

if [ -z "$V4_SO" ]; then
    echo "ERROR: v4 kernel build failed, no .so found"
    exit 1
fi

# --- Step 3: Run the comparison test ---
echo "=== Running v4 vs v1 comparison ==="
python3 custom_ops/ephemeral_core_apply/torch_ext/v4_multicore/test_v4_multicore.py \
    --op-library "$V4_SO" \
    --v1-library "${V1_SO:-}" \
    --output results/v4_multicore_benchmark.json \
    --warmup 30 --iters 200 --repeats 5 2>&1 | tee results/v4_multicore_benchmark.log

# --- Step 4: Run msprof for the beyond-L2 geometry ---
echo "=== Running msprof at T=4096 ==="
# Collect matched profiler passes for v1 and v4 at the beyond-L2 geometry
for VERSION in v1 v4; do
    if [ "$VERSION" = "v1" ] && [ -n "$V1_SO" ]; then
        OP_NAME="ephemeral_core_apply"
        SO_PATH="$V1_SO"
    elif [ "$VERSION" = "v4" ] && [ -n "$V4_SO" ]; then
        OP_NAME="ephemeral_core_apply_v4"
        SO_PATH="$V4_SO"
    else
        continue
    fi
    
    PROF_DIR="results/msprof_v4_${VERSION}_T4096"
    mkdir -p "$PROF_DIR"
    
    msprof --output "$PROF_DIR" \
        --aic-metrics=Memory \
        --application="
            python3 -c \"
import torch
torch.ops.load_library('$SO_PATH')
device = torch.device('npu:0')
torch.npu.set_device(0)
T, H, R = 4096, 128, 128
ctrl = torch.randn(T, H, dtype=torch.float32, device=device)
hw = torch.randn(R, H, dtype=torch.float32, device=device)
hb = torch.randn(R, dtype=torch.float32, device=device)
act = torch.randn(T, R, dtype=torch.float16, device=device)
for _ in range(50):
    out = torch.ops.mwg.$OP_NAME(act, ctrl, hw, hb, 0.05)
torch.npu.synchronize()
\"
        " 2>&1 | tail -20
    
    echo "  msprof $VERSION done -> $PROF_DIR"
done

echo "=== DONE ==="
echo "Results: results/v4_multicore_benchmark.json"
echo "Logs: results/v4_multicore_benchmark.log"
