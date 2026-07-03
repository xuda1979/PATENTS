# TOOLS.md — MWG-EW Patent Workspace

## Huanxin

- Available environments: `ai1`, `AI`, `ASI2`, `ASI3`
- Startable environments: `AI`, `ASI2`, `ASI3` (if a row/page shows stopped/`已停止`,
  click the start/run control and wait for the environment to become openable
  before treating shell access as failed)
- Current training policy: use `ASI3` only for any new training launches.
  Historical `ai1`/`ASI1`/`ASI2` artifacts may be cited as past evidence, but
  do not launch new training there.
- Default environment: `ASI3` for new MWG-EW training
- Remote root ai1: `/root/work/mwg-ew-patent`
- Remote root ASI2: `/vllm-workspace/mwg-ew-transformer-research`
- Remote root ASI3: `/vllm-workspace/mwg-ew-transformer-research`
- Generic shell wrapper: `scripts/huanxin_shell.sh`
- ASI2 shell shortcut: `scripts/asi2_shell.sh`
- ASI2 job manager: `scripts/asi2_job.sh`
- ai1 shell shortcut: `scripts/ai1_shell.sh`
- ai1 job manager: `scripts/ai1_job.sh`
- ai1 run file: `scripts/ai1_run_file.sh`

## S3 Relay

- S3 endpoint: `https://iner.aihuanxin.cn`
- S3 rclone remote: `iner-aihuanxin`
- S3 root: `iner-aihuanxin:jtdlp-21b4208dde424e96b159362ef49c9c96/mwg-ew-patent`
- Local -> S3 helper: `scripts/push_to_s3.sh`
- S3 -> local helper: `scripts/pull_from_s3.sh`
- ASI2 sync helper: `research_paper_mwg_ew_transformer/scripts/ASI2_sync_code_from_s3.sh`
- ASI2 push-back helper: `research_paper_mwg_ew_transformer/scripts/ASI2_push_results_to_s3.sh`
- ai1 sync helper: `scripts/ai1_sync_from_s3.sh` for historical patent artifacts only
- ai1 push-back helper: `scripts/ai1_push_results_to_s3.sh` for historical patent artifacts only

## Experiment Context

- Project: MWG-EW patent (一种面向存储带宽受限神经网络执行的临时权重描述子生成、消费与生命周期控制系统及方法)
- Purpose: Run real numerical experiments on the current Huanxin training environment to produce patent-grade and paper-grade evidence
- Simulation (local): `simulation/mwg_ew_simulation.py` — analytical model, not hardware evidence
- Real experiments (remote): run new MWG-EW Transformer training on ASI3 via the shell wrappers above when the ASI3 command channel is healthy
- Results destination: `results/` on remote, synced back via S3, inserted into 交底书

## Experiment Workflow

1. Push code to S3: `bash scripts/push_to_s3.sh simulation experiments`
2. Sync to ASI3 with the ASI3 sync helper from the research-paper workspace
3. Run experiment: `bash research_paper_mwg_ew_transformer/scripts/ASI3_shell.sh "cd /vllm-workspace/mwg-ew-transformer-research && <command>"`
4. Push results back through the S3 relay
5. Pull results locally: `bash scripts/pull_from_s3.sh results`
6. Update 交底书 with real measured data
