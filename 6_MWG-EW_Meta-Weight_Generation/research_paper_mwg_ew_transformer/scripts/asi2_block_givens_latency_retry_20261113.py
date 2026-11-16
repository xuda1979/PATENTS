#!/usr/bin/env python3
"""Retry the failed block-Givens latency arm on ASI2 (2026-11-13).

The Q4 matched run trained ``mwg_block_givens_r384`` students whose latency
arm failed: the benchmark's ``load_trained_master_weights`` did not
understand block-Givens checkpoints (it misread the angle head as a
token_diag_core controller).  This driver stages the fixed benchmark (and
the patched Q4 worker), re-runs ONLY the block-Givens latency measurement
against the already-trained checkpoints from run
``asi2_q4_matched_quality_latency_20261113T134959Z``, and merges the new
``latency_mwg_block_givens_r384.json`` rows into that run's
``q4_summary.json`` (in place, with a timestamped backup).

Usage:
  python3 asi2_block_givens_latency_retry_20261113.py push     # stage files
  python3 asi2_block_givens_latency_retry_20261113.py run      # re-run + merge
  python3 asi2_block_givens_latency_retry_20261113.py status   # tail retry log
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request

DAEMON = "http://127.0.0.1:19004"
ROOT = "/vllm-workspace/mwg-ew-transformer-research"
RUN_ID = "asi2_q4_matched_quality_latency_20261113T134959Z"
RUN_DIR = f"{ROOT}/results/{RUN_ID}"
SEEDS = [2026, 2027, 2028, 2029]
STUDENT = "mwg_block_givens_r384"
RANK = 384
LOG = f"{ROOT}/logs/asi2_block_givens_latency_retry_{RUN_ID}.log"

# Latency geometry mirrors the Q4 worker defaults (Qwen2.5-1.5B layer 16).
BENCH_D = 1536
BENCH_M = 8960
BENCH_SEQ = 128
BENCH_DTYPE = "fp16"
BENCH_WARMUP = 10
BENCH_ITERS = 50
BENCH_REPEATS = 3

RETRY_REMOTE_WORKER = f"{ROOT}/scripts/asi2_block_givens_latency_retry_worker_20261113.sh"


def daemon_exec(cmd: str, timeout: int = 300) -> tuple[bool, str]:
    req = urllib.request.Request(
        DAEMON + "/exec",
        data=json.dumps({"command": cmd}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.load(r)
    except Exception as exc:
        return False, f"EXEC_ERR: {exc}"
    out = (d.get("output") or "") + "\n" + (d.get("after") or "")
    return bool(d.get("commandOk")), out


def push_file(local_path: str, remote_path: str) -> None:
    import base64
    import pathlib

    b64 = base64.b64encode(pathlib.Path(local_path).read_bytes()).decode()
    chunk = 150000
    parts = [b64[i : i + chunk] for i in range(0, len(b64), chunk)]
    daemon_exec(f"rm -f /tmp/_push.b64 '{remote_path}'")
    for index, part in enumerate(parts):
        # Pass the chunk as a printf argument (base64 has no single quotes).
        last = 30
        while True:
            ok, out = daemon_exec(f"printf '%s' '{part}' >> /tmp/_push.b64")
            if ok or last <= 0:
                break
            time.sleep(10)
            last -= 1
        if not ok:
            print("push chunk failed:", out)
            sys.exit(1)
        print(f"  chunk {index + 1}/{len(parts)} pushed")
    ok, out = daemon_exec(
        f"base64 -d /tmp/_push.b64 > '{remote_path}' && rm -f /tmp/_push.b64 && wc -c < '{remote_path}'"
    )
    if not ok:
        print("push finalize failed:", out)
        sys.exit(1)
    print(f"pushed {local_path} -> {remote_path} ({out.strip()} bytes remote)")


WORKER_SCRIPT = r"""#!/usr/bin/env bash
set -Eeuo pipefail
# Detached retry worker: block-Givens latency only (no retraining).
ROOT="/vllm-workspace/mwg-ew-transformer-research"
RUN_ID="asi2_q4_matched_quality_latency_20261113T134959Z"
RUN_DIR="$ROOT/results/$RUN_ID"
SEEDS="2026 2027 2028 2029"
STUDENT="mwg_block_givens_r384"
RANK=384
LOG="$ROOT/logs/asi2_block_givens_latency_retry_${RUN_ID}.log"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$LOG"; }

