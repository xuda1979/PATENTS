# Huanxin Run Attempt - 2026-04-30

## Local Validation

The benchmark script passed two local CPU smoke runs before remote execution:

- `python3 experiments/mwg_transformer_ASI3_benchmark.py --preset tiny --outdir /tmp/mwg-ew-smoke`
- `python3 experiments/mwg_transformer_ASI3_benchmark.py --preset ASI3_smoke --outdir /tmp/mwg-ew-ASI3-smoke-local`

The new `ASI3_smoke` preset completed and wrote:

- `/tmp/mwg-ew-ASI3-smoke-local/ASI3_mwg_transformer_20260430T040141Z.json`
- `/tmp/mwg-ew-ASI3-smoke-local/ASI3_mwg_transformer_20260430T040141Z.md`

Summary from the local smoke run:

| Method | Rank | Traffic reduction | Forward speedup | Train speedup |
|---|---:|---:|---:|---:|
| MWG-EW | 32 | 11.733x | 2.796x | 2.199x |
| MWG-EW | 64 | 5.867x | 2.060x | 1.756x |
| MWG-EW | 128 | 2.933x | 1.300x | 1.279x |

## Huanxin Control-Plane Status

The Huanxin profile was stale for the exact ASI3 URL:

`https://aihuanxin.cn/kunlun/kl-web?poolId=6&projectId=21b4208dde424e96b159362ef49c9c96#/train-dev/environment/dl-c72bd81a96e33134bbe0ae4a478fbab0?name=ASI3`

The probe returned `login_required`. I then ran the Safari SSO repair flow:

```bash
HUANXIN_TRAIN_DEV_URL='https://aihuanxin.cn/kunlun/kl-web?poolId=6&projectId=21b4208dde424e96b159362ef49c9c96#/train-dev/environment/dl-c72bd81a96e33134bbe0ae4a478fbab0?name=ASI3' \
HUANXIN_PROFILE_REPAIR_RESULT_PATH=/tmp/mwg-ew-huanxin-repair-ASI3.json \
HUANXIN_PROFILE_REPAIR_STATE_PATH=/tmp/mwg-ew-huanxin-repair-ASI3-state.json \
HUANXIN_REPAIR_RUN_PROBE=1 \
HUANXIN_PROFILE_REPAIR_PRINT_RESULT=1 \
HUANXIN_REPAIR_RESTART_DAEMON_ON_SUCCESS=0 \
bash /Users/daxu/software/quantum-gpt/scripts/repair_huanxin_browser_profile.sh
```

The repair reported `ok: true`, `mode: safari_sso_bridge`, `finalUrlState: app_surface`,
and synced the working profile back to the base profile.

## Environment Startup Status

After applying the startable-environment rule, the train-dev list confirmed both
paper environments were already running:

| Environment | Status | Resources | Last start |
|---|---|---:|---|
| `ASI3` | `运行中` | 4 accelerator cards | 2026-04-30 14:38:05 |
| `AI` | `运行中` | 8 accelerator cards | 2026-04-30 14:38:00 |

The ASI3 shell then reached a prompt and reported:

```text
__MWG_ASI3_READY__ /vllm-workspace
dl-c72bd81a96e33134bbe0ae4a478fbab0-r0-24e1e34c015d-0
2026-04-30T06:44:08Z
```

## Remote Upload

The research-paper workspace uploaded successfully to:

`/vllm-workspace/mwg-ew-transformer-research`

The upload included `README.md`, `paper/`, `experiments/`, and `scripts/`.

## Remote Single-Process ASI3 Smoke

Command:

```bash
cd /vllm-workspace/mwg-ew-transformer-research &&
python3 experiments/mwg_transformer_ASI3_benchmark.py --preset ASI3_smoke --outdir results
```

The run completed successfully and wrote:

- `results/ASI3_mwg_transformer_20260430T064933Z.json`
- `results/ASI3_mwg_transformer_20260430T064933Z.md`

Summary:

