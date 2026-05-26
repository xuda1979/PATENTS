# MWG-EW Transformer Research Paper

This folder is the research-paper workspace for MWG-EW as a neural network
algorithm and infrastructure paper. It intentionally avoids patent-application
language and frames the contribution as a Transformer FFN replacement that
reduces weight bandwidth and distributed gradient communication.

## Layout

- `paper/main.tex` - clean paper draft.
- `paper/refs.bib` - bibliography for the draft.
- `experiments/mwg_transformer_ai3_benchmark.py` - distributed NPU benchmark.
- `experiments/mwg_quality_distillation.py` - checkpoint-backed FFN quality and
  low-rank distillation probe.
- `scripts/ai3_shell.sh` - local AI3 shell wrapper using the robust Huanxin
  browser automation from `/Users/daxu/software/quantum-gpt`.
- `scripts/ai3_upload.js` - chunked tar upload into AI3.
- `scripts/run_ai3_all_npus.sh` - older remote launcher for all AI3 NPUs.
- `scripts/run_asi1_quality_distillation.sh` - ASI1 quality/distillation
  launcher for Qwen2.5-1.5B FFN weights.
- `archive/started_drafts/` - earlier paper starts moved out of the repo root.
- `results/` - local copies of pulled AI3 results.

## Current ASI1 Target

The current large-experiment target is ASI1 because it exposes eight usable
Ascend 910B2 NPUs:

`https://aihuanxin.cn/kunlun/kl-web?poolId=6&projectId=21b4208dde424e96b159362ef49c9c96#/train-dev/environment/dl-9a5a098accce31c28cf4c6ca23391341?name=ASI1`

The ASI1 project root used by the current experiments is:

`/workspace/software/6_MWG-EW_Meta-Weight_Generation/research_paper_mwg_ew_transformer`

The strongest current systems artifact is
`ai3_reliability_scaling_20260518T072507Z`: 1/2/4/8 NPU scaling, three repeats
per setting, 8B FFN geometry, and ranks `64,128,256`.

The checkpoint quality artifact is
`mwg_quality_distillation_20260518T083242Z`: Qwen2.5-1.5B layer-0 FFN,
eight NPUs, fp32, ranks `64,128`, static SVD vs persistent low-rank vs MWG
rank-scale generator.

## Typical Workflow

From this folder:

```bash
bash scripts/push_ai3_code_to_s3.sh
./scripts/ai3_shell.sh "cd /vllm-workspace/mwg-ew-transformer-research && bash scripts/ai3_sync_code_from_s3.sh && bash scripts/run_ai3_all_npus.sh"
```

For a local smoke test:

```bash
python3 experiments/mwg_transformer_ai3_benchmark.py --preset tiny --outdir /tmp/mwg-ew-smoke
```

For a remote-sized smoke test before the full all-NPU run:

```bash
python3 experiments/mwg_transformer_ai3_benchmark.py --preset ai3_smoke --outdir results
```

The AI3 launcher writes JSON and Markdown summaries under remote
`/vllm-workspace/mwg-ew-transformer-research/results/`.

The latest ASI1 pulled systems summary is under
`results/pulled_asi1/ai3_reliability_scaling_20260518T072507Z/`.

## Broad Held-Out Validation

Use `experiments/mwg_broad_eval_manifest.py` for leakage-resistant validation
across multiple explicit corpora. It never falls back to `DEFAULT_TEXTS`; each
suite in the manifest must name a real held-out text source with enough text to
pass `--min-texts` and `--min-chars`.

Prepare corpus files with:

```bash
python3 experiments/prepare_heldout_corpora.py --outdir data/heldout --allow-partial
```

This writes `data/heldout/manifest.json`, `router_train.txt`,
`router_eval.txt`, and `provenance.json`. The provenance file records successful
dataset splits and any unavailable sources.

Remote ASI3 launcher:

```bash
MANIFEST=/vllm-workspace/mwg-ew-transformer-research/data/heldout/manifest.json \
PATCH=/vllm-workspace/mwg-ew-transformer-research/results/.../mwg_expert_residual_r384_belle_lmce_cal_1200.pt \
bash scripts/launch_asi3_broad_validation_detached.sh
```

The manifest shape is shown in `results/broad_eval_manifest.example.json`.

## Deployable Router Validation

Use `experiments/mwg_router_gate_eval.py` to test the next algorithmic step:
a deployable dense-fallback policy for a single patched FFN layer. The router
is trained on one explicit text split using labels from dense-vs-patched loss
deltas, but at evaluation time it routes only from pre-FFN hidden-state summary
features. This makes it a candidate runtime policy rather than the oracle
frontier reported by `experiments/mwg_hybrid_gate_eval.py`.

Remote ASI3 launcher:

```bash
TRAIN_TEXTS=/vllm-workspace/mwg-ew-transformer-research/data/heldout/router_train.txt \
EVAL_TEXTS=/vllm-workspace/mwg-ew-transformer-research/data/heldout/router_eval.txt \
PATCH=/vllm-workspace/mwg-ew-transformer-research/results/.../mwg_expert_residual_r384_belle_lmce_cal_1200.pt \
bash scripts/launch_asi3_router_validation_detached.sh
```

Do not cite router results unless `TRAIN_TEXTS` and `EVAL_TEXTS` are disjoint
real held-out files. The JSON report includes always-dense, always-patched,
deployable routed, and oracle-frontier rows so the paper can separate achievable
policy quality from the best-case upper bound.
