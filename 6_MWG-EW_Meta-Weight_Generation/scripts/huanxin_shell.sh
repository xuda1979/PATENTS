#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "/Users/daxu/software/quantum-gpt/scripts/huanxin_shell.sh" "$@"
