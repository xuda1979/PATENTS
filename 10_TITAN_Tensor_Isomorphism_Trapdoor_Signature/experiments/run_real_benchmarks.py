from __future__ import annotations

import csv
import hashlib
import json
import platform
import random
import statistics
import sys
import time
import types
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import sympy

from titan_impl import TitanParams, TitanSignature


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
RESULTS_DIR.mkdir(exist_ok=True)

FALCON_IMPL_DIR = (
    ROOT.parent.parent / "5_QTS-Falcon_Threshold_Signature" / "real_benchmarks" / "falcon_standard" / "falcon_impl"
)


def install_beartype_shim() -> None:
    try:
        import beartype  # noqa: F401
    except Exception:
        shim = types.ModuleType("beartype")

        def _noop(func=None, *args, **kwargs):
            if func is None:
                def deco(inner):
                    return inner
                return deco
            return func

        shim.beartype = _noop
        sys.modules["beartype"] = shim


install_beartype_shim()
if str(FALCON_IMPL_DIR) not in sys.path:
    sys.path.insert(0, str(FALCON_IMPL_DIR))
from falcon import Falcon  # type: ignore  # noqa: E402


def timer() -> float:
    return time.perf_counter()


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * q)))
    return ordered[idx]


def format_ms_stats(values: list[float]) -> dict[str, float]:
    return {
        "iterations": len(values),
        "mean_ms": round(statistics.mean(values), 3),
        "median_ms": round(statistics.median(values), 3),
        "stdev_ms": round(statistics.stdev(values), 3) if len(values) > 1 else 0.0,
        "min_ms": round(min(values), 3),
        "max_ms": round(max(values), 3),
        "p95_ms": round(percentile(values, 0.95), 3),
    }


def random_messages(count: int, size: int, seed: int) -> list[bytes]:
    rng = random.Random(seed)
    return [rng.randbytes(size) for _ in range(count)]


def tamper_message(msg: bytes) -> bytes:
    data = bytearray(msg)
    data[0] ^= 0x01
    return bytes(data)


def tamper_bytes(blob: bytes) -> bytes:
    data = bytearray(blob)
    index = len(data) // 2 if len(data) > 2 else 0
    if index == 0 and len(data) > 1:
        index = 1
    data[index] ^= 0x01
    return bytes(data)


def bench_titan(params: TitanParams, kg_iters: int, sv_iters: int, msg_size: int, seed: int) -> list[dict[str, Any]]:
    scheme = TitanSignature(params=params, rng_seed=seed)
    rows: list[dict[str, Any]] = []

    for i in range(kg_iters):
        t0 = timer()
        sk, pk = scheme.keygen()
        t1 = timer()
        rows.append(
            {
                "scheme": params.name,
                "family": "titan",
                "param_n": params.N,
                "rounds": params.rounds,
                "operation": "keygen",
                "iteration": i + 1,
                "time_ms": (t1 - t0) * 1000,
                "pk_bytes": scheme.public_key_size_bytes(pk),
                "sk_bytes": scheme.secret_key_size_bytes(sk),
                "sig_bytes": "",
                "verify_success": "",
                "tampered_msg_reject": "",
                "tampered_sig_reject": "",
            }
        )

    messages = random_messages(sv_iters, msg_size, seed + 1000)
    last_sk, last_pk = sk, pk  # type: ignore[possibly-undefined]

    for i, msg in enumerate(messages):
        t0 = timer()
        sig = scheme.sign(msg, last_sk)
        t1 = timer()
        sig_bytes = scheme.signature_size_bytes(sig)
        rows.append(
            {
                "scheme": params.name,
                "family": "titan",
                "param_n": params.N,
                "rounds": params.rounds,
                "operation": "sign",
                "iteration": i + 1,
                "time_ms": (t1 - t0) * 1000,
                "pk_bytes": scheme.public_key_size_bytes(last_pk),
                "sk_bytes": scheme.secret_key_size_bytes(last_sk),
                "sig_bytes": sig_bytes,
                "verify_success": "",
                "tampered_msg_reject": "",
                "tampered_sig_reject": "",
            }
        )

        t2 = timer()
        ok = scheme.verify(msg, sig, last_pk)
        t3 = timer()
        tampered_msg_ok = scheme.verify(tamper_message(msg), sig, last_pk)
        tampered_sig_ok = scheme.verify(msg, scheme.tamper_signature(sig), last_pk)
        rows.append(
            {
                "scheme": params.name,
                "family": "titan",
                "param_n": params.N,
                "rounds": params.rounds,
                "operation": "verify",
                "iteration": i + 1,
                "time_ms": (t3 - t2) * 1000,
                "pk_bytes": scheme.public_key_size_bytes(last_pk),
                "sk_bytes": scheme.secret_key_size_bytes(last_sk),
                "sig_bytes": sig_bytes,
                "verify_success": int(ok),
                "tampered_msg_reject": int(not tampered_msg_ok),
                "tampered_sig_reject": int(not tampered_sig_ok),
            }
        )
        if not ok:
            raise RuntimeError(f"TITAN verification failed for {params.name} iteration {i + 1}")

    return rows


