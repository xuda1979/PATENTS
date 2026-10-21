# Session Change Ledger (2026-08-20/21, 17 loop iterations)

All changes made under the "keep improving the paper" loop, with AI1/ASI2
real measurements. Final state: 38 pages, 0 LaTeX warnings.

## New AI1/ASI2 measurements (all real, artifacted)

| # | Experiment | Platform | Result |
|---|-----------|----------|--------|
| 1 | MMLU probe (570 items, ~2% budget) | AI1 | 62.11/62.11/62.46%, neutral |
| 2 | GSM8K 5-shot CoT (260 items) | AI1 | 41.54/41.15/38.85%, neutral |
| 3 | MMLU @ Delta_max=-0.05 (~8.7% patch) | AI1 | 62.11% unchanged; 5/570 per-item changes |
| 4 | World-4 rank sweep (3 launches) | ASI2 | 1.42-1.58x, peak r128, third environment |
| 5 | World-4 sweep, train_iters=10 | ASI2 | 1.52-1.59x, tighter std, closes timing-loop caveat |
| 6 | Unseen-family transfer (Dolly + arXiv) | AI1 | Always-patched 2.29x/1.29x; router over-patches (18.9%/41.8%), degrades (1.38x/1.07x) — family-specific |

## main.tex changes (215 insertions / 63 deletions)

1. **New tables**: tab:mmluacc, tab:gsm8kcot, tab:paretofull (96-cell
   per-row distribution)
2. **Corrected data**: tab:tighterpareto (3 cells), tab:ckptreplication
   (Orig column), distribution claim ([0.9923,1.0195], 66/19/11)
3. **Corrected statistics**: GSM8K sigma 1.4 -> 1.3 of difference-level SE
   (4 sites); other probes verified correct
4. **New evidence text**: abstract (downstream neutrality + layer/family
   specificity), contributions, limitations (8th item: 4 probes + -0.05
   budget + per-item stability), future work (measured boundary), systems
   section (ASI2 replication + ti10), Discussion (family-specificity),
   evidence ladder (3 rows), conclusion (3 sites), reproducibility
5. **Layout fix**: evidence ladder to scriptsize (float overflow)
6. **Fixed**: future-work third item opener inconsistency

## Other files

- REBUTTAL_DRAFT.md: ASI2 note, ti10 note, transfer-negative entry,
  sigma correction, stale items (opening platforms, Concern 6) fixed
- REVIEW.md: pass-3 status block (all outstanding items closed)
- experiments/: mwg_mmlu_acc_eval.py, mwg_gsm8k_cot_eval.py,
  prep_mmlu_subset.py, prep_transfer_corpora.py (new)
- data/: mmlu_subset_10x57.jsonl, transfer/ corpora (new)
- results/: 8 new summaries + verification note (5 passes) + this ledger

## Verification record

results/ASI3_pareto_2026-08-21_verification_note.md — 5 passes:
(1) Pareto 7 cell errors fixed; (2) 16 tables exact vs artifacts;
(3) qualitative tables + sigma audit; (4) ti10 timing loop;
(5) unseen-family transfer.

## Open items (user decision required)

- Multi-model generalization (Baichuan2-13B) — hours-scale experiment,
  available if requested
- Patent disclosure (交底书) April evidence vs paper's May+ forward
  speedups discrepancy — patent filing change, requires explicit direction
- Committing the working-tree changes

## Iteration 19 — clean-build verification

Full from-scratch rebuild (rm aux + pdflatex -> bibtex -> pdflatex x2):
pass3 = 0 warnings, 38 pages; bibtex 0 errors. Camera-ready reproducible.

## Iteration 20 — left-padded GSM8K re-run

Closed the right-padding caveat of the Aug 13 GSM8K probe: re-ran the
zero-shot 260-item probe with padding_side="left" (the staged fix).
Results 22.69/23.46/19.23 (dense/selective/random) vs 18.08/16.92/21.15
right-padded — verdict unchanged (max pairwise 1.26 sigma), absolute
scores improved. All four downstream probes now share left-padded
batching; tab:gsm8kem, downstream paragraph, limitations, ladder,
REBUTTAL updated; 0 warnings, 38 pages.

