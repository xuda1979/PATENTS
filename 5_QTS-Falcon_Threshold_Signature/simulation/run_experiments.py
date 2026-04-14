import csv
import json
import math
import random
from pathlib import Path
from statistics import mean, median, stdev

ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
CONFIG_PATH = ROOT / "config.json"


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def percentile(sorted_values, pct: float) -> float:
    if not sorted_values:
        return float("nan")
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * pct
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    d0 = sorted_values[f] * (c - k)
    d1 = sorted_values[c] * (k - f)
    return d0 + d1


def confidence_interval_95(values):
    if len(values) < 2:
        x = values[0] if values else 0.0
        return (x, x)
    m = mean(values)
    s = stdev(values)
    margin = 1.96 * s / math.sqrt(len(values))
    return (m - margin, m + margin)


def normal_clamped(rng: random.Random, mu: float, sigma: float, low: float | None = None, high: float | None = None) -> float:
    value = rng.gauss(mu, sigma)
    if low is not None:
        value = max(low, value)
    if high is not None:
        value = min(high, value)
    return value


def simulate_standard(config: dict, size_cfg: dict, iterations: int, rng: random.Random):
    rows = []
    for idx in range(iterations):
        size = round(normal_clamped(rng, size_cfg["standard_mean"], size_cfg["standard_std"], size_cfg["min"], size_cfg["max"]))
        signing = normal_clamped(rng, config["signing_mean_ms"], config["signing_std_ms"], 0.1)
        verify = normal_clamped(rng, config["verification_mean_ms"], config["verification_std_ms"], 0.05)
        total = signing
        throughput = 1000.0 / total
        rows.append({
            "scheme": "Standard Falcon-512",
            "trial": idx + 1,
            "signature_size_bytes": size,
            "online_latency_ms": total,
            "offline_latency_ms": 0.0,
            "verification_ms": verify,
            "attempts": 1,
            "communication_rounds": config["communication_rounds"],
            "data_kb": config["data_kb"],
            "throughput_sig_s": throughput,
            "accepted": 1,
        })
    return rows


def simulate_threshold(cfg: dict, size_cfg: dict, iterations: int, rng: random.Random):
    rows = []
    for idx in range(iterations):
        attempts = 1
        while rng.random() > cfg["acceptance_probability"]:
            attempts += 1
        size = round(normal_clamped(rng, size_cfg["threshold_mean"], size_cfg["threshold_std"], size_cfg["min"], size_cfg["max"]))
        per_attempt = (
            normal_clamped(rng, cfg["local_ntt_mean_ms"], cfg["local_ntt_std_ms"], 0.05)
            + normal_clamped(rng, cfg["gaussian_mean_ms"], cfg["gaussian_std_ms"], 0.05)
            + normal_clamped(rng, cfg["broadcast_mean_ms"], cfg["broadcast_std_ms"], 0.05)
            + normal_clamped(rng, cfg["beaver_mean_ms"], cfg["beaver_std_ms"], 0.05)
            + normal_clamped(rng, cfg["reveal_mean_ms"], cfg["reveal_std_ms"], 0.05)
            + normal_clamped(rng, cfg["coinflip_mean_ms"], cfg["coinflip_std_ms"], 0.05)
            + normal_clamped(rng, cfg["aggregation_mean_ms"], cfg["aggregation_std_ms"], 0.05)
        )
        total_online = per_attempt * attempts
        offline = normal_clamped(rng, cfg["offline_mean_ms"], cfg["offline_std_ms"], 0.1)
        throughput = 1000.0 / total_online
        rows.append({
            "scheme": cfg["name"],
            "trial": idx + 1,
            "signature_size_bytes": size,
            "online_latency_ms": total_online,
            "offline_latency_ms": offline,
            "verification_ms": normal_clamped(rng, 1.35, 0.2, 0.05),
            "attempts": attempts,
            "communication_rounds": cfg["communication_rounds"],
            "data_kb": cfg["data_kb"],
            "throughput_sig_s": throughput,
            "accepted": 1,
        })
    return rows


def summarize(rows: list[dict]) -> dict:
    by_scheme = {}
    for row in rows:
        by_scheme.setdefault(row["scheme"], []).append(row)

    summary = {"schemes": []}
    for scheme, samples in by_scheme.items():
        online = sorted(sample["online_latency_ms"] for sample in samples)
        offline = sorted(sample["offline_latency_ms"] for sample in samples)
        sizes = sorted(sample["signature_size_bytes"] for sample in samples)
        attempts = sorted(sample["attempts"] for sample in samples)
        throughput = sorted(sample["throughput_sig_s"] for sample in samples)
        verify = sorted(sample["verification_ms"] for sample in samples)
        ci_low, ci_high = confidence_interval_95(online)
        summary["schemes"].append({
            "scheme": scheme,
            "trials": len(samples),
            "signature_size": {
                "mean": round(mean(sizes), 3),
                "std": round(stdev(sizes), 3) if len(sizes) > 1 else 0.0,
                "min": min(sizes),
                "max": max(sizes)
            },
            "online_latency": {
                "mean_ms": round(mean(online), 3),
                "std_ms": round(stdev(online), 3) if len(online) > 1 else 0.0,
                "p50_ms": round(percentile(online, 0.50), 3),
                "p95_ms": round(percentile(online, 0.95), 3),
                "p99_ms": round(percentile(online, 0.99), 3),
                "ci95_ms": [round(ci_low, 3), round(ci_high, 3)]
            },
            "offline_latency": {
                "mean_ms": round(mean(offline), 3),
                "std_ms": round(stdev(offline), 3) if len(offline) > 1 else 0.0
            },
            "verification": {
                "mean_ms": round(mean(verify), 3),
                "p95_ms": round(percentile(verify, 0.95), 3)
            },
            "attempts": {
                "mean": round(mean(attempts), 3),
                "p95": round(percentile(attempts, 0.95), 3),
                "max": max(attempts)
            },
            "communication_rounds": samples[0]["communication_rounds"],
            "data_kb": round(mean(sample["data_kb"] for sample in samples), 3),
            "throughput_sig_s": round(mean(throughput), 3)
        })
    summary["schemes"].sort(key=lambda item: item["scheme"])
    return summary


