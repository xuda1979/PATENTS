# MWG-EW Transformer research

The current manuscript is **Auditing Conditional Low-Rank Layers: An Evidence Protocol Applied to Ephemeral FFN Cores, with Negative Results on Dynamic Capacity Allocation**, revised November 16, 2026. It presents the audit methodology for conditional low-rank layers as the primary contribution, with the negative dynamic-versus-static findings as the centerpiece results.

Sole author: **Da Xu**, China Mobile Research Institute, xudayj@chinamobile.com.

## Current manuscript

- `paper/main.tex` and `paper/journal_content.tex`: canonical author-review manuscript.
- `paper/main.pdf`: compiled author-review PDF.
- `paper/tmlr/main_tmlr.tex` and `main_tmlr.pdf`: TMLR-style **preprint**, generated from the same content.
- `paper/journal_refs.bib`: active bibliography; other bibliography/ICLR parts are historical and unused by these builds.
- `paper/REVIEW_20261022.md`: review findings, corrections, verification, and remaining publication gates.

`paper/main_iclr2027.tex` is now a compatibility alias to the canonical manuscript; it is not an ICLR submission. Earlier drafts and run records are retained for provenance. The current manuscript supersedes earlier claims of publication readiness.

## What the revision establishes

The paper derives a fixed-output-subspace error floor, a frozen-projection constant-core baseline, and a matched-schedule descriptor-transfer bound. The accounting code now separates scratch cardinality from global transfers. Archived quality and timing values are recomputed without claiming that hashes establish execution provenance. The v4 kernel's original repeated-call failure is retained as a superseded record; the hardened v3 re-run (2026-11-08) passes 1000/1000 calls and is the current verdict, and parsed HBM/L2 device counters (2026-11-10) corroborate the multicore speedup's traffic attribution. A same-run complete-FFN five-arm sweep (2026-11-12) extends the validated v4 comparison to the full-FFN boundary: v4 beats the v1 fused arm from T=1024 upward but remains slower than the materialized arm at every geometry. A matched trained-model quality–latency run (2026-11-13) closes the Q4 gate for the new block-Givens arm with a negative engineering verdict: matched quality and perplexity, but reference execution 4.48× the persistent latency on the same checkpoints and device.

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

The matched trained-model quality–latency comparison (Q4) is now measured (2026-11-13 run, four seeds): the input-dependent block-Givens arm matches persistent-low-rank quality (relative MSE 0.4444 vs 0.4449; held-out perplexity degradation 2.49% vs 2.38%) but its reference (PyTorch) execution is 4.48× the persistent latency on the same checkpoints, runtime, and Ascend 910B2 device — so the engineering claim is measured false for the reference realization. The pre-registered second architecture (attention output projection $W_O$) has been executed at the CPU synthetic-fixture evidence class (2026-11-16, `experiments/audit_second_architecture_wo.py`): the training-matched Q1 contrast, per-head error budgets, constant-core control, and Q3 checkpointing identity all transfer unchanged and reproduce the central negative finding — capacity, not conditioning, dominates. What remains open: (1) a compiled tile-local realization of the block-Givens rotation, measured against the persistent arm on the same trained checkpoints (the prototype kernel and UB-layout simulator are in `custom_ops/block_givens_tile_apply/`); (2) a constant-core control and quantized baselines in the Q4 design; (3) end-to-end decode latency ($S{=}1$, serving stack) if a serving claim is made. See the review and submission guide for precise acceptance gates.

Remote access is restored and was used for the 2026-11-10–14 measurement campaign (ASI2/ASI3: provenance regeneration, floors evaluation, complete-FFN five-arm sweep, paired shuffled control, matched Q4 run).
