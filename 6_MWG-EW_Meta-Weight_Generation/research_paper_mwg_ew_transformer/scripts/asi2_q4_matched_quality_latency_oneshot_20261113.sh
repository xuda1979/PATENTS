#!/usr/bin/env bash
#
# Q4 matched trained-model quality-latency launch through the ASI2 daemon
# (2026-11-13).  One-shot driver for the detached Q4 worker: stages the
# updated harness files (block-Givens student, trained-checkpoint benchmark
# path, Q4 worker), runs preflight, launches the worker detached, and offers
# --status / --collect / --pull helpers.
#
# Assumes the ASI2 daemon (port 19004) is authenticated.

set -Eeuo pipefail

DAEMON="${DAEMON:-http://127.0.0.1:19004}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="/vllm-workspace/mwg-ew-transformer-research"

die() { echo "ERROR: $*" >&2; exit 1; }

daemon_exec() {
  python3 - "$DAEMON" "$1" <<'PY'
import json, sys, urllib.request
daemon, cmd = sys.argv[1], sys.argv[2]
req = urllib.request.Request(daemon + "/exec",
    data=json.dumps({"command": cmd}).encode(),
    headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.load(r)
except Exception as e:
    print("EXEC_ERR: " + str(e)); sys.exit(2)
out = (d.get("output") or "") + "\n" + (d.get("after") or "")
print(out)
if d.get("commandOk"):
    sys.exit(0)
sys.exit(d.get("commandStatus") or 1)
PY
}

push_file() {
  local local_path="$1" remote_path="$2"
  local b64 size chunk total chunks i part
  b64="$(base64 < "$local_path" | tr -d '\n')"
  size="${#b64}"
  chunk=180000
  total=$(( (size + chunk - 1) / chunk ))
  daemon_exec "rm -f /tmp/_push.b64 '$remote_path'" >/dev/null
  for (( i=0; i<total; i++ )); do
    part="${b64:$((i*chunk)):$chunk}"
    daemon_exec "printf '%s' '$part' >> /tmp/_push.b64" >/dev/null \
      || die "push part $i failed for $remote_path"
  done
  daemon_exec "base64 -d /tmp/_push.b64 > '$remote_path' && rm -f /tmp/_push.b64 && wc -c < '$remote_path'" \
    || die "push decode failed for $remote_path"
}

health_ready() {
  python3 - "$DAEMON" <<'PY'
import json, sys, urllib.request
try:
    with urllib.request.urlopen(sys.argv[1] + "/health", timeout=10) as r:
        print(str(json.load(r).get("ready")).lower())
except Exception as e:
    print("EXEC_ERR: " + str(e))
PY
}

launch() {
  echo "== Checking ASI2 daemon =="
  local r
  r="$(health_ready)"
  [[ "$r" == "true" ]] || die "ASI2 daemon not authenticated (ready=$r)."
  echo "ASI2 ready."

  echo "== Staging Q4 harness files on ASI2 =="
  daemon_exec "mkdir -p '$ROOT/experiments' '$ROOT/scripts'" >/dev/null
  push_file "$REPO_DIR/experiments/mwg_quality_distillation.py" "$ROOT/experiments/mwg_quality_distillation.py"
  push_file "$REPO_DIR/experiments/mwg_block_givens.py" "$ROOT/experiments/mwg_block_givens.py"
  push_file "$REPO_DIR/experiments/mwg_four_arm_lifetime_benchmark.py" "$ROOT/experiments/mwg_four_arm_lifetime_benchmark.py"
  push_file "$REPO_DIR/experiments/mwg_ppl_patch_eval.py" "$ROOT/experiments/mwg_ppl_patch_eval.py"
  push_file "$REPO_DIR/scripts/asi2_q4_matched_quality_latency_worker_20261113.sh" "$ROOT/scripts/asi2_q4_matched_quality_latency_worker_20261113.sh"
  daemon_exec "chmod +x '$ROOT'/scripts/*.sh" >/dev/null

  echo "== Preflight =="
  daemon_exec "cd '$ROOT' && bash scripts/asi2_q4_matched_quality_latency_worker_20261113.sh --check" \
    || die "Q4 preflight failed"

  echo "== Launching detached Q4 worker =="
  daemon_exec "cd '$ROOT' && env PROJECT_ROOT='$ROOT' nohup bash scripts/asi2_q4_matched_quality_latency_worker_20261113.sh > /tmp/asi2_q4_launch.out 2>&1 < /dev/null & sleep 3; cat /tmp/asi2_q4_launch.out"
  echo
  echo "Launched. Monitor with: bash scripts/asi2_q4_matched_quality_latency_oneshot_20261113.sh --status"
}

status() {
  echo "== Launch marker =="
  daemon_exec "cat /tmp/asi2_q4_launch.out 2>/dev/null || echo '(no launch marker)'" | tail -8
  echo "== Worker processes =="
  daemon_exec "ps aux | grep -E 'mwg_quality_distillation|asi2_q4' | grep -v grep | head" | tail -6
  echo "== Latest Q4 run dirs =="
  daemon_exec "ls -1t '$ROOT/results/' 2>/dev/null | grep q4 | head -3"
  echo "== Latest status.json =="
  local latest
  latest="$(daemon_exec "ls -1t '$ROOT/results/' 2>/dev/null | grep q4 | head -1")"
  if [[ -n "$latest" ]]; then
    daemon_exec "cat '$ROOT/results/$latest/status.json' 2>/dev/null || echo '(no status yet)'"
  fi
}

collect() {
  local outdir="${1:-$REPO_DIR/results/asi2_q4_matched_quality_latency_20261113}"
  mkdir -p "$outdir"
  local latest
  latest="$(daemon_exec "ls -1t '$ROOT/results/' 2>/dev/null | grep q4 | head -1")"
  [[ -n "$latest" ]] || die "no q4 run dir found"
  echo "Collecting from $latest"
  local files
  files="$(daemon_exec "find '$ROOT/results/$latest' -maxdepth 2 -name '*.json' | sort")"
  local f base remote_b64
  for f in $files; do
    base="$(echo "$f" | sed "s|$ROOT/results/||; s|/|__|g")"
    remote_b64="$(daemon_exec "base64 -w0 '$f' 2>/dev/null")"
    [[ -n "$remote_b64" ]] || continue
    printf '%s' "$remote_b64" | base64 -d > "$outdir/$base" 2>/dev/null || echo "WARN: decode failed for $base"
    echo "  $base"
  done
  echo "== Collected into $outdir =="
}

case "${1:-}" in
  --status)  status ;;
  --collect) collect "${2:-}" ;;
  *)         launch ;;
esac
