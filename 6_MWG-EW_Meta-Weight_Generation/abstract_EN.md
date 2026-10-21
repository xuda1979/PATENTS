# Patent Abstract

## Meta-Weight Generation for On-the-Fly Ephemeral Weights (MWG-EW)

---

### Abstract

A neural network inference system and method are disclosed for converting a memory-bandwidth-limited large-model inference pipeline into a compute-dominant pipeline by generating feed-forward-network weights on demand rather than statically storing full projection matrices in external memory. A shared meta-generator receives a conditioning signal comprising at least a token feature representation and a layer identifier, and produces low-rank factors, basis coefficients, or equivalent latent weight descriptors for one or more linear transformations of a neural network block. A fused execution kernel computes an output according to an associative decomposition of a target matrix product, including forms such as `Y = (XU)V`, such that the full matrix `UV` is not instantiated in high-bandwidth memory, system DRAM, or persistent storage. The generated factors are consumed inside a fast local memory region including SRAM, shared memory, cache, or registers, and are released after use without write-back. The invention supports migration from pretrained transformer models through continual training or distillation, and is particularly suitable for memory-bound inference workloads on GPUs, AI accelerators, edge devices, and cloud inference servers where compute throughput substantially exceeds sustainable external-memory bandwidth.

**(Word count: 188)**

---

### Keywords

Large language model inference; memory wall; meta-weight generation; ephemeral weights; hypernetwork; low-rank factorization; SRAM-resident kernel; fused matmul; transformer feed-forward network; bandwidth reduction; continual training; knowledge distillation

---

### Brief Description of Drawings

**Figure 1**: Comparison between conventional static-weight inference and the proposed on-the-fly ephemeral-weight inference architecture

**Figure 2**: Overall MWG-EW system including meta-generator, conditioning module, SRAM-resident fused kernel, and inference controller

**Figure 3**: Associative execution flow showing generation of low-rank factors `U` and `V`, followed by `Y = (XU)V` without explicit materialization of `UV`

**Figure 4**: Fused SRAM dataflow in which token activations, layer embedding, and meta-generator outputs remain inside registers, shared memory, or cache during generation-compute-release execution

**Figure 5**: Training and migration pipeline from a pretrained dense model into a meta-weight-generated model via freezing, continual training, and teacher-student distillation

**Figure 6**: Deployment scenarios for edge devices, workstation GPUs, and cloud inference clusters

---

### Tentative IPC / CPC Directions

- G06N 3/0455 - Architectures of neural networks
- G06N 3/08 - Learning methods for neural networks
- G06F 9/3001 - Resource allocation or scheduling for computer architectures
- G06F 15/78 - Digital computing using specific architectures
- G06F 11/36 - Error detection, monitoring, or performance analysis in computing systems

---

### Technical Effects Summary

| Technical Metric | Conventional Dense FFN | MWG-EW |
|------------------|------------------------|--------|
| Weight residency | Full matrices in external memory | Shared meta-generator only |
| Per-token FFN weight traffic | Proportional to dense matrix size | Proportional to low-rank factors or latent codes |
| Full matrix instantiation | Required | Avoided |
| External-memory write-back of generated weights | Not applicable | Eliminated |
| Hardware utilization | Bandwidth-bound | More compute-intensive |
| Migration path from pretrained model | Full retraining often required for redesign | Continual training or distillation supported |
| Deployment fit | HBM-rich accelerators | Compute-rich, bandwidth-limited accelerators |
