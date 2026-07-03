#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
QUANTUM_GPT_DIR="${QUANTUM_GPT_DIR:-/Users/daxu/software/quantum-gpt}"

export HUANXIN_TRAIN_DEV_URL="${HUANXIN_TRAIN_DEV_URL:-https://aihuanxin.cn/kunlun/kl-web?poolId=6&projectId=21b4208dde424e96b159362ef49c9c96#/train-dev/environment/dl-c72bd81a96e33134bbe0ae4a478fbab0?name=ASI3}"
export HUANXIN_PROFILE_COPY_NAME="${HUANXIN_PROFILE_COPY_NAME:-mwg-ew-ASI3}"
export HUANXIN_ALLOW_STANDALONE_FALLBACK="${HUANXIN_ALLOW_STANDALONE_FALLBACK:-0}"
export HUANXIN_HEADLESS="${HUANXIN_HEADLESS:-1}"

WAIT_MS="${HUANXIN_WAIT_MS:-180000}"
DAEMON_HEALTH_URL="${ASI3_DAEMON_HEALTH_URL:-http://127.0.0.1:20653/health}"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 \"<remote command>\"" >&2
  exit 1
fi

cd "$ROOT_DIR"
if [[ "${ASI3_ALLOW_BROWSER:-0}" == "1" ]]; then
  exec node "$QUANTUM_GPT_DIR/browser-automation/huanxin_shell_exec.js" \
    ASI3 --skip-daemon --wait-ms "$WAIT_MS" --command "$*"
fi

if [[ "${ASI3_SKIP_DAEMON_HEALTH_GUARD:-0}" != "1" ]] && command -v python3 >/dev/null 2>&1; then
  HEALTH_JSON="$(python3 - "$DAEMON_HEALTH_URL" <<'PY' 2>/dev/null || true
import sys
import urllib.request

try:
    with urllib.request.urlopen(sys.argv[1], timeout=2) as response:
        print(response.read().decode("utf-8"))
except Exception:
    pass
PY
)"
  if [[ -n "$HEALTH_JSON" ]]; then
    python3 - "$HEALTH_JSON" <<'PY'
import json
import sys
from datetime import datetime, timezone

health = json.loads(sys.argv[1])
if health.get("env") != "ASI3":
    raise SystemExit(
        "ERROR: refusing ASI3 daemon command because the health endpoint is not ASI3 "
        f"(env={health.get('env')!r}); check ASI3_DAEMON_HEALTH_URL."
    )
if health.get("startupFailureKind") == "shell_endpoint_unavailable" or health.get("shellEndpointFailure"):
    raise SystemExit(
        "ERROR: refusing ASI3 daemon command because the ASI3 shell endpoint is unavailable: "
        f"{health.get('healthSummary') or health.get('startupError') or 'unknown'}"
    )
if not health.get("ready"):
    raise SystemExit(
        "ERROR: refusing ASI3 daemon command because the ASI3 daemon is not ready: "
        f"{health.get('healthSummary') or health.get('startupError') or 'unknown'}"
    )
if health.get("busy") or health.get("pendingRequestCount", 0):
    raise SystemExit(
        "ERROR: refusing ASI3 daemon command because daemon is busy or has pending requests; "
        "set ASI3_SKIP_DAEMON_HEALTH_GUARD=1 only for a deliberate manual recovery attempt."
    )
started = health.get("lastCommandStartedAt")
completed = health.get("lastCommandCompletedAt")
if started and completed and started > completed:
    def parse_iso(value):
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))

    try:
        started_dt = parse_iso(started)
        completed_dt = parse_iso(completed)
        now_dt = datetime.now(timezone.utc)
        stale_gap_seconds = (started_dt - completed_dt).total_seconds()
        age_seconds = (now_dt - started_dt).total_seconds()
    except Exception:
        stale_gap_seconds = None
        age_seconds = None

    if not (
        stale_gap_seconds is not None
        and stale_gap_seconds >= 0.0
        and stale_gap_seconds <= 120.0
        and age_seconds is not None
        and age_seconds >= 30.0
        and not health.get("busy")
        and not health.get("pendingRequestCount", 0)
    ):
        raise SystemExit(
            "ERROR: refusing ASI3 daemon command because the previous command appears incomplete "
            f"(started {started}, completed {completed}); set ASI3_SKIP_DAEMON_HEALTH_GUARD=1 only "
            "for a deliberate manual recovery attempt."
        )
PY
  fi
fi

export HUANXIN_WAIT_MS="$WAIT_MS"
exec bash "$QUANTUM_GPT_DIR/scripts/huanxin_shell.sh" ASI3 "$*"
