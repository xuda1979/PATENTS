# Decisions

## D-0001 — Evidence scope

Preserve all original archives. Treat incomplete-provenance records as archived summaries, retain the failed v4 numerical gate, and make no full-model quality–latency claim. New measurements are bounded CPU software fixtures. Publication readiness remains false.

## D-0002 — Remote access and policy conflict

Read-only local recovery-path inspection found the delegated Mac shell wrapper, rclone binary, and relay configuration unavailable in this session. No browser/authentication repair, environment start, or remote job was attempted. CLAUDE.md and the operations skill name ASI2; TOOLS.md names ASI3. The initial contract’s assumption of an unambiguous ASI2 policy is replaced with an explicit unresolved target. This changes no measurement data or threshold. Remote artifact existence remains unknown.

## D-0003 — Handoff scope

Release the verified manuscript revision, source, audit and CPU evidence for author review through a GitHub branch/PR. Skip accelerator canary/training phases because no usable target runtime was established. Completion of this revision is separate from scientific submission readiness.

## D-0004 — Methodological reframing (2026-11-09)

With remote training blocked and the remaining empirical gates requiring
device access, reposition the manuscript as an **audit methodology for
conditional low-rank layers**, demonstrated on MWG-EW, with the negative
dynamic-versus-static findings as the centerpiece results. Rationale: the
methodology, matched-contrast invariants, evidence taxonomy, and retained
negative gates are complete and locally verified now; the joint
quality–latency study is not, and is blocked. Scope of this change: title,
abstract, contributions paragraph, an evidence-protocol portability note,
and the conclusion in `journal_content.tex`; title/date in
`journal_preamble.tex`/`main.tex`; README and SUBMISSION_README framing
notes. No number, table, gate verdict, or archived record was altered; the
submission-readiness flag remains false and the readiness check still
intentionally exits 2. Historical review documents were left untouched. The
venue implication (systems/benchmarking track such as MLSys or NeurIPS
D&B, or TMLR) is guidance for the author, not a submission action.

## D-0006 — Q4 verdict and claim boundary (2026-11-14)

The 2026-11-13 matched trained-model run (asi2_q4_matched_quality_latency_20261113T134959Z,
four seeds) closes the pre-declared Q4 gate with a **negative engineering verdict for the
reference realization**: the input-dependent block-Givens arm matches persistent-low-rank
quality (relative MSE 0.4444±0.0008 vs 0.4449±0.0008) and held-out perplexity (2.49±0.07 vs
2.38±0.07 percent degradation) on the same trained checkpoints, but its measured reference
(PyTorch) execution is 4.40–4.54× (mean 4.48×) the persistent latency at batch 1, seq 128,
fp16 on a single Ascend 910B2. Decision:

1. The manuscript reports this as a measured negative result (new Section 7.3), not as an
   open gap; the abstract, findings, conclusion, and limitations are updated accordingly.
2. The audit's blocking gap is rewritten from "no verified quality/latency Pareto curve from
   the same causal model and runtime" to "Q4 answered only for the reference block-Givens
   realization; the compiled tile-local execution path that could win remains unmeasured."
3. The tile-local prototype (custom_ops/block_givens_tile_apply/, Ascend-C source +
   simulator, not compiled) is retained as future work; no serving or speedup claim is made
   for the block-Givens arm.
4. submission_ready remains false: the compiled tile-local realization, constant-core and
   quantized baselines inside the Q4 design, and canonical dataset disjointness across
   seeds remain open.

Scope of the change: audit gate + two generated tables, manuscript Section 7.3 and
abstract/findings/conclusion/limitations/disclosure updates, README/SUBMISSION_README/
REVIEW_20261022 sync, loop records. No archived record was altered; the four retained raw
per-seed latency records and the 48-row summary are new artifacts, and the audit
cross-checks summary against raw at every cell.

## D-0007 — reviewer-response revision scope (2026-11-16, EV-0025)

The second-round reviewer verdict was major revision with eight findings. All
eight are addressed by local source edits only, within the contract's
constraints (no invented experiments, no remote accelerator spending, no
promotion of failed gates):

1. Error decomposition: replaced the self-contradictory "three quantities +
   a fourth" diagnostic with an explicit additive relative-error budget
   (rank loss / subspace selection / within-subspace fit) and attributed the
   token-controller row term by term. The floors table and its numbers are
   unchanged; only the reading is corrected.
2. Fresh-evidence primacy: the 2026-11 campaign is primary; archived
   2026-08/09 records are marked corroborating wherever they appear.
3. Q4 boundaries: quality = held-out MSE + patched perplexity on saved
   checkpoints (seed-level dataset disjointness unestablished, descriptive
   intervals); timing = single-layer reference (non-compiled) execution, one
   device; compiled tile-local path explicitly unmeasured.
4. Block-Givens spec: full mathematical specification added, verified against
   the run source and the recorded persistent_state_bytes (32,873,216).
5. Artifact URL + versioned pre-declaration: github.com/xuda1979/PATENTS,
   branch loop/d0004-reframing-and-v4-evidence; question-set pre-declaration
   commit 7d03947 (2026-10-22, merged 2026-10-27 as 7f169bd) predates the Q4
   runs; pre-registered thresholds quoted from the worker header.
6. Abstract: shortened; measurement chronology removed; 4.48x and 13x kept.
7. Appendix B: the 13.0 retained-storage ratio is reported with its exact
   definition and tied to the abstract's 13x; the no-memory-ratio-headline
   statement is scoped to the legacy NPU records.
8. Second architecture: pre-registered (not executed) instantiation on the
   attention output projection W_O with per-head block-diagonal modulation;
   same Q1-Q4, same thresholds, per-head floors; explicitly unmeasured.

Two stale statements contradicting the measured Q4 verdict were corrected
("absence of any validated joint quality-latency gain", "no validated
complete-model efficiency gain"), and the Q4-limitations tense was fixed
("was a pre-declared open gate"). No number, table value, gate verdict, or
archived record was altered. submission_ready remains false.
## D-0007 — Second-architecture execution at the CPU evidence class (2026-11-17)

The pre-registered W_O instantiation (D-0006 item 8, EV-0025) is executed at
its first available evidence class: CPU synthetic fixtures, same class as
Appendix B. Decision and scope:

1. The demonstration is reported as a measured result (new Section 7.4 and
   Table 11), not as a pre-registration-only item; the limitations paragraph,
   abstract, contributions, taxonomy, findings lead-in, conclusion, and
   reproducibility sections are updated. No prior number, gate verdict, or
   archived record is altered.
2. Two latent defects in the drafted script were fixed before integration:
   in-place fixture mutation through nn.Parameter storage sharing, and an
   untrained-persistent-arm contrast (training-exposure confound). The
   error-budget function now computes the actual-error attribution of
   Eq. (error-budget) with verified additivity and a checked theorem premise.
   Both defects are regression-tested (11 new tests, 115/115 total).
3. The audit gate (second_architecture_wo_gate, schema v2) enforces
   seed coverage, budget bounds on the compensated arm, contrast tightness,
   budget additivity, constant-core non-dominance, and exact Q3 identity;
   blocking_gaps now names the remaining W_O accelerator questions.
4. Claim boundary: CPU synthetic fixtures only. The pre-registered Q2 and Q4
   on W_O remain open with unmodified thresholds; no accelerator, trained
   model, dataset, or serving claim is made. submission_ready remains false.
