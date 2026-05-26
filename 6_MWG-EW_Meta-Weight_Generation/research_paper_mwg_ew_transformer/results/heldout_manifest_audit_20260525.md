# Held-Out Manifest Coverage Audit

Manifest: `data/heldout/manifest.json`
Provenance: `data/heldout/provenance.json`

## Sources

| Label | Manifest | Suites | Failures |
| --- | --- | ---: | ---: |
| main | `data/heldout/manifest.json` | 3 | 1 |

## Family Coverage

| Family | Suites | Lines | Characters |
| --- | --- | ---: | ---: |
| code_generation | main:mbpp_test | 194 | 29,746 |
| instruction_following | main:alpaca_cleaned_train_tail | 260 | 185,863 |
| math_reasoning | main:gsm8k_test | 260 | 139,393 |

Missing recommended families: general_language_modeling, commonsense_reasoning, multi_turn_dialogue, long_context

## Dataset Failures

- `main:wikitext103_validation` from `Salesforce/wikitext`: ConnectionError("Couldn't reach 'Salesforce/wikitext' on the Hub (LocalEntryNotFoundError)")

## Claim Boundary

Ready for broad-family claim: `false`

Current manifest is useful for broad stress testing, but top-journal broad-family claims need the missing recommended families and resolved dataset failures.
