# Training-Lifecycle (Multi-Layer) Measurement

**Run ID:** asi3_training_lifecycle_multilayer_20260913
**Date:** 2026-09-13
**Device:** Ascend 910B2 (single-NPU single-process; ASI2 environment)
**Software:** torch 2.9.0, torch_npu 2.9.0

## What this adds

Extends the single-FFN training-lifecycle result
(`results/asi3_training_lifecycle_20260909/`) to a **stack of N FFN layers**,
substantiating that the saved-for-backward activation footprint—the quantity
that scales with depth, batch, and sequence—is reduced by recompute-in-backward
at every depth, while gradient equality remains exact.

Because the generated diagonal core is token-local (a deterministic function of
the pre-FFN input), backward can recompute it from a replayed input instead of
materializing and saving its intermediate activations. We measure the
saved-for-backward activation footprint (the deterministic sum of tensors
autograd must retain for backward, in fp32 bytes) and verify on-device gradient
equality (max abs diff) between:

- **Materialize-and-save:** standard autograd saves each FFN layer's input and
  pre-activation intermediate for backward.
- **Recompute-in-backward:** gradient checkpointing re-executes each FFN layer
  from its saved input during backward.

## Results (single seed 2026; footprint is geometry-determined)

| d    | m     | N  | materialize (MiB) | recompute (MiB) | footprint reduction | grad maxdiff |
|------|-------|----|--------------------|------------------|---------------------|--------------|
| 1536 | 8960  | 1  | 5.12               | 0.75             | 6.83x               | 0.0          |
| 1536 | 8960  | 4  | 20.50              | 3.00             | 6.83x               | 0.0          |
| 1536 | 8960  | 8  | 41.00              | 6.00             | 6.83x               | 0.0          |
| 1536 | 8960  | 16 | 82.00              | 12.00            | 6.83x               | 0.0          |
| 2048 | 11008 | 1  | 6.38               | 1.00             | 6.38x               | 0.0          |
| 2048 | 11008 | 4  | 25.50              | 4.00             | 6.38x               | 0.0          |
| 2048 | 11008 | 8  | 51.00              | 8.00             | 6.38x               | 0.0          |
| 2048 | 11008 | 16 | 102.00             | 16.00            | 6.38x               | 0.0          |

All B=2, S=64 (Nin=128), fp32, single fixed seed (2026). The eight
(geometry, depth) configurations converge to the same geometry-determined
footprint; **gradient max-abs diff =
0.0 in all 8 configurations** (exact equality, so recompute does not perturb training
dynamics). Unlike the single-FFN run (asi3_training_lifecycle_20260909,
seeds 2026/2027/2028 per config), this multi-layer run used one seed; the
seed-invariance of the footprint (geometry-determined) is inherited from the
3-seed single-layer result, but gradient equality here is verified at one
seed only.

## Interpretation (honest)

- The **per-layer** footprint reduction is the geometric constant
  `(d+m)/d` (6.83x at d=1536/m=8960, 6.38x at d=2048/m=11008) and is
  **independent of depth**, so the recompute advantage does not shrink as the
  model gets deeper.
- Because the materialize-and-save footprint **grows linearly with depth N**
  (5.12 -> 82.00 MiB at d=1536), while recompute stays at `N*d` (0.75 -> 12.00
  MiB), the **absolute bytes saved increase with depth**: at N=16 a stack saves
  ~70-86 MiB of saved-for-backward activation per pass.
- This is a **single-process, multi-layer FFN** measurement (matching the
  paper's single-layer scope extended across layers). Full-model end-to-end
  prefill/decode throughput, a synchronized optimizer step, and distributed
  (DDP) activation-capacity accounting remain open and are not claimed.

## Reproduce

Script: `measure_training_lifecycle_multilayer.py` (this directory).
Run on the NPU host (ASI2/ASI3, torch_npu):

```bash
python3 measure_training_lifecycle_multilayer.py
```

Writes `training_lifecycle_multilayer_measured.json`.
