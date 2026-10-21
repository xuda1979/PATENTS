#!/usr/bin/env python3
"""Regenerate the measured-data paper figures from archived result artifacts.

Sources (all under results/ASI3_arm4_decisive_20260828/):
  key_results_SHIPPED.json  - the authoritative shipped-kernel run
                               (probe T=128 + large-T T=4096 medians)
  full_metrics.json         - pipes_materialized / pipes_fused: op-level
                               Task Durations over the matched large-T
                               msprof passes (the fig:opdecomp source)

Outputs (into figs/ and tmlr/figs/):
  fourarm_ladder.pdf        - Fig. tab:fourarmmeasured companion
  op_decomp.pdf             - Fig. fig:opdecomp companion

Run from paper/:
  python3 make_paper_figures.py

Design rules:
  * No hard-coded measurement values: every bar/label is read from the
    archived JSON, so a re-run can never silently desynchronize figure
    and text.
  * Layout matches the original figures (two-panel ladder; horizontal
    op-duration bars) so the paper source does not need changes.
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.normpath(os.path.join(
    HERE, os.pardir, "results", "ASI3_arm4_decisive_20260828"))


def load(name):
    path = os.path.join(RESULTS, name)
    with open(path) as fh:
        return json.load(fh)


def fmt(ms):
    return f"{ms:.3f}"


def fourarm_ladder(shipped, out_paths):
    probe = shipped["probe_geometry"]
    larget = shipped["largeT_geometry"]
    pm = probe["median_ms"]
    lm = larget["median_ms"]

    probe_ratio = pm["fused"] / pm["materialized"]
    large_ratio = lm["fused"] / lm["materialized"]

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(7.2, 2.5),
        gridspec_kw={"width_ratios": [4, 2], "wspace": 0.38})

    labels = ["Dense\nkernels", "Persistent\nlow-rank",
              "Materialized\ncore (arm 3)", "Fused no-store\ncore (arm 4)"]
    vals = [pm["dense"], pm["persistent"], pm["materialized"], pm["fused"]]
    colors = ["#4C72B0", "#4C716F", "#DD8452", "#55A868"]
    bars = ax1.bar(labels, vals, color=colors, width=0.62)
    for b, v in zip(bars, vals):
        ax1.annotate(fmt(v), (b.get_x() + b.get_width() / 2, v),
                     ha="center", va="bottom", fontsize=8)
    ax1.set_ylabel("median latency (ms)")
    ax1.set_ylim(0, 1.0)
    ax1.set_title(f"(a) Four-arm probe, T = 128 (working set L2-resident)",
                  fontsize=9)
    ax1.annotate(f"parity: {probe_ratio:.2f}×\n(max|$\\Delta$| at fp16 floor)",
                 xy=(0.74, 0.80), xycoords="axes fraction",
                 ha="center", va="top", fontsize=8,
                 bbox=dict(boxstyle="round,pad=0.3", fc="white",
                           ec="#999999", lw=0.6))

    labels2 = ["Materialized\ncore (arm 3)", "Fused no-store\ncore (arm 4)"]
    vals2 = [lm["materialized"], lm["fused"]]
    bars2 = ax2.bar(labels2, vals2, color=["#DD8452", "#55A868"], width=0.55)
    for b, v in zip(bars2, vals2):
        ax2.annotate(f"{v:.2f}", (b.get_x() + b.get_width() / 2, v),
                     ha="center", va="bottom", fontsize=8)
    ax2.set_ylabel("median latency (ms)")
    ax2.set_ylim(0, 3.0)
    ax2.set_title(f"(b) T = 4096, core (2 MiB) exceeds 192 KiB per-core UB: "
                  f"{large_ratio:.2f}×", fontsize=9)

    for ax in (ax1, ax2):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.tick_params(axis="x", labelsize=7.5)

    fig.tight_layout()
    for p in out_paths:
        fig.savefig(p)
        print(f"wrote {p}")
    plt.close(fig)


def op_decomp(full_metrics, out_paths):
    mat = full_metrics["pipes_materialized"]["top"]
    fus = full_metrics["pipes_fused"]["top"]

    # Op display order mirrors the kernel pipeline: matmul, ephemeral,
    # then elementwise families.
    order = [
        ("aclnnMatmul", "Matmul"),
        ("ephemeral", "Ephemeral\nkernel"),
        ("aclnnMul", "Mul"),
        ("aclnnCast", "Cast"),
        ("aclnnSilu", "SiLU"),
        ("aclnnTanh", "Tanh"),
        ("aclnnAdd", "Add"),
        ("aclnnMuls", "Muls"),
    ]
    rows = []
    for key, label in order:
        m = mat.get(key, {}).get("Task Duration(us)", 0.0) / 1000.0
        f = fus.get(key, {}).get("Task Duration(us)", 0.0) / 1000.0
        rows.append((label, m, f))

    rows.sort(key=lambda r: r[1] + r[2])  # smallest at top axis position 0

    labels = [r[0] for r in rows]
    mat_ms = [r[1] for r in rows]
    fus_ms = [r[2] for r in rows]
    y = range(len(rows))

    fig, ax = plt.subplots(figsize=(3.4, 2.55))
    h = 0.36
    ax.barh([i - h / 2 for i in y], mat_ms, height=h,
            color="#DD8452", label="arm 3 (materialized)")
    ax.barh([i + h / 2 for i in y], fus_ms, height=h,
            color="#55A868", label="arm 4 (fused)")
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=7.5)
    ax.set_xlabel("total kernel time, large-T pass (ms)", fontsize=8)
    ax.tick_params(axis="x", labelsize=7.5)
    # center right: the mid-height rows (SiLU 2.75 ms, Cast 1.51 ms on a
    # 0-25 ms axis) leave the right half bar-free; the lower-right corner
    # is reserved for the Epilogue annotation next to the sub-1-ms rows.
    ax.legend(fontsize=7.5, loc="center right", frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    eph = fus.get("ephemeral", {}).get("Task Duration(us)", 0.0) / 1000.0
    ax.annotate("Epilogue bottleneck: fused arm's\ncore generation is "
                "single-core",
                xy=(0.97, 0.06), xycoords="axes fraction",
                ha="right", va="bottom", fontsize=7,
                bbox=dict(boxstyle="round,pad=0.3", fc="white",
                          ec="#999999", lw=0.6))

    fig.tight_layout()
    for p in out_paths:
        fig.savefig(p)
        print(f"wrote {p}")
    plt.close(fig)
    return eph


def regime_map(out_paths):
    """Analytic reuse break-even curves (Figure fig:regimemap).

    Reimplements the closed-form model of Section sec:analysis (verified
    against experiments/mwg_regime_map.py and
    results/regime_map/mwg_regime_map.json): for causal reuse group q and
    B=1, S=1024, the optimistic base-only payload ratio vs dense is
      full factor:  rho = Gamma(r) * ceil(S/q)          (crosses 1 at
                    q_min = ceil(S / (ceil(1/Gamma)-1)); 43 (8B), 342 (1.5B))
      diag core:    rho = Gamma(r) + ceil(S/q) * r/(dm) (Eq. core-payload;
                    generated term 0.0022 (8B) / 0.0286 (1.5B) at q=1,
                    staying below 1 for all q)
    plotted on the log-q / log-ratio axes of the original figure.
    """
    import math
    import numpy as np

    S = 1024
    geoms = [
        ("8B", 4096, 14336, 128, "#C44E52"),
        ("1.5B", 1536, 8960, 384, "#4C72B0"),
    ]
    q = np.logspace(0, 3, 200)

    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    styles = {"full": "--", "diag": "-"}
    for name, d, m, r, color in geoms:
        gamma = r * (d + m) / (d * m)
        n_max = math.ceil(1 / gamma) - 1
        q_min = math.ceil(S / n_max)
        full = gamma * np.ceil(S / q)
        diag = gamma + np.ceil(S / q) * r / (d * m)
        for kind, y in (("full", full), ("diag", diag)):
            label = f"full factor, {name}" if kind == "full" else \
                    f"diag core, {name}"
            ax.plot(q, y, styles[kind], color=color, lw=1.4, label=label)
        print(f"  {name}: gamma={gamma:.4f}, q_min={q_min}")
    ax.axhline(1.0, color="k", lw=0.8, ls=":")
    ax.annotate("break-even (=1)", xy=(0.55, 1.0), xycoords="axes fraction",
                xytext=(0, 3), textcoords="offset points", fontsize=7.5)
    ax.set_title("Reuse break-even: full factors need\n"
                 "q >= 43 (8B) / q >= 342 (1.5B)", fontsize=8)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("causal reuse group q (tokens)", fontsize=8)
    ax.set_ylabel("logical payload / dense", fontsize=8)
    ax.tick_params(labelsize=7.5)
    ax.legend(fontsize=7.5, frameon=False, loc="center right")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    for p in out_paths:
        fig.savefig(p)
        print(f"wrote {p}")
    plt.close(fig)


def main():
    shipped = load("key_results_SHIPPED.json")
    full_metrics = load("full_metrics.json")

    figs = os.path.join(HERE, "figs")
    tmlr_figs = os.path.join(HERE, "tmlr", "figs")

    fourarm_ladder(shipped, [
        os.path.join(figs, "fourarm_ladder.pdf"),
        os.path.join(tmlr_figs, "fourarm_ladder.pdf"),
    ])
    op_decomp(full_metrics, [
        os.path.join(figs, "op_decomp.pdf"),
        os.path.join(tmlr_figs, "op_decomp.pdf"),
    ])
    regime_map([
        os.path.join(figs, "regime_map.pdf"),
        os.path.join(tmlr_figs, "regime_map.pdf"),
    ])

    # Consistency report against the paper's claims.
    pm = shipped["probe_geometry"]["median_ms"]
    lm = shipped["largeT_geometry"]["median_ms"]
    print()
    print("consistency report:")
    print(f"  probe fused/mat = {pm['fused']/pm['materialized']:.4f} "
          f"(paper: parity, 0.97x)")
    print(f"  large-T fused/mat = {lm['fused']/lm['materialized']:.4f} "
          f"(paper: 1.93x)")
    eph = full_metrics["pipes_fused"]["top"]["ephemeral"][
        "Task Duration(us)"] / 1000.0
    m3 = full_metrics["pipes_materialized"]["top"]["aclnnMatmul"][
        "Task Duration(us)"] / 1000.0
    m4 = full_metrics["pipes_fused"]["top"]["aclnnMatmul"][
        "Task Duration(us)"] / 1000.0
    ok = eph > m3 + m4
    print(f"  ephemeral {eph:.2f} ms vs combined matmuls "
          f"{m3:.2f}+{m4:.2f} = {m3+m4:.2f} ms; "
          f"caption claim (ephemeral > both combined): {ok}")


if __name__ == "__main__":
    sys.exit(main())
