# Technical Specification: Meta-Weight Generation for On-the-Fly Ephemeral Weights

## MWG-EW Mathematical Foundations and System Design

**Document Version**: 1.0  
**Status**: Initial technical framing for patent drafting and prototype planning

---

## 1. Problem Definition

### 1.1 Memory-Bound Inference

For a dense transformer feed-forward network (FFN), a hidden vector `x in R^(1 x d)` is typically processed as:

`h = phi(x W_up + b_up)`

`y = h W_down + b_down`

where `W_up in R^(d x m)` and `W_down in R^(m x d)` with `m > d`.

For large models, the dominant runtime bottleneck in autoregressive inference is frequently the transfer of `W_up` and `W_down` from external memory to on-chip memory structures, not the raw multiply-accumulate capability of the accelerator.

If each weight element occupies `b` bytes, the minimum external-memory traffic for the two FFN projections is approximately:

`B_dense ~= b (d m + m d) = 2 b d m`

and for gated FFN variants with up, gate, and down projections:

`B_gated ~= 3 b d m`

This traffic is paid repeatedly across tokens and layers.

### 1.2 Target Shift

The invention seeks to replace the above bandwidth scaling with a compute-centric path in which:

1. a compact shared generator is stored instead of all explicit FFN matrices,
2. layer- and token-conditioned low-rank factors are produced on demand,
3. the factors are consumed inside on-chip memory, and
4. the factors are discarded after use.

---

## 2. Meta-Weight Generation Formulation

### 2.1 Conditioning Signal

For token index `t` and layer `l`, define a conditioning signal:

`c_(t,l) = C(x_t, e_l, p_t, s_t)`

where:

- `x_t` is a token hidden-state representation,
- `e_l` is a layer embedding,
- `p_t` is an optional positional or sequence summary,
- `s_t` is optional routing or task-state metadata.

The conditioning module `C(.)` may include normalization, projection, compression, or quantization.

### 2.2 Generator Output

A meta-generator `G_theta` produces descriptors for one or more projections:

`(U_up, V_up, U_down, V_down) = G_theta(c_(t,l))`

with:

- `U_up in R^(d x r1)`,
- `V_up in R^(r1 x m)`,
- `U_down in R^(m x r2)`,
- `V_down in R^(r2 x d)`,

where `r1, r2 << min(d, m)`.

For gated FFN variants:

`(U_gate, V_gate)` are generated similarly.

### 2.3 Basis-Bank Variant

Instead of directly outputting full low-rank factors, the generator may output coefficients:

`alpha = g_alpha(c_(t,l))`

`beta = g_beta(c_(t,l))`

that combine learned bases:

`U_up = sum_k alpha_k B^U_k`

`V_up = sum_j beta_j B^V_j`

This variant allows a larger effective expressivity while keeping the conditioning output small.

---

## 3. Associative Evaluation Without Dense Materialization

### 3.1 Core Identity

For compatible matrices:

`Y = X (U V) = (X U) V`

The invention exploits the associativity of matrix multiplication so that the dense matrix `U V` need not be explicitly formed or stored.

### 3.2 Forward Pass

For a non-gated FFN:

`q_up = x U_up`

`h = phi(q_up V_up + b_up)`

`q_down = h U_down`

`y = q_down V_down + b_down`

For a gated FFN:

`a = phi((x U_up) V_up)`

`g = psi((x U_gate) V_gate)`

`y = (((a .* g) U_down) V_down)`

The full matrices `U_up V_up`, `U_gate V_gate`, and `U_down V_down` are never materialized in external memory.

### 3.3 Memory-Residency Rule

Generated descriptors must satisfy the following residency rule:

`Residency(descriptor) in {registers, shared memory, SRAM, cache}`

`WriteBack(descriptor, external memory) = 0`

except optionally for debug or offline verification modes.

This rule is central to the technical effect of reducing memory traffic.

---

## 4. Analytical Bandwidth Model

### 4.1 Dense Baseline

For one projection `W in R^(d x m)` in fp16:

`Traffic_dense = 2 d m bytes`

For `d = 4096`, `m = 14336`:

`Traffic_dense = 117,440,512 bytes ~= 112 MiB`

### 4.2 Low-Rank Descriptor Footprint

For a rank-`r` factorization:

`Traffic_factor = 2 (d r + r m) bytes`

For `d = 4096`, `m = 14336`:

