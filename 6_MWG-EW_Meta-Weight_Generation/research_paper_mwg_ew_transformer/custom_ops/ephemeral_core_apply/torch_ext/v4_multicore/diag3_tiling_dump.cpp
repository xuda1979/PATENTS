// diag3_tiling_dump.cpp — host-only tiling introspection, NO kernel launch.
//
// Purpose (task #4): dump every TCubeTiling field returned by
// MultiCoreMatmulTiling::GetTiling for the exact geometries the v1/v4
// host wrappers generate, BEFORE and AFTER the post-GetTiling pinning
// overrides, to test the working hypothesis:
//
//   v4 post-pins baseM=64 / baseN=128 / stepM=stepN=1 over the API's
//   internally-consistent output while leaving derived fields
//   (depthA1, depthB1, singleCoreM/N, iterateOrder, ...) inconsistent,
//   which makes the matmul framework compute wrong addresses/buffer
//   layouts during Iterate → D-cache/UB bus error 0x26 (507015).
//
// Struct recovered from ASI3 CANN 8.5.0
// (kernel_tiling/kernel_tiling.h): 50 consecutive int32_t fields, POD.
// We dump a named view (compile-checked against the real header) plus
// raw slots for anything beyond the known 50 fields.
//
// Output: one JSON object per line:
//   platform {"soc":"...","libApiWorkSpaceSize":N}
//   v1_raw_T{T} {"T":T,"getTilingRes":0,"slots":{...}}
//   v1_pinned_T{T} {"slots":{...}}
//   v4_raw_T{T} {"T":T,"mLocal":M,"blockDim":B,"getTilingRes":0,"slots":{...}}
//   v4_pinned_T{T} {"slots":{...}}
//
// Build (on ASI3, aarch64):
//   CANN=/usr/local/Ascend/cann-8.5.0/aarch64-linux
//   g++ -O0 -g diag3_tiling_dump.cpp -o /tmp/diag3_tiling_dump \
//       -I"$CANN/ascendc/include" -I"$CANN/include" \
//       -L"$CANN/lib64" -ltiling_api -lplatform -lregister -ldl -lpthread
//
// Run: /tmp/diag3_tiling_dump   (prints JSON lines; zero device launch)

#include <cstdint>
#include <cstdio>

#include "tiling/platform/platform_ascendc.h"
#include "tiling/tiling_api.h"
#include "kernel_tiling/kernel_tiling.h"

#ifndef MWG_SOC_VERSION
#define MWG_SOC_VERSION "Ascend910B2"
#endif

using AscendC::tiling::TCubeTiling;

// Mirror of the recovered header layout (50 int32_t, POD).  Indexing the
// real struct through a raw int32 view covers these plus any extra slots.
static const char* kFieldNames[] = {
    "usedCoreNum", "M", "N", "Ka", "Kb",
    "singleCoreM", "singleCoreN", "singleCoreK",
    "baseM", "baseN", "baseK",
    "depthA1", "depthB1",
    "stepM", "stepN",
    "isBias", "transLength", "iterateOrder",
    "shareMode", "shareL1Size", "shareL0CSize", "shareUbSize",
    "batchM", "batchN", "singleBatchM", "singleBatchN",
    "stepKa", "stepKb",
    "depthAL1CacheUB", "depthBL1CacheUB",
    "dbL0A", "dbL0B", "dbL0C",
    "ALayoutInfoB", "ALayoutInfoS", "ALayoutInfoN", "ALayoutInfoG", "ALayoutInfoD",
    "BLayoutInfoB", "BLayoutInfoS", "BLayoutInfoN", "BLayoutInfoG", "BLayoutInfoD",
    "CLayoutInfoB", "CLayoutInfoS1", "CLayoutInfoN", "CLayoutInfoG", "CLayoutInfoS2",
    "BatchNum", "mxTypePara",
};
static const int kNumNamed = (int)(sizeof(kFieldNames) / sizeof(kFieldNames[0]));

// Prints: "slots":{...}}   (opens nothing, closes the outer object)
static void printSlots(const TCubeTiling& t) {
  const int32_t* raw = reinterpret_cast<const int32_t*>(&t);
  int slots = (int)(sizeof(TCubeTiling) / sizeof(int32_t));
  printf("\"sizeof\":%zu,\"slots\":{", sizeof(TCubeTiling));
  for (int i = 0; i < slots; ++i) {
    const char* name = (i < kNumNamed) ? kFieldNames[i] : nullptr;
    if (i > 0) printf(",");
    if (name) printf("\"%s\":%d", name, (int)raw[i]);
    else printf("\"raw%d\":%d", i, (int)raw[i]);
  }
  printf("}}\n");
}

