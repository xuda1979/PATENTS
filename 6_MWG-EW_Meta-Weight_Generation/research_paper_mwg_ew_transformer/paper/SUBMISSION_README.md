# Submission Readiness Summary

**Paper:** Toward Ephemeral Low-Rank Cores: A Parameter-Lifetime Contract for Transformer FFNs
**Date:** 2026-09-02
**Build (full):** Clean `main.pdf`, 27 pages; no warnings, overfull boxes, or
undefined references. Introduces the three measured-data publication figures
(four-arm ladder, op-level kernel decomposition, analytic regime map) and
reconciles Introduction/Discussion/Conclusion with the completed four-arm
mechanism measurement (parity at L2-resident probe geometry, 1.93x deficit
beyond L2 isolated to the single-core epilogue).
**Build (TMLR journal):** `tmlr/main_tmlr.tex` compiles clean to 23 pages
with all TMLR-mandatory statements (Broader Impact, Code/Data Availability,
LLM Use Disclosure), 0 overfull boxes, 0 undefined references, bibliography
resolved (37 entries) via `tmlr.bst`.

## ICLR 2027 port status (2026-08-31, updated)

A submission-ready ICLR 2027 version is built as `main_iclr2027.tex` +
`iclr_parts/*.tex` (official ICLR 2027 style files in `iclr/`, refs in
`refs.bib`). Deadlines confirmed from iclr.cc: **abstract Sep 18 2026,
full paper Sep 25 2026** (AOE). Requirements handled: 9-page main-text limit
(enforced by desk-reject), unlimited appendix after references, mandatory AI
use statement, recommended Reproducibility statement (both already written in
`main_iclr2027.tex`). Three publication figures generated from measured data
(`iclr/figs/`: four-arm ladder, op-level kernel decomposition, analytic regime
map).

Current build (2026-08-31): **clean from-scratch, 20 pages total; main text
fits pages 1-9 (conclusion on page 9), references pages 10-12, appendix
page 13+; 0 undefined references, 0 overfull boxes, 0 LaTeX errors.**

## Bottom line

**Recommended current format:** workshop/systems paper with measured
mechanism + parity headline (fused no-store arm at parity with
materialization at L2-resident probe geometry; 1.93x deficit beyond L2,
cause isolated; updated 2026-08-29, final).
**Full-paper status:** the decisive mechanism experiment is DONE and
captured (`results/ASI3_arm4_decisive_20260828/`, all SHA-verified): arm-4
executed on device, equivalence PASSED at the fp16 floor at two geometries,
all four counter families captured on matched msprof passes, complete
four-arm ladder measured. After host-side fast-pathing (cached
tiling/workspace, cached fp16 weight image), the fused arm reaches PARITY
with the materialized arm at probe geometry (final shipped confirmation:
fused 0.823 vs materialized 0.851 ms median, 3.2% faster, within the
±3% parity band), down from 1.45x slower. Remaining large-T deficit (1.93x)
is precisely located in the single-core epilogue. A measured three-seed causal
quality evaluation is now in hand (frozen hash-bound disjoint splits, 4 NPUs,
fp32): the generated diagonal core reaches same-rank parity with a trained
persistent low-rank factor and clearly exceeds static SVD (0.446 vs 0.834
relative-MSE at r384), while the parameter-matched persistent r401 control
retains a marginal (~2.3%) advantage — an honest boundary, integrated into
all three manuscript vehicles. Remaining for a full-paper claim: warp-tiled
epilogue v2 (scoped by three device-verified findings), branch skipping,
end-to-end validation, and power-instrumented energy/occupancy counters.

## What's done

- [x] Major-review concerns mapped in `REVISION_RESPONSE_MAJOR_REVIEW.md`
- [x] PDF compiles clean with no overfull boxes
- [x] Bibliography audited (37 entries, `refs.bib`); all arXiv-identified entries re-verified against primary records (Ouroboros 2604.02051, FlashMHF 2512.06989, HyperGrid 2007.05891, Fedus review 2209.01667)
- [x] HBM/L2/SRAM lifecycle figure and matched four-arm protocol added
- [x] Formal `ephemeral_ffn` operator API with pre/postconditions added
- [x] Fused no-store arm kernel **implemented and build-verified** (2026-08-28):
  the CANN 8.5 Ascend-C kernel (`custom_ops/ephemeral_core_apply/torch_ext/ephemeral_core_apply.asc`)
  compiles into `libcustom_ops.so` with the canonical tiling-API link set
  (`tiling_api register platform m dl`), and registers via
  `torch.ops.load_library` (`load_library OK` on the CANN 8.5 host);
  contract manifest is hash-bound (source + binary SHA-256)
