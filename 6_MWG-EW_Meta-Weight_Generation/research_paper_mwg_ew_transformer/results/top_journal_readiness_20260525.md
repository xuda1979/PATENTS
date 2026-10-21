# MWG-EW Top-Journal Readiness Plan

Date: 2026-05-25

This note tracks the current publishability path for the MWG-EW Transformer
paper. It deliberately separates runnable engineering steps from claims that
are not yet justified.

## Publication Standard

The paper should not claim top-journal readiness until all of the following are
true:

1. Broad held-out evaluation passes on explicit corpora with no
   `DEFAULT_TEXTS` fallback.
2. Router evaluation is repeated across multiple seeds on disjoint train/eval
   text splits.
3. The calibrated MWG layer-16 checkpoint beats a same-rank persistent
   low-rank baseline on broad held-out corpora, not only BELLE.
4. Results include at least one stronger algorithmic baseline beyond static SVD
   and the existing persistent low-rank layer-16 control.
5. Systems claims are backed by fused-kernel or hardware-counter evidence for
   descriptor lifecycle, not only software byte estimates.
6. The paper text only claims what the broad evidence supports.

## Steps And Execution Status

1. Restore ASI3 access and use the exact `ASI3` environment.
   Status: done. Remote shell works through the Huanxin daemon.

2. Populate `/vllm-workspace/mwg-ew-transformer-research` on ASI3.
   Status: done. Code, scripts, paper files, and held-out corpora are present.

3. Verify model and held-out data.
   Status: done. Model directory is
   `/root/work/filestorage/Qwen2.5-1.5B-Instruct`; held-out files are present
   under `data/heldout`.

4. Regenerate the missing layer-16 rank-384 checkpoint with explicit text.
   Status: done. Launched
   `asi3_layer16_recovery_20260525T102958Z` with
   `LMCE_TEXTS=data/heldout/router_train.txt` and
   `HYBRID_TEXTS=data/heldout/router_eval.txt`. The calibrated checkpoint path
   is:
   `results/asi3_layer16_recovery_20260525T102958Z/layer16/checkpoints/mwg_expert_residual_r384_belle_lmce_cal_1200.pt`.

5. Launch broad held-out validation with the exact checkpoint path.
   Status: done. Status file:
   `logs/asi3_broad_validation_20260525T103501Z.status.json`. The result is
   negative on all three manifest suites.

6. Launch deployable router validation with disjoint train/eval files.
   Status: done for three launched runs:
   `logs/asi3_router_validation_20260525T103501Z.status.json`,
   `logs/asi3_router_validation_20260525T104452Z.status.json`, and
   `logs/asi3_router_validation_20260525T104654Z.status.json`.

7. Pull ASI3 result JSON/log/status files back locally.
   Status: done for compact summaries. The broad summary, broad status, and
   compact validation summary were pulled or reconstructed from the remote
   compact export under `results/pulled_asi3/asi3_validation_20260525/`.

8. Update `paper/main.tex`.
   Status: done for the 2026-05-25 evidence. The paper is framed as a
   feasibility and negative-control study, not a deployment-ready result.

9. Add hardware-counter/fused-kernel evidence.
   Status: partially done as a negative/operator-level probe, but still pending
   for full systems validation. ASI3 run
   `asi3_runtime_profiler_probe_20260525T192357Z` captured dense, `mwg_r128`,
   and `mwg_r256` operator summaries on an environment with 8 visible Ascend
   910B2 NPUs, `npu-smi`, and `msprof`. The PyTorch profiler exposed CPU
   activities only, observed no fused-like MWG operator, and explicitly marks
   `hardware_counter_complete=false`.

10. Run same-rank persistent low-rank broad baseline.
    Status: done. The first launch
    `asi3_persistent_broad_baseline_20260525T114206Z` failed because launcher
    variable `RANK` collided with distributed runtime state and became zero.
    The fixed launcher uses `BASELINE_RANK`; run
    `asi3_persistent_broad_baseline_20260525T114920Z` trained
    `persistent_low_rank_r384.pt` from explicit `router_train.txt` activations
    and launched broad validation
    `asi3_broad_validation_20260525T115053Z`.

