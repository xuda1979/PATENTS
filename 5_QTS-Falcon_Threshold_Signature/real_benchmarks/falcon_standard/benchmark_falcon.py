"""
Real Falcon Benchmark
=====================
This script benchmarks the **real** Falcon signature scheme implementation
from https://github.com/tprest/falcon.py (by Thomas Prest, MIT license).

It measures:
  - Key generation time
  - Signing time
  - Verification time
  - Secret-key size (serialised)
  - Verification-key (public-key) size
  - Signature size

For each parameter set (n = 256, 512, 1024) it performs multiple independent
iterations and records **every** individual measurement.  No data is simulated
or interpolated; every number comes from an actual run of the algorithm on
this machine.

Outputs
-------
  raw_benchmark.csv  – one row per (parameter_set, operation, iteration)
  summary.json       – aggregate statistics derived from raw_benchmark.csv

Usage
-----
  cd real_benchmarks/falcon_standard/falcon_impl
  python ../benchmark_falcon.py          # default: 10 keygen, 20 sign/verify
  python ../benchmark_falcon.py --kg 5 --sv 10   # custom iteration counts

Requirements
------------
  numpy, pycryptodome, beartype   (installed in the current environment)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import statistics
import sys
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Make sure we import from the real implementation sitting next to us
# ---------------------------------------------------------------------------
IMPL_DIR = Path(__file__).resolve().parent / "falcon_impl"
if str(IMPL_DIR) not in sys.path:
    sys.path.insert(0, str(IMPL_DIR))

from falcon import Falcon  # type: ignore  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _timer() -> float:
    """High-resolution monotonic timer (seconds)."""
    return time.perf_counter()


def _bytes_of_sk(falcon_obj: Falcon, sk) -> int:
    """Return the byte-length of a serialised secret key."""
    return len(falcon_obj.pack_sk(sk))


# ---------------------------------------------------------------------------
# Single-parameter-set benchmark
# ---------------------------------------------------------------------------

def bench_one(n: int, kg_iters: int, sv_iters: int) -> list[dict[str, Any]]:
    """Run a full benchmark for Falcon-{n}.

    Returns a list of raw measurement dicts (one per operation per iteration).
    """
    rows: list[dict[str, Any]] = []
    falcon = Falcon(n)
    msg = b"Benchmark message for patent experiment - real Falcon implementation"

    # --- Key generation ---------------------------------------------------
    for i in range(kg_iters):
        t0 = _timer()
        sk, vk = falcon.keygen()
        t1 = _timer()
        sk_bytes = _bytes_of_sk(falcon, sk)
        rows.append({
            "param_n": n,
            "operation": "keygen",
            "iteration": i + 1,
            "time_s": t1 - t0,
            "sk_bytes": sk_bytes,
            "vk_bytes": len(vk),
            "sig_bytes": None,
        })
        print(f"  [n={n}] keygen {i+1}/{kg_iters}  {(t1-t0)*1000:.1f} ms")

    # Keep last key pair for sign/verify rounds
    # (regenerating each time would conflate keygen cost into sign cost)
    last_sk, last_vk = sk, vk  # type: ignore[possibly-undefined]
    last_sk_bytes = sk_bytes  # type: ignore[possibly-undefined]

    # --- Signing ----------------------------------------------------------
    sigs: list[bytes] = []
    for i in range(sv_iters):
        t0 = _timer()
        sig = falcon.sign(last_sk, msg)
        t1 = _timer()
        sigs.append(sig)
        rows.append({
            "param_n": n,
            "operation": "sign",
            "iteration": i + 1,
            "time_s": t1 - t0,
            "sk_bytes": last_sk_bytes,
            "vk_bytes": len(last_vk),
            "sig_bytes": len(sig),
        })
        print(f"  [n={n}] sign   {i+1}/{sv_iters}  {(t1-t0)*1000:.1f} ms  sig={len(sig)}B")

    # --- Verification -----------------------------------------------------
    for i, sig in enumerate(sigs):
        t0 = _timer()
        ok = falcon.verify(last_vk, msg, sig)
        t1 = _timer()
        if not ok:
            raise RuntimeError(f"Verification FAILED at n={n}, iteration {i+1}")
        rows.append({
            "param_n": n,
            "operation": "verify",
            "iteration": i + 1,
            "time_s": t1 - t0,
            "sk_bytes": last_sk_bytes,
            "vk_bytes": len(last_vk),
            "sig_bytes": len(sig),
        })
        print(f"  [n={n}] verify {i+1}/{sv_iters}  {(t1-t0)*1000:.3f} ms  ok={ok}")

    return rows


# ---------------------------------------------------------------------------
# Aggregate helpers
# ---------------------------------------------------------------------------

def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute per-param, per-operation aggregate statistics."""
    from collections import defaultdict
    buckets: dict[tuple[int, str], list[float]] = defaultdict(list)
    size_info: dict[int, dict[str, Any]] = {}

    for r in rows:
        key = (r["param_n"], r["operation"])
        buckets[key].append(r["time_s"])
        n = r["param_n"]
        if n not in size_info:
            size_info[n] = {}
        if r["sk_bytes"] is not None:
            size_info[n]["sk_bytes"] = r["sk_bytes"]
        if r["vk_bytes"] is not None:
            size_info[n]["vk_bytes"] = r["vk_bytes"]
        if r["sig_bytes"] is not None:
            size_info[n]["sig_bytes"] = r["sig_bytes"]

    summary: dict[str, Any] = {
        "implementation": "tprest/falcon.py (pure Python, MIT)",
        "implementation_url": "https://github.com/tprest/falcon.py",
        "python_version": sys.version,
        "platform": platform.platform(),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "parameters": {},
    }

    for (n, op), times in sorted(buckets.items()):
        pkey = f"falcon-{n}"
        if pkey not in summary["parameters"]:
            summary["parameters"][pkey] = {"sizes": size_info.get(n, {})}
        ms_times = [t * 1000 for t in times]
        summary["parameters"][pkey][op] = {
            "iterations": len(times),
            "mean_ms": round(statistics.mean(ms_times), 3),
            "median_ms": round(statistics.median(ms_times), 3),
            "stdev_ms": round(statistics.stdev(ms_times), 3) if len(ms_times) > 1 else 0.0,
            "min_ms": round(min(ms_times), 3),
            "max_ms": round(max(ms_times), 3),
        }

    return summary


