#!/usr/bin/env python3
"""Execute one command on ASI2 through the authenticated daemon.

Usage: python3 asi2_daemon_exec_20261113.py "command" [--timeout SECONDS]

Prints the daemon's `output` field; exit code mirrors commandOk/commandStatus.
"""
import json
import sys
import urllib.request

DAEMON = "http://127.0.0.1:19004"


def main() -> int:
    cmd = sys.argv[1]
    timeout = 300
    if "--timeout" in sys.argv:
        timeout = int(sys.argv[sys.argv.index("--timeout") + 1])
    req = urllib.request.Request(
        DAEMON + "/exec",
        data=json.dumps({"command": cmd}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.load(r)
    except Exception as exc:
        print(f"EXEC_ERR: {exc}", file=sys.stderr)
        return 2
    out = d.get("output") or ""
    if out:
        print(out)
    if d.get("commandOk"):
        return 0
    return d.get("commandStatus") or 1


if __name__ == "__main__":
    raise SystemExit(main())