11. Add a stricter token-level dense-fallback router.
    Status: done for one ASI3 run. Added
    `experiments/mwg_token_router_gate_eval.py`,
    `scripts/launch_asi3_token_router_validation_detached.sh`, and daemon-only
    upload helper `scripts/ASI3_daemon_upload_files.js`. Launched
    `asi3_token_router_validation_20260525T125011Z` with explicit
    `router_train.txt`, disjoint `router_eval.txt`, and the exact layer-16
    r384 LM-CE checkpoint. The run evaluates actual mixed dense/patch forward
    passes rather than offline oracle loss mixing.

12. Run token-router cross-validation splits.
    Status: done. Added `experiments/prepare_router_cv_splits.py` and
    `scripts/launch_asi3_token_router_cv_detached.sh`. The CV prep pools the
    512 unique lines from `router_train.txt` and `router_eval.txt`, then writes
    three explicit non-overlapping train/eval folds under
    `data/heldout/router_cv/seed{0,1,2}`. ASI3 run
    `asi3_token_router_cv_20260525T131335Z` completed with the exact layer-16
    r384 checkpoint and actual mixed-forward token-router evaluation.

13. Run leakage-clean broad token-router validation.
    Status: done. Added `experiments/prepare_router_broad_splits.py` and
    `scripts/launch_asi3_token_router_broad_detached.sh`. Split preparation
    removed exact overlap between the router train pool and each broad eval
    suite before training: 196 GSM8K lines, 136 MBPP lines, and 180 Alpaca-tail
    lines were removed. After fixing a launcher quoting bug in the first failed
    attempt (`asi3_token_router_broad_20260525T141442Z`), run
    `asi3_token_router_broad_20260525T141738Z` completed with the exact
    layer-16 r384 checkpoint, `--require-texts`, and actual mixed-forward
    token-router evaluation.

14. Repeat leakage-clean broad token-router validation across split seeds.
    Status: done for three explicit broad split seeds. Added
    `scripts/launch_asi3_token_router_broad_seed_sweep_detached.sh` and used
    `experiments/prepare_router_broad_splits.py --seed --train-fraction 0.75`
    for each seed. ASI3 run
    `asi3_token_router_broad_seed_sweep_20260525T161810Z` completed with the
    exact layer-16 r384 checkpoint, `--require-texts`, and actual mixed-forward
    token-router evaluation. The aggregate summary and status were fetched
    locally through the daemon-only SHA-verified fetch helper.

15. Run leave-suite-out broad auxiliary router seed sweep.
    Status: done for three explicit split seeds. Added
    `experiments/prepare_router_leave_suiteout_splits.py` and
    `scripts/launch_asi3_token_router_leave_suiteout_seed_sweep_detached.sh`.
    For each target broad suite, the router train set uses explicit
    `router_train.txt`, `router_eval.txt`, and the other two broad suites, with
    exact target-suite eval lines removed. ASI3 run
    `asi3_token_router_leave_suiteout_seed_sweep_20260525T171658Z` completed
    with the exact layer-16 r384 checkpoint, `--require-texts`, and actual
    mixed-forward token-router evaluation. The aggregate summary and status
    were fetched locally through the daemon-only SHA-verified fetch helper.

16. Run initial ASI3 runtime profiler probe.
    Status: done for operator-level evidence. Added
    `experiments/mwg_runtime_profiler_probe.py` and
    `scripts/launch_asi3_runtime_profiler_probe_detached.sh`, uploaded them to
    ASI3 via daemon-only SHA-verified upload, and launched
    `asi3_runtime_profiler_probe_20260525T192357Z` with
    `D=2048 M=5504 RANKS=128,256 BATCH=1 SEQ=128 MODE=forward`. The result
    was fetched locally as
    `results/pulled_asi3/asi3_validation_20260525/runtime_profiler_probe_20260525T192357Z.latest.json`.

