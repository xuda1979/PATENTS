# Session Change Ledger — 2026-10-10 (external-review PDF-integrity fixes)

Scope: address the two PDF-integrity complaints from the external review of
the ICLR 2027 submission (Figure 4 legend overlap; Table 19 footnote
crowding), verified programmatically from the built PDFs, plus one latent
figure defect found during the audit.

## Figure 4 (`fig:op_decomp`) — legend/annotation collision (review complaint, confirmed)

Root cause: in `make_paper_figures.py:op_decomp()` the legend
(`loc="lower right"`, frameless) and the two-line "Epilogue bottleneck"
annotation (anchored lower-right at axes fraction (0.97, 0.06) with an
opaque white bbox) shared the same corner. Glyph-metric extraction from the
embedded DejaVu subset (pypdf, per-glyph /Widths accumulation with TJ
kerning) measured 77.2 pt of x-overlap between "arm 3 (materialized)" and
the annotation's first line and 51.2 pt between "arm 4 (fused)" and the
second line, at baseline deltas of 0.9/1.9 pt — a genuine text-on-text
collision, not a near miss.

Fix:
- Legend moved to `loc="center right"`: the mid-height rows (SiLU 2.75 ms,
  Cast 1.51 ms on the 0-25 ms axis; bars end at x <= 72.4 pt) leave the
  right half bar-free; the legend block spans y 97-109 with >70 pt clearance
  to any bar.
- Annotation stays lower-right next to the sub-1-ms rows (Muls 0.42 ms,
  Tanh 0.57 ms; bars end at x <= 57.5 pt), >50 pt clearance.
- Post-fix glyph-metric re-check on the regenerated PDF: 0 collisions.
- Both figure copies regenerated and hash-identical
  (`figs/op_decomp.pdf`, `tmlr/figs/op_decomp.pdf`, sha1
  3a6937049a701753edef579a630c32a57b1a9173).

## Figure 4 — dead `Adds` row (latent defect found during the audit)

The committed figure had a ninth y-label "Adds" with zero bars in both
arms: the order list carried `("aclnnAdds", "Adds")`, but `aclnnAdds` is
absent from `full_metrics.json`'s per-pass top-N aggregation (it exists
only in `hw_counters.json`: 138 calls / 0.40 ms materialized, 3 calls /
0.013 ms fused — below the top-N cut). The row also mismatches the paper's
`tab:opdecomp`, which has exactly 8 op rows. Dropped the entry; the
regenerated figure has 8 rows matching the table.

## Table 19 (`tab:lifecycle`) — footnote crowding (review complaint, confirmed)

Root cause: the tabular was followed by `\\[-1mm]` (negative vertical pull)
and an inline `{\footnotesize ...}` footnote whose second sentence
duplicated the caption's gradient-equality sentence, all inside
`\begin{table}[h]` after a 10-line caption — the footnote sat tight against
the `\bottomrule`.

Fix (ICLR `iclr_parts/appendix_b.tex` + TMLR `tmlr/main_tmlr.tex`, same
edit): adopted the layout already used by `main.tex`'s `tab:lifecycle` —
a dedicated `$B,S$` column (values 2,64 / 4,128 / 2,64 / 2,64) instead of
the "row 2 uses (4,128)" footnote, the cramped footnote removed, and one
caption sentence added ("Column $B,S$ is the batch and sequence length;
all configs use (2,64) except the 146.98-MiB row at (4,128)"). Table 20
(`tab:lifecycle-depth`) audited: already clean (caption self-contained, no
footnote, all rows at B=2,S=64 per its caption).

## Table 14 (`tab:positioning`) — latent 4.5 pt overfull box

The only remaining Overfull hbox (4.53 pt, lines 635-646 of
`appendix_b.tex`) pre-dated this session but was fixed while auditing
layout: p-column widths 0.13/0.17/0.19 linewidth reduced to
0.12/0.16/0.18 to give the three `c` columns room for their headers.

## Build verified

- ICLR (`main_iclr2027.tex`): 29 pages, 0 undefined references/citations,
  0 overfull boxes, 0 LaTeX errors; labels `tab:lifecycle` (19),
  `tab:lifecycle-depth` (20) unchanged; figure 4 re-verified inside the
  built PDF (legend y 108.9/97.7 vs annotation y 56.6/48.2 — clear
  separation).
- TMLR (`tmlr/main_tmlr.tex`): 30 pages, 0 undefined, 0 overfull.

## Files changed

- `paper/make_paper_figures.py` (legend relocation, dead row removal)
- `paper/figs/op_decomp.pdf`, `paper/tmlr/figs/op_decomp.pdf` (regenerated)
- `paper/iclr_parts/appendix_b.tex` (Table 19 layout, Table 14 widths)
- `paper/tmlr/main_tmlr.tex` (Table 19 layout)