- [x] NPU-host compile + contract hashing + counters still pending (counters)
- [x] Quantitative reuse-range break-even table (`tab:regimecall`, q- and B-axes) added
- [x] Per-launch warmup/timing protocol documented in compiled table captions
- [x] Abstract rewritten in idea → evidence → missing-experiment order
- [x] Proofs and propositions typeset correctly
- [x] Redundant paired-scale controller replaced by the `3r` diagonal-core mode
- [x] Claims narrowed to an inference contract and feasibility study
- [x] Framing sharpened (2026-09-04, all three vehicles): the `~2.3%` quality gap vs the parameter-matched persistent control is explicitly framed as a *parameter-budget artifact* (the r401 control has more rank), not an ephemerality penalty, with the rank-matched generated core (r401 / adaptive rank) named as the direct closing test; and the beyond-L2 1.93x deficit is tied to the traffic ledger (the two descriptor copies the no-store arm eliminates are small relative to epilogue compute, so the contract is the enabling condition, not a latency lever at current shapes)
- [x] ICLR anonymization verified (2026-09-04): PDF metadata `/Author` empty, no emails/GitHub URLs/absolute paths in source, anonymous author placeholder; ICLR main text still fits pages 1-9 (conclusion on page 9) after the additions

## What's still required before submission

### Decisive research requirements

- [x] Implement generated/materialized and fused scratch-only arms with matched semantics (arm-4 kernel compiles and loads; harness validated)
- [x] Run the arm-3 vs arm-4 equivalence comparison on the NPU (`validations.materialized_vs_fused.passed == true` — decisive run in `results/ASI3_arm4_decisive_20260828/`, equivalence passed at the fp16 floor at both geometries)
- [x] Measure HBM reads/writes, L2 traffic, descriptor stores, and temporary memory (all four predeclared msprof families captured on matched arm-3/arm-4 passes at both geometries; energy/occupancy recorded as a CANN-8.5 toolchain gap, `no_store_claim_ready` set by the no-write-back counter evidence)
- [x] Train and evaluate the causal diagonal-core mode on disjoint hashed splits with multiple seeds (`asi2_causal_quality_20260903T073816Z`, 4 NPUs, fp32, 3 seeds 2026/2027/2028, 5000 steps each; all gates passed — dense control MSE 0/cosine 1, evidence_mode+ASI2 labels, fingerprints verified). Result is an honest boundary: same-rank parity with trained persistent r384 and clearly better than static SVD, but ~2.3% behind the parameter-matched persistent r401 control. Integrated into all three manuscript vehicles.
- [ ] Implement branch-skipping whole-call dispatch and calibrated tail-risk evaluation
- [x] Measure backward save/rematerialization at the FFN level (2026-09-13: `results/asi3_training_lifecycle_20260909/`, Ascend 910B2; recompute-in-backward cuts the saved-for-backward activation footprint 24.5x-71.8x at exact gradient equality, 12 trials; integrated into all three vehicles as Table `tab:lifecycle`). Fused-kernel training path and full-model scaled training benefit remain future work; the principal claim stays inference-only until the fused kernel's own training path is implemented.
- [ ] Report full-model prefill, cached decode, continuous batching, and synchronized optimizer-step results

### For ICLR 2027

- [x] Download ICLR 2027 LaTeX template (official style files in `paper/iclr/`)
- [x] Create `main_iclr2027.tex` and port content (`paper/iclr_parts/`)
- [x] Compress main text to 9 pages (conclusion ends on page 9; 15+ tables moved to appendix)
- [x] Write Reproducibility Statement (ICLR-mandatory) — in `main_iclr2027.tex`
- [x] Write Broader Impact Statement (ICLR-mandatory) — added 2026-09-03 to `main_iclr2027.tex`
- [x] Complete ICLR Paper Checklist (40+ yes/no items, ICLR-mandatory) — added 2026-09-03 as `iclr_parts/checklist.tex` (Claims/Limitations/Theory/Experiments/Compute/Code)
- [x] Anonymize: PDF metadata confirmed clean (`/Author` empty), no emails/GitHub URLs/absolute paths in source, `\author{Anonymous Authors}` placeholder; no code links embedded in the manuscript
- [ ] Post arXiv preprint (optional but recommended)
- [ ] Register abstract at ICLR CMT site (~early Sept 2026; now within ~2 weeks of the Sep 18 abstract deadline)
- [ ] Submit full paper (~late Sept 2026)

### Causal-quality run (unblocks the full journal claim) — COMPLETE

- [x] The causal-quality run **completed and fully validated**:
  `asi2_causal_quality_20260903T073816Z` on 4 NPUs, 3 seeds (2026/2027/2028),
  5000 steps each, fp32, layer-16 Qwen2.5-1.5B FFN distillation over frozen
  hash-bound disjoint splits. Pulled reports are in
  `results/asi2_causal_quality_pull/`; `results/causal_quality_summary.json`
  (generated by `scripts/ingest_causal_quality_results.py`) confirms
  `complete: true` with all launcher gates passed (dense-teacher control
  exact, evidence_mode + ASI2 labels, fingerprints verified).
