# Acceptance-Oriented Filing Strategy
# Meta-Weight Generation for On-the-Fly Ephemeral Weights (MWG-EW)

---

## Objective

Increase the likelihood of allowance by presenting MWG-EW as a concrete accelerator-execution invention that solves a memory-traffic problem, rather than as a broad abstract idea of generating neural-network weights.

---

## Core Positioning

The application should repeatedly frame the invention as a technical solution to a technical problem:

- technical problem: repeated external-memory transfer of large projection weights during inference,
- technical means: runtime generation of temporary descriptors, associative evaluation, on-chip-only residency, and no-write-back lifecycle,
- technical effect: lower external-memory traffic and improved utilization of matrix-compute hardware.

This is the safest framing for computer-implemented inventions in most major jurisdictions.

---

## Claim Strategy

### Keep in Independent Claims

1. an accelerator or computing system with on-chip local memory and external memory,
2. a conditioning signal based on token-dependent data and a layer identifier,
3. runtime generation of temporary weight descriptors,
4. associative execution without forming a full dense matrix in external memory,
5. release or overwrite of generated descriptors after use, and
6. prevention of write-back to external memory during inference.

### Keep as Dependent Fallbacks

1. FFN-specific up, gate, and down projections,
2. shared generator across layers,
3. direct low-rank factors,
4. basis-bank reconstruction,
5. persistent single-kernel implementation,
6. adaptive rank,
7. grouped-token reuse,
8. hybrid switching between static and generated weights,
9. migration from pretrained dense checkpoints.

### Avoid Making Central

1. profiler-verification language,
2. deployment-environment labels by themselves,
3. very broad language such as "equivalent latent factors" without technical context,
4. purely commercial benefits,
5. claims that rely only on mathematical equivalence without memory-lifecycle limitations.

---

## Specification Priorities

To support examination and later amendment flexibility, the specification should clearly disclose:

1. the memory hierarchy and where descriptors are permitted to reside,
2. a tile-wise generation-consume-release loop,
3. at least one implementation path using a fused accelerator kernel,
4. at least one embodiment using direct factor generation,
5. at least one embodiment using basis coefficients,
6. fallback embodiments using partial layer replacement and hybrid static-dynamic execution,
7. explicit distinction from static low-rank storage, generic hypernetworks, and ordinary kernel fusion.

---

## Evidence Priorities

The strongest examination support package would include:

1. profiler evidence showing no descriptor write-back to external memory,
2. HBM or external-memory traffic comparison against a dense baseline,
3. numerical agreement between reference and fused execution paths,
4. quality-recovery evidence after continual training or distillation,
5. throughput or latency data on bandwidth-limited hardware.

Without this evidence, the application can still be filed, but prosecution flexibility is weaker because the technical effect becomes more theoretical.

---

## Likely Objections and Responses

### Objection 1: The claims are directed to an abstract algorithm or mathematical method

Response direction:

- point to the recited accelerator memory hierarchy,
- point to on-chip local-memory residency and no-write-back lifecycle,
- point to reduced external-memory traffic as the technical effect.

### Objection 2: Hypernetworks already generate weights

Response direction:

- distinguish generic parameter generation from tile-wise local generation plus immediate consumption and release,
- emphasize that the claims are directed to inference-time memory-traffic reduction on accelerator hardware.

### Objection 3: Low-rank factorization is known

Response direction:

- clarify that static low-rank storage is not the point of novelty,
- emphasize runtime-conditioned generation and non-persistent lifecycle.

### Objection 4: Kernel fusion is known

Response direction:

- distinguish fusion of activations from fusion that extends upstream to weight creation itself,
- emphasize that generated descriptors are transient hardware-resident objects, not stored model parameters.

---

## Immediate Next Steps

1. Use `claims_EN_v2.md` as the new prosecution baseline.
2. Align the description and drawings with the narrower claim language so the support is explicit.
3. Remove reliance on claim concepts that are really proof artifacts rather than invention features.
4. Run a formal prior-art search focused on hypernetworks, generated-parameter inference, and on-chip generated-weight execution.
5. Prepare at least one concrete implementation example before filing if timing allows.

---

## Final Note

No claim set can guarantee allowance. The practical goal is to make the first office action argue about technical distinctions and prior art, not about abstraction or lack of technical character. This redraft is aimed at that outcome.
