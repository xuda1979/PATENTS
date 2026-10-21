# External critical review — response plan (2026-10-09)

Source: `Ephemeral_Low_Rank_Cores_Critical_Review.docx` (review date 9 Oct 2026),
saved verbatim as `results/external_critical_review_20261009.md`.
Manuscript reviewed: `main_iclr2027(1).pdf` (29 pages, ICLR 2027 submission).

Overall recommendation: **reject in current form, resubmit after substantial new
experiments.** The review does not allege fabrication; it says the evidence does
not yet support the claims, and cross-table inconsistencies prevent coherent
interpretation.

## What the review credits (preserve these)

- The parameter-lifetime contract and descriptor/factor/training-rematerialization
  separation as a useful execution contract.
- Prefix and batch invariance tests.
- The disclosure-and-withdrawal audit trail (kept as a concise audit appendix).
- The materialized-vs-fused matched profiling design with source+binary fingerprints.
- The unfavorable controls, read as informative (rank/training dominate conditioning).

## P0 items (must land before resubmission)

| # | Review demand | Status 2026-10-09 | Next action |
|---|---|---|---|
| P0-1 | Result registry: every table/narrative value maps to an exact run; same-rank and equal-total-budget results correctly labeled; reconcile the four flagged MSE discrepancies (below) | **OPEN — in progress locally** | Trace each flagged value to its source JSON/log in `results/`; document run IDs, configs, split hashes, seeds; produce one registry file that regenerates Tables 10–12 numbers |
| P0-2 | Equal-total-parameter, equal-fitting-compute comparison: static trained factors vs constant cores vs causal cores vs shuffled cores on one frozen held-out test set | **OPEN** | Check coverage of existing scripts (`mwg_random_perturbation_control.py`, `launch_ASI2_shuffled_context_control.sh`, `launch_ASI2_rank512_control.sh`, four-arm lifetime scripts); design the missing arms; run on ASI3 |
| P0-3 | Complete-model quality: predeclared layer replacement sweep, perplexity + generation tasks, paired intervals vs a practical quality margin | **OPEN** | Requires ASI3 device time; reuse `mwg_ppl_patch_eval.py`, `mwg_mmlu_acc_eval.py`, `mwg_humaneval_pass1_eval.py` under a predeclared sweep |

### The four flagged discrepancies (P0-1 core)

| Value | Table A | Table B | Reviewer demand |
|---|---|---|---|
| Persistent r384 MSE | 0.4362 (Table 10 discussion) | 0.4405 (Table 11) | Explain which persistent control pairs with each causal model |
| Persistent r512 MSE | 0.376 (Table 10) | 0.3833 (Table 12) | Report fresh-fit vs changed-evaluation |
| Generated r384 MSE | 0.4462 (Tables 10/11 discussion) | 0.4489 (Table 12 cross-rank) | Bind each comparison to its own paired run IDs |
| Causal-vs-shuffled r384 diff | 0.0029 (Table 11 discussion) | ~0.0002 (Table 12 discussion) | Reconcile under the stated identical protocol |

Plus: generated r384 = 48.1 MiB vs persistent r401 = 48.2 MiB — reviewer accepts
these are nearly equal budget, but demands the ~2.29% relative-MSE gap be stated
as the honest head-to-head, and every comparison be bound to paired run IDs.

## P1 items

| # | Review demand | Status 2026-10-09 |
|---|---|---|
| P1-1 | Four-arm ladder rerun including v4, same randomized-order session, all shapes: absolute latency, paired CIs, persistent storage, peak scratch/workspace, launch counts, physical traffic; cached decode S=1, variable batches, continuous batching; comparable optimization/caching/dtype/workspace for every arm | Partially covered: v4-vs-v1 same-session decisive run done on ASI2 2026-10-08 (1.13×–3.03×, bit-identical outputs); the four-arm v4-inclusive ladder and serving-shape (S=1 decode, continuous batching) measurements remain open |
| P1-2 | Memory boundary + stability verification: compiled-artifact audit, attributable descriptor writes, positive materialized control, failure-inclusive sequential and concurrent stress; tail-risk certification (e.g., ≥2995 independent selected calls for a 0.001 one-sided 95% bound) | Open. Known open item: 1000-call stability check NaN at T=4096 (environment-transient family per diag9v2), plus UB risk at r≥256 |

## P2 items

- Cross-model/cross-device transfer (another architecture or FFN shape; second
  device family, else narrow scope).
- Public artifact: immutable environments, provenance, raw per-run samples,
  profiler traces, failure logs, deterministic table-generation commands.

