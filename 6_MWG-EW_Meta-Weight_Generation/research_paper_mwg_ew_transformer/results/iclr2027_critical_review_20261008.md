# ICLR 2027 critical self-review — research_paper_mwg_ew_transformer (2026-10-08)

Reviewer stance: hostile but fair area chair + 3 expert reviewers
(systems, efficiency, and one skeptical theorist). Question: would this
survive review, and if not, what is the cheapest set of honest fixes?

## Verdict

**Not acceptable in current form, but salvageable.** The paper's core virtue
— an unusually honest evidence ledger that separates measured from proposed
— is also its reviewing risk: reviewers will read the limitations list as
the review itself. The fixes below are (a) framing, (b) four verifiable
related-work gaps, (c) terminology that leaks internal project jargon,
(d) one cost-framing omission that a systems reviewer will flag as
cherry-picking. None require new device runs.

## Strengths (what to protect)

1. **The evidence-status ledger is rare and valuable.** Measured / proposed /
   withdrawn / invalid quadrants, with hashes and aborted-run artifacts
   preserved (`*_aborted0525.*`, `*_aborted0745.*`). Reviewers increasingly
   ask for exactly this; do not soften it.
2. **The four-arm ladder is a clean experimental design**: dense /
   persistent-low-rank / materialized-core / fused-no-store isolates the
   lifetime variable. The fp16-floor equivalence (1.95e-3) with a
   hash-bound audited operator is credible.
3. **Withdrawal of invalid evidence** (world-1 conditioning ablation,
   routed-savings estimates) preempts the worst reviewer attack and should
   stay prominent.
4. **The approximation result was repaired** and its retained-energy claim
   now matches the matrix norm it uses.

## Major issues (must fix)

### M1. Related work: four verifiable gaps, one un-citable claim

The related-work section covers MoE, low-rank, quantization, offloading,
speculative decoding, and FlashMHF. A systems/efficiency reviewer will
notice four missing mechanisms that are *closer to the paper's operational
claims than half the cited list*:

1. **Contextual/dynamic sparsity for LLM inference** — Deja Vu (Liu et al.,
   ICML 2023, arXiv:2310.17157) predicts and materializes only the sparse
   activated neurons per token; this is the closest thing to an "operational
   router that skips dense fetches" that actually shipped. The paper's
   unrealized router (limitation #1 in the abstract) invites exactly this
   comparison.
2. **Hot/cold weight staging** — PowerInfer (Song et al., SOSP 2024,
   arXiv:2312.12456) and LLM in a flash (Alizadeh et al., ACL 2024,
   arXiv:2312.11514) both make weight *residency* conditional on activation
   statistics. MWG-EW's lifetime contract (persist thin factors, fetch
   nothing for the core) is a strictly stronger residency claim and must be
   positioned against them.
3. **Token-level conditional compute** — Mixture-of-Depths (Raposo et al.,
   arXiv:2404.02258) allocates compute per token. The paper conditions at
   call level (whole-call vs token-fraction dispatch is already a stated
   distinction in analysis.tex) but never cites it.
4. **Kernels that fuse weight generation** — beyond FlashMHF, the
   weight-generation-inside-the-kernel idea should acknowledge that
   fused-kernel epilogues with on-chip generation exist in spirit in fast
   weight programming (already cited via schlag2021fastweights — fine), but
   the *systems* claim (no-store contract, audited) is genuinely distinct;
   say so explicitly rather than via a footnote-level clause.

**Verified metadata** (all four fetched from arXiv on 2026-10-08, see
session log): Deja Vu = ICML 2023, 11 authors (Zichang Liu, Jue Wang, Tri
Dao, ... Beidi Chen); PowerInfer = SOSP 2024 (Yixin Song, Zeyu Mi, Haotong
Xie, Haibo Chen); LLM in a flash = ACL 2024, exact title "LLM in a flash:
Efficient Large Language Model Inference with Limited Memory"; MoD =
arXiv:2404.02258, Raposo, Ritter, Richards, Lillicrap, Humphreys, Santoro.

**Do NOT add**: any "hypernetwork generates LoRA weights" citation —
searched 7 variants (HyperFormer/Hyper-LoRA/Adapt-and-Share/Phang), none
verifiable; adding an unverified citation would be worse than the gap.

### M2. "world-N" jargon leaks internal experiment names into the paper

`world-4 optimizer-inclusive synchronized-DDP` (intro.tex:109),
`world-8 dense per-launch JSON` (appendix.tex:32), `world-8 synthetic
all-reduce` (appendix_b.tex:184), `world-1 conditioning ablation`
(appendix_b.tex:706, results.tex:70). A reviewer reading "world-4" has no
way to know this means "4-process DDP world size" (it is not defined
anywhere; protocol.tex says "world size 4" once, in different words).
Fix: replace with explicit descriptors — "a four-process
(\texttt{DistributedDataParallel}) optimizer-inclusive training step",
"eight-process", "the historical (world-size-1) conditioning ablation" —
keeping at most one parenthetical world-size mention where the historical
table name must match the archived artifact name.

