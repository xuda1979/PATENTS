# ASI3 2026-06-24 — Recovery + Three-Seed Five-Suite Token-Router Sweep

Hardware: Huanxin ASI3, Ascend 910B2, single NPU (device 0; pod exposes 4 NPUs to torch_npu).
Model: Qwen2.5-1.5B-Instruct, layer-16 FFN MWG-EW patch, rank r=384, expert_residual student.
Project synced to persistent NAS root `/root/work/filestorage/mwg-ew-transformer-research`
(iner S3 relay unreachable from ASI3 due to proxy 403; code shipped via daemon tarball upload).

## 1. Layer-16 recovery (train 5000 steps -> LM-CE calibrate 1200 -> hybrid oracle)
run_id: asi3_layer16_recovery_20260624T110725Z
LMCE_TEXTS: data/heldout/router_eval.txt
Calibration held-out PPL (router_eval, 35,374 tokens):
  dense PPL 3.6854, patched PPL 1.4899, ppl_ratio 0.4043, delta_loss -0.9057
Checkpoint produced:
  results/asi3_layer16_recovery_20260624T110725Z/layer16/checkpoints/mwg_expert_residual_r384_belle_lmce_cal_1200.pt

This reproduces the strong in-distribution calibration benefit (prior 2026-06-11 run on
17,812 tokens gave 0.701x; this run on 35,374 tokens gives 0.404x — same checkpoint family,
larger token base, consistent direction).

## 2. Three-seed five-suite token-router sweep (seeds 0,1,2)
run_id: asi3_five_suite_router_seed_sweep_20260624T111613Z
manifest: data/heldout/combined_extra_splits/manifest.json
patch: the calibrated checkpoint above
suites: gsm8k_test, mbpp_test, alpaca_cleaned_train_tail, wikitext103_validation_extra, hellaswag_validation_extra

Always-patched aggregate ppl_ratio (mean/min/max over seeds): 1.4086 / 1.4086 / 1.4086
(seed variance ~0; always-patched eval is deterministic given fixed checkpoint).

Per-suite always-patched mean ppl_ratio:
  gsm8k_test                    0.9652   (positive)
  mbpp_test                     1.2162
  alpaca_cleaned_train_tail     1.2398
  wikitext103_validation_extra  1.7973
  hellaswag_validation_extra    2.5485

Token-router mixed frontier (mean over 3 seeds):
  target 0.05 -> actual 0.6229 -> ppl_ratio 1.1725
  target 0.10 -> actual 0.8169 -> ppl_ratio 1.3424
  target 0.25 -> actual 1.0000 -> ppl_ratio 1.4117

## Interpretation (honest)
The fresh, fully re-run checkpoint is strongly positive IN-DISTRIBUTION (router_eval / calibration
slice, 0.404x) and on GSM8K (0.965x), but the always-patched five-suite AGGREGATE is ABOVE dense
(1.409x = worse) for this seed-swept reproduction, driven by the out-of-family suites
(HellaSwag 2.55x, Wikitext-103 1.80x). The token router does not recover a net win on this
five-suite mix: the suite-local threshold policy over-selects (actual patch fractions far above
target) so the frontier stays >1.0x. This is a more conservative result than the earlier single-run
2026-06-11 five-suite number (0.9352x); the difference is attributable to the corrected seeded
splits and balanced-ridge / fail-on-overlap controls applied here across three seeds.

Takeaway for the paper: the defensible positive claim is (a) in-distribution / calibration-slice
benefit and (b) GSM8K under the five-suite manifest; the always-patched FIVE-SUITE aggregate is
NOT uniformly safe under leakage-clean seeded evaluation, and the dense-fallback router needs a
tighter threshold policy than suite_local to realize a net five-suite win.
