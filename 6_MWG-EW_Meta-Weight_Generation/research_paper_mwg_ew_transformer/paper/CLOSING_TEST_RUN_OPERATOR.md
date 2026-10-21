# Causal-Quality Closing Test (r401): Operator Runbook

**What this unlocks:** the paper's explicitly stated closing test for the
~2.3% parameter-matched gap. The frozen v1 causal-quality run
(`asi2_causal_quality_20260903T073816Z`) trained `token_diag_core` at r384 and
`persistent` at r401. This closing run **additionally trains `token_diag_core`
at r401**, giving a direct *equal-rank* (401=401) comparison that either
closes the gap (if the generated core reaches parity with the persistent r401
control at equal rank) or confirms the honest boundary at the higher rank.

## Status (2026-09-06)

- **COMPLETED.** The closing-test run `asi2_causal_quality_closing_20260906T135350Z`
  finished all three seeds (2026/2027/2028) and passed every launcher gate
  (`state=completed`, dense-teacher control exact, `evidence_mode` + `ASI2`
  labels, fingerprint-verified checkpoints including `mwg_token_diag_core_r401.pt`).
- **RESULT: the ~2.3% gap CLOSES at equal rank r401.** 3-seed mean relative-MSE:
  generated diagonal core r401 = **0.4362±0.0006** vs persistent r401 =
  **0.4359±0.0006** (and cosine 0.753 vs 0.753) — statistically indistinguishable,
  exactly as at r384. This confirms the gap was a **rank-allocation artifact,
  not an ephemerality penalty**. The result is integrated into all three
  manuscript vehicles (abstracts, causal-quality tables at r384+r401, three
  findings, Discussion, Conclusion, broader-impact).
- **Raw-artifacts caveat**: the 5.1 GB per-seed reports/checkpoints live on the
  original ASI2 worker pod's local `/vllm-workspace`. That pod is no longer the
  daemon's current node (the daemon reconnected to a different pod after restart),
  so the raw JSON/checkpoints are not currently co-located for further pull.
  The **verified numbers** are preserved locally in
  `results/asi2_causal_quality_closing_pull/VERIFIED_RESULT_RECORD.json` (read
  directly from the completed report); the frozen launcher + staged inputs are
  preserved, so the run is reproducible for re-pull or re-run.
- The frozen v1 oneshot's `push_file` had a base64 double-encode bug (now fixed
  in both oneshots) and did not stage the `create_quality_threeway_split`
  dependency; use the verified push helper in "Notes / caveats".

## How it differs from the frozen v1 run

Only one change, in a **separate, versioned launcher**, applied in exactly
three places (never mutating the frozen v1 `launch_ASI2_causal_quality_detached.sh`):

| Place | Change |
|---|---|
| Default `STUDENT_SPECS` | add `token_diag_core:${MATCHED_RANK}` |
| Preflight expected set | add `("token_diag_core", matched)` |
| Worker validation expected set | add `mwg_token_diag_core_r{matched}` |

`RUN_ID` defaults to `asi2_causal_quality_closing_<TS>` so it cannot collide
with the completed v1 run. All frozen inputs (data splits, seed set, model,
fp32, 5000 steps, 4 NPUs) are identical to v1; the new student is added to
the same evidence-mode, SHA-fingerprinted, gate-validated protocol.

## Launch (already done 2026-09-06; for re-launch / seed resume)

The worker is already running. To re-launch (e.g. after an interruption)
or for a fresh copy, use the correct staging helper (NOT the broken oneshot —
see Notes / caveats), then launch the detached worker:

