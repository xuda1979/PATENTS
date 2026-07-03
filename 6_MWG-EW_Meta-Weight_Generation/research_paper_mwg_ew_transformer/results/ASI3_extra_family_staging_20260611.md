# ASI3 extra-family staging status, 2026-06-11

## Verified local artifacts

- Extra held-out suites are available in `data/heldout_extra`:
  - `wikitext103_validation_extra.txt`: 260 examples, 171,078 non-newline characters.
  - `hellaswag_validation_extra.txt`: 260 examples, 97,066 non-newline characters.
- Corrected manifest/provenance:
  - `data/heldout_extra/manifest_extra.json`
  - `data/heldout_extra/provenance_extra.json`
- Five-suite broad manifest:
  - `data/heldout/manifest_with_extra.json`
  - suites: GSM8K, MBPP, Alpaca-tail, Wikitext-103 validation, HellaSwag validation.
- Five-suite router split:
  - `data/heldout/combined_extra_splits/manifest.json`
  - deterministic seed: 20260611
  - train/eval split: 50/50 per suite.

## Code changes

- Added `experiments/create_suite_split_manifest.py`, a lightweight deterministic splitter that avoids importing torch.
- Updated ASI3 task launchers to require `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` from the environment instead of embedding defaults.

## Upload status

The staged manifests, extra-family text files, splitter, and ASI3 task scripts were uploaded to the INER/Huanxin S3 relay with:

```bash
bash scripts/push_ASI3_code_to_s3.sh \
  experiments/create_suite_split_manifest.py \
  data/heldout/manifest_with_extra.json \
  data/heldout/combined_extra_splits \
  data/heldout_extra/manifest_extra.json \
  data/heldout_extra/provenance_extra.json \
  data/heldout_extra/wikitext103_validation_extra.txt \
  data/heldout_extra/hellaswag_validation_extra.txt \
  scripts/submit_ASI3_token_router_global_task.sh \
  scripts/submit_ASI3_scaled_sweep_task.sh \
  scripts/remote_ASI3_token_router_global_payload.sh
```

## Current ASI3 execution blocker

- `scripts/ASI3_shell.sh` still fails before remote command execution:
  - `getShellVisitUrl code=170022`
  - frontend websocket falls through to `wss://aihuanxin.cn/kunlun/null`
- The safer task launcher dry-run now correctly fails fast unless S3 credentials are supplied in the environment:
  - `AWS_ACCESS_KEY_ID must be set in the environment`

## Next evidence-producing run

Run the calibrated layer-16 checkpoint on:

- broad PPL: `data/heldout/manifest_with_extra.json`
- router/global replication: `data/heldout/combined_extra_splits/manifest.json`
- ASI3 NPU use: at most two NPUs concurrently.

Do not add five-suite quantitative claims to the paper until this evaluation completes.
