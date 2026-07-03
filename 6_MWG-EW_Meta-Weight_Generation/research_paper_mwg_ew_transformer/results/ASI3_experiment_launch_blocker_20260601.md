# ASI3 Training Blocker Update - 2026-06-01

Current policy: use ASI3 only for any new MWG-EW Transformer training
launches. Do not launch new training on ASI1 or ASI2. The notes below record
why new ASI3 training was blocked at the time of this audit.

Preferred environment for the next training attempt:

- Environment: ASI3
- Shell wrapper: `scripts/ASI3_shell.sh`
- Remote project root: `/vllm-workspace/mwg-ew-transformer-research`
- Launcher candidate: `scripts/launch_asi3_token_router_global_suite_balanced_when_ready.sh`

# ASI3 Experiment Launch Blocker - 2026-06-01

## User constraint

At the time of the attempt below, training launches for the MWG-EW Transformer
paper were constrained to ASI3. That remains the active policy for new training.

## Attempted action

I attempted to start the next paper-improving ASI3 experiments using scripts
only:

- ASI3 reliability/scaling replication:
  `scripts/launch_ASI3_reliability_scaling_detached.sh`
- ASI3 broad selective-router sweep:
  `scripts/launch_asi3_token_router_leave_suiteout_seed_sweep_detached.sh`

No training was launched because the ASI3 command channel is unavailable.

## Current blocker

The real ASI3 daemon is on port `20653` and reports:

```text
startupFailureKind=shell_endpoint_unavailable
getShellVisitUrl code=170022 for env=ASI3 pod=dl-c72bd81a96e33134bbe0ae4a478fbab0-r0-b9aa825b43b4-0 type=terminal
frontend fell through to wss://aihuanxin.cn/kunlun/null
```

There is also a stale lowercase environment daemon on port `19003`. That daemon
must not be used for ASI3 work.

## Local guard fix

`scripts/ASI3_shell.sh` now defaults its health guard to the real ASI3 daemon
port `20653` and refuses to run if:

- the health endpoint is not `env=ASI3`,
- the ASI3 shell endpoint is unavailable,
- the ASI3 daemon is not ready,
- the daemon is busy or has pending requests,
- the previous command is incomplete.

This prevents accidental use of the stale lowercase daemon and prevents browser
fallback/standalone recovery from being used for ASI3 launches.

## Exact verification command

```bash
cd /Users/daxu/PATENTS/6_MWG-EW_Meta-Weight_Generation/research_paper_mwg_ew_transformer
bash scripts/ASI3_shell.sh "printf ASI3_HEALTH_OK"
```

Expected current result:

```text
ERROR: refusing ASI3 daemon command because the ASI3 shell endpoint is unavailable: getShellVisitUrl code=170022 ...
```

## Resume plan when ASI3 recovers

1. Verify ASI3 command channel:

   ```bash
   bash scripts/ASI3_shell.sh "cd /vllm-workspace/mwg-ew-transformer-research && pwd && python3 - <<'PY'
import torch
import torch_npu
print('torch', torch.__version__)
print('torch_npu', getattr(torch_npu, '__version__', 'unknown'))
print('npu_count', torch.npu.device_count())
PY"
   ```

2. Launch the stricter global suite-balanced ASI3 router run:

   ```bash
   THRESHOLD_POLICY=suite_local \
     bash scripts/launch_asi3_token_router_global_suite_balanced_when_ready.sh
   ```

3. Fetch status/results only with daemon helpers after launch completes.
