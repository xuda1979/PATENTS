# Training-Lifecycle Measurement: Materialize-and-Save vs. Recompute-in-Backward

**Run ID:** asi3_training_lifecycle_20260909
**Date:** 2026-09-09
**Device:** Ascend 910B2 (8 available; single-NPU single-process trials)
**Software:** torch 2.9.0, torch_npu 2.9.0

## What this measures

The paper's required-validation item (5) — training lifecycle: either save-core or
deterministic backward rematerialization. This measurement closes that item with a
real, multi-setting, multi-seed NPU experiment.

Because the generated diagonal core is **token-local** (a deterministic function of
the pre-FFN input), backward can recompute it from a replayed input instead of
materializing and saving its intermediate activations. We measure, for a
`token_diag_core`-style diagonal-core FFN, the **saved-for-backward activation
footprint** and **peak allocator memory** under two lifecycles:

- **Materialize-and-save:** standard autograd saves the generated-core and FFN
  intermediates for backward.
- **Recompute-in-backward:** gradient checkpointing re-executes the FFN from the
  saved pre-FFN input during backward (deterministic rematerialization).

We verify **gradient equality** between the two lifecycles (max abs difference),
so the memory saving does not change training dynamics.

## Predeclared schema

`{d, m, r, B, S, seed}` -> `{saved_activ_bytes:{materialize,recompute},
peak_alloc_bytes:{materialize,recompute}, grad_maxdiff}`

## Configs (all Qwen2.5-1.5B-with-8B/11k FFN-geometry layer FFN matrix shapes)

| d | m | r | B | S | materialized saved (MiB) | recompute saved (MiB) | **saved-footprint reduction** | grad maxdiff |
|---|---|---|---|---|---|---|---|---|
| 1536 | 8960 | 384 | 2 | 64 | 86.04 | 1.50 | **57.4x** | 0.0 |
| 1536 | 8960 | 384 | 4 | 128 | 146.98 | 6.00 | **24.5x** | 0.0 |
| 1536 | 8960 | 512 | 2 | 64 | 107.76 | 1.50 | **71.8x** | 0.0 |
| 2048 | 11008 | 384 | 2 | 64 | 107.70 | 2.00 | **53.9x** | 0.0 |

Seeds 2026/2027/2028 per config; all three seeds match exactly (geometry-determined),
and **gradient max-abs difference = 0.0 in all 12 trials**.

## How to reproduce

Script: `scripts/measure_training_lifecycle.py` (in the research workspace).
Run on the NPU host:

```bash
python3 scripts/measure_training_lifecycle.py
```

Writes `results/asi3_training_lifecycle_20260909/training_lifecycle_measured.json`.

## Honest interpretation

- The **saved-for-backward activation footprint** (the quantity that scales with
  depth, batch, and sequence and drives optimizer/activation capacity) drops
  24.5x-71.8x under recompute-in-backward.
- The **peak allocator** is comparable at these single-FFN, small-batch shapes
  (recompute holds both the saved input and transient recompute tensors at once);
  the recompute path trades a small recompute-FLOP overhead for the large saved
  footprint reduction Dru IDA.
- This is a single-layer FFN measurement, matching the paper's single-layer
  scoped evidence; full-model peak-memory and end-to-end benefit remain open.
