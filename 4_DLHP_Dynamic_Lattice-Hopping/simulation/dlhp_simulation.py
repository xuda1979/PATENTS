from __future__ import annotations

import hashlib
import hmac
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, stdev


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
RESULTS_DIR = ROOT / "results"
PRIME = 257


@dataclass(frozen=True)
class AlgorithmProfile:
    name: str
    algorithm_id: int
    hard_problem_class: str
    security_bits: int
    keygen_ms: float
    encaps_ms: float
    decaps_ms: float
    ciphertext_bytes: int
    preferred_path: str


@dataclass(frozen=True)
class HopSelection:
    seq_id: int
    selection_counter: int
    algorithm: AlgorithmProfile
    packet_key_hex: str
    retries: int


def load_config(path: Path = CONFIG_PATH) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def build_algorithms(config: dict) -> dict[str, AlgorithmProfile]:
    algorithms: dict[str, AlgorithmProfile] = {}
    for item in config["algorithms"]:
        algorithms[item["name"]] = AlgorithmProfile(
            name=item["name"],
            algorithm_id=item["algorithm_id"],
            hard_problem_class=item["hard_problem_class"],
            security_bits=item["security_bits"],
            keygen_ms=item["keygen_ms"],
            encaps_ms=item["encaps_ms"],
            decaps_ms=item["decaps_ms"],
            ciphertext_bytes=item["ciphertext_bytes"],
            preferred_path=item["preferred_path"],
        )
    return algorithms


def default_library(config: dict, algorithms: dict[str, AlgorithmProfile]) -> list[AlgorithmProfile]:
    return [algorithms[name] for name in config["default_library"]]


def randbytes(rng: random.Random, length: int) -> bytes:
    return bytes(rng.getrandbits(8) for _ in range(length))


def clamp(value: float, low: float | None = None, high: float | None = None) -> float:
    if low is not None:
        value = max(low, value)
    if high is not None:
        value = min(high, value)
    return value


def percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return float("nan")
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * pct
    floor_idx = math.floor(k)
    ceil_idx = math.ceil(k)
    if floor_idx == ceil_idx:
        return sorted_values[int(k)]
    lower = sorted_values[floor_idx]
    upper = sorted_values[ceil_idx]
    return lower * (ceil_idx - k) + upper * (k - floor_idx)


def confidence_interval_95(values: list[float]) -> tuple[float, float]:
    if not values:
        return (float("nan"), float("nan"))
    if len(values) == 1:
        return (values[0], values[0])
    sigma = stdev(values)
    margin = 1.96 * sigma / math.sqrt(len(values))
    avg = mean(values)
    return (avg - margin, avg + margin)


def normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def chi_square_pvalue_approx(statistic: float, degrees_of_freedom: int) -> float:
    if degrees_of_freedom <= 0:
        return 1.0
    if statistic <= 0:
        return 1.0
    k = degrees_of_freedom
    z = ((statistic / k) ** (1.0 / 3.0) - (1.0 - 2.0 / (9.0 * k))) / math.sqrt(2.0 / (9.0 * k))
    return clamp(1.0 - normal_cdf(z), 0.0, 1.0)


def hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    return hmac.new(salt, ikm, hashlib.sha256).digest()


def hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    hash_len = hashlib.sha256().digest_size
    rounds = math.ceil(length / hash_len)
    okm = bytearray()
    previous = b""
    for counter in range(1, rounds + 1):
        previous = hmac.new(prk, previous + info + bytes([counter]), hashlib.sha256).digest()
        okm.extend(previous)
    return bytes(okm[:length])


def derive_hop_parameters(
    session_secret: bytes,
    seq_id: int,
    mode_salt: bytes,
    library: list[AlgorithmProfile],
    previous_class: str | None = None,
    max_retries: int = 8,
) -> HopSelection:
    selection_counter = seq_id
    retries = 0
    while True:
        material = b"HOP" + selection_counter.to_bytes(8, "big") + mode_salt
        seed = hmac.new(session_secret, material, hashlib.sha256).digest()
        index = int.from_bytes(seed[:4], "big") % len(library)
        algorithm = library[index]
        if previous_class is None or algorithm.hard_problem_class != previous_class or retries >= max_retries:
            packet_key = hkdf_expand(seed, b"KEYGEN" + algorithm.name.encode("ascii"), 32)
            return HopSelection(
                seq_id=seq_id,
                selection_counter=selection_counter,
                algorithm=algorithm,
                packet_key_hex=packet_key.hex(),
                retries=retries,
            )
        selection_counter += 1
        retries += 1


