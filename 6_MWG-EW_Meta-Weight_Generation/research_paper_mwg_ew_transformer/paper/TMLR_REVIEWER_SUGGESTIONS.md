# TMLR Suggested Reviewers (4-6)

Confidential working document for the TMLR submission.
TMLR's review form asks for suggested reviewers; these are candidates whose
published work is closest to the paper's contribution. Verify current
affiliation/availability before finalizing at submission time. Prefer
reviewers active in (a) low-rank / conditional weight generation for LLMs,
and (b) efficient LLM serving systems / weight-memory movement.

## Core reviewer suggestions

1. **Dan Alistarh** (IST Austria / Neural Magic)
   - Directly relevant: GPTQ (post-training quantization), QSGD
     (communication-efficient training), Monarch structured matrices context.
   - Can assess the low-rank-descriptor traffic accounting and whether the
     no-store contract's claims are correctly bounded.
2. **Tri Dao** (Princeton / Together AI)
   - FlashAttention (IO-aware memory movement), Monarch matrices.
   - Ideal to judge whether the fused no-store kernel's DRAM-traffic
     reasoning matches IO-aware systems standards, and the L2-resident
     parity analysis.
3. **Song Han** (MIT)
   - AWQ (activation-aware weight quantization, on-device LLM compression),
     deep gradient compression.
   - Strong on the on-device weight-memory / bandwidth framing and the
     no-write-back counter evidence.
4. **William Fedus** (Google DeepMind)
   - Switch Transformers, sparse expert models review, MoE.
   - Relevant to conditional computation / routing (the eligibility and
     branch-skip frontier) and the selective-execution framing.
5. **Yi Tay** (Google DeepMind)
   - HyperGrid Transformers (conditional FFN weights), efficient Transformers.
   - Closest prior art for the input-conditioned-weight mechanism; can test
     novelty against HyperGRID/Ouroboros/FlashMHF.
6. **Thijs Vogels / Martin Jaggi** (EPFL)
   - PowerSGD (low-rank gradient compression for distributed training).
   - Relevant to the gradient-communication / distributed-training section
     and the lifetime-contract's distributed budget framing.

## Alternative / backup candidates
- **Tim Dettmers** (Washington) — QLoRA, low-rank + quantization tradeoffs.
- **Elias Frantar** (IST Austria) — GPTQ, weight compression correctness.
- **Beidi Chen** (CMU) — structured matrices / efficient attention.
- **Samyam Rajbhandari** (Microsoft) — ZeRO-style memory optimizations,
  training-lifecycle (backward/rematerialization) memory analysis.
- **Imanol Schlag / Kazuki Irie** (Fast Weight Programmers,
  Schmidhuber line) — relevance of fast-weight / weight-generated-at-inference.

## Reviewer-mix guidance
- Ensure at least one reviewer is a *systems/IO* person (Dao, Han, Vogels)
  and at least one is an *algorithm/architecture* person (Tay, Fedus,
  Alistarh) so both halves of the contract (mechanism + quality) are
  independently checked.
- Flag honestly, in the "requested non-reviewers" field, any candidate with a
  direct prior collaboration/conflict; do not request author-affiliated
  reviewers.
