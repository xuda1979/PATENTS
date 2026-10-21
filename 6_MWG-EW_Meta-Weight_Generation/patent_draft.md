# Patent Application Draft

## Title of Invention

Meta-Weight Generation System and Method for On-the-Fly Ephemeral Weights in Memory-Bound Neural Network Inference

**Short Name**: MWG-EW

---

## Technical Field

The present invention relates to artificial intelligence inference systems, neural network model compression, accelerator-aware machine learning, and memory-optimized execution of large language models and other deep neural networks. More particularly, the invention relates to dynamically generating temporary neural network weights during inference and consuming said weights inside fast local memory without storing corresponding dense matrices in external memory.

---

## Background Art

### 1. Root Cause of Slow Large-Model Inference

Modern large language model inference is often limited not by raw arithmetic throughput, but by the cost of repeatedly moving large parameter matrices from external memory into on-chip memory structures. In dense transformer architectures, feed-forward network blocks account for a large fraction of parameters and require repeated movement of large up-projection, gate, and down-projection matrices.

As accelerator compute density grows faster than external-memory bandwidth, a large fraction of matrix-compute units remains underutilized while waiting for weight data. This gap is commonly referred to as the memory wall.

### 2. Limits of Existing Mitigations

Existing techniques only partially address this bottleneck:

1. **Quantization** reduces weight size but still requires reading the weight tensors from external memory.
2. **Mixture-of-Experts (MoE)** reduces active computation, but active experts still need to be fetched, and expert routing introduces additional memory movement.
3. **Low-rank adaptation methods** such as LoRA provide train-time or fine-tune-time low-rank updates, but typically still assume persistent storage of the underlying dense weights.
4. **Kernel fusion** reduces some intermediate-memory traffic, but does not remove the need to load large static FFN matrices.
5. **Hypernetworks** are known in machine learning, but prior approaches generally focus on functional parameter generation rather than a hardware-constrained inference loop in which generated descriptors are kept in on-chip memory and destroyed immediately after use.

Accordingly, the industry lacks a system-level invention that treats the dominant bottleneck as an external-memory transport problem and eliminates repeated dense-weight materialization from the inference path.

---

## Summary of the Invention

### 1. Purpose

The present invention aims to convert a memory-bound inference path into a more compute-dominant path by replacing externally stored dense weights with a shared meta-generator that emits temporary weight descriptors on demand.

### 2. Core Technical Solution

The invention provides a neural network inference system in which:

1. a conditioning module forms a token- and layer-specific conditioning signal;
2. a meta-generator produces low-rank factors, basis coefficients, or equivalent latent descriptors for one or more neural network projections;
3. a fused execution engine evaluates the projection through an associative decomposition such as `Y = (XU)V`;
4. the generated descriptors exist only within fast local memory such as SRAM, shared memory, cache, or registers; and
5. the descriptors are released after use and are not written back as persistent weights.

### 3. Key Inventive Points

The invention is not merely a mathematical factorization and not merely a generic hypernetwork. Its novelty lies in the coordinated combination of:

1. **conditional generation of projection descriptors during inference**,
2. **associative evaluation without dense matrix instantiation**,
3. **SRAM-resident generation-compute-release execution**, and
4. **migration from pretrained dense checkpoints by continual training or distillation**.

### 4. Technical Effects

The proposed system can:

1. reduce external-memory traffic associated with targeted dense projections,
2. lower model residency requirements for large FFN-heavy architectures,
3. improve utilization of underused tensor-compute resources on bandwidth-limited hardware,
4. enable larger effective models on devices with insufficient memory for dense deployments, and
5. create a hardware-software moat through custom fused kernels.

---

## Brief Description of Drawings

**Figure 1** illustrates a conventional dense-weight inference path versus the proposed ephemeral-weight path.

**Figure 2** illustrates the overall MWG-EW architecture including conditioning, meta-generation, fused execution, and local-memory release.

**Figure 3** illustrates the associative evaluation rule in which a dense matrix corresponding to `UV` is never instantiated in external memory.

**Figure 4** illustrates a tile-wise SRAM-resident kernel flow for generation-compute-release.

