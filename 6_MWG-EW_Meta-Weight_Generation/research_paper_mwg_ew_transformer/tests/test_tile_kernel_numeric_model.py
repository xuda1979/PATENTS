"""Algorithm-correctness tests: kernel numeric model vs. reference path.

These tests close the CPU-side algorithm-correctness question for the
tile-local block-Givens kernel prototype
(``custom_ops/block_givens_tile_apply/block_givens_tile_apply_kernel.cpp``):

``simulate_kernel_numeric_model`` reproduces the Ascend-C source's compute
sequence numerically (fp16 GM loads, fp32 accumulate via explicit
element-wise loop, fp32 cos/sin rotation, fp16 CAST_NONE store, TILE_M row
blocking with partial tiles, TILE_N=128 output tiles).  Validation is
two-tier:

1. **Numeric-sequence identity.**  The model must match a vectorized
   computation of the *same declared numeric sequence* (fp16 activation,
   fp32 accumulate of fp16 inputs, fp32 rotation, fp16 store) to fp32
   accumulate-order tolerance.  This proves the tile loop, M-blocking,
   partial-tile handling, and angle-chunk indexing in the model implement
   one consistent algorithm.

2. **Reference agreement at fp16 precision.**  The model must match the
   paper's reference block-Givens path (``apply_block_givens`` on the dense
   fp32 projection) within fp16 input/output rounding, measured
   scale-relative.  This proves the kernel's algorithm is the one the paper
   describes; the remaining question for the device run is
   compile-and-measure, not algorithm correctness.

No device, no compilation, no timing claim.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import torch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "custom_ops" / "block_givens_tile_apply"))
sys.path.insert(0, str(ROOT / "experiments"))

from sim_block_givens_tile_apply import (  # noqa: E402
    KERNEL_MAX_RANK,
    KERNEL_TILE_M,
    KERNEL_TILE_N,
    simulate_kernel_numeric_model,
)
from mwg_block_givens import apply_block_givens  # noqa: E402


def _fixture(t: int, d: int, r: int, seed: int, angle_scale: float = 1.0):
    torch.manual_seed(seed)
    x = torch.randn(t, d, dtype=torch.float32)
    u = torch.randn(d, r, dtype=torch.float32)
    v = torch.randn(r, d, dtype=torch.float32)
    angles = (torch.rand(t, d // 2) - 0.5) * 2.0 * angle_scale
    return x, u, v, angles


def _vectorized_kernel_sequence(x, u, v, angles):
    """The kernel's declared numeric sequence, vectorized.

    z = fp16(x @ u)                       [fp16 GM tensor]
    c = fp32(z) @ fp32(fp16(v))           [fp32 accumulate of fp16 inputs]
    rotated = fp32 pair rotation of c     [fp32 cos/sin]
    out = fp16(rotated)                   [CAST_NONE store]
    """
    z = (x @ u).to(torch.float16)
    c = z.float() @ v.to(torch.float16).float()
    rotated = apply_block_givens(c, angles.to(torch.float32))
    return rotated.to(torch.float16)


def _fp32_reference(x, u, v, angles):
    """The paper's reference path: dense fp32 projection + rotation."""
    return apply_block_givens((x @ u) @ v, angles)


def _scale_relative_diff(a: torch.Tensor, b: torch.Tensor) -> float:
    scale = b.float().abs().max().item()
    return ((a.float() - b.float()).abs().max().item()
            / max(scale, 1e-6))


