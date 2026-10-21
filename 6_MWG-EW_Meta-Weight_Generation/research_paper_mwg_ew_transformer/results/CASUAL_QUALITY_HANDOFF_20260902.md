# Causal Quality Campaign — Staged & Preflight-Verified (2026-09-02)

## Status
The causal-quality experiment (the largest remaining open item for a positive
efficiency claim) is **fully staged and its local configuration/data-integrity
gates PASS** (verified locally on 2026-09-02 via a mirror of the ASI2 project).
The **only** blocker to execution is ASI2 access: the ASI2 web shell requires a
phone-SMS login (`获取验证码` / `login_required`) that is not obtainable by any
authorized non-interactive path. No trained `token_diag_core` checkpoint
exists, so no local CPU quality evaluation is possible without first training.

## What is staged and verified
- Launcher: `scripts/launch_ASI2_causal_quality_detached.sh` (483 lines)
  - Frozen seeds: 2026, 2027, 2028
  - Controls: dense teacher, static SVD (r=384/401/512), persistent-low-rank
    r=384, token_diag_core r=384, persistent r=401 (parameter-matched), persistent r=512 (effective)
  - Checks: preflight (config/rank/dtype consistency) + split integrity audit
- Data: `data/quality/{train,dev,test}.txt` + `manifest.json`
  - Hash-bound: every element SHA-256; cross-split exact-overlap = 0,
    near-duplicate pairs = 0 for all train/dev/test pairs (audit `ready: true`)
  - `canonical_controls_verified`: d=1536, m=8960, base=384, matched=401 exactly
    consistent for fp32
- Local preflight pass (mirror): `ASI2 causal-quality preflight passed`

## Launch command (ASI2 restored)
```
bash scripts/async_sync_to_asi2.sh   # (or equivalent code push)
bash scripts/asi2_shell.sh "cd /vllm-workspace/mwg-ew-transformer-research && \
  bash scripts/ASI2_sync_code_from_s3.sh && bash scripts/launch_ASI2_causal_quality_detached.sh"
```
Expected duration: multi-day (`STEPS=5000` x 3 seeds x 4 student models on 4 NPUs).

## What the result would add to the paper
A disjoint, multi-seed causal quality evaluation with explicit controls would
convert the "mechanism-verified, benefit-open" claim into an established
positive or negative result: if the diagonal-core causal mode preserves or
improves quality over dense/SVD/persistent controls at matched parameters, the
parameter-lifetime story gains a quality anchor; if neutral/negative, the paper
honestly reports the boundary. Either way the paper's empirical completeness
improves materially for a top-journal submission.

## Related paper state (2026-09-02)
- `main.tex` reconciled: Introduction/Discussion/Conclusion now reflect the
  completed four-arm mechanism measurement (parity at probe, 1.93x beyond L2
  isolated); three measured-data figures added.
- `tmlr/main_tmlr.tex`: complete TMLR journal package, 23 pp clean build.
- ICLR 2027 port: ready (`main_iclr2027.tex`), deadline Sep 25 2026.
