#!/usr/bin/env bash
# Upload a local file to ASI3 via sequential base64-append commands over
# the ASI3 shell daemon, with health-gating between chunks.
#
# Rationale: ASI3's HTTP egress proxy 403-blocks the S3 relay endpoint, and
# the fine-grained chunk uploader (ASI3_daemon_upload_files.js) needs 15+
# consecutive daemon wins against competing traffic.  This script uses
# fewer, larger chunks (default 6 KiB of base64 per command) and gates
# every command on daemon health, retrying each chunk until it lands.
#
# Usage:
#   bash scripts/asi3_chunked_upload.sh <local-file> <remote-file>
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL="$1"
REMOTE="$2"
CHUNK_B64_BYTES="${ASI3_CHUNK_B64_BYTES:-6144}"
MAX_TRIES_PER_CHUNK="${ASI3_CHUNK_MAX_TRIES:-30}"
POLL_SECONDS="${ASI3_CHUNK_POLL_SECONDS:-15}"
HEALTH_URL="${ASI3_DAEMON_HEALTH_URL:-http://127.0.0.1:20653/health}"

[ -f "$LOCAL" ] || { echo "missing local file: $LOCAL" >&2; exit 1; }

REMOTE_TMP="${REMOTE}.chunkupload.tmp"

wait_free() {
  for _ in $(seq 1 "$MAX_TRIES_PER_CHUNK"); do
    STATE=$(curl -s --max-time 8 "$HEALTH_URL" | python3 -c "
import json,sys
try:
    h=json.load(sys.stdin)
    print('FREE' if (not h.get('busy') and h.get('pendingRequestCount',0)==0 and h.get('ready')) else 'BUSY')
except Exception:
    print('DOWN')" 2>/dev/null)
    [ "$STATE" = "FREE" ] && return 0
    sleep "$POLL_SECONDS"
  done
  return 1
}

# Start: truncate remote tmp
wait_free || { echo "daemon never freed (truncate stage)" >&2; exit 1; }
bash "$SCRIPT_DIR/ASI3_shell.sh" "rm -f '$REMOTE_TMP'" >/dev/null 2>&1

# Split local file into base64 chunks
B64_FILE=$(mktemp)
base64 < "$LOCAL" | tr -d '\n' > "$B64_FILE"
TOTAL=$(wc -c < "$B64_FILE" | tr -d ' ')
NCHUNKS=$(( (TOTAL + CHUNK_B64_BYTES - 1) / CHUNK_B64_BYTES ))
echo "uploading $LOCAL ($TOTAL base64 bytes, $NCHUNKS chunks) -> $REMOTE"

OFF=0
for i in $(seq 1 "$NCHUNKS"); do
  CHUNK=$(dd if="$B64_FILE" bs="$CHUNK_B64_BYTES" skip=$((i-1)) count=1 2>/dev/null)
  RC=1
  for t in $(seq 1 "$MAX_TRIES_PER_CHUNK"); do
    wait_free || continue
    OUT=$(bash "$SCRIPT_DIR/ASI3_shell.sh" "printf '%s' '$CHUNK' | base64 -d >> '$REMOTE_TMP' && echo CHUNK_OK" 2>/dev/null)
    if printf '%s' "$OUT" | grep -q CHUNK_OK; then
      RC=0
      break
    fi
    sleep "$POLL_SECONDS"
  done
  [ "$RC" -ne 0 ] && { echo "chunk $i/$NCHUNKS failed after $MAX_TRIES_PER_CHUNK tries" >&2; rm -f "$B64_FILE"; exit 1; }
  echo "  chunk $i/$NCHUNKS ok"
  OFF=$((OFF + CHUNK_B64_BYTES))
done
rm -f "$B64_FILE"

LOCAL_MD5=$(md5 -q "$LOCAL")
wait_free || { echo "daemon never freed (verify stage)" >&2; exit 1; }
OUT=$(bash "$SCRIPT_DIR/ASI3_shell.sh" "mv '$REMOTE_TMP' '$REMOTE' && md5sum '$REMOTE'" 2>/dev/null)
# The ASI3_shell.sh response is JSON; the md5 appears in the "output" field
# followed by two spaces and the remote path.
REMOTE_MD5=$(printf '%s' "$OUT" | python3 -c "
import json,sys,re
raw=sys.stdin.read()
try:
    obj=json.loads(raw[raw.find('{'):])
    out=obj.get('output') or ''
    m=re.search(r'\b([0-9a-f]{32})\b\s', out)
    print(m.group(1) if m else '')
except Exception:
    print('')
" 2>/dev/null)
echo "local  md5: $LOCAL_MD5"
echo "remote md5: $REMOTE_MD5"
if [ "$LOCAL_MD5" = "$REMOTE_MD5" ]; then
  echo "UPLOAD VERIFIED OK"
  exit 0
else
  echo "MD5 MISMATCH" >&2
  exit 1
fi