## Iteration 25 — multi-model probe attempt (aborted, tool improvement kept)

Attempted a Baichuan2-13B layer-16 multi-model probe on AI1:
- Feasibility OK: 13.9B fp16 loads on the NPU (accelerate installed).
- Found and fixed a real tooling limitation: find_ffn_triplet in
  mwg_quality_distillation.py loaded entire safetensors shards over the
  slow NFS filesystem (~10 min/shard) to find one layer's weights. Patched
  with a lazy safe_open fast path that reads only the target layer's three
  tensors (identical results, seconds instead of ~40 min).
- Aborted: the activation-capture phase (26GB model load + teacher
  forwards) reads ~154GB and made no progress in 23+ min on the slow
  filesystem — an environment limit, not a paper gap. Multi-model
  generalization stays future work, now with a documented tooling fix in
  place for when the environment supports it.
- Paper: unchanged (no new claims); the patch is a code-only improvement.

## Iteration 30 — nine-run replication claim verified and corrected

- Found: the paper's "nine-run replication" sentence (1.65x@w1,
  1.55-1.59x@w2, 1.65-1.81x@w4, fwd 0.57-0.80x) had NO archived artifact
  and its numbers matched no archived family (reliability set: w1 ~1.51,
  w2 ~1.42, w4 ~1.47; 0512 family: w4 1.57-1.72).
- Fixed: sentence now reports the verified twelve-run reliability set
  (1.51/1.42/1.47x, fwd 0.52-0.70x) with a Table reference; "nine-run"
  corrected to "twelve-run" in the Discussion and Reproducibility sections
  (the artifact has 4 world sizes x 3 launches = 12 runs).
- A fresh 9-run replication (worlds 1/2/4 x 3, ranks 64/128/256) was
  launched on ASI2 to re-measure the original claim, but the ASI2 Huanxin
  session expired (login_required) mid-way; the remote nohup process may
  have completed — to be checked when ASI2 re-auth is possible.
- 0 warnings, 38 pages.

## Iterations 36-45 — post-convergence maintenance summary

- 36: conclusion redundancy merged (controls/2.1x/low-rank framing stated
  once, not twice).
- 37: Discussion future-work stale claim fixed (dialogue/long-context PPL
  transfer is measured negative, not untested).
- 38: Related Work + Numerical-Evidence intro read (clean); reproducibility
  paragraph now covers the left-padded GSM8K re-run and the transfer corpora.
- 39: Limitations full read (9 items, clean).
- 40: Systems Realization read (four-arm ablation description precise).
- 42: AI1 world-1 benchmark (4th environment, torch 2.7.1): 1.445-1.473x
  vs ASI3 world-1 1.475-1.531x — cross-stack consistent; added to systems
  section.
- 44: evidence ladder + rebuttal sync for the 4th environment.
- 45: rebuttal opening platform description updated (AI1 also ran the
  world-1 systems sweep).
- Final: 38 pages, 0 warnings; systems evidence = 4 environments x 2 torch
  versions.

## Iteration 49-50 — multi-model training on ASI2 (user-directed)

- Baichuan2-13B layer-16 MWG-EW distillation (r384, 5000 steps) on ASI2
  (4 NPUs, fast local storage — the env that AI1's attempt couldn't use).
- Fixed fp16 training NaN on 13B (fp32 student training); found the
  platform's fp16/bf16 lm_head degeneracy (loss ~ ln(vocab)) that blocks
  full-model CE PPL for 13B on this NPU.
- Result: MWG-EW rel MSE 0.1097 / cosine 0.9471 vs static SVD 0.9386/0.2681
  — the generator's advantage over fixed SVD reproduces on a second model
  family (Qwen: 0.10/0.95 vs 0.84/0.40).
- Integrated: ablation ladder rows, quality section sentence, limitations
  item 4 (multi-model partially probed), evidence ladder row, REBUTTAL.
  0 warnings, 38 pages.