17. Add a stronger same-rank persistent low-rank LM-CE baseline.
    Status: launcher ready, remote launch pending daemon availability. Added
    `scripts/launch_asi3_persistent_lmce_baseline_detached.sh` to calibrate the
    existing same-rank persistent low-rank checkpoint with the same direct
    LM-CE objective used for the strongest MWG checkpoint, using explicit
    `router_train.txt`, `--require-texts`, and the broad manifest. This tests
    whether the observed MWG advantage survives a fairer durable low-rank
    calibration baseline. The local script passed `bash -n`; ASI3 launch was
    not attempted because the daemon-required health probe reported that the
    `ASI3` daemon was not available.

18. Audit broad held-out family coverage.
    Status: done locally. Added `experiments/audit_heldout_manifest.py` and
    generated `results/heldout_manifest_audit_20260525.{json,md}`. The current
    explicit manifest covers math reasoning, code generation, and instruction
    following, but it is missing general language modeling, commonsense
    reasoning, multi-turn dialogue, and long-context families. The earlier
    Wikitext preparation failure remains recorded in provenance. This means the
    current manifest is useful broad stress testing, but not sufficient for a
    broad-family top-journal claim.

19. Prepare additional held-out families.
    Status: script added, data fetch blocked locally. Added
    `experiments/prepare_extra_heldout_families.py`, which writes extra-family
    corpora into `data/heldout_extra` without modifying the main manifest and
    records all failures in `provenance_extra.json`. A local partial run
    attempted Wikitext103 validation, HellaSwag validation, DailyDialog
    validation, and Qasper validation for general LM, commonsense, dialogue,
    and long-context coverage. All four failed because Hugging Face dataset
    access timed out or was refused, leaving `manifest_extra.json` empty and
    `provenance_extra.json` as the machine-readable blocker record.

20. Preserve an offline path for extra held-out corpora.
    Status: done locally, with no new broad-family evidence yet. The ASI3
    daemon-only health probe still reports that the `ASI3` daemon is unavailable,
    so the persistent LM-CE baseline remains unlaunched. Local and S3 discovery
    found no usable Wikitext/HellaSwag/DailyDialog/Qasper-style text corpora
    beyond the existing empty `heldout_extra` blocker record; the Wikitext hits
    under `/Users/daxu/papers/energy_efficient_ai` are training scripts and
    result summaries, not raw validation text. Updated
    `experiments/prepare_extra_heldout_families.py` with an explicit
    `--local-text name=family=/path/to/text.txt` ingestion path and `--skip-hf`
    offline mode, preserving minimum-size checks and provenance recording. A
    temporary local-source smoke run passed and did not modify
    `data/heldout_extra`.

21. Audit main and extra held-out manifests together.
    Status: done locally. Extended `experiments/audit_heldout_manifest.py` with
    an explicit `--include-extra` mode that loads `data/heldout_extra` as a
    separate source, honors the `family` field supplied by extra manifests, and
    reports source-qualified dataset failures and overlap checks. Generated
    `results/heldout_manifest_audit_with_extra_20260525.{json,md}`. The
    combined audit currently has three main suites, zero extra suites, and five
    recorded dataset failures, so `ready_for_broad_family_claim=false` remains
    the correct boundary.

22. Guard the pending persistent LM-CE baseline launch.
    Status: done locally; remote launch still blocked by daemon availability.
    Added `scripts/launch_asi3_persistent_lmce_baseline_when_ready.sh`, a
    daemon-only wrapper that first probes `ASI3`, then uploads/chmods
    `scripts/launch_asi3_persistent_lmce_baseline_detached.sh` with
    SHA-verified daemon upload, and finally launches the exact explicit
    `TRAIN_TEXTS`, `MANIFEST`, `BASE_CKPT`, and `LMCE_STEPS=1200` command. A
    local guard test passed: with the current unavailable daemon, the wrapper
    exits at `ASI3_HEALTH_OK` and performs no upload or remote launch.

