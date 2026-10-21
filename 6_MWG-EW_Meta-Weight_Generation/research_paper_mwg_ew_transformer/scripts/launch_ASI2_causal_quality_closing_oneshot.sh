#!/usr/bin/env bash
#
# One-shot CLOSING-test causal-quality launch through the ASI2 daemon.
# Extends the frozen v1 protocol to ALSO train token_diag_core at the
# matched rank (r401), giving a direct equal-rank r401 comparison that
# closes the ~2.3% parameter-matched gap (the paper's stated closing test).
#   Usage:
#     bash scripts/launch_ASI2_causal_quality_closing_oneshot.sh          # launch
#     bash scripts/launch_ASI2_causal_quality_closing_oneshot.sh --status  # poll
#
# Assumes the ASI2 daemon (port 19004) is authenticated (user completed the
# ~30s SMS login). See paper/CAUSAL_QUALITY_RUN_OPERATOR.md.
set -Eeuo pipefail

DAEMON="${DAEMON:-http://127.0.0.1:19004}"
TODO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

die() { echo "ERROR: $*" >&2; exit 1; }
json_field() {
  python3 -c "
import sys, json
d = json.loads(sys.stdin.read())
v = d.get('$1','')
if isinstance(v, bool):
    v = 'true' if v else 'false'
print(v)
"
}

health_ready() {
  curl -s -m 12 "$DAEMON/health" | json_field ready
}

# exec via daemon; prints output; returns exit status
daemon_exec() {
  python3 - "$DAEMON" "$1" <<'PY'
import json, sys, urllib.request
daemon, cmd = sys.argv[1], sys.argv[2]
req = urllib.request.Request(daemon + "/exec",
    data=json.dumps({"command": cmd}).encode(),
    headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=120) as r:
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

# push a local file to a remote path via base64 (single exec, chunked if needed)
push_file() {
  local local_path="$1" remote_path="$2"
  local b64 size chunk total chunks i part
  b64="$(base64 < "$local_path" | tr -d '\n')"
  size="${#b64}"
  chunk=180000   # chars per exec; keep well under terminal/time limits
  total=$(( (size + chunk - 1) / chunk ))
  echo "  pushing $(basename "$local_path") ($size b64 chars, $total parts)"
  daemon_exec "rm -f /tmp/_push.b64 '$remote_path'" >/dev/null   # truncate for idempotent re-runs
  for ((i=0;i<total;i++)); do
    part="${b64:i*chunk:chunk}"
    # NOTE: 'part' is already a base64 chunk of the file. Append the RAW chunk
    # to a temp b64 file, then decode ONCE at the end. (The previous code
    # re-encoded each chunk and decoded once on the remote, leaving the file
    # base64-of-base64 / base64-encoded on disk.)
    cmd="printf '%s' '$part' >> /tmp/_push.b64"
    daemon_exec "$cmd" >/dev/null || die "push part $i failed for $remote_path"
  done
  daemon_exec "base64 -d /tmp/_push.b64 > '$remote_path' && rm -f /tmp/_push.b64" >/dev/null \
    || die "final decode failed for $remote_path"
  # verify sha256
  local want got
  want="$(shasum -a 256 < "$local_path" | awk '{print $1}')"
  got="$(daemon_exec "sha256sum '$remote_path' | awk '{print \\\$1}'" | tail -1)"
  if [[ "$want" == "$got" ]]; then
    echo "  verified $remote_path (sha256 ok)"
  else
    # sha256sum line may be bracketed by transcript; re-extract
    got="$(daemon_exec "python3 -c \\\"import hashlib;print(hashlib.sha256(open('$remote_path','rb').read()).hexdigest())\\\"" | grep -E '^[0-9a-f]{64}$' | tail -1)"
    [[ "$want" == "$got" ]] && echo "  verified $remote_path (sha256 ok)" || die "sha256 mismatch for $remote_path"
  fi
}