log "block-givens latency retry worker start"
cd "$ROOT"
for seed in $SEEDS; do
  outdir="$RUN_DIR/seed_${seed}"
  ckpt="$outdir/checkpoints/${STUDENT}.pt"
  if [[ ! -s "$ckpt" ]]; then
    log "seed ${seed}: checkpoint missing ($ckpt); skipping"
    continue
  fi
  rm -f "$outdir/latency_${STUDENT}.json"
  python3 experiments/mwg_four_arm_lifetime_benchmark.py \
    --d 1536 --m 8960 --rank "$RANK" --controller-hidden 384 \
    --batch 1 --seq 128 --amplitude 0.05 --dtype fp16 \
    --arms dense,persistent,block_givens \
    --device auto --warmup 10 --iters 50 --repeats 3 \
    --trained-checkpoint "$ckpt" \
    --run-label "q4_retry_${RUN_ID}_seed_${seed}_${STUDENT}" \
    --output "$outdir/latency_${STUDENT}.json" \
    >> "$LOG" 2>&1 || { log "seed ${seed}: retry latency FAILED (kept old state)"; continue; }
  log "seed ${seed}: retry latency measured (arms: dense,persistent,block_givens)"
done

# ---- Merge latency rows into q4_summary.json (timestamped backup first). ----
python3 - "$RUN_DIR" $SEEDS "$STUDENT" <<'PY' >> "$LOG" 2>&1
import json, shutil, sys
from datetime import datetime, timezone
from pathlib import Path

run_dir = Path(sys.argv[1])
seeds = [int(s) for s in sys.argv[2:-1]]
student = sys.argv[-1]
summary_path = run_dir / "q4_summary.json"
backup = run_dir / (
    "q4_summary.json.bak_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
)
shutil.copy2(summary_path, backup)
summary = json.loads(summary_path.read_text())
rows = summary["rows"]

# Drop any stale retry rows from a previous partial merge, then re-add.
merged = 0
for seed in seeds:
    lat_path = run_dir / f"seed_{seed}" / f"latency_{student}.json"
    if not lat_path.is_file():
        continue
    d = json.loads(lat_path.read_text())
    arms = d.get("arms", {})
    if "block_givens" not in (arms or {}):
        continue
    rows[:] = [
        r
        for r in rows
        if not (r.get("student") == student and "latency_ms" in r and r.get("seed") == seed)
    ]
    row = {
        "seed": seed,
        "student": student,
        "latency_ms": {
            arm: res.get("timing", {}).get("median_ms") for arm, res in arms.items()
        },
        "trained_checkpoint_sha256": (d.get("trained_checkpoint") or {}).get("sha256"),
    }
    rows.append(row)
    merged += 1

summary_path.write_text(json.dumps(summary, indent=2) + "\n")
print(f"merged {merged} latency rows into {summary_path}; backup at {backup}")
PY
log "block-givens latency retry worker complete (merged summary)"
"""

LOCAL_STAGE = {
    "experiments/mwg_four_arm_lifetime_benchmark.py": f"{ROOT}/experiments/mwg_four_arm_lifetime_benchmark.py",
    "experiments/mwg_quality_distillation.py": f"{ROOT}/experiments/mwg_quality_distillation.py",
    "experiments/mwg_block_givens.py": f"{ROOT}/experiments/mwg_block_givens.py",
}


def cmd_push() -> None:
    import pathlib

    here = pathlib.Path(__file__).resolve().parent
    for local, remote in LOCAL_STAGE.items():
        push_file(str(here.parent / local), remote)
    # Stage the retry worker script itself (generated fresh each push).
    tmp = here / "asi2_block_givens_latency_retry_worker_20261113.sh"
    tmp.write_text(WORKER_SCRIPT)
    push_file(str(tmp), RETRY_REMOTE_WORKER)
    daemon_exec(f"chmod +x '{RETRY_REMOTE_WORKER}'")
    print("staged retry worker:", RETRY_REMOTE_WORKER)


def cmd_run() -> None:
    ok, out = daemon_exec(
        f"cd {ROOT} && nohup bash {RETRY_REMOTE_WORKER} >/dev/null 2>&1 & echo started-$!",
        timeout=60,
    )
    print(out.strip() if ok else f"start failed: {out}")
    if not ok:
        sys.exit(1)


def cmd_status() -> None:
    ok, out = daemon_exec(f"tail -30 {LOG} 2>/dev/null || echo 'no log yet'")
    print(out)


def cmd_merge_check() -> None:
    ok, out = daemon_exec(
        f"python3 -c \"import json; d=json.load(open('{RUN_DIR}/q4_summary.json')); "
        f"rows=[r for r in d['rows'] if r.get('student')=='{STUDENT}' and 'latency_ms' in r]; "
        f"print('block_givens latency rows:', len(rows)); "
        f"[print(json.dumps(r)) for r in rows]\""
    )
    print(out)


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "status"
    if mode == "push":
        cmd_push()
    elif mode == "run":
        cmd_run()
    elif mode == "status":
        cmd_status()
    elif mode == "mergecheck":
        cmd_merge_check()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