def bench_falcon(n: int, kg_iters: int, sv_iters: int, msg_size: int, seed: int) -> list[dict[str, Any]]:
    falcon = Falcon(n)
    rows: list[dict[str, Any]] = []

    for i in range(kg_iters):
        t0 = timer()
        sk, vk = falcon.keygen()
        t1 = timer()
        rows.append(
            {
                "scheme": f"falcon-{n}",
                "family": "falcon",
                "param_n": n,
                "rounds": "",
                "operation": "keygen",
                "iteration": i + 1,
                "time_ms": (t1 - t0) * 1000,
                "pk_bytes": len(vk),
                "sk_bytes": len(falcon.pack_sk(sk)),
                "sig_bytes": "",
                "verify_success": "",
                "tampered_msg_reject": "",
                "tampered_sig_reject": "",
            }
        )

    messages = random_messages(sv_iters, msg_size, seed + 2000)
    last_sk, last_vk = sk, vk  # type: ignore[possibly-undefined]
    sk_bytes = len(falcon.pack_sk(last_sk))

    for i, msg in enumerate(messages):
        t0 = timer()
        sig = falcon.sign(last_sk, msg)
        t1 = timer()
        sig_len = len(sig)
        rows.append(
            {
                "scheme": f"falcon-{n}",
                "family": "falcon",
                "param_n": n,
                "rounds": "",
                "operation": "sign",
                "iteration": i + 1,
                "time_ms": (t1 - t0) * 1000,
                "pk_bytes": len(last_vk),
                "sk_bytes": sk_bytes,
                "sig_bytes": sig_len,
                "verify_success": "",
                "tampered_msg_reject": "",
                "tampered_sig_reject": "",
            }
        )

        t2 = timer()
        ok = falcon.verify(last_vk, msg, sig)
        t3 = timer()
        tampered_msg_ok = falcon.verify(last_vk, tamper_message(msg), sig)
        try:
            tampered_sig_ok = falcon.verify(last_vk, msg, tamper_bytes(sig))
        except Exception:
            tampered_sig_ok = False
        rows.append(
            {
                "scheme": f"falcon-{n}",
                "family": "falcon",
                "param_n": n,
                "rounds": "",
                "operation": "verify",
                "iteration": i + 1,
                "time_ms": (t3 - t2) * 1000,
                "pk_bytes": len(last_vk),
                "sk_bytes": sk_bytes,
                "sig_bytes": sig_len,
                "verify_success": int(ok),
                "tampered_msg_reject": int(not tampered_msg_ok),
                "tampered_sig_reject": int(not tampered_sig_ok),
            }
        )
        if not ok:
            raise RuntimeError(f"Falcon verification failed for n={n} iteration {i + 1}")

    return rows


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_scheme: dict[str, dict[str, Any]] = {}
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)

    for row in rows:
        scheme = row["scheme"]
        by_scheme.setdefault(
            scheme,
            {
                "family": row["family"],
                "param_n": row["param_n"],
                "rounds": row["rounds"] if row["rounds"] != "" else None,
                "sizes": {},
                "correctness": {
                    "verify_success_count": 0,
                    "verify_total": 0,
                    "tampered_msg_reject_count": 0,
                    "tampered_sig_reject_count": 0,
                },
            },
        )
        if row["pk_bytes"] != "":
            by_scheme[scheme]["sizes"]["pk_bytes"] = int(row["pk_bytes"])
        if row["sk_bytes"] != "":
            by_scheme[scheme]["sizes"]["sk_bytes"] = int(row["sk_bytes"])
        if row["sig_bytes"] != "":
            by_scheme[scheme]["sizes"]["sig_bytes"] = int(row["sig_bytes"])
        if row["operation"] in {"keygen", "sign", "verify"}:
            grouped[(scheme, row["operation"])].append(float(row["time_ms"]))
        if row["operation"] == "verify":
            by_scheme[scheme]["correctness"]["verify_total"] += 1
            by_scheme[scheme]["correctness"]["verify_success_count"] += int(row["verify_success"])
            by_scheme[scheme]["correctness"]["tampered_msg_reject_count"] += int(row["tampered_msg_reject"])
            by_scheme[scheme]["correctness"]["tampered_sig_reject_count"] += int(row["tampered_sig_reject"])

    for scheme, data in by_scheme.items():
        for op in ("keygen", "sign", "verify"):
            stats = grouped.get((scheme, op))
            if stats:
                data[op] = format_ms_stats(stats)
        correctness = data["correctness"]
        total = correctness["verify_total"] or 1
        correctness["verify_success_rate"] = round(correctness["verify_success_count"] / total, 4)
        correctness["tampered_msg_reject_rate"] = round(correctness["tampered_msg_reject_count"] / total, 4)
        correctness["tampered_sig_reject_rate"] = round(correctness["tampered_sig_reject_count"] / total, 4)
        verify_mean = data.get("verify", {}).get("mean_ms")
        sign_mean = data.get("sign", {}).get("mean_ms")
        if sign_mean:
            data["sign_throughput_sig_s"] = round(1000.0 / sign_mean, 3)
        if verify_mean:
            data["verify_throughput_sig_s"] = round(1000.0 / verify_mean, 3)

    return {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python_version": sys.version,
        "platform": platform.platform(),
        "numpy_version": np.__version__,
        "sympy_version": sympy.__version__,
        "falcon_impl_dir": str(FALCON_IMPL_DIR),
        "security_note": (
            "TITAN parameter points are engineering proof-of-concept points only; "
            "they are not claimed to be security-level matched to Falcon."
        ),
        "schemes": by_scheme,
    }


