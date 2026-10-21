from __future__ import annotations

import json
import platform
import shutil
import sys
import traceback
from typing import Any


def main() -> int:
    report: dict[str, Any] = {
        "python_executable": sys.executable,
        "python_version": sys.version,
        "platform": platform.platform(),
        "git_on_path": shutil.which("git") is not None,
        "cmake_on_path": shutil.which("cmake") is not None,
        "cl_on_path": shutil.which("cl") is not None,
    }

    try:
        import oqs  # type: ignore

        mechanisms = list(oqs.get_enabled_sig_mechanisms())
        falcon_mechanisms = [name for name in mechanisms if "falcon" in name.lower()]

        report["oqs_import"] = "ok"
        report["enabled_signature_count"] = len(mechanisms)
        report["falcon_mechanisms"] = falcon_mechanisms
        report["falcon_available"] = bool(falcon_mechanisms)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    except BaseException as exc:  # pragma: no cover - diagnostic path
        report["oqs_import"] = "failed"
        report["error_type"] = type(exc).__name__
        report["error_message"] = str(exc)
        report["traceback"] = traceback.format_exc()
        print(json.dumps(report, indent=2, ensure_ascii=False))
        if isinstance(exc, SystemExit):
            code = exc.code if isinstance(exc.code, int) else 1
            return code
        return 1


if __name__ == "__main__":
    raise SystemExit(main())