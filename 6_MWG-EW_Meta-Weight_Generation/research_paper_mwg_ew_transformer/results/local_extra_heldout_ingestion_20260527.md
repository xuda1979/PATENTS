# Local Extra Held-Out Ingestion Update

Created: 2026-05-27

`prepare_extra_heldout_families.py` now supports more practical offline/local
sources for the missing benchmark families. Existing usage still works:

```bash
python3 experiments/prepare_extra_heldout_families.py \
  --skip-hf \
  --local-text name=family=/path/to/text.txt
```

New local source support:

- Plain text can be split by line, or by blank-line paragraph blocks with
  `--local-paragraphs`.
- JSONL and JSON files can be ingested directly.
- Structured files can select explicit fields with
  `name=family=/path/to/data.jsonl:field1,field2`.
- Provenance records `source_path`, selected `fields`, and whether paragraph
  splitting was used.

Smoke test:

```bash
python3 experiments/prepare_extra_heldout_families.py \
  --skip-hf \
  --allow-partial \
  --outdir /tmp/mwg_extra_heldout_smoke/out \
  --min-item-chars 40 \
  --min-suite-texts 2 \
  --min-suite-chars 120 \
  --local-paragraphs \
  --local-text smoke_general=general_language_modeling=/tmp/mwg_extra_heldout_smoke/src/general.jsonl:text \
  --local-text smoke_commonsense=commonsense_reasoning=/tmp/mwg_extra_heldout_smoke/src/commonsense.txt
```

The smoke prepared two extra suites and the audit helper saw them as
`general_language_modeling` and `commonsense_reasoning`. The audit still
correctly refused broad-family readiness because the smoke did not cover
`multi_turn_dialogue` or `long_context`, and the main Wikitext dataset failure
remained recorded.

This is a data-plane improvement only. It does not add real benchmark-family
evidence until real independent local corpora are provided for the missing
families.
