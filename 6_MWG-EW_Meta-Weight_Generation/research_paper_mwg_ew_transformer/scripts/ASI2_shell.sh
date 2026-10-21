#!/usr/bin/env bash
set -euo pipefail

# ASI2 shell wrapper (2026-10-08).  Mirrors ASI3_shell.sh but targets the
# ASI2 daemon (env ASI2, port 19004, quantum-gpt browser-automation stack).
#
# Usage: scripts/ASI2_shell.sh '<remote shell command>'
#
# Daemon health: curl -s http://127.0.0.1:19004/health

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QUANTUM_GPT_DIR="${QUANTUM_GPT_DIR:-/Users/daxu/software/quantum-gpt}"

HEALTH_URL="http://127.0.0.1:19004/health"
STATE=$(curl -s -m 10 "$HEALTH_URL" | python3 -c "
import json,sys
try:
    h=json.load(sys.stdin)
    print('FREE' if (not h.get('busy') and h.get('ready')) else 'BUSY')
except Exception:
    print('DOWN')" 2>/dev/null)
if [ "$STATE" != "FREE" ]; then
  echo "ASI2 daemon not FREE (state=$STATE); refusing to launch a replacement browser." >&2
  echo "Recover the daemon (see .huanxin_shell_connections/ASI2.json) or retry later." >&2
  exit 2
fi

exec node "$QUANTUM_GPT_DIR/browser-automation/huanxin_shell_exec.js" \
  ASI2 --require-daemon --wait-ms "${HUANXIN_WAIT_MS:-20000}" --command "$*"
