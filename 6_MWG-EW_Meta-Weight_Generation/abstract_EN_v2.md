# Patent Abstract

## Meta-Weight Generation for On-the-Fly Ephemeral Weights (MWG-EW)

---

### Abstract

A neural-network inference system and method reduce external-memory traffic during inference of transformer and other neural-network layers. An accelerator includes matrix-compute units, an on-chip local memory region, and an external memory region. A conditioning module forms a conditioning signal from at least a token-dependent feature representation and a layer identifier. A meta-generator generates weight-descriptor tiles comprising low-rank factors, basis coefficients for reconstruction of low-rank factors, or combinations thereof. A fused execution engine places each generated weight-descriptor tile in the on-chip local memory region, evaluates a linear transformation by an associative decomposition including `Y = (XU)V`, accumulates an output tile, and releases or overwrites the generated weight-descriptor tile before generation of a next tile. A full dense weight matrix corresponding to the generated weight descriptors is not stored in the external memory region during inference.

**(Approx. word count: 130)**

---

### Keywords

Neural-network inference; transformer feed-forward network; external-memory traffic reduction; weight-descriptor tiles; on-chip local memory; associative matrix multiplication; no-write-back execution; fused accelerator kernel; low-rank factors; basis coefficients

---

### Brief Description of Drawings

**Figure 1**: Comparison between conventional dense-weight inference and proposed generated-descriptor inference

**Figure 2**: Accelerator architecture including conditioning module, meta-generator, on-chip local memory, fused execution engine, memory-lifecycle controller, and external memory

**Figure 3**: Associative execution of generated factor tiles in a form including `Y = (XU)V` without storage of a corresponding full dense matrix in external memory

**Figure 4**: Tile-wise generation, local storage, consumption, accumulation, and release of descriptor tiles

**Figure 5**: Migration from a pretrained dense model to a generated-descriptor execution path

**Figure 6**: Hybrid scheduler for selecting generated descriptors or stored static weights

---

### Tentative IPC / CPC Directions

- G06N 3/0455 - Architectures of neural networks
- G06N 3/08 - Learning methods for neural networks
- G06F 15/78 - Digital computing using specific architectures
- G06F 9/3001 - Resource allocation or scheduling for computer architectures

---

### Technical Effects Summary

| Technical Metric | Conventional Dense Execution | MWG-EW v2 |
|------------------|------------------------------|-----------|
| Projection operand source | Stored weights in external memory | Generated descriptor tiles |
| Residency of generated descriptors | Not applicable | On-chip local memory only during use |
| Full dense matrix storage during inference | Required or assumed | Avoided for generated path |
| External-memory write-back of generated descriptors | Not applicable | Prevented |
| Execution style | Weight-fetch dominated | Tile-wise generate-consume-release |
| Hardware fit | Bandwidth-limited under dense inference | Better aligned to accelerator compute resources |
