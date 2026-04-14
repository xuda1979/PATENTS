# Preliminary Prior Art Framing
# Meta-Weight Generation for On-the-Fly Ephemeral Weights (MWG-EW)

---

## Scope Note

This document is an internal first-pass prior-art framing memo.

- No live patent-database or academic-database search was executed while preparing this file.
- The purpose of this memo is to define the likely novelty boundary, closest technical neighborhoods, and recommended keyword strategy for a later formal search.
- Any patentability or freedom-to-operate conclusion in this file is therefore preliminary only.

---

## 1. Claimed Problem Space

The proposed invention sits at the intersection of:

1. transformer inference acceleration,
2. dynamic or generated neural-network weights,
3. low-rank factorization,
4. accelerator-kernel fusion,
5. memory-bandwidth reduction for large models.

The likely strongest patent thesis is not "low-rank matrices" by themselves and not "hypernetworks" by themselves, but rather:

1. runtime generation of temporary projection descriptors,
2. associative evaluation without dense materialization,
3. SRAM-resident generation-compute-release execution,
4. non-write-back handling of generated descriptors.

---

## 2. Nearest Prior-Art Categories

### Category A: Dense Transformer Inference

This category covers standard transformer and LLM inference pipelines in which FFN and attention weights are stored persistently and loaded from external memory during inference.

**Relevance**:

- establishes the baseline memory wall problem,
- confirms that dense FFN matrices dominate storage in many models,
- does not by itself disclose generated ephemeral weights.

**Likely distinction of MWG-EW**:

- dense weights are replaced by generated temporary descriptors,
- the dense matrix is not externally materialized.

### Category B: Quantization and Compression

This includes weight-only quantization, activation-aware quantization, structured pruning, and static low-rank compression.

**Relevance**:

- reduces bytes per weight,
- may reduce footprint substantially,
- still presumes a stored weight tensor or stored low-rank factors.

**Likely distinction of MWG-EW**:

- descriptors are generated conditioned on runtime input and layer identity,
- descriptors are temporary rather than persistent model weights.

### Category C: Hypernetworks and Meta-Networks

This category is the closest conceptual neighborhood. A hypernetwork generates parameters for another network.

**Relevance**:

- teaches the general idea of generating weights from a secondary network,
- may cover token- or task-conditioned parameter generation.

**Likely distinction of MWG-EW**:

- explicit claim focus on inference-time memory traffic reduction,
- hardware-aware associative evaluation such as `Y = (XU)V`,
- fast-local-memory lifecycle with no external write-back,
- fused kernel implementation boundary.

### Category D: Low-Rank Adaptation and Factorized Networks

This includes LoRA-like methods, low-rank matrix factorization, tensor decomposition, and matrix-product-state style compression.

**Relevance**:

- provides algebraic tools for representing large projections compactly,
- may teach using `U` and `V` factors.

**Likely distinction of MWG-EW**:

- factors are not merely static stored parameters,
- factors are generated on demand from runtime conditioning information,
- system claims emphasize lifecycle and memory path, not only algebraic representation.

### Category E: Mixture-of-Experts and Conditional Computation

This category covers expert routing, sparse activation, token-dependent compute selection, and expert caching.

**Relevance**:

- uses token-conditioned computation,
- addresses compute efficiency,
- still generally relies on fetching active expert weights.

**Likely distinction of MWG-EW**:

- generates descriptors instead of fetching stored experts,
- targets weight-movement reduction rather than only sparse activation.

### Category F: Kernel Fusion and On-Chip Execution

This includes FlashAttention-style IO-aware kernels, fused MLP kernels, and SRAM-optimized tiling schemes.

**Relevance**:

- strongly related on the hardware side,
- teaches minimizing reads and writes of intermediate activations,
- may disclose keeping some tiles in SRAM or shared memory.

**Likely distinction of MWG-EW**:

- fusion is extended upstream to the weight-creation stage,
- generated descriptors themselves are transient and locally scoped.

---

## 3. Preliminary Distinction Matrix

| Prior-Art Neighborhood | What It Likely Teaches | What MWG-EW Adds |
|------------------------|------------------------|------------------|
| Dense transformer inference | Stored FFN matrices loaded from memory | Generated temporary descriptors instead of stored dense matrices |
| Quantization | Smaller stored weights | Removes need for persistent projection matrices for selected blocks |
| Static low-rank compression | Fixed factorized weights | Runtime-conditioned factor generation |
| Hypernetworks | Weight generation in principle | Hardware-constrained no-write-back local execution |
| MoE | Token-conditional expert selection | Token-conditional descriptor generation instead of expert fetch |
| Fused kernels | IO-aware activation handling | Fused generation-compute-release for ephemeral descriptors |

