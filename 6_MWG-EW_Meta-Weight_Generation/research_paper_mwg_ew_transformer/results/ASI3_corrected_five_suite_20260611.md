# ASI3 Corrected Five-Suite Validation, 2026-06-11

Verified local artifacts:

- `results/asi3_layer16_recovery_20260611T063442Z/layer16/mwg_quality_distillation_20260611T063555Z.json`
- `results/asi3_layer16_recovery_20260611T063442Z/ppl_layer16_r384_belle_lmce_cal_1200_heldout256_eval128_tb2.json`
- `results/asi3_corrected_eval_20260611T064834Z/token_router_five_suite.json`
- `results/asi3_corrected_eval_20260611T064834Z/hybrid_corrected_combined_eval.json`

## Generator recovery

Layer 16, rank 384:

| Method | Relative MSE | Cosine |
| --- | ---: | ---: |
| Static SVD | 0.835157 | 0.406409 |
| MWG expert residual | 0.130428 | 0.932599 |

## LM-CE calibration slice

| Policy | Tokens | Loss | PPL |
| --- | ---: | ---: | ---: |
| Dense | 17,812 | 1.321229 | 3.748023 |
| Patched | 17,812 | 0.966304 | 2.628212 |

Patched/dense PPL ratio: 0.701226.

## Corrected five-suite token-router validation

Five suites: GSM8K, MBPP, Alpaca-tail, Wikitext-103 validation, HellaSwag validation.

| Policy | Tokens | Actual patch fraction | PPL ratio |
| --- | ---: | ---: | ---: |
| Always patched | 74,456 | 1.000000 | 0.935222 |
| Router target 0.05 | 75,073 | 0.035859 | 0.969159 |
| Router target 0.10 | 75,073 | 0.066875 | 0.955161 |
| Router target 0.25 | 75,073 | 0.147102 | 0.940282 |

Suite-level always-patched ratios:

| Suite | PPL ratio |
| --- | ---: |
| GSM8K | 0.759710 |
| MBPP | 0.754216 |
| Alpaca-tail | 0.988355 |
| Wikitext-103 validation | 1.128375 |
| HellaSwag validation | 1.037403 |

Claim boundary: aggregate five-suite validation is positive, with strong gains
on GSM8K and MBPP. Wikitext-103 and HellaSwag regress under unconditional
layer replacement, so the paper should not claim uniform suite-wise improvement.

## Corrected hybrid manifest

| Policy | Tokens | PPL ratio |
| --- | ---: | ---: |
| Always patched hybrid | 39,394 | 0.849315 |

The earlier `hybrid_oracle_layer16_r384_lmce1200_belle256.json` artifact should
not be cited because it used a manifest JSON as text.
