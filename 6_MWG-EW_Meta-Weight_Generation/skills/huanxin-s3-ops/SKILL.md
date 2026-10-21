---
name: huanxin-s3-ops
description: Operate Huanxin train-dev environments from this workspace and move files between local disk, S3, and Huanxin using repo-local scripts and shell helpers. Use when the user asks to access Huanxin, run experiments, inspect Huanxin auth or daemon state, or sync code and results through S3. This workspace targets the MWG-EW patent and research paper.
---

# Huanxin + S3 Ops - MWG-EW

Use `TOOLS.md` as the source of truth for the current Huanxin training policy.
For this workspace, new MWG-EW Transformer training launches currently use
`ASI2` only. Historical environments may be used only as sources for already
completed artifacts.

## Environment

- Current training environment: `ASI2`
- Historical/source environments: `ai1`, `AI`, `ASI3`
- Startable environments: read `TOOLS.md`. If a Huanxin row/page says `已停止`,
  `stopped`, or shows a start/run control such as `运行`, start the environment
  only through a non-interrupting approved script path.
- Patent remote workdir: `/root/work/mwg-ew-patent`
- Research-paper remote workdir: `/vllm-workspace/mwg-ew-transformer-research`
- S3 relay: `iner-aihuanxin:jtdlp-21b4208dde424e96b159362ef49c9c96/mwg-ew-patent`

## Default Entry Point

```bash
scripts/asi2_shell.sh "cd /vllm-workspace/mwg-ew-transformer-research && <command>"
```

This workspace includes a local `browser-automation/` bundle, so the shell wrapper is self-contained.

The transfer helpers are dual-mode:

- when run locally, they route through the environment shell wrapper
- when run inside the remote workdir, they execute `rclone` directly

## Long Jobs

Use background jobs and durable local handles:

```bash
scripts/asi2_job.sh start mwg-exp /tmp/mwg-exp.log "python3 experiments/run_real_benchmark.py"
scripts/asi2_job.sh status mwg-exp-20260414T000000Z
scripts/asi2_job.sh logs mwg-exp-20260414T000000Z 120
scripts/asi2_job.sh list
```

Use `scripts/asi2_job.sh` instead of raw `nohup` when you need a durable local job handle.

## Patent-Specific Experiment Rules

- New training results must come from the current environment named in `TOOLS.md`.
- Historical ai1/ASI1/ASI3 artifacts may be cited only as already-completed evidence.
- Record hardware environment (GPU model, memory, driver, CUDA version, precision) for every run.
- Collect profiler evidence: HBM bytes read/written, descriptor write-back status, tensor-core utilization.
- Measure against the dense baseline first, then MWG-EW at r=64, r=128, r=256.
- Cover at least: rank sweep, replacement-ratio sweep, distributed-training communication.
- All results must be reproducible and tied to a specific commit/kernel version.

## Experiment Matrix

1. **1B pilot**: single-projection, direct-factor path, r={32,64,96,128}
2. **8B patent-grade**: three-projection gated FFN, basis-bank path, r={32,64,128,256}
3. **Replacement sweep**: 25%, 50%, 75%, 100% FFN replacement at r=128
4. **Distributed training**: 8-GPU All-Reduce volume measurement
5. **KV-cache context**: dense vs MWG-EW maximum context under 80 GiB budget
6. **Profiler capture**: Nsight traces proving zero descriptor write-back

## File Movement

- Local -> S3: `scripts/push_to_s3.sh`
- S3 -> Huanxin: use the current environment sync helper from `TOOLS.md`.
- Huanxin -> S3: use the current environment push-results helper from `TOOLS.md`.
- S3 -> local: `scripts/pull_from_s3.sh`
- Run file remotely: `scripts/ai1_run_file.sh <relative-path>`

## Core Rules

- Read `TOOLS.md` first for workspace-specific values.
- Treat S3 and non-interrupting daemon/script APIs as the control/data plane.
- Before shell, sync, or training work, verify the target Huanxin environment is
  authenticated and running without popping/focusing/foregrounding browser UI.
- Never run visible Chrome/Safari, Safari callback capture, AppleScript
  foregrounding, headed fallback, or login/repair/open-env helpers that may
  interrupt the user. Browser-backed work is allowed only when headless,
  backgrounded, profile-isolated, and explicitly guarded against headed/Safari
  fallback.
- Prefer the repo's sync helpers over manual `rclone` or browser paste.
- Validate locally before any remote mutation.
- Use `--dry-run` first for large or risky transfers.
- Do not kill unrelated browser daemons, discard authenticated profiles, or
  delete remote content unless explicitly instructed.

## Shell Endpoint Recovery

Treat shell-open failures from the Huanxin terminal endpoint as transient until a fresh environment-page retry has failed. Common recoverable symptoms include:

- `getShellVisitUrl`
- `code=170022`
- `data=null`
- `获取shell终端信息失败`
- a websocket target or terminal URL ending in `/null`

When these appear, do not conclude that the environment is unavailable from the first failure. Close stale train-dev environment tabs for the target env, reopen the environment surface from the train-dev list or exact workspace URL, activate `Shell终端` again, and rerun the command through the workspace wrapper. If the wrapper exposes `HUANXIN_SHELL_OPEN_CYCLES`, raise it for stubborn endpoint retries before falling back to auth repair or manual intervention.

## Multiline Shell Commands

For heredocs or multiline probes, prefer a wrapper that sends the payload as a temporary script rather than embedding the raw command inside marker text. If a terminal command hangs after `python3 - <<'PY'` or another heredoc, interrupt that shell attempt and retry with the current wrapper or an encoded temporary script. Do not treat a heredoc marker hang as evidence that the remote environment or experiment code is broken.

## When To Load References

- Read [references/workflows.md](references/workflows.md) for concrete command recipes.
- Read [references/portability.md](references/portability.md) when packaging or adapting the skill for another repo.

## Success Standard

A successful step should leave at least one concrete artifact:

- shell JSON output with experiment metrics
- profiler trace or CSV
- sync log tail
- remote file listing
- fetched result file ready for insertion into the disclosure
