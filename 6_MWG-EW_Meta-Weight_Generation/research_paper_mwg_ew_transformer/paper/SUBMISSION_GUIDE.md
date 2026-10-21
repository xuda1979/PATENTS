# Submission Guide — "Ephemeral Meta-Weights: Turning Transformer FFN Parameters into Runtime-Generated Operands"

**Prepared:** 2026-07-16
**Status:** Paper is built (`main.pdf`, 27 pages, 11pt article). Reviewer pass W1–W10 addressed per `REVIEW.md`.

---

## 1. Venue recommendation

### 1.1 Primary recommendation — **ICLR 2027**

**Why ICLR is the best fit**

| Factor | Fit |
|---|---|
| Conceptual framing ("parameter lifetime" as a new axis) | Strong — ICLR rewards conceptually novel framings |
| Algorithmic contribution (basis-bank generator + benefit-supervised router) | Strong — falls naturally into ICLR's "new methods" track |
| Selective/routing contribution | Strong — aligns with ICLR's interest in conditional computation |
| Honest scope (some claims are "implementation targets") | Acceptable — ICLR accepts scoped contributions if honestly framed |
| Systems content (8-accelerator benchmark) | Secondary — ICLR is method-first, systems evidence supports |
| Page count (27 pages single-column) | Fits ICLR's 9-page main + unlimited appendix convention after reformatting |

**Timeline** (assumed based on prior-year cadence — verify on `iclr.cc` when 2027 dates are posted):
- Abstract registration deadline: ~early September 2026
- Full paper deadline: ~late September 2026
- Reviews released: ~mid-November 2026
- Author rebuttal: ~late November 2026
- Decisions: ~late January 2027
- Conference: ~April 2027

**Verdict:** ICLR 2027 is the closest realistic top-tier conference deadline. The paper's conceptual novelty (parameter lifetime), selective execution framing, and methodological breadth are a strong match for ICLR's preferences.

### 1.2 Secondary recommendation — **TMLR** (Transactions on Machine Learning Research)

**Why TMLR as parallel/backup**

- Rolling submission — no deadline pressure; can submit any time.
- Reviews are on the "correctness + usefulness" criterion rather than SOTA-headline chasing. The paper's honest scoping (no decode-latency claim, single-layer quality anchor) is well-aligned with TMLR's review form, which explicitly asks whether claims are adequately supported rather than whether they are SOTA.
- TMLR is ISI-indexed and widely respected; publications count as journal publications.
- Allowed to submit to TMLR while a conference version is under review? **No** — TMLR policy forbids double submission to other venues. Pick one.

**Two reasonable paths**

- **Path A (conference-first):** Target ICLR 2027 (Sept 2026). If rejected, fall back to TMLR with revisions informed by ICLR reviews.
- **Path B (journal-first):** Submit to TMLR now (July–Aug 2026). Reviews in ~2–3 months. Decision by Oct–Nov 2026. This gives a publication decision before ICLR 2027 rebuttal phase even begins.

**Recommendation:** Path A if you want conference prestige and are willing to wait until Jan 2027 for a decision. Path B if you want a definitive answer faster and value journal format.

### 1.3 Tertiary options (not recommended as primary)

| Venue | Deadline | Fit | Note |
|---|---|---|---|
| NeurIPS 2026 | PASSED (May 2026) | — | Next opportunity is NeurIPS 2027 (May 2027) |
| ICML 2026 | PASSED (Jan 2026) | — | Next opportunity is ICML 2027 (Jan 2027) |
| MLSys 2027 | ~Oct 2026 | Strong systems fit | Excellent secondary target if ICLR rejects — MLSys 2027 deadline is ~2 weeks after ICLR 2027 deadline |
| AAAI 2027 | Abstract ~Aug 2026 | Moderate | Short paper format less ideal for 21 tables; proceedings deadline pressure |
| EMNLP 2026 | PASSED | Weak | Method is not NLP-task-focused |
| ACL 2027 | ~Jan 2027 | Weak | Same reason as EMNLP |
| NeurIPS 2026 workshops | ~Sept 2026 | Strong workshop fit | Workshop on Efficient ML or Low-Bit LLMs would welcome this work; non-archival unless combined with arXiv |
| COLM 2027 | TBD (April 2027 likely) | Strong fit | Conference on Language Modeling; matches the LLM-efficiency framing |

