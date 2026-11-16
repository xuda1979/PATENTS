#!/usr/bin/env python3
"""Fetch a file from ASI2 through the daemon in base64 chunks.

The daemon's /exec response truncates long single-command output, so files
are base64-encoded remotely, split into small chunks, fetched one at a time,
and reassembled locally.

Usage:
  python3 asi2_fetch_file_20261114.py REMOTE_PATH LOCAL_PATH [CHUNK_BYTES]
"""

from __future__ import annotations

import base64
import json
import sys
import time
import urllib.request

DAEMON = "http://127.0.0.1:19004"
DEFAULT_CHUNK = 1500


def daemon_exec(cmd: str, timeout: int = 120) -> str:
    req = urllib.request.Request(
        DAEMON + "/exec",
        data=json.dumps({"command": cmd}).encode(),
        headers={"Content-Type": "application/json"},
    )
    last_exc: Exception | None = None
    for _ in range(30):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.load(r)
            out = (d.get("output") or "") + "\n" + (d.get("after") or "")
            if d.get("commandOk"):
                return out
            raise RuntimeError(f"remote command failed: {out}")
        except Exception as exc:  # noqa: BLE001 - retry loop
            last_exc = exc
            time.sleep(8)
    raise RuntimeError(f"daemon unreachable: {last_exc}")


def _extract_between_markers(text: str, start_marker: str, end_marker: str) -> str:
    """Pull the payload between two markers, immune to prompt noise."""
    if start_marker not in text or end_marker not in text:
        raise RuntimeError(f"markers missing from daemon output: {text[:200]!r}")
    payload = text.split(start_marker, 1)[1].split(end_marker, 1)[0]
    return "".join(payload.split())


def fetch(remote_path: str, local_path: str, chunk: int = DEFAULT_CHUNK) -> None:
    raw = daemon_exec(f"stat -c %s '{remote_path}'")
    digits = [ln.strip() for ln in raw.splitlines() if ln.strip().isdigit()]
    if not digits:
        raise RuntimeError(f"could not parse size from: {raw!r}")
    size = int(digits[-1])
    print(f"remote size: {size} bytes; fetching in {chunk}-byte chunks")
    pieces: list[str] = []
    offset = 0
    while offset < size:
        piece = daemon_exec(
            "echo __CHUNK_START__; "
            f"dd if='{remote_path}' bs={chunk} skip={offset // chunk} count=1 2>/dev/null | base64 -w0; "
            "echo; echo __CHUNK_END__"
        )
        pieces.append(_extract_between_markers(piece, "__CHUNK_START__", "__CHUNK_END__"))
        offset += chunk
        if (offset // chunk) % 8 == 0 or offset >= size:
            print(f"  {offset}/{size} bytes")
    data = base64.b64decode("".join(pieces))
    if len(data) != size:
        raise RuntimeError(f"size mismatch: decoded {len(data)} != {size}")
    with open(local_path, "wb") as handle:
        handle.write(data)
    print(f"saved {local_path} ({len(data)} bytes)")


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    remote, local = sys.argv[1], sys.argv[2]
    chunk = int(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_CHUNK
    fetch(remote, local, chunk)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
