/*
 * mwg::block_givens_tile_apply - Ascend-C prototype (tile-local output
 * rotation; NOT COMPILED, NOT A PERFORMANCE CLAIM).
 *
 * Prototype for the input-dependent output subspace Q_theta(x) of the
 * manuscript's future-work section: block Givens rotations applied to
 * output tiles of a persistent low-rank projection.
 *
 * Semantics (one output tile of width TILE_N):
 *
 *   Given rank activations  Z in R^{T x R}          (persistent, GM)
 *   and the tile's factor   V_tile in R^{R x TILE_N} (persistent, GM)
 *   and the tile's angles   theta in R^{T x TILE_N/2} (descriptor, GM)
 *
 *   1. scratch:    load theta[t, :] for this tile into a UB scratch buffer;
 *   2. accumulate: Y_tile = Z @ V_tile                  (Matmul, cube);
 *   3. rotate:     for k in [0, TILE_N/2):
 *                      e = Y_tile[t, 2k];   o = Y_tile[t, 2k+1];
 *                      Y_tile[t, 2k]   = cos(theta[t,k]) * e
 *                                      - sin(theta[t,k]) * o;
 *                      Y_tile[t, 2k+1] = sin(theta[t,k]) * e
 *                                      + cos(theta[t,k]) * o;
 *   4. write:      copy Y_tile to the output tile in GM.
 *
 * Givens pairs never straddle the tile (TILE_N is even), so the angle chunk
 * a tile needs is contiguous and the rotate step never reads outside the
 * tile.  This source documents the UB layout and per-tile compute sequence
 * a compiled implementation must reproduce; the executable semantics
 * prototype is sim_block_givens_tile_apply.py, and the vectorized
 * algebraic reference is experiments/mwg_block_givens.py.
 *
 * Contract (prototype; mirrors the ephemeral_core_apply contract style):
 *   - exactly one global output (rotated_tile), same shape/dtype as the
 *     accumulated tile input would be;
 *   - the angle tensor is a persistent descriptor in GM: no ephemeral-core
 *     lifetime claim is made about it;
 *   - zero global workspace: the per-tile angle scratch lives in UB;
 *   - the intermediate rotated values exist only in UB; they are never
 *     written to GM.
 *
 * UB budget at TILE_M=8 (tokens per M tile), TILE_N=128, R=128,
 * fp16 activations/angles, fp32 accumulate:
 *   angle scratch  TILE_M * (TILE_N/2) * 2 B = 1.0 KiB
 *   A tile         TILE_M * R        * 2 B = 2.0 KiB
 *   B tile         R * TILE_N        * 2 B = 32 KiB
 *   C tile         TILE_M * TILE_N   * 4 B = 4.0 KiB
 *   cos/sin        2 * TILE_M * (TILE_N/2) * 4 B = 4.0 KiB
 *   = ~43 KiB per M-tile pass, within the 192 KiB Unified Buffer of
 *   Ascend 910B even with double buffering.
 */

#include "kernel_operator.h"

using namespace AscendC;

namespace {

constexpr int32_t TILE_M = 8;    // tokens per M tile
constexpr int32_t TILE_N = 128;  // output tile width (even; pairs inside)
constexpr int32_t MAX_RANK = 128;  // maximum rank dimension (v1 prototype)
constexpr int32_t BUFFER_NUM = 2;

}  // namespace

class KernelBlockGivensTileApply {
 public:
  __aicore__ inline KernelBlockGivensTileApply() {}

  /*
   * GM layout:
   *   rankActivation  [T, R]        fp16  (Z: persistent low-rank activation)
   *   tileFactor      [R, TILE_N]   fp16  (V_tile: this output tile's factor
   *                                        columns, transposed row-major)
   *   tileAngles      [T, TILE_N/2] fp32  (descriptor chunk for this tile)
   *   rotatedTile     [T, TILE_N]   fp16  (the rotated output tile)
   */
  __aicore__ inline void Init(GM_ADDR rankActivation, GM_ADDR tileFactor,
                              GM_ADDR tileAngles, GM_ADDR rotatedTile,
                              uint32_t tokenCount, uint32_t rankDim) {
    tokenCount_ = tokenCount;
    rankDim_ = rankDim;

    zGm_.SetGlobalBuffer(reinterpret_cast<__gm__ half*>(rankActivation),
                         tokenCount_ * rankDim_);
    vGm_.SetGlobalBuffer(reinterpret_cast<__gm__ half*>(tileFactor),
                         rankDim_ * TILE_N);
    angleGm_.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(tileAngles),
                             tokenCount_ * (TILE_N / 2));
    outGm_.SetGlobalBuffer(reinterpret_cast<__gm__ half*>(rotatedTile),
                           tokenCount_ * TILE_N);

