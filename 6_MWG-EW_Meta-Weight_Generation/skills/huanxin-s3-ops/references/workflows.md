# Workflow Recipes

Use the repo's helper scripts first. The exact script names and roots should come from `TOOLS.md`.

## Health Check

```bash
bash scripts/huanxin_status.sh
node browser-automation/huanxin_probe.js
```

Use the probe only when the wrapper path is failing or auth state is unclear.

## Run A Remote Command

```bash
bash scripts/huanxin_shell.sh ai1 "cd /root/work/project && pwd && whoami"
bash scripts/huanxin_shell.sh ai2 "cd /root/work/project && ls -la"
```

Prefer the generic shell wrapper over lower-level browser commands.

## Local -> S3

```bash
bash scripts/push_to_s3.sh --dry-run scripts skills
bash scripts/push_to_s3.sh scripts skills
```

Push only the paths you need unless the workspace explicitly wants a broad sync.

## S3 -> Huanxin

```bash
bash scripts/ai1_sync_from_s3.sh --dry-run
bash scripts/ai1_sync_from_s3.sh

bash scripts/ai2_sync_from_s3.sh --dry-run
bash scripts/ai2_sync_from_s3.sh
```

Use the env-specific helper that matches the target environment.

## Huanxin -> S3

```bash
bash scripts/ai1_push_results_to_s3.sh --dry-run outputs reports
bash scripts/ai1_push_results_to_s3.sh outputs reports

bash scripts/ai2_push_results_to_s3.sh --dry-run outputs reports
bash scripts/ai2_push_results_to_s3.sh outputs reports
```

Remote uploads often need `--s3-no-check-bucket`. The helper should own that detail.

## S3 -> Local

```bash
bash scripts/pull_from_s3.sh --dry-run reports
bash scripts/pull_from_s3.sh reports
```

## Recommended End-To-End Pattern

1. Validate locally.
2. `push_to_s3.sh` the changed code or assets.
3. `ai1_sync_from_s3.sh` or `ai2_sync_from_s3.sh`.
4. Run the remote command with `huanxin_shell.sh`.
5. Push results back with the matching `*_push_results_to_s3.sh`.
6. Pull results locally with `pull_from_s3.sh`.

## Failure Handling

- If the Huanxin shell wrapper fails, check the workspace status helper first.
- If auth is stale, use the repo's repair or login path instead of inventing a new URL flow.
- If an S3 upload from Huanxin fails on bucket checks, use the repo helper instead of raw `rclone`.
- If a workspace has inconsistent remote roots, trust the current helper script defaults over old notes.
