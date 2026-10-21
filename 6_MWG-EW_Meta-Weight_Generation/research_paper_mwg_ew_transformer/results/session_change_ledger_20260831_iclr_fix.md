# Session Change Ledger — 2026-08-31 (ICLR 2027 manuscript hardening)

Scope: bring the active ICLR 2027 submission (`main_iclr2027.tex` +
`iclr_parts/*.tex`) to a clean, compliant, top-venue-ready state and reconcile
the measured-claims ledger against the decisive arm-4 artifacts.

## Critical defect fixed: duplicated Introduction

`iclr_parts/intro.tex` contained a stale, truncated second `\section{Introduction}`
block (lines 145-164, a leftover merge artifact). This was live in the build:
- Section numbering was shifted by one (Related Work rendered as section 3
  instead of 2).
- The main text spilled past page 9 (conclusion on page 10), violating ICLR's
  9-page main-text limit.
Removed the duplicate block. After the fix, section numbering is correct
(Intro/Related/Arch/Analysis/Systems/Protocol/Results/Discussion = 1-8) and the
main text now ends on **page 9**, satisfying the ICLR limit.

## Numeric reconciliation (arm-4 decisive artifacts)

Aligned the paper's headline numbers to the authoritative shipped measurement
in `results/ASI3_arm4_decisive_20260828/`:
- Large-T (T=4096) fused/materialized ratio: `1.95x` -> `1.93x` (exact
  2.6821/1.3932 = 1.9252) across abstract, evidence-map, systems text, appendix
  figure caption. (The `1.95e-3` equivalence max_abs is a distinct number and
  was left unchanged.)
- Parity prose in `systems.tex` now precisely reports the final shipped
  same-session confirmation (fused 0.823 ms vs materialized 0.851 ms, 3.2%
  faster), keeping the conservative "within a +/-3% band straddling 1.0x"
  framing that the repeated independent runs support.

## Build verified (from-scratch)

rm aux/bbl/blg/out/log -> pdflatex -> bibtex -> pdflatex x2:
- 20 pages total; main text pages 1-9, references 10-12, appendix 13+.
- 0 undefined references/citations, 0 overfull boxes, 0 LaTeX errors.

## README/gitignore updates

- `SUBMISSION_README.md`: current build status (9-page limit CONFIRMED),
  decisive arm-3/arm-4 equivalence + counter measurement marked complete,
  causal-quality item marked fully staged (frozen SHA-verified splits +
  `launch_ASI2_causal_quality_detached.sh`) pending ASI2 re-auth.
- `paper/.gitignore`: ignore `main_iclr2027` build artifacts.

## Open / blocked from this session

- The causal diagonal-core LM-quality evaluation (the paper's largest open
  item) is fully staged and verified locally (train 630 / dev 300 / test 303
  frozen rows, SHA-256-verified, zero near-duplicate overlap between splits;
  `mwg_quality_distillation.py` supports the `token_diag_core` student mode).
  Launching it needs the ASI2 browser-automation session, which cannot be
  established from this headless context (daemon startup times out; Safari SSO
  and standalone fallback are deliberately disabled). One command fires it once
  auth is restored:
  `bash scripts/launch_ASI2_causal_quality_detached.sh`.
