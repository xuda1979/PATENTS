# MWG-EW Transformer Research Paper

This folder is the research-paper workspace for MWG-EW as a neural network
algorithm and infrastructure paper. It intentionally avoids patent-application
language and frames the contribution as a Transformer FFN replacement that
reduces weight bandwidth and distributed gradient communication.

## Layout

- `paper/main.tex` - clean paper draft.
- `paper/refs.bib` - bibliography for the draft.
- `experiments/mwg_transformer_ai3_benchmark.py` - distributed NPU benchmark.
- `scripts/ai3_shell.sh` - local AI3 shell wrapper using the robust Huanxin
  browser automation from `/Users/daxu/software/quantum-gpt`.
- `scripts/ai3_upload.js` - chunked tar upload into AI3.
- `scripts/run_ai3_all_npus.sh` - remote launcher for all AI3 NPUs.
- `archive/started_drafts/` - earlier paper starts moved out of the repo root.
- `results/` - local copies of pulled AI3 results.

## AI3 Target

The target Huanxin environment is `ai3`:

`https://aihuanxin.cn/kunlun/kl-web?poolId=6&projectId=21b4208dde424e96b159362ef49c9c96#/train-dev/environment/dl-c72bd81a96e33134bbe0ae4a478fbab0?name=ai3`

The current AI3 runtime exposes four usable logical Ascend 910B2 NPUs as `0,1,2,3`, with
`/vllm-workspace` as the remote shell root. The launcher defaults to using
all four via `ASCEND_RT_VISIBLE_DEVICES=0,1,2,3`. Older physical-looking IDs
such as `1,3,5,6` can make the 4-rank distributed smoke fail even though
two-card subsets work.

## Typical Workflow

From this folder:

```bash
node scripts/ai3_upload.js
./scripts/ai3_shell.sh "cd /vllm-workspace/mwg-ew-transformer-research && bash scripts/run_ai3_all_npus.sh"
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