```bash
# 0. Confirm the daemon is authenticated (must print ready=True)
curl -s http://127.0.0.1:19004/health | python3 -c "import sys,json;print('ready=',json.load(sys.stdin).get('ready'))"

# 1. Stage the code + frozen data on the remote with SHA-verified pushes
#    (use the correct push helper; the oneshot's push_file double-encodes)
ROOT=/vllm-workspace/mwg-ew-transformer-research
python3 /tmp/asi2_push.py experiments/mwg_quality_distillation.py        $ROOT/experiments/mwg_quality_distillation.py
python3 /tmp/asi2_push.py experiments/audit_quality_threeway_split.py    $ROOT/experiments/audit_quality_threeway_split.py
python3 /tmp/asi2_push.py experiments/create_quality_threeway_split.py   $ROOT/experiments/create_quality_threeway_split.py
python3 /tmp/asi2_push.py scripts/launch_ASI2_causal_quality_closing_detached.sh $ROOT/scripts/launch_ASI2_causal_quality_closing_detached.sh
python3 /tmp/asi2_push.py data/quality/train.txt  $ROOT/data/quality/train.txt
python3 /tmp/asi2_push.py data/quality/dev.txt    $ROOT/data/quality/dev.txt
python3 /tmp/asi2_push.py data/quality/test.txt   $ROOT/data/quality/test.txt
python3 /tmp/asi2_push.py data/quality/manifest.json $ROOT/data/quality/manifest.json

# 2. Preflight
python3 /tmp/asi2exec.py 'cd '$ROOT' && chmod +x scripts/*.sh && bash scripts/launch_ASI2_causal_quality_closing_detached.sh --check'

# 3. Launch detached worker
python3 /tmp/asi2exec.py 'cd '$ROOT' && env PROJECT_ROOT='$ROOT' nohup bash scripts/launch_ASI2_causal_quality_closing_detached.sh > /tmp/asi2_closing_launch.out 2>&1 < /dev/null & sleep 4; cat /tmp/asi2_closing_launch.out'

# 4. Monitor
python3 /tmp/asi2exec.py 'cat '$ROOT'/logs/asi2_causal_quality_closing_*.log | tail; ls -la '$ROOT'/results/asi2_causal_quality_closing_*/seed_*/progress.json'
```

## Notes / caveats

- **The frozen v1 oneshot's `push_file` has a base64 double-encode bug**: it
  writes the remote file as base64-of-base64 of the source (the remote file
  is base64-encoded Python, which won't run). Do not rely on
  `launch_ASI2_causal_quality_(*)_oneshot.sh` for staging; use the verified
  `/tmp/asi2_push.py` single-decode helper above (SHA-256 verified).
- **The oneshot does not stage the `create_quality_threeway_split.py`
  dependency** that `audit_quality_threeway_split.py` imports; it must be
  pushed too or the split preflight fails with `ModuleNotFoundError`.
- The run is `evidence_mode` + `env_label=ASI2`; every checkpoint/report is
  SHA-fingerprinted by the launcher gates, so the result is self-auditing.
- Expected duration: many hours (5000 steps x 3 seeds x 5 students on 4 NPUs).

## Verifying the result

When the run completes (all three seeds pass every launcher gate), the
decisive comparison is in each per-seed report under
`results/<run_id>/seed_<s>/`:

- `mwg_token_diag_core_r401` vs `persistent_low_rank_r401` (equal rank)
- If rel-MSE / cosine are statistically indistinguishable → **the ~2.3% gap
  is a rank-allocation effect, closed at equal rank r401**.
- Ingest via: `python3 scripts/ingest_causal_quality_results.py --pull-dir
  results/.../*pull*` (or the closing-run pull dir).

## Paper integration (if the gap closes)

Then the honest-boundary sentence in all three vehicles can be upgraded:
the generated core reaches equal-rank parity with the matched persistent
control at both r384 **and** r401, and the parameter-matched advantage of a
slightly-higher-rank persistent factor is explicitly tested and bounded.
Update `main.tex`, `tmlr/main_tmlr.tex`, and `iclr_parts/appendix_b.tex`
causal-quality tables/prose consistently, and re-verify all three builds
(0 undefined refs, 0 overfull) before submission.

## Do NOT

- Mutate `launch_ASI2_causal_quality_detached.sh` (frozen v1, SHA-verified).
- Change any frozen data split, seed, or the v1 result table.
- Re-run branch-skip / backward work in the same launch.