---

## 4. Likely Novelty Core

The most defensible novelty core currently appears to be the combination of:

1. a conditioning signal including at least token features and layer identity,
2. a meta-generator producing low-rank or equivalent descriptors for FFN projections,
3. associative evaluation without forming the corresponding dense matrix in external memory,
4. fast-local-memory residency and destruction of the descriptors after use.

If prior-art search reveals direct hypernetwork references, the fallback novelty emphasis should shift further toward:

1. the no-write-back lifecycle,
2. the tile-wise fused kernel,
3. the memory-bandwidth-centric use case,
4. conversion of pretrained dense models into this execution regime.

---

## 5. Potential Vulnerability Areas

### 5.1 Generic Hypernetwork Literature

If older hypernetwork literature broadly claims generating weights from input features, then purely algorithmic claims around "a network generates another network's weights" may be vulnerable.

**Mitigation**:

- anchor claims to memory-residency behavior,
- anchor claims to associative no-materialization execution,
- anchor claims to accelerator-kernel behavior.

### 5.2 Static Low-Rank Models

Static factorization is well known.

**Mitigation**:

- emphasize that the factors are generated at inference time,
- emphasize that the factors are conditioned on runtime input and/or layer identity,
- emphasize temporary lifetime and no persistent storage.

### 5.3 Fused-Kernel Literature

Some IO-aware kernels may already claim on-chip retention of temporary tensors.

**Mitigation**:

- distinguish between temporary activations and temporary generated weights,
- claim a closed loop of generation plus consumption plus release within one local-memory lifecycle.

---

## 6. Recommended Search Keywords

### General

- ephemeral weights
- on-the-fly weight generation
- dynamic generated weights inference
- runtime generated neural network parameters
- local-memory weight generation

### Transformer / LLM Specific

- generated FFN weights transformer
- dynamic feed-forward projection generation
- hypernetwork transformer inference
- low-rank generated projection LLM
- token-conditioned projection weights

### Hardware / Kernel Specific

- SRAM resident weight generation
- fused kernel generated weights
- no materialization matrix product accelerator
- generated weights shared memory GPU
- write-back avoidance generated descriptors

### Patent Search Variants

- neural network weight generation during inference
- temporary weight matrix generation
- meta-generator for inference acceleration
- memory bandwidth reduction using generated weights
- associative matrix multiplication without materializing weight matrix

---

## 7. Recommended Search Buckets

1. Patent databases:
   - CNIPA
   - WIPO Patentscope
   - Google Patents
   - USPTO
   - EPO Espacenet

2. Academic sources:
   - arXiv
   - Google Scholar
   - ACL Anthology
   - NeurIPS / ICML / ICLR proceedings
   - MLSys / ASPLOS / ISCA / MICRO proceedings

3. Implementation sources:
   - Triton language examples
   - vendor blogs on fused MLP kernels
   - accelerator compiler talks

---

## 8. Preliminary Filing Strategy

### Primary claim center

Center claims on the fused lifecycle:

`condition -> generate -> consume locally -> release without write-back`

### Secondary claim centers

1. low-rank factor generation,
2. basis-bank coefficient generation,
3. adaptive rank scheduling,
4. pretrained-model migration,
5. MoE expert replacement.

### Evidence that will materially improve patent strength

1. profiler trace proving absence of external-memory writes for generated descriptors,
2. comparison of HBM bytes per token versus a dense baseline,
3. loss-recovery evidence after continued training,
4. at least one Triton or equivalent kernel embodiment.

---

## 9. Preliminary Conclusion

The concept appears most promising as a system-and-execution patent rather than as a pure mathematical or pure machine-learning patent. The strongest practical moat is likely to come from proving that dynamically generated projection descriptors can stay inside local accelerator memory and be destroyed immediately after use while preserving model quality.

Before external filing, a formal novelty search should specifically test whether prior hypernetwork or generated-parameter patents already cover:

1. runtime-conditioned weight generation,
2. low-rank factor generation,
3. on-chip generated-weight execution,
4. accelerator-kernel level non-write-back behavior.

