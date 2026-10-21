# Local Suite-Balanced Router Hygiene

Created: 2026-05-29

Purpose: record local validation for the daemon-safe global suite-balanced
router path before any ASI3 launch.

## Checks

Python compile check passed for:

- `experiments/mwg_token_router_gate_eval.py`
- `experiments/create_global_router_split_manifest.py`
- `experiments/audit_router_split_manifest.py`

Shell syntax checks passed individually with `bash -n` for:

- `scripts/launch_asi3_token_router_global_suite_balanced_detached.sh`
- `scripts/launch_asi3_token_router_global_suite_balanced_when_ready.sh`
- `scripts/fetch_asi3_persistent_lmce_artifacts_when_ready.sh`

Global split manifest sanity:

| Suite | Train file rows | Eval file rows |
| --- | ---: | ---: |
| gsm8k_test | 130 | 130 |
| mbpp_test | 97 | 97 |
| alpaca_cleaned_train_tail | 130 | 130 |

All six referenced train/eval files exist locally under
`data/heldout/router_global_splits`.

## Boundary

No ASI3 command, upload, fetch, or browser action was run for this check. This
only validates the local launch path and input manifest hygiene.
