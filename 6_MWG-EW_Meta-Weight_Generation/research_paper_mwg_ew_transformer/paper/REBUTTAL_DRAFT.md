# Rebuttal Draft — Response After the Integrity Audit

> Note (2026-08-24): `REVISION_RESPONSE_MAJOR_REVIEW.md` is the authoritative
> point-by-point response to the major review and includes the post-audit
> additions. This draft remains the prose-level rebuttal skeleton.

This response supersedes the pre-audit rebuttal. We do not claim that all
reviewer concerns are closed. The active manuscript now separates verified
software/accounting corrections from experiments that still require fresh ASI2
runs. In particular, no new causal-quality or synchronized-DDP accelerator
number is reported in the active paper.

## Summary of the revised claim

The evidence currently supports three limited contributions:

1. a parameter-lifetime interface and a concrete no-write-back systems
   contract;
2. a persistent-low-rank forward--backward microbenchmark, explicitly excluding
   optimizer steps and integrated DDP synchronization; and
3. a token-causal, batch-independent replacement implementation covered by
   information-boundary and checkpoint tests.

It does **not** yet support an ephemeral-lifetime speedup, causal language-model
quality preservation, realized routed-traffic savings, or downstream-task
equivalence. Those claims have been withdrawn pending the reruns below.

## R1. Causal leakage and unmatched quality controls

**Agreed; the archived quality interpretation is invalid.** The historical
`expert_residual` controller pooled hidden states across the full
teacher-forced sequence and across batch members. Earlier-token logits could
therefore depend on future tokens and unrelated examples. A full-Transformer
evaluation, a random-mask control, or an additional checkpoint does not repair
that information leak.

The historical student was also not rank- or parameter-matched to rank-384
SVD. It used a rank-384 base plus four rank-32 residual experts: the residual
factors add 33.3% of the base-factor state, and the effective operator rank can
reach 512. The manuscript now reports this configuration and treats the old
cache-fit, PPL, router, and downstream tables only as noncausal diagnostics.

**Implemented but not empirically validated:** a separate
`token_expert_residual` mode computes controls independently from each token's
pre-FFN state and reuses the same token-local control across gate, up, and down
projections. Prefix-invariance, batch-independence, projection-equivalence, and
checkpoint round-trip tests validate the intended information boundary. They
do not establish model quality.

**Still required:** train and calibrate a fresh causal checkpoint on disjoint
text, evaluate it once on a content-hashed held-out split, and include
persistent rank-384, persistent rank-512, and equal-parameter controls. A
fixed-mixture or shuffled-context control is also needed to isolate conditioning
from added capacity.

## R2. Systems timing and lifetime attribution

**Agreed; the systems result has been rescoped.** The historical timer measures
zeroing gradients, forward, a synthetic loss, and backward. It has no optimizer
step and no DDP gradient synchronization. The reported all-reduce latency comes
from a separate synthetic buffer benchmark. The active manuscript therefore
calls the result an eight-process forward--backward microbenchmark, not
distributed-training throughput.

The lifetime ablation is negative for the current implementation. Persistent
low-rank execution averages a 3.22x speedup, while the
conditioned/materialized arm averages 1.51x; the former is about 2.1x faster.
The arms share base rank and projection shapes but not identical controller
compute or active state. This result supports low-rank savings and exposes
generation overhead; it does not support ephemerality.

An opt-in DDP-wrapped timing path has been implemented and smoke-tested, but its
ASI2 measurements are pending. The decisive lifetime experiment remains a
fused generated path that consumes descriptor tiles without off-chip
write-back and is measured with device-memory counters.

## R3. Traffic and routing semantics

**The manuscript arithmetic is corrected; the empirical traffic claim remains
open.** For whole generated calls, the active text uses

`T_routed/T_dense = (1 - p_call) + p_call * Gamma_call`

and hence a saving of `p_call * (1 - Gamma_call)`. It also defines
`Gamma_call = ceil(T/q) * Gamma` and distinguishes a whole-call rate from a
token patch fraction.

