# Real Experiments for TITAN Patent

This directory contains only executable benchmark code and machine-generated
result artifacts for the TITAN patent draft.

Rules followed here:

- No simulated benchmark numbers
- No interpolated or hand-filled tables
- Every reported timing, size, and success rate must come from an actual run
- Falcon comparison data must come from the real local implementation under
  `5_QTS-Falcon_Threshold_Signature/real_benchmarks/falcon_standard/falcon_impl`

Main files:

- `titan_impl.py` — integer-only TITAN proof-of-concept implementation
- `run_real_benchmarks.py` — runs TITAN and Falcon on the current machine and
  writes raw/summary outputs
- `results/raw_benchmark.csv` — per-iteration measurements
- `results/summary.json` — machine-readable aggregate statistics
- `results/reviewer_answers.md` — reviewer-oriented quantitative findings

Notes:

- The Falcon import uses a local `beartype` no-op shim if `beartype` is absent
  in the current Python environment. This only disables runtime type checking;
  it does not replace the Falcon algorithm implementation itself.
- TITAN parameter sets in these experiments are proof-of-concept engineering
  points. They are not claimed to be security-level matched to NIST-standard
  Falcon parameters.
