# Local Token Router Robustness Prep

Created: 2026-05-27

`mwg_token_router_gate_eval.py` now supports suite-aware router data loading and
training prep. This is intended for distribution-robust follow-up runs at the
fragile `0.25` target, where the current ASI3 evidence is average-positive but
slightly unstable under leave-suite-out validation.

New options:

```bash
python3 experiments/mwg_token_router_gate_eval.py \
  --suite-split-manifest path/to/global_leakage_clean_router_manifest.json \
  --suite-balanced-sampling \
  --suite-balanced-ridge \
  --require-texts \
  ...
```

Behavior:

- `--suite-split-manifest` loads suite-labeled train/eval text files from an
  explicit split manifest, preserving the no-`DEFAULT_TEXTS` guard.
- `--suite-balanced-sampling` samples examples round-robin across suites, so
  small or budgeted runs do not accidentally train on one suite only.
- `--suite-balanced-ridge` weights token rows so each suite contributes equal
  total ridge weight even when token counts differ.
- The script removes train rows that overlap the union of eval rows before
  sampling. If that leaves no train rows, it refuses the run instead of falling
  back to unsafe data.
- `--fail-on-suite-overlap` can turn any detected train/eval overlap into an
  immediate hard failure.
- Collection summaries now include per-suite dense loss, patched loss, patched
  PPL ratio, tokens, examples, and positive-delta fraction.

## Split Audit Finding

`router_broad_splits/manifest.json` is safe for per-suite evaluation, but it is
not safe as one combined suite-aware router manifest. A static audit found:

- Train rows across suite files: 1,024 total, 512 unique.
- Eval rows across suite files: 714 total, 714 unique.
- Unique train/eval overlap across the combined eval union: 512.
- Clean train rows after removing the eval union: 0.

Each suite had zero overlap with its own eval file, so the manifest remains
valid for per-suite runs. It should not be passed as a single combined
`--suite-split-manifest`; use per-suite runs or prepare a global leakage-clean
split first.

Local static checks:

- `python3 -m py_compile experiments/mwg_token_router_gate_eval.py`
- Manifest helper loaded 1,024 training rows from
  `data/heldout/router_broad_splits/manifest.json`.
- Plain random sampling of 12 rows with seed 7 selected only `gsm8k_test`.
- Suite-balanced sampling of 12 rows selected 4 each from
  `alpaca_cleaned_train_tail`, `gsm8k_test`, and `mbpp_test`.
- Weighted ridge helper produced the expected weighted diagnostics without
  loading a model.
- `audit_router_split_manifest.py` correctly marked
  `router_broad_splits/manifest.json` as not ready for one combined router run.

This is not new router-quality evidence yet. It prepares a safer ASI3/local
launch path for testing whether suite-balanced training can improve the `0.25`
target without worsening leave-suite-out instability.