| Rank r | Factor Bytes / Projection | Reduction vs Dense |
|--------|---------------------------|--------------------|
| 32 | 1,179,648 bytes | 99.6x |
| 64 | 2,359,296 bytes | 49.8x |
| 128 | 4,718,592 bytes | 24.9x |
| 256 | 9,437,184 bytes | 12.4x |

For a three-projection gated FFN block with `r = 64`, the explicit dense weights are about `336 MiB`, whereas the low-rank descriptor footprint is about `6.75 MiB`, before accounting for generator parameter amortization.

### 4.3 Amortized Generator Cost

Let `P_G` denote shared meta-generator parameters and `T` denote the number of tokens processed while the generator remains resident or reused.

The amortized external-memory cost per token is approximately:

`B_amortized ~= P_G / T + sum_i descriptor_i`

The architecture is advantageous when:

`P_G / T + descriptor traffic < dense weight traffic`

particularly in long-context or batched inference where `T` is large.

---

## 5. Hardware Execution Architecture

### 5.1 Module Decomposition

The system may include:

1. a token-conditioning module,
2. a layer-embedding lookup module,
3. a meta-generator micro-network,
4. a descriptor assembly unit,
5. a fused matmul engine,
6. a local-memory lifetime controller,
7. an optional profiler or verifier.

### 5.2 Fused Generation-Compute-Release Loop

```
Algorithm EphemeralFFNForward(x, layer_id)
Input: token activation x, layer identifier layer_id
Output: layer output y

1. c <- Conditioning(x, layer_id)
2. (U_up, V_up, U_gate, V_gate, U_down, V_down) <- MetaGenerate(c)
3. q_up   <- x * U_up
4. a      <- Act(q_up * V_up)
5. q_gate <- x * U_gate
6. g      <- Gate(q_gate * V_gate)
7. q_down <- (a .* g) * U_down
8. y      <- q_down * V_down
9. Release(U_up, V_up, U_gate, V_gate, U_down, V_down)
10. return y
```

In practice, steps 2-9 are preferably tiled and fused such that no complete descriptor set is held longer than necessary.

### 5.3 Triton or Equivalent Kernel Strategy

An implementation may use a custom kernel that:

1. loads an activation tile into registers or shared memory,
2. evaluates a small portion of the meta-generator,
3. constructs a descriptor tile,
4. immediately multiplies the descriptor tile with an activation tile,
5. accumulates results,
6. discards the descriptor tile,
7. repeats until the output tile is complete.

This converts external-memory traffic into local compute and on-chip movement.

---

## 6. Training and Migration From Pretrained Models

### 6.1 Initialization Path

Starting from a pretrained dense model `M_0`, construct a transformed model `M_1` by:

1. selecting target dense projections, preferably FFN projections,
2. freezing a subset of original parameters,
3. inserting `G_theta` and fused execution logic,
4. training the new modules using continual training, distillation, or both.

### 6.2 Distillation Objectives

Useful losses include:

`L = lambda_ce L_ce + lambda_kl L_kl + lambda_hid L_hidden + lambda_bw L_bandwidth`

where:

- `L_ce` is next-token cross-entropy,
- `L_kl` matches teacher logits,
- `L_hidden` matches hidden states before and after transformed blocks,
- `L_bandwidth` penalizes higher ranks or excess descriptor generation cost.

### 6.3 Rank Scheduling

Ranks may be:

- globally fixed,
- per-layer tuned,
- token-adaptive,
- hardware-adaptive according to a latency or bandwidth budget.

This provides a controllable accuracy-latency-memory tradeoff.

---

## 7. Engineering Embodiments

### 7.1 Direct-Factor Pilot Path

`G_theta` may directly emit low-rank factors for a single target projection. This is the
cleanest path for early kernel bring-up because it minimizes coefficient reconstruction
logic and allows direct comparison with a materialized `U V` reference path.

Under the reproducible analytical simulation in `simulation/mwg_ew_simulation.py`, a 1B
pilot with `d=2048`, `m=5632`, and one replaced projection gives the following:

| Rank | Effective Read (MiB/token) | Latency (ms) | Perplexity | Loss Increase |
|------|----------------------------|--------------|------------|---------------|
| Dense | 22.00 | 2.80 | 8.20 | 0.00% |
| 64 | 1.09 | 1.37 | 8.57 | 4.49% |
| 96 | 1.60 | 1.43 | 8.42 | 2.63% |

This pilot regime is best suited for validating the fused generation-consume-release loop
and proving that the generated object no longer behaves like a dense persistent weight.

### 7.2 Basis-Bank Patent-Grade Path