**Figure 5** illustrates migration from a pretrained dense model via freezing, insertion of a meta-generator, and continual training or knowledge distillation.

**Figure 6** illustrates deployment embodiments on edge devices, workstation GPUs, and cloud servers.

---

## Detailed Description of the Invention

### 1. System Architecture

In one embodiment, the system comprises:

- a token activation input module,
- a conditioning module,
- a layer-identifier module,
- a meta-generator,
- a descriptor assembly module,
- a fused projection engine,
- a local-memory lifetime controller,
- an optional profiler and verifier.

The conditioning module may receive a hidden state vector, an attention summary, a layer identifier, position information, a task tag, or a hardware execution state. The meta-generator may be a compact neural network, a basis-bank controller, a coefficient generator, or a hybrid thereof.

### 2. Runtime Generation of Temporary Weights

For each target layer and token group, the meta-generator outputs descriptors for at least one projection. In a preferred embodiment, the descriptors are low-rank factors `U` and `V` such that:

`W_eff ~= U V`

Instead of forming `W_eff` and storing it in external memory, the execution engine directly evaluates:

`Y = (XU)V`

If a gated FFN block is used, the system generates descriptors for up, gate, and down projections, executes the corresponding multiplications on chip, and then discards the descriptors.

### 3. Local-Memory Lifecycle

The descriptors are preferably created and consumed inside a single fused kernel. A local-memory lifetime controller allocates register or shared-memory space for descriptor tiles, schedules their consumption, and releases or overwrites them after accumulation of the corresponding output tile.

This design is distinct from a system that generates weights and then stores them in high-bandwidth memory or host memory for later use.

### 4. Layer Sharing and Basis Embodiments

In one embodiment, the meta-generator is shared across multiple layers and uses a learned layer embedding to specialize outputs. In another embodiment, the generator outputs coefficients of a learned basis bank and the actual factors are assembled on chip from said basis elements. In a further embodiment, only a subset of layers uses generated ephemeral weights while other layers keep static dense weights.

### 5. Adaptive Rank and Scheduling

The system may choose descriptor rank dynamically according to:

- token entropy,
- activation norm,
- layer depth,
- latency budget,
- measured bandwidth pressure,
- occupancy of tensor-compute units.

Thus, the system can trade accuracy against memory traffic in a controlled manner.

### 6. Token Grouping and Reuse

Although the system preferably generates descriptors per token or token group, the invention does not require a strict one-token-one-descriptor rule. Descriptors may be reused across a short token window, a cluster of similar hidden states, or a block of micro-batch elements, provided that the descriptors remain temporary and are not committed to persistent model storage.

### 7. Continual Training and Distillation

A practical migration path is important for commercialization. The invention therefore supports conversion from an existing pretrained model by:

1. selecting target projections, preferably FFN projections,
2. freezing all or part of the original model,
3. inserting the meta-generator and fused execution path,
4. training the inserted modules using additional corpora or teacher supervision.

Loss functions may include token-level cross-entropy, teacher-logit matching, hidden-state matching, or regularizers penalizing high descriptor rank or high memory cost.

### 8. Hardware Embodiments

The fused execution path may be implemented using:

- a Triton 内核,
- a CUDA 内核,
- a ROCm/HIP 内核,
- an NPU microcode path,
- a TPU custom call,
- a custom accelerator pipeline,
- or combinations thereof.

In a preferred GPU embodiment, the generator and the descriptor-consumption path are fused so that generated descriptor tiles are created, multiplied, accumulated, and released in shared memory or registers.

### 9. Deployment Embodiments

The invention may be used in:

1. cloud inference servers hosting large language models,
2. edge inference on consumer GPUs or NPUs,
3. workstation inference for local copilots,
4. memory-limited deployment of distilled or compressed foundation models,
5. MoE-like systems where generated descriptors replace or compress experts.

### 10. Distinction From Existing Approaches

The invention differs from known approaches as follows:

