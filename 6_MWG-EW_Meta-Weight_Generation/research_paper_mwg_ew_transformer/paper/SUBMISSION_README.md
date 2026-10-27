# Current journal manuscript

Sole author: Da Xu, China Mobile Research Institute, xudayj@chinamobile.com.

Use `main.pdf` for the standard author-review copy or `tmlr/main_tmlr.pdf` for the TMLR preprint. Both use `journal_content.tex`, `journal_preamble.tex`, `journal_refs.bib`, the current generated tables, and the two `figs/journal_*.pdf` plots.

The current version is **not certified submission-ready**. See `REVIEW_20261022.md` for the failed v4 stability gate, missing canonical quality provenance, and absent same-model quality–latency evidence. No journal submission has been made in this revision.

Rebuild from the research root with `bash scripts/build_journal.sh`. Run `python scripts/audit_journal_evidence.py --require-submission-ready` to check the scientific readiness gate; it intentionally exits 2 while unresolved.

The TMLR wrapper uses the bundled style's `preprint` option to show the author requested by the user. A future double-blind submission must be anonymized consistently, including supplements and links; it is not created automatically here. The retired ICLR entry point forwards to the canonical article and must not be submitted as conference-format material.