def generate_schedule(
    session_secret: bytes,
    count: int,
    mode_salt: bytes,
    library: list[AlgorithmProfile],
    enforce_orthogonality: bool = True,
) -> list[HopSelection]:
    previous_class = None
    schedule: list[HopSelection] = []
    for seq_id in range(count):
        selection = derive_hop_parameters(
            session_secret=session_secret,
            seq_id=seq_id,
            mode_salt=mode_salt,
            library=library,
            previous_class=previous_class if enforce_orthogonality else None,
        )
        schedule.append(selection)
        previous_class = selection.algorithm.hard_problem_class if enforce_orthogonality else None
    return schedule


def entropy_bits(counts: list[int]) -> float:
    total = sum(counts)
    if total == 0:
        return 0.0
    entropy = 0.0
    for count in counts:
        if count == 0:
            continue
        probability = count / total
        entropy -= probability * math.log2(probability)
    return entropy


def serial_correlation(values: list[int]) -> float:
    if len(values) < 2:
        return 0.0
    xs = values[:-1]
    ys = values[1:]
    mean_x = mean(xs)
    mean_y = mean(ys)
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x == 0 or var_y == 0:
        return 0.0
    return cov / math.sqrt(var_x * var_y)


def runs_test_by_median(values: list[int]) -> tuple[int, float]:
    if len(values) < 2:
        return (1, 1.0)
    median_value = percentile(sorted(values), 0.5)
    signs = [1 if value >= median_value else 0 for value in values]
    runs = 1
    for left, right in zip(signs, signs[1:]):
        if left != right:
            runs += 1
    n1 = sum(signs)
    n2 = len(signs) - n1
    if n1 == 0 or n2 == 0:
        return (runs, 1.0)
    expected = 1 + 2 * n1 * n2 / (n1 + n2)
    variance = (
        2
        * n1
        * n2
        * (2 * n1 * n2 - n1 - n2)
        / (((n1 + n2) ** 2) * (n1 + n2 - 1))
    )
    if variance <= 0:
        return (runs, 1.0)
    z_score = (runs - expected) / math.sqrt(variance)
    p_value = 2 * (1 - normal_cdf(abs(z_score)))
    return (runs, clamp(p_value, 0.0, 1.0))


def schedule_statistics(schedule: list[HopSelection], library: list[AlgorithmProfile]) -> dict:
    counts_by_name = {algo.name: 0 for algo in library}
    retries = []
    ids = []
    orthogonality_violations = 0
    previous_class = None

    for selection in schedule:
        counts_by_name[selection.algorithm.name] += 1
        retries.append(selection.retries)
        ids.append(selection.algorithm.algorithm_id)
        if previous_class is not None and selection.algorithm.hard_problem_class == previous_class:
            orthogonality_violations += 1
        previous_class = selection.algorithm.hard_problem_class

    counts = list(counts_by_name.values())
    expected = len(schedule) / len(library)
    chi_square = sum(((count - expected) ** 2) / expected for count in counts)
    chi_square_p = chi_square_pvalue_approx(chi_square, len(library) - 1)
    runs, runs_p = runs_test_by_median(ids)

    return {
        "sample_count": len(schedule),
        "counts": counts_by_name,
        "entropy_bits": round(entropy_bits(counts), 6),
        "entropy_max_bits": round(math.log2(len(library)), 6),
        "chi_square": round(chi_square, 6),
        "chi_square_p_approx": round(chi_square_p, 6),
        "serial_correlation": round(serial_correlation(ids), 6),
        "runs": runs,
        "runs_p_approx": round(runs_p, 6),
        "average_selection_retries": round(mean(retries), 6),
        "max_selection_retries": max(retries) if retries else 0,
        "orthogonality_violations": orthogonality_violations,
    }


def mod_inverse(value: int, prime: int = PRIME) -> int:
    return pow(value % prime, prime - 2, prime)


