# Patent Claims Document
# Meta-Weight Generation for On-the-Fly Ephemeral Weights (MWG-EW)

*This file is a prosecution-oriented redraft intended to improve examination survivability by centering the claims on concrete technical features and fallback positions.*

---

## Drafting Objective

This redraft narrows the independent claims around:

1. a hardware memory hierarchy including on-chip local memory and external memory,
2. runtime generation of temporary projection descriptors from token and layer conditioning,
3. tile-wise associative evaluation without dense-matrix materialization in external memory, and
4. release of generated descriptors after use without external-memory write-back.

The goal is to present the invention as a technical solution to a memory-traffic problem in accelerator inference, rather than as an abstract weight-generation concept.

---

## Independent Claims

### Claim 1 (System Claim)

A neural network inference system, comprising:

a) an accelerator comprising matrix-compute units, an on-chip local memory region, and an external memory region;

b) a conditioning module configured to obtain, for a current inference step, a conditioning signal comprising at least a token-dependent feature representation and a layer identifier corresponding to a target neural-network layer;

c) a meta-generator configured to generate, from the conditioning signal, weight-descriptor tiles for at least one linear transformation of the target neural-network layer, wherein the weight-descriptor tiles comprise low-rank factors, basis coefficients for reconstruction of low-rank factors, or combinations thereof;

d) a fused execution engine configured to:

1. place a generated weight-descriptor tile in the on-chip local memory region,
2. evaluate the linear transformation by an associative matrix-product decomposition including `Y = (XU)V`,
3. accumulate an output tile while the generated weight-descriptor tile remains in the on-chip local memory region, and
4. release or overwrite the generated weight-descriptor tile before generation of a next weight-descriptor tile,

wherein the fused execution engine completes the linear transformation without storing a full dense weight matrix corresponding to the generated weight descriptors in the external memory region; and

e) a memory-lifecycle controller configured to prevent write-back of the generated weight-descriptor tiles from the on-chip local memory region to the external memory region during inference.

### Claim 2 (Method Claim)

A method for performing memory-efficient neural network inference on an accelerator having matrix-compute units, on-chip local memory, and external memory, the method comprising:

S1) receiving an activation tensor for a current inference step;

S2) forming a conditioning signal using at least a token feature representation derived from the activation tensor and a layer identifier;

S3) generating, by a meta-generator, weight-descriptor tiles for at least one projection associated with a neural-network layer;

S4) for each generated weight-descriptor tile, storing the generated weight-descriptor tile only in the on-chip local memory and computing a partial output using an associative matrix-product decomposition in which the generated weight-descriptor tile is consumed without materializing a corresponding full dense weight matrix in external memory;

S5) accumulating the partial output to produce an output tensor for the projection; and

S6) releasing or overwriting the generated weight-descriptor tile in the on-chip local memory before generating a next weight-descriptor tile, without storing the generated weight-descriptor tile as a persistent model weight in external memory.

### Claim 18 (Computer-Readable Medium Claim)

A non-transitory computer-readable storage medium storing instructions that, when executed by one or more processors of an accelerator, cause the one or more processors to perform the method of claim 2.

---

## Dependent Claims

### Claims Depending from Claim 1

**Claim 3.** The system according to claim 1, wherein the target neural-network layer is a feed-forward-network block of a transformer model.

**Claim 4.** The system according to claim 3, wherein the fused execution engine is configured to process an up-projection, a gate projection, and a down-projection of the feed-forward-network block by generating separate weight-descriptor tiles for each projection.

**Claim 5.** The system according to claim 1, wherein the conditioning signal further comprises at least one of a sequence-position embedding, a routing summary, a domain identifier, a task identifier, a batch statistic, or a hardware-execution profile.

**Claim 6.** The system according to claim 1, wherein the meta-generator is shared across a plurality of transformer layers and uses layer embeddings to differentiate generated outputs for different layers.

**Claim 7.** The system according to claim 1, wherein the weight-descriptor tiles comprise first and second low-rank factor tiles `U` and `V` having a rank `r` satisfying `r < min(d_in, d_out)` for a target projection of dimensions `d_in x d_out`.

**Claim 8.** The system according to claim 1, wherein the meta-generator outputs coefficients for a learned basis bank and the fused execution engine reconstructs the low-rank factors from the coefficients entirely within the on-chip local memory region.

**Claim 9.** The system according to claim 1, wherein the fused execution engine is implemented as a persistent accelerator kernel that performs generation, consumption, accumulation, and release of the generated weight-descriptor tiles within a single kernel launch.

**Claim 10.** The system according to claim 1, wherein the on-chip local memory region comprises registers, shared memory, SRAM, cache, or combinations thereof.

**Claim 11.** The system according to claim 1, wherein the memory-lifecycle controller is configured to zeroize or overwrite the generated weight-descriptor tiles after accumulation of a corresponding output tile.

**Claim 12.** The system according to claim 1, wherein the rank `r` is adaptively selected according to at least one of token complexity, layer depth, latency target, available bandwidth, or occupancy of the matrix-compute units.

**Claim 13.** The system according to claim 1, further comprising a scheduler configured to switch between generated weight descriptors and stored static weights on a per-layer, per-token, or per-batch basis.

### Claims Depending from Claim 2

**Claim 14.** The method according to claim 2, wherein S3 comprises generating a first low-rank factor tile `U` and a second low-rank factor tile `V`, and S4 comprises computing `Y = (XU)V`.

**Claim 15.** The method according to claim 2, wherein the neural-network layer is a gated feed-forward block and S4 comprises computing:
`A = phi((XU_up)V_up)`,
`G = psi((XU_gate)V_gate)`, and
`Y = ((A .* G)U_down)V_down`.

**Claim 16.** The method according to claim 2, wherein tokens having similar conditioning signals are grouped and at least part of the generated weight descriptors is reused across the grouped tokens for a bounded time window while remaining non-persistent.

**Claim 17.** The method according to claim 2, wherein the method is executed entirely within one fused Triton, CUDA, ROCm, HIP, or equivalent accelerator kernel.

### Training and Migration Claims

**Claim 19.** The system according to claim 1, further comprising a training pipeline configured to initialize from a pretrained dense model, replace at least one stored dense projection with the meta-generator and fused execution engine, freeze a first subset of original model parameters, and optimize remaining parameters using continual training or knowledge distillation.

**Claim 20.** The system according to claim 19, wherein the training pipeline minimizes a loss comprising at least one of token-level cross-entropy, hidden-state matching, attention-map matching, KL divergence to a teacher model, or bandwidth-aware regularization.

---

## Why This Version Is Stronger

1. The independent claims now recite the memory hierarchy and tile lifecycle as essential features instead of leaving them mostly to dependent claims.
2. The independent claims focus on a concrete technical effect: avoiding external-memory materialization and write-back during inference.
3. Weaker or evidentiary-only language, such as profiler-verification language, has been removed from the core claim set.
4. Broader commercial variants remain available as dependent claims without carrying the entire patentability burden of the application.

---

## Prosecution Notes

1. If prior art is found against runtime parameter generation broadly, further narrow claim 1 around tile-wise generation and release within a single fused kernel.
2. If prior art is found against low-rank generation, maintain claim 1 at the lifecycle level and treat low-rank generation as one embodiment.
3. If examination requires a more hardware-specific posture, promote claim 9 and claim 11 concepts into an amended independent claim.