launch() {
  echo "== Checking ASI2 auth =="
  local r
  r="$(health_ready)"
  [[ "$r" == "true" ]] || die "ASI2 daemon not authenticated (ready=$r). Do the ~30s SMS login first."
  echo "ASI2 ready."

  # Direct file transfer (robust regardless of S3 reachability from the cloud)
  echo "== Staging files on ASI2 =="
  local ROOT="/vllm-workspace/mwg-ew-transformer-research"
  daemon_exec "mkdir -p '$ROOT/experiments' '$ROOT/scripts' '$ROOT/data/quality' '$ROOT/results/oneshot_launch'" >/dev/null
  push_file "$TODO_DIR/experiments/mwg_quality_distillation.py" "$ROOT/experiments/mwg_quality_distillation.py"
  push_file "$TODO_DIR/experiments/audit_quality_threeway_split.py" "$ROOT/experiments/audit_quality_threeway_split.py"
  push_file "$TODO_DIR/scripts/launch_ASI2_causal_quality_closing_detached.sh" "$ROOT/scripts/launch_ASI2_causal_quality_closing_detached.sh"
  push_file "$TODO_DIR/data/quality/train.txt" "$ROOT/data/quality/train.txt"
  push_file "$TODO_DIR/data/quality/dev.txt" "$ROOT/data/quality/dev.txt"
  push_file "$TODO_DIR/data/quality/test.txt" "$ROOT/data/quality/test.txt"
  push_file "$TODO_DIR/data/quality/manifest.json" "$ROOT/data/quality/manifest.json"
  daemon_exec "chmod +x '$ROOT'/scripts/*.sh" >/dev/null

  echo "== Preflight =="
  daemon_exec "cd '$ROOT' && bash scripts/launch_ASI2_causal_quality_closing_detached.sh --check" || die "preflight failed"

  echo "== Launching detached closing-test worker (adds token_diag_core at matched rank r401) =="
  daemon_exec "cd '$ROOT' && env PROJECT_ROOT='$ROOT' nohup bash scripts/launch_ASI2_causal_quality_closing_detached.sh > /tmp/asi2_causal_launch.out 2>&1 < /dev/null & sleep 3; cat /tmp/asi2_causal_launch.out"
  echo
  echo "Launched. Monitor with:  bash scripts/launch_ASI2_causal_quality_oneshot.sh --status"
}

status() {
  local ROOT="/vllm-workspace/mwg-ew-transformer-research"
  echo "== Launch marker =="
  daemon_exec "cat /tmp/asi2_causal_launch.out 2>/dev/null || echo '(no launch marker yet)'" | tail -8
  echo "== Running workers =="
  daemon_exec "ps aux | grep -E 'mwg_quality_distillation|torch.distributed' | grep -v grep | head" | grep -vE '^\s*$' | tail -8
  echo "== result dirs =="
  daemon_exec "ls -1 '$ROOT/results/' 2>/dev/null | grep -i causal | tail" | grep -vE '^\s*$' | tail
}

# Pull a remote text file's contents to stdout (base64 round-trip to avoid
# terminal mangling); empty string if absent.
cat_remote() {
  python3 - "$DAEMON" "$1" <<'PY'
import json, sys, urllib.request, base64
daemon, path = sys.argv[1], sys.argv[2]
cmd = ("python3 - <<'PY2'\n"
       "import base64,os,sys\n"
       "p='%s'\n"
       "if os.path.isfile(p):\n"
       "    sys.stdout.write(base64.b64encode(open(p,'rb').read()).decode())\n"
       "else:\n"
       "    sys.stdout.write('__ABSENT__')\n"
       "PY2") % path
req = urllib.request.Request(daemon + "/exec",
    data=json.dumps({"command": cmd}).encode(),
    headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.load(r)
    out = (d.get("output") or "")
    for line in out.splitlines():
        line = line.strip()
        if not line or line in ("true", "false") or "base64" in line:
            continue
        if line == "__ABSENT__":
            break
        try:
            sys.stdout.write(base64.b64decode(line).decode())
            break
        except Exception:
            continue
except Exception:
    pass
PY
}

collect() {
  local ROOT="/vllm-workspace/mwg-ew-transformer-research"
  echo "== Causal-quality results on ASI2 =="
  local run_dirs
  run_dirs="$(daemon_exec "ls -1 '$ROOT/results/' 2>/dev/null | grep -iE 'causal_quality'" | grep -E 'asi2_causal_quality' | sort -u | tail -5)"
  if [[ -z "$run_dirs" ]]; then
    echo "(no causal-quality run dirs found on ASI2 yet)"
    return 0
  fi
  echo "$run_dirs"
  local outdir="$TODO_DIR/results/asi2_causal_quality_pull"
  mkdir -p "$outdir"
  local run seed report f first
  for run in $run_dirs; do
    echo "== $run =="
    for seed in 2026 2027 2028; do
      report=""
      first="$(daemon_exec "ls -1 '$ROOT/results/$run/seed_$seed/' 2>/dev/null | grep -E '^mwg_quality_distillation_.*\\.json\$' | head -1" | grep -E 'mwg_quality_distillation_' | head -1)"
      if [[ -n "$first" ]]; then
        report="$(cat_remote "$ROOT/results/$run/seed_$seed/$first")"
      fi
      if [[ -n "$report" ]]; then
        f="$outdir/${run}__seed_${seed}_report.json"
        printf '%s\n' "$report" > "$f"
        echo "  seed $seed report -> $f"
      else
        echo "  seed $seed report not present yet"
      fi
    done
  done
  echo "== Pulled reports in $outdir =="
  ls -1 "$outdir" 2>/dev/null | grep -i report || true
}

case "${1:-}" in
  --status)   status ;;
  --collect)  collect ;;
  *)          launch ;;
esac
