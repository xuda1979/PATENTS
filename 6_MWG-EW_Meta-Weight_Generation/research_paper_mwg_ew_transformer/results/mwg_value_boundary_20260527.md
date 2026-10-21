# MWG Value Boundary

Created: 2026-05-27

Question: have we found cases where MWG is very valuable?

Short answer: not yet in the broad/top-journal sense. We have found a
repeatable narrow value regime: MWG is useful as a benefit-supervised,
budgeted, projection-internal patch with dense fallback. We have not found
evidence that always-on MWG replacement is broadly valuable.

## Strongest Positive Case

The strongest ASI3 evidence is leakage-clean token-level selective routing on
the broad suites, not always-patched replacement.

Three-seed broad token-router sweep
`asi3_token_router_broad_seed_sweep_20260525T161810Z`:

| Target | Mean actual patch fraction | Mean PPL ratio | Min seed | Max seed |
|---:|---:|---:|---:|---:|
| 0.05 | 0.49% | 0.9977 | 0.9941 | 0.9997 |
| 0.10 | 1.82% | 0.9920 | 0.9890 | 0.9952 |
| 0.25 | 8.52% | 0.9864 | 0.9820 | 0.9929 |
| 0.50 | 21.68% | 1.0164 | 0.9943 | 1.0312 |

Leave-suite-out broad auxiliary sweep
`asi3_token_router_leave_suiteout_seed_sweep_20260525T171658Z`:

| Target | Mean actual patch fraction | Mean PPL ratio | Min seed | Max seed |
|---:|---:|---:|---:|---:|
| 0.05 | 2.84% | 0.9975 | 0.9964 | 0.9996 |
| 0.10 | 5.65% | 0.9926 | 0.9914 | 0.9943 |
| 0.25 | 13.80% | 0.9943 | 0.9889 | 1.0004 |
| 0.50 | 28.06% | 1.0274 | 1.0076 | 1.0488 |

Interpretation: target 0.05 and 0.10 are stable wins in the stricter
leave-suite-out setting. Target 0.25 is promising but still slightly unstable.
Target 0.50 fails.

## Strong Negative Boundary

Always-patched MWG is not valuable on the current broad manifest:

| Suite | Tokens | PPL ratio |
|---|---:|---:|
| GSM8K | 44,708 | 1.3589 |
| MBPP | 13,301 | 1.1354 |
| Alpaca-tail | 33,343 | 1.1399 |

Token-weighted ratio: 1.2464 over 91,352 tokens.

Same-rank persistent low-rank baselines are also broad-negative:

- persistent r384 broad baseline: token-weighted ratio 1.2795 over 66,873
  tokens.
- persistent r384 direct LM-CE calibration baseline: token-weighted ratio
  1.3099 over 91,352 tokens.

This means the current evidence supports selective routing as the source of
value, not broad patch quality preservation.

## Local Mechanism Findings

Local synthetic probes explain where the signal is strongest:

- FFN internal projection-path residuals are better than output-only residuals.
  At 25% supervised routing, internal improves 1.439% over the low-rank base,
  versus 1.079% for output-only.
- Attention K/V patching has signal, but weaker than FFN-internal. K-only is
  weak. V or K+V carries most of the benefit; K+V supervised at 25% improves
  0.682% in the local probe.
- Combining FFN-internal and K/V did not unlock a larger gain. At 25%,
  combined separate supervised routing improves only 0.038% in the synthetic
  combined block, and true joint allocation is not better.

Usage rule from local evidence:

1. Do not use MWG blindly.
2. Patch inside large projection paths, especially FFN internal paths.
3. Train routers from per-token benefit labels.
4. Keep patch budgets bounded; quality degrades as the patch fraction grows.

## Systems Boundary

The current runtime profiler probe is negative for hardware value:

| Case | Descriptor MiB | Mean time ms | Matmul-like ops | Fused-like op |
|---|---:|---:|---:|---|
| dense | 64.50 | 0.3391 | 27 | false |
| mwg_r128 | 5.53 | 0.7638 | 54 | false |
| mwg_r256 | 11.06 | 0.7559 | 54 | false |

The descriptor-size reduction is conceptually attractive, but the measured
prototype is slower than dense and no fused operator or hardware-counter
validation has been captured.

## Current Answer

MWG is currently valuable in a narrow algorithmic regime:

- selective, not always-on;
- supervised by benefit/risk labels, not just budget penalties;
- sparse enough to stay in the 0.05--0.10 stable region, with 0.25 still under
  investigation;
- placed inside projection paths rather than as a post-hoc output correction.

MWG is not yet "very valuable" in the stronger sense needed for a top-journal
claim. To upgrade the claim, we need at least one of:

1. target 0.25 becomes stable under leave-suite-out and broader independent
   families;
2. a real broad-family benchmark set confirms gains beyond GSM8K/MBPP/Alpaca;
3. MWG beats stronger durable low-rank/adaptation baselines on paired broad
   evaluations;
4. fused-kernel or hardware-counter evidence shows real memory-traffic or
   latency value.

Until then, the honest claim is: MWG-EW has a promising selective-patching
regime, but the evidence does not yet support broad replacement or systems
deployment claims.