# ---------------------------------------------------------------------------
# CSV / JSON writers
# ---------------------------------------------------------------------------

def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    fieldnames = ["param_n", "operation", "iteration", "time_s",
                  "sk_bytes", "vk_bytes", "sig_bytes"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"\n[✓] Raw data written to {path}")


def write_json(data: dict[str, Any], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[✓] Summary written to {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Real Falcon benchmark")
    parser.add_argument("--kg", type=int, default=5,
                        help="Number of keygen iterations per param set (default 5)")
    parser.add_argument("--sv", type=int, default=10,
                        help="Number of sign/verify iterations per param set (default 10)")
    parser.add_argument("--params", type=str, default="256,512,1024",
                        help="Comma-separated list of n values (default 256,512,1024)")
    args = parser.parse_args()

    param_list = [int(x.strip()) for x in args.params.split(",")]
    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)

    print("=" * 60)
    print("  REAL Falcon Benchmark")
    print(f"  Implementation: tprest/falcon.py (pure Python)")
    print(f"  Python: {sys.version}")
    print(f"  Platform: {platform.platform()}")
    print(f"  Parameters: {param_list}")
    print(f"  Keygen iterations: {args.kg}")
    print(f"  Sign/Verify iterations: {args.sv}")
    print("=" * 60)

    all_rows: list[dict[str, Any]] = []

    for n in param_list:
        print(f"\n--- Falcon-{n} ---")
        rows = bench_one(n, args.kg, args.sv)
        all_rows.extend(rows)

    csv_path = out_dir / "raw_benchmark.csv"
    json_path = out_dir / "summary.json"

    write_csv(all_rows, csv_path)

    summary = summarise(all_rows)
    write_json(summary, json_path)

    # Print a quick table
    print("\n" + "=" * 60)
    print("  Summary (mean ± stdev, in ms)")
    print("-" * 60)
    for pkey, pdata in summary["parameters"].items():
        sizes = pdata.get("sizes", {})
        print(f"\n  {pkey}")
        print(f"    sk={sizes.get('sk_bytes','?')}B  "
              f"vk={sizes.get('vk_bytes','?')}B  "
              f"sig={sizes.get('sig_bytes','?')}B")
        for op in ("keygen", "sign", "verify"):
            if op in pdata:
                d = pdata[op]
                print(f"    {op:8s}: {d['mean_ms']:10.3f} ± {d['stdev_ms']:.3f} ms  "
                      f"(min={d['min_ms']:.3f}, max={d['max_ms']:.3f}, n={d['iterations']})")
    print("=" * 60)
    print("Done.")


if __name__ == "__main__":
    main()
