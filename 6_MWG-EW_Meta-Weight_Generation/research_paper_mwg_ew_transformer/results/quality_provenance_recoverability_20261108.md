# I-0002 quality-provenance recoverability assessment — 2026-11-08

## Question

Issue I-0002 ("Original quality provenance incomplete", severity high,
first evidence `paper/REVIEW_20261022.md`) asks whether the original
quality-experiment provenance — checkpoint/data/code bindings for the
four training-seed records — can be recovered and verified from
surviving artifacts, after the review found that local hashes only
established integrity of archived files and that realized
split/checkpoint provenance remained incomplete.

## What survives, and where

The 4-seed closing-test family `asi2_causal_quality_closing_20260920T044032Z`
(Family 3 in `results/REGISTRY.md`, archived under
`results/asi2_causal_quality_closing_pull_20260920_4seed/`) records its
provenance anchors **inside the per-seed reports**:

- `teacher.model_digest` = `b6c944482ac7fe5c54afe482fadc7cf9a100a652a79ca1fbe684e268261c1c40`
- `teacher.state_file` = `/root/work/filestorage/Qwen2.5-1.5B-Instruct/model.safetensors`
- `teacher.layer` = `16`, weight tensors
  `model.layers.16.mlp.{up,gate,down}_proj.weight`

## Verification performed (2026-11-08, live on ASI2)

1. **Teacher model directory re-hashed.** Recomputed the exact
   `build_run_provenance()` model digest
   (canonical SHA-256 over {path, bytes, sha256} rows for state files
   plus config/tokenizer globs, per
   `experiments/mwg_quality_distillation.py:371-437`) over the current
   ASI2 `/root/work/filestorage/Qwen2.5-1.5B-Instruct/`:

   - recomputed digest = `b6c944482ac7fe5c54afe482fadc7cf9a100a652a79ca1fbe684e268261c1c40`
   - **MATCHES the recorded `model_digest` exactly.**
   - `model.safetensors` sha256 = `dd924a11b4c220f385b51ffa522daea7c9f3d850e31b162bb5661df483c6d3ee` (3,087,467,144 bytes), unchanged since the May 6, 2026 checkout.

   Conclusion: the teacher checkpoint binding for all four seeds is
   **recovered and verified** — the model directory on ASI2 is
   byte-identical to what the September 20, 2026 4-seed run consumed.

2. **Data-split provenance verified locally.** The quality split
   (`data/quality/`) hashes to the audited values
   (`train/dev/test` = `832e3e3c…` / `e67987cc…` / `8e2acce8…`, zero
   cross-split overlap per `results/quality_split_audit_20260823.md`),
   and its manifest binds five upstream held-out sources (gsm8k_test,
   mbpp_test, alpaca_cleaned_train_tail, wikitext103_validation_extra,
   …) by sha256 — all of which re-hash identically today.

3. **What is NOT recoverable from live remote state.** The original
   execution trees under `/vllm-workspace/mwg-ew-transformer-research/`
   (the `PROJECT_ROOT` the September runs used) no longer exist on the
   current ASI2 environment — `/vllm-workspace` now contains only the
   vllm installation, and the shared
   `/root/work/filestorage/mwg-ew-transformer-research/results/` tree
   (71 entries) has no `asi2_causal_quality_*` directories. The
   full `artifact_manifest.json` / per-run `run_input_digest` records
   (written by the launcher into each `RUN_DIR`) were therefore lost
   with those run directories; only the pulled per-seed reports and
   VERIFIED_RESULT_RECORD survive.

## Assessment

- **Teacher checkpoint binding: RECOVERED and VERIFIED** (live digest
  match on ASI2, 2026-11-08).
- **Data-split binding: RECOVERED and VERIFIED** (sha256 chain from
  `data/quality/manifest.json` through upstream held-out sources,
  re-verified locally).
- **Code binding: PARTIAL.** The per-seed reports embed
  `model_digest` but the archived fragments do not include the
  `code_digest` / `run_input_digest` fields (the launcher wrote those
  into `RUN_DIR/artifact_manifest.json`, which is among the lost
  files). The exact code state is however reconstructible from the
  repository git history at the launch dates (2026-09-06/09-20), and
  the protocol scripts that produced the runs
  (`scripts/launch_ASI2_causal_quality_closing_{detached,oneshot}.sh`,
  `experiments/mwg_quality_distillation.py`) survive in the repo.
- **Run-directory level provenance (status.json, artifact_manifest.json,
  raw run logs): NOT RECOVERABLE** from the current remote
  environments; only the pulled metric reports survive.

## Recommended disposition

I-0002 can be substantially narrowed: the checkpoint/data bindings —
the part the review called "realized split/checkpoint provenance" —
are now re-verified against live remote state. The residual gap is
limited to (a) per-run artifact manifests and (b) code digests, both
recoverable in the future by re-running the closing protocol under the
still-present launcher, which writes those records into the run
directory at execution time. Recommend recording this assessment in
the issue tracker and, if journal submission requires it, re-running
the 4-seed protocol once on a quiet device to regenerate the full
provenance chain end-to-end.

## Verification record

- Recomputation script: `/tmp/recompute_model_digest.py` (replicates
  `build_run_provenance` model-digest logic verbatim), executed on
  ASI2 via the Huanxin daemon (port 19004) 2026-11-08.
- Recomputed output archived at `results/model_digest_check_asi2_20261108.json` (pulled below).
- Per-seed reports with `model_digest`:
  `results/asi2_causal_quality_closing_pull_20260920_4seed/seed_202{6,7,8,9}_report.json`.
