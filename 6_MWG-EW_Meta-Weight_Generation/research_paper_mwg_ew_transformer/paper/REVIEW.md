# Second-Round Review: Ephemeral Meta-Weights: Turning Transformer FFN Parameters into Runtime-Generated Operands

**Reviewer:** Anonymous

**Round-one review:** 2026-07-13

**Second-round review:** 2026-08-21
**Recommendation:** Major revision

**Editorial status (2026-08-22):** This report evaluates the pre-audit
revision. The active manuscript has since implemented the cited claim-scoping,
accounting, causal-software, and citation fixes. The accelerator reruns and
fused branch-skipping experiment remain open; see `REBUTTAL_DRAFT.md` for the
itemized response.

## Second-round summary

The parameter-lifetime abstraction remains interesting and potentially
publishable. The revision also contains several substantive improvements:
negative results are reported rather than hidden, off-chip traffic is now
described as analytic rather than measured, a persistent-low-rank control was
added, the full selective-routing distribution is summarized, downstream
probes and a random-routing control were run, and layer/family transfer failures
are disclosed.

Those improvements do not, however, close the central validity questions. The
current manuscript still leaks ordinary low-rank effects into the claimed
parameter-lifetime story, calls a forward/backward microbenchmark “distributed
training throughput,” applies call-level traffic arithmetic to token-level
routing, and treats seed sweeps that change little or nothing in the evaluated
model/data as uncertainty estimates. Several of the claimed “closed” items also
require reruns because the router counts padded positions, does not receive the
same attention-mask feature used for fitting, and evaluates both dense and
patched branches eagerly.

The paper should therefore not state that all reviewer concerns are closed.
The conceptual contribution is promising, but the empirical paper requires a
causally matched systems experiment and a corrected quality/routing rerun.

## What is verified and improved

1. **The no-write-back claim is now explicitly unvalidated.** The paper
   correctly reports that the available profiler did not expose accelerator
   HBM counters or a fused MWG operator, and that the unfused forward is slower
   than dense.

2. **A useful negative lifetime control was added.** At matched base rank, the
   persistent low-rank forward/backward path is substantially faster than the
   generated-and-materialized path. This is important evidence that the present
   speedup is a low-rank effect, not evidence for ephemerality.

3. **The quality boundary is reported more honestly.** Always-patched
   five-suite PPL is above dense for the conservative checkpoint; layers 17 and
   18 show no selective wins; dialogue and long-form transfer are negative.

4. **The first-round presentation requests are largely implemented.** The
   manuscript includes a 96-configuration min/median/max summary, states that
   router-partition seeds do not bound checkpoint variation, reports random-mask
   routing, and includes GSM8K, HumanEval, and MMLU probes.

5. **The Eckart--Young conflict was recognized.** The revision now
   distinguishes matrix Frobenius error from activation-conditioned output
   error. The theorem presentation still needs refinement, but the former
   contradiction is no longer the intended claim.

6. **Typesetting and broad claim scoping improved.** The latest build record
   reports no overfull/underfull boxes, and the manuscript repeatedly marks the
   fused no-write-back kernel as future work.

## Major unresolved issues

### R1. Causal leakage: low rank, generation, and ephemerality are not isolated

The systems benchmark stores the low-rank factors durably. Its context head
rescales those factors, but there is no fused scratch-resident descriptor path.
The measured forward/backward speedup is therefore an ordinary low-rank compute
effect. The new lifetime ablation makes this clearer, but it does not establish
any parameter-lifetime benefit because the decisive fused no-write-back arm is
still absent.

There is a second causal mismatch on the quality side. The headline
expert-residual student is not simply rank 384: it combines a rank-384 base
operator with four rank-32 residual experts. The residual factors add 33.3% of
the base factor state, not 17%, and the per-context operator can have effective
rank up to 512. Comparing it only with rank-384 SVD/persistent factors is not a
rank- or parameter-matched test of conditional generation.

The random-mask control answers a narrower question: learned eligibility is
better than selecting tokens uniformly at random. It does not show that the
generated descriptor beats a random-factor, shuffled-context, fixed-mixture, or
parameter-matched persistent intervention.

**Required reruns:**

- Add a parameter-matched persistent/static control, including at least a
  rank-512 (or equal-total-parameter) baseline for the expert-residual model.
- Add a shuffled-context or fixed-expert-mixture control to isolate
  context-conditioned generation from extra rank/capacity.
- Retain the four-arm lifetime design, but describe arms (i)--(iii) only as
  negative/boundary evidence until the fused arm is measured.

### R2. The systems timing is not end-to-end distributed training

The benchmark’s timed “train” step performs zero-grad, forward, squared-loss,
and backward. It does not perform an optimizer update and does not synchronize
model gradients through DDP. The all-reduce result is a separate synthetic
buffer benchmark. Consequently:

- “distributed training throughput” is too strong;
- the timed speedup cannot be attributed to the smaller synchronized parameter
  set;
- the claim that ASI2 world-4 results bracket world-8 results because of
  all-reduce parallelism is unsupported by the timed step;
- “identical rank and compute” is inaccurate because the generated arm executes
  the scale head and factor materialization while the persistent arm does not.

