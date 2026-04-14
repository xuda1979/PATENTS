# Patent Application Draft

## Title of Invention

Meta-Weight Generation System and Method for On-the-Fly Ephemeral Weights in Memory-Bound Neural Network Inference

**Short Name**: MWG-EW

---

## Technical Field

The present invention relates to accelerator-executed neural-network inference, including transformer inference on GPUs, NPUs, TPUs, and other AI accelerators. More particularly, the invention relates to systems and methods in which weight-descriptor tiles for a linear transformation are generated at runtime from a conditioning signal comprising at least token-dependent information and a layer identifier, stored only in an on-chip local memory region, consumed by associative matrix-product execution, and released without write-back to an external memory region.

---

## Background Art

### 1. Memory-Traffic Bottleneck in Large-Model Inference

Modern large-model inference is frequently constrained by repeated transfer of projection weights from external memory to on-chip compute resources. In transformer architectures, feed-forward-network blocks often contain large up-projection, gate projection, and down-projection matrices whose movement from high-bandwidth memory, off-chip DRAM, or host memory can dominate token latency.

As matrix-compute throughput increases faster than sustainable external-memory bandwidth, matrix-compute units may remain underutilized while waiting for weight data. This imbalance is commonly described as a memory wall.

### 2. Limits of Existing Approaches

Existing techniques do not fully solve this external-memory transport problem:

1. **Quantization** reduces bytes per stored weight but still relies on reading stored weight data from external memory.
2. **Static low-rank compression** stores smaller factors, but the factors remain persistent parameters fetched from external memory.
3. **Mixture-of-Experts** selects among stored experts, but active experts still must be loaded.
4. **Kernel fusion** reduces activation traffic, yet typically assumes that the projection weights already exist as stored operands.
5. **Hypernetworks** may generate parameters, but prior approaches often do not require a tile-wise on-chip generation, consumption, and release lifecycle that prevents external-memory write-back during inference.

Accordingly, a need exists for a technical solution that reduces repeated external-memory movement of projection weights during inference by generating temporary descriptors on demand and consuming them locally on the accelerator.

---

## Summary of the Invention

### 1. Technical Problem

The invention addresses repeated transfer of large projection weights from an external memory region to matrix-compute units during inference of neural-network layers, especially feed-forward-network layers of transformer models.

### 2. Core Technical Solution

In one aspect, the invention provides a neural-network inference system comprising:

1. an accelerator including matrix-compute units, an on-chip local memory region, and an external memory region;
2. a conditioning module configured to obtain, for a current inference step, a conditioning signal comprising at least a token-dependent feature representation and a layer identifier corresponding to a target neural-network layer;
3. a meta-generator configured to generate, from the conditioning signal, weight-descriptor tiles for at least one linear transformation of the target neural-network layer, wherein the weight-descriptor tiles comprise low-rank factors, basis coefficients for reconstruction of low-rank factors, or combinations thereof;
4. a fused execution engine configured to place a generated weight-descriptor tile in the on-chip local memory region, evaluate the linear transformation by an associative matrix-product decomposition including `Y = (XU)V`, accumulate an output tile while the generated weight-descriptor tile remains in the on-chip local memory region, and release or overwrite the generated weight-descriptor tile before generation of a next weight-descriptor tile; and
5. a memory-lifecycle controller configured to prevent write-back of the generated weight-descriptor tiles from the on-chip local memory region to the external memory region during inference.

In preferred embodiments, the fused execution engine completes the linear transformation without storing a full dense weight matrix corresponding to the generated weight descriptors in the external memory region.

### 3. Technical Effects

By shifting selected projections from stored dense weights to generated temporary descriptors, the invention can:

1. reduce external-memory traffic for targeted projections;
2. improve utilization of matrix-compute units that would otherwise stall on weight fetches;
3. reduce model-resident storage requirements for targeted layers;
4. enable hybrid execution in which some layers use generated descriptors and other layers retain stored static weights; and
5. support migration from pretrained dense models by continual training or knowledge distillation.

### 4. Key Inventive Boundary

The invention is not directed merely to low-rank mathematics and not merely to generic parameter generation. The inventive boundary lies in the coordinated hardware-aware lifecycle:

`condition -> generate tile -> store in on-chip local memory -> consume by associative execution -> release without write-back`

This lifecycle converts a weight-fetch problem into a local-compute problem for at least part of the inference path.

---

## Brief Description of Drawings

**Figure 1** illustrates a conventional dense-weight inference path that repeatedly fetches stored projection weights from external memory and a proposed generated-descriptor path that uses a meta-generator and a fused local execution path.

**Figure 2** illustrates an accelerator architecture including a conditioning module, layer identifier input, meta-generator, on-chip local memory region, fused execution engine, memory-lifecycle controller, matrix-compute units, and external memory region.

**Figure 3** illustrates associative execution of a linear transformation using generated factor tiles in a form including `Y = (XU)V`, while preventing storage of a corresponding full dense weight matrix in the external memory region.

