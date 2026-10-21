#!/usr/bin/env python3
import pathlib
parts = []
parts.append(r"""
#include "torch_npu/csrc/core/npu/NPUStream.h"
#include <ATen/ATen.h>
#include <torch/library.h>
#include <stdexcept>
#include "kernel_operator.h"
#include "lib/matmul_intf.h"
using namespace AscendC;
""")
parts.append(r"""
namespace mwg { constexpr int32_t BASE_M = 128; constexpr int32_t BASE_N = 128; constexpr int32_t BASE_K = 128; }
""")
parts.append(r"""
using aType = half;
using bType = float;
using cType = float;
using biasType = float;
""")
parts.append(r"""
using matmulType = matmul::Matmul<
    matmul::MatmulType<AscendC::TPosition::GM, CubeFormat::ND, aType>,
    matmul::MatmulType<AscendC::TPosition::GM, CubeFormat::ND, bType>,
    matmul::MatmulType<AscendC::TPosition::VECIN, CubeFormat::ND, cType>,
    matmul::MatmulType<AscendC::TPosition::GM, CubeFormat::ND, biasType>,
    matmul::CFG_NORM,
    matmul::MatmulCallBackFunc<nullptr, nullptr, nullptr>,
    matmul::MatmulPolicy>;
""")
parts.append(r"""
class KernelEphemeralCoreApply {
 public:
  __aicore__ inline KernelEphemeralCoreApply() {}

  __aicore__ inline void Init(GM_ADDR rankActivation, GM_ADDR controllerHidden,
                              GM_ADDR headWeightT, GM_ADDR headBias,
                              GM_ADDR scaledRankActivation, GM_ADDR workspace,
                              const tCubeTiling_t& tiling, float amplitude,
                              uint32_t tokenCount, uint32_t hiddenDim,
                              uint32_t rankDim) {
    tokenCount_ = tokenCount;
    hiddenDim_ = hiddenDim;
    rankDim_ = rankDim;
    amplitude_ = amplitude;
    aGm_.SetGlobalBuffer(reinterpret_cast<__gm__ aType *>(controllerHidden),
                         tokenCount_ * hiddenDim_);
    bGm_.SetGlobalBuffer(reinterpret_cast<__gm__ bType *>(headWeightT),
                         rankDim_ * hiddenDim_);
    biasGm_.SetGlobalBuffer(reinterpret_cast<__gm__ biasType *>(headBias),
                            rankDim_);
    actGm_.SetGlobalBuffer(reinterpret_cast<__gm__ half *>(rankActivation),
                           tokenCount_ * rankDim_);
    outGm_.SetGlobalBuffer(reinterpret_cast<__gm__ half *>(scaledRankActivation),
                           tokenCount_ * rankDim_);
    mm_.SetTensorA(aGm_);
    mm_.SetTensorB(bGm_);
    mm_.SetBias(biasGm_);
    InitQueues();
  }

  __aicore__ inline void InitQueues() {
    pipe_.InitBuffer(cBuf_, 1, BASE_M * BASE_N * sizeof(cType));
    pipe_.InitBuffer(actBuf_, 1, BASE_M * BASE_N * sizeof(half));
    pipe_.InitBuffer(actF32Buf_, 1, BASE_M * BASE_N * sizeof(float));
    pipe_.InitBuffer(outBuf_, 1, BASE_M * BASE_N * sizeof(half));
  }

  __aicore__ inline void Process() {
    int32_t mRound = 0;
    while (mm_.Iterate(true)) {
      AscendC::LocalTensor<cType> cLocal = cBuf_.AllocTensor<cType>();
      AscendC::LocalTensor<half> actLocal = actBuf_.AllocTensor<half>();
      mm_.GetTensorC(cLocal, false, true);
      int32_t actualRows = min(BASE_M, static_cast<int32_t>(tokenCount_ - mRound * BASE_M));
      int32_t count = actualRows * rankDim_;
      DataCopy(actLocal, actGm_[mRound * BASE_M * rankDim_],
               DataCopyParams{static_cast<uint32_t>(actualRows),
                              rankDim_ * sizeof(half), rankDim_ * sizeof(half),
                              rankDim_ * sizeof(half)});
      AscendC::Tanh(cLocal, cLocal, count);
      AscendC::Muls(cLocal, cLocal, amplitude_, count);
      AscendC::Adds(cLocal, cLocal, static_cast<float>(1.0), count);
      AscendC::LocalTensor<float> actF32 = actF32Buf_.AllocTensor<float>();
      AscendC::Cast(actF32, actLocal, AscendC::RoundMode::CAST_NONE, count);
      AscendC::Mul(cLocal, cLocal, actF32, count);
      AscendC::LocalTensor<half> outLocal = outBuf_.AllocTensor<half>();
      AscendC::Cast(outLocal, cLocal, AscendC::RoundMode::CAST_NONE, count);
      DataCopy(outGm_[mRound * BASE_M * rankDim_], outLocal,
               DataCopyParams{static_cast<uint32_t>(actualRows),
                              rankDim_ * sizeof(half), rankDim_ * sizeof(half),
                              rankDim_ * sizeof(half)});
      actF32Buf_.FreeTensor(actF32);
      outBuf_.FreeTensor(outLocal);
      actBuf_.FreeTensor(actLocal);
      cBuf_.FreeTensor(cLocal);
      mRound++;
    }
  }

 private:
  TPipe pipe_;
  matmulType mm_;
  TQue<QuePosition::VECOUT, 1> cBuf_;
  TQue<QuePosition::VECIN, 1> actBuf_;
  TQue<QuePosition::VECIN, 1> actF32Buf_;
  TQue<QuePosition::VECIN, 1> outBuf_;
  GlobalTensor<aType> aGm_;
  GlobalTensor<bType> bGm_;
  GlobalTensor<biasType> biasGm_;
  GlobalTensor<half> actGm_;
  GlobalTensor<half> outGm_;
  uint32_t tokenCount_;
  uint32_t hiddenDim_;
  uint32_t rankDim_;
  float amplitude_;
};

extern "C" __global__ __aicore__ void ephemeral_core_apply_kernel(
    GM_ADDR rankActivation, GM_ADDR controllerHidden, GM_ADDR headWeightT,
    GM_ADDR headBias, GM_ADDR scaledRankActivation, GM_ADDR workspace,
    tCubeTiling_t tiling, float amplitude, uint32_t tokenCount,
    uint32_t hiddenDim, uint32_t rankDim) {
  KernelEphemeralCoreApply op;
  op.Init(rankActivation, controllerHidden, headWeightT, headBias,
          scaledRankActivation, workspace, tiling, amplitude, tokenCount,
          hiddenDim, rankDim);
  op.Process();
}

// ---- host-side tiling (runs on CPU) ----
tCubeTiling_t GenerateTiling(platform_ascendc::PlatformAscendC* platform,
                             uint32_t M, uint32_t N, uint32_t K) {
  using TPosition = matmul_tiling::TPosition;
  using CubeFormat = matmul_tiling::CubeFormat;
  using DataType = matmul_tiling::DataType;
  matmul_tiling::MultiCoreMatmulTiling api(*platform);
  api.SetDim(1);
  api.SetAType(TPosition::GM, CubeFormat::ND, DataType::DT_FLOAT16, false);
  api.SetBType(TPosition::GM, CubeFormat::ND, DataType::DT_FLOAT, false);
  api.SetCType(TPosition::VECIN, CubeFormat::ND, DataType::DT_FLOAT);
  api.SetBiasType(TPosition::GM, CubeFormat::ND, DataType::DT_FLOAT);
  api.SetOrgShape(M, N, K);
  api.SetShape(M, N, K);
  api.SetBias(true);
  api.SetTraverse(matmul_tiling::MatrixTraverse::FIRSTM);
  api.SetFixSplit(BASE_M, BASE_N, -1);
  api.SetBufferSpace(-1, -1, -1);
  tCubeTiling_t tiling;
  int64_t res = api.GetTiling(tiling);
  if (res == -1) {
    throw std::runtime_error("mwg: tiling generation failed");
  }
  tiling.stepM = 1;
  tiling.stepN = 1;
  return tiling;
}
""")
parts.append(r"""
// ---- host wrapper (eager torch) ----
namespace mwg {
at::Tensor ephemeral_core_apply(const at::Tensor& rank_activation,
                                const at::Tensor& controller_hidden,
                                const at::Tensor& head_weight,
                                const at::Tensor& head_bias, double amplitude) {
  TORCH_CHECK(rank_activation.is_contiguous() && controller_hidden.is_contiguous(),
              "mwg: inputs must be contiguous");
  TORCH_CHECK(rank_activation.scalar_type() == at::kHalf,
              "mwg: rank_activation must be fp16");
  TORCH_CHECK(controller_hidden.scalar_type() == at::kFloat,
              "mwg: controller_hidden must be fp32");
  TORCH_CHECK(rank_activation.device().type() == c10::kPrivateUse1,
              "mwg: rank_activation must be on NPU");
  auto out = at::empty_like(rank_activation);
  auto weight_t = head_weight.t().contiguous();
  uint32_t t = static_cast<uint32_t>(rank_activation.size(0));
  uint32_t h = static_cast<uint32_t>(controller_hidden.size(1));
  uint32_t r = static_cast<uint32_t>(rank_activation.size(1));

  auto platform = platform_ascendc::PlatformAscendCManager::GetInstance("ascend910b");
  auto tiling = GenerateTiling(platform, t, r, h);
  size_t workspace_size = platform->GetLibApiWorkSpaceSize();
  auto workspace = at::empty({static_cast<int64_t>(workspace_size)},
                             rank_activation.options().dtype(at::kByte));
  auto acl_stream = c10_npu::getCurrentNPUStream().stream(false);
  uint32_t block_dim = 1;
  ephemeral_core_apply_kernel<<<block_dim, nullptr, acl_stream>>>(
      rank_activation.data_ptr(), controller_hidden.data_ptr(),
      weight_t.data_ptr(), head_bias.data_ptr(), out.data_ptr(),
      workspace.data_ptr(), tiling, static_cast<float>(amplitude), t, h, r);
  return out;
}
}  // namespace mwg

TORCH_LIBRARY(mwg, m) {
  m.def("ephemeral_core_apply(Tensor rank_activation, Tensor controller_hidden, "
        "Tensor head_weight, Tensor head_bias, float amplitude) -> Tensor");
}
TORCH_LIBRARY_IMPL(mwg, PrivateUse1, m) {
  m.impl("ephemeral_core_apply", TORCH_FN(mwg::ephemeral_core_apply));
}
""")

import sys
pathlib.Path("/tmp/mwg_kernel.asc").write_text("".join(parts))
print("assembled", len("".join(parts)), "bytes")



