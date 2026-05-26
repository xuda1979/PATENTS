# ASI3 Compact Validation Summary

Source remote:
`/vllm-workspace/mwg-ew-transformer-research/results/asi3_validation_20260525_compact/compact_validation_summary.json`

## Broad Held-Out Validation

### MWG Layer-16 r384 LM-CE Checkpoint

| Suite | Tokens | Dense PPL | Patched PPL | PPL Ratio |
| --- | ---: | ---: | ---: | ---: |
| gsm8k_test | 44,708 | 3.4941 | 4.7481 | 1.3589 |
| mbpp_test | 13,301 | 3.9877 | 4.5276 | 1.1354 |
| alpaca_cleaned_train_tail | 33,343 | 3.8818 | 4.4249 | 1.1399 |

Aggregate: 91,352 tokens, token-weighted PPL ratio 1.2464, max suite ratio
1.3589.

### Same-Rank Persistent Low-Rank Baseline

Run:
`asi3_broad_validation_20260525T115053Z`

Checkpoint:
`/vllm-workspace/mwg-ew-transformer-research/results/asi3_persistent_broad_baseline_20260525T114920Z/checkpoints/persistent_low_rank_r384.pt`

| Suite | Tokens | Dense PPL | Patched PPL | PPL Ratio |
| --- | ---: | ---: | ---: | ---: |
| gsm8k_test | 31,329 | 4.7059 | 6.0889 | 1.2939 |
| mbpp_test | 12,850 | 4.1360 | 5.3876 | 1.3026 |
| alpaca_cleaned_train_tail | 22,694 | 4.2148 | 5.2535 | 1.2464 |

Aggregate: 66,873 tokens, token-weighted PPL ratio 1.2795, max suite ratio
1.3026. The baseline used the same manifest and explicit text guardrails, but
its evaluated token counts differ from the MWG run, so this should be read as a
separate broad negative baseline rather than a token-identical paired test.

### Same-Rank Persistent Low-Rank Baseline With LM-CE Calibration

Run:
`asi3_broad_validation_20260526T024509Z`

Calibrated checkpoint:
`/vllm-workspace/mwg-ew-transformer-research/results/asi3_persistent_lmce_baseline_20260526T024239Z/checkpoints/persistent_low_rank_r384_lmce.pt`

| Suite | Tokens | Dense PPL | Patched PPL | PPL Ratio |
| --- | ---: | ---: | ---: | ---: |
| gsm8k_test | 44,708 | 3.4941 | 5.0680 | 1.4504 |
| mbpp_test | 13,301 | 3.9877 | 4.1225 | 1.0338 |
| alpaca_cleaned_train_tail | 33,343 | 3.8818 | 4.7813 | 1.2317 |

Aggregate: 91,352 tokens, token-weighted PPL ratio 1.3099, max suite ratio
1.4504. This fairer direct LM-CE persistent low-rank baseline is still
negative on the broad manifest and does not close the gap to the bounded
selective-router evidence. Full JSON artifacts are present on ASI3 but only the
persistent run status has been fetched locally so far; larger JSON fetches
timed out through the sticky daemon and still need a later SHA-verified fetch.

## Router Validation

Three router validation runs completed:

- asi3_router_validation_20260525T103501Z
- asi3_router_validation_20260525T104452Z
- asi3_router_validation_20260525T104654Z

The current ridge router is deterministic for these inputs, so the three runs
produce identical aggregate frontiers.

| Policy | Target Patch Fraction | Actual Patch-Token Fraction | PPL Ratio |
| --- | ---: | ---: | ---: |
| Routed frontier | 0.10 | 0.016877 | 1.012908 |
| Routed frontier | 0.25 | 0.034517 | 1.027341 |
| Routed frontier | 0.50 | 0.145304 | 1.141131 |
| Always patched | 1.00 | 1.000000 | 2.062533 |
| Oracle frontier | 0.10 | 0.102844 | 1.013907 |
| Oracle frontier | 0.25 | 0.251682 | 1.062423 |
| Oracle frontier | 0.50 | 0.502742 | 1.200023 |

Interpretation: broad validation is negative for deployment-quality claims.
The same-rank persistent low-rank baseline is also negative on the broad
manifest. The deployable router can keep perplexity close to dense only by
patching a very small fraction of tokens. This is useful as a negative control
and a direction for better risk-aware routing, not a top-journal-quality result
yet.

## Token-Level Router Validation

A stronger token-level dense-fallback router run was launched through the ASI3
daemon-only script path:
`asi3_token_router_validation_20260525T125011Z`.