1. unlike quantization, it does not merely reduce bytes per stored weight; it changes how weights come into existence at inference time;
2. unlike static low-rank compression, it makes the descriptors input- and layer-conditioned;
3. unlike generic hypernetworks, it explicitly claims a local-memory execution lifecycle with no dense matrix materialization in external memory;
4. unlike MoE, it does not merely choose among stored experts; it computes the needed descriptors on demand.

---

## Representative Embodiments

### Embodiment A: Direct Low-Rank Descriptor Generation

The meta-generator directly emits `U_up`, `V_up`, `U_down`, and `V_down` for a targeted FFN block.

### Embodiment B: Basis-Coefficient Reconstruction

The meta-generator emits coefficients that select and combine basis tensors into temporary factors assembled entirely on chip.

### Embodiment C: Hybrid Static-Dynamic Stack

Early layers use static dense weights while memory-heavy middle and late FFN layers use generated ephemeral descriptors.

### Embodiment D: Hardware-Adaptive Scheduling

The system reads current hardware counters or configuration values and selects descriptor rank or token grouping to maintain a target bandwidth-compute ratio.

### Embodiment E: Distilled Replacement of Selected Open-Source Models

An open-source pretrained model is converted by replacing a subset of FFN blocks with generated ephemeral descriptors, freezing selected original parameters, and training against the original model as a teacher.

---

## Example Mathematical Description

Let `x_t in R^(1 x d)` be a token hidden state and `e_l` a layer embedding. A conditioning vector is formed:

`c_(t,l) = C(x_t, e_l)`

The generator outputs:

`(U_up, V_up, U_gate, V_gate, U_down, V_down) = G_theta(c_(t,l))`

Then a gated FFN may be computed as:

`a = phi((x_t U_up) V_up)`

`g = psi((x_t U_gate) V_gate)`

`y_t = (((a .* g) U_down) V_down)`

with the generated factors consumed in local memory and released after use.

---

## Initial Claim Themes

The strongest claim themes presently identified are:

1. a system claim centered on conditional meta-generation plus no-write-back local execution,
2. a method claim centered on generation-compute-release,
3. dependent claims covering basis banks, adaptive rank, grouped-token reuse, and hybrid static-dynamic scheduling,
4. training claims covering insertion into pretrained models via continual training or distillation,
5. hardware claims covering fused Triton or equivalent kernels.

---

## Preliminary Commercial Significance

This invention is commercially significant because it maps well onto accelerators whose available matrix-compute throughput grows faster than memory bandwidth. If validated, the system can reduce the memory barrier that currently limits deployment of larger models on edge devices and cloud inference fleets.

The strongest moat is expected to reside not only in model design but also in the low-level fused kernel implementation that proves generated descriptors can remain on chip and avoid external-memory materialization.

---

## Filing Notes

### 1. Evidence Needed for a Strong Filing

- profiler traces showing absence of descriptor write-back,
- a benchmark showing reduced memory footprint on a target model,
- a loss-recovery study versus a dense teacher,
- one implementation example using a fused kernel.

### 2. Potential Divisional Topics

- token-grouped descriptor reuse,
- basis-bank reconstruction on chip,
- adaptive-rank scheduler,
- hardware counter guided switching between static and generated weights,
- MoE expert replacement using generated descriptors.

### 3. Tentative Search Terms

- ephemeral weights inference
- on-the-fly weight generation transformer
- hypernetwork inference local memory
- low-rank generated FFN weights
- no materialization matrix product inference
- SRAM resident generated weights

---

## Draft Abstract

The present invention discloses a neural network inference system and method that replace externally stored dense projection matrices with on-demand generated temporary weight descriptors. A conditioning module derives a token- and layer-specific conditioning signal, and a meta-generator produces low-rank factors, basis coefficients, or equivalent latent descriptors for one or more projections of a neural network layer. A fused execution engine evaluates the projection through an associative decomposition such as `Y = (XU)V`, whereby a dense matrix corresponding to `UV` is not instantiated in external memory. The generated descriptors are created, consumed, and released inside fast local memory including SRAM, shared memory, cache, or registers, without write-back as persistent weights. The invention is particularly suitable for bandwidth-limited inference of large language models and other deep neural networks, and supports migration from pretrained dense models by continual training or knowledge distillation.