struct DumpCtx {
  platform_ascendc::PlatformAscendC* platform;
  size_t libWs;
};

// Common type/shape setup shared by v1 and v2 tiling sequences.
static void setupApi(matmul_tiling::MultiCoreMatmulTiling& api,
                     uint32_t M, uint32_t N, uint32_t K) {
  using TPosition = matmul_tiling::TPosition;
  using CubeFormat = matmul_tiling::CubeFormat;
  using DataType = matmul_tiling::DataType;
  api.SetAType(TPosition::GM, CubeFormat::ND, DataType::DT_FLOAT16, false);
  api.SetBType(TPosition::GM, CubeFormat::ND, DataType::DT_FLOAT16, false);
  api.SetCType(TPosition::GM, CubeFormat::ND, DataType::DT_FLOAT);
  api.SetBiasType(TPosition::GM, CubeFormat::ND, DataType::DT_FLOAT);
  api.SetOrgShape(M, N, K);
  api.SetShape(M, N, K);
  api.SetBias(true);
  api.SetTraverse(matmul_tiling::MatrixTraverse::FIRSTM);
  api.SetBufferSpace(-1, -1, -1);
}

// v1-style: full-M single-core tiling (SetDim(1)), then v1's
// stepM=stepN=1 post-pins.  Mirrors the v1 host wrapper.
static void dumpV1(DumpCtx& ctx, uint32_t T, uint32_t N = 128, uint32_t K = 128) {
  matmul_tiling::MultiCoreMatmulTiling api(*ctx.platform);
  api.SetDim(1);
  setupApi(api, T, N, K);
  TCubeTiling t;
  int64_t res = api.GetTiling(t);
  printf("v1_raw_T%u {\"T\":%u,\"getTilingRes\":%lld,", T, T, (long long)res);
  printSlots(t);
  // v1 post-pins: stepM=1, stepN=1 only (baseM/baseN left as API chose).
  t.stepM = 1;
  t.stepN = 1;
  printf("v1_pinned_T%u {", T);
  printSlots(t);
}

// v4-style: per-core mLocal geometry from the v4 host partition
// arithmetic (no SetDim), then v4's post-pins (baseN=N, stepN=1,
// baseM=64, stepM=1).  Mirrors GenerateTilingV4 in
// ephemeral_core_apply_v4_multicore.asc.
static void dumpV4(DumpCtx& ctx, uint32_t T, uint32_t N = 128, uint32_t K = 128) {
  const uint32_t baseMConst = 64;  // BASE_M_V4
  uint32_t totalTiles = (T + baseMConst - 1) / baseMConst;
  uint32_t block_dim = (totalTiles < 8u) ? totalTiles : 8u;
  if (block_dim < 1) block_dim = 1;
  uint32_t tilesPerCore = (totalTiles + block_dim - 1) / block_dim;
  uint32_t mLocal = tilesPerCore * baseMConst;

  matmul_tiling::MultiCoreMatmulTiling api(*ctx.platform);
  setupApi(api, mLocal, N, K);
  TCubeTiling t;
  int64_t res = api.GetTiling(t);
  printf("v4_raw_T%u {\"T\":%u,\"mLocal\":%u,\"blockDim\":%u,\"getTilingRes\":%lld,",
         T, T, mLocal, block_dim, (long long)res);
  printSlots(t);
  // v4 post-pins (GenerateTilingV4 tail):
  t.baseN = N;
  t.stepN = 1;
  t.baseM = baseMConst;
  t.stepM = 1;
  printf("v4_pinned_T%u {", T);
  printSlots(t);
}

int main() {
  auto* platform =
      platform_ascendc::PlatformAscendCManager::GetInstance(MWG_SOC_VERSION);
  if (platform == nullptr) {
    fprintf(stderr, "FATAL: PlatformAscendCManager::GetInstance(%s) failed\n",
            MWG_SOC_VERSION);
    return 1;
  }
  DumpCtx ctx{platform, (size_t)platform->GetLibApiWorkSpaceSize()};
  printf("platform {\"soc\":\"%s\",\"libApiWorkSpaceSize\":%zu}\n",
         MWG_SOC_VERSION, ctx.libWs);

  // v1 geometries: full-M, single core (v1 host calls with M=T).
  for (uint32_t T : {64u, 96u, 128u, 160u, 192u, 256u, 512u, 2048u, 4096u}) {
    dumpV1(ctx, T);
  }
  // v4 geometries: per-core mLocal per the v4 host partition arithmetic.
  for (uint32_t T : {64u, 128u, 192u, 256u, 384u, 512u, 2048u, 4096u}) {
    dumpV4(ctx, T);
  }
  return 0;
}
