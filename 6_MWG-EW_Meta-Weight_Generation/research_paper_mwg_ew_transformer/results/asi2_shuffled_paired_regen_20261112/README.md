# Same-run paired shuffled-context control on regenerated artifacts — ASI2, 2026-11-12

## What this is

Re-establishment of the manuscript's shuffled-context control
(Table `tab:paired`, "generated-minus-shuffled" contrasts) on the
2026-11-10 regeneration's artifacts. The archived control
(`asi2_rank512_control_20260922`) measured the contrast as a
**same-run pair** — token and shuffled students trained in one process,
one seed at a time — giving $-0.000208$ (r384) and $-0.000196$ (r401).
The 2026-11-10 regeneration retrained token/persistent students but not
the shuffled arm, so the control needed re-running against the same
teacher, activations, splits, and hyperparameters before the paired
contrast could be claimed on the regenerated family.

This run trains `token_diag_core` and `shuffled_diag_core` at ranks
384 and 401 **in the same process per seed**, reusing the
regeneration's activation cache (identical cache fingerprints: model
digest `b6c94448…`, same code digest, same split metadata, same
activation parameters).

## Result

Same-run paired contrast (token − shuffled, relative MSE, n=4 seeds):

| Rank | Mean | Per-seed | Descriptive 95% interval |
|------|------|----------|--------------------------|
| 384 | $-0.000239$ | $-0.000290, -0.000262, -0.000228, -0.000176$ | $[-0.000316, -0.000162]$ |
| 401 | $-0.000289$ | $-0.000373, -0.000268, -0.000265, -0.000248$ | $[-0.000379, -0.000198]$ |

The archived contrasts ($-0.000208$, $-0.000196$) fall within the new
intervals: the "little observed dependence on correct token context"
conclusion replicates on the regenerated artifacts. As before, this is
about $0.05\%$ of the control MSE and does not establish a meaningful
task-quality difference; it shows the learned controller's advantage
over a shuffled-context control is near zero at these ranks.

## Methodological note (why two runs exist)

A first attempt (run `asi2_shuffled_context_regen_20261112T092733Z`,
retained on ASI2) trained **only** the shuffled students and paired
them cross-run with the 2026-11-10 regeneration's token arm. That
pairing produced $-0.0019$/$-0.0021$ contrasts — an order of magnitude
larger than the archive — because independent trainings of the same
student differ by $\sim 0.002$ relative MSE (run-to-run variance),
which dominates a $0.0002$ contrast. Cross-run pairing of separately
trained students is therefore **not a valid estimate** of the contrast;
only same-run pairs are. The paired run in this directory is the valid
control; the first run is retained as the negative example documenting
this pitfall.

## Files

- `shuffled_context_summary.json` — 8 shuffled rows (4 seeds × 2 ranks),
  md5 `b4b4ae7b8eae42730cd85761eaa55a53` (matches remote).
- `paired_cells.json` — per-seed same-run cells for both arms (4 rows,
  `kind: paired_shuffled_control_cells_v1`, md5
  `dca0f8fd1243bff7a21bb39881cab6f7`, fetched from remote
  `/tmp/paired_cells.json` and hash-verified on arrival). The audit
  gate computes contrasts from these same-run cells only.
- `README.md` — this record.

Remote (ASI2, retained):
`/vllm-workspace/mwg-ew-transformer-research/results/asi2_shuffled_paired_regen_20261112/`
— full per-seed `mwg_quality_distillation_*.json` reports (with
token-arm cells), checkpoints, progress records; plus the first
attempt's directory `asi2_shuffled_context_regen_20261112T092733Z/`.

## Provenance

- Run: 2026-11-12T10:18–10:32Z, ASI2 (CPU), 4 seeds sequential.
- Harness: `experiments/mwg_quality_distillation.py` (md5
  `ae17e6bf2a588840c81ff4edf84638db` — same as regeneration and
  archived shuffled-context family).
- Args: identical to the 2026-11-10 regeneration's per-seed invocation
  (recorded in its provenance argv) except `--student-specs
  token_diag_core:384,shuffled_diag_core:384,token_diag_core:401,shuffled_diag_core:401`,
  per-seed outdir, and run id.
- Teacher: Qwen2.5-1.5B-Instruct layer-16 FFN, model digest
  `b6c944482ac7fe5c…` (identical to regeneration).
- Activation cache: reused from the regeneration
  (`--cache-dir …/asi2_causal_quality_closing_20261110T155855Z/cache`);
  fingerprints matched, no rebuild.

## Claim boundary

- Relative-MSE reconstruction for one isolated layer; no perplexity or
  task metric.
- Two ranks (384, 401); rank 512 contrast was not re-run (the archived
  r512 contrast is $+0.000025$, interval spanning zero).
- Four seeds; descriptive intervals only, no population claim.