### 1.4 Final venue ranking

1. **ICLR 2027** — primary target (Sept 2026 deadline, ~2 months away)
2. **MLSys 2027** — secondary target (Oct 2026 deadline, ~3 months away; strong systems fit)
3. **TMLR** — parallel option if you prefer journal format / rolling review

---

## 2. Pre-submission checklist (submission-ready)

The paper is already built and reviewer-revised. Before submitting to ICLR 2027 or TMLR, complete these items:

### 2.1 Template conversion

**For ICLR 2027**
- Download `iclr2027_conference.sty` and `iclr2027_conference.bst` from `https://iclr.cc/Conferences/2027/CallForPapers` (URL will go live when 2027 dates are announced; meanwhile use the 2026 template as a placeholder)
- Replace `\documentclass[11pt]{article}` with `\documentclass{iclr2027_conference,tvt}`
- Add required sections: abstract (already present), checklist (ICLR requires a reproducibility checklist)
- Move current 1-inch margin + article formatting into ICLR's mandated format (ICLR is double-column? **No** — ICLR is single-column 11pt, similar to current)
- Length: ICLR 2026 was 9 pages main text + unlimited references/appendix. Current 27 pages of single-column 11pt article format will need to be split into ~9 pages main + appendix.

**For TMLR**
- Download `tmlr.cls` from `https://www.jmlr.org/tmlr/author-guide.html`
- Replace document class with `\documentclass{tmlr}`
- TMLR allows arbitrary length (no page limit) — current 27-page format is fine
- TMLR requires open-access arXiv preprint and code release commitment

**For MLSys 2027**
- Use the MLSys template from `https://mlsys.org/Conferences/2027/`
- MLSys is 12 pages + references; current content will need trimming
- Strong fit for the systems benchmark content

### 2.2 Mandatory additions for ICLR 2027

ICLR requires a **Reproducibility Statement** and a **Broader Impact** statement. Add these before the bibliography.

ICLR also requires the **Paper Checklist** (40+ yes/no questions) at the end of the paper. This is mandatory and desk-reject will occur if missing.

### 2.3 Mandatory additions for TMLR

TMLR requires:
- An explicit statement of contributions
- A code/data availability statement
- Disclosure of any use of LLM assistants for writing

### 2.4 Author anonymity

For ICLR 2027 (double-blind): currently set as `Anonymous Authors` — correct. Ensure no author-identifying information in:
- PDF metadata (run `exiftool -all= main.pdf` before submission)
- Code repository if linked (must be anonymized)
- Acknowledgments section (remove for anonymous version)

For TMLR (single-blind): authors should be filled in.

### 2.5 Figure/table tightening

Per `REVIEW.md` W7 — there's a 157.9pt overfull hbox at lines 1298–1318 (tighter-eligibility Pareto paragraph). This should be fixed before camera-ready. For initial submission, ICLR is tolerant, but TMLR desk-edit will flag it.

### 2.6 Citation hygiene

29 references is on the low side for a 27-page paper. ICLR reviewers typically expect 40–60. Consider adding:
- Additional hypernetwork / weight-generation citations (Ha et al. extended follow-ups)
- More low-rank compression citations (TensorGPT, SliceGPT, Chain-of-LoRA)
- Distributed training communication citations (ZeroQuant, FireIter, etc.)

### 2.7 Compile clean

```bash
cd /Users/daxu/PATENTS/6_MWG-EW_Meta-Weight_Generation/research_paper_mwg_ew_transformer/paper
pdflatex main && bibtex main && pdflatex main && pdflatex main
```

The current `main.pdf` builds clean (27 pages, 380 KB). Verify before submission.

---

## 3. Submission steps — ICLR 2027 (recommended primary)

### Step 1 — Prepare submission package (T-2 weeks, ~early September 2026)

1. Download ICLR 2027 LaTeX template when available. Until then, use ICLR 2026 template from `https://github.com/ICLR/Master-Template/`.
2. Create a new file `main_iclr2027.tex` based on the template.
3. Port content from `main.tex` into the ICLR template, preserving:
   - Abstract (trim to ~250 words if ICLR requires)
   - All 21 tables (move larger tables to appendix)
   - The single TikZ figure (`fig:lifecycle`)
   - All math blocks (definitions, propositions, proofs)
