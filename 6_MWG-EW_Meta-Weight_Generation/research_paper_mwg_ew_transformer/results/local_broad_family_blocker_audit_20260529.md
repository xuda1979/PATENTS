# Local Broad-Family Blocker Audit

Created: 2026-05-29

Purpose: refresh the local held-out family audit after the ASI3 daemon-safe
router prep work, without contacting ASI3 or using browser automation.

## Commands

```bash
python3 -m py_compile \
  experiments/prepare_extra_heldout_families.py \
  experiments/audit_heldout_manifest.py

python3 experiments/audit_heldout_manifest.py \
  --include-extra \
  --out-json results/heldout_manifest_audit_with_extra_20260529.json \
  --out-md results/heldout_manifest_audit_with_extra_20260529.md
```

## Result

The combined audit still has only three main suites and zero extra suites:

| Family | Suite |
| --- | --- |
| math_reasoning | main:gsm8k_test |
| code_generation | main:mbpp_test |
| instruction_following | main:alpaca_cleaned_train_tail |

Missing recommended families:

- general_language_modeling
- commonsense_reasoning
- multi_turn_dialogue
- long_context

Recorded dataset-access failures: 5 total:

- main Wikitext103
- extra Wikitext103
- extra HellaSwag
- extra DailyDialog
- extra Qasper

`ready_for_broad_family_claim=false` remains the correct boundary.

## Boundary

This is blocker documentation, not new benchmark evidence. No ASI3 command,
upload, fetch, or browser action was run.