### M3. Arm-2 (persistent low-rank, 0.2469 ms) is the missing baseline in the abstract's cost story

The abstract reports the fused arm at parity with materialization (0.823 vs
0.851 ms, L2-resident) and the T=4096 deficit, but never states the
persistent-low-rank arm is 3.3x faster than both (0.2469 ms). A systems
reviewer's first question will be: "Why would anyone run the generated path
when the unconditioned low-rank arm costs 0.25 ms?" The correct answer
(verified against `mwg_four_arm_lifetime_benchmark.py` MasterWeights
shapes on 2026-10-08): arm 2 and arm 4 have nearly identical persistent
storage (13.5 vs 15.7 MiB incl. controller at (d,m,r)=(4096,14336,128));
the 3.3x gap is purely the per-call cost of generating and applying the
conditioned core — arms 2 vs 4 trade conditioning quality against call
latency, with no capacity difference. The paper lets the reviewer
discover this question before the answer. Fix applied in results.tex:
state the 3.3x figure with the near-identical-storage explanation, and
note arm 2 is the honest latency floor for any low-rank arm.

[Correction 2026-10-08: the original draft of this review item claimed
arm 2 "pays 117 MiB of persistent core storage" — wrong; arm 2 stores
only the thin factors, same as arms 3/4. Fixed before applying.]

### M4. The abstract's closing sentence self-rejects

[Corrected 2026-10-08: the original M4 draft claimed the 3.37×–4.14×
training speedup was missing from the abstract — wrong; it is present
(main_iclr2027.tex abstract, "a synchronized DDP training step runs
3.37×–4.14× faster than dense at 8B-scale geometry"). Only the framing
issue stands.]

"The work is a feasibility prototype with a measured mechanism result,
not a finished systems deployment" is honest but reads as a
self-rejection — reviewers anchor on it as the authors' own verdict.
Reframe as a scope statement with the same facts: evidence restricted to
one layer geometry and one device family; measured / designed-but-
unmeasured / withdrawn quadrants reported explicitly; router treated as
future work. Defensive posture without self-harm.

## Minor issues

- **m1.** Uncited bib entries: groeneveld2024olmo, qwen2025qwen25,
  shazeer2017outrageously, touvron2023llama, xai2024grok1 — all harmless
  (they were background reads), but ICLR reviewers sometimes diff the bib;
  either cite where the models are mentioned (discussion mentions
  production models generically) or drop them. Recommendation: cite
  shazeer2017outrageously in related.tex (it is the canonical sparsely-gated
  MoE predecessor and the paragraph cites only GShard/Switch/DeepSeek-V2),
  cite llama/qwen/olmo/grok1 as a single "open-weight production models"
  citation cluster in discussion.tex, or drop all five.
- **m2.** `tab:lifetimeablation` caption says "averaged over ranks" —
  fine — but the table is cited in results.tex as "design exploration
  only"; the caption itself should carry the "invalid for quality/routing
  interpretation" caveat so the table cannot be screenshot out of context.
- **m3.** Figure 1 (regime_map.pdf): caption says break-even at q≥43 (8B)
  / q≥342 (1.5B) — these numbers should match Table tab:regimecall
  exactly; spot-check after any edit (they did match on 2026-10-08 build).
- **m4.** protocol.tex says "world size 4" — after M2's fix, standardize
  on "four-process DDP" everywhere.
- **m5.** The paper says the decisive v4 rerun "is designed" (sec:systems)
  and the abstract calls v4 "unmeasured" — after the ASI2 decisive run
  completes, both spots must be updated in the same commit as the results
  doc, or the paper will contradict its own evidence ledger.

## Action plan (in order, no device runs needed)

1. Add 4 verified bib entries (Deja Vu, PowerInfer, LLM-in-a-flash, MoD)
   and a 4–6 line positioning passage in related.tex (M1).
2. Purge "world-N" jargon; explicit process-count descriptors (M2).
3. Add arm-2 cost framing sentence in results.tex + abstract clause (M3).
4. Rebalance abstract: add training speedup, reframe prototype sentence (M4).
5. m1–m4 cleanups.
6. Rebuild PDF, verify page count still ≤ 9 main body + refs/appendix,
   verify no new undefined refs (audit script run clean 2026-10-08:
   0 undefined refs, 0 missing bib keys before edits).
7. (Deferred, gated on task #2) v4 rerun results into sec:systems + abstract.