| Method | Params MiB | Descriptor MiB | Fwd ms | Train ms | Fwd speedup | Train speedup | Traffic reduction |
|---|---:|---:|---:|---:|---:|---:|---:|
| dense | 4.125 | 4.125 | 0.3117 | 1.2820 | 1.000 | 1.000 | 1.000 |
| mwg_r32 | 0.524 | 0.352 | 0.7978 | 2.8807 | 0.391 | 0.445 | 11.733 |
| mwg_r64 | 0.924 | 0.703 | 0.7967 | 2.8769 | 0.391 | 0.446 | 5.867 |
| mwg_r128 | 1.722 | 1.406 | 0.7764 | 2.7362 | 0.401 | 0.469 | 2.933 |

This small geometry validates the ASI3 runtime, fp16 NPU execution, result
writing, and descriptor/parameter accounting. It is not intended as the headline
performance configuration.

## Remote Distributed Smoke Diagnostics

Command:

```bash
cd /vllm-workspace/mwg-ew-transformer-research &&
export ASCEND_RT_VISIBLE_DEVICES=1,3,5,6 \
       PYTORCH_NPU_ALLOC_CONF=max_split_size_mb:256 \
       HCCL_CONNECT_TIMEOUT=1800 \
       OMP_NUM_THREADS=1 &&
python3 -m torch.distributed.run --nproc_per_node=4 \
  experiments/mwg_transformer_ASI3_benchmark.py \
  --preset ASI3_smoke --outdir results --warmup 1 --iters 2 --train-iters 1 --comm-iters 1
```

The initial 4-NPU distributed launch failed with `ChildFailedError`; local ranks
2 and 3 exited with code 1. Diagnostics showed this was a device-ID selection
problem:

| Visible devices | NPROC | Result | Notes |
|---|---:|---|---|
| `1,3` | 2 | pass | HCCL/distributed path works on first tested pair |
| `5,6` | 2 | pass | also passed when `--dtype fp16` was forced |
| `0,1,2,3` | 4 | pass | correct logical four-card mapping for current ASI3 runtime |
| `1,3,5,6` | 4 | fail | older physical-looking mapping; ranks 2/3 exited |

The launcher has been updated to default to `ASCEND_RT_VISIBLE_DEVICES=0,1,2,3`.

Latest successful 4-NPU smoke:

- `results/ASI3_mwg_transformer_20260430T083252Z.json`
- `results/ASI3_mwg_transformer_20260430T083252Z.md`

Summary for the successful logical-ID 4-NPU smoke:

| Method | Params MiB | Descriptor MiB | Fwd speedup | Train speedup | Traffic reduction |
|---|---:|---:|---:|---:|---:|
| mwg_r32 | 0.524 | 0.352 | 0.734 | 0.560 | 11.733 |
| mwg_r64 | 0.924 | 0.703 | 0.748 | 0.609 | 5.867 |
| mwg_r128 | 1.722 | 1.406 | 0.779 | 0.624 | 2.933 |

## Remote Four-NPU Medium Geometry

Command shape:

```bash
cd /vllm-workspace/mwg-ew-transformer-research &&
export ASCEND_RT_VISIBLE_DEVICES=0,1,2,3 &&
python3 -m torch.distributed.run --nproc_per_node=4 \
  experiments/mwg_transformer_ASI3_benchmark.py \
  --preset ASI3_smoke --d 1024 --m 2816 --ranks 32,64,128 \
  --batch-decode 1 --seq-decode 128 --batch-train 1 --seq-train 256 \
  --warmup 1 --iters 2 --train-iters 1 --comm-iters 1 --outdir results
```

The run completed successfully and wrote:

- `results/ASI3_mwg_transformer_20260430T084229Z.json`
- `results/ASI3_mwg_transformer_20260430T084229Z.md`

Summary:

| Method | Params MiB | Descriptor MiB | Fwd ms | Train ms | Fwd speedup | Train speedup | Traffic reduction | AllReduce ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dense | 16.500 | 16.500 | 0.9123 | 2.2849 | 1.000 | 1.000 | 1.000 | 1.1870 |
| mwg_r32 | 1.298 | 0.703 | 1.3120 | 4.4409 | 0.695 | 0.515 | 23.467 | 0.6994 |
| mwg_r64 | 2.096 | 1.406 | 1.2955 | 3.8536 | 0.704 | 0.593 | 11.733 | 0.7336 |
| mwg_r128 | 3.691 | 2.812 | 1.2890 | 3.8626 | 0.708 | 0.592 | 5.867 | 0.8074 |