This run trains on token CE deltas from `router_train.txt` and evaluates actual
mixed dense/patch forward passes on disjoint `router_eval.txt`; it is not an
oracle loss-mixing calculation. The train split is patch-favorable
(`patched_ppl_ratio=0.4366` over 30,053 tokens), while the held-out eval split
is patch-negative (`patched_ppl_ratio=2.0616` over 35,118 tokens), exposing a
large train/eval distribution shift.

| Target Patch Fraction | Actual Patch-Token Fraction | PPL Ratio |
| ---: | ---: | ---: |
| 0.01 | 0.0038 | 1.0132 |
| 0.03 | 0.0124 | 1.0249 |
| 0.05 | 0.0193 | 1.0360 |
| 0.10 | 0.0363 | 1.0508 |
| 0.25 | 0.0947 | 1.1665 |
| 0.50 | 0.2485 | 1.6013 |

Interpretation: token-level routing confirms the same boundary as the
example-level router. It can bound quality loss only when the actual patch-token
fraction is tiny. This is better evidence for the paper because it evaluates
real mixed forwards, but it is still negative for a deployment-quality claim.

## Token-Level Router Cross-Validation

Run:
`asi3_token_router_cv_20260525T131335Z`

To test whether the fixed `router_train.txt`/`router_eval.txt` result was a
single unlucky split, the two router corpora were pooled into 512 unique lines
and repartitioned into three explicit train/eval folds. Each fold has 256 train
lines and 256 eval lines with no overlap. The same token-level router was then
trained and evaluated with actual mixed dense/patch forwards.

| Target Patch Fraction | Mean Actual Patch-Token Fraction | Mean PPL Ratio | Min PPL Ratio | Max PPL Ratio |
| ---: | ---: | ---: | ---: | ---: |
| 0.01 | 0.0009 | 0.9989 | 0.9955 | 1.0009 |
| 0.03 | 0.0038 | 0.9940 | 0.9870 | 1.0009 |
| 0.05 | 0.0075 | 0.9896 | 0.9796 | 1.0007 |
| 0.10 | 0.0193 | 0.9787 | 0.9644 | 0.9974 |
| 0.25 | 0.0695 | 0.9462 | 0.9282 | 0.9618 |
| 0.50 | 0.1766 | 0.9218 | 0.9137 | 0.9373 |

Interpretation: CV resampling of the router corpus is encouraging: the router
can find patch-favorable subsets on these mixed router texts, and the mean
frontier improves below dense at moderate target fractions. This does not
overturn the negative broad manifest, because the folds are resamples of the
router corpora rather than independent GSM8K/MBPP/Alpaca-style benchmarks. It
does show that the next publishability path should focus on distribution-robust
router training and evaluation on truly independent broad corpora.

## Leakage-Clean Broad Token-Router Validation

Run:
`asi3_token_router_broad_20260525T141738Z`

This run evaluates the token-level router on the broad manifest suites. For
each suite, the router train pool was made from `router_train.txt` plus
`router_eval.txt`, then all exact lines overlapping that suite's eval file were
removed before training. Removed overlaps: 196 for GSM8K, 136 for MBPP, and 180
for Alpaca-tail. This makes the router train/eval boundary explicit and avoids
the accidental overlap found during split preparation.

| Target Patch Fraction | Token-Weighted Actual Patch Fraction | Token-Weighted PPL Ratio | Min Suite Ratio | Max Suite Ratio |
| ---: | ---: | ---: | ---: | ---: |
| 0.01 | 0.0005 | 1.0010 | 1.0001 | 1.0050 |
| 0.03 | 0.0019 | 1.0008 | 1.0005 | 1.0025 |
| 0.05 | 0.0055 | 0.9989 | 0.9970 | 1.0004 |
| 0.10 | 0.0208 | 0.9916 | 0.9648 | 0.9996 |
| 0.25 | 0.0849 | 0.9868 | 0.9197 | 1.0038 |
| 0.50 | 0.1975 | 1.0140 | 0.8587 | 1.0498 |

Per-suite always-patched ratios remain negative: GSM8K 1.3238, MBPP 1.1131,
and Alpaca-tail 1.1100. The routed frontier is therefore a selective routing
result, not a claim that the patch itself is broadly quality preserving. The
bounded positive result is that leakage-clean token routing can recover a small
token-weighted gain on the broad suites at moderate patch fractions, especially
target 0.10--0.25, while avoiding the large always-patched degradation.

## Leakage-Clean Broad Token-Router Seed Sweep

Run:
`asi3_token_router_broad_seed_sweep_20260525T161810Z`

