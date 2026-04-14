# Patent Claims Document
# Meta-Weight Generation for On-the-Fly Ephemeral Weights (MWG-EW)

*This file is a first-pass claim set aligned with the initial patent draft and intended for later attorney refinement.*

---

## Independent Claims

### Claim 1 (System Claim)

A neural network inference system, comprising:

a) a conditioning module configured to obtain, for an inference step, a conditioning signal comprising at least a token-dependent feature representation and a layer identifier;

b) a meta-generator configured to generate, from the conditioning signal, weight descriptors for at least one neural network linear transformation, wherein the weight descriptors comprise low-rank factors, basis coefficients, latent factors, or combinations thereof;

c) a fused execution engine configured to evaluate the linear transformation using the generated weight descriptors according to an associative decomposition of a matrix product, including a form `Y = (XU)V`, such that a full dense weight matrix corresponding to `UV` is not instantiated in external memory;

d) a local-memory management module configured to hold the generated weight descriptors only within a fast local memory region comprising SRAM, shared memory, cache, registers, or combinations thereof during execution; and

e) a release controller configured to discard the generated weight descriptors after completion of said execution without writing the generated weight descriptors back to external memory.

### Claim 2 (Method Claim)

A method for performing memory-efficient neural network inference, comprising:

S1) receiving an activation tensor for a current inference step;

S2) forming a conditioning signal using at least a token feature representation derived from the activation tensor and a layer identifier;

S3) generating, by a meta-generator, low-rank factors or equivalent weight descriptors for at least one projection associated with a neural network layer;

S4) computing an output using an associative matrix-product decomposition in which the generated weight descriptors are consumed without explicitly materializing a corresponding dense weight matrix in external memory;

S5) keeping the generated weight descriptors only within a local-memory region during the computing of S4; and

S6) releasing the generated weight descriptors after use without storing the generated weight descriptors as persistent model weights.

### Claim 24 (Computer-Readable Medium Claim)

A non-transitory computer-readable storage medium storing instructions that, when executed by one or more processors of an AI accelerator, cause the one or more processors to perform the method of claim 2.

---

## Dependent Claims

### Claims Depending from Claim 1

**Claim 3.** The system according to claim 1, wherein the conditioning signal further comprises at least one of a sequence-position embedding, a routing summary, a domain identifier, a task identifier, a batch statistic, or a hardware profile.

**Claim 4.** The system according to claim 1, wherein the meta-generator is shared across a plurality of transformer layers and uses layer embeddings to differentiate generated weights for different layers.

**Claim 5.** The system according to claim 1, wherein the weight descriptors comprise first and second low-rank factors `U` and `V` having rank `r` satisfying `r < min(d_in, d_out)` for a target projection of dimensions `d_in x d_out`.

**Claim 6.** The system according to claim 1, wherein the meta-generator outputs coefficients for a learned basis bank, and the fused execution engine reconstructs the low-rank factors from said coefficients entirely within the fast local memory region.

**Claim 7.** The system according to claim 1, wherein the fused execution engine is configured to process an up-projection, a gate projection, and a down-projection of a feed-forward network block by generating separate weight descriptors for each projection.

**Claim 8.** The system according to claim 1, wherein the fused execution engine is implemented as a persistent GPU kernel that performs a generation-compute-release cycle within a single kernel launch.

**Claim 9.** The system according to claim 1, wherein the local-memory management module prevents a write-back of the generated weight descriptors to high-bandwidth memory, off-chip DRAM, or host memory.

**Claim 10.** The system according to claim 1, wherein the fused execution engine uses tensor-core, matrix-core, systolic-array, or equivalent mixed-precision compute units to generate and consume the weight descriptors.

**Claim 11.** The system according to claim 1, wherein the rank `r` is adaptively selected according to at least one of token complexity, layer depth, latency target, available bandwidth, or hardware occupancy.

**Claim 12.** The system according to claim 1, wherein the inference system further comprises a scheduler configured to switch between generated ephemeral weights and stored static weights on a per-layer, per-token, or per-batch basis.

