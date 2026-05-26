#!/usr/bin/env bash
set -euo pipefail

# Leave-suite-out broad router sweep:
# for each target broad suite, train the token router on explicit router texts
# plus the other broad suites, with exact target-suite eval lines removed.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export RUN_PREFIX="${RUN_PREFIX:-asi3_token_router_leave_suiteout_seed_sweep}"
export SPLIT_PREP_SCRIPT="${SPLIT_PREP_SCRIPT:-experiments/prepare_router_leave_suiteout_splits.py}"
export TRAIN_FRACTION="${TRAIN_FRACTION:-0.75}"
export SEEDS="${SEEDS:-0,1,2}"

exec bash "$SCRIPT_DIR/launch_asi3_token_router_broad_seed_sweep_detached.sh"