This follow-up repeats the leakage-clean broad router protocol over three
explicit split seeds with `TRAIN_FRACTION=0.75`. Each seed prepares per-suite
router train files from the pooled router texts after removing exact overlaps
with the target suite's broad eval file, then evaluates actual mixed
dense/patch forwards on GSM8K, MBPP, and Alpaca-tail. The aggregate below is
the mean across the three split seeds; min and max are over seed-level
token-weighted broad ratios.

| Target Patch Fraction | Mean Actual Patch Fraction | Mean Token-Weighted PPL Ratio | Min Seed Ratio | Max Seed Ratio |
| ---: | ---: | ---: | ---: | ---: |
| 0.01 | 0.0007 | 1.0011 | 1.0008 | 1.0013 |
| 0.03 | 0.0021 | 0.9998 | 0.9980 | 1.0013 |
| 0.05 | 0.0049 | 0.9977 | 0.9941 | 0.9997 |
| 0.10 | 0.0182 | 0.9920 | 0.9890 | 0.9952 |
| 0.25 | 0.0852 | 0.9864 | 0.9820 | 0.9929 |
| 0.50 | 0.2168 | 1.0164 | 0.9943 | 1.0312 |

Interpretation: the three-seed sweep strengthens the selective-router result
because target 0.05, 0.10, and 0.25 remain below dense on every seed. The
usable region is still bounded: target 0.50 is unstable, and always-patched
broad evaluation remains negative. This is stronger evidence for
distribution-aware selective routing, not evidence that the current patch can
replace the dense FFN broadly without routing or fallback.

## Leave-Suite-Out Broad Auxiliary Router Seed Sweep

Run:
`asi3_token_router_leave_suiteout_seed_sweep_20260525T171658Z`

This is a stricter distribution-robust router stress test. For each target
broad suite, the router train set is built from `router_train.txt`,
`router_eval.txt`, and the other two broad suites, while exact target-suite eval
lines are removed before training. With `TRAIN_FRACTION=0.75`, each seed uses
the same candidate counts: GSM8K trains on 340 of 454 candidates, MBPP on 390
of 520 candidates, and Alpaca-tail on 340 of 454 candidates, with zero
train/eval overlap.

| Target Patch Fraction | Mean Actual Patch Fraction | Mean Token-Weighted PPL Ratio | Min Seed Ratio | Max Seed Ratio |
| ---: | ---: | ---: | ---: | ---: |
| 0.01 | 0.0043 | 1.0007 | 1.0004 | 1.0009 |
| 0.03 | 0.0166 | 0.9989 | 0.9980 | 1.0004 |
| 0.05 | 0.0284 | 0.9975 | 0.9964 | 0.9996 |
| 0.10 | 0.0565 | 0.9926 | 0.9914 | 0.9943 |
| 0.25 | 0.1380 | 0.9943 | 0.9889 | 1.0004 |
| 0.50 | 0.2806 | 1.0274 | 1.0076 | 1.0488 |

Interpretation: leave-suite-out broad auxiliary training confirms the bounded
selective-router signal at target 0.05 and 0.10 across all seeds, and gives an
average gain at target 0.25 with one near-neutral/slightly-worse seed. The
target 0.50 row degrades on all seeds. This is stronger than router-corpus CV
because the target suite is held out, but it is still a selective dense-fallback
result, not a broad always-patched replacement result.

## Runtime Profiler Probe

Run:
`asi3_runtime_profiler_probe_20260525T192357Z`

This run is an operator-level probe for the current unfused associative FFN
prototype on ASI3, not a full hardware-counter study. The environment reported
8 visible Ascend 910B2 NPUs, `torch_npu=2.9.0`, `npu-smi` at
`/usr/local/bin/npu-smi`, and `msprof` at
`/usr/local/Ascend/cann-8.5.0/bin/msprof`. The PyTorch profiler exposed CPU
activities only for this capture, so the result explicitly keeps
`hardware_counter_complete=false`.

| Case | Descriptor MiB | Mean Time (ms) | Matmul-Like Op Count | Fused-Like Op Observed |
| --- | ---: | ---: | ---: | --- |
| dense | 64.50 | 0.3391 | 27 | false |
| mwg_r128 | 5.53 | 0.7638 | 54 | false |
| mwg_r256 | 11.06 | 0.7559 | 54 | false |

Interpretation: the probe confirms the current prototype is still an unfused
factor-matmul path. The low-rank descriptor estimates show the intended traffic
reduction, but the measured prototype path is slower than dense in this
microprobe and no fused MWG operator appears in the profiler. Since no device
activity or off-chip traffic counters were captured, this is useful negative
fused-kernel evidence and tool-availability evidence, not the hardware-counter
validation required for a top-journal systems claim.