### Claims Depending from Claim 2

**Claim 13.** The method according to claim 2, wherein S3 comprises generating a first low-rank factor `U` and a second low-rank factor `V` and S4 comprises computing `Y = (XU)V`.

**Claim 14.** The method according to claim 2, wherein S3 further comprises generating descriptors for a gated feed-forward block and S4 comprises computing:
`A = phi((XU_up)V_up)`,
`G = psi((XU_gate)V_gate)`, and
`Y = ((A .* G)U_down)V_down`.

**Claim 15.** The method according to claim 2, wherein S2 uses a normalized hidden state vector and a learned layer embedding to form the conditioning signal.

**Claim 16.** The method according to claim 2, wherein S4 comprises tiling the activation tensor and the generated weight descriptors such that each tile is generated, multiplied, accumulated, and released before a next tile is generated.

**Claim 17.** The method according to claim 2, wherein S4 is executed entirely within one fused Triton, CUDA, ROCm, or equivalent accelerator kernel.

**Claim 18.** The method according to claim 2, wherein S6 comprises zeroizing or overwriting the generated weight descriptors in local memory after accumulation of the output.

**Claim 19.** The method according to claim 2, further comprising clustering or grouping multiple tokens having similar conditioning signals and reusing at least part of the generated weight descriptors across the grouped tokens for a bounded time window.

**Claim 20.** The method according to claim 2, wherein a profiler verifies that no full dense matrix corresponding to the generated weight descriptors is written to external memory during S4.

### Training, Migration, and Deployment Claims

**Claim 21.** The system according to claim 1, further comprising a training pipeline configured to initialize from a pretrained dense model, freeze a first subset of parameters, insert the meta-generator in place of at least one dense projection, and optimize remaining parameters using continual training or knowledge distillation.

**Claim 22.** The system according to claim 21, wherein the training pipeline minimizes a loss comprising at least one of token-level cross-entropy, hidden-state matching, attention-map matching, KL divergence to a teacher model, or bandwidth-aware regularization.

**Claim 23.** The system according to claim 1, wherein the system is deployed on an edge device, workstation GPU, server GPU, NPU, TPU, or custom AI accelerator whose peak matrix-compute throughput exceeds sustainable external-memory bandwidth for dense inference.

---

## Optional Attorney Expansion Directions

1. Add jurisdiction-specific claim formats for China, PCT, and US filings.
2. Split claims between algorithm claims and hardware-execution claims.
3. Draft a divisional family covering token grouping, basis-bank reconstruction, and kernel-level non-write-back guarantees.

---

## Claim Dependency Chart

```
Claim 1 (System - Independent)
|-- Claim 3 (Extended conditioning signal)
|-- Claim 4 (Shared meta-generator across layers)
|-- Claim 5 (Low-rank factors)
|-- Claim 6 (Basis-bank coefficients)
|-- Claim 7 (FFN up/gate/down projections)
|-- Claim 8 (Persistent fused kernel)
|-- Claim 9 (No write-back)
|-- Claim 10 (Tensor-core execution)
|-- Claim 11 (Adaptive rank)
|-- Claim 12 (Hybrid static/dynamic switching)
|-- Claim 21 (Migration from pretrained model)
|   |-- Claim 22 (Training objectives)
|-- Claim 23 (Deployment hardware scope)

Claim 2 (Method - Independent)
|-- Claim 13 (Y = (XU)V)
|-- Claim 14 (Gated FFN form)
|-- Claim 15 (Normalized hidden state + layer embedding)
|-- Claim 16 (Tile-wise generation-compute-release)
|-- Claim 17 (Single fused accelerator kernel)
|-- Claim 18 (Local-memory zeroization)
|-- Claim 19 (Grouped-token reuse)
|-- Claim 20 (Profiler verification)

Claim 24 (Computer-Readable Medium - Independent)
```

**Total Claims: 24** (3 independent, 21 dependent)
