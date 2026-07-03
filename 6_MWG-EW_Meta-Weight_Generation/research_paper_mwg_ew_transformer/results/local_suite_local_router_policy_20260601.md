# Local Suite-Local Router Policy

Created: 2026-06-01

Purpose: prepare a stricter ASI3 router robustness experiment without using
browser automation or launching into a degraded ASI3 shell endpoint.

## ASI3 Control-Plane State

The exact ASI3 daemon health endpoint is reachable at port 20653, but reports
`ready=false` with `startupFailureKind=shell_endpoint_unavailable`.
The shell API failure is `getShellVisitUrl code=170022`, with frontend fallback
to `wss://aihuanxin.cn/kunlun/null`. No ASI3 shell, upload, fetch, or browser
action was run.

## Change

`experiments/mwg_token_router_gate_eval.py` now supports
`--threshold-policy suite_local`.

This policy keeps per-suite train-score quantile thresholds and applies the
matching suite threshold at evaluation time. It differs from:

- `global`: one global quantile over all train tokens;
- `suite_min`: the strictest suite threshold, usually under-patching easier
  suites;
- `suite_mean` and `suite_median`: one aggregate suite-aware threshold.

## Rationale

The current broad-router evidence supports target `0.05` and `0.10`, while
target `0.25` is average-positive but slightly unstable under leave-suite-out
validation. `suite_local` is an ASI3-ready robustness variant for the next
global suite-balanced run: it avoids one suite's score scale dominating the
threshold used for all suites, while preserving the requested patch budget
within each suite.

This is not new benchmark evidence. It is a safer launch candidate for ASI3.

## Verification

Commands:

```bash
python3 -m pytest -q tests/test_token_router_threshold_policy.py
python3 -m py_compile experiments/mwg_token_router_gate_eval.py
bash -n scripts/launch_asi3_token_router_global_suite_balanced_detached.sh \
  scripts/launch_asi3_token_router_global_suite_balanced_when_ready.sh \
  scripts/fetch_asi3_persistent_lmce_artifacts_when_ready.sh
```

Result: `4 passed`; Python compilation and shell syntax checks passed.

## Next ASI3 Command When Shell Endpoint Recovers

Use the existing daemon-only launcher with:

```bash
THRESHOLD_POLICY=suite_local \
  bash scripts/launch_asi3_token_router_global_suite_balanced_when_ready.sh
```

Keep `ASI3_ALLOW_BROWSER=0` and `HUANXIN_ALLOW_STANDALONE_FALLBACK=0`.
