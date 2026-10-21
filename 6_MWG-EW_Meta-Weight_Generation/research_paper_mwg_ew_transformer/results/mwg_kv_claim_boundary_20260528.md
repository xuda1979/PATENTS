# MWG K/V Claim Boundary

Created: 2026-05-28

Question: do the current results confirm that MWG is valuable for replacing the
large K/V projection matrices in Transformers?

Short answer: they support the direction, but do not yet fully confirm the
real-LM K/V replacement claim.

## What Is Supported

K/V projection matrices are a natural target for MWG:

- they are large Transformer weight matrices;
- they sit on a central activation path;
- generated low-rank descriptors directly match the goal of reducing
  persistent weight operands;
- V and K+V have local signal in the current synthetic attention probe.

Local K/V probe evidence:

| Method | Budget | Mean improvement vs base |
| --- | ---: | ---: |
| K always residual | 100% | 0.281% |
| V always residual | 100% | 1.431% |
| K+V always residual | 100% | 1.567% |
| K+V supervised routing | 10% | 0.286% |
| K+V supervised routing | 25% | 0.682% |
| K+V supervised routing | 50% | 0.879% |

Interpretation: K alone is weak. V carries most of the local attention-path
benefit. K+V is the best local K/V variant.

## What Is Not Yet Confirmed

The strongest real ASI3 evidence is still bounded selective routing around the
current layer-16 MWG checkpoint, not a clean real-LM K/V replacement result.

The paper should not claim yet:

- MWG broadly replaces K/V matrices in a real Transformer LM;
- K/V MWG improves broad held-out LM perplexity;
- K/V MWG gives real latency or off-chip memory-traffic wins.

Those claims require real held-out LM K/V experiments, paired baselines, and
hardware-counter or fused-kernel evidence.

## Safe Paper Wording

Current defensible wording:

> MWG is designed for large projection paths such as FFN and attention K/V
> matrices. Local attention probes show that V and K+V projections are viable
> MWG targets, while real LM experiments currently validate the broader
> selective generated-weight routing principle. Establishing K/V replacement on
> real Transformer held-out benchmarks remains a decisive next experiment.

This is still meaningful progress: it positions K/V as the clean architectural
motivation and next scaling target without overstating the current evidence.
