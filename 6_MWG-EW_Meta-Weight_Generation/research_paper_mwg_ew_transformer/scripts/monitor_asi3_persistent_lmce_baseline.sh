#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <asi3_persistent_lmce_baseline_run_id>" >&2
  exit 2
fi

RUN_ID="$1"
PROJECT_ROOT="${PROJECT_ROOT:-/vllm-workspace/mwg-ew-transformer-research}"

export AI3_ALLOW_BROWSER="${AI3_ALLOW_BROWSER:-0}"
export HUANXIN_ALLOW_STANDALONE_FALLBACK="${HUANXIN_ALLOW_STANDALONE_FALLBACK:-0}"
export HUANXIN_WAIT_MS="${HUANXIN_WAIT_MS:-15000}"

if [[ "$AI3_ALLOW_BROWSER" == "1" ]]; then
  echo "ERROR: refusing browser fallback; unset AI3_ALLOW_BROWSER for daemon-only monitor." >&2
  exit 2
fi

REMOTE_CMD=$(cat <<'EOF'
python3 - "$PROJECT_ROOT" "$RUN_ID" <<'PY'
import json
import re
import sys
from pathlib import Path

project_root = Path(sys.argv[1])
run_id = sys.argv[2]
status_path = project_root / "logs" / f"{run_id}.status.json"
log_path = project_root / "logs" / f"{run_id}.log"
outdir = project_root / "results" / run_id
launch_path = outdir / "broad_validation_launch.txt"

def read_tail(path: Path, limit: int = 80) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:]

status = None
if status_path.exists():
    status = json.loads(status_path.read_text(encoding="utf-8"))

broad_launch_tail = read_tail(launch_path, 40)
broad_run_ids = []
for line in broad_launch_tail:
    match = re.search(r"run_id=(asi3_broad_validation_[0-9TZ]+)", line)
    if match:
        broad_run_ids.append(match.group(1))

payload = {
    "run_id": run_id,
    "project_root": str(project_root),
    "status_path": str(status_path),
    "status_exists": status_path.exists(),
    "status": status,
    "wrapper_log": str(log_path),
    "wrapper_log_exists": log_path.exists(),
    "wrapper_log_tail": read_tail(log_path),
    "outdir": str(outdir),
    "outdir_exists": outdir.exists(),
    "result_json": sorted(str(path) for path in outdir.glob("**/*.json")) if outdir.exists() else [],
    "checkpoint_count": len(list(outdir.glob("**/*.pt"))) if outdir.exists() else 0,
    "broad_validation_launch": str(launch_path),
    "broad_validation_launch_exists": launch_path.exists(),
    "broad_validation_run_ids": broad_run_ids,
    "broad_validation_launch_tail": broad_launch_tail,
}
print(json.dumps(payload, indent=2))
PY
EOF
)

REMOTE_CMD="${REMOTE_CMD//\$PROJECT_ROOT/$PROJECT_ROOT}"
REMOTE_CMD="${REMOTE_CMD//\$RUN_ID/$RUN_ID}"

cd "$(dirname "${BASH_SOURCE[0]}")/.."
bash scripts/ai3_shell.sh "$REMOTE_CMD"
