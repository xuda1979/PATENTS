# ASI3 2-NPU Top-Quality Experiment Status, 2026-06-09

## Goal

Run the next evidence-strengthening router experiment on ASI3 while respecting
the active constraint: at most two ASI3 NPUs concurrently.

## Completed Local Work

- Updated `scripts/submit_ASI3_token_router_global_task.sh` so the ASI3 router
  training-task payload defaults to two accelerator cards and exports
  `ASCEND_RT_VISIBLE_DEVICES='0,1'`.
- Added configurable router manifest, threshold policy, sequence length, and
  train/eval count parameters:
  - `HUANXIN_ASI3_ROUTER_SPLIT_MANIFEST`
  - `HUANXIN_ASI3_ROUTER_FRACTIONS`
  - `HUANXIN_ASI3_ROUTER_THRESHOLD_POLICY`
  - `HUANXIN_ASI3_ROUTER_TRAIN_EXAMPLES`
  - `HUANXIN_ASI3_ROUTER_EVAL_EXAMPLES`
  - `HUANXIN_ASI3_ROUTER_SEQ`
- Added early S3 heartbeat upload in the remote payload, before the expensive
  evaluation starts. This should create `${RUN_ID}.boot.json` under
  `results/asi3_token_router_global_task_artifacts` when the remote task
  actually starts.
- Added `scripts/check_huanxin_task_status.js` for reusable task status
  inspection from the authenticated Huanxin profile.
- Pushed the updated ASI3 launcher and evaluator scripts to the INER S3 relay.

## Validation

- `bash -n scripts/submit_ASI3_token_router_global_task.sh scripts/submit_ASI3_scaled_sweep_task.sh`
  passed.
- Decoded dry-run payload confirms:
  - `export ASCEND_RT_VISIBLE_DEVICES='0,1'`
  - `--accelerator-cards 2`
  - early boot artifact path contains `boot.json`
  - default manifest is `data/heldout/router_global_splits/manifest.json`
  - default fractions are `0.01,0.03,0.05,0.10,0.25,0.50`

## ASI3 Launch Attempts

- Previous UI task `asi3-2npu-router-ui-06090231` was submitted earlier and
  initially listed as starting, but no S3 artifacts appeared under
  `asi3_token_router_global_task_artifacts`.
- Huanxin task status API returned `403` even after successful SSO bridge.
- A later UI task-list view showed no visible matching task and no task-list
  network response containing the task.
- Replacement UI submit attempt `asi3-2npu-router-topq-06091141` failed before
  task creation because the page did not expose the `提交任务` drawer control.
- Direct API submit attempt `asi3-2npu-router-topq-06091145` failed with
  `403 RBAC: access denied`; no task was created.
- ASI3 shell remains blocked by:
  `getShellVisitUrl code=170022 ... frontend fell through to wss://aihuanxin.cn/kunlun/null`.

## Current Evidence Boundary

No new ASI3 result should be added to the paper from these launch attempts.
The paper should continue to rely on the already fetched ASI3 validation and
rank-sweep artifacts until the S3 artifact prefix contains a completed router
result or a verifiable status/log artifact.

## Next Concrete Action

When ASI3 task submission UI/API is usable again, submit exactly one two-NPU
router task with the improved launcher and poll:

```bash
rclone lsf iner-aihuanxin:jtdlp-21b4208dde424e96b159362ef49c9c96/mwg-ew-patent/research_paper_mwg_ew_transformer/results/asi3_token_router_global_task_artifacts --s3-no-check-bucket
```

If a boot/status/result JSON appears, fetch and inspect it before modifying the
paper.
