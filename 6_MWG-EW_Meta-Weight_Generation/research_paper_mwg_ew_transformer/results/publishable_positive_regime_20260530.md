# Publishable Positive Regime Boundary

A top-journal paper can center on scoped positive scenarios, but the current evidence supports bounded selective routing only. It does not support broad always-patched replacement or systems deployment claims yet.

## Positive Scoped Regime

Current defensible positive case: MWG-EW as a benefit-supervised, token-level selective router with dense fallback.

| Target | Status | Broad actual | Broad mean ratio | Broad max | Leave-suite-out actual | Leave-suite-out mean ratio | Leave-suite-out max |
|---:|---|---:|---:|---:|---:|---:|---:|
| 0.01 | negative_or_unready | 0.07% | 1.0011 | 1.0013 | 0.43% | 1.0007 | 1.0009 |
| 0.03 | promising_but_unstable | 0.21% | 0.9998 | 1.0013 | 1.66% | 0.9989 | 1.0004 |
| 0.05 | stable_positive | 0.49% | 0.9977 | 0.9997 | 2.84% | 0.9975 | 0.9996 |
| 0.10 | stable_positive | 1.82% | 0.9920 | 0.9952 | 5.65% | 0.9926 | 0.9943 |
| 0.25 | promising_but_unstable | 8.52% | 0.9864 | 0.9929 | 13.80% | 0.9943 | 1.0004 |
| 0.50 | negative_or_unready | 21.68% | 1.0164 | 1.0312 | 28.06% | 1.0274 | 1.0488 |

Interpretation: target 0.05 and 0.10 are the present stable positive window. Target 0.25 is promising but still unstable under leave-suite-out validation, and target 0.50 is negative.

## Negative Boundaries

| Boundary | Tokens | Token-weighted ratio | Max suite ratio |
|---|---:|---:|---:|
| always_patched_mwg | 91,352 | 1.2464 | 1.3589 |
| persistent_low_rank_r384 | 66,873 | 1.2795 | 1.3026 |
| persistent_low_rank_r384_lmce | 91,352 | 1.3099 | 1.4504 |

## Systems Boundary

Hardware-counter complete: `false`.
Fused-like MWG op observed: `false`.

## Readiness

Ready for scoped positive case study: `true`.
Ready for broad top-journal claim: `false`.