    // UB buffers (per M tile):
    //   zLocal   TILE_M * rankDim          fp16  (A tile)
    //   vLocal   rankDim * TILE_N          fp16  (B tile, loaded once)
    //   cLocal   TILE_M * TILE_N           fp32  (C tile / accumulate)
    //   angleLocal TILE_M * (TILE_N/2)     fp32  (scratch: angle chunk)
    //   cosLocal, sinLocal TILE_M*(TILE_N/2) fp32
    //   outLocal TILE_M * TILE_N           fp16  (rotated tile before write)
    pipe_.InitBuffer(zQueue_, BUFFER_NUM, TILE_M * MAX_RANK * sizeof(half));
    pipe_.InitBuffer(vQueue_, 1, MAX_RANK * TILE_N * sizeof(half));
    pipe_.InitBuffer(cQueue_, BUFFER_NUM, TILE_M * TILE_N * sizeof(float));
    pipe_.InitBuffer(angleQueue_, BUFFER_NUM,
                     TILE_M * (TILE_N / 2) * sizeof(float));
    pipe_.InitBuffer(outQueue_, BUFFER_NUM, TILE_M * TILE_N * sizeof(half));
    cosLocal_.SetSize(TILE_M * (TILE_N / 2));
    sinLocal_.SetSize(TILE_M * (TILE_N / 2));