The headline world-8 per-launch timing artifacts are also not locally
recoverable. A world-4 directional replication does not recreate the lost
world-8 measurement.

**Required action:** either rerun an actual DDP training step on ASI2
(forward, backward, gradient synchronization, optimizer update; adequate
warmup and at least tens of measured iterations) or rename every result as an
eight-process FFN forward/backward microbenchmark plus a separate synthetic
all-reduce probe. The recoverable ASI2 measurements should become the headline
numbers if the world-8 raw artifacts cannot be restored.

### R3. Traffic semantics are still not aligned with the routing experiment

The revised traffic equation is closer to the right quantity, but three
problems remain.

First, the manuscript twice states that the routed saving is
(1-p)(1-Gamma); the equation itself implies p(1-Gamma).

Second, p in the equation must be the fraction of whole calls/token groups that
execute only the generated path. The reported p is a token fraction from
within mixed calls. If patched tokens are split out of an otherwise dense call,
the dense matrix is still fetched for the unpatched invocation; in the current
implementation both branches are evaluated for the full tensor before
selection. The weighted call-level formula therefore cannot be populated
directly with the measured token fraction.

Third, the quality traffic calculation uses rank 384 while omitting the four
rank-32 residual experts and generator state. Descriptor-only geometry for the
implemented factor set is closer to effective rank 512 (about 2.56x rather than
3.41x reduction), before generator-head reads.

**Required action:**

- Correct the saving formula and use Gamma_call when descriptors are regenerated
  for multiple groups.
- Rename the current effective-savings table as a hypothetical generated-only
  call model, or remove it until a group-level router is evaluated.
- Define a fixed group size q, route whole groups, and rerun quality under the
  same grouping that would allow the dense read to be skipped.
- Count all implemented factor/expert/generator bytes and distinguish
  descriptor-only traffic from total operand traffic.

### R4. The reported patch fraction and “actual mixed forward” require a rerun

During router fitting, sequence occupancy is derived from the real attention
mask. During mixed evaluation, the router is passed an all-ones mask. Patch
counters include padded positions, while PPL counts only valid next-token
labels. The dense and patched modules are both evaluated eagerly and then
combined with a selection mask. Thus the implementation is a functional
mixture for quality evaluation, not cost-realizing conditional execution.

The downstream-generation scripts also do not report the realized valid-token
patch fraction, so “approximately 2% patching” on GSM8K, HumanEval, and MMLU is
inherited from a different evaluation rather than measured on those tasks. The
random-control evaluator additionally accumulates cumulative patch counters
across examples.

**Required rerun:** propagate the real mask, count patched valid tokens only,
reset counters correctly, record per-suite/per-task patch rates, and rerun the
selected router, random control, and downstream probes. If both branches remain
eagerly evaluated, call the experiment output mixing and make no realized
compute/traffic claim from it.

### R5. The 96-cell and seed claims conflate different experimental units

The original Pareto result has 96 configurations:

8 maximum-delta values x 4 policies x 3 target budgets,

with each configuration averaged over three router seeds. The manuscript
instead describes the 12 cells per row as 4 policies x 3 seeds. The
checkpoint-replication sweep uses a different 96-unit construction:

8 maximum-delta values x 4 policies x 3 seeds at a single target budget.

The statement that both checkpoints recover the “same 66/96” therefore
compares different units and is not an identical-grid replication.

The near-zero seed variance is also not an uncertainty estimate for the
headline PPL effect. The checkpoint, evaluation texts, and much of the pipeline
are fixed; the router seeds are effectively a no-op at the reported precision
for several cells. One additional distillation seed is useful directional
evidence, but it does not estimate checkpoint variance.

**Required reruns/analysis:**

- Correct the 96-cell combinatorics everywhere.
- Repeat the same policy x budget x delta grid for the second checkpoint, or
  compare only exactly matched cells.
- Report paired sequence/document-level bootstrap confidence intervals,
  stratified by suite.
- Select the operating point on development data and evaluate it once on an
  untouched test set to avoid winner’s-curse from choosing the best of 96
  configurations.

### R6. Downstream “neutrality” is stated too strongly

Running downstream probes was worthwhile and directly responds to round one.
However, failure to reject a difference on 164--570 paired items is not evidence
of equivalence. The current independent-binomial sigma summaries also ignore
the paired nature of predictions.

**Required action:** report paired McNemar or paired-bootstrap confidence
intervals and say “no statistically detectable difference at this sample
size.” Use “equivalent” or “task-accuracy-neutral” only if an equivalence
margin and powered equivalence test are specified. Include the realized
valid-token patch rate for every task.

### R7. Layer-16 selection remains insufficiently documented

The text says layers 12, 14, 16, and 18 were compared and cites a table that
contains only layer-16 rows. A later local multilayer summary gives nominal
Belle ratios for layers 16--18 that do not obviously support “layer 16 had the
lowest held-out ratio.” Settings may differ, but that difference must be
reconciled rather than hidden. The current explanation that layer 16 is
amenable because it is mid-stack is speculative.

