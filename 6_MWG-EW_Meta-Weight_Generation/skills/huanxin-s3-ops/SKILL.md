---
name: huanxin-s3-ops
description: Operate Huanxin ai1 from this patent repo and move files between local disk, S3, and Huanxin using repo-local browser automation and shell helpers. Use when the user asks to access Huanxin, run experiments on ai1, inspect Huanxin auth or daemon state, or sync code and results through S3. This workspace targets the MWG-EW patent (Meta-Weight Generation for Ephemeral Weights).
---

# Huanxin + S3 Ops — MWG-EW Patent

Use Huanxin **ai1** for running real numerical experiments that support the patent disclosure.

## Environment

- Primary environment: `ai1`
- Remote workdir: `/root/work/mwg-ew-patent`
- S3 relay: `nm-aihuanxin:jtdlp-3ed7854b946a47b1a49ad754baa76cd3/mwg-ew-patent`

## Default Entry Point

```bash
scripts/ai1_shell.sh "cd /root/work/mwg-ew-patent && <command>"
```

This workspace includes a local `browser-automation/` bundle, so the shell wrapper is self-contained.

The transfer helpers are dual-mode:

- when run locally, they route through `scripts/ai1_shell.sh`
- when run inside `/root/work/mwg-ew-patent` on ai1, they execute `rclone` directly

## Long Jobs

Use background jobs and durable local handles:

```bash
scripts/ai1_job.sh start mwg-exp /tmp/mwg-exp.log "python3 experiments/run_real_benchmark.py"
scripts/ai1_job.sh status mwg-exp-20260414T000000Z
scripts/ai1_job.sh logs mwg-exp-20260414T000000Z 120
scripts/ai1_job.sh list
```

Use `scripts/ai1_job.sh` instead of raw `nohup` when you need a durable local job handle.

## Patent-Specific Experiment Rules

- All experimental results from ai1 are intended for direct inclusion in the patent disclosure (交底书).
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
- S3 -> ai1: `scripts/ai1_sync_from_s3.sh`
- ai1 -> S3: `scripts/ai1_push_results_to_s3.sh`
- S3 -> local: `scripts/pull_from_s3.sh`
- Run file remotely: `scripts/ai1_run_file.sh <relative-path>`

## Core Rules

- Read `TOOLS.md` first for workspace-specific values.
- Treat Huanxin browser automation as the control plane and S3 as the data plane.
- Prefer the repo's sync helpers over manual `rclone` or browser paste.
- Validate locally before any remote mutation.
- Use `--dry-run` first for large or risky transfers.
- Do not kill the browser daemon, discard the authenticated profile, or delete remote content unless explicitly instructed.

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