    // The tile's factor columns are identical for every M tile: load once.
    LocalTensor<half> vLocal = vQueue_.AllocTensor<half>();
    DataCopy(vLocal, vGm_, rankDim_ * TILE_N);
    vQueue_.EnQue(vLocal);
    vLocal_ = vQueue_.DeQue<half>();
  }

  __aicore__ inline void Process() {
    mTileCount_ = (tokenCount_ + TILE_M - 1) / TILE_M;
    for (int32_t i = 0; i < mTileCount_; ++i) {
      CopyIn(i);
      Compute(i);
      CopyOut(i);
    }
  }

 private:
  __aicore__ inline void CopyIn(int32_t mIdx) {
    // 1. scratch + accumulate inputs for this M tile.
    int32_t rowStart = mIdx * TILE_M;
    int32_t rows = Min(TILE_M, tokenCount_ - rowStart);

    LocalTensor<half> zLocal = zQueue_.AllocTensor<half>();
    DataCopy(zLocal, zGm_ + rowStart * rankDim_, rows * rankDim_);
    zQueue_.EnQue(zLocal);

    LocalTensor<float> angleLocal = angleQueue_.AllocTensor<float>();
    // scratch: load this tile's descriptor chunk (angles) for these rows.
    DataCopy(angleLocal, angleGm_ + rowStart * (TILE_N / 2),
             rows * (TILE_N / 2));
    angleQueue_.EnQue(angleLocal);

    LocalTensor<float> cLocal = cQueue_.AllocTensor<float>();
    // 2. accumulate: C tile = Z_tile @ V_tile (rank contributions).
    //    (Prototype notation; a compiled kernel uses matmul::Matmul with
    //    the same tiling as the v4 kernel: A[TM, R] fp16, B[R, TN] fp16.)
    MatmulZxV(zLocal, vLocal_, cLocal, rows);
    cQueue_.EnQue(cLocal);
  }

  __aicore__ inline void Compute(int32_t mIdx) {
    LocalTensor<float> cLocal = cQueue_.DeQue<float>();
    LocalTensor<float> angleLocal = angleQueue_.DeQue<float>();
    int32_t rowStart = mIdx * TILE_M;
    int32_t rows = Min(TILE_M, tokenCount_ - rowStart);
    int32_t pairs = TILE_N / 2;

    // 3. rotate: per-pair Givens rotation, in place in the C tile.
    //    cos/sin are computed once per (token, pair) into UB scratch.
    Cos(cosLocal_, angleLocal, rows * pairs);
    Sin(sinLocal_, angleLocal, rows * pairs);
    for (int32_t k = 0; k < pairs; ++k) {
      for (int32_t t = 0; t < rows; ++t) {
        float e = cLocal.GetValue(t * TILE_N + 2 * k);
        float o = cLocal.GetValue(t * TILE_N + 2 * k + 1);
        float c = cosLocal_.GetValue(t * pairs + k);
        float s = sinLocal_.GetValue(t * pairs + k);
        cLocal.SetValue(t * TILE_N + 2 * k, c * e - s * o);
        cLocal.SetValue(t * TILE_N + 2 * k + 1, s * e + c * o);
      }
    }

    LocalTensor<half> outLocal = outQueue_.AllocTensor<half>();
    Cast(outLocal, cLocal, rows * TILE_N, RoundMode::CAST_NONE);
    outQueue_.EnQue(outLocal);

    cQueue_.FreeTensor(cLocal);
    angleQueue_.FreeTensor(angleLocal);
  }

  __aicore__ inline void CopyOut(int32_t mIdx) {
    // 4. write: store the rotated tile to GM.
    LocalTensor<half> outLocal = outQueue_.DeQue<half>();
    int32_t rowStart = mIdx * TILE_M;
    int32_t rows = Min(TILE_M, tokenCount_ - rowStart);
    DataCopy(outGm_ + rowStart * TILE_N, outLocal, rows * TILE_N);
    outQueue_.FreeTensor(outLocal);
  }

  __aicore__ inline int32_t Min(int32_t a, int32_t b) { return a < b ? a : b; }

  /*
   * Prototype stand-in for matmul::Matmul<GM A, GM B, VECIN C> with the v4
   * tiling (TILE_M x rankDim @ rankDim x TILE_N).  Kept explicit here so
   * the accumulate step of the loop is visible; a compiled kernel replaces
   * the body with the Matmul template exactly as in
   * ephemeral_core_apply_v4_multicore.asc.
   */
  __aicore__ inline void MatmulZxV(const LocalTensor<half>& a,
                                   const LocalTensor<half>& b,
                                   const LocalTensor<float>& c, int32_t rows) {
    for (int32_t t = 0; t < rows; ++t) {
      for (int32_t n = 0; n < TILE_N; ++n) {
        float acc = 0.0f;
        for (int32_t r = 0; r < static_cast<int32_t>(rankDim_); ++r) {
          acc += static_cast<float>(a.GetValue(t * rankDim_ + r)) *
                 static_cast<float>(b.GetValue(r * TILE_N + n));
        }
        c.SetValue(t * TILE_N + n, acc);
      }
    }
  }

  __aicore__ inline void Cos(const LocalTensor<float>& dst,
                             const LocalTensor<float>& src, int32_t count) {
    for (int32_t i = 0; i < count; ++i) {
      dst.SetValue(i, cosf(src.GetValue(i)));
    }
  }

  __aicore__ inline void Sin(const LocalTensor<float>& dst,
                             const LocalTensor<float>& src, int32_t count) {
    for (int32_t i = 0; i < count; ++i) {
      dst.SetValue(i, sinf(src.GetValue(i)));
    }
  }

 private:
  TPipe pipe_;
  TQue<QuePosition::VECIN, BUFFER_NUM> zQueue_;
  TQue<QuePosition::VECIN, 1> vQueue_;
  TQue<QuePosition::VECIN, BUFFER_NUM> angleQueue_;
  TQue<QuePosition::VECIN, BUFFER_NUM> cQueue_;
  TQue<QuePosition::VECOUT, BUFFER_NUM> outQueue_;
  TBuf<TPosition::VECCALC> cosBuf_;
  TBuf<TPosition::VECCALC> sinBuf_;
  LocalTensor<float> cosLocal_;
  LocalTensor<float> sinLocal_;
  LocalTensor<half> vLocal_;
  GlobalTensor<half> zGm_;
  GlobalTensor<half> vGm_;
  GlobalTensor<float> angleGm_;
  GlobalTensor<half> outGm_;
  int32_t tokenCount_ = 0;
  int32_t rankDim_ = 0;
  int32_t mTileCount_ = 0;
};

extern "C" __global__ __aicore__ void block_givens_tile_apply(
    GM_ADDR rankActivation, GM_ADDR tileFactor, GM_ADDR tileAngles,
    GM_ADDR rotatedTile, GM_ADDR kernelTiling) {
  KernelBlockGivensTileApply op;
  // Tiling is read from the host in a compiled implementation; the
  // prototype fixes TILE_M/TILE_N at compile time and takes tokenCount /
  // rankDim as scalar args in a compiled signature.
  (void)kernelTiling;
  op.Init(rankActivation, tileFactor, tileAngles, rotatedTile, 128, 128);
  op.Process();
}
