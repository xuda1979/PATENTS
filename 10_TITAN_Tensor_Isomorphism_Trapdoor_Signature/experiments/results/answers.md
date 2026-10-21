# -Oriented Quantitative Findings

All numbers in this file come from actual local execution on the current machine.

## 1. Core Correctness Questions

| Scheme | Verify Success | Tampered Message Reject | Tampered Signature Reject |
| --- | ---: | ---: | ---: |
| titan-n8-r16 | 50/50 (100.00%) | 50/50 (100.00%) | 50/50 (100.00%) |
| titan-n8-r32 | 50/50 (100.00%) | 50/50 (100.00%) | 50/50 (100.00%) |
| titan-n10-r32 | 50/50 (100.00%) | 50/50 (100.00%) | 50/50 (100.00%) |
| titan-n12-r32 | 50/50 (100.00%) | 50/50 (100.00%) | 50/50 (100.00%) |
| falcon-512 | 50/50 (100.00%) | 50/50 (100.00%) | 50/50 (100.00%) |
| falcon-1024 | 50/50 (100.00%) | 50/50 (100.00%) | 50/50 (100.00%) |

## 2. Engineering Cost Comparison

| Scheme | Public Key (B) | Secret Key (B) | Signature (B) | KeyGen Mean (ms) | Sign Mean (ms) | Verify Mean (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| titan-n8-r16 | 512 | 384 | 3104 | 4.539 | 16.534 | 1.808 |
| titan-n8-r32 | 512 | 384 | 6176 | 4.936 | 33.794 | 3.495 |
| titan-n10-r32 | 1000 | 600 | 9632 | 6.525 | 43.297 | 4.136 |
| titan-n12-r32 | 1728 | 864 | 13856 | 10.096 | 50.150 | 4.806 |
| falcon-512 | 896 | 3584 | 666 | 2328.044 | 16.280 | 4.263 |
| falcon-1024 | 1792 | 7168 | 1280 | 11414.624 | 40.760 | 10.706 |

## 3. TITAN Parameter Scaling

| TITAN Config | N | Rounds | Public Key (B) | Signature (B) | Sign Mean (ms) | Verify Mean (ms) | Verify Throughput (sig/s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| titan-n8-r16 | 8 | 16 | 512 | 3104 | 16.534 | 1.808 | 553.097 |
| titan-n8-r32 | 8 | 32 | 512 | 6176 | 33.794 | 3.495 | 286.123 |
| titan-n10-r32 | 10 | 32 | 1000 | 9632 | 43.297 | 4.136 | 241.779 |
| titan-n12-r32 | 12 | 32 | 1728 | 13856 | 50.150 | 4.806 | 208.073 |

## 4. Quantitative Takeaways

- Against `falcon-512`, `titan-n8-r16` shows 512.9x faster key generation and 2.36x faster verification on this machine.
- Against `falcon-512`, `titan-n8-r16` uses 0.57x public-key bytes, 1.02x signing time, and 4.66x signature bytes.
- Against `falcon-1024`, `titan-n12-r32` shows 1130.6x faster key generation and 2.23x faster verification, with public key at 0.96x of Falcon-1024.
- The same `titan-n12-r32` point signs in 1.23x the time of `falcon-1024` and produces 10.82x signature bytes.
- All TITAN configurations achieved 100% observed verification success in the executed trials.
- All TITAN configurations rejected every tested tampered message and every tested tampered signature.
- The current TITAN proof-of-concept shows a compute-versus-signature-size tradeoff: latency can be low, but uncompressed signatures are larger than Falcon.
- Because TITAN parameter points are not yet mapped to standard security categories, these results should be read as engineering evidence, not security-level-equivalent benchmarking.
