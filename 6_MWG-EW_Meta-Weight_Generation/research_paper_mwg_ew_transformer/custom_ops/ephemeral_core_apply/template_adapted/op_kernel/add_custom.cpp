/*
 * @file add_custom.cpp  (template filename retained for the sample build)
 *
 * mwg::ephemeral_core_apply Ascend-C kernel (arm 4, no-store contract),
 * adapted to the ACLNN framework entry convention:
 *
 *   scaled_rank_activation[t, r]
 *     = rank_activation[t, r]
 *       * ( 1 + amplitude * tanh( controller_hidden[t, :] @ head_weight[:, r]
 *                                 + head_bias[r] ) )
 *
 * The generated diagonal core exists only as LocalTensors in UB/scratch: it is
 * computed into the C tile buffer, transformed in place (tanh, scale, offset),
 * and multiplied into the activation tile.  It is never declared as a
 * GlobalTensor and never copied to global memory.
 *
 * Framework adaptation (relative to the standalone audited source):
 *   - entry signature is (4 inputs, 1 output, workspace, tiling);
 *   - scalars (amplitude, tokenCount, hiddenDim, rankDim) arrive via tiling;
 *   - head_weight is consumed in its declared [H, R] layout (no host
 *     transpose: the B tile is read transposed via a strided DataCopy);
 *   - workspace is unused (contract: workspace_bytes == 0).
 *
 * Contract properties (unchanged):
 *   - exactly five GlobalTensors: four inputs and one output; the core never
 *     appears as a GlobalTensor;
 *   - no DataCopy writes core values to GM; the only GM writes are the final
 *     scaled activation tiles (the declared output);
 *   - deterministic: no RNG, no atomics, no device-clock dependence.
 *
 * v1 constraints: hiddenDim (H) == TILE_K == 128; 16 <= rankDim (R) <= 128,
 * R % 16 == 0; tokenCount >= 1; all GM tensors contiguous and 32-byte aligned.
 * UB budget at TILE_M=8, H=128, R=128 is ~153 KiB < 192 KiB (Ascend 910B).
 */

#include "kernel_operator.h"
#include "add_custom_tiling.h"

using namespace AscendC;

namespace {

constexpr int32_t TILE_M = 8;    // rows of the GEMM per M tile
constexpr int32_t TILE_K = 128;  // full controller hidden dimension (v1)
constexpr int32_t TILE_N = 128;  // maximum rank dimension (v1, no N tiling)
constexpr int32_t BUFFER_NUM = 2;

}  // namespace

class KernelEphemeralCoreApply {
 public:
  __aicore__ inline KernelEphemeralCoreApply() {}