23. Add a daemon-only persistent-baseline monitor helper.
    Status: done locally; no remote query was possible while the daemon is
    unavailable. Added `scripts/monitor_asi3_persistent_lmce_baseline.sh`, which
    accepts a persistent LM-CE run id and uses `scripts/ASI3_shell.sh` to emit a
    JSON snapshot of remote status, wrapper-log tail, result JSON paths,
    checkpoint count, and any nested broad-validation run id parsed from
    `broad_validation_launch.txt`. The helper refuses browser fallback and does
    not fetch checkpoints. Local `bash -n` passed; a dummy run-id smoke test
    stopped at the same daemon-unavailable guard.

24. Harden the persistent LM-CE launch guard against local daemon contention.
    Status: done locally after the daemon briefly returned. The guarded
    launcher reached `ASI3_HEALTH_OK`, but daemon upload timed out while another
    local `huanxin_shell_exec.js ASI3 --require-daemon` process was running an
    unrelated ALPHAQUBIT command. No MWG upload or launch completed. Updated
    `scripts/launch_asi3_persistent_lmce_baseline_when_ready.sh` to fail early
    if a local ASI3 daemon shell command is already running before the health
    check, or appears between health and upload. Also added a bounded health
    retry for the known recoverable `stale_daemon_state_recovered` response.

25. Launch persistent LM-CE baseline when daemon became available.
    Status: completed on ASI3. The guarded daemon-only wrapper passed
    `ASI3_HEALTH_OK`, SHA-verified upload of
    `scripts/launch_asi3_persistent_lmce_baseline_detached.sh`, and launched
    `asi3_persistent_lmce_baseline_20260526T024239Z` with pid 27467. Config:
    `TRAIN_TEXTS=/vllm-workspace/mwg-ew-transformer-research/data/heldout/router_train.txt`,
    `MANIFEST=/vllm-workspace/mwg-ew-transformer-research/data/heldout/manifest.json`,
    `BASE_CKPT=/vllm-workspace/mwg-ew-transformer-research/results/asi3_persistent_broad_baseline_20260525T114920Z/checkpoints/persistent_low_rank_r384.pt`,
    and `LMCE_STEPS=1200`. First daemon-only monitor snapshot showed model
    weights loaded and LM-CE calibration events through at least step 60; no
    nested broad-validation run had launched yet. A later daemon-only monitor
    showed status `done`, one calibrated checkpoint, and one LM-CE JSON.

26. Evaluate persistent LM-CE baseline on the broad manifest.
    Status: completed on ASI3 but only partially fetched locally. The persistent
    LM-CE launcher spawned broad validation run
    `asi3_broad_validation_20260526T024509Z` with pid 27796, using
    `results/asi3_persistent_lmce_baseline_20260526T024239Z/checkpoints/persistent_low_rank_r384_lmce.pt`.
    The daemon status/log query showed a negative broad result:
    token-weighted PPL ratio 1.3099 over 91,352 tokens and max suite ratio
    1.4504. The visible per-suite rows include MBPP ratio 1.0338 over 13,301
    tokens and Alpaca-tail ratio 1.2317 over 33,343 tokens; the max ratio
    corresponds to the remaining GSM8K suite. This fairer direct-LM-CE
    persistent low-rank baseline is still negative and does not close the gap to
    the bounded selective-router evidence. Local daemon fetch succeeded only for
    `asi3_persistent_lmce_baseline_20260526T024239Z.status.json`; fetching the
    larger LM-CE JSON and broad summary/status timed out through the sticky
    daemon, so those artifacts still need a later SHA-verified fetch.

27. Define the K/V projection claim boundary.
    Status: done locally. Added
    `results/mwg_kv_claim_boundary_20260528.md` to separate the architectural
    motivation from confirmed real-LM evidence. K/V projection matrices remain
    natural MWG targets because they are large projection paths, and local
    synthetic attention probes show signal for V and K+V: K always residual
    improves 0.281%, V always residual improves 1.431%, K+V always residual
    improves 1.567%, and supervised K+V routing improves 0.286%, 0.682%, and
    0.879% at 10%, 25%, and 50% budgets. The safe boundary is that current
    real-LM ASI3 evidence validates bounded selective routing around the
    layer-16 checkpoint, not a clean K/V replacement claim on held-out
    Transformer benchmarks.

