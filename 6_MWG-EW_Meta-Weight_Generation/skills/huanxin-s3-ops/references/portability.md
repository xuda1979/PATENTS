# Portability Contract

This skill is designed to be shared across workspaces without leaking one workspace's Huanxin URL, S3 path, or browser-profile layout.

## What Must Stay Outside The Skill

Store these values in `TOOLS.md`, helper scripts, or local environment variables:

- canonical Huanxin train-dev URL
- valid environment names such as `ai1` and `ai2`
- default environment
- remote workdir per environment
- S3 remote root or prefix
- browser profile path
- daemon ports
- wrapper script locations

## Minimal `TOOLS.md` Template

```md
## Huanxin

- Train-dev route: `https://...#/train-dev`
- Available environments: `ai1`, `ai2`
- Default environment: `ai2`
- Remote root ai1: `/root/work/project`
- Remote root ai2: `/root/work/project`
- Generic shell wrapper: `scripts/huanxin_shell.sh`
- Status helper: `scripts/huanxin_status.sh`
- Profile repair helper: `scripts/repair_huanxin_browser_profile.sh`

## S3 Relay

- S3 root: `remote-name:bucket-or-prefix/project-root`
- Local -> S3 helper: `scripts/push_to_s3.sh`
- S3 -> local helper: `scripts/pull_from_s3.sh`
- ai1 sync helper: `scripts/ai1_sync_from_s3.sh`
- ai2 sync helper: `scripts/ai2_sync_from_s3.sh`
- ai1 push-back helper: `scripts/ai1_push_results_to_s3.sh`
- ai2 push-back helper: `scripts/ai2_push_results_to_s3.sh`
```

## Recommended Script Contract

For a workspace to use this skill smoothly, the local repo should provide:

- one generic shell wrapper that accepts `<env> "<cmd>"`
- optional env-specific shortcuts
- one local push helper
- one local pull helper
- one per-env sync-from-S3 helper
- one per-env push-results-to-S3 helper
- optional status or repair helpers

## Sharing Guidance

- Share the `skills/huanxin-s3-ops/` folder.
- Share wrapper scripts only if the receiving workspace does not already have equivalents.
- Do not publish personal cookies, profile directories, auth dumps, or private bucket credentials.
- If the receiving workspace uses different script names, update `TOOLS.md` there rather than cloning your personal notes into the skill.