**Figure 4** illustrates a tile-wise generation-consume-release loop in which each generated weight-descriptor tile is placed in on-chip local memory, used for multiply-accumulate computation, and released or overwritten before a next tile is generated.

**Figure 5** illustrates migration from a pretrained dense model by layer selection, replacement of one or more stored dense projections with the claimed generation-and-execution path, parameter freezing, and continual training or knowledge distillation.

**Figure 6** illustrates a hybrid scheduler that selectively uses generated weight descriptors or stored static weights according to layer, token, batch, latency target, or available bandwidth.

---

## Detailed Description of the Invention

### 1. Definitions

For purposes of this description:

- **on-chip local memory region** includes registers, shared memory, SRAM, cache, or combinations thereof that are directly usable by an accelerator execution path without first storing generated descriptors in external memory;
- **external memory region** includes high-bandwidth memory, off-chip DRAM, host memory, persistent storage, or combinations thereof;
- **weight-descriptor tile** includes a tile of one or more low-rank factors, a tile of basis coefficients for reconstruction of low-rank factors, or a combination thereof, representing less than a complete stored dense weight matrix; and
- **prevent write-back** means that, during the claimed inference path, generated weight-descriptor tiles are not stored as persistent model weights in the external memory region.

### 2. Accelerator Architecture

In one embodiment, the system comprises:

1. an activation input path for a current inference step;
2. a conditioning module;
3. a layer-identifier input;
4. a meta-generator;
5. an on-chip local memory region;
6. a fused execution engine;
7. a memory-lifecycle controller; and
8. matrix-compute units coupled to an external memory region.

The conditioning module receives at least a token-dependent feature representation and a layer identifier. In optional embodiments, the conditioning module further receives sequence-position information, a routing summary, a domain identifier, a task identifier, a batch statistic, or a hardware-execution profile.

The meta-generator may be shared across a plurality of transformer layers and may use layer embeddings to differentiate generated outputs for different layers.

### 3. Runtime Method

In one embodiment, inference is performed according to the following sequence:

1. receive an activation tensor for a current inference step;
2. form a conditioning signal using at least a token feature representation derived from the activation tensor and a layer identifier;
3. generate, by the meta-generator, weight-descriptor tiles for at least one projection associated with a target neural-network layer;
4. for each generated weight-descriptor tile, store the generated weight-descriptor tile only in the on-chip local memory region and compute a partial output using an associative matrix-product decomposition;
5. accumulate the partial output to produce an output tensor for the projection; and
6. release or overwrite the generated weight-descriptor tile in the on-chip local memory region before generating a next weight-descriptor tile, without storing the generated weight-descriptor tile as a persistent model weight in the external memory region.

This sequence may be carried out by one fused accelerator kernel or by an equivalent tightly coupled execution path that preserves the claimed memory lifecycle.

### 4. Associative Matrix-Product Execution

For a linear transformation represented by a dense matrix `W`, the invention uses an associative decomposition so that a corresponding full dense matrix need not be stored in the external memory region. In a preferred embodiment, generated factor tiles `U` and `V` satisfy:

`W_eff ~= U V`

and the fused execution engine computes:

`Y = (XU)V`

The generated weight-descriptor tiles are consumed while resident in the on-chip local memory region. The fused execution engine accumulates output tiles and releases or overwrites the generated weight-descriptor tiles before generation of a next tile. A full dense weight matrix corresponding to the generated weight descriptors is not stored in the external memory region during inference.

### 5. Feed-Forward-Network Embodiment

In preferred transformer embodiments, the target neural-network layer is a feed-forward-network block. Separate weight-descriptor tiles may be generated for an up-projection, a gate projection, and a down-projection.

For a gated feed-forward block, the fused execution engine may compute:

`A = phi((XU_up)V_up)`

`G = psi((XU_gate)V_gate)`

`Y = ((A .* G)U_down)V_down`

Each descriptor tile for the up-projection, gate projection, and down-projection is generated, stored only in the on-chip local memory region, consumed for computation, and released or overwritten before a next tile is generated.

### 6. Low-Rank and Basis-Bank Embodiments

In one embodiment, the weight-descriptor tiles comprise first and second low-rank factor tiles `U` and `V` having rank `r`, where `r < min(d_in, d_out)` for a target projection of dimensions `d_in x d_out`.

In another embodiment, the meta-generator outputs basis coefficients for reconstruction of low-rank factors. The fused execution engine reconstructs the low-rank factors from the basis coefficients entirely within the on-chip local memory region. The reconstructed factor tiles are then consumed by associative execution and released without write-back to the external memory region.

### 7. Tile-Wise Memory Lifecycle

The fused execution engine preferably operates tile by tile. For each tile:

