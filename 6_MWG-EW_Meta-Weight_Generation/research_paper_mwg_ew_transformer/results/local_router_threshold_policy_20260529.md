# Local Router Threshold Policy Update

Created: 2026-05-29

Purpose: make the next suite-balanced router run more conservative without
changing legacy token-router behavior.

## Change

Added `--threshold-policy` to `experiments/mwg_token_router_gate_eval.py`.

Policies:

- `global`: existing behavior; threshold is the global train-score quantile.
- `suite_min`: conservative suite-aware behavior; threshold is the strictest
  per-suite train-score quantile.
- `suite_mean`: mean of per-suite train-score quantiles.
- `suite_median`: median of per-suite train-score quantiles.

The global suite-balanced ASI3 launcher now defaults to
`THRESHOLD_POLICY=suite_min`. Existing launchers keep default `global` behavior
unless explicitly overridden.

## Rationale

The leave-suite-out target 0.25 result is average-positive but has a slightly
unstable seed. For the next global suite-aware run, `suite_min` should reduce
over-patching when one suite has a stricter score distribution. This is a
robustness experiment, not a claim improvement until evaluated on ASI3.

## Verification

Commands:

```bash
python3 -m pytest -q tests/test_token_router_threshold_policy.py
python3 -m py_compile experiments/mwg_token_router_gate_eval.py
bash -n scripts/launch_asi3_token_router_global_suite_balanced_detached.sh
```

Result: `3 passed`; compile and shell syntax checks passed.

No ASI3 command, upload, fetch, or browser action was run.