28. Prepare a global suite-aware router split.
    Status: done locally. Added
    `experiments/create_global_router_split_manifest.py` and generated
    `data/heldout/router_global_splits/manifest.json`, plus audit artifacts
    `results/router_global_split_audit_20260528.{json,md}`. The manifest has
    357 train and 357 eval unique rows with zero train/eval overlap, balanced
    across GSM8K, MBPP, and Alpaca-tail. This enables a cleaner combined
    suite-aware router run with `--suite-split-manifest`,
    `--suite-balanced-sampling`, `--suite-balanced-ridge`, and
    `--fail-on-suite-overlap`. It is not new independent broad-family evidence;
    it is a safer repartition of the existing math/code/instruction manifest.

29. Add a detached launcher for the global suite-aware router run.
    Status: done locally; not launched on ASI3. Added executable script
    `scripts/launch_asi3_token_router_global_suite_balanced_detached.sh`.
    The launcher runs `experiments/mwg_token_router_gate_eval.py` once against
    `data/heldout/router_global_splits/manifest.json` using
    `--suite-split-manifest`, `--suite-balanced-sampling`,
    `--suite-balanced-ridge`, `--fail-on-suite-overlap`, and `--require-texts`.
    It preserves the exact checkpoint through required `PATCH=...`, writes
    `logs/asi3_token_router_global_suite_balanced_*.status.json`, and emits
    `results/asi3_token_router_global_suite_balanced_*/token_router_global_suite_balanced.json`.
    Local `bash -n` passed. This should be uploaded/launched only after the
    `ASI3` daemon health guard allows fresh commands; no browser fallback is
    needed or allowed.

30. Add a daemon-only guarded launcher for the global suite-aware router run.
    Status: done locally; not executed. Added executable script
    `scripts/launch_asi3_token_router_global_suite_balanced_when_ready.sh`.
    It follows the persistent-baseline guard pattern: refuses
    `ASI3_ALLOW_BROWSER=1`, sets `HUANXIN_ALLOW_STANDALONE_FALLBACK=0`, checks
    that no local `huanxin_shell_exec.js ASI3 --require-daemon` command is
    already active, probes `scripts/ASI3_shell.sh "printf ASI3_HEALTH_OK"` with
    bounded retries for recoverable stale-daemon responses, uploads the
    detached launcher through `scripts/ASI3_daemon_upload_files.js`, and then
    launches it with explicit `SPLIT_MANIFEST`, `PATCH`, and `LAYER`. Local
    `bash -n` passed. This wrapper is the preferred entry point when the daemon
    becomes healthy, but it should not be run while the health guard reports a
    busy, pending, or incomplete command state.

31. Harden the guarded global-router launcher dependency upload.
    Status: done locally; not executed. Updated
    `scripts/launch_asi3_token_router_global_suite_balanced_when_ready.sh` so
    the daemon upload step sends the detached launcher, the current
    `experiments/mwg_token_router_gate_eval.py`, the global split manifest, and
    all six train/eval text files referenced by that manifest. A local manifest
    dependency check found six unique split text paths and no missing files;
    local `bash -n` passed. This prevents a stale remote evaluator or missing
    `data/heldout/router_global_splits/*/router_{train,eval}.txt` file from
    invalidating the next suite-balanced run.

32. Add a daemon-only guarded fetch wrapper for persistent LM-CE artifacts.
    Status: done locally; not executed. Added executable script
    `scripts/fetch_asi3_persistent_lmce_artifacts_when_ready.sh`, which refuses
    browser fallback, checks for an idle `ASI3` daemon shell path, probes
    `scripts/ASI3_shell.sh "printf ASI3_HEALTH_OK"` with bounded stale-daemon
    retries, and then uses `scripts/ASI3_daemon_fetch_files.js` to SHA-verify
    three artifacts: `logs/asi3_broad_validation_20260526T024509Z.status.json`,
    `results/asi3_broad_validation_20260526T024509Z/summary_broad_eval.json`,
    and
    `results/asi3_persistent_lmce_baseline_20260526T024239Z/persistent_low_rank_r384_lmce.json`.
    Local `bash -n` passed. The broad status and broad summary are already
    present locally under `results/pulled_asi3/asi3_validation_20260525/`; the
    persistent calibration JSON remains missing locally and is the main reason
    to run this wrapper when the daemon is clean.