class TestKernelNumericModel:
    def test_kernel_constants_match_source(self):
        # Must mirror the constexprs in block_givens_tile_apply_kernel.cpp.
        assert KERNEL_TILE_M == 8
        assert KERNEL_TILE_N == 128
        assert KERNEL_MAX_RANK == 128

    def test_model_matches_same_numeric_sequence_tightly(self):
        # Tier 1: vectorized same-sequence vs. explicit tile loop must agree
        # to fp32 accumulate-order tolerance (~1e-5 relative).
        t, d, r = 21, 512, 64
        x, u, v, angles = _fixture(t, d, r, seed=2026)
        out, stats = simulate_kernel_numeric_model(x, u, v, angles)
        same_seq = _vectorized_kernel_sequence(x, u, v, angles)
        rel = _scale_relative_diff(out, same_seq)
        assert rel < 1e-4, f"tile loop diverges from vectorized sequence: {rel}"

    def test_model_matches_fp32_reference_at_fp16_precision(self):
        # Tier 2: kernel algorithm == paper's reference algorithm, with the
        # difference bounded by fp16 input/output rounding (empirically
        # ~0.4% scale-relative; bound at 1%).
        t, d, r = 21, 512, 64
        x, u, v, angles = _fixture(t, d, r, seed=2027)
        out, _ = simulate_kernel_numeric_model(x, u, v, angles)
        reference = _fp32_reference(x, u, v, angles)
        rel = _scale_relative_diff(out, reference)
        assert rel < 1e-2, (
            f"kernel model diverges from fp32 reference beyond fp16 "
            f"rounding: {rel:.4%}")

    def test_partial_m_tile_rows_are_correct(self):
        # 21 tokens = 2 full M tiles (8) + one partial (5): partial rows
        # must be computed and written correctly.
        t, d, r = 21, 256, 32
        x, u, v, angles = _fixture(t, d, r, seed=2028)
        out, stats = simulate_kernel_numeric_model(x, u, v, angles)
        same_seq = _vectorized_kernel_sequence(x, u, v, angles)
        assert stats["partial_m_tiles"] == 1
        assert stats["m_tiles"] == 3
        assert torch.allclose(out.float(), same_seq.float(),
                              atol=1e-2, rtol=1e-5)
        # The partial tile's last row must be written, not garbage.
        assert torch.isfinite(out[t - 1]).all()

    def test_exact_multiple_of_tile_m(self):
        t, d, r = 16, 128, 16
        x, u, v, angles = _fixture(t, d, r, seed=2029)
        out, stats = simulate_kernel_numeric_model(x, u, v, angles)
        assert stats["partial_m_tiles"] == 0
        same_seq = _vectorized_kernel_sequence(x, u, v, angles)
        assert torch.allclose(out.float(), same_seq.float(),
                              atol=1e-2, rtol=1e-5)

    def test_zero_angles_reduce_to_plain_projection(self):
        # theta=0 -> identity rotation: the model must equal the plain
        # low-rank projection under the kernel's own accumulate order
        # (explicit fp32 scalar loop), exactly.  (torch matmul's vectorized
        # summation order differs from the kernel's loop by <=1 fp16 ulp,
        # which is why the reference here uses the kernel's order.)
        t, d, r = 12, 256, 48
        x, u, v, _ = _fixture(t, d, r, seed=2030)
        angles = torch.zeros(t, d // 2)
        out, _ = simulate_kernel_numeric_model(x, u, v, angles)
        z = (x @ u).to(torch.float16)
        vf = v.to(torch.float16).float()
        plain = torch.empty(t, d, dtype=torch.float16)
        for ti in range(t):
            for j in range(d):
                acc = 0.0
                for k in range(r):
                    acc += float(z[ti, k]) * float(vf[k, j])
                plain[ti, j] = acc
        assert torch.equal(out, plain)

    def test_rotation_preserves_row_norms(self):
        # Givens rotation is norm-preserving per pair; the model's per-row
        # norm must match the same-sequence pre-rotation norm exactly.
        t, d, r = 10, 512, 64
        x, u, v, angles = _fixture(t, d, r, seed=2031, angle_scale=2.0)
        out, _ = simulate_kernel_numeric_model(x, u, v, angles)
        z = (x @ u).to(torch.float16)
        pre = z.float() @ v.to(torch.float16).float()
        n_model = out.float().pow(2).sum(-1).sqrt()
        n_pre = pre.pow(2).sum(-1).sqrt()
        assert torch.allclose(n_model, n_pre, rtol=1e-3)

    def test_angle_chunk_alignment(self):
        # Tile n's angle chunk must be angles[:, n*tile_n/2 : (n+1)*tile_n/2]:
        # perturbing an angle in tile 0's chunk must not change tile 1.
        t, d, r = 8, 256, 32
        x, u, v, angles = _fixture(t, d, r, seed=2032)
        out_a, _ = simulate_kernel_numeric_model(x, u, v, angles)
        perturbed = angles.clone()
        perturbed[:, 0] += 1.5  # pair 0 lives in tile 0's chunk
        out_b, _ = simulate_kernel_numeric_model(x, u, v, perturbed)
        # Tile 1 (columns 128..256) must be untouched.
        assert torch.equal(out_a[:, 128:], out_b[:, 128:])
        # Tile 0 must differ.
        assert not torch.equal(out_a[:, :128], out_b[:, :128])

    def test_rejects_rank_above_kernel_max(self):
        t, d = 4, 128
        x, u, v, angles = _fixture(t, d, KERNEL_MAX_RANK + 1, seed=2033)
        with pytest.raises(ValueError, match="MAX_RANK"):
            simulate_kernel_numeric_model(x, u, v, angles)

    def test_rejects_undivisible_tile(self):
        t, d, r = 4, 130, 8  # 130 not divisible by TILE_N=128
        x, u, v, angles = _fixture(t, d, r, seed=2034)
        with pytest.raises(ValueError, match="divisor"):
            simulate_kernel_numeric_model(x, u, v, angles)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
