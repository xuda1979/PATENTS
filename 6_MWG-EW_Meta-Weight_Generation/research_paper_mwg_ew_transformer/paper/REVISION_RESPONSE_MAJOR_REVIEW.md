# Major-review revision response

This revision treats the review as a major redesign, not a wording-only rebuttal.
The paper is now explicitly a runtime proposal and feasibility study; it does
not claim that parameter lifetime has produced a measured efficiency or quality
gain.

`REVIEW_COMPLIANCE_AUDIT.md` gives the exhaustive mapping for all ten major
concerns, twelve additional issues, and six requested experimental packages.

| Review concern | Revision made | Current evidence boundary |
|---|---|---|
| Principal fused mechanism absent | Added a formal inference no-escape/no-store operator with an explicit entry-point signature and pre/postconditions (`ephemeral_ffn`), plus a matched four-arm protocol. The decisive comparison is generated/materialized core versus fused scratch-only core. The introduction states verbatim that the paper is a runtime proposal and feasibility analysis, not a completed efficiency method. | Fused arm and HBM counters remain unimplemented. |
| Target, benchmark, and causal prototype differ | Added an early artifact-separation table. Chose persistent factors plus a small generated core as the actual architecture; full-factor synthesis is now only a feasibility boundary. | Historical systems numbers still measure persistent low rank. |
| Full-factor granularity explosion | Added exact call-level accounting and break-even thresholds: `q >= 43` and `q >= 342` for the two reviewed geometries at `T=1024`. Added a quantitative reuse-range table (`tab:regimecall`) sweeping `q` for both geometries and the `B`-axis scaling (`q >= 342` at `B=8`; `q >= 1024` for `B in {2,3}`; none for `B >= 4` in the 1.5B geometry). Added prefill, cached-decode, continuous-batching, and training regimes. | Counts are analytic, not device traffic. |
| Paired scale redundancy | Replaced six paired scales with three identifiable diagonal cores. Added a redundancy proposition and a canonical `token_diag_core` implementation that emits `3r` values. | New mode needs fresh training. Legacy modes remain loadable only for compatibility. |
| Training lifecycle unspecified | Restricted the strict contract to inference. Specified `save-core` and deterministic `rematerialize-core` backward semantics, retained context/RNG state, generator gradients, and required cost reporting. | Neither training lifecycle is implemented by a fused kernel. |
| Operator/Frobenius norm mismatch | Replaced the theorem with a Frobenius-error perturbation bound using `||X Delta W||_F <= ||X||_2 ||Delta W||_F`; retained SVD energy now specializes it directly. | The result is labeled elementary sensitivity analysis, not learnability or generalization theory. |
| Systems evidence incomplete | Added the reconstructed dense aggregate with an explicit provenance footnote, explained the `24.9x` MAC versus `1.638x` historical gap, documented nearly flat rank timing, split mixed-dtype state accounting into elements and bytes, expanded the measurement protocol, and stated the per-launch warmup/timing protocol (three warmup, ten forward, three training iterations) directly in the compiled table captions. The abstract no longer headlines the irrecoverable numeric speedup. | Raw dense launch samples/variance, integrated DDP, optimizer timing, energy, and counters remain absent. |
| Quality evidence absent | Kept only the layer-0 support-set diagnostic and states that it shows no conditioning benefit. Causal tests are described as software validation only. | No held-out causal quality result is claimed. |
| Routing is not deployable | Removed “Selective” from the title. Defined a per-call threshold frozen on a separate calibration set, deterministic causal tie handling, whole-call dispatch, calibrated upper-confidence risk, mean non-inferiority, and tail-risk requirements. Any hard rank cap is restricted to an already-present scheduling window. | The historical `torch.where` path is non-skipping and supports no savings claim. |
| Novelty boundary unclear | Sharpened novelty to the formal no-escape/no-store contract plus call-level dispatch and counter-verifiable memory behavior. Added HyperGrid, Ouroboros, FlashMHF, and fast-weight comparisons. | Novelty remains a proposal until realized and measured. |
| Bibliographic error | Removed the false arXiv:2302.09908 entry; added the Fedus–Dean–Zoph review, DeepSeekMoE, and fast-weight-programmer reference; and corrected OLMo, Grok-1, ACT, and GLU metadata against primary records. All arXiv-identified entries were then re-checked against primary records, including Ouroboros (2604.02051), FlashMHF (2512.06989), and HyperGrid (2007.05891, ICLR 2021 title variant): all match; no further bib changes were needed. | All cited identifiers implicated by the review are verified correct. |
| Unrecoverable SVD table | Removed the 18-matrix table and specified checkpoint, projection-list, hash, singular-tail, and raw-artifact requirements for a rerun. | No replacement SVD sweep is reported. |
| Decode terminology and soft experts | Renamed `B=1,S=128` as a length-128 forward/prefill shape; separated cached `S=1` decode. The canonical method uses `K=0`; legacy soft experts are explicitly non-sparse. | Cached decode remains to be benchmarked. |

## Software changes and checks

- Added `token_diag_core` with one diagonal rank core for each of gate, up, and down.
- Changed the default comparison to persistent low rank versus the canonical diagonal core.
- Added analytic output metadata that distinguishes persistent-factor geometry from measured HBM traffic.
- Added tests for prefix invariance, batch invariance, explicit diagonal-core equivalence, `3r` controller width, exact legacy-scale collapse, and checkpoint round-trip.

## Post-audit additions (2026-08-24)

- Formal operator API (`eq:operator-api`) with dispatch-order, durable-state,
  tolerance, scratch-confinement, and counter postconditions.
- Quantitative reuse-range table (`tab:regimecall`) plus `B`-axis break-even
  thresholds.
- Verbatim "runtime proposal and feasibility analysis" framing in the
  introduction, tied to the evidence map.
- Abstract rewritten in idea → surviving-evidence → missing-experiment order.
- Figure 1 shows the core's tile shape (`r x r` diagonal, `r` scalars per
  projection).
- Per-launch warmup/timing protocol stated in the compiled systems table
  captions.
- Full marker sweep of the compiled text confirms every review item is present
  outside the source-only archive; fresh build is 23 pages with zero warnings.

## Experiments still required before a full-paper claim

1. Matched four-arm fused kernel experiment with HBM/L2/store counters.
2. Measured regime map over rank, reuse group, workload shape, core/controller structure, and basis/expert count.
3. Disjoint multi-seed causal quality training and evaluation.
4. Real branch-skipping whole-call routing with calibrated tail risk.
5. Explicit backward save/rematerialization implementation and measurements; until then, retain the inference-only scope.
6. End-to-end prefill, cached decode, continuous batching, synchronized optimizer-step, peak-memory, and energy results.