## Section 9 corrections (wording/consistency, locally actionable now)

1. Abstract `Wg` outer-product notation does not match Equations 1/3/4 diagonal-core
   convention — unify shapes and one projection convention for V.
2. Claim-wording softening (mechanism vs application distinction throughout).
3. Related-work table: qualify unverified negative entries (absence in a brief
   comparison ≠ absence in the method).
4. Identifiability: replace "identifiable" with "removes one explicitly described
   redundancy" (diagonal rescaling argument from the review).
5. Saved-tensor bytes ≠ peak activation memory: reconcile Tables 19/20 claims with
   the comparable-peak observation; stop promoting to "order-of-magnitude relief
   of dominant training activation pressure".
6. Tail-risk: state iid assumptions and certify the actual dispatch distribution
   before any 0.001-style bound.
7. Reviewer's suggested replacement conclusion — adopt a version of it.

## Decisive success criterion (reviewer's words)

A reproducible quality-adjusted advantage over a strong persistent low-rank
implementation, **or** a broadly useful enforcement-and-measurement method that
explains when transient operands improve real systems. Speedup magnitude is not
prescribed; it depends on workload, quality budget, and complete serving cost.

## Execution order

1. P0-1 registry (local, no device) — running now.
2. Section 9 corrections in `paper/iclr_parts/` (local, no device) after registry
   facts are pinned.
3. P0-2 equal-budget experiment design + P1-1 four-arm ladder harness
   (device-gated; ASI3 for new training, ASI2 historical only).
4. P0-3 complete-model quality sweep (device-gated, ASI3).
5. P1-2 stress/stability + tail-risk certification (device-gated).


## Progress record — 2026-10-13 session

Section-9 corrections applied to all three manuscripts (main.tex, tmlr/main_tmlr.tex,
iclr_parts/* -> main_iclr2027.tex), all rebuilt clean (0 undefined references):

1. Identifiability overclaim (review 4.5 / section-9 item 4): "three identifiable token-local
   diagonal cores" -> "three token-local diagonal cores ... removing one explicitly
   described redundancy"; added "Scope of the claim" paragraph after the paired-scale
   Proposition in all 3 papers stating the U/V invertible-diagonal-rescaling
   non-identifiability and disclaiming full factor identifiability.
2. Abstract notation (section-9 item 1, main.tex only): replaced mismatched
   "W_g outer product W_g U_p V_p^T" with the canonical diagonal-core
   convention P(x;U_p,V_p,z)=((x U_p) .* z) V_p with declared shapes; added
   "(a rank effect, not a no-store effect)" to the DDP sentence. (TMLR and ICLR
   abstracts already used the canonical notation.)
3. Saved-tensor vs peak-memory (review 6.1): "relaxes the dominant activation-capacity
   pressure ... by one to two orders of magnitude" -> scoped statement: saved-for-backward
   accounting reduction of 24.5x-71.8x; explicit "not a measured peak-memory
   reduction; peak allocator comparable at these single-FFN shapes; complete-Transformer
   peak memory not measured" in all 3 papers (main.tex x1, appendix_b x1, tmlr x2).
4. Tail-risk sampling assumptions (review 7 / section-9 item 6): added "Sampling assumptions
   for tail-risk certification" paragraph after Definition 3 in all 3 papers (i.i.d.
   requirement, invalidation under correlation/shift/adaptivity, no numeric
   failure-probability claim made).
5. Memory-hierarchy L2 vs UB (section-9 item 5): removed unqualified "2 MiB L2 capacity"
   statements (main.tex ~3403, tmlr ~3423) and unqualified "exceeds L2" claims
   (main.tex ~1136/~1262); all now distinguish 192 KiB per-core UB from L2 (capacity
   not separately measured; UB overflow is not L2 overflow). Fixed dangling
   app:counters ref in main.tex -> sec:systems.
6. Verified already-correct: v1 tiling reconciliation and 32-tile/2-ms timing
   arithmetic (appendix_b.tex already carries both corrections); Table 19 caption
   (4 configs x 3 seeds = 12 trials, matches asi3_training_lifecycle_20260909 JSON);
   checklist seed statements (2026-2029 with retained 3-seed runs labeled).

Remaining open after this session: P0-2 equal-budget arm design (device-gated),
P0-3 complete-model quality (device-gated), P1-1 four-arm ladder rerun (device-gated),
P1-2 stress/tail-risk certification (device-gated), P2 transfer/artifact items.