1. an activation tile is made available to the fused execution engine;
2. the meta-generator produces a corresponding weight-descriptor tile from the conditioning signal;
3. the generated weight-descriptor tile is placed in the on-chip local memory region;
4. matrix-compute units consume the generated weight-descriptor tile to compute a partial output;
5. the partial output is accumulated; and
6. the memory-lifecycle controller releases, overwrites, or zeroizes the generated weight-descriptor tile before generation of a next tile.

This tile-wise lifecycle may be implemented as a persistent accelerator kernel that performs generation, consumption, accumulation, and release within a single kernel launch.

### 8. Adaptive Rank and Hybrid Scheduling

The system may adapt a rank `r` according to token complexity, layer depth, latency target, available bandwidth, or occupancy of the matrix-compute units.

In a hybrid embodiment, a scheduler selectively switches between generated weight descriptors and stored static weights on a per-layer, per-token, or per-batch basis. For example, selected feed-forward-network layers may use generated descriptors while other layers continue to use stored dense weights. Such switching may be based on measured bandwidth pressure, latency budget, or service-level constraints.

### 9. Grouped-Token Reuse

In some embodiments, tokens having similar conditioning signals are grouped and at least part of the generated weight descriptors is reused across the grouped tokens for a bounded time window. Even in such embodiments, the reused descriptors remain non-persistent and are not written back to the external memory region as stored model weights.

### 10. Training and Migration From Pretrained Dense Models

In one embodiment, the system further comprises a training pipeline configured to initialize from a pretrained dense model, replace at least one stored dense projection with the meta-generator and fused execution engine, freeze a first subset of original model parameters, and optimize remaining parameters using continual training or knowledge distillation.

Suitable losses may include one or more of:

1. token-level cross-entropy;
2. hidden-state matching;
3. attention-map matching;
4. KL divergence to a teacher model; and
5. bandwidth-aware regularization.

This migration path provides support for converting pretrained dense checkpoints into implementations that use the claimed local generation and no-write-back execution path.

### 11. Hardware Execution Embodiments

The fused execution engine may be implemented as:

1. a Triton kernel;
2. a CUDA kernel;
3. a ROCm or HIP kernel;
4. an NPU microcode path;
5. a TPU custom call; or
6. another accelerator execution path providing matrix-compute units, on-chip local memory, and control of descriptor lifetime.

In preferred embodiments, the fused execution engine and the meta-generator are sufficiently coupled that generated weight-descriptor tiles are created, consumed, and released within the on-chip local memory region without storage of a full dense weight matrix corresponding to the generated weight descriptors in the external memory region.

### 12. Distinction From Existing Techniques

The invention differs from known approaches as follows:

1. unlike quantization, the invention changes the manner in which projection operands are generated and consumed during inference rather than merely reducing bytes per stored weight;
2. unlike static low-rank compression, the generated descriptors are conditioned on runtime information and are non-persistent;
3. unlike generic hypernetworks, the claimed subject matter recites a hardware memory hierarchy and a generation-consume-release lifecycle that prevents external-memory write-back during inference; and
4. unlike ordinary kernel fusion, the fused execution path extends to creation and lifetime management of generated projection descriptors.

### 13. Representative Embodiments

Representative embodiments include:

1. direct generation of low-rank factor tiles for a transformer feed-forward-network block;
2. basis-bank reconstruction of factor tiles entirely within on-chip local memory;
3. a shared meta-generator used across multiple transformer layers with layer embeddings;
4. a persistent single-kernel implementation with zeroization after use;
5. grouped-token reuse for a bounded non-persistent window; and
6. hybrid scheduling between generated descriptors and stored static weights.

### 14. Example Mathematical Description

Let `x_t in R^(1 x d)` denote a token hidden state and let `e_l` denote a layer representation for layer `l`. A conditioning vector may be formed as:

`c_(t,l) = C(x_t, e_l)`

The meta-generator may output:

`(U_up, V_up, U_gate, V_gate, U_down, V_down) = G_theta(c_(t,l))`

with the generated descriptors represented as tiles during execution. A gated feed-forward-network output may then be computed by:

`A = phi((x_t U_up)V_up)`

`G = psi((x_t U_gate)V_gate)`

`y_t = ((A .* G)U_down)V_down`

where the factor tiles are stored only in the on-chip local memory region during use and are released or overwritten before generation of a next tile.

---

## Drafting Notes for Filing

### 1. Core Language to Preserve

For prosecution consistency, the application should preserve the following concepts in substantially the same form:

1. on-chip local memory region and external memory region;
2. weight-descriptor tiles generated from token-dependent information and a layer identifier;
3. associative execution including `Y = (XU)V`;
4. tile-wise generation, local storage, accumulation, and release; and
5. prevention of write-back during inference.

### 2. Evidence That Strengthens the Technical Effect

Although not required for written-description support, the following evidence would strengthen examination and later enforcement:

1. profiler traces showing absence of descriptor write-back;
2. reduced external-memory traffic relative to a dense baseline;
3. improved matrix-compute utilization on bandwidth-limited hardware; and
4. quality recovery after migration from a pretrained dense model.