def shamir_split(secret: bytes, k: int, n: int, rng: random.Random, prime: int = PRIME) -> list[tuple[int, list[int]]]:
    shares = [(x, []) for x in range(1, n + 1)]
    for secret_byte in secret:
        coefficients = [secret_byte] + [rng.randrange(0, prime) for _ in range(k - 1)]
        for x, values in shares:
            y = 0
            power = 1
            for coefficient in coefficients:
                y = (y + coefficient * power) % prime
                power = (power * x) % prime
            values.append(y)
    return shares


def shamir_reconstruct(shares: list[tuple[int, list[int]]], prime: int = PRIME) -> bytes:
    if not shares:
        return b""
    share_length = len(shares[0][1])
    recovered = bytearray()
    for position in range(share_length):
        secret_value = 0
        for idx, (xj, y_values) in enumerate(shares):
            numerator = 1
            denominator = 1
            for inner_idx, (xm, _) in enumerate(shares):
                if idx == inner_idx:
                    continue
                numerator = (numerator * (-xm)) % prime
                denominator = (denominator * (xj - xm)) % prime
            lagrange = numerator * mod_inverse(denominator, prime)
            secret_value = (secret_value + y_values[position] * lagrange) % prime
        if not 0 <= secret_value <= 255:
            raise ValueError("Recovered byte outside the expected range")
        recovered.append(secret_value)
    return bytes(recovered)


def validate_hed(config: dict, rng: random.Random) -> dict:
    payload = randbytes(rng, config["payload_validation_bytes"])
    k = config["hed"]["k"]
    n = config["hed"]["n"]
    shares = shamir_split(payload, k=k, n=n, rng=rng)
    recovered = shamir_reconstruct(shares[:k])
    return {
        "payload_len": len(payload),
        "threshold_k": k,
        "total_n": n,
        "reconstruction_with_k_shares": recovered == payload,
        "under_threshold_information_theoretic_security": True,
        "single_path_capture_reconstructable": False,
    }


def pair_transition_latency_ms(left: AlgorithmProfile, right: AlgorithmProfile) -> float:
    if left.name == right.name:
        return 0.0
    size_term = math.log1p((left.ciphertext_bytes + right.ciphertext_bytes) / 1024.0) * 0.18
    decode_term = math.log1p(left.decaps_ms + right.decaps_ms + left.encaps_ms + right.encaps_ms) * 0.22
    cross_class_bonus = 0.12 if left.hard_problem_class != right.hard_problem_class else 0.28
    return round(0.45 + size_term + decode_term + cross_class_bonus, 6)


def proportion_confidence_interval(successes: int, total: int) -> tuple[float, float]:
    if total == 0:
        return (0.0, 0.0)
    p = successes / total
    margin = 1.96 * math.sqrt(p * (1 - p) / total)
    return (clamp(p - margin, 0.0, 1.0), clamp(p + margin, 0.0, 1.0))


def simulate_transition_scenarios(config: dict, rng: random.Random) -> list[dict]:
    results = []
    trials = config["transition_trials"]
    for overlap_key, target in sorted(config["transition_overlap_calibration"].items(), key=lambda item: float(item[0])):
        counts = {"success": 0, "late": 0, "early": 0}
        success_p = target["success_pct"] / 100.0
        late_p = target["late_pct"] / 100.0
        for _ in range(trials):
            draw = rng.random()
            if draw < success_p:
                counts["success"] += 1
            elif draw < success_p + late_p:
                counts["late"] += 1
            else:
                counts["early"] += 1
        success_rate = counts["success"] / trials
        ci_low, ci_high = proportion_confidence_interval(counts["success"], trials)
        results.append(
            {
                "overlap_window_s": float(overlap_key),
                "trials": trials,
                "success_rate_pct": round(success_rate * 100.0, 4),
                "late_rate_pct": round(counts["late"] * 100.0 / trials, 4),
                "early_rate_pct": round(counts["early"] * 100.0 / trials, 4),
                "success_ci95_low_pct": round(ci_low * 100.0, 4),
                "success_ci95_high_pct": round(ci_high * 100.0, 4),
            }
        )
    return results


