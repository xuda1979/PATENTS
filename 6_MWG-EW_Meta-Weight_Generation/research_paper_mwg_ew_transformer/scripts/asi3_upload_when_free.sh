#!/usr/bin/env bash
# Health-gated ASI3 daemon upload: polls the local ASI3 daemon health
# endpoint and only invokes the file upload while the channel is free.
#
# Why: the ASI3 browser channel is shared with other automation; the
# daemon busy-guard rejects commands submitted while competing traffic is
# in flight, and the built-in retry in ASI3_daemon_upload_files.js only
# covers 'stale_daemon_state_recovered', not the busy refusal.  This
# wrapper converts upload into a poll-and-strike loop.
#
# Usage (same args as ASI3_daemon_upload_files.js):
#   bash scripts/asi3_upload_when_free.sh \
#     --file <local> <remote> [--file ...]
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HEALTH_URL="${ASI3_DAEMON_HEALTH_URL:-http://127.0.0.1:20653/health}"
MAX_TRIES="${ASI3_UPLOAD_MAX_TRIES:-40}"
POLL_SECONDS="${ASI3_UPLOAD_POLL_SECONDS:-20}"

for i in $(seq 1 "$MAX_TRIES"); do
  STATE=$(curl -s --max-time 8 "$HEALTH_URL" | python3 -c "
import json,sys
try:
    h=json.load(sys.stdin)
    print('FREE' if (not h.get('busy') and h.get('pendingRequestCount',0)==0 and h.get('ready')) else 'BUSY')
except Exception:
    print('DOWN')
" 2>/dev/null)
  if [ "$STATE" = "FREE" ]; then
    echo "[asi3_upload_when_free] try $i: daemon FREE, uploading"
    node "$SCRIPT_DIR/ASI3_daemon_upload_files.js" "$@" && exit 0
    echo "[asi3_upload_when_free] try $i: upload failed; polling again"
  else
    echo "[asi3_upload_when_free] try $i: daemon $STATE"
  fi
  sleep "$POLL_SECONDS"
done
echo "[asi3_upload_when_free] giving up after $MAX_TRIES tries" >&2
exit 1
