# Session Verification Ledger — 2026-08-31 (v2)

Second working session on the "top journals" goal. Focus: re-attempt ASI2,
verify the causal-quality run is fully armed, and independently audit the
paper's analytic claims.

## ASI2 re-check — still blocked (authoritative)

- ASI2 daemon IS up on port 19004 (PID 85814) but NOT authenticated:
  `ready:false, shellSurfaceReady:false, startupState:booting`,
  `healthSummary: "[auth-retry #27] ... login_required"`.
- The CDP-9224 standalone Chrome is ALSO on the login page
  (`aihuanxin.cn/auth/.../login`), so no authenticated bridge exists.
- Authoritative doc `quantum-gpt/reports/asi2_auth_recovery_options_20260820.md`
  states: **no non-interactive auth path exists**. Password login is disabled
  server-side; KEYCLOAK_REMEMBER_ME cannot resurrect a dead SSO; the API-key JWT
  does not cover the /kunlun SPA. The ONLY path is an SMS login in Safari
  requiring the user's phone (~30 s), after which the bridge rehydrates the
  profile and the daemon self-recovers.

Conclusion: the causal-quality TRAINING cannot be launched from this headless
session; it requires one user interaction (phone SMS). Everything else is staged
and verified (below).

## Causal-quality run: fully armed and verified on S3 relay

All dependencies are staged on S3 and byte-identical (SHA-256) to the local
verified copies:
- `scripts/launch_ASI2_causal_quality_detached.sh` MATCH
- `experiments/mwg_quality_distillation.py` MATCH
- `experiments/audit_quality_threeway_split.py` MATCH
- `data/quality/{train,dev,test}.txt` MATCH the frozen manifest hashes
  (train 630 / dev 300 / test 303; zero cross-split near-duplicate overlap)

Turnkey launch (after SMS login):
`bash scripts/launch_ASI2_causal_quality_detached.sh`

## Manuscript: both submission vehicles build clean

- `main_iclr2027.tex` (ICLR 2027, 9-page main text + refs + appendix): 20 pages,
  0 undefined refs, 0 overfull, 0 errors. Main text ends page 9.
- `main.tex` (full 25-page journal/TMLR-length version): 25 pages, 0 undefined
  refs, 0 overfull, 0 errors.
- No stale/withdrawn claims remain in the ICLR manuscript (scanned: the only
  1.638 is a correctly-framed historical microbenchmark speedup; the withdrawn
  router-savings/quality numbers are gone or explicitly flagged as withdrawn).

## Independent analytic audit (passes)

Re-derived the paper's closed-form claims and confirmed every spot-check:
- 8B systems geometry (4096,14336,128): Gamma=9/224=0.04018, n_max=24,
  q_min=43 (paper: 43); logical core payload @ T=1024,q=1 = 0.0424 (paper 0.0424).
- Quality geometry (1536,8960,384): Gamma=41/140=0.29286, n_max=3, q_min=342
  (paper: 342); payload @ T=1024,q=1 = 0.3214 (paper 0.3214).
- Generated-term contributions at q=1: 0.00223 (8B) / 0.02857 (1.5B)
  (paper: "at most 0.0022 (8B), 0.0286 (1.5B)").
- Arm-4 headline numbers tie to `results/ASI3_arm4_decisive_20260828/
  key_results_SHIPPED.json`: probe fused 0.823 / materialized 0.851 (3.2%
  faster); large-T 2.682/1.393 = 1.925x (paper rounds to 1.93x; equivalence
  max_abs 1.95e-3 at the fp16 floor, all validations passed).

## Remaining path to a full top-journal claim

Only the phone SMS login (user, ~30 s) is between the current state and the
decisive causal-quality run. After it runs, update: table of quality results,
abstract "quality preserved" claim, evidence map row, discussion; then the paper
can carry a measured deployment-quality claim rather than "mechanism verified,
net benefit open."