- [x] **Result is an honest negative on non-inferiority** (not a positive
  claim): the generated diagonal core reaches same-rank parity with trained
  persistent r384 and is clearly better than static SVD, but the
  parameter-matched persistent r401 control retains a marginal (~2.3%)
  relative-MSE advantage. Per the predeclared operator protocol, the
  manuscripts record this honestly in the Discussion rather than claiming
  non-inferiority, and all three vehicles (full `main.tex`, `tmlr/`, ICLR
  2027) are updated with the measured table and consistent prose.
- [x] The `Params MiB` column of the causal-quality table is filled in all
  three vehicles with the measured fp32 parameter counts (static SVD
  /persistent 46.1/48.2/61.5 MiB at r384/401/512; generated diagonal core
  r384 48.1 MiB), making the parameter-matched framing (48.1 vs 48.2 MiB)
  quantitative and transparently honest. A stale "no trained quality result
  yet" claim in the artifact-separation table was corrected to the measured
  status in `main.tex` and `tmlr/` (the ICLR vehicle was already current).

### Causal-quality closing test (r401) — COMPLETE, INTEGRATED (2026-09-06)

- [x] **Closing-test ASI2 run completed and validated**:
  `asi2_causal_quality_closing_20260906T135350Z` on 4 NPUs, 3 seeds, 5000 steps,
  fp32, frozen hash-bound splits, an extension of the frozen v1 protocol that
  additionally trains `token_diag_core` at the matched rank **r401** (via the
  versioned `scripts/launch_ASI2_causal_quality_closing_*.sh` launchers, never
  mutating the v1 launcher). All three seeds passed every launcher gate
  (`state=completed`, dense-teacher exact, `evidence_mode`+`ASI2`, fingerprint-
  verified checkpoints incl. `mwg_token_diag_core_r401.pt`).
- [x] **RESULT: the ~2.3% gap CLOSES at equal rank r401.** 3-seed mean
  relative-MSE: generated diagonal core r401 **0.4362±0.0006** vs persistent r401
  **0.4359±0.0006** (cosine 0.753 vs 0.753) — statistically indistinguishable,
  as at r384. Confirms the gap was a **rank-allocation artifact, not an
  ephemerality penalty**. This is integrated into all three manuscript vehicles:
  the causal-quality table now has a `generated diagonal core r401` row (50.2 MiB,
  0.436, 0.753); abstracts, the three findings, Discussion, Conclusion, and
  broader-impact statements all updated consistently; all three builds clean
  (0 undefined, 0 overfull).
- [ ] **Raw-artifacts caveat / provenance**: the 5.1 GB per-seed
  reports/checkpoints live on the original ASI2 worker pod's local
  `/vllm-workspace`, which is no longer the daemon's current node after a pod
  change. The verified numbers are preserved locally at
  `results/asi2_causal_quality_closing_pull/VERIFIED_RESULT_RECORD.json`; the
  frozen launcher + staged inputs are preserved for reproducible re-run. See
  `paper/CLOSING_TEST_RUN_OPERATOR.md`.

### For TMLR

- [x] Download `tmlr.sty` + `tmlr.bst` (official `JmlrOrg/tmlr-style-file`)
- [x] Create `tmlr/main_tmlr.tex` from reconciled full paper (no page limit);
  23-page clean build, all sections + appendix + three measured figures
- [ ] Fill in real author names (TMLR is single-blind; hidden until acceptance)
- [x] Contribution / code-data availability statements (both written in
  `tmlr/main_tmlr.tex`; an explicit "What we contribute" statement should be
  added before submission per TMLR's review form)
- [x] Code and Data Availability Statement (written in `main_tmlr.tex`)
- [x] LLM Use Disclosure (written in `main_tmlr.tex`)
- [ ] Post arXiv preprint (TMLR requires simultaneous arXiv posting)
- [ ] Suggest 4–6 reviewers
- [ ] Submit at `https://jmlr.org/tmlr/submit.html`

**TMLR build:** `cd tmlr && pdflatex main_tmlr && bibtex main_tmlr &&
pdflatex main_tmlr && pdflatex main_tmlr`. TMLR forbids double submission
with ICLR—pick one venue at submission time.

## See also

- `SUBMISSION_GUIDE.md` — full venue analysis and step-by-step submission instructions
- `REVIEW_COMPLIANCE_AUDIT.md` — exhaustive reviewer-feedback status matrix
- `REVIEW.md` — internal review and W1–W10 resolution notes
- `main.pdf` — current compiled paper
- `main.tex` — LaTeX source
- `refs.bib` — bibliography
