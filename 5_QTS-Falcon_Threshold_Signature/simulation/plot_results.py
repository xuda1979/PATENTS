import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / 'results'
SUMMARY_PATH = RESULTS_DIR / 'summary.json'


def load_summary() -> dict:
    with SUMMARY_PATH.open('r', encoding='utf-8') as fh:
        return json.load(fh)


def short_label(name: str) -> str:
    return (
        name.replace('Standard Falcon-512', 'Standard')
            .replace('Threshold Falcon ', '')
    )


def extract_series(summary: dict):
    schemes = summary['schemes']
    ordered = []
    standard = next(item for item in schemes if item['scheme'] == 'Standard Falcon-512')
    ordered.append(standard)
    threshold = [item for item in schemes if item['scheme'] != 'Standard Falcon-512']
    threshold.sort(key=lambda item: item['online_latency']['mean_ms'])
    ordered.extend(threshold)
    labels = [short_label(item['scheme']) for item in ordered]
    return ordered, labels


def annotate_bars(ax, bars, fmt='{:.2f}', y_offset=0.01):
    ymax = ax.get_ylim()[1]
    for bar in bars:
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            height + ymax * y_offset,
            fmt.format(height),
            ha='center',
            va='bottom',
            fontsize=9,
        )


def save_online_latency(summary: dict):
    ordered, labels = extract_series(summary)
    means = [item['online_latency']['mean_ms'] for item in ordered]
    p95 = [item['online_latency']['p95_ms'] for item in ordered]

    fig, ax = plt.subplots(figsize=(10, 6))
    x = range(len(labels))
    bars = ax.bar(x, means, color=['#1f77b4'] + ['#2ca02c'] * (len(labels) - 1))
    ax.plot(list(x), p95, color='#d62728', marker='o', linewidth=2, label='P95 latency')
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylabel('Latency (ms)')
    ax.set_title('Falcon Online Signing Latency Comparison')
    ax.grid(axis='y', linestyle='--', alpha=0.4)
    ax.legend()
    annotate_bars(ax, bars)
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / 'Chart_Falcon_OnlineLatency.png', dpi=300)
    plt.close(fig)


def save_throughput(summary: dict):
    ordered, labels = extract_series(summary)
    values = [item['throughput_sig_s'] for item in ordered]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(labels, values, color=['#1f77b4'] + ['#9467bd'] * (len(labels) - 1))
    ax.set_ylabel('Signatures / second')
    ax.set_title('Falcon Throughput Comparison')
    ax.grid(axis='y', linestyle='--', alpha=0.4)
    annotate_bars(ax, bars)
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / 'Chart_Falcon_Throughput.png', dpi=300)
    plt.close(fig)


def save_communication(summary: dict):
    ordered, labels = extract_series(summary)
    data_kb = [item['data_kb'] for item in ordered]
    rounds = [item['communication_rounds'] for item in ordered]

    fig, ax1 = plt.subplots(figsize=(10, 6))
    bars = ax1.bar(labels, data_kb, color=['#1f77b4'] + ['#ff7f0e'] * (len(labels) - 1))
    ax1.set_ylabel('Transferred Data (KB)', color='#ff7f0e')
    ax1.tick_params(axis='y', labelcolor='#ff7f0e')
    ax1.set_title('Communication Cost Comparison')
    ax1.grid(axis='y', linestyle='--', alpha=0.4)
    annotate_bars(ax1, bars)

    ax2 = ax1.twinx()
    ax2.plot(labels, rounds, color='#2ca02c', marker='o', linewidth=2)
    ax2.set_ylabel('Communication Rounds', color='#2ca02c')
    ax2.tick_params(axis='y', labelcolor='#2ca02c')

    plt.tight_layout()
    plt.savefig(RESULTS_DIR / 'Chart_Falcon_Communication.png', dpi=300)
    plt.close(fig)


def save_attempts(summary: dict):
    ordered, labels = extract_series(summary)
    values = [item['attempts']['mean'] for item in ordered]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(labels, values, color=['#1f77b4'] + ['#8c564b'] * (len(labels) - 1))
    ax.set_ylabel('Average Attempts')
    ax.set_title('Rejection Sampling Attempt Comparison')
    ax.grid(axis='y', linestyle='--', alpha=0.4)
    annotate_bars(ax, bars)
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / 'Chart_Falcon_Attempts.png', dpi=300)
    plt.close(fig)


def main():
    summary = load_summary()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    save_online_latency(summary)
    save_throughput(summary)
    save_communication(summary)
    save_attempts(summary)
    print('Generated Falcon experiment charts.')


if __name__ == '__main__':
    main()