For the patent-grade three-projection gated FFN block, `G_theta` preferably emits basis
coefficients that are expanded on chip. This reduces descriptor transfer pressure while
preserving expressivity.

For `d=4096`, `m=14336`, three FFN projections, and the basis-bank path:

- dense gated-FFN footprint per block: `336.0 MiB`;
- `r=128` effective read per block: `11.08 MiB`;
- full-replacement batch latency: `2.27 s` versus `4.20 s` dense;
- validation-loss increase at full replacement: `3.20%`.

The analytical simulation therefore places the preferred operating point near `r=96` to
`r=128`, where the loss increase stays below `5%` while the end-to-end speedup remains
about `1.85x`.

### 7.3 Partial-Replacement Deployment Path

The invention does not require immediate full-model deployment. A practical staging path is
to replace only a subset of FFN blocks first.

At `r=128`, the simulation gives:

| Replacement Ratio | Batch Latency (s) | Peak Memory (GiB) | Max Context (tokens) | All-Reduce (MiB/step) |
|-------------------|-------------------|-------------------|----------------------|-----------------------|
| 25% | 3.72 | 61.71 | 24965 | 816 |
| 50% | 3.24 | 55.43 | 33547 | 608 |
| 75% | 2.75 | 49.14 | 42129 | 400 |
| 100% | 2.27 | 42.86 | 50711 | 192 |

This partial-replacement path is important for the disclosure because it shows that the
same lifecycle-controlled temporary object can create staged benefits in latency, context
capacity, and distributed-training communication.

### 7.4 Token-Group Reuse

Tokens with similar conditioning signals may reuse descriptors over a bounded token window.
For `r=128`, the simulation gives:

| Reuse Window | Effective Read (MiB/block) | Batch Latency (s) | Extra Loss Drift |
|--------------|----------------------------|-------------------|------------------|
| 1 | 11.08 | 2.27 | 0.0% |
| 2 | 10.40 | 2.23 | 0.2% |
| 4 | 10.06 | 2.20 | 0.6% |
| 8 | 9.89 | 2.19 | 1.5% |

Accordingly, bounded-window reuse is best described as an optional enhancement, not as a
precondition for the core patent effect.

### 7.5 Expert Replacement

In MoE-style systems, generated descriptors may replace or compress expert matrices,
reducing expert-loading traffic. The same temporary-object rule still applies: expert
descriptors are generated on demand, consumed on chip, and prevented from becoming a dense
external-memory object.

---

## 8. Reproducible Analytical Simulation

### 8.1 Source of Truth

All simulation numbers in this specification are generated from:

`simulation/mwg_ew_simulation.py`

That script is the single source of truth for the following quantities:

1. effective external-memory read;
2. end-to-end latency under partial or full FFN replacement;
3. peak-memory reduction and derived KV-cache context gain;
4. grouped-token reuse tradeoffs; and
5. distributed-training All-Reduce reduction.

### 8.2 Effective-Read Formula

For a dense target block:

`Traffic_dense = 2 d m`

For a low-rank descriptor path:

`Traffic_effective = alpha * 2 (d r + r m) + P_G / W`

where:

- `alpha` is the descriptor-compaction factor;
- `P_G` is the amortized generator-transfer term;
- `W` is the reuse window.

The patent-grade basis-bank path uses `alpha = 0.72`.

### 8.3 End-to-End Latency Formula

The total runtime is modeled as a fixed non-target share plus a target-block share:

`Latency_total = L_fixed + rho * [(1 - p) + p * C_path]`

where:

- `p` is the FFN replacement ratio;
- `rho` is the target-block contribution under the dense baseline;
- `C_path` mixes remaining memory pressure with added local compute.

This construction is intentionally conservative because attention, unchanged layers, and
framework overhead remain in the total runtime.

### 8.4 Memory, Context, and Communication Mapping

Peak memory is estimated by replacing the dense FFN resident share with the compact MWG-EW
resident share. The released HBM is then converted into additional KV-cache capacity under
an 80 GiB device budget and a `0.75 MiB/token` KV-cache cost.

Distributed training uses:

`AllReduce_mwg = Sync_non_target + (1 - p) * Sync_target_dense + p * Sync_generator`

In the patent-grade setup, this corresponds to `1024 MiB/step` for the dense baseline and
`192 MiB/step` at `100%` FFN replacement.

---

## 9. Simulation Results Summary

### 9.1 Patent-Grade Rank Frontier

