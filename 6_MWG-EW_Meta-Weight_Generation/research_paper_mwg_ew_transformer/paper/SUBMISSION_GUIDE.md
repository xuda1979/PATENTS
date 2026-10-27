# Journal readiness and next experiments

Current status: author-review preprint; scientific submission gate open. See `REVIEW_20261022.md` for the evidence and correction map.

1. Recover full canonical quality records, checkpoint identities, immutable data manifests and code/config hashes. Preserve archived summaries; do not overwrite them with reconstructed data.
2. Independently evaluate a causal trained model on frozen held-out text and tasks. Establish and freeze a meaningful quality margin before collecting new comparisons. Compare persistent low rank, same-budget ranks, fitted constant cores, and suitable quantized baselines.
3. Resolve v4's nonfinite repeated-call failure. Use an independent high-precision reference, explicit supported device/shape checks, and before/after finite checks. Identical v1/v4 output is insufficient.
4. Measure complete FFNs for materialized and fused versions of the same checkpoint with paired launches, timing distributions, cache policy and counters. Include S=1 cached decoding and prefill if making a serving claim.
5. Report the combined quality–latency tradeoff, including regressions. Do not combine a quality result from one mode with speed from another.
6. Have Da Xu review the paper and contribution statements. Select the journal, prepare its anonymized format if required, complete truthful availability/disclosure fields, and obtain final submission authorization.

TMLR official requirements checked October 22, 2026:
- Acceptance criteria: https://jmlr.org/tmlr/acceptance-criteria.html
- Author guide: https://jmlr.org/tmlr/author-guide.html

The author is the sole author, Da Xu, China Mobile Research Institute, xudayj@chinamobile.com. TMLR's double-blind submission requirement does not alter the requested authorship metadata in the author-review/preprint version. No account action or submission is authorized by this file.
