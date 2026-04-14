from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
SUMMARY_PATH = RESULTS_DIR / "summary.json"


def load_summary() -> dict:
    with SUMMARY_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def ordered_scheme_names(summary: dict) -> list[str]:
    schemes = summary["schemes"]
    titan_names = sorted(
        (name for name, item in schemes.items() if item["family"] == "titan"),
        key=lambda name: (schemes[name]["param_n"], schemes[name]["rounds"]),
    )
    falcon_names = sorted(
        (name for name, item in schemes.items() if item["family"] == "falcon"),
        key=lambda name: schemes[name]["param_n"],
    )
    return titan_names + falcon_names


def short_label(name: str) -> str:
    if name.startswith("titan-"):
        _, n_part, r_part = name.split("-")
        return f"{n_part.upper()}\n{r_part.upper()}"
    if name.startswith("falcon-"):
        return name.replace("falcon-", "F")
    return name


def color_for(name: str) -> str:
    return "#4C78A8" if name.startswith("titan-") else "#7F7F7F"


def annotate_bars(ax, bars, fmt: str) -> None:
    ymax = ax.get_ylim()[1]
    for bar in bars:
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            height + ymax * 0.015,
            format(height, fmt),
            ha="center",
            va="bottom",
            fontsize=8,
            rotation=90,
        )


def plot_latency(summary: dict) -> None:
    schemes = summary["schemes"]
    names = ordered_scheme_names(summary)
    labels = [short_label(name) for name in names]
    colors = [color_for(name) for name in names]
    x = np.arange(len(names))

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.6))
    ops = [
        ("keygen", "Key Generation Mean (ms)", True),
        ("sign", "Signing Mean (ms)", False),
        ("verify", "Verification Mean (ms)", False),
    ]

    for ax, (op, title, use_log) in zip(axes, ops):
        values = [schemes[name][op]["mean_ms"] for name in names]
        bars = ax.bar(x, values, color=colors)
        ax.set_title(title)
        ax.set_xticks(x, labels)
        ax.grid(axis="y", alpha=0.25, linestyle="--")
        if use_log:
            ax.set_yscale("log")
            annotate_bars(ax, bars, ".1f")
        else:
            annotate_bars(ax, bars, ".2f")
        ax.set_axisbelow(True)

    fig.suptitle("Real Runtime Comparison Generated from summary.json", fontsize=13)
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "latency_comparison.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_sizes(summary: dict) -> None:
    schemes = summary["schemes"]
    names = ordered_scheme_names(summary)
    labels = [short_label(name) for name in names]
    colors = [color_for(name) for name in names]
    x = np.arange(len(names))

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.6))
    metrics = [
        ("pk_bytes", "Public Key Size (B)"),
        ("sk_bytes", "Secret Key Size (B)"),
        ("sig_bytes", "Signature Size (B)"),
    ]

    for ax, (metric, title) in zip(axes, metrics):
        values = [schemes[name]["sizes"][metric] for name in names]
        bars = ax.bar(x, values, color=colors)
        ax.set_title(title)
        ax.set_xticks(x, labels)
        ax.grid(axis="y", alpha=0.25, linestyle="--")
        annotate_bars(ax, bars, ".0f")
        ax.set_axisbelow(True)

    fig.suptitle("Real Size Comparison Generated from summary.json", fontsize=13)
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "size_comparison.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    summary = load_summary()
    plot_latency(summary)
    plot_sizes(summary)
    print("Generated:", RESULTS_DIR / "latency_comparison.png")
    print("Generated:", RESULTS_DIR / "size_comparison.png")


if __name__ == "__main__":
    main()