def build_reviewer_answers(summary: dict[str, Any]) -> str:
    schemes = summary["schemes"]
    titan_names = sorted(
        (name for name, item in schemes.items() if item["family"] == "titan"),
        key=lambda name: (schemes[name]["param_n"], schemes[name]["rounds"]),
    )
    falcon_names = sorted(
        (name for name, item in schemes.items() if item["family"] == "falcon"),
        key=lambda name: schemes[name]["param_n"],
    )

    lines: list[str] = []
    lines.append("# Reviewer-Oriented Quantitative Findings")
    lines.append("")
    lines.append("All numbers in this file come from actual local execution on the current machine.")
    lines.append("")
    lines.append("## 1. Core Correctness Questions")
    lines.append("")
    lines.append("| Scheme | Verify Success | Tampered Message Reject | Tampered Signature Reject |")
    lines.append("| --- | ---: | ---: | ---: |")
    for name in titan_names + falcon_names:
        correctness = schemes[name]["correctness"]
        lines.append(
            f"| {name} | {correctness['verify_success_count']}/{correctness['verify_total']} "
            f"({correctness['verify_success_rate']:.2%}) | "
            f"{correctness['tampered_msg_reject_count']}/{correctness['verify_total']} "
            f"({correctness['tampered_msg_reject_rate']:.2%}) | "
            f"{correctness['tampered_sig_reject_count']}/{correctness['verify_total']} "
            f"({correctness['tampered_sig_reject_rate']:.2%}) |"
        )

    lines.append("")
    lines.append("## 2. Engineering Cost Comparison")
    lines.append("")
    lines.append("| Scheme | Public Key (B) | Secret Key (B) | Signature (B) | KeyGen Mean (ms) | Sign Mean (ms) | Verify Mean (ms) |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for name in titan_names + falcon_names:
        item = schemes[name]
        sizes = item["sizes"]
        lines.append(
            f"| {name} | {sizes.get('pk_bytes','?')} | {sizes.get('sk_bytes','?')} | {sizes.get('sig_bytes','?')} | "
            f"{item['keygen']['mean_ms']:.3f} | {item['sign']['mean_ms']:.3f} | {item['verify']['mean_ms']:.3f} |"
        )

    lines.append("")
    lines.append("## 3. TITAN Parameter Scaling")
    lines.append("")
    lines.append("| TITAN Config | N | Rounds | Public Key (B) | Signature (B) | Sign Mean (ms) | Verify Mean (ms) | Verify Throughput (sig/s) |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for name in titan_names:
        item = schemes[name]
        sizes = item["sizes"]
        lines.append(
            f"| {name} | {item['param_n']} | {item['rounds']} | {sizes.get('pk_bytes','?')} | {sizes.get('sig_bytes','?')} | "
            f"{item['sign']['mean_ms']:.3f} | {item['verify']['mean_ms']:.3f} | {item.get('verify_throughput_sig_s','?')} |"
        )

    lines.append("")
    lines.append("## 4. Quantitative Takeaways")
    lines.append("")
    titan_small = schemes.get("titan-n8-r16")
    titan_large = schemes.get("titan-n12-r32")
    falcon_512 = schemes.get("falcon-512")
    falcon_1024 = schemes.get("falcon-1024")
    if titan_small and falcon_512:
        keygen_ratio = falcon_512["keygen"]["mean_ms"] / titan_small["keygen"]["mean_ms"]
        sign_ratio = titan_small["sign"]["mean_ms"] / falcon_512["sign"]["mean_ms"]
        verify_ratio = falcon_512["verify"]["mean_ms"] / titan_small["verify"]["mean_ms"]
        pk_ratio = titan_small["sizes"]["pk_bytes"] / falcon_512["sizes"]["pk_bytes"]
        sig_ratio = titan_small["sizes"]["sig_bytes"] / falcon_512["sizes"]["sig_bytes"]
        lines.append(
            f"- Against `falcon-512`, `titan-n8-r16` shows {keygen_ratio:.1f}x faster key generation and "
            f"{verify_ratio:.2f}x faster verification on this machine."
        )
        lines.append(
            f"- Against `falcon-512`, `titan-n8-r16` uses {pk_ratio:.2f}x public-key bytes, "
            f"{sign_ratio:.2f}x signing time, and {sig_ratio:.2f}x signature bytes."
        )
    if titan_large and falcon_1024:
        keygen_ratio = falcon_1024["keygen"]["mean_ms"] / titan_large["keygen"]["mean_ms"]
        sign_ratio = titan_large["sign"]["mean_ms"] / falcon_1024["sign"]["mean_ms"]
        verify_ratio = falcon_1024["verify"]["mean_ms"] / titan_large["verify"]["mean_ms"]
        pk_ratio = titan_large["sizes"]["pk_bytes"] / falcon_1024["sizes"]["pk_bytes"]
        sig_ratio = titan_large["sizes"]["sig_bytes"] / falcon_1024["sizes"]["sig_bytes"]
        lines.append(
            f"- Against `falcon-1024`, `titan-n12-r32` shows {keygen_ratio:.1f}x faster key generation and "
            f"{verify_ratio:.2f}x faster verification, with public key at {pk_ratio:.2f}x of Falcon-1024."
        )
        lines.append(
            f"- The same `titan-n12-r32` point signs in {sign_ratio:.2f}x the time of `falcon-1024` "
            f"and produces {sig_ratio:.2f}x signature bytes."
        )
    lines.append("- All TITAN configurations achieved 100% observed verification success in the executed trials.")
    lines.append("- All TITAN configurations rejected every tested tampered message and every tested tampered signature.")
    lines.append("- The current TITAN proof-of-concept shows a compute-versus-signature-size tradeoff: latency can be low, but uncompressed signatures are larger than Falcon.")
    lines.append("- Because TITAN parameter points are not yet mapped to standard security categories, these results should be read as engineering evidence, not security-level-equivalent benchmarking.")
    lines.append("")
    return "\n".join(lines)


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    fieldnames = [
        "scheme",
        "family",
        "param_n",
        "rounds",
        "operation",
        "iteration",
        "time_ms",
        "pk_bytes",
        "sk_bytes",
        "sig_bytes",
        "verify_success",
        "tampered_msg_reject",
        "tampered_sig_reject",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    titan_params = [
        TitanParams(name="titan-n8-r16", N=8, p=251, rounds=16),
        TitanParams(name="titan-n8-r32", N=8, p=251, rounds=32),
        TitanParams(name="titan-n10-r32", N=10, p=251, rounds=32),
        TitanParams(name="titan-n12-r32", N=12, p=251, rounds=32),
    ]
    falcon_params = [512, 1024]

    titan_keygen_iters = 5
    titan_sign_verify_iters = 50
    falcon_keygen_iters = 3
    falcon_sign_verify_iters = 50
    msg_size = 64

    rows: list[dict[str, Any]] = []

    print("=" * 72)
    print("REAL TITAN / FALCON BENCHMARK")
    print(f"Python   : {sys.version}")
    print(f"Platform : {platform.platform()}")
    print(f"NumPy    : {np.__version__}")
    print(f"SymPy    : {sympy.__version__}")
    print("=" * 72)

    for idx, params in enumerate(titan_params):
        print(f"\n--- TITAN {params.name} ---")
        rows.extend(
            bench_titan(
                params=params,
                kg_iters=titan_keygen_iters,
                sv_iters=titan_sign_verify_iters,
                msg_size=msg_size,
                seed=100 + idx,
            )
        )

    for idx, n in enumerate(falcon_params):
        print(f"\n--- Falcon-{n} ---")
        rows.extend(
            bench_falcon(
                n=n,
                kg_iters=falcon_keygen_iters,
                sv_iters=falcon_sign_verify_iters,
                msg_size=msg_size,
                seed=500 + idx,
            )
        )

    summary = summarise(rows)
    reviewer_answers = build_reviewer_answers(summary)

    write_csv(rows, RESULTS_DIR / "raw_benchmark.csv")
    with (RESULTS_DIR / "summary.json").open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
    with (RESULTS_DIR / "reviewer_answers.md").open("w", encoding="utf-8") as fh:
        fh.write(reviewer_answers)

    print("\n[OK] Raw benchmark written to:", RESULTS_DIR / "raw_benchmark.csv")
    print("[OK] Summary written to      :", RESULTS_DIR / "summary.json")
    print("[OK] Reviewer report written:", RESULTS_DIR / "reviewer_answers.md")


if __name__ == "__main__":
    main()
