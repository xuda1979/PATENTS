#!/usr/bin/env python3
"""Synthetic algebra checks, not model-quality or hardware experiments."""
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def optimal_constant_core(a, z, v):
    """Fit a frozen projection's constant scale under output squared error."""
    gram = v @ v.T
    q = a[:, :, None] * gram[None, :, :] * a[:, None, :]
    h = q.mean(axis=0)
    b = np.einsum("nij,nj->i", q, z) / len(a)
    return np.linalg.pinv(h) @ b


def run():
    residual, decomposition, normal_eq, excess = [], [], [], []
    for seed in range(50):
        rng = np.random.default_rng(seed)
        a, z, v = rng.normal(size=(31, 3)), rng.normal(size=(31, 3)), rng.normal(size=(3, 8))
        y, target = (a * z) @ v, rng.normal(size=(31, 8))
        basis = np.linalg.svd(v, full_matrices=False)[2]
        p = basis.T @ basis
        residual.append(float(np.max(np.abs(y - y @ p))))
        lhs = np.linalg.norm(target - y)**2
        rhs = np.linalg.norm(target - target @ p)**2 + np.linalg.norm(target @ p - y)**2
        decomposition.append(float(abs(lhs - rhs) / max(1, lhs)))
        c = optimal_constant_core(a, z, v)
        design = np.stack([a[i, :, None] * v for i in range(len(a))]).transpose(0, 2, 1).reshape(-1, 3)
        reference = np.linalg.lstsq(design, y.ravel(), rcond=None)[0]
        normal_eq.append(float(np.max(np.abs(c - reference))))
        loss_c = np.linalg.norm(y - (a * c) @ v)**2
        loss_mean = np.linalg.norm(y - (a * z.mean(axis=0)) @ v)**2
        excess.append(float(loss_c - loss_mean))
    assert max(residual) < 1e-11
    assert max(decomposition) < 1e-12
    assert max(normal_eq) < 1e-11
    assert max(excess) <= 1e-9
    return {"evidence_class": "synthetic_float64_algebra_check", "seeds": list(range(50)),
            "numpy_version": np.__version__, "passed": True,
            "max_rowspace_residual": max(residual),
            "max_relative_orthogonal_decomposition_residual": max(decomposition),
            "max_constant_core_vs_independent_lstsq_error": max(normal_eq),
            "max_fit_loss_difference_vs_unweighted_mean": max(excess),
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "claim_boundary": "Numerical checks of identities only; no real-model quality, generalization, or runtime evidence."}


if __name__ == "__main__":
    result = run()
    output = ROOT / "results/journal_revision_20261022/analysis_checks.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result))
