# TOOLS.md — MWG-EW Patent Workspace

## Huanxin

- Available environments: `ai1`
- Default environment: `ai1`
- Remote root ai1: `/root/work/mwg-ew-patent`
- Generic shell wrapper: `scripts/huanxin_shell.sh`
- ai1 shell shortcut: `scripts/ai1_shell.sh`
- ai1 job manager: `scripts/ai1_job.sh`
- ai1 run file: `scripts/ai1_run_file.sh`

## S3 Relay

- S3 root: `nm-aihuanxin:jtdlp-3ed7854b946a47b1a49ad754baa76cd3/mwg-ew-patent`
- Local -> S3 helper: `scripts/push_to_s3.sh`
- S3 -> local helper: `scripts/pull_from_s3.sh`
- ai1 sync helper: `scripts/ai1_sync_from_s3.sh`
- ai1 push-back helper: `scripts/ai1_push_results_to_s3.sh`

## Experiment Context

- Project: MWG-EW patent (一种面向存储带宽受限神经网络执行的临时权重描述子生成、消费与生命周期控制系统及方法)
- Purpose: Run real numerical experiments on ai1 GPUs to produce patent-grade evidence
- Simulation (local): `simulation/mwg_ew_simulation.py` — analytical model, not hardware evidence
- Real experiments (remote): run on ai1 via the shell wrappers above
- Results destination: `results/` on remote, synced back via S3, inserted into 交底书

## Experiment Workflow

1. Push code to S3: `bash scripts/push_to_s3.sh simulation experiments`
2. Sync to ai1: `bash scripts/ai1_sync_from_s3.sh`
3. Run experiment: `bash scripts/ai1_shell.sh "cd /root/work/mwg-ew-patent && python3 experiments/run_real_benchmark.py"`
4. Push results back: `bash scripts/ai1_push_results_to_s3.sh results`
5. Pull results locally: `bash scripts/pull_from_s3.sh results`
6. Update 交底书 with real measured data
