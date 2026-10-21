# Causal-Quality Run: Operator Runbook

**What this unlocks:** the decisive experiment that upgrades the paper from
"mechanism verified, net quality open" to "mechanism verified **and**
measured causal multi-seed quality" — the difference between a strong
feasibility/workshop paper and a complete top-journal (TMLR) claim.

## Status (2026-09-04): RUN COMPLETE, RESULT INTEGRATED

- **The causal-quality run completed and fully validated.**
  `asi2_causal_quality_20260903T073816Z` ran on **4 Ascend 910B2 NPUs**, 3
  seeds (2026/2027/2028), 5000 steps each, fp32, layer-16 Qwen2.5-1.5B FFN
  distillation over frozen, hash-bound, near-duplicate-free disjoint splits.
- **All launcher gates passed:** the dense-teacher control is exact
  (relative-MSE 0, cosine 1), reports carry `evidence_mode=true` +
  `env_label=ASI2`, disjoint-split provenance is recorded, and every
  checkpoint/report fingerprint is verified. Pulled reports:
  `results/asi2_causal_quality_pull/*.json`; verified summary:
  `results/causal_quality_summary.json` (`complete: true`).
- **The result is an honest boundary (not a positive claim).** The generated
  diagonal core reaches **same-rank parity** with a trained persistent r384
  factor (rel-MSE 0.446±0.001 vs 0.446±0.001; cosine 0.746) and is clearly
  superior to static SVD (0.446 vs 0.834 at r384), but the **parameter-matched
  persistent r401 control retains a marginal (~2.3%) advantage** (0.4359 vs
  0.4459). Per the predeclared protocol this is recorded honestly in the
  Discussion of all three vehicles (full `main.tex`, `tmlr/`, ICLR 2027)
  rather than claimed as non-inferiority.
- **No further login/collection is required for this run.** The results are
  already pulled and integrated. See "What the results feed into the paper"
  below for where the numbers appear.

## If you need to re-verify or re-collect the completed run

To re-pull the already-completed reports and regenerate the summary/table rows:

```bash
bash scripts/launch_ASI2_causal_quality_oneshot.sh --collect
python3 scripts/ingest_causal_quality_results.py --pull-dir results/asi2_causal_quality_pull
```

(Only needed if the local `results/asi2_causal_quality_pull/` is accidentally
removed; the reports are already mirrored under the run's remote output dir.)

## Quick check: is it authenticated?

```bash
curl -s http://127.0.0.1:19004/health | python3 -c "import sys,json;d=json.load(sys.stdin);print('ready=',d.get('ready'))"
```
`ready:true` = good to launch.

## What the one-shot does

1. **Imports the S3 remote** on ASI2 (`iner-aihuanxin`) if absent.
2. **Syncs the frozen code** from S3 to `/vllm-workspace/mwg-ew-transformer-research`
   (mwg_quality_distillation.py, audit_quality_threeway_split.py,
   launch_ASI2_causal_quality_detached.sh, and the frozen
   `data/quality/{train,dev,test}.txt` + `manifest.json`).
3. **Preflights** the launcher (`--check` mode) to validate the frozen splits
   and hashes.
4. **Launches** the detached causal-quality worker (seeds 2026/2027/2028,
   ranks base=384, matched=401, effective=512; 4 NPUs, fp32, 5000 steps).
5. **Polls** `status.json` / log until each seed's report validates.
6. **Pushes results** back to S3 and pulls them into `results/`.
7. **Writes a summary** markdown into `results/` for the paper tables.

## Frozen inputs (SHA-verified by the launcher)

- `data/quality/train.txt` (630), `dev.txt` (300), `test.txt` (303) —
  hashed manifests with zero cross-split near-duplicate overlap.
- `experiments/mwg_quality_distillation.py`, `experiments/audit_quality_threeway_split.py`,
  `scripts/launch_ASI2_causal_quality_detached.sh` — byte-identical to the
  locally verified copies (the launcher re-verifies by SHA-256 at run time).

## What the results feed into the paper (once available)

When the run completes (all three seeds pass every gate — see below), the
following updates turn the "causal quality: open" item into a measured,
multi-seed result. A helper (`scripts/ingest_causal_quality_results.py`)
reads the pulled `mwg_quality_distillation_*.json` reports and emits the
table rows + prose so the edits below are mechanical.

**Full/TMLR journal vehicle** (`paper/main.tex`, `paper/tmlr/main_tmlr.tex`):
1. `Numerical Evidence` → replace the "retained only for audit" note on the
   quality tables with a new table reporting mean±std over seeds of the
   trained `token_diag_core` (rank 384) relative-MSE and cosine against the
   dense teacher (MSE 0, cosine 1), static-SVD (same/parity rank),
   same-rank persistent (384), parameter-matched persistent (401), and
   effective-rank persistent (512) controls.
2. The framed disclaimer ("none is evidence about causal language-model
   quality") is replaced by the predeclared protocol back-reference showing
   the inputs are the frozen hashed disjoint splits.
3. `Current Evidence and Open Validation` → move the "Causal quality" item
   from *open* to *measured*; keep it conditional until branch-skipping and
   end-to-end remain open.
4. Abstract + Conclusion → upgrade "mechanism verified, net quality open" to
   "mechanism verified **and** causal quality preserved at
   ≤r-parameter budget across three disjoint seeds," only if the diagonal-core
   mean is not worse than the parameter-matched persistent control within the
   predeclared non-inferiority margin (an honest negative updates the
   Discussion instead).

**ICLR 2027** (`paper/iclr_parts/`): mirror the same table/claim into the
appendix ("Causal Replacement: Legacy Redundancy" / results appendix) and the
one-line abstract claim, keeping the 9-page main-text limit intact (the table
goes in the appendix).

Do **not** change the systems (four-arm) numbers — they are already final and
verified against `key_results_SHIPPED.json`.

## Verification of completeness (after the run)

The launcher already refuses to mark a seed complete unless:
- it produced all expected checkpoints (persistent_r384, token_diag_core_r384,
  persistent_r401, persistent_r512, static SVD controls, dense teacher);
- `evidence_mode=true`, `env_label=ASI2`, disjoint data provenance recorded;
- dense teacher control is exact (MSE 0, cosine 1);
- resume checkpoints are complete and fingerprint-matched.

Only after **all three seeds** pass these gates is the run `completed`.

## Closing test (2026-09-06): r401 maximum-rank generated core

The v1 run above is COMPLETE and its result (an honest boundary: same-rank
parity with persistent r384, ~2.3% behind parameter-matched persistent r401)
is integrated. The paper's stated closing test is to train the generated
diagonal core **at the matched rank r401** for a direct equal-rank comparison.
A separate, versioned launcher is prepared (never mutating the frozen v1 one):
`scripts/launch_ASI2_causal_quality_closing_detached.sh` +
`..._closing_oneshot.sh`. It is locally syntax/spec-validated but NOT yet
launched because ASI2 is currently auth-blocked (SMS login needed). Full launch
+ integration instructions: `paper/CLOSING_TEST_RUN_OPERATOR.md`.
