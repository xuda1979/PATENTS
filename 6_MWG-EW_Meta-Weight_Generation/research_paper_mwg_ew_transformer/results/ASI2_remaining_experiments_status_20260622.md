# ASI2 Remaining Experiments + Paper Status, 2026-06-22

## Hard blocker (cluster)
ASI2 Huanxin shell is blocked by expired auth:
`Huanxin auth expired before opening ASI2; Safari SSO bridge is disabled`.
The non-activating `huanxin_safari_keepalive.sh --refresh` finds no live tab,
and the 2026-06-12 blocker doc also recorded a Keycloak `UPDATE_PASSWORD`
required action plus `403 RBAC` on the task API. Restoring access needs a
FOREGROUND Safari SSO login (and likely a password update), which automation
refuses to avoid interrupting the user. No new training was launched.

## Re-auth attempt (2026-06-22, "go ahead")
- Safari has live Huanxin (焕新社区) tabs, but `huanxin_safari_keepalive.sh
  --activate` returns `found:false` (no tab matched the hard-coded target URL).
- A `huanxin_password_login.js` automation (PID 97012, NOT started by me) was
  already running against the ASI2 URL. It filled username `xuda2025` + password
  + captcha `ryht`, captured `huanxin-password-login.after-captcha.png` at 22:59,
  then stalled with no further output for 5+ minutes.
- Likely cause: captcha rejected and/or Keycloak `UPDATE_PASSWORD` required
  action. ASI2 shell still returns `Huanxin auth expired ... SSO bridge disabled`.
- I did NOT kill the in-flight login process and did NOT guess credentials/
  captcha for an automation whose env I cannot see.

### What needs YOU
Complete the Huanxin login once in the foreground (enter the captcha correctly
and, if prompted, set a new password). Then re-run the launch block below.

## Ready-to-fire (after re-auth)
- Code + data already pushed to S3 relay (verified reachable independent of
  the browser session).
- One-command launch once ASI2 shell is healthy:

```bash
cd /Users/daxu/PATENTS/6_MWG-EW_Meta-Weight_Generation
bash scripts/asi2_shell.sh "cd /vllm-workspace/mwg-ew-transformer-research && \
  bash scripts/ASI2_sync_code_from_s3.sh && \
  bash scripts/launch_ASI2_risk_router_sweep_detached.sh && \
  bash scripts/launch_ASI2_reliability_scaling_detached.sh"
```
Then push back + pull:
```bash
bash scripts/asi2_shell.sh "cd /vllm-workspace/mwg-ew-transformer-research && bash scripts/ASI2_push_results_to_s3.sh results logs"
bash scripts/pull_from_s3.sh research_paper_mwg_ew_transformer/results research_paper_mwg_ew_transformer/logs
```

## Paper improvements completed (no cluster needed)
- Added dedicated `Related Work` section (conditional computation/MoE, low-rank
  & structured weights, hypernetworks/weight generation, post-training
  compression, communication-efficient distributed training, IO-aware/KV).
- Expanded `refs.bib` from 7 to 18 verifiable references; wired new gradient-
  compression / optimizer-sharding citations into the Gradient Communication
  analysis.
- Added `Limitations` and `Reproducibility` paragraphs to the Discussion.
- Verified clean build: pdflatex+bibtex, 0 undefined citations, 0 overfull
  hboxes, 21 pages. Updated paper pushed to S3.
