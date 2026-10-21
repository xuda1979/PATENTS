# ASI1 Unseen-Family Transfer Test (2026-08-21)

- Platform: Huanxin ASI1, single Ascend 910B2 NPU, torch 2.7.1/torch_npu 2.7.1.
- Purpose: extend the Seventh limitation ("manifest does not yet cover
  dialogue or long-context families") with measured out-of-family transfer.
- Setup: router fitted on the five-suite train pool (concatenated
  combined_extra_splits router_train files, uniform ridge, seed 0), evaluated
  on two held-out families via mwg_token_router_gate_eval.py at the
  tight-eligibility risk budget (target 0.10, risk-max-predicted-delta -0.20,
  threshold policy global).
- Corpora (transferred to AI1 data/heldout_extra/):
  - dolly_dialogue.txt: 100 instruction+response turns from
    databricks/databricks-dolly-15k (single-line format)
  - arxiv_papers_longcontext.txt: 15 classic ML papers from ar5iv
    (8K chars each; long-form scientific prose)

## Results

| family | dense PPL | always-patched ratio | router actual | router ratio |
|--------|-----------|----------------------|---------------|--------------|
| Dolly (dialogue) | 10.804 | 2.29x | 18.9% | 1.38x |
| arXiv (scientific) | 12.945 | 1.29x | 41.8% | 1.07x |

## Interpretation

- Always-patched layer-16 replacement degrades both out-of-family families
  severely (2.29x, 1.29x), consistent with the in-family Wikitext/HellaSwag
  behavior.
- The five-suite-calibrated router does NOT transfer: at a 10% train-side
  target it over-patches out-of-family tokens (18.9%/41.8% actual vs ~2%
  in-family) and degrades PPL (1.38x/1.07x vs 0.9923x in-family). The
  benefit predictor over-trusts unseen-family tokens; the eligibility policy
  is family-specific, like the layer-specificity already documented.
- Caveat: the transfer eval used the uniform-ridge explicit-train branch
  (threshold derived from the unweighted pool, not the suite-balanced
  -0.2015 operating point); the qualitative no-transfer conclusion is robust
  to this deviation.
- Paper updated: limitations Seventh, evidence-ladder selective-win row,
  Discussion layer/family-specificity paragraph; compiles clean.
- Raw JSONs on ASI1:
  results/transfer_20260820T200347Z.json (arxiv; dolly overwritten by the
  shared-TS filename bug), results/transfer_dolly_rerun_20260820T205921Z.json;
  logs transfer_evals_20260820T2003*.log, transfer_dolly_rerun.log.