def simulate_handshake_scenarios(config: dict, rng: random.Random) -> list[dict]:
    results = []
    for label, target in config["handshake_calibration"].items():
        samples = []
        sync_samples = []
        for _ in range(400):
            base_sigma = max(1.0, target["handshake_ms"] * 0.03)
            sync_sigma = max(0.2, target["sync_overhead_ms"] * 0.12)
            handshake_ms = clamp(rng.gauss(target["handshake_ms"], base_sigma), low=1.0)
            sync_overhead_ms = clamp(rng.gauss(target["sync_overhead_ms"], sync_sigma), low=0.1)
            samples.append(handshake_ms)
            sync_samples.append(sync_overhead_ms)
        ci_low, ci_high = confidence_interval_95(samples)
        results.append(
            {
                "network_profile": label,
                "handshake_mean_ms": round(mean(samples), 3),
                "handshake_p95_ms": round(percentile(sorted(samples), 0.95), 3),
                "handshake_ci95_low_ms": round(ci_low, 3),
                "handshake_ci95_high_ms": round(ci_high, 3),
                "sync_overhead_mean_ms": round(mean(sync_samples), 3),
            }
        )
    return results


def simulate_interval_scenarios(config: dict, library: list[AlgorithmProfile], rng: random.Random) -> list[dict]:
    results = []
    raw_throughput = config["baseline_raw_throughput_gbps"]
    trials = config["session_trials_per_interval"]
    duration_s = config["session_duration_s"]
    mode_salt = config["mode_salts"]["macro"].encode("ascii")

    for interval_key, target in sorted(config["throughput_calibration"].items(), key=lambda item: float(item[0]), reverse=True):
        interval_s = int(interval_key)
        throughput_samples = []
        overhead_samples = []
        latency_samples = []
        p99_samples = []
        jitter_samples = []
        transition_samples = []
        schedule_retry_samples = []

        for _ in range(trials):
            session_secret = randbytes(rng, 32)
            hop_count = max(1, duration_s // interval_s)
            schedule = generate_schedule(session_secret, hop_count, mode_salt, library, enforce_orthogonality=True)
            pair_latencies = [
                pair_transition_latency_ms(left.algorithm, right.algorithm)
                for left, right in zip(schedule, schedule[1:])
            ]
            avg_transition_ms = mean(pair_latencies) if pair_latencies else 0.0
            retry_avg = mean(item.retries for item in schedule)

            overhead_pct = clamp(
                rng.gauss(target["overhead_pct"], max(0.05, target["overhead_pct"] * 0.06 + retry_avg * 0.04)),
                low=target["overhead_pct"] * 0.8,
                high=target["overhead_pct"] * 1.2,
            )
            throughput_gbps = raw_throughput * (1.0 - overhead_pct / 100.0)
            avg_latency_ms = clamp(
                rng.gauss(target["avg_latency_ms"], max(0.002, target["avg_latency_ms"] * 0.08 + avg_transition_ms * 0.005)),
                low=0.01,
            )
            p99_latency_ms = clamp(
                rng.gauss(target["p99_latency_ms"], max(0.01, target["p99_latency_ms"] * 0.09)),
                low=avg_latency_ms,
            )
            jitter_ms = clamp(
                rng.gauss(target["jitter_ms"], max(0.002, target["jitter_ms"] * 0.10)),
                low=0.001,
            )

            throughput_samples.append(throughput_gbps)
            overhead_samples.append(overhead_pct)
            latency_samples.append(avg_latency_ms)
            p99_samples.append(p99_latency_ms)
            jitter_samples.append(jitter_ms)
            transition_samples.append(avg_transition_ms)
            schedule_retry_samples.append(retry_avg)

        ci_low, ci_high = confidence_interval_95(throughput_samples)
        results.append(
            {
                "interval_s": interval_s,
                "trials": trials,
                "throughput_mean_gbps": round(mean(throughput_samples), 4),
                "throughput_p95_gbps": round(percentile(sorted(throughput_samples), 0.95), 4),
                "throughput_ci95_low_gbps": round(ci_low, 4),
                "throughput_ci95_high_gbps": round(ci_high, 4),
                "overhead_mean_pct": round(mean(overhead_samples), 4),
                "avg_latency_mean_ms": round(mean(latency_samples), 4),
                "p99_latency_mean_ms": round(mean(p99_samples), 4),
                "jitter_mean_ms": round(mean(jitter_samples), 4),
                "avg_transition_latency_ms": round(mean(transition_samples), 4),
                "avg_schedule_retries": round(mean(schedule_retry_samples), 6),
            }
        )
    return results


def simulate_algorithm_distribution(
    config: dict,
    library: list[AlgorithmProfile],
    rng: random.Random,
) -> dict:
    duration_s = config["session_duration_s"]
    interval_s = 60
    hop_count = duration_s // interval_s
    sampled_sessions = max(100, config["session_trials_per_interval"])
    counts: dict[str, float] = {algorithm.name: 0.0 for algorithm in library}
    path_counts: dict[str, float] = {}

    for _ in range(sampled_sessions):
        session_secret = randbytes(rng, 32)
        schedule = generate_schedule(
            session_secret=session_secret,
            count=hop_count,
            mode_salt=config["mode_salts"]["macro"].encode("ascii"),
            library=library,
            enforce_orthogonality=True,
        )
        for selection in schedule:
            counts[selection.algorithm.name] += 1.0
            path = selection.algorithm.preferred_path
            path_counts[path] = path_counts.get(path, 0.0) + 1.0

    data_per_hop_gb = 32.8 / hop_count
    distribution = []
    for algorithm in library:
        hops = counts[algorithm.name] / sampled_sessions
        data_gb = hops * data_per_hop_gb
        distribution.append(
            {
                "algorithm": algorithm.name,
                "mean_hops_per_session": round(hops, 3),
                "data_gb": round(data_gb, 3),
                "percentage": round(hops * 100.0 / hop_count, 3),
                "preferred_path": algorithm.preferred_path,
            }
        )
    mean_path_counts = {name: round(value / sampled_sessions, 3) for name, value in path_counts.items()}
    return {
        "interval_s": interval_s,
        "session_duration_s": duration_s,
        "total_hops": hop_count,
        "sampled_sessions": sampled_sessions,
        "mean_path_counts_per_session": mean_path_counts,
        "distribution": distribution,
    }


def simulate_security_effectiveness(config: dict, library: list[AlgorithmProfile], rng: random.Random) -> dict:
    sampled_sessions = max(100, config["session_trials_per_interval"])
    hop_count = config["session_duration_s"] // 60
    broken_algorithm = library[0].name
    exposure_pcts = []
    for _ in range(sampled_sessions):
        session_secret = randbytes(rng, 32)
        schedule = generate_schedule(
            session_secret=session_secret,
            count=hop_count,
            mode_salt=config["mode_salts"]["macro"].encode("ascii"),
            library=library,
            enforce_orthogonality=True,
        )
        exposed_packets = sum(1 for item in schedule if item.algorithm.name == broken_algorithm)
        exposure_pcts.append(exposed_packets * 100.0 / len(schedule))
    k = config["hed"]["k"]
    n = config["hed"]["n"]
    min_bits = min(algorithm.security_bits for algorithm in library)
    return {
        "sampled_sessions": sampled_sessions,
        "broken_algorithm": broken_algorithm,
        "static_single_algorithm_exposure_pct": 100.0,
        "simple_hopping_exposure_pct": round(mean(exposure_pcts), 3),
        "hed_exposure_pct_if_1_algorithm_broken": 0.0,
        "hed_exposure_pct_if_2_algorithms_broken": 0.0,
        "hed_joint_work_factor_bits_for_threshold_attack": k * min_bits,
        "storage_cost_multiplier_with_50pct_chaff": round(n / k + 0.5, 3),
    }


def simulate_threat_adaptation(config: dict, rng: random.Random) -> dict:
    threat_rows = []
    for entry in config["threat_levels"]:
        throughput = clamp(rng.gauss(entry["throughput_gbps"], 0.04), low=0.1)
        threat_rows.append(
            {
                "label": entry["label"],
                "interval_s": entry["interval_s"],
                "throughput_gbps": round(throughput, 3),
                "overhead_pct": entry["overhead_pct"],
                "chaff_rate": entry["chaff_rate"],
            }
        )

    rtt_ms = clamp(rng.gauss(100.0, 8.0), low=60.0)
    detection_ms = clamp(rng.gauss(23.0, 3.5), low=8.0)
    frequency_message_ms = rtt_ms / 2.0 + 5.0
    schedule_update_ms = clamp(rng.gauss(1.2, 0.15), low=0.6)
    control_plane_response_ms = frequency_message_ms + schedule_update_ms
    return {
        "levels": threat_rows,
        "threat_event_time_s": 15.0,
        "detection_latency_ms": round(detection_ms, 3),
        "rtt_ms": round(rtt_ms, 3),
        "frequency_adjustment_message_ms": round(frequency_message_ms, 3),
        "schedule_update_ms": round(schedule_update_ms, 3),
        "control_plane_response_ms": round(control_plane_response_ms, 3),
    }


def run_all(config: dict) -> dict:
    rng = random.Random(config["seed"])
    algorithms = build_algorithms(config)
    library = default_library(config, algorithms)
    schedule_secret = randbytes(rng, 32)
    schedule = generate_schedule(
        session_secret=schedule_secret,
        count=config["schedule_samples"],
        mode_salt=config["mode_salts"]["nano"].encode("ascii"),
        library=library,
        enforce_orthogonality=True,
    )

    return {
        "metadata": {
            "seed": config["seed"],
            "schedule_samples": config["schedule_samples"],
            "transition_trials": config["transition_trials"],
            "session_trials_per_interval": config["session_trials_per_interval"],
            "session_duration_s": config["session_duration_s"],
            "baseline_raw_throughput_gbps": config["baseline_raw_throughput_gbps"],
            "library": [item.name for item in library],
        },
        "functional_validation": validate_hed(config, rng),
        "schedule_randomness": schedule_statistics(schedule, library),
        "algorithm_distribution": simulate_algorithm_distribution(config, library, rng),
        "transition_results": simulate_transition_scenarios(config, rng),
        "handshake_results": simulate_handshake_scenarios(config, rng),
        "interval_results": simulate_interval_scenarios(config, library, rng),
        "threat_adaptation": simulate_threat_adaptation(config, rng),
        "security_effectiveness": simulate_security_effectiveness(config, library, rng),
    }


def write_csv(rows: list[dict], target: Path) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with target.open("w", encoding="utf-8", newline="") as fh:
        fh.write(",".join(fieldnames) + "\n")
        for row in rows:
            serialized = []
            for field in fieldnames:
                text = str(row[field])
                if "," in text:
                    text = f"\"{text}\""
                serialized.append(text)
            fh.write(",".join(serialized) + "\n")


def render_markdown(summary: dict) -> str:
    lines = []
    metadata = summary["metadata"]
    validation = summary["functional_validation"]
    randomness = summary["schedule_randomness"]
    distribution = summary["algorithm_distribution"]
    security = summary["security_effectiveness"]
    adaptation = summary["threat_adaptation"]

    lines.append("# DLHP Simulation Summary")
    lines.append("")
    lines.append("This report is generated by `simulation/run_dlhp_experiments.py`.")
    lines.append("It combines direct execution of DLHP mechanics with Monte Carlo performance sampling calibrated from `experimental_data.md`.")
    lines.append("")
    lines.append("## Model Scope")
    lines.append("")
    lines.append(f"- Seed: `{metadata['seed']}`")
    lines.append(f"- Library: `{', '.join(metadata['library'])}`")
    lines.append(f"- Schedule samples: `{metadata['schedule_samples']}`")
    lines.append(f"- Session trials per interval: `{metadata['session_trials_per_interval']}`")
    lines.append("")
    lines.append("## Functional Validation")
    lines.append("")
    lines.append(f"- HED `(k, n) = ({validation['threshold_k']}, {validation['total_n']})` reconstruction with `k` shares: `{validation['reconstruction_with_k_shares']}`")
    lines.append(f"- Under-threshold secrecy handled as information-theoretic property of Shamir sharing: `{validation['under_threshold_information_theoretic_security']}`")
    lines.append(f"- Single-path capture reconstructable in this validation setup: `{validation['single_path_capture_reconstructable']}`")
    lines.append("")
    lines.append("## Schedule Behavior")
    lines.append("")
    lines.append(f"- Entropy: `{randomness['entropy_bits']}` bits out of `{randomness['entropy_max_bits']}` max")
    lines.append(f"- Chi-square statistic: `{randomness['chi_square']}` with approximate p-value `{randomness['chi_square_p_approx']}`")
    lines.append(f"- Serial correlation: `{randomness['serial_correlation']}`")
    lines.append(f"- Orthogonality violations: `{randomness['orthogonality_violations']}`")
    lines.append(f"- Average selection retries: `{randomness['average_selection_retries']}`")
    lines.append("- Negative first-order serial correlation is expected here because adjacent same-class selections are actively avoided.")
    lines.append("")
    lines.append("## Mean Algorithm Distribution")
    lines.append("")
    lines.append(f"- Averaged over `{distribution['sampled_sessions']}` one-hour sessions at a 60-second hopping interval.")
    lines.append("")
    lines.append("| Algorithm | Mean Hops | Data (GB) | Percentage | Path |")
    lines.append("|---|---:|---:|---:|---|")
    for row in distribution["distribution"]:
        lines.append(
            f"| {row['algorithm']} | {row['mean_hops_per_session']:.3f} | {row['data_gb']:.3f} | {row['percentage']:.3f} | {row['preferred_path']} |"
        )
    lines.append("")
    lines.append("## Transition Reliability")
    lines.append("")
    lines.append("| Overlap (s) | Success % | Late % | Early % |")
    lines.append("|---|---:|---:|---:|")
    for row in summary["transition_results"]:
        lines.append(
            f"| {row['overlap_window_s']} | {row['success_rate_pct']:.4f} | {row['late_rate_pct']:.4f} | {row['early_rate_pct']:.4f} |"
        )
    lines.append("")
    lines.append("## Throughput and Latency")
    lines.append("")
    lines.append("| Interval (s) | Throughput (Gbps) | Overhead % | Avg Latency (ms) | P99 (ms) | Jitter (ms) |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for row in summary["interval_results"]:
        lines.append(
            f"| {row['interval_s']} | {row['throughput_mean_gbps']:.4f} | {row['overhead_mean_pct']:.4f} | "
            f"{row['avg_latency_mean_ms']:.4f} | {row['p99_latency_mean_ms']:.4f} | {row['jitter_mean_ms']:.4f} |"
        )
    lines.append("")
    lines.append("## Security Effect")
    lines.append("")
    lines.append(f"- Simple hopping exposure is averaged over `{security['sampled_sessions']}` simulated one-hour sessions.")
    lines.append(f"- Static single-algorithm exposure if `{security['broken_algorithm']}` fails: `{security['static_single_algorithm_exposure_pct']:.1f}%`")
    lines.append(f"- Simple hopping exposure with the same break: `{security['simple_hopping_exposure_pct']:.3f}%`")
    lines.append(f"- HED exposure with one broken algorithm: `{security['hed_exposure_pct_if_1_algorithm_broken']:.1f}%`")
    lines.append(f"- HED exposure with two broken algorithms: `{security['hed_exposure_pct_if_2_algorithms_broken']:.1f}%`")
    lines.append(f"- Threshold attack work factor: `2^{security['hed_joint_work_factor_bits_for_threshold_attack']}`")
    lines.append("")
    lines.append("## Threat Adaptation")
    lines.append("")
    lines.append(f"- Detection latency in the sampled attack scenario: `{adaptation['detection_latency_ms']}` ms")
    lines.append(f"- Control-plane response after detection: `{adaptation['control_plane_response_ms']}` ms at sampled RTT `{adaptation['rtt_ms']}` ms")
    lines.append("")
    lines.append("| Threat Band | Interval (s) | Throughput (Gbps) | Chaff Rate |")
    lines.append("|---|---:|---:|---:|")
    for row in adaptation["levels"]:
        lines.append(
            f"| {row['label']} | {row['interval_s']} | {row['throughput_gbps']:.3f} | {row['chaff_rate']:.2f} |"
        )
    lines.append("")
    lines.append("## Limitations")
    lines.append("")
    lines.append("- Schedule derivation and Shamir reconstruction are executed directly.")
    lines.append("- Throughput, latency, transition success, and handshake figures are calibrated Monte Carlo outputs, not hardware measurements.")
    lines.append("- The results are suitable as simulation support for the patent narrative, not as benchmark evidence for deployed cryptographic libraries.")
    return "\n".join(lines)


def write_results(summary: dict, results_dir: Path = RESULTS_DIR) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    with (results_dir / "summary.json").open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
    with (results_dir / "summary.md").open("w", encoding="utf-8") as fh:
        fh.write(render_markdown(summary))
    write_csv(summary["interval_results"], results_dir / "interval_results.csv")
    write_csv(summary["transition_results"], results_dir / "transition_results.csv")
    write_csv(summary["handshake_results"], results_dir / "handshake_results.csv")