4. Add ICLR-mandatory sections:
   - Reproducibility Statement
   - Broader Impact
   - Paper Checklist (40+ items)
5. Move proofs and extended tables to appendix.
6. Trim main text to 9 pages (ICLR limit). With 21 tables this is tight — most tables will move to appendix.

### Step 2 — Anonymize (T-1 week)

1. Replace author block with `Anonymous Author(s)`.
2. Anonymize code repository links in the text.
3. Run `exiftool -all= main.pdf` to strip PDF metadata.
4. Check that acknowledgments are removed for the anonymous version.
5. Verify no file paths in figures or tables leak author identity.

### Step 3 — Register abstract (T-1 week, ~early Sept 2026)

1. Create account at `https://cmt3.research.microsoft.com/ICLR2027/` (URL will go live when submissions open).
2. Register abstract by the abstract deadline (typically ~1 week before full paper deadline).
3. Pay attention to subject area selection — recommend:
   - Primary: "Deep Learning / Architectures"
   - Secondary: "Optimization / Training Methods"
   - Tertiary: "Systems / Infrastructure"

### Step 4 — Submit full paper (deadline ~late Sept 2026)

1. Upload `main.pdf` (anonymized, max 9 pages main + unlimited appendix).
2. Upload supplementary material (code archive, optional video).
3. Upload `main.tex` source as a `.zip` (required for ICLR).
4. Confirm subject areas.
5. Confirm reviewers can access supplementary (set to visible).
6. Submit.

### Step 5 — During review (Nov 2026 – Jan 2027)

1. Mid-Nov 2026: reviews released. Read all reviews carefully.
2. Late Nov 2026: author rebuttal period (typically 7 days). Prepare a concise rebuttal addressing each reviewer concern.
3. Late Jan 2027: decisions released.

### Step 6 — If accepted

1. Camera-ready deadline typically ~6 weeks after decision.
2. De-anonymize.
3. Add acknowledgments.
4. Prepare code release (ICLR strongly encourages public artifacts).
5. Upload final version.

### Step 7 — If rejected

1. Read reviewer feedback carefully.
2. Address each concern.
3. Submit revised version to:
   - MLSys 2027 (Oct 2026 deadline — likely too soon if ICLR decisions are Jan 2027)
   - TMLR (rolling — best fallback)
   - ICML 2027 (Jan 2027 deadline — good timing)
   - NeurIPS 2027 (May 2027 deadline)

---

## 4. Submission steps — TMLR (recommended journal path)

### Step 1 — Prepare TMLR submission (anytime)

1. Download TMLR template from `https://www.jmlr.org/tmlr/author-guide.html`.
2. Port `main.tex` content into `tmlr.cls`. TMLR has no page limit, so current 27-page structure is fine.
3. Fill in real author names (TMLR is single-blind).
4. Add TMLR-mandatory sections:
   - Contribution Statement
   - Code and Data Availability (already implicit in your reproducibility commitment, formalize it)
   - LLM Use Disclosure (if applicable)
5. Prepare an arXiv preprint — TMLR requires simultaneous arXiv posting.

### Step 2 — Submit to TMLR

1. Create account at `https://jmlr.org/tmlr/submit.html`.
2. Upload manuscript PDF + source `.zip` + arXiv preprint ID.
3. Suggest 4–6 reviewers (TMLR asks for reviewer suggestions).
4. Submit.

### Step 3 — Review timeline

- Reviews typically take 2–3 months.
- TMLR has one revision round; if reviews are "minor revisions" you'll get ~1 month to revise.
- Final decision typically 3–4 months from submission.

---

## 5. Concrete next actions (this week)

1. **Decide path A (ICLR 2027) vs. Path B (TMLR).** Given today is July 16, 2026:
   - Path A gives you ~2 months to reformat into the 9-page ICLR template, which is tight given 21 tables.
   - Path B lets you submit in ~2 weeks with no page-limit pressure.

2. **If Path A (ICLR 2027):**
   - Download the ICLR 2026 template now as a placeholder.
   - Create `main_iclr2027.tex` and begin porting content.
   - Plan appendix structure: most of the 21 tables will need to move there.
   - Draft the Reproducibility Statement and Paper Checklist (these take time).

