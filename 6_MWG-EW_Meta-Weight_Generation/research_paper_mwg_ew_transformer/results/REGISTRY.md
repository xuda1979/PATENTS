# Result Run Registry

**Created:** 2026-10-09 (ICLR 2027 critical-review response, Track A)
**Purpose:** Bind every quality-table row in the paper to a single verified run
family, with run ID, seeds, config, code hash, and record-file hash. No table row
may mix rows from different run families.

**Provenance rule (binding):** every aggregate, paired difference, and narrative
number derived from a family below must come from *that family alone*. If a
comparison needs two arms, both arms must exist in the same family. Rows that
would require mixing families are marked **mixed-source** and are **deprecated**
for paper use.

---

## Family 1 (canonical): `asi2_rank512_control_20260922T080042Z`

This is the **only family used for Tables 10–12** after the ICLR 2027 review. It
contains, in one code execution and one protocol, all arms the review asks to be
compared: persistent low-rank, causal generated diagonal core, shuffled-context
control, and static SVD, at ranks 384/401/512, four seeds each.

| Field | Value |
|---|---|
| Run ID | `asi2_rank512_control_20260922T080042Z` |
| Directory | `results/asi2_rank512_control_20260922/` |
| Date | 2026-09-22 |
| Seeds | 2026, 2027, 2028, 2029 (disjoint) |
| Device | Ascend 910B2 (ASI2) |
| Model / layer | Qwen2.5-1.5B-Instruct layer-16 FFN (d=1536, m=8960) |
| Steps / lr / batch | 5000 / 2e-4 / 1 (fp32) |
| Activation source | `data/quality/train.txt` vs `test.txt`, near-duplicate threshold 0.82, max 315 batches, 128 eval batches |
| Factor seed / act seed | 4242 / 1729 |
| Code md5 | `ae17e6bf2a588840c81ff4edf84638db` (matches shuffled-context family — same code, different run) |
| Record SHA-256 | `1153803d…fb3764ea` (`VERIFIED_RESULT_RECORD.json`) |
| Per-seed SHA-256 | `6283b14c…62a611a5a` (`per_seed_results.json`) |
| Arms | persistent_low_rank_{r384,r401,r512}; mwg_token_diag_core_{r384,r401,r512}; mwg_shuffled_diag_core_{r384,r401,r512}; static_svd_{r384,r401,r512}; dense_teacher |

**Aggregated results (rel-MSE mean±std, cosine mean±std, n=4):**

| Arm | rel-MSE | Cosine |
|---|---|---|
| persistent_low_rank_r384 | 0.4496±0.0014 | 0.7424±0.0009 |
| mwg_token_diag_core_r384 | 0.4489±0.0013 | 0.7429±0.0009 |
| mwg_shuffled_diag_core_r384 | 0.4491±0.0013 | 0.7428±0.0009 |
| persistent_low_rank_r401 | 0.4403±0.0014 | 0.7487±0.0009 |
| mwg_token_diag_core_r401 | 0.4395±0.0013 | 0.7492±0.0008 |
| mwg_shuffled_diag_core_r401 | 0.4397±0.0012 | 0.7490±0.0008 |
| persistent_low_rank_r512 | 0.3833±0.0012 | 0.7857±0.0007 |
| mwg_token_diag_core_r512 | 0.3820±0.0012 | 0.7865±0.0007 |
| mwg_shuffled_diag_core_r512 | 0.3820±0.0012 | 0.7866±0.0007 |
| static_svd_r384 | 0.8369±0.0017 | 0.4107±0.0018 |
| static_svd_r401 | 0.8260±0.0017 | 0.4236±0.0017 |
| static_svd_r512 | 0.7541±0.0017 | 0.5003±0.0016 |

**Paired per-seed differences (causal − control, rel-MSE):**

| Comparison | r384 | r401 | r512 |
|---|---|---|---|
| causal − shuffled | −0.00021 (t(3)=−12.31) | −0.00020 (t(3)=−10.13) | +0.00002 (t(3)=+2.50, n.s.) |
| causal − persistent | −0.00075 (t(3)=−3.94) | −0.00080 (t(3)=−3.94) | −0.00132 (t(3)=−65.94) |

**Key derived numbers (single-family):**

- Same-rank parity: causal vs persistent within ±0.0008 rel-MSE at every rank
  (causal slightly better at all ranks, −0.0006 to −0.0013).
- Context-conditioning effect (causal − shuffled): **≈0.0002 rel-MSE (≈0.05%)**
  at r384/r401; **statistically indistinguishable at r512** (+0.00002, t=+2.50).