This medium geometry is diagnostic rather than headline evidence. It confirmed
that the four-rank HCCL path, descriptor accounting, and all-reduce timing work
outside the tiny smoke size, while showing that unfused PyTorch low-rank
operators are not beneficial at this scale.

## Remote Four-NPU 8B-Scale Short Run

Command shape:

```bash
cd /vllm-workspace/mwg-ew-transformer-research &&
export ASCEND_RT_VISIBLE_DEVICES=0,1,2,3 &&
python3 -m torch.distributed.run --nproc_per_node=4 \
  experiments/mwg_transformer_ASI3_benchmark.py \
  --preset ASI3_large --ranks 64,128,256 \
  --warmup 1 --iters 2 --train-iters 1 --comm-iters 1 --outdir results
```

The run completed successfully and wrote:

- `results/ASI3_mwg_transformer_20260430T084455Z.json`
- `results/ASI3_mwg_transformer_20260430T084455Z.md`

Summary:

| Method | Params MiB | Descriptor MiB | Fwd ms | Train ms | Fwd speedup | Train speedup | Traffic reduction | AllReduce ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dense | 336.000 | 336.000 | 1.5159 | 7.9869 | 1.000 | 1.000 | 1.000 | 10.5336 |
| mwg_r64 | 11.127 | 6.750 | 1.3750 | 4.0148 | 1.102 | 1.989 | 49.778 | 1.0506 |
| mwg_r128 | 18.254 | 13.500 | 1.2936 | 3.8167 | 1.172 | 2.093 | 24.889 | 1.2024 |
| mwg_r256 | 32.507 | 27.000 | 1.2697 | 3.7759 | 1.194 | 2.115 | 12.444 | 1.6092 |

This short run established the headline 8B geometry on all four ASI3 NPUs and
showed forward and training speedups under short timing counts. Because the
iteration counts are low, a longer reproduction was launched before inserting
numbers into the paper.

## Remote Four-NPU 8B-Scale Main Run

Command:

```bash
cd /vllm-workspace/mwg-ew-transformer-research &&
bash scripts/run_ASI3_all_npus.sh
```

The script resolved `ASCEND_RT_VISIBLE_DEVICES=0,1,2,3`, launched four ranks,
and used the full `ASI3_large` defaults:

- warmup iterations: 4
- forward timing iterations: 12
- training iterations: 4
- all-reduce iterations: 4

The run completed successfully and wrote:

- `results/ASI3_mwg_transformer_20260430T092119Z.json`
- `results/ASI3_mwg_transformer_20260430T092119Z.md`

Summary:

| Method | Params MiB | Descriptor MiB | Fwd ms | Train ms | Fwd speedup | Train speedup | Traffic reduction | AllReduce ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dense | 336.000 | 336.000 | 0.9275 | 5.4483 | 1.000 | 1.000 | 1.000 | 10.9841 |
| mwg_r64 | 11.127 | 6.750 | 1.3920 | 3.6486 | 0.666 | 1.493 | 49.778 | 0.9714 |
| mwg_r128 | 18.254 | 13.500 | 1.5094 | 3.5931 | 0.614 | 1.516 | 24.889 | 1.2116 |
| mwg_r256 | 32.507 | 27.000 | 1.2347 | 3.8407 | 0.751 | 1.419 | 12.444 | 1.5495 |

This is the main result used in the paper draft. It is stronger as evidence
because it uses longer timing loops, but it is also more conservative: the
unfused PyTorch-NPU forward path is slower than dense, while the training path,
state size, descriptor traffic, and all-reduce measurements still support the
MWG-EW parameter-lifecycle claim. At rank 128, descriptor traffic falls from
336.0 MiB to 13.5 MiB, trainable state falls to 18.254 MiB, the measured
training step improves from 5.4483 ms to 3.5931 ms, and all-reduce latency
falls from 10.9841 ms to 1.2116 ms.