def write_csv(rows: list[dict], target: Path):
    fieldnames = list(rows[0].keys())
    with target.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def render_markdown(summary: dict, config: dict) -> str:
    lines = []
    lines.append("# Falcon 数值试验结果汇总")
    lines.append("")
    lines.append("## 试验说明")
    lines.append("")
    lines.append("本文件由 `simulation/run_experiments.py` 自动生成。")
    lines.append("试验采用**可重复统计仿真**，比较传统 `Falcon-512` 与多种门限 `Falcon-512` 在线签名配置。")
    lines.append("这不是对 `liboqs` 或 Falcon 参考实现的直接封装，而是对专利材料中延迟、通信、拒绝采样和签名长度行为的参数化建模。")
    lines.append("")
    lines.append("## 试验参数")
    lines.append("")
    lines.append(f"- 随机种子：`{config['seed']}`")
    lines.append(f"- 每个方案试验次数：`{config['iterations']}`")
    lines.append(f"- 目标算法：`{config['falcon_variant']}`")
    lines.append("")
    lines.append("## 汇总结果")
    lines.append("")
    lines.append("| Scheme | Signature Size Mean (B) | Online Mean (ms) | P95 (ms) | Offline Mean (ms) | Attempts Mean | Rounds | Data (KB) | Throughput (sig/s) |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for item in summary["schemes"]:
        lines.append(
            f"| {item['scheme']} | {item['signature_size']['mean']:.2f} | {item['online_latency']['mean_ms']:.2f} | {item['online_latency']['p95_ms']:.2f} | {item['offline_latency']['mean_ms']:.2f} | {item['attempts']['mean']:.2f} | {item['communication_rounds']} | {item['data_kb']:.2f} | {item['throughput_sig_s']:.2f} |"
        )
    lines.append("")
    standard = next(item for item in summary["schemes"] if item["scheme"] == "Standard Falcon-512")
    threshold_items = [item for item in summary["schemes"] if item["scheme"] != "Standard Falcon-512"]
    lines.append("## 对比结论")
    lines.append("")
    for item in threshold_items:
        online_ratio = item['online_latency']['mean_ms'] / standard['online_latency']['mean_ms']
        size_delta = item['signature_size']['mean'] - standard['signature_size']['mean']
        lines.append(
            f"- `{item['scheme']}` 的平均在线签名时延是传统 Falcon 的 **{online_ratio:.2f}×**，"
            f"签名长度差为 **{size_delta:.2f} B**。"
        )
    lines.append("")
    lines.append("## 解释")
    lines.append("")
    lines.append("- 传统 Falcon 没有多方交互，因此在线延迟最低、通信轮数最少。")
    lines.append("- 门限 Falcon 保持了与标准 Falcon 基本一致的签名长度，但在线耗时会随着参与方数量增加而上升。")
    lines.append("- 拒绝采样使门限方案的尝试次数大于 1；配置规模越大，平均尝试次数通常越高。")
    lines.append("- 离线开销主要来自 Beaver 三元组和相关预处理，适合批量摊销。")
    lines.append("")
    lines.append("## 文件产物")
    lines.append("")
    lines.append("- `simulation/results/raw_samples.csv`：逐次试验原始数据")
    lines.append("- `simulation/results/summary.json`：结构化统计结果")
    lines.append("- `simulation/results/summary.md`：当前报告")
    lines.append("")
    return "\n".join(lines)


def main():
    config = load_config()
    rng = random.Random(config["seed"])
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    rows.extend(simulate_standard(config["standard_falcon"], config["signature_size"], config["iterations"], rng))
    for threshold_cfg in config["threshold_configs"]:
        rows.extend(simulate_threshold(threshold_cfg, config["signature_size"], config["iterations"], rng))

    summary = summarize(rows)
    write_csv(rows, RESULTS_DIR / "raw_samples.csv")
    with (RESULTS_DIR / "summary.json").open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
    markdown = render_markdown(summary, config)
    with (RESULTS_DIR / "summary.md").open("w", encoding="utf-8") as fh:
        fh.write(markdown)

    print(f"Generated {len(rows)} samples across {len(summary['schemes'])} schemes.")
    print(f"Summary written to: {RESULTS_DIR / 'summary.md'}")


if __name__ == "__main__":
    main()