| Rank | Effective Read (MiB/block) | Batch Latency (s) | Tokens/s | Tensor Utilization | Validation Loss | Loss Increase |
|------|----------------------------|-------------------|----------|--------------------|-----------------|---------------|
| Dense | 336.00 | 4.20 | 290.00 | 68.00% | 2.14 | 0.00% |
| 32 | 3.41 | 2.15 | 567.29 | 83.81% | 2.42 | 13.10% |
| 64 | 5.97 | 2.19 | 556.55 | 83.09% | 2.30 | 7.62% |
| 96 | 8.52 | 2.23 | 546.20 | 82.64% | 2.24 | 4.73% |
| 128 | 11.08 | 2.27 | 536.23 | 82.34% | 2.21 | 3.20% |
| 160 | 13.64 | 2.31 | 526.62 | 82.13% | 2.19 | 2.40% |
| 256 | 21.31 | 2.44 | 499.75 | 81.74% | 2.17 | 1.63% |

The preferred engineering region is therefore `r=96` to `r=128`.

### 9.2 Replacement-Ratio Sweep

| Replacement Ratio | Batch Latency (s) | Peak Memory (GiB) | Max Context (tokens) | Validation Loss | All-Reduce (MiB/step) |
|-------------------|-------------------|-------------------|----------------------|-----------------|-----------------------|
| 0% | 4.20 | 68.00 | 16384 | 2.14 | 1024 |
| 25% | 3.72 | 61.71 | 24965 | 2.16 | 816 |
| 50% | 3.24 | 55.43 | 33547 | 2.18 | 608 |
| 75% | 2.75 | 49.14 | 42129 | 2.19 | 400 |
| 100% | 2.27 | 42.86 | 50711 | 2.21 | 192 |

This table ties together the three most important patent-visible effects: less external
traffic, larger decode context, and lower synchronization volume.

### 9.3 Hardware Sensitivity

| HBM Bandwidth (TB/s) | Dense Latency (s) | MWG-EW Latency (s) | Speedup |
|----------------------|-------------------|--------------------|---------|
| 1.6 | 5.36 | 2.81 | 1.90x |
| 2.4 | 4.20 | 2.27 | 1.85x |
| 3.2 | 3.62 | 2.02 | 1.80x |

The relative gain is largest on the most bandwidth-constrained accelerator, which is fully
consistent with the original problem definition.

---

## 10. Verification Criteria

The patent thesis is strongest when the following can be demonstrated:

1. generated descriptors are not written to external memory during fused inference;
2. target-block traffic is reduced by at least one order of magnitude;
3. end-to-end runtime improves on bandwidth-limited hardware rather than only at the
   micro-kernel level;
4. released HBM can be converted into larger KV-cache or longer supported context;
5. distributed-training synchronization visibly shrinks for the targeted path.

Suggested profiler evidence:

- no off-chip store corresponding to full generated descriptors;
- reduced HBM bytes for the target FFN block;
- increased matrix-unit utilization with lower memory-stall share;
- lower All-Reduce volume or missing target-layer gradient packets.

---

## 11. Failure Modes and Safeguards

### 11.1 Quality Degradation

If the generated descriptors are under-parameterized, perplexity or downstream accuracy may
degrade. A fallback static path, partial replacement, or adaptive-rank policy mitigates
this risk.

### 11.2 Generator Bandwidth Spill

If the meta-generator becomes too large or poorly tiled, the design can regress toward a
memory-bound regime. Basis-bank compaction, persistent kernels, and layer sharing are
preferred safeguards.

### 11.3 Numerical Stability

Mixed-precision generation should use scaling, normalization, or accumulation safeguards for
stability.

### 11.4 Latency Jitter

Token-adaptive rank selection and token-group reuse should be bounded so that service-level
predictability is preserved.

---

## 12. Implementation Checklist

- [x] Define the target model family and FFN scope
- [x] Provide a reproducible analytical simulation script
- [x] Choose direct-factor and basis-bank descriptor paths
- [x] Quantify replacement-ratio, rank, and reuse-window tradeoffs
- [x] Map memory savings into explicit KV-cache context gain
- [x] Map target-layer replacement into explicit All-Reduce reduction
- [ ] Implement the fused generation-consume-release kernel
- [ ] Verify zero descriptor write-back with profiler evidence
- [ ] Validate numerical agreement against a materialized reference path
- [ ] Measure dense versus MWG-EW traffic on real hardware
- [ ] Validate downstream quality after continued training or distillation
