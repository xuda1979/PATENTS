# ASI3 Five-Suite Seed Sweep Launch Blocker, 2026-06-12

Goal: launch a top-journal strengthening experiment on ASI3 using at most two
NPUs: five-suite token-router replication over seeds `0,1,2`, split manifest
`data/heldout/combined_extra_splits/manifest.json`, calibrated checkpoint
`results/asi3_layer16_recovery_20260611T063442Z/layer16/checkpoints/mwg_expert_residual_r384_belle_lmce_cal_1200.pt`.

Prepared:

- Added `scripts/launch_asi3_five_suite_router_seed_sweep_detached.sh`.
- Pushed updated `scripts`, `experiments`, `data/heldout`, and
  `data/heldout_extra` to the INER S3 relay.
- Existing task payload `scripts/remote_ASI3_token_router_global_payload.sh`
  already supports multi-seed sequential runs with one NPU per seed and
  `ASCEND_RT_VISIBLE_DEVICES` restricted to device `0` or `1`.

Launch attempts:

1. Direct ASI3 dev shell:
   - Command route: `ASI3_ALLOW_BROWSER=1 ... bash scripts/ASI3_shell.sh ...`
   - Blocker: daemon health reports `getShellVisitUrl code=170022` and frontend
     falls through to `wss://aihuanxin.cn/kunlun/null`; terminal surface is
     disconnected.

2. Direct training-task API:
   - Task: `asi3-five-router-0612a`
   - Resource request: 1 instance, 2 Ascend 910B cards, 40 CPU, 480 GB memory.
   - Blocker: direct submit response `403 RBAC: access denied`.

3. UI training-task fallback:
   - Task: `asi3-five-router-0612b`
   - Blocker: submit automation timed out waiting for the ASI3 environment row:
     `locator('tr').filter({ hasText: 'ASI3' }).first()` not visible in 60 s.

4. Task-status checks:
   - `browser-automation/asi3-five-router-0612a-status.json`
   - `browser-automation/asi3-five-router-0612b-status.json`
   - Both landed on Keycloak required action:
     `execution=UPDATE_PASSWORD`.
   - Page text: password update required.
   - Task list API still returns `403 RBAC: access denied`.

Current state:

- No ASI3 five-suite seed-sweep task was confirmed created.
- No ASI3 experiment process is known to be running from these attempts.
- The local/S3 launch assets are ready; the blocker is Huanxin account/session
  required password update plus ASI3 shell endpoint failure.

Next concrete action after Huanxin account/session repair:

```bash
HUANXIN_ASI3_TASK_NAME=asi3-five-router-0612c \
HUANXIN_ASI3_ARTIFACT_STEM=asi3-five-router-0612c \
HUANXIN_ASI3_ACCELERATOR_CARDS=2 \
HUANXIN_ASI3_CPU_CORES=40 \
HUANXIN_ASI3_MEMORY_GB=480 \
HUANXIN_ASI3_ROUTER_PATCH=/vllm-workspace/mwg-ew-transformer-research/results/asi3_layer16_recovery_20260611T063442Z/layer16/checkpoints/mwg_expert_residual_r384_belle_lmce_cal_1200.pt \
HUANXIN_ASI3_ROUTER_SPLIT_MANIFEST=data/heldout/combined_extra_splits/manifest.json \
HUANXIN_ASI3_ROUTER_SEEDS=0,1,2 \
HUANXIN_ASI3_ROUTER_THRESHOLD_POLICY=suite_local \
HUANXIN_ASI3_ROUTER_JOINT_BUDGETS=0.05,0.10,0.25 \
HUANXIN_ASI3_WAIT_MS=30000 \
bash scripts/submit_ASI3_token_router_global_task.sh --submit --ui-submit
```
