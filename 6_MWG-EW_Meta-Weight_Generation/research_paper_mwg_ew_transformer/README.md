# MWG-EW Transformer Research Paper

This folder is the research-paper workspace for MWG-EW as a neural network
algorithm and infrastructure paper. It intentionally avoids patent-application
language and frames the contribution as a Transformer FFN replacement that
reduces weight bandwidth and distributed gradient communication.

## Layout

- `paper/main.tex` - clean paper draft.
- `paper/refs.bib` - bibliography for the draft.
- `experiments/mwg_transformer_ASI3_benchmark.py` - distributed NPU benchmark
  with ASI2 presets for the current training lane.
- `experiments/mwg_quality_distillation.py` - checkpoint-backed FFN quality and
  low-rank distillation probe.
- `scripts/launch_ASI2_reliability_scaling_detached.sh` - current ASI2 systems
  replication launcher.
- `scripts/run_asi1_quality_distillation.sh` - ASI1 quality/distillation
  launcher for Qwen2.5-1.5B FFN weights.
- `archive/started_drafts/` - earlier paper starts moved out of the repo root.
- `results/` - local copies of pulled ASI3 results.

## Current ASI2 Target

The current training policy is ASI2 only for new MWG-EW Transformer
experiments. Historical ASI1/ASI3 results may be cited as completed evidence
but should not be resumed for new training launches.

The ASI2 project root is:

`/vllm-workspace/mwg-ew-transformer-research`

The strongest current systems artifact is
`ASI3_reliability_scaling_20260518T072507Z`: 1/2/4/8 NPU scaling, three repeats
per setting, 8B FFN geometry, and ranks `64,128,256`.

The checkpoint quality artifact is
`mwg_quality_distillation_20260518T083242Z`: Qwen2.5-1.5B layer-0 FFN,
eight NPUs, fp32, ranks `64,128`, static SVD vs persistent low-rank vs MWG
rank-scale generator.

## Typical Workflow

From this folder:

```bash
bash scripts/push_ASI2_code_to_s3.sh
../scripts/asi2_shell.sh "cd /vllm-workspace/mwg-ew-transformer-research && bash scripts/ASI2_sync_code_from_s3.sh && bash scripts/launch_ASI2_reliability_scaling_detached.sh"
```

For a local smoke test:

```bash
python3 experiments/mwg_transformer_ASI3_benchmark.py --preset tiny --outdir /tmp/mwg-ew-smoke
```

For a remote-sized ASI2 smoke test before the full all-NPU run:

```bash
python3 experiments/mwg_transformer_ASI3_benchmark.py --preset ASI2_smoke --env-label ASI2 --outdir results
```

The ASI2 launcher writes JSON and Markdown summaries under remote
`/vllm-workspace/mwg-ew-transformer-research/results/`.

The latest ASI1 pulled systems summary is under
`results/pulled_asi1/ASI3_reliability_scaling_20260518T072507Z/`.

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