33. Record exact next daemon-safe actions.
    Status: done locally. Added
    `results/asi3_next_daemon_safe_actions_20260529.md`, a compact checklist
    for the next healthy `ASI3` daemon window. It names only two preferred
    script-only actions: the guarded persistent-LMCE artifact fetch and the
    guarded global suite-balanced router launch. It repeats the no-browser,
    no-fallback, no-relaunch, explicit-text, and daemon-health guardrails, and
    records the local global-split audit totals.

34. Validate local suite-balanced router launch hygiene.
    Status: done locally. Added
    `results/local_suite_balanced_router_hygiene_20260529.md`. Python compile
    checks passed for the token-router evaluator, global split creator, and
    router split auditor. Shell syntax checks have passed for the detached
    global router launcher, guarded global router launcher, and guarded
    persistent-LMCE fetch wrapper. The global split manifest still references
    six existing train/eval files with expected row counts: GSM8K 130/130,
    MBPP 97/97, and Alpaca-tail 130/130. No ASI3 command, upload, fetch, or
    browser action was run for this check.

35. Refresh broad-family blocker audit.
    Status: done locally. Added
    `results/local_broad_family_blocker_audit_20260529.md` and regenerated
    `results/heldout_manifest_audit_with_extra_20260529.{json,md}` with
    `--include-extra`. The audit still has only math_reasoning,
    code_generation, and instruction_following suites; extra manifest suite
    count remains zero. Missing recommended families remain
    general_language_modeling, commonsense_reasoning, multi_turn_dialogue, and
    long_context. Recorded dataset-access failures total five, so
    `ready_for_broad_family_claim=false` remains the correct boundary.

36. Add conservative suite-aware router threshold policy.
    Status: done locally. Added `--threshold-policy` to
    `experiments/mwg_token_router_gate_eval.py` with default `global` behavior
    preserved for existing launchers. New policies include `suite_min`,
    `suite_mean`, and `suite_median`; `suite_min` selects the strictest
    per-suite train-score quantile and is intended to reduce over-patching on
    suite-balanced robustness runs. Updated
    `scripts/launch_asi3_token_router_global_suite_balanced_detached.sh` to
    default to `THRESHOLD_POLICY=suite_min`. Added
    `tests/test_token_router_threshold_policy.py` and
    `results/local_router_threshold_policy_20260529.md`. Verification passed:
    `python3 -m pytest -q tests/test_token_router_threshold_policy.py` reported
    `3 passed`; `python3 -m py_compile experiments/mwg_token_router_gate_eval.py`
    and `bash -n scripts/launch_asi3_token_router_global_suite_balanced_detached.sh`
    also passed. No ASI3 command, upload, fetch, or browser action was run.

## Current Claim Boundary

The strongest always-patched algorithmic result remains layer-16 rank-384
direct LM-CE calibration: BELLE held-out ratio 1.1799 over 51,267 tokens,
diverse64 ratio 1.0870, heldout12 ratio 1.0405, and a same-rank persistent
low-rank BELLE baseline worse at 1.3729. The strongest new broad evidence is
selective rather than always-patched: leakage-clean token routing repeats a
small token-weighted broad gain across three split seeds at limited patch
fractions. Together these are promising but still not enough for a top-journal
deployment claim.

The K/V projection story should be framed as a next scaling target, not as a
validated real-LM result. Local attention-path probes support V and K+V as
plausible MWG targets, but the paper should not claim broad K/V replacement,
K/V perplexity improvement, latency improvement, or off-chip traffic reduction
until those are shown with real held-out LM experiments and hardware-counter or
fused-kernel evidence.

The next router-training milestone is now a suite-aware combined split rather
than another per-suite split. The prepared global split has no train/eval row
overlap and should be used for target-0.25 robustness work once ASI3 is healthy,
while preserving `--require-texts` and explicit manifest paths.

