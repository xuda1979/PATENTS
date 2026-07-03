# Router Split Manifest Audit

Manifest: `data/heldout/router_global_splits/manifest.json`

Train/eval overlap unique rows: `0`
Clean train rows after eval-union removal: `357`
Combined manifest ready: `true`

## Suite Cleanup

| Suite | Train | Own eval | Own overlap | Removed vs eval union | Clean train |
| --- | ---: | ---: | ---: | ---: | ---: |
| gsm8k_test | 130 | 130 | 0 | 0 | 130 |
| mbpp_test | 97 | 97 | 0 | 0 | 97 |
| alpaca_cleaned_train_tail | 130 | 130 | 0 | 0 | 130 |

## Claim Boundary

ready for one combined router train/eval run