## Iteration 51-52 — multi-model always-patched PPL unlocked

- Discovered a platform-wide quirk: fp16/bf16 lm_head logits are degenerate
  (loss ~ ln(vocab)) on the Ascend NPU; an fp32 lm_head forward pre-hook
  restores normal logits (Qwen fp16 test: PPL 10.68). All paper evals are
  fp32 so the reported numbers are unaffected.
- With the workaround: Baichuan2-13B always-patched (uncalibrated, r384,
  5,964 tokens): dense PPL 4.318 / patched 4.415 / ratio 1.0225x —
  degradation direction consistent with Qwen's uncalibrated 1.287x.
- Integrated: limitations item 4, REBUTTAL Concern 5, summary md.
- Final: 38 pages, 0 warnings.

## Iteration 53 — major-review redesign and claim reset (2026-08-23)

- Retitled the paper to remove “Selective” and reframed it as an
  inference-side parameter-lifetime contract and feasibility study.
- Chose persistent low-rank factors plus a small generated core as the actual
  method. Full factor synthesis is now only a break-even analysis boundary.
- Removed the exact paired-scale redundancy: the canonical
  `token_diag_core` controller emits three rank vectors (`3r`), with legacy
  paired-scale/expert modes retained only for checkpoint compatibility.
- Added tests for prefix invariance, batch invariance, diagonal-core algebra,
  `3r` output width, exact paired-scale collapse, and checkpoint round-trip.
- Repaired the Frobenius/operator norm mismatch, removed the unrecoverable
  18-matrix SVD table, added exact `q >= 43` and `q >= 342` full-factor
  thresholds, and added a deployment-regime table.
- Formalized the inference no-escape/no-store operator, split inference from
  save/rematerialize training semantics, and redrew the HBM/L2/SRAM lifecycle.
- Added a matched four-arm kernel protocol, full counter list, call-level
  risk/tail routing requirements, explicit dense latency, mixed-dtype
  element-first state accounting, and prefill/decode terminology corrections.
- Removed the erroneous arXiv:2302.09908 citation; added verified sparse-expert,
  DeepSeekMoE, and fast-weight references.
- Added `paper/REVISION_RESPONSE_MAJOR_REVIEW.md` mapping every major concern
  to completed revisions and open decisive experiments.
- Local targeted prototype tests: 11 passed. Full-suite and final rendered-PDF
  verification follow in this iteration.
- Accelerator policy: any new training is ASI2-only. The queued ASI3 scheduler
  was stopped. No browser/tab control or new login was used. The existing ASI2
  background daemon was not healthy, so no new remote training was claimed or
  launched during this revision.

## Iteration 54 — exhaustive reviewer-compliance double-check (2026-08-23)

- Independently audited all 10 major concerns, 12 additional issues, and six
  minimum experimental packages; recorded the status matrix in
  `paper/REVIEW_COMPLIANCE_AUDIT.md`.
- Corrected remaining architecture language: the method reads persistent thin
  factors and generates only a structured core. Documented the implemented
  bounded `z = 1 + a tanh(h)` parameterization, current `q=1`, and causal rule
  for any future shared group.
- Replaced evaluation-set global ranking with a deployable risk threshold and
  keyed tie rule frozen on a separate calibration set.
- Added controller/source/bank/materialization terms to the scheduled-traffic
  ledger and required measured/model residual plots in the regime experiment.
- Clarified fixed-group theorem scope and retained-energy wording; demoted the
  irrecoverable `1.638x` number from the abstract and labeled dense latency as a
  reconstructed aggregate.
- Corrected OLMo, Grok-1, ACT, and GLU bibliography metadata against primary
  sources and changed unverified prior-work HBM-counter cells to “not reported.”
- Marked legacy generator outputs as ordinary-framework-tensor evidence with no
  no-store claim.
- Verification: 24 tests passed; BibTeX and multi-pass PDF build succeeded with
  no warnings or overfull boxes; all 21 rendered pages visually inspected.
- No accelerator training was launched. Future training remains ASI2-only and
  background-only; no browser or login operation was used.