## ASI3 Broad/Router Results From 2026-05-25

The new broad validation is negative for a top-journal deployment claim. The
layer-16 r384 LM-CE checkpoint degrades all three explicit manifest suites:

| Suite | Tokens | Dense PPL | Patched PPL | Ratio |
| --- | ---: | ---: | ---: | ---: |
| gsm8k_test | 44,708 | 3.4941 | 4.7481 | 1.3589 |
| mbpp_test | 13,301 | 3.9877 | 4.5276 | 1.1354 |
| alpaca_cleaned_train_tail | 33,343 | 3.8818 | 4.4249 | 1.1399 |

Router validation completed for three launched runs. The runs are effectively
identical because the current ridge router is deterministic for these inputs.
Always-patched router-eval PPL ratio is about 2.0625. The deployable routed
frontier only stays close to dense at a very small actual patch-token fraction:
target 0.10 patches about 1.69% of tokens with PPL ratio about 1.0129; target
0.25 patches about 3.45% with ratio about 1.0273; target 0.50 patches about
14.53% with ratio about 1.1411. This is useful as a negative control and a
direction for risk-aware routing, but it is not yet a strong systems-quality
tradeoff.

The stricter token-level router confirms this limitation with real mixed
forwards. It was trained on token CE deltas from `router_train.txt`, where the
patch looked favorable (`patched_ppl_ratio=0.4366` over 30,053 tokens), but on
held-out `router_eval.txt` the same patch was unfavorable
(`patched_ppl_ratio=2.0616` over 35,118 tokens). The mixed-forward frontier
stays close to dense only at tiny patch fractions: target 0.01 patches about
0.38% of tokens with PPL ratio 1.0132; target 0.03 patches about 1.24% with
ratio 1.0249; target 0.05 patches about 1.93% with ratio 1.0360; target 0.10
patches about 3.63% with ratio 1.0508. Higher patch fractions degrade quickly:
target 0.25 patches about 9.47% with ratio 1.1665, and target 0.50 patches
about 24.85% with ratio 1.6013. This is strong negative evidence for current
router generalization and a useful next-step target for risk-aware training.

The follow-up three-fold token-router CV run is more encouraging but still
bounded. It pools the two router corpora into 512 unique lines and repartitions
them into three explicit 256/256 train/eval folds. Mean mixed-forward PPL ratios
over the three folds are: target 0.01 patches 0.09% tokens ratio 0.9989; target
0.03 patches 0.38% ratio 0.9940; target 0.05 patches 0.75% ratio 0.9896; target
0.10 patches 1.93% ratio 0.9787; target 0.25 patches 6.95% ratio 0.9462; target
0.50 patches 17.66% ratio 0.9218. This suggests the router can find
patch-favorable subsets inside the router corpus distribution, but it is not
independent broad evidence and does not overturn the negative GSM8K/MBPP/Alpaca
manifest. The next publishability step is distribution-robust router training
and evaluation on broad held-out corpora with real repeated seeds/splits.

The leakage-clean broad token-router run is the strongest router evidence so
far, while still requiring conservative wording. Each broad suite gets its own
router train file with exact eval-line overlaps removed. Always-patched remains
negative on every suite: GSM8K ratio 1.3238, MBPP ratio 1.1131, and Alpaca-tail
ratio 1.1100. Selective routing is different: the token-weighted broad frontier
over 89,188 evaluated tokens is approximately target/actual/ratio =
0.01/0.05%/1.0010, 0.03/0.19%/1.0008, 0.05/0.55%/0.9989,
0.10/2.08%/0.9916, 0.25/8.49%/0.9868, and 0.50/19.75%/1.0140. The target 0.25
row is the most useful point: a small token-weighted gain while patching about
8.5% of tokens, though the max suite ratio is still 1.0038 and GSM8K worsens at
some higher patch fractions. This supports a bounded risk-aware routing claim,
not a broad always-patched quality-preservation claim.

