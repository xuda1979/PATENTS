# ASI2 Next Experiment Plan - 2026-06-01

Purpose: improve the paper with new ASI2-only evidence, while preserving the
no-browser-interruption rule.

## Training Policy

- New training/benchmark launches: ASI2 only.
- Historical ASI1/ASI3 artifacts may be cited as completed evidence.
- Do not launch new training on ASI1 or ASI3.

## Launch Targets

1. ASI2 risk-controlled router scale-up:

   ```bash
   cd /vllm-workspace/mwg-ew-transformer-research
   bash scripts/launch_ASI2_risk_router_sweep_detached.sh
   ```

   This evaluates five seeds with suite-local thresholds, suite-balanced ridge
   fitting, exact train/eval overlap rejection, dense fallback, and an explicit
   predicted-loss risk cap. It is the next algorithmic experiment because it
   tests whether the router can enlarge the quality-preserving patch set without
   claiming broad always-patched replacement.

2. ASI2 systems replication:

   ```bash
   cd /vllm-workspace/mwg-ew-transformer-research
   bash scripts/launch_ASI2_reliability_scaling_detached.sh
   ```

3. Push ASI2 results back to S3 after completion:

   ```bash
   cd /vllm-workspace/mwg-ew-transformer-research
   bash scripts/ASI2_push_results_to_s3.sh results logs
   ```

4. Pull locally:

   ```bash
   bash scripts/pull_from_s3.sh research_paper_mwg_ew_transformer/results research_paper_mwg_ew_transformer/logs
   ```

## Current Access Boundary

Huanxin browser/Safari foreground recovery is disabled. Use only:

- existing non-interrupting daemon/shell channels,
- S3 relay,
- headless/background/profile-isolated automation with headed and Safari
  fallback disabled.

If ASI2 shell startup requires Safari SSO bridge, headed fallback, visible
browser, or foreground login repair, do not run it. Report the blocker instead.

## 2026-06-01 Local Repair Attempt

- Improved the Huanxin shell wrapper so an explicit `HUANXIN_PROFILE_DIR` is
  respected and no automatic full-profile copy is forced over it.
- Verified that a slim headless profile launches without the previous Chromium
  SIGTRAP profile crash.
- ASI2 command execution is still blocked by expired Huanxin auth:
  `Huanxin auth expired before opening ASI2; Safari SSO bridge is disabled to
  avoid foreground browser interruption. API-key smoke=null.`
- Code and paper artifacts were pushed to the S3 relay, but no ASI2 training or
  router sweep was launched under expired auth.
