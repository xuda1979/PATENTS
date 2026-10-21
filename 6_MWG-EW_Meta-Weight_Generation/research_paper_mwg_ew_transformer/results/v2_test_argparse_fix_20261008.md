# v2 test staging bug (missing argparse) — fix, re-upload, watcher re-arm (2026-10-08)

## Incident

The hardened decisive run at 2026-10-08T09:44:08Z (watcher-v2 auto-launched
after the device freed at 09:44:06Z) failed before reaching the device:

```
[2026-10-08T09:46:58Z] running test_v4_multicore_v2.py
Traceback (most recent call last):
    main()
  File "/tmp/test_v4_multicore_v2.py", line 336, in main
    parser = argparse.ArgumentParser(...)
NameError: name 'argparse' is not defined
[2026-10-08T09:47:08Z] test rc=1
```

Root cause: the staged `test_v4_multicore_v2.py` (md5 582470c5452ccdf7680370d628b29961)
was missing `import argparse` (present in v1's test; dropped when the hardened
docstring/imports block was rewritten). This is a **harness staging bug**, not a
device or kernel defect: the run died at argument parsing, before any NPU launch.
The worker's own gates all passed (fixed v4 source 701e9be0..., v1 baseline
59cf1751..., cmake rc=0, make rc=0, warmup-fix string present, 60 s settle).

## Fix

One-line fix in the local source
(`custom_ops/ephemeral_core_apply/torch_ext/v4_multicore/test_v4_multicore_v2.py`):
added `import argparse` to the import block. No other changes; H1 (gated ref),
H2 (NaN attribution vs CPU truth), H3 (per-config 3x retry) logic untouched.

- Fixed file md5: `60dd757f10e374346977b4949d1d6dc8` (14925 bytes)
- Syntax-verified locally (`ast.parse` OK)

## Re-upload (new tooling)

ASI2 has no working S3 egress relay for pushes from this Mac, so the file was
uploaded through the ASI2 browser-shell daemon (port 19004) with a new
chunked uploader:

- `scripts/ASI2_shell.sh` — daemon-gated remote shell wrapper (mirrors
  ASI3_shell.sh; refuses to spawn browsers if the daemon is down/busy).
- `scripts/asi2_chunked_upload.sh` — base64-append uploader, default 1500-char
  chunks (3000-char chunks corrupted mid-line in earlier staging; 1500 verified
  clean), health-gated between chunks, per-chunk retry (30x), final md5 check.

Upload log: 19924 base64 bytes, 14 chunks, all CHUNK_OK first try; remote
md5 `60dd757f10e374346977b4949d1d6dc8` == local. UPLOAD VERIFIED OK.

## Watcher re-arm

- Old watcher had exited (single-shot by design; it ran worker v2 once and
  the worker returned rc=1 → watcher logged `worker v2 finished rc=0` —
  note: the watcher's rc line records the *worker script's* exit, which is 0
  because the worker itself completed its logging despite the test rc=1;
  the true test rc is in `results/v4_asi2_decisive_v2_20261008.log`).
- Re-armed 2026-10-08T11:18:06Z, PID 26466 on ASI2
  (`/tmp/asi2_v2_watcher.sh`, same 12 h max, 30 s polls).
- Worker unchanged: `/tmp/asi2_v4_decisive_worker_v2.sh`
  md5 `002550def2bd737e8283d64f74f9c3b3` (matches local).
- Device state at re-arm: busy — 8 tenant NPU processes (SAPA holdout leg +
  GRPO 27B selfeval training started ~11:00Z). The watcher waits for
  `npu-smi info` to show zero tenant processes, then runs the worker.

## Expected decisive-run artifacts (when the device frees)

- `results/v4_multicore_benchmark_asi2_v2_20261008.json`
- Appended `results/v4_asi2_decisive_20261008.log` (worker v2 section)
- Watcher log: `/tmp/asi2_v2_watcher.log` on ASI2

Interpretation rule (unchanged from diag9v2 doc): the decisive claim is
v4 ≈ v1 numerically with v4 faster at T≥512 (multi-core epilogue). H1–H3
distinguish genuine kernel defects from ASI2's transient bad-launch windows;
abort (rc=3) only on persistent op-attributed failure.