  __aicore__ inline void Init(GM_ADDR rankActivation, GM_ADDR controllerHidden,
                              GM_ADDR headWeight, GM_ADDR headBias,
                              GM_ADDR scaledRankActivation, float amplitude,
                              uint32_t tokenCount, uint32_t hiddenDim,
                              uint32_t rankDim) {
    tokenCount_ = tokenCount;
    hiddenDim_ = hiddenDim;
    rankDim_ = rankDim;
    amplitude_ = amplitude;

    aGm_.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(controllerHidden),
                         tokenCount_ * hiddenDim_);
    // headWeight is declared [H, R] in GM; element count is rankDim * hiddenDim.
    bGm_.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(headWeight),
                         rankDim_ * hiddenDim_);
    biasGm_.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(headBias), rankDim_);
    actGm_.SetGlobalBuffer(reinterpret_cast<__gm__ half*>(rankActivation),
                           tokenCount_ * rankDim_);
    outGm_.SetGlobalBuffer(reinterpret_cast<__gm__ half*>(scaledRankActivation),
                           tokenCount_ * rankDim_);

    pipe_.InitBuffer(inQueueA_, BUFFER_NUM, TILE_M * TILE_K * sizeof(float));
    pipe_.InitBuffer(inQueueB_, BUFFER_NUM, TILE_K * TILE_N * sizeof(float));
    pipe_.InitBuffer(outQueueC_, BUFFER_NUM, TILE_M * TILE_N * sizeof(float));
    pipe_.InitBuffer(actF16Queue_, 1, TILE_M * TILE_N * sizeof(half));
    pipe_.InitBuffer(actF32Queue_, 1, TILE_M * TILE_N * sizeof(float));
    pipe_.InitBuffer(outF16Queue_, 1, TILE_M * TILE_N * sizeof(half));
    pipe_.InitBuffer(biasQueue_, 1, TILE_N * sizeof(float));

    mTileCount_ = (tokenCount_ + TILE_M - 1) / TILE_M;
  }

  __aicore__ inline void Process() {
    biasLocal_ = biasQueue_.AllocTensor<float>();
    DataCopy(biasLocal_, biasGm_[0], rankDim_);

    for (int32_t i = 0; i < mTileCount_; ++i) {
      LocalTensor<float> aLocal = inQueueA_.AllocTensor<float>();
      LocalTensor<float> bLocal = inQueueB_.AllocTensor<float>();
      LocalTensor<float> cLocal = outQueueC_.AllocTensor<float>();
      LocalTensor<half> actF16Local = actF16Queue_.AllocTensor<half>();
      LocalTensor<float> actF32Local = actF32Queue_.AllocTensor<float>();
      LocalTensor<half> outF16Local = outF16Queue_.AllocTensor<half>();

      CopyIn(i, aLocal, bLocal, actF16Local);
      Compute(aLocal, bLocal, cLocal, actF16Local, actF32Local, outF16Local);
      CopyOut(i, outF16Local);

      inQueueA_.FreeTensor(aLocal);
      inQueueB_.FreeTensor(bLocal);
      outQueueC_.FreeTensor(cLocal);
      actF16Queue_.FreeTensor(actF16Local);
      actF32Queue_.FreeTensor(actF32Local);
      outF16Queue_.FreeTensor(outF16Local);
    }

    biasQueue_.FreeTensor(biasLocal_);
  }

 private:
  __aicore__ inline void CopyIn(int32_t tileIndex, LocalTensor<float>& aLocal,
                                LocalTensor<float>& bLocal,
                                LocalTensor<half>& actF16Local) {
    int32_t actualRows =
        min(TILE_M, static_cast<int32_t>(tokenCount_ - tileIndex * TILE_M));
    // A tile: actualRows full rows of controllerHidden [T, H] (contiguous).
    DataCopy(aLocal, aGm_[tileIndex * TILE_M * hiddenDim_],
             DataCopyParams{actualRows, hiddenDim_ * sizeof(float),
                            hiddenDim_ * sizeof(float),
                            hiddenDim_ * sizeof(float)});
    // B tile: headWeight is [H, R]; read its transpose ([R, H] rows) with a
    // column-strided DataCopy (no host-side transpose in the GE flow).
    DataCopy(bLocal, bGm_[0],
             DataCopyParams{rankDim_, hiddenDim_ * sizeof(float),
                            sizeof(float), hiddenDim_ * sizeof(float)});
    // Activation tile: actualRows full rows of rankActivation [T, R] (fp16).
    DataCopy(actF16Local, actGm_[tileIndex * TILE_M * rankDim_],
             DataCopyParams{actualRows, rankDim_ * sizeof(half),
                            rankDim_ * sizeof(half), rankDim_ * sizeof(half)});
    inQueueA_.EnQue(aLocal);
    inQueueB_.EnQue(bLocal);
  }

  __aicore__ inline void Compute(LocalTensor<float>& aLocal,
                                 LocalTensor<float>& bLocal,
                                 LocalTensor<float>& cLocal,
                                 LocalTensor<half>& actF16Local,
                                 LocalTensor<float>& actF32Local,
                                 LocalTensor<half>& outF16Local) {
    mm_.SetTensorA(aLocal);
    mm_.SetTensorB(bLocal);
    mm_.SetBias(biasLocal_);
    mm_.Iterate(1);
    mm_.GetTensorC(cLocal);
    // The core z = 1 + amplitude * tanh(logits) is formed in place in the C
    // tile buffer (UB only); it is never written to GM.
    int32_t count = TILE_M * rankDim_;
    Tanh(cLocal, cLocal, count);
    Muls(cLocal, cLocal, amplitude_, count);
    Adds(cLocal, cLocal, static_cast<float>(1.0), count);
    // y = activation * core, computed in fp32 and cast back to fp16 output.
    Cast(actF32Local, actF16Local, RoundMode::CAST_NONE, count);
    Mul(cLocal, cLocal, actF32Local, count);
    Cast(outF16Local, cLocal, RoundMode::CAST_NONE, count);
  }

  __aicore__ inline void CopyOut(int32_t tileIndex,
                                 LocalTensor<half>& outF16Local) {
    int32_t actualRows =
        min(TILE_M, static_cast<int32_t>(tokenCount_ - tileIndex * TILE_M));
    DataCopy(outGm_[tileIndex * TILE_M * rankDim_], outF16Local,
             DataCopyParams{actualRows, rankDim_ * sizeof(half),
                            rankDim_ * sizeof(half), rankDim_ * sizeof(half)});
  }

 private:
  TPipe pipe_;
  TQue<QuePosition::VECIN, BUFFER_NUM> inQueueA_;
  TQue<QuePosition::VECIN, BUFFER_NUM> inQueueB_;
  TQue<QuePosition::VECOUT, BUFFER_NUM> outQueueC_;
  TQue<QuePosition::VECIN, 1> actF16Queue_;
  TQue<QuePosition::VECIN, 1> actF32Queue_;
  TQue<QuePosition::VECIN, 1> outF16Queue_;
  TQue<QuePosition::VECIN, 1> biasQueue_;
  // Contract note: exactly five GlobalTensors — four inputs and one output.
  // The generated core never appears as a GlobalTensor.
  GlobalTensor<float> aGm_;
  GlobalTensor<float> bGm_;
  GlobalTensor<float> biasGm_;
  GlobalTensor<half> actGm_;
  GlobalTensor<half> outGm_;
  LocalTensor<float> biasLocal_;
  Matmul<TPosition::GM, TPosition::VECIN> mm_;
  uint32_t tokenCount_;
  uint32_t hiddenDim_;
  uint32_t rankDim_;
  float amplitude_;
  int32_t mTileCount_;
};

extern "C" __global__ __aicore__ void ephemeral_core_apply(
    GM_ADDR rankActivation, GM_ADDR controllerHidden, GM_ADDR headWeight,
    GM_ADDR headBias, GM_ADDR scaledRankActivation, GM_ADDR workspace,
    GM_ADDR tiling) {
  GET_TILING_DATA(tilingData, tiling);
  KernelEphemeralCoreApply op;
  op.Init(rankActivation, controllerHidden, headWeight, headBias,
          scaledRankActivation, tilingData.amplitude, tilingData.tokenCount,
          tilingData.hiddenDim, tilingData.rankDim);
  op.Process();
}
