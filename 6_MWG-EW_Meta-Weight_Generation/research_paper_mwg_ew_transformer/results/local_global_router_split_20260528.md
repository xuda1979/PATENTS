# Global Router Split Prep

Created: 2026-05-28

Purpose: create one combined suite-aware router split that is safe for
suite-balanced routing experiments. The previous
`data/heldout/router_broad_splits/manifest.json` remains useful for per-suite
runs, but is not safe as one combined manifest because every router-train row
overlaps the broad eval union.

## New Helper

`experiments/create_global_router_split_manifest.py`

Command:

```bash
python3 experiments/create_global_router_split_manifest.py \
  --source-manifest data/heldout/manifest.json \
  --out-dir data/heldout/router_global_splits \
  --seed 17 \
  --eval-fraction 0.5
```

## Output

Manifest:

`data/heldout/router_global_splits/manifest.json`

Audit:

- `results/router_global_split_audit_20260528.json`
- `results/router_global_split_audit_20260528.md`

## Audit Summary

| Suite | Train | Eval | Train/eval overlap |
| --- | ---: | ---: | ---: |
| gsm8k_test | 130 | 130 | 0 |
| mbpp_test | 97 | 97 | 0 |
| alpaca_cleaned_train_tail | 130 | 130 | 0 |

Global totals:

- train rows: 357
- train unique rows: 357
- eval rows: 357
- eval unique rows: 357
- train/eval overlap unique rows: 0
- clean train rows after eval-union removal: 357

## Claim Boundary

This split is ready for one combined router train/eval run with
`--suite-split-manifest`, `--suite-balanced-sampling`,
`--suite-balanced-ridge`, and `--fail-on-suite-overlap`.

It is not new independent broad-family evidence. It repartitions the current
math/code/instruction held-out files so target-0.25 routing can be tested under
a cleaner suite-aware protocol before spending ASI3 time.