**Required action:** provide the complete selection table with identical
settings and identify whether layer 16 was selected post hoc. Either add
measured per-layer rank energy/calibration stability/router predictability or
state that the mechanism is unknown.

### R8. Related-work repair contains a factual miscitation

The speculative-decoding paragraph cites Fedus et al., “Revisiting MoE
Specialist Decomposition,” which is not a speculative-decoding paper. Dynamic
weight generation and fused FFN kernels are mentioned mostly without direct
citations.

**Required action:** cite the actual speculative-decoding/sampling papers and
primary dynamic-weight/fused-MLP work. Keep the Fedus citation only for the MoE
discussion. Avoid the blanket claim that all prior dynamic-weight methods
materialize ordinary tensors unless that scope is substantiated.

## Round-one concern status

### W1. Small selective win and missing controls — **partially addressed**

The full distribution and router-variance scope are now present, and random
routing plus one additional checkpoint were measured. The cell-definition
mismatch, padding/mask issue, lack of sequence-level uncertainty, and unmatched
replication prevent closure.

### W2. Systems estimate vs measurement — **partially addressed**

Traffic is more consistently labeled analytic and no fused/decode win is
claimed in the body. The abstract should still state explicitly that the
unfused forward is slower. More importantly, the timed result is not DDP
training and the routed-traffic table does not match token-level execution.

### W3. Single-layer/single-model evidence — **partially addressed**

Negative layer/family results and a preliminary Baichuan reconstruction probe
are useful. The selection provenance and causal property of layer 16 remain
unresolved; the full selective pipeline has not transferred to another model.

### W4. Downstream-task evaluation — **experiment run; inference incomplete**

Four probes are reported, satisfying the request to measure end-task accuracy.
Patch-rate accounting and paired/equivalence statistics still need correction.

### W5. Approximation proposition — **partially addressed**

The Eckart--Young statement is now correct for static matrix error. Constants
remain undefined, the data-conditioned discussion is not a corollary of the
bound, and the implemented expert model’s effective rank/K dependence is
missing. Reframe it as a generic bound plus a separate data-conditioned remark,
or provide a genuinely rank/K-aware result.

### W6. Always-patched broad penalty — **partially addressed**

The manuscript offers plausible distribution-shift hypotheses and now reports
negative dialogue/long-form transfer. Claims about context length and the
router rejecting high-loss out-of-family tokens are not demonstrated. Add
per-suite patch rates, score calibration, and length/error stratification, or
label the explanation explicitly as a hypothesis.

### W7. Typesetting — **verified fixed**

The recorded clean build has no overfull or underfull boxes.

### W8. Precision and units — **mostly fixed**

Headline training tables are normalized, but the early quality table still
uses three-decimal traffic-reduction factors while other tables use one
decimal. Apply one final consistency pass.

### W9. Systems-benchmark phrasing — **textually improved, empirically incomplete**

Calling it an FFN benchmark avoids implying a full-model run. “Distributed
training” should still be replaced unless actual synchronized DDP steps are
timed.

### W10. Related work — **not yet correctly closed**

A paragraph was added, but the speculative-decoding citation is wrong and the
dynamic-weight/fused-kernel coverage needs primary citations.

### Reproducibility — **partially addressed**

Manifest guards, explicit-text paths, and run summaries are strong. The public
release commitment is welcome. Nevertheless, the headline world-8 raw timing
artifacts are not locally recoverable, the exact 18-matrix SVD selection is not
artifacted, several new raw quality artifacts remain only on remote hosts, and
the manuscript refers to an artifact appendix that is not present. Add an
artifact table containing exact run IDs, commands/configs, software versions,
checkpoint/data hashes, and current availability. Do not state that every
number is exactly replayable until this is true.

## Required reruns versus manuscript-only corrections

### Required reruns

1. Actual synchronized DDP systems timing, or withdrawal of the distributed
   training-throughput claim.
2. Mask-aware, valid-token router evaluation with correct counters and explicit
   whole-group routing semantics.
3. Random/control and downstream reruns under the corrected router, reporting
   realized patch fractions.
4. An identical-grid checkpoint replication plus paired sequence-level
   uncertainty on an untouched test set.
5. Rank/parameter-matched quality controls for the expert-residual model.

### Manuscript-only corrections

1. Fix p(1-Gamma), Gamma_call, the effective-rank/K count, and the
   1.3--8.2% PPL-penalty typo.
2. Correct the 96-cell combinatorics and remove the unmatched “same 66/96”
   claim.
3. Change the early quality-table caption from layer 16 to layer 0, matching
   its source artifact.
4. Recast “task-accuracy-neutral” as “no detectable difference” pending paired
   analysis.
5. Correct the speculative-decoding citation and complete the platform/artifact
   table.
6. Shorten the abstract and state directly that the unfused forward is slower
   and decode latency remains unvalidated.

## Recommendation

The conceptual parameter-lifetime framing remains a meaningful contribution,
and the revision’s negative controls improve the paper. Acceptance should be
reconsidered after the causal baselines, systems-timing semantics, routing
implementation, and uncertainty analysis are corrected. Until then, the honest
status is **major revision**, not “all issues closed.”
