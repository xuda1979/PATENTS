# ASI3 Next Daemon-Safe Actions

Created: 2026-05-29

Purpose: record the exact script-only actions to take when the `ASI3` daemon is
healthy, without using browser fallback or relaunching completed baselines.

## Guardrails

- Keep `ASI3_ALLOW_BROWSER=0`.
- Keep `HUANXIN_ALLOW_STANDALONE_FALLBACK=0`.
- Do not run anything if `scripts/ASI3_shell.sh` refuses due to busy, pending,
  or incomplete daemon state.
- Do not relaunch `asi3_persistent_lmce_baseline_20260526T024239Z`.
- Preserve explicit manifests, explicit text paths, and `--require-texts`.

## Latest Local Daemon Health Observation

2026-05-29 heartbeat: a read-only health probe eventually returned
`ready=true`, `busy=false`, and `pendingRequestCount=0`, but
`lastCommandStartedAt=2026-05-27T16:35:32.298Z` was later than
`lastCommandCompletedAt=2026-05-26T09:56:54.515Z`. Treat this as an incomplete
previous command state. The guarded wrappers should not be run until this state
clears or a deliberate manual recovery is performed.

## Fetch Remaining Persistent LM-CE Artifact

Preferred command from repo root:

```bash
bash research_paper_mwg_ew_transformer/scripts/fetch_asi3_persistent_lmce_artifacts_when_ready.sh
```

This wrapper fetches and SHA-verifies:

- `logs/asi3_broad_validation_20260526T024509Z.status.json`
- `results/asi3_broad_validation_20260526T024509Z/summary_broad_eval.json`
- `results/asi3_persistent_lmce_baseline_20260526T024239Z/persistent_low_rank_r384_lmce.json`

Local check before this note: broad status and broad summary are already
present locally; the persistent calibration JSON is still missing locally.

## Launch Global Suite-Balanced Router Robustness Run

Preferred command from repo root, only after the daemon is clean:

```bash
bash research_paper_mwg_ew_transformer/scripts/launch_asi3_token_router_global_suite_balanced_when_ready.sh
```

This wrapper uploads the detached launcher, current token-router evaluator, the
global split manifest, and all six split text files before launching:

- `data/heldout/router_global_splits/manifest.json`
- `data/heldout/router_global_splits/gsm8k_test/router_train.txt`
- `data/heldout/router_global_splits/gsm8k_test/router_eval.txt`
- `data/heldout/router_global_splits/mbpp_test/router_train.txt`
- `data/heldout/router_global_splits/mbpp_test/router_eval.txt`
- `data/heldout/router_global_splits/alpaca_cleaned_train_tail/router_train.txt`
- `data/heldout/router_global_splits/alpaca_cleaned_train_tail/router_eval.txt`

The detached run uses:

- `--suite-split-manifest`
- `--suite-balanced-sampling`
- `--suite-balanced-ridge`
- `--fail-on-suite-overlap`
- `--require-texts`

Local split audit before this note:

| Suite | Train rows | Eval rows | Train/eval overlap |
| --- | ---: | ---: | ---: |
| gsm8k_test | 130 | 130 | 0 |
| mbpp_test | 97 | 97 | 0 |
| alpaca_cleaned_train_tail | 130 | 130 | 0 |

Global totals: 357 train rows, 357 eval rows, 357 unique train rows, 357 unique
eval rows, and zero train/eval overlap.

## Current Interpretation

These actions do not make the work top-journal ready by themselves. The
persistent LM-CE baseline remains broad-negative. The global suite-balanced
router run is a cleaner robustness check for bounded selective routing,
especially target 0.25, not independent broad-family evidence.