The three-seed leakage-clean broad token-router sweep strengthens that bounded
claim. With `TRAIN_FRACTION=0.75` over split seeds 0, 1, and 2, the mean
token-weighted broad frontier is target/actual/ratio =
0.01/0.07%/1.0011, 0.03/0.21%/0.9998, 0.05/0.49%/0.9977,
0.10/1.82%/0.9920, 0.25/8.52%/0.9864, and 0.50/21.68%/1.0164. The target
0.05, 0.10, and 0.25 rows are below dense for all three seeds; target 0.50 is
unstable, with seed-level token-weighted ratios spanning 0.9943 to 1.0312.
This is now real multi-split broad evidence for selective routing at limited
patch fractions, but it still does not rescue always-patched broad replacement
or remove the need for stronger baselines and hardware evidence.

The leave-suite-out broad auxiliary sweep is a stronger distribution-robust
check because each target suite is excluded from the broad auxiliary train set.
For each seed, GSM8K uses 340 of 454 overlap-clean train candidates, MBPP uses
390 of 520, and Alpaca-tail uses 340 of 454; the candidate pool is
`router_train.txt`, `router_eval.txt`, and the two non-target broad suites.
The three-seed mean frontier is target/actual/ratio =
0.01/0.43%/1.0007, 0.03/1.66%/0.9989, 0.05/2.84%/0.9975,
0.10/5.65%/0.9926, 0.25/13.80%/0.9943, and 0.50/28.06%/1.0274. Target 0.05
and 0.10 are below dense on every seed; target 0.25 is below dense on average
but has one near-neutral/slightly-worse seed; target 0.50 degrades on all
seeds. This strengthens the bounded selective-router claim while preserving
the conclusion that broad always-patched replacement is not supported.

The same-rank persistent low-rank baseline was retrained with explicit
`router_train.txt` activation text and evaluated through the same manifest
guardrail. It is also negative: gsm8k_test ratio 1.2939 over 31,329 tokens,
mbpp_test ratio 1.3026 over 12,850 tokens, and alpaca_cleaned_train_tail ratio
1.2464 over 22,694 tokens, for a token-weighted ratio of 1.2795 over 66,873
tokens. Token counts differ from the MWG broad run, so this should be cited as
a separate broad negative baseline rather than a token-identical paired
comparison.

The initial runtime profiler probe is negative for fused-kernel claims and
useful for claim hygiene. ASI3 reported 8 visible Ascend 910B2 NPUs,
`torch_npu=2.9.0`, `npu-smi`, and `msprof`, but the PyTorch profiler captured
CPU activities only. Dense used a 64.50 MiB descriptor estimate and averaged
0.3391 ms in the microprobe; `mwg_r128` used a 5.53 MiB descriptor estimate
and averaged 0.7638 ms; `mwg_r256` used an 11.06 MiB descriptor estimate and
averaged 0.7559 ms. The MWG cases doubled the matmul-like op count from 27 to
54 and observed no fused-like operator. Therefore this supports the statement
that the current prototype is an unfused factor-matmul path, not that the
systems hypothesis has been validated with off-chip hardware counters.

Conclusion for the paper: keep the current conservative framing. Do not claim
that the layer-16 patch is broadly quality-preserving. The publishable story is
now sharper: always-patched MWG is negative on broad suites, but leakage-clean
token-level routing can selectively recover a small broad token-weighted gain at
limited patch fractions, and that selective result now repeats across three
broad split seeds and a leave-suite-out auxiliary broad protocol.
Quality-preserving ephemeral FFN replacement still needs stronger training,
stronger baselines, and hardware-counter/fused-kernel evidence before
top-journal deployment claims.

2026-05-30 update: added
`experiments/summarize_publishable_positive_regime.py` and regenerated
`results/publishable_positive_regime_20260530.{json,md}` from the pulled ASI3
result JSONs. The machine-generated boundary is now explicit: the current work
is ready to support a scoped positive case study around benefit-supervised
token-level selective routing with dense fallback, with stable positive targets
0.05 and 0.10. It is not ready for a broad top-journal claim that MWG works well
in all scenarios. The paper should present the negative always-patched and
persistent low-rank results as boundary evidence, not hide them.
