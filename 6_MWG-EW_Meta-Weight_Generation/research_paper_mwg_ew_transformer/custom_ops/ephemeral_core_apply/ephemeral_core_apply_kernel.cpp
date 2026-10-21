/*
 * mwg::ephemeral_core_apply - Ascend-C kernel source (arm 4, no-store contract)
 *
 * Semantics (must match the algebraic reference in
 * experiments/mwg_four_arm_lifetime_benchmark.py exactly):
 *
 *   scaled_rank_activation[t, r]
 *     = rank_activation[t, r]
 *       * ( 1 + amplitude * tanh( controller_hidden[t, :] @ head_weight[:, r]
 *                                 + head_bias[r] ) )
 *
 * The generated diagonal core therefore exists only as LocalTensors in
 * UB/scratch: it is computed into the C tile buffer, transformed in place
 * (tanh, scale, offset), and multiplied into the activation tile.  It is
 * never declared as a GlobalTensor and never copied to global memory.
 *
 * Contract properties required by contract.example.json:
 *   - exactly one global output (scaled_rank_activation, same shape and dtype
 *     as rank_activation);
 *   - zero global workspace (every shape parameter is a scalar kernel
 *     argument; there is no tiling struct in workspace memory);
 *   - source_audit.no_global_core_tensor == true: no GlobalTensor refers to
 *     the core values;
 *   - source_audit.no_core_datacopy_to_global == true: no DataCopy writes the
 *     core values to GM; the only GM writes are the final scaled activation
 *     tiles (the declared output);
 *   - deterministic: no RNG, no atomics, no device-clock dependence.
 *
 * v1 constraints (enforced by the benchmark harness defaults; see README):
 *   - controller tensors (controller_hidden, head_weight^T, head_bias) are
 *     fp32; rank_activation and the output are fp16.
 *   - hiddenDim (H) == TILE_K == 128.
 *   - 16 <= rankDim (R) <= TILE_N == 128, and R % 16 == 0 (no N tiling in v1).
 *   - tokenCount (T) >= 1; M tiling handles arbitrary T with tail rows.
 *   - All GM tensors are contiguous with 32-byte-aligned base addresses.
 *   - head_weight is expected TRANSPOSED by the host wrapper: GM layout
 *     [R, H] (row-major W^T) so the single B tile is a set of contiguous
 *     H-length rows.
 *
 * UB budget at TILE_M=8, H=128, R=128 (fp32 A/C/B, fp16 activation/output):
 *   2 * (A 4 KiB + B 64 KiB + C 4 KiB) + post buffers 8.5 KiB + bias 0.5 KiB
 *   = 153 KiB, comfortably within the 192 KiB Unified Buffer of Ascend 910B.
 */

#include "kernel_operator.h"

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
                              GM_ADDR headWeightTransposed, GM_ADDR headBias,
                              GM_ADDR scaledRankActivation, float amplitude,
                              uint32_t tokenCount, uint32_t hiddenDim,
                              uint32_t rankDim) {
    tokenCount_ = tokenCount;
    hiddenDim_ = hiddenDim;
    rankDim_ = rankDim;
    amplitude_ = amplitude;

    aGm_.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(controllerHidden),
                         tokenCount_ * hiddenDim_);
    // headWeightTransposed is [R, H] row-major in GM.
    bGm_.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(headWeightTransposed),
                         rankDim_ * hiddenDim_);
    biasGm_.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(headBias), rankDim_);
    actGm_.SetGlobalBuffer(reinterpret_cast<__gm__ half*>(rankActivation),
                           tokenCount_ * rankDim_);
    outGm_.SetGlobalBuffer(reinterpret_cast<__gm__ half*>(scaledRankActivation),
                           tokenCount_ * rankDim_);

    pipe_.InitBuffer(inQueueA_, BUFFER_NUM, TILE_M * TILE_K * sizeof(float));
    pipe_.InitBuffer(inQueueB_, BUFFER_NUM, TILE_K * TILE_N * sizeof(float));
    pipe_.InitBuffer(outQueueC_, BUFFER_NUM, TILE_M * TILE_N * sizeof(float));
    // Post-processing buffers (activation staging and fp16 output staging).
    pipe_.InitBuffer(actF16Queue_, 1, TILE_M * TILE_N * sizeof(half));
    pipe_.InitBuffer(actF32Queue_, 1, TILE_M * TILE_N * sizeof(float));
    pipe_.InitBuffer(outF16Queue_, 1, TILE_M * TILE_N * sizeof(half));
    pipe_.InitBuffer(biasQueue_, 1, TILE_N * sizeof(float));

    mTileCount_ = (tokenCount_ + TILE_M - 1) / TILE_M;
  }

  __aicore__ inline void Process() {
    // Bias is copied once: it is identical for every M tile.
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
    // B tile: the whole W^T [R, H], contiguous in GM.
    DataCopy(bLocal, bGm_[0], rankDim_ * hiddenDim_);
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
  // Audit note: exactly five GlobalTensors exist in this kernel — four inputs
  // and one output.  The generated core never appears as a GlobalTensor.
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

extern "C" __global__ __aicore__ void ephemeral_core_apply_kernel(
    GM_ADDR rankActivation, GM_ADDR controllerHidden,
    GM_ADDR headWeightTransposed, GM_ADDR headBias,
    GM_ADDR scaledRankActivation, float amplitude, uint32_t tokenCount,
    uint32_t hiddenDim, uint32_t rankDim) {
  KernelEphemeralCoreApply op;
  op.Init(rankActivation, controllerHidden, headWeightTransposed, headBias,
          scaledRankActivation, amplitude, tokenCount, hiddenDim, rankDim);
  op.Process();
}