The historical mixed path evaluates both dense and patched branches before
`torch.where`; its realized generated-only whole-call fraction is therefore
zero. The old token fractions cannot be inserted into the whole-call formula,
and the earlier routed-savings table is withdrawn. The revised accounting also
includes the four rank-32 expert banks: for the historical quality model the
factor-only ratio is about 2.56x and the total fp32 footprint ratio about 2.45x,
not the base-only 3.41x.

**Still required:** propagate masks and decode positions, count valid tokens,
derive causal marginal labels, and dispatch complete calls or explicit token
groups without executing the unselected branch. Both token and whole-call
rates must be reported under the same grouping used for traffic measurement.

## R4–R6. Router seeds, replication, and downstream inference

**Agreed; the earlier replication and neutrality claims are withdrawn.** The
historical launches requested zero train and evaluation examples, so nominal
split seeds did not resample the data. Moreover, the original 96 cells and the
second-checkpoint 96 units used different constructions. “The same 66/96 on an
identical grid” was therefore not established.

The historical router also used an all-ones evaluation mask, counted padded
positions, reset decode-position features under cached generation, and fitted
GSM8K routing on examples drawn from the file later used for accuracy. The
random-control counters and per-task patch-rate accounting were not adequate to
repair these problems.

Finally, failure to detect a difference on the reported downstream samples is
not evidence of equivalence. “Task-accuracy-neutral” has been removed from the
active empirical conclusion. A valid rerun must use positive split sizes,
record split hashes and near-duplicate overlap, keep a fixed untouched test
set, report realized valid-token/call rates, and use paired bootstrap or
McNemar analysis. Equivalence language requires a predeclared margin and an
appropriately powered test.

## R7. Layer selection

**Textually corrected; causal selection evidence remains pending.** The local
artifacts do not substantiate an identical-setting sweep proving layer 16 was
best. The active manuscript now calls it a development-selected case study
subject to selection bias. A causal rerun must preregister candidate layers and
use common train, calibration, and evaluation splits.

## R8. Related work and novelty

**Corrected.** Fedus et al. is retained only in the MoE discussion. The
speculative-decoding analogy now cites Leviathan et al.; the related-work
section also cites Transformer FFN hypernetworks and a close dynamically
weighted fused-FFN system. We accordingly narrow the proposed novelty to the
explicit no-write-back lifetime contract and selective call-level interface,
not dynamic weight generation itself.

## Reproducibility

The active manuscript no longer claims that every historical number is exactly
replayable. The world-8 per-launch timing JSON and checkpoint-replication raw
JSON are not locally recoverable. Historical ASI2 identifiers such as
`ASI2_mwg_transformer_20260820T1649xxZ` and
`ASI2_mwg_transformer_20260820T1755xxZ` are retained only as provenance leads,
not substitutes for archived raw records. Fresh runs must preserve per-launch
JSON, device and software metadata, checkpoint/data hashes, split hashes, and a
fresh-run marker.

## Required experiments before restoring empirical claims

1. Fresh DDP-wrapped ASI2 timings with synchronized backward, multiple launches,
   and explicit optimizer exclusion or inclusion.
2. Fresh causal checkpoint training, separate calibration, and one disjoint
   held-out evaluation with rank- and parameter-matched controls.
3. Mask-aware branch-skipping routing with causal labels and measured token and
   whole-call rates.
4. Genuine split/checkpoint variation with paired item- or document-level
   uncertainty; no reuse of the unmatched 66/96 comparison.
5. A fused no-write-back kernel with hardware-counter confirmation of off-chip
   descriptor traffic.

## Superseded statements retained for the audit trail

The earlier rebuttal stated that the selective PPL win was attributable to
learned eligibility, that a second checkpoint reproduced the “same 66/96” on
an identical grid, that four downstream probes were task-accuracy-neutral, and
that world-4 timing closed the short-loop/distributed-systems concern. These
statements are superseded for the reasons above. The corresponding historical
numbers may remain useful for debugging, but they are not evidence for the
active paper's causal-quality, equivalence, routed-traffic, or
distributed-training claims.
