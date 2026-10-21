#!/usr/bin/env bash
# Upload a local file to ASI2 via sequential base64-append commands over
# the ASI2 shell daemon (port 19004), with health-gating between chunks.
#
# Adapted from asi3_chunked_upload.sh (2026-10-08).  ASI2-specific notes
# from the 2026-10-08 test-file staging: 3000-char base64 chunks corrupted
# mid-line; ~1500-char chunks verified clean per-chunk.  Default chunk
# size is therefore 1500 base64 chars.
#
# Usage: scripts/asi2_chunked_upload.sh <local-file> <remote-path>
# Env:   ASI2_CHUNK_B64_BYTES (default 1500)
#        ASI2_CHUNK_MAX_TRIES (default 30)
#        ASI2_DAEMON_HEALTH_URL (default http://127.0.0.1:19004/health)

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL="$1"
REMOTE="$2"
CHUNK_B64_BYTES="${ASI2_CHUNK_B64_BYTES:-1500}"
MAX_TRIES="${ASI2_CHUNK_MAX_TRIES:-30}"
POLL_SECONDS="${ASI2_CHUNK_POLL_SECONDS:-10}"
HEALTH_URL="${ASI2_DAEMON_HEALTH_URL:-http://127.0.0.1:19004/health}"

[ -f "$LOCAL" ] || { echo "missing local file: $LOCAL" >&2; exit 1; }

REMOTE_TMP="${REMOTE}.chunkupload.tmp"

wait_free() {
  for _ in $(seq 1 "$MAX_TRIES"); do
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
bash "$SCRIPT_DIR/ASI2_shell.sh" "rm -f '$REMOTE_TMP'" >/dev/null 2>&1

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
  for t in $(seq 1 "$MAX_TRIES"); do
    wait_free || continue
    OUT=$(bash "$SCRIPT_DIR/ASI2_shell.sh" "printf '%s' '$CHUNK' | base64 -d >> '$REMOTE_TMP' && echo CHUNK_OK" 2>/dev/null)
    if printf '%s' "$OUT" | grep -q CHUNK_OK; then
      RC=0
      break
    fi
    echo "  chunk $i attempt $t failed; retrying" >&2
    sleep "$POLL_SECONDS"
  done
  if [ "$RC" -ne 0 ]; then
    echo "CHUNK $i FAILED after $MAX_TRIES attempts" >&2
    exit 1
  fi
  # Per-chunk progress marker every 5 chunks
  if [ $((i % 5)) -eq 0 ] || [ "$i" -eq "$NCHUNKS" ]; then
    echo "  chunk $i/$NCHUNKS done"
  fi
done
rm -f "$B64_FILE"

# Finalize: atomic move + verify md5
wait_free || { echo "daemon never freed (finalize stage)" >&2; exit 1; }
OUT=$(bash "$SCRIPT_DIR/ASI2_shell.sh" "mv '$REMOTE_TMP' '$REMOTE' && md5sum '$REMOTE'" 2>/dev/null)
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
LOCAL_MD5=$(md5 -q "$LOCAL")
echo "local  md5: $LOCAL_MD5"
echo "remote md5: $REMOTE_MD5"
if [ "$LOCAL_MD5" = "$REMOTE_MD5" ]; then
  echo "UPLOAD VERIFIED OK"
  exit 0
else
  echo "MD5 MISMATCH" >&2
  exit 1
fi
