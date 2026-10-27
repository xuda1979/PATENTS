#!/usr/bin/env python3
"""Figures from the audited archive and explicit analytical formula."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / "results/journal_revision_20261022/evidence_audit.json").read_text())
out = ROOT / "paper/figs"
out.mkdir(exist_ok=True)
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "pdf.fonttype": 42, "savefig.bbox": "tight"})
fig, ax = plt.subplots(figsize=(6.3, 2.8))
for name, label, color, marker in [("persistent_low_rank", "Trained persistent", "#333333", "o"),
                                  ("mwg_token_diag_core", "Token controller", "#176b92", "s"),
                                  ("mwg_shuffled_diag_core", "Shuffled controller", "#bd642b", "^")]:
    rows = [r for r in data["quality"]["rows"] if r["method"] == name]
    ax.errorbar([r["reconstructed_fp32_mib"] for r in rows], [r["mean"] for r in rows],
                yerr=[r["sample_sd"] for r in rows], label=label, color=color, marker=marker,
                linestyle="--", capsize=3, linewidth=1)
ax.set(xlabel="Reconstructed parameter storage (MiB; fp32, h=192)", ylabel="FFN relative MSE")
ax.legend(frameon=False, fontsize=8)
ax.grid(alpha=.15)
fig.tight_layout()
fig.savefig(out / "journal_quality.pdf")
plt.close(fig)
fig, ax = plt.subplots(figsize=(6.3, 2.8))
n = np.geomspace(1, 4096, 100)
for total, label in [(18432, "d=4096, m=14336"), (10496, "d=1536, m=8960")]:
    ax.plot(n, 1 + 2 * n / total, label=label)
ax.set_xscale("log", base=2)
ax.set(xlabel="Descriptor groups n (q=1 implies n=T)", ylabel="Cold-factor byte-ratio ceiling")
ax.legend(frameon=False, fontsize=8)
ax.grid(alpha=.15)
fig.tight_layout()
fig.savefig(out / "journal_bytes.pdf")
