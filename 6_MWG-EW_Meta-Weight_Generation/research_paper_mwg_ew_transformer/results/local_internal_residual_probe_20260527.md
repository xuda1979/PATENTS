# Local Internal Residual Probe

Created: 2026-05-27

This local CPU probe compares two ways to use MWG as a budgeted selective
residual:

- `output_*`: add a small generated residual only to the FFN output.
- `internal_*`: add generated residuals inside the FFN path, to the gate/up
  projections and the hidden-to-output path.

Both variants use a synthetic dense gated-FFN teacher with `d=128`, `m=384`,
rank-32 low-rank base, rank-16 residual, three seeds, 120 base steps, 240
residual steps, and 160 router-supervision steps.

Source results:

- `/tmp/mwg_selective_internal_compare/mwg_selective_residual_probe_20260526T161934Z.json`
- `/tmp/mwg_selective_internal_compare/mwg_selective_residual_probe_20260526T161940Z.json`
- `/tmp/mwg_selective_internal_compare/mwg_selective_residual_probe_20260526T161947Z.json`

## Three-Seed Aggregate

| Method | Actual budget | Mean rel. MSE | Mean improvement vs base | Min improvement | Max improvement | Mean cosine |
|---|---:|---:|---:|---:|---:|---:|
| persistent_low_rank | 0.0000 | 0.888040 | 0.000% | 0.000% | 0.000% | 0.334711 |
| output_always_residual | 1.0000 | 0.871360 | 1.879% | 1.793% | 1.945% | 0.359575 |
| internal_always_residual | 1.0000 | 0.866505 | 2.425% | 2.370% | 2.473% | 0.366578 |
| output_oracle_residual_b0.05 | 0.0508 | 0.882788 | 0.592% | 0.578% | 0.606% | 0.342740 |
| internal_oracle_residual_b0.05 | 0.0508 | 0.881087 | 0.783% | 0.764% | 0.803% | 0.345229 |
| output_supervised_router_b0.05 | 0.0508 | 0.885133 | 0.327% | 0.318% | 0.335% | 0.339147 |
| internal_supervised_router_b0.05 | 0.0508 | 0.884375 | 0.413% | 0.408% | 0.417% | 0.340254 |
| output_oracle_residual_b0.10 | 0.1016 | 0.879918 | 0.915% | 0.889% | 0.936% | 0.347086 |
| internal_oracle_residual_b0.10 | 0.1016 | 0.877388 | 1.200% | 1.172% | 1.223% | 0.350753 |
| output_supervised_router_b0.10 | 0.1016 | 0.883102 | 0.556% | 0.529% | 0.601% | 0.342217 |
| internal_supervised_router_b0.10 | 0.1016 | 0.881553 | 0.731% | 0.686% | 0.767% | 0.344486 |
| output_oracle_residual_b0.25 | 0.2500 | 0.875013 | 1.467% | 1.425% | 1.507% | 0.354419 |
| internal_oracle_residual_b0.25 | 0.2500 | 0.871375 | 1.877% | 1.832% | 1.908% | 0.359609 |
| output_supervised_router_b0.25 | 0.2500 | 0.878457 | 1.079% | 1.034% | 1.127% | 0.349190 |
| internal_supervised_router_b0.25 | 0.2500 | 0.875261 | 1.439% | 1.410% | 1.465% | 0.353820 |
| output_oracle_residual_b0.50 | 0.5000 | 0.871639 | 1.847% | 1.780% | 1.905% | 0.359354 |
| internal_oracle_residual_b0.50 | 0.5000 | 0.867500 | 2.313% | 2.254% | 2.362% | 0.365223 |
| output_supervised_router_b0.50 | 0.5000 | 0.873898 | 1.593% | 1.533% | 1.639% | 0.355937 |
| internal_supervised_router_b0.50 | 0.5000 | 0.869308 | 2.110% | 2.075% | 2.147% | 0.362522 |

## Interpretation

Internal FFN-path residuals are consistently better than output-only residuals.
The internal variant improves the always-on residual from 1.879% to 2.425%.
At 25% supervised routing budget, it improves from 1.079% to 1.439%. At 50%
budget, it improves from 1.593% to 2.110%.

This supports a sharper MWG usage rule: generated descriptors should patch the
large projection path itself, not merely add a post-hoc output correction.
That is closer to the original idea of replacing or modulating large matrices,
while the token budget and benefit-supervised router prevent blind use.

Next local tests:

1. Add the analogous selective internal residual for attention `K` and `V`
   projections.
2. Compare FFN-internal, K/V-internal, and combined FFN+K/V budgets under the
   same token-routing policy.
3. Replace synthetic activations with held-out LM activations before launching
   ASI3-scale validation.
