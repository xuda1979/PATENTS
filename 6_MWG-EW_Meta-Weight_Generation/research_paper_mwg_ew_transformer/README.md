# MWG-EW Transformer research

The current manuscript is **Ephemeral Low-Rank Cores for Transformer FFNs: Representation Limits, Memory Accounting, and Controlled Evaluation**, revised October 22, 2026.

Sole author: **Da Xu**, China Mobile Research Institute, xudayj@chinamobile.com.

## Current manuscript

- `paper/main.tex` and `paper/journal_content.tex`: canonical author-review manuscript.
- `paper/main.pdf`: compiled author-review PDF.
- `paper/tmlr/main_tmlr.tex` and `main_tmlr.pdf`: TMLR-style **preprint**, generated from the same content.
- `paper/journal_refs.bib`: active bibliography; other bibliography/ICLR parts are historical and unused by these builds.
- `paper/REVIEW_20261022.md`: review findings, corrections, verification, and remaining publication gates.

`paper/main_iclr2027.tex` is now a compatibility alias to the canonical manuscript; it is not an ICLR submission. Earlier drafts and run records are retained for provenance. The current manuscript supersedes earlier claims of publication readiness.

## What the revision establishes

The paper derives a fixed-output-subspace error floor, a frozen-projection constant-core baseline, and a matched-schedule descriptor-transfer bound. The accounting code now separates scratch cardinality from global transfers. Archived quality and timing values are recomputed without claiming that hashes establish execution provenance. The v4 kernel's failed repeated-call test remains failed.

New CPU checks exercise the actual `LowRankFFN(token_diag_core)` implementation. Checkpointing retained 13× fewer unique nonparameter storage bytes in nine small synthetic cases, with exact output and gradient agreement. This is software evidence, not peak-memory, accelerator-speed, or trained-model-quality evidence.

## Rebuild and verify

Python dependencies: NumPy, Matplotlib, pytest, and PyTorch (CPU is sufficient). LaTeX needs pdfLaTeX, BibTeX, PGF/TikZ, natbib, and the included TMLR style files. Recorded versions are in `results/journal_revision_20261022/`.

```bash
python scripts/audit_journal_evidence.py --tables
python scripts/verify_journal_analysis.py
python experiments/measure_journal_lifecycle.py --output /tmp/mwg-lifecycle-check.json
python -m pytest -q tests/test_journal_accounting.py tests/test_journal_evidence.py tests/test_journal_lifecycle.py tests/test_mwg_regime_map.py tests/test_token_diag_core.py
bash scripts/build_journal.sh
```

`PYTHON_BIN` selects the Python used by the build. `MWG_BUILD_ROOT` selects its temporary LaTeX directory. Regenerating the CPU experiment into `/tmp` preserves the committed historical measurement record.

```bash
python scripts/audit_journal_evidence.py --require-submission-ready
```

This command intentionally exits 2 while the documented empirical gates remain unresolved. A successful audit execution is distinct from submission readiness.

## Evidence and scope

- `results/journal_revision_20261022/evidence_audit.json`: recomputed archive values, hashes, failed gates, and limitations.
- `results/journal_revision_20261022/analysis_checks.json`: 50 synthetic algebra checks.
- `results/journal_revision_20261022/lifecycle_cpu.json`: nine new actual-module software measurements.
- `scripts/audit_journal_evidence.py`: standard-library archive audit and current table generation.
- `experiments/mwg_regime_map.py`: version-2 partial global-transfer accounting; old version-1 totals are not directly comparable.

Original canonical quality run reports, trained checkpoints, and complete data manifests are absent from this checkout. The v1 kernel's full timing reports are also absent locally. The revised paper does not claim independent reproduction of these accelerator measurements.

## Remaining research

The critical requirement is a quality–latency comparison from the same causal trained model and runtime, including persistent/constant-core/quantized controls, resolved v4 stability, same-run materialized-versus-fused measurements, and independently verified held-out model quality. See the review and submission guide for precise acceptance gates.

Remote recovery is currently blocked in this session: the shell wrapper delegates to an absent Mac-local script, and neither rclone nor its relay configuration is available. Runtime guidance also conflicts: the parent `CLAUDE.md` and operations skill say ASI2, while `TOOLS.md` says ASI3. Restore the approved access path and resolve the target environment before launching new training. This revision launched no remote jobs.
