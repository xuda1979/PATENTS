#!/usr/bin/env python3
"""Stage a local file to ASI2 through the daemon (base64 chunked).

Usage: python3 asi2_stage_file_20261113.py LOCAL_PATH REMOTE_PATH
"""
import base64
import json
import sys
import urllib.request

DAEMON = "http://127.0.0.1:19004"
CHUNK = 180_000


def daemon_exec(cmd: str, timeout: int = 300) -> dict:
    req = urllib.request.Request(
        DAEMON + "/exec",
        data=json.dumps({"command": cmd}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def stage(local_path: str, remote_path: str) -> None:
    b64 = base64.b64encode(open(local_path, "rb").read()).decode()
    daemon_exec(f"rm -f /tmp/_push.b64 '{remote_path}'")
    total = (len(b64) + CHUNK - 1) // CHUNK
    for i in range(total):
        part = b64[i * CHUNK : (i + 1) * CHUNK]
        d = daemon_exec(f"printf '%s' '{part}' >> /tmp/_push.b64")
        if not d.get("commandOk"):
            raise SystemExit(f"push part {i + 1}/{total} failed")
    d = daemon_exec(
        f"base64 -d /tmp/_push.b64 > '{remote_path}' && rm -f /tmp/_push.b64 && wc -c < '{remote_path}'"
    )
    if not d.get("commandOk"):
        raise SystemExit(f"decode failed for {remote_path}")
    size = (d.get("output") or "").strip()
    local_size = len(open(local_path, "rb").read())
    print(f"staged {local_path} -> {remote_path} ({size} bytes; local {local_size})")
    if size != str(local_size):
        raise SystemExit(f"size mismatch: remote {size} != local {local_size}")


if __name__ == "__main__":
    stage(sys.argv[1], sys.argv[2])
