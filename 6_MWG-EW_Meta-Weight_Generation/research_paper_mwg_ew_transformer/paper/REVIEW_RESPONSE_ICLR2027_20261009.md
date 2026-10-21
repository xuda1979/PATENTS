# Response to the Critical Review of "Toward Ephemeral Low-Rank Cores"

**Review reviewed:** `Ephemeral_Low_Rank_Cores_Critical_Review.docx`, dated 2026-10-09
**Recommendation in review:** Reject in present form, with encouragement to resubmit after substantial new experiments.
**This document:** Point-by-point verification, response plan, and execution ledger. Every
factual claim of the review has been checked against the repository's result registry
(`results/` verified records, kernel sources, and paper sources). The review's arithmetic
is correct in every spot-checked instance; the criticisms are accepted as the working
requirements list for resubmission.

---

## 0. Verification summary — what we checked and found

We independently re-derived every quantitative claim in the review before planning any
response. Findings:

| Review claim | Verified? | Repository evidence |
|---|---|---|
| Persistent r401 = 48.2 MiB vs generated r384 = 48.1 MiB; generated r401 = 50.2 MiB (4.15% extra) | ✅ exact | `parameter_bytes` of the models: 3·r·(d+m)·4 B = 12,091,392 params (46.125 MiB) at r384 persistent; generated adds a 2-layer controller (d→192→3r, 517,440 params) = 12,608,832 params = 48.099 MiB; r401 generated = 13,159,872+controller ≈ 50.2 MiB |
| Persistent r512 = 61.5 MiB = 27.86% more than generated r384 = 48.1 MiB | ✅ exact | 61.5/48.1 − 1 = 27.86% |
| "Parameter-matched" label in cross-rank table (r512 vs r384) is wrong | ✅ accepted | `appendix_b.tex` Table (cross-rank rows): persistent r512 61.5 MiB vs causal r384 48.1 MiB are *not* parameter-matched; the near-match is persistent r401 (48.2) vs generated r384 (48.1) |
| Persistent r384 MSE differs across tables: 0.4458/0.4460 (Table 10 region) vs 0.4498 (shuffled table) | ✅ confirmed | Two different run families: `asi2_causal_quality_closing_pull_20260920_4seed` (run `asi2_causal_quality_closing_20260920T044032Z`) gives persistent r384 = 0.4460±0.0006; `asi2_shuffled_context_4seed_20260922` (run `asi2_shuffled_context_4seed_20260922T042246Z`) gives 0.4498±0.0013 |
| Persistent r401 MSE: 0.4362 vs 0.4405 across tables | ✅ confirmed | Same two run families (0.4363 vs 0.4405) |
| Persistent r512: 0.376 vs 0.3833 | ✅ confirmed | Closing-pull family 0.3761; `asi2_rank512_control_20260922` family 0.3833±0.0012 |
| Causal-vs-shuffled r384 diff: 0.0029 vs ~0.0002 | ✅ confirmed | Mixed-family comparison gives 0.4462−0.4491 = 0.0029 (the paper's shuffled table); coherent family `asi2_rank512_control_20260922T080042Z` gives per-seed paired diff −0.00021 (t(3)=−12.31) |
| Fused 0.8234 ms / persistent 0.2469 ms = 3.33× slower | ✅ arithmetic correct | Table 1 four-arm values in `systems.tex` |
| v4 "3.03×" is vs v1, not vs materialized | ✅ confirmed | `v4_multicore_benchmark_asi2_v2_20261008.json`: T=4096 v1 0.5434 ms → v4 0.1794 ms; no materialized arm in the v4 session |
| Table 6 caption says optimizer update "identical for both arms" while Table 7 shows it differs | ✅ confirmed | `appendix_b.tex` line 112 vs Table 7 narrative ("dense pays 8.97 ms … vs 1.0–1.3 ms") |
| 32 tiles × ~2 ms ⇒ ~64 ms contradicts 2.682 ms call | ✅ confirmed | `appendix_b.tex` line ~986; the 2 ms is per-*launch-of-32-tiles* profiler-pass aggregation, not per-tile — wording must be fixed |
| Main text (v1 tiles T at baseM=128) vs Appendix S (v1 materializes full T×r in UB) | ✅ confirmed real tension | `systems.tex` line 68 says v1 tiles at baseM=128; `appendix_b.tex` line ~1005 says v1 materializes the full T×r C matrix in UB. Kernel source `ephemeral_core_apply.asc` shows v1 *does* tile M (BASE_M=128, `while (mm_.Iterate<true>())` loop) but the per-tile C is only baseM×r; the "2 MiB full C" claim is the *logical* C size, not the resident UB footprint. Both texts are misleading and must be reconciled to the audited source |
| Abstract notation ($W_g U_p V_p^\top$ outer product) inconsistent with canonical diagonal-core form ($((xU)\odot z)V$) | ✅ confirmed | `main_iclr2027.tex` abstract vs `arch.tex` Eq. (diag-core) |
| 1000-call NaN event ("environment-level transient") is unresolved | ✅ accepted | `v4_multicore_benchmark_asi2_v2_20261008.json` `stability_1000_calls`: `{completed: 1000, final_max_abs_err: NaN, pass: false}` — the failure is in the *record*; attribution is unproven |
| Checklist has stale seed counts (2026–2028) and blanket [Yes] | ✅ confirmed | `checklist.tex` line 75 still says seeds 2026–2028 although the paper is 4-seed (2026–2029) |

**Bottom line of the verification:** the review contains zero factual errors we could
find. The cross-table inconsistencies are real registry-hygiene failures: the paper mixes
values from (at least) three distinct run families — `…closing_20260920T044032Z`,
`…shuffled_…20260922T042246Z`, and `…rank512_…20260922T080042Z` — without binding
each table row to a run ID.

---

## 1. Single most important discovery during verification

The coherent run family **`asi2_rank512_control_20260922T080042Z`** already contains,
in one run, every arm the review asks to be compared: persistent / causal-diag /
shuffled-diag / static-SVD at ranks 384, 401, 512, four seeds each. Its per-seed
paired statistics (computed fresh from its per-seed record):

| Paired difference (rel-MSE, causal − control) | r384 | r401 | r512 |
|---|---|---|---|
| causal − shuffled | −0.00021 (t(3)=−12.31) | −0.00020 (t(3)=−10.13) | +0.00002 (t(3)=+2.50, n.s.) |
| causal − persistent | −0.00075 (t(3)=−3.94) | −0.00080 (t(3)=−3.94) | −0.00132 (t(3)=−65.94) |

Implication, accepted honestly: **in the coherent single-family comparison the
context-conditioning effect is ~0.0002 (≈0.05% of MSE), an order of magnitude smaller
than the 0.0029 the paper currently reports from mixed-family rows.** The paper's
"small but consistent causal edge" narrative survives directionally (r384, r401 paired
t ≈ −10 to −12) but its magnitude claim must be corrected, and the equal-total-budget
question (controller parameters vs. quality) remains unfavorable to the method at this
scale. This is exactly the review's Section 4 point; we will rebuild Tables 10–12
exclusively from this run family and re-derive every narrative number from it.

---

## 2. Response strategy

The review's decisive criterion (its Section 8 close) is: *a reproducible
quality-adjusted advantage over a strong persistent low-rank implementation, or a
broadly useful enforcement-and-measurement method that explains when transient operands
improve real systems.* Our response therefore has three tracks:

- **Track A (P0, no new device time needed):** rebuild the result registry and
  re-derive every table from single coherent run families; correct all mislabeled
  comparisons; fix every Section 9 presentation defect. This is executable immediately
  from existing verified records.
- **Track B (P0/P1, needs ASI2 time):** the review's required experiments that need
  device runs — matched four-arm v4 ladder, persistent-low-rank DDP control, patched
  complete-model evaluation, router dispatch implementation, stress/failure-inclusive
  stability runs.
- **Track C (framing):** adopt the review's suggested conclusion as the new paper
  skeleton. The paper becomes: an *enforcement-and-measurement* contribution
  (parameter-lifetime contract + audit method + measurement protocol) with an honest
  negative-to-neutral quality result and a positive kernel-engineering result (v1→v4),
  explicitly narrowing claims until Track B evidence lands.

We do **not** plan to contest any of the review's factual findings.

---

## 3. Point-by-point response

### 3.1 §3.1 — "The lifetime distinction needs a substantive result"
**Accept.** The novelty question (vs. conditional low-rank adaptation, FlashMHF [R3],
FlashAttention [R4]) is fairly posed. Response:
1. Recenter the contribution on the *enforcement and measurement method*: the contract
   manifest + source audit + (to be added per §5.1) binary/address-level audit with a
   positive materialized control. This is a methods contribution that does not require
   beating persistent low rank on quality.
2. Run the review's suggested mechanism-enforcement demonstration across a second
   generated-operand architecture (constant-core and mean-core generators are already
   cheap to add in `mwg_quality_distillation.py`'s generator registry).
3. Remove every "advantage" implication that lacks a quality- or latency-matched
   comparison (see Track A item list below).

### 3.2 §3.2 — "The best current baseline challenges the method"
**Accept.** The fused path being 3.33× slower than persistent low rank at the probe
shape (0.8234 vs 0.2469 ms) and only ~3.2% faster than materialized generation is
correctly characterized as "a limited fusion result." Response:
- The v4-vs-materialized matched rerun (review P1 "four-arm ladder with v4") is the
  decisive experiment; the design exists (`v4_multicore`), the decisive v4-vs-v1
  benchmark (3.03× at T=4096) is done, and the missing piece is adding materialized
  and persistent arms to the same randomized-order session. We will run it.
- We will add the quality-vs-latency / quality-vs-memory frontier plot the review
  asks for, with persistent low rank, static SVD, materialized, fused v1/v4, and
  (new) fused conditional baselines on one axis set.
- If persistent low rank dominates the frontier, we will present that as the main
  empirical finding and narrow the method claim, exactly as the review prescribes.

### 3.3 §4.1 — Parameter-matched gap not closed
**Accept.** The r512-vs-r384 "parameter-matched" label is wrong (27.86% storage
delta); the r401-vs-r384 near-match (48.2 vs 48.1 MiB) is the only defensible
near-equal-budget pair, and it favors persistent (0.4363 vs 0.4465, +2.3% relative MSE
for the generated arm). The "gap closed" language in `results.tex` line 36, the
checklist item, and the closing-test narrative will be removed/replaced with:
- an explicit three-way ledger (same-rank / same-storage / same-compute) as the review
  requires, built from `parameter_bytes()` counts (elements and bytes by dtype);
- the honest statement that at equal total parameters the generated model is ~2.3%
  worse (closing-pull family) and the conditioning effect in the coherent family is
  ~0.0002 MSE — i.e., the parameter-matched gap is *not* closed by conditioning.

### 3.4 §4.2 — Cross-table reconciliation
**Accept; root cause identified.** The three run families are now mapped (see §0
table). Fixes:
- Every table gets a `run_id` binding in its caption and a machine-readable
  `results/REGISTRY.md` mapping table row → run ID → config hash → split hash →
  checkpoint hash. `VERIFIED_RESULT_RECORD.json` files already exist for all three
  families; the registry simply binds them and forbids cross-family mixing.
- Tables 10–12 will be rebuilt from `asi2_rank512_control_20260922T080042Z` alone
  (it contains all arms at all ranks). The closing-pull family remains as an
  independent replication, cited as such, not mixed in.
- The 0.0029-vs-0.0002 discrepancy resolves as family mixing: within the coherent
  family the causal−shuffled paired difference is −0.0002 (t(3)=−12.3), not −0.0029.
  The paper's magnitude claim will be corrected accordingly.

### 3.5 §4.3 — Reconstruction parity ≠ LM parity
**Accept.** One-layer fp32 reconstruction after 5000 steps cannot support "causal LM
quality" phrasing. Response:
- Rename the claim everywhere to "single-layer reconstruction parity under a frozen
  teacher protocol."
- Add the P0 complete-model experiment: predeclared early/middle/late layer
  replacement sweep on a small causal LM, causal perplexity + generation on disjoint
  corpora, cached decode (S=1), with a predeclared practical quality margin and paired
  CIs. This requires ASI2/GPU time and is scheduled as Track B item 1.
- The hidden-state extraction protocol (source corpus, split rules, normalization,
  extraction point) will be documented in the appendix and bound by split hash; the
  test-split insulation from selection will be stated as a predeclaration.

### 3.6 §4.4 (statistics) — non-inferiority framing
**Accept.** We will predeclare a practical non-inferiority margin (e.g., Δ = 0.005
relative MSE ≈ 1% of the control's MSE), report paired-difference CIs against that
margin, and downgrade "statistically indistinguishable" language to the interval-based
equivalence statement. The very large t statistics (t(3)=−514 etc.) come from
between-family mixing and tiny between-seed variance; rebuilding from single families
(§3.4) fixes both the numbers and the implausible statistics. Four seeds stay the
floor; if device time permits we extend to 8 seeds for the decisive comparisons.

### 3.7 §5.1 — No-store claim needs address/binary evidence
**Accept.** Current evidence is source-level (no explicit `DataCopy` of the core) plus
missing-op checks; the review correctly says this does not prove absence of spills,
workspace staging, or cache-mediated writes. Response plan (Track B):
- Bind the audit to the compiled artifact (hash of the .asc + build flags + CCE
  version), and add msprof/HCCL-counter evidence: attributable descriptor-store
  counts on the output/workspace address ranges, cold-cache vs warm-cache runs, and a
  positive control (materialized arm) that reliably triggers the forbidden writes.
- Until then, every "no HBM write" claim is narrowed to "no explicit global-memory
  store of the descriptor in the audited source; physical-traffic attribution pending
  binary-level counters" — the review's suggested narrower wording.
- The review's byte-level ledger (expected in/out bytes, actual global writes, DRAM
  R/W, workspace, normalization, uncertainty) will be added as an appendix table.

### 3.8 §5.2 — v4 speedup has the wrong comparison
**Accept.** v4 ratios are v4-vs-v1 (operator-level). The paper will state explicitly
that 1.13–3.03× is (a) operator-scope (generation-and-apply), not full-FFN, and (b)
vs. v1, not vs. materialized. The "two-times viability threshold" will be either
derived from a serving budget or dropped. The decisive matched four-arm rerun with v4
in-session (review P1) is scheduled; the 2.682 ms figure will not be divided by any
operator ratio.

### 3.9 §5.3 — Training gains are low-rank gains until isolated
**Accept.** The DDP benchmark is a synchronized low-rank-FFN step benchmark, not the
canonical fused operator's training path. Fixes:
- Retitle and relabel Tables 6–7 as "synchronized low-rank FFN step results."
- Add a trained persistent-low-rank arm to the same DDP benchmark (it is the missing
  control that isolates low-rank-ness from ephemeral-ness; both are low-rank here, so
  the honest statement is that 3.37–4.14× is a *low-rank* result, not a lifetime
  result).
- Correct the Table 6 caption: the optimizer update is *not* identical across arms
  (Table 7 shows 8.97 ms vs 1.0–1.3 ms); the caption will say the update is excluded
  and *why*, and point to Table 7 for the optimizer-inclusive version.
- Add convergence-to-target-quality comparisons, not only per-step time, per the
  review's requirement.

### 3.10 §6.1 — Saved bytes ≠ peak activation memory
**Accept.** Tables 19–20 report saved-for-backward bytes, not peak allocator or
complete-model memory. Fixes:
- Add the tensor-by-tensor liveness ledger the review asks for (storage IDs,
  liveness intervals, weights vs aliases vs controller activations vs workspace vs
  allocator overhead).
- Add peak allocated/reserved measurements and maximum-feasible-batch/context at
  complete-model scope.
- Add the standard activation-checkpointing-on-persistent-low-rank control; keep the
  [R5] credit and the "exact gradients ⇒ local correctness, not a new learning
  principle" framing the review demands.
- Keep (already present, strengthen): "single-FFN scoped; full-model peak memory
  remains open."

### 3.11 §6.2 — Math results are accounting identities
**Accept with the review's suggested path.** Propositions 1–5 will be retained under a
modest label ("elementary traffic/sensitivity bounds under declared assumptions"). The
identifiability claim will be narrowed to "the redesign removes one explicitly
described redundancy." For a leading-journal anchor we will add and empirically test
one substantive result — candidate: an IO lower bound for the
generate-and-consume pattern under a declared two-level memory model (UB/L2/HBM),
tested against the v1/v4 measurements (which already deviate interestingly from
roofline: 3.03× vs projected 5–7×, attributed to L2 contention — this deviation is
exactly the kind of falsifiable prediction the review asks for).

### 3.12 §7 — Deployment/routing
**Accept.** The router stays specified-but-unimplemented in this cycle; all
branch-skipping savings language is already withdrawn and will remain so. The
finite-sample framing the review gives (2995 calls for a 95% one-sided 0.001 bound
under i.i.d.) will be quoted verbatim as the certification requirement the future
implementation must meet, with the i.i.d.-violation caveat for autoregressive
dispatch.

### 3.13 §8 — Required experiments (priority order adopted verbatim)

| Priority | Experiment | Status / plan |
|---|---|---|
| P0 | Reconcile result registry + parameter budgets | **Track A — executable now** from existing VERIFIED_RESULT_RECORDs; no device time |
| P0 | Test whether conditioning adds value (equal total params + fitting compute: static/causal/constant/mean-core/constant-input controls) | Constant-core, mean-core, constant-input generators are small additions to `mwg_quality_distillation.py`'s generator registry; equal-budget variants need rank sweeps (r320–r384 generated vs r401 persistent). Requires ASI2 time; scheduled as Track B item 2 |
| P0 | Complete-model quality (layer replacement sweep, causal PPL + generation, predeclared margin) | Track B item 1; `mwg_ppl_patch_eval.py` exists as the patch-eval harness seed |
| P1 | Four-arm ladder rerun with v4, randomized order, all shapes incl. S=1 decode | v4 kernel + benchmark driver exist; add materialized + persistent arms to the session; Track B item 3 |
| P1 | Memory-boundary verification + failure-inclusive stress tests | Track B item 4 (msprof counters, positive materialized control, sequential/concurrent/multi-stream/restart matrix, failure rate reported, retries kept in-sample) |
| P1 | Conditional dispatch implementation | Deferred beyond this cycle unless Track B items 1–3 land early; claims remain withdrawn |
| P1 | Complete-model memory + training (storage-dedup ledger, peak bytes, checkpointed static controls, time-to-quality) | Track B item 5 |
| P2 | Transfer (second architecture / device family) | Deferred; scope narrowed in text meanwhile |
| P2 | Reproducible artifact (environments, provenance, raw per-run samples, traces, deterministic table generation) | `REGISTRY.md` + `make_tables.py` (deterministic table generation from VERIFIED_RESULT_RECORDs) is part of Track A; full artifact packaging continues |

### 3.14 §9 — Corrections (all accepted; each mapped to an edit)

| Review item | Fix location | Action |
|---|---|---|
| Abstract notation mismatch ($W_g$ outer product vs diagonal-core form) | `main_iclr2027.tex` abstract | Rewrite abstract projection sentence in canonical $((xU)\odot z)V$ notation with explicit shapes |
| "Causal LM quality" phrasing (pp. 9, 10, 15, 28) | `results.tex`, `discussion.tex`, `checklist.tex`, conclusion | Replace with "single-layer reconstruction parity under frozen-teacher protocol" |
| L2 vs 192 KiB UB conflation (pp. 7, 23, 25, 26) | `appendix_b.tex` fig. caption, `systems.tex`, `arch.tex` | State measured L2 capacity; separate "exceeds UB" (192 KiB, true for 2 MiB logical C) from "exceeds L2" (needs the stated L2 size); per-projection vs all-projection bytes by dtype |
| v1 description contradiction (main text tiles-at-baseM=128 vs Appendix S full-C-in-UB) | `systems.tex` §v1 root-cause + `appendix_b.tex` App. S | Reconcile to audited source: v1 *tiles* M at BASE_M=128 (kernel source `ephemeral_core_apply.asc`: `while (mm_.Iterate<true>())` over baseM-row tiles); the 2 MiB is the *logical* full-C size, while the resident UB footprint per tile is baseM×r. Both texts corrected; the serial cube→vector dependency (the actual root cause) stays |
| 32 tiles × ~2 ms ⇒ 64 ms vs 2.682 ms (p. 25) | `appendix_b.tex` App. S | Fix: the ~2 ms is the aggregated per-tile profiler-pass figure across the full call, not per-tile wall time; correct the units and per-tile estimate so the arithmetic is consistent with 2.682 ms |
| Table 6 caption "optimizer update … identical for both arms" | `appendix_b.tex` Table 6 caption | Correct: update excluded; when included (Table 7) it differs across arms (8.97 vs 1.0–1.3 ms) |
| Duplicated legacy-mode paragraphs, stale seeds (pp. 19, 27–29) | `appendix_b.tex`, `checklist.tex` | Deduplicate; update checklist seeds to 2026–2029; replace blanket [Yes] with per-item experiment bindings |
| PDF malformed-font/stream warnings | build | Rebuild from clean sources with embedded fonts (`latexmk -g`), inspect all equations/figures/tables; keep a build log in the artifact |
| Artifact language (hash ≠ correctness) | `README`/artifact docs | Distinguish source audit / binary audit / summary counters / address traces / independently reproduced; hashes bind bytes only |
| Related-work table negative entries ("no fusion", "no counters") | `related.tex` positioning table | Reword to "the cited work reports X"; mark unverified negatives as unverified |
| "Parameter-matched gap closed" claims | `results.tex` line 36, checklist, closing-test narrative | Remove until an exact-budget run exists; state the honest ±: coherent-family comparison shows conditioning ≈ 0.0002 MSE and equal-budget generated arm ~2.3% worse |

### 3.15 §10 — Questions (answers as of this response)

1. **What remains novel vs. a fused input-conditioned low-rank modulation baseline?**
   The enforcement-and-measurement method: a declared parameter-lifetime contract made
   operational (single entry point, preconditions, manifest), a source+binary audit
   protocol with positive controls, and a registry discipline (run-ID-bound tables).
   Quality or latency novelty is *not* claimed pending the P0/P1 reruns.
2. **Does any configuration improve quality at equal total parameters, or latency at
   equal quality, over trained persistent low rank?** Not currently demonstrated. In
   the coherent family, conditioning contributes ~0.0002 MSE (0.05%); at equal total
   parameters the generated arm is ~2.3% worse; at the probe shape the fused path is
   3.33× slower than persistent low rank. The v4 matched rerun will answer the latency
   half.
3. **What explains changed persistent/causal MSE values across Tables 10–12?**
   Cross-family mixing of three run IDs (§0/§3.4). All tables will be rebuilt from
   `asi2_rank512_control_20260922T080042Z` with the closing-pull family retained as a
   labeled replication.
4. **What dataset/split produce the hidden states; how is test insulated?** To be
   documented in the appendix with split hashes and the predeclaration that layer,
   rank, and checkpoint selection never touch the test split (the protocol already
   uses hash-bound disjoint splits; the documentation gap is accepted).
5. **Does v4 improve complete-FFN/decoder latency over same-run materialized at decode
   and large prefill?** Unknown until the P1 four-arm v4 rerun; the paper will say so.
6. **Which compiled-kernel writes/counters prove the descriptor cannot escape?**
   None yet at binary level; §3.7's plan (address-range attribution, positive
   materialized control, cold-cache runs) is the path. Current claim narrowed to
   source-level absence.
7. **How are unique live saved activations separated from persistent references and
   aliases in Tables 19–20?** Currently by construction (fresh tensors per pass, no
   aliasing in the audited path); the liveness ledger (§3.10) will make this explicit
   with storage IDs.
8. **Can the stability failure be reproduced and attributed without discarding failed
   runs?** Not yet. The 1000-call record stands as failed (`pass: false`,
   `final_max_abs_err: NaN`). The failure-inclusive stress matrix (§3.13 P1) is
   scheduled; the "environment-level transient" attribution is retracted.
9. **Complete-model quality/storage cost of a dense fallback?** Not measured; will be
   part of the P0 complete-model sweep design (dense-fallback residency is one of the
   arms).
10. **Router finite-sample risk bound under actual dispatch distribution?** Not
    available (router unimplemented). The review's i.i.d.-bound example is adopted as
    the certification requirement; the autoregressive-dependence caveat is accepted.

---

## 4. Concrete execution queue (what happens next, in order)

**Track A (local, no device): — COMPLETED 2026-10-10 (see §5 below)**
1. **[DONE]** Create `results/REGISTRY.md` + `scripts/make_tables.py`: deterministic
   table generation from VERIFIED_RESULT_RECORDs; forbid cross-family rows.
2. **[DONE]** Rebuild Tables 10–12 from `asi2_rank512_control_20260922T080042Z`; recompute all
   narrative numbers and paired stats from that family (numbers above are the preview).
3. **[DONE]** Apply every §3.14 text fix (abstract notation, LM-quality phrasing, L2/UB
   separation, v1 tiling reconciliation, 2 ms units fix, Table 6 caption, checklist
   seeds, dedup, related-work rewording, "gap closed" removal).
4. **[DONE]** Adopt the review's suggested conclusion as the new conclusion skeleton.
5. **[DONE]** Rebuild PDF clean; verify fonts/streams; log the build.

## 5. Track A completion record (2026-10-10)

Revisions executed in `iclr_parts/` and rebuilt into `main_iclr2027.pdf`
(31 pages, 0 undefined references):

- **§4.2 reconciliation:** new "Cross-family reconciliation" paragraph in
  `appendix_b.tex` explains that the three run families (not contradictory
  measurements) produced the previously mixed 0.4458/0.4498-style values;
  registry binding and deprecated-number marking stated in-paper; all tables
  carry the canonical run ID in their captions.
- **§4.4 statistics:** predeclared non-inferiority margin
  $\delta_{\rm NI}=0.005$ relative-MSE paragraph added before the findings;
  95% paired-difference CIs added to all six comparisons (parity r384/r401/r512,
  shuffled r384/r401/r512); r512 no-context-advantage stated plainly as a
  negative result; sign instability across retained families disclosed
  (Family 1: −0.0007/−0.0008; closing-pull: +0.0005) with an explicit
  "no directional causal-quality claim" sentence.
- **§4.3 extraction protocol:** new "Activation extraction protocol" paragraph
  documents the five source suites, 1234-record pool, seed-20260823 50/25/25
  split, NFKC/4-gram/0.82 dedup rules, split SHA-256s
  (`data/quality/manifest.json`), frozen test policy, layer-16 extraction
  point, batch limits, and the single-layer-frozen-teacher scope statement
  (no perplexity/generation claims).
- **§4.1 labeling:** checklist Q4 now says "near-equal-budget persistent
  control (persistent r401 48.2 MiB vs. causal r384 48.1 MiB)" and marks the
  r512 cross-rank comparison as explicitly not parameter-matched; the
  appendix's "rank-512 (or equal-total-parameter)" mislabel removed; the
  generated arm's Params-MiB column includes controller bytes (46.1+2.0).
- **Verified against the PDF build:** no stale 0.4458/0.4498/0.4362/0.4405/
  0.4462 claims outside the deprecated-number explanations; run ID present in
  all three table captions; margin paragraph and all six CIs render.

**Track B (needs ASI2/device time; priority order per review §8):**
1. P0 complete-model layer-replacement sweep (causal PPL + generation, predeclared
   margin, paired CIs).
2. P0 equal-total-budget conditioning test (constant-core / mean-core /
   constant-input / static controls at matched budgets and matched fitting compute).
3. P1 four-arm ladder with v4 in one randomized-order session (prefill, S=1 decode,
   variable batches) + quality-latency frontier.
4. P1 memory-boundary verification (binary-bound audit, positive materialized
   control, counters) + failure-inclusive stress matrix.
5. P1 persistent-low-rank DDP control + optimizer-inclusive rerun with
   convergence-to-quality.

**Decision gate:** if Track B items 1–3 confirm the review's expectation that
persistent low rank dominates on quality-adjusted latency at this scale, the paper's
empirical section becomes (per §3.2) "the boundary where fused ephemeral execution
beats/loses to persistent low rank," and the contribution rests on the
enforcement-measurement method — the review's second success criterion.

---

## 6. What the review got right that we had missed

For the record, three findings in this verification pass were *not* visible from the
review alone and change our internal plans:
1. The coherent run family already exists and shows the conditioning effect is
   ~10× smaller than the paper's mixed-family narrative claims — the paper's most
   positive quality sentence is an artifact of registry indiscipline, not of
   measurement.
2. The v1 "full C in UB" appendix sentence contradicts the audited kernel source
   (v1 tiles at BASE_M=128); the appendix description must be regenerated from the
   source, not from memory.
3. The Table 6 caption error ("identical for both arms") is inconsistent with the
   paper's own Table 7 — an internal contradiction the review caught that our
   compliance audit missed.

We consider the review fair, technically precise, and actionable. No rebuttal of its
facts is planned; the response is execution.
