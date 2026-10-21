# Frozen Quality Split Audit

Ready: `true`
Near-duplicate threshold: `0.82` (character `4`-grams)

| Split | Rows | Unique | Distinct templates | Compression | SHA-256 |
| --- | ---: | ---: | ---: | ---: | --- |
| train | 630 | 630 | 630 | 1.0000 | `832e3e3cda7c6b26c911096cb5097c31715439b0fc05f7b8c68efc87d9f65494` |
| dev | 300 | 300 | 300 | 1.0000 | `e67987ccb60cf5562c27af6ee226dca0edde1656c0cdd35d096b7c6361911995` |
| test | 303 | 303 | 303 | 1.0000 | `8e2acce8615c34c742b59f8840c63d3cf1ac841d1308d502ba31a0c114147b4e` |

| Pair | Exact overlap | Near-duplicate pairs | Maximum score |
| --- | ---: | ---: | ---: |
| train_vs_dev | 0 | 0 | -- |
| train_vs_test | 0 | 0 | -- |
| dev_vs_test | 0 | 0 | -- |

## Claim boundary

split integrity and diversity gate only; this audit does not establish model quality
