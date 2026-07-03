# Local Selective Residual Probe

Created: 2026-05-26

This local CPU probe tests the proposed algorithmic pivot from broad FFN
replacement to budgeted selective residual patching. The experiment uses a
synthetic dense gated-FFN teacher with `d=128`, `m=384`, rank-32 low-rank base,
rank-16 residual, three seeds, 120 base steps, 240 residual steps, and 160
router-supervision steps.

Source results:

- `/tmp/mwg_selective_residual_probe_main/mwg_selective_residual_probe_20260526T152753Z.json`
- `/tmp/mwg_selective_residual_probe_main/mwg_selective_residual_probe_20260526T152827Z.json`
- `/tmp/mwg_selective_residual_probe_main/mwg_selective_residual_probe_20260526T152830Z.json`

## Three-Seed Aggregate

| Method | Actual budget | Mean rel. MSE | Mean improvement vs base | Min improvement | Max improvement | Mean cosine |
|---|---:|---:|---:|---:|---:|---:|
| persistent_low_rank | 0.0000 | 0.888040 | 0.000% | 0.000% | 0.000% | 0.334711 |
| always_residual | 1.0000 | 0.871360 | 1.879% | 1.793% | 1.945% | 0.359575 |
| oracle_residual_b0.05 | 0.0508 | 0.882788 | 0.592% | 0.578% | 0.606% | 0.342740 |
| supervised_router_b0.05 | 0.0508 | 0.885133 | 0.327% | 0.318% | 0.335% | 0.339147 |
| selective_residual_b0.05 | 0.0508 | 0.887888 | 0.017% | 0.014% | 0.021% | 0.334938 |
| oracle_residual_b0.10 | 0.1016 | 0.879918 | 0.915% | 0.889% | 0.936% | 0.347086 |
| supervised_router_b0.10 | 0.1016 | 0.883102 | 0.556% | 0.529% | 0.601% | 0.342217 |
| selective_residual_b0.10 | 0.1016 | 0.887735 | 0.034% | 0.029% | 0.038% | 0.335164 |
| oracle_residual_b0.25 | 0.2500 | 0.875013 | 1.467% | 1.425% | 1.507% | 0.354419 |
| supervised_router_b0.25 | 0.2500 | 0.878457 | 1.079% | 1.034% | 1.127% | 0.349190 |
| selective_residual_b0.25 | 0.2500 | 0.886645 | 0.157% | 0.101% | 0.220% | 0.336808 |
| oracle_residual_b0.50 | 0.5000 | 0.871639 | 1.847% | 1.780% | 1.905% | 0.359354 |
| supervised_router_b0.50 | 0.5000 | 0.873898 | 1.593% | 1.533% | 1.639% | 0.355937 |
| selective_residual_b0.50 | 0.5000 | 0.875320 | 1.433% | 1.347% | 1.504% | 0.353679 |

## Interpretation

The residual path has useful capacity: always-on residual improves mean relative
MSE by 1.879% over the persistent low-rank base. Oracle sparse routing shows a
budget-quality frontier: 5% tokens recover 0.592%, 10% recover 0.915%, 25%
recover 1.467%, and 50% recover 1.847%.

The unsupervised budgeted router is weak at low budgets, which is important
negative evidence. It only improves 0.017% at 5%, 0.034% at 10%, and 0.157% at
25%. A supervised router trained against oracle benefit labels is much better:
0.327% at 5%, 0.556% at 10%, 1.079% at 25%, and 1.593% at 50%.

This supports the algorithmic pivot: MWG-EW should be framed and developed as a
budgeted selective residual method with router supervision from per-token
benefit/error estimates, not as broad FFN replacement.

Next test: move the residual from the FFN output to the internal gate/up/down
hidden path, then train the router from dense-vs-residual token benefit labels
on held-out LM activations.