- Capacity effect (persistent r512 vs causal r384): −0.0656 rel-MSE
  (**−14.6%**), t(3)=−514.
- Equal-budget pair within this family: persistent r401 (48.2 MiB) vs causal
  r384 (48.1 MiB) → 0.4403 vs 0.4489, **generated arm +1.95% relative MSE worse**
  (review's +2.3% figure recomputed on the coherent family: +0.0086 absolute).
- Storage model (fp32, 3 factors): 3·r·(d+m)·4B → 46.1 / 48.2 / 61.5 MiB at
  r384 / r401 / r512.

---

## Family 2 (retained, cross-check only): `asi2_shuffled_context_4seed_20260922T042246Z`

| Field | Value |
|---|---|
| Run ID | `asi2_shuffled_context_4seed_20260922T042246Z` |
| Directory | `results/asi2_shuffled_context_4seed_20260922/` |
| Date | 2026-09-22 |
| Seeds | 2026, 2027, 2028, 2029 |
| Record SHA-256 | `101b0df8…b46bea8` (`VERIFIED_RESULT_RECORD.json`) |
| Raw CSV SHA-256 | `245e0b59…7fe1411` (`raw_results.csv`) |
| Code md5 | `ae17e6bf2a588840c81ff4edf84638db` (same code as Family 1) |

Aggregates agree with Family 1 on shuffled arms (0.4491 r384 / 0.4397 r401) and
static-SVD arms, but its **causal** arms (0.4462 / 0.4365) differ from Family 1's
(0.4489 / 0.4395). The two families are distinct executions; any comparison that
takes the causal arm from one and the shuffled arm from the other is
**mixed-source and deprecated**. The paper's previous Table 11 (shuffled-context
control, 0.4462 vs 0.4491, "0.6–0.7% causal edge") was exactly such a
mixed-source comparison and has been rebuilt from Family 1 alone.

**Deprecated mixed-source numbers (do not cite):** causal-vs-shuffled r384
difference 0.0029 ("0.6%"), causal-vs-shuffled r401 difference 0.0032
("0.7%"); these mix Family 2's causal arm with Family 2's persistent arm and
Family 1's shuffled arm.

---

## Family 3 (retained, closing-test record): `asi2_causal_quality_closing_20260920T044032Z`

| Field | Value |
|---|---|
| Run ID | `asi2_causal_quality_closing_20260920T044032Z` |
| Directory | `results/asi2_causal_quality_closing_pull_20260920_4seed/` |
| Date | 2026-09-20 |
| Seeds | 2026, 2027, 2028, 2029 |
| Record SHA-256 | `adc649de…8b6030b38` (`VERIFIED_RESULT_RECORD.json`) |
| Raw CSV SHA-256 | `9c2bd1de…de159de9` (`raw_results.csv`) |

Four-seed extension of the 3-seed r384/r401 closing test; confirms same-rank
parity at both ranks. Aggregate block (verified against raw CSV, n=4):
causal r384 0.4465±0.0006, persistent r384 0.4460±0.0006, causal r401
0.4368±0.0006, persistent r401 0.4363±0.0005, persistent r512 0.3761±0.0004,
static SVD r384/r401/r512 0.8342/0.8235/0.7521.

**Internal note:** the record's `key_findings` text quotes 0.4462±0.0008 (the
earlier 3-seed figure); the aggregate block and raw CSV give 0.4465±0.0006. The
aggregate block is authoritative (recomputed from `raw_results.csv` and
matching per-seed values). Family 3 is retained as a parity confirmation and
seed-robustness cross-check; Table 10's rows are now sourced exclusively from
Family 1.

---

## Storage / lifetime-benchmark records (unchanged by this response)

These families were not part of the quality-table rebuild and are listed for
completeness only:

- `results/ASI2_v4_latency/` — v1→v4 kernel latency ladder (Table 6/7 basis;
  optimizer-update mislabeling corrected separately, see response §3.9).
- `results/asi2_ddp_train_20260917T012017Z/` — DDP low-rank FFN step benchmark
  (Tables 6–7; relabeled as synchronized low-rank FFN step results).
- `results/ASI1_*` — ASI1-era single-seed records; superseded by the ASI2
  4-seed families above for all quality claims.

---

## Enforcement

`scripts/make_tables.py` reads **only** the families above and refuses to emit a
table whose rows draw on more than one family. Table generation writes each
row's run ID into the emitted caption so the binding is visible in the PDF.
Regenerate all quality tables with:

```
python3 scripts/make_tables.py --check   # verify records against registry hashes
python3 scripts/make_tables.py            # emit paper/generated_tables/*.tex
```