3. **If Path B (TMLR):**
   - Download `tmlr.cls` today.
   - Create `main_tmlr.tex`.
   - Fill in author names.
   - Prepare arXiv submission in parallel.

4. **Either path:**
   - Fix the 157.9pt overfull hbox at lines 1298–1318.
   - Add 10–15 more references (currently 29, target 40+).
   - Verify the PDF compiles clean from a fresh `pdflatex && bibtex && pdflatex && pdflatex` cycle.

5. **Create arXiv preprint** (recommended for both paths):
   - Title: "Ephemeral Meta-Weights: Turning Transformer FFN Parameters into Runtime-Generated Operands"
   - Primary category: `cs.LG` (Machine Learning)
   - Secondary category: `cs.DC` (Distributed Computing) or `cs.AR` (Hardware Architecture)
   - ArXiv can be updated, so posting a v1 now establishes priority.

---

## 6. Quick-reference timeline

| Date | Action (Path A — ICLR 2027) | Action (Path B — TMLR) |
|---|---|---|
| 2026-07-16 (today) | Decide; download ICLR 2026 template as placeholder | Decide; download TMLR template |
| 2026-07-30 | Begin porting to ICLR template; draft Paper Checklist | Port to TMLR template; fill in authors |
| 2026-08-15 | Main text trimmed to 9 pages; appendix reorganized | Internal review; prepare arXiv preprint |
| 2026-08-31 | Anonymize; compile final; post arXiv preprint | Submit to TMLR; post arXiv |
| 2026-09-15 | ICLR abstract registration (estimated) | TMLR review begins |
| 2026-09-30 | ICLR full paper deadline (estimated) | (Under review) |
| 2026-11-15 | ICLR reviews released | TMLR initial reviews (est.) |
| 2026-11-30 | ICLR rebuttal period | TMLR revision (if needed) |
| 2027-01-31 | ICLR decisions | TMLR final decision (est.) |

---

## 7. Risk register

| Risk | Mitigation |
|---|---|
| ICLR 2027 deadline slips or moves | Have TMLR as fallback |
| Paper rejected on "not enough SOTA wins" (the honest scoping) | TMLR explicitly accepts scoped, well-supported claims |
| 21 tables don't fit ICLR 9-page limit | Move 15+ tables to appendix; main text shows 5–6 key tables |
| Reviewers ask for fused-kernel decode-latency results (a known future-work item) | Rebuttal points to the explicit scope statement; offer to add during camera-ready |
| Code release required but code is not yet public | ICLR allows "code available upon request" during review; commit to public release at camera-ready |
| Simultaneous arXiv posting reveals author identity to ICLR reviewers | Wait to post arXiv until after ICLR submission, or post anonymously to arXiv under the anonymous submission option |

---

## 8. Files in the submission package

The submission-ready package for either venue should contain:

- `main.pdf` — compiled paper (anonymized for ICLR, named for TMLR)
- `main.tex` — LaTeX source
- `refs.bib` — bibliography
- `figures/` — any external figures (currently the single TikZ figure is inline in `main.tex`, so this is empty)
- `code.zip` — anonymized code release (optional at submission, required at camera-ready)
- `supplementary.pdf` — additional experimental details, proofs, tables (optional)
- `checklist.md` or `checklist.pdf` — ICLR Paper Checklist (ICLR only)
- `reproducibility.md` — Reproducibility Statement (ICLR only)
- `broader_impact.md` — Broader Impact Statement (ICLR only)

---

## 9. Final decision recommendation

**Go with Path A: ICLR 2027**, because:

1. The paper's conceptual framing ("parameter lifetime as an architectural variable") is exactly the kind of contribution ICLR rewards.
2. The selective execution / routing contribution aligns with current ICLR interests.
3. Conference prestige for a junior researcher's first paper in this area is valuable.
4. The 2-month runway is tight but sufficient if you start porting to the ICLR template this week.
5. If rejected, you have TMLR, ICML 2027, and NeurIPS 2027 as natural fallbacks with reviewer feedback in hand.

**Switch to Path B: TMLR** if any of the following are true:
- You need a publication decision before January 2027 (e.g., for graduation or job market).
- You prefer the journal format with no page limit (the 21 tables fit naturally).
- You want to avoid the ICLR 9-page compression exercise.
- You value TMLR's "correctness-focused" review over ICLR's "novelty-focused" review.

