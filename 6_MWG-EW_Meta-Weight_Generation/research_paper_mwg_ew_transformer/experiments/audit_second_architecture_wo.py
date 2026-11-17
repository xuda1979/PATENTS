#!/usr/bin/env python3
"""Second-architecture audit demonstration on synthetic CPU fixtures.

Executes the paper's audit machinery end to end on the pre-registered second
architecture: the causal self-attention output projection W_O with per-head
block-diagonal modulation of low-rank factors.  This closes the
"demonstrate the audit on a second architecture" requirement at the CPU
synthetic-fixture evidence level: it runs the same question set, controls,
and floors as the FFN study, on the same terms as the Appendix-B lifecycle
check (synthetic random fixtures, exact identities, no accelerator claim).

What is measured here (all on CPU, float64/float32, synthetic data):
  Q1  training-matched budget contrast: per-head conditioned modulation vs
      same-rank persistent low rank vs capacity-compensated persistent low
      rank (largest rank fitting the conditioned arm's parameter budget) vs
      static SVD; every trainable arm uses the same fixture, optimizer, and
      step count, so the contrast isolates conditioning rather than training
      exposure or capacity;
  error-budget attribution: actual error of each trained arm decomposed
      additively into rank loss / subspace selection / within-subspace fit
      per head (Eq. error-budget instantiated per head, additivity checked);
  constant-core control: the activation-weighted least-squares constant
      per head (Proposition constant) vs the learned per-token scales of the
      same trained artifact;
  Q3  checkpointing identity: ordinary autograd vs non-reentrant
      torch.utils.checkpoint on the same module gives identical outputs,
      losses, and gradients.

What is NOT measured here: any accelerator latency, any trained-model
quality, any HBM traffic, any serving claim.  No gate is promoted beyond
the CPU synthetic-fixture evidence class.

Synthetic random inputs and factors; no dataset and no checkpoint from any
prior run is used.  Uses only the standard library and torch on CPU.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]

ATOL = 0.0

SEEDS = (2026, 2027, 2028)
D_MODEL = 64
HEADS = 4
HEAD_DIM = 16
RANK_PER_HEAD = 4
BATCH = 2
SEQ = 16
ALPHA = 0.2


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PerHeadController(torch.nn.Module):
    """Per-head dispatch wrapper around one controller MLP per head."""

    def __init__(self, heads: int, head_dim: int, rank: int, alpha: float):
        super().__init__()
        self.heads = heads
        self.nets = torch.nn.ModuleList(
            [make_head_controller(head_dim, rank, alpha) for _ in range(heads)])

    def forward(self, head_idx: int, x_h: torch.Tensor) -> torch.Tensor:
        return self.nets[head_idx](x_h)


class PerHeadLowRankAttentionOut(torch.nn.Module):
    """W_O as per-head low-rank factors with optional per-head modulation.

    y = concat(h_1, ..., h_H) W_O^T with W_O block-diagonal per head:
    y_head = (x_head U_h) V_h, rank r per head.  The conditioned variant
    multiplies the rank activations of head h by a per-token, per-rank
    diagonal scale z(x)_{h,:} emitted by a small controller, exactly the
    paper's Eq. (projection) instantiated per head.  The persistent variant
    is z = 1 (no modulation).
    """

    def __init__(self, factors, controller: PerHeadController, heads: int,
                 rank: int, conditioned: bool, dtype: torch.dtype):
        super().__init__()
        self.factors = torch.nn.ParameterList(
            # Clone so optimizer updates cannot mutate the caller's fixture
            # tensors (nn.Parameter shares storage with its source tensor).
            [torch.nn.Parameter(f.detach().clone()) for f in factors])
        self.controller = controller
        self.heads = heads
        self.rank = rank
        self.conditioned = conditioned

    def head_scales(self, head_idx: int, x_h: torch.Tensor) -> torch.Tensor:
        if not self.conditioned:
            return torch.ones(*x_h.shape[:-1], self.rank,
                              dtype=x_h.dtype, device=x_h.device)
        return self.controller(head_idx, x_h)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, S, D) already attention-mixed per head.
        head_outs = []
        for h in range(self.heads):
            sl = slice(h * (x.shape[-1] // self.heads),
                       (h + 1) * (x.shape[-1] // self.heads))
            x_h = x[..., sl]
            a = x_h @ self.factors[2 * h]
            z = self.head_scales(h, x_h)  # (B, S, r)
            a = a * z
            head_outs.append(a @ self.factors[2 * h + 1])
        return torch.cat(head_outs, dim=-1)


def make_head_controller(head_dim: int, rank: int, alpha: float):
    """Small MLP head emitting bounded per-rank scales for one head."""

    class HeadController(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.net = torch.nn.Sequential(
                torch.nn.Linear(head_dim, 16, dtype=torch.float64),
                torch.nn.SiLU(),
                torch.nn.Linear(16, rank, dtype=torch.float64))

        def forward(self, x_h: torch.Tensor) -> torch.Tensor:
            return 1.0 + alpha * torch.tanh(self.net(x_h))

    return HeadController()


def svd_truncate(w_block: torch.Tensor, rank: int):
    """Rank-truncated SVD factors (u_r, s_r v_r) of one dense block."""
    u, s, vh = torch.linalg.svd(w_block, full_matrices=False)
    return (u[:, :rank].clone(),
            (torch.diag(s[:rank]) @ vh[:rank, :]).clone())


def make_fixture(seed: int):
    """Synthetic per-head attention-out fixture and dense target W_O.

    Returns (factors, w_blocks, x, y_dense): per-head rank-r SVD factors of
    the dense blocks, the dense blocks themselves, the input states, and the
    dense reference output.
    """
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        d, hd, H, r = D_MODEL, HEAD_DIM, HEADS, RANK_PER_HEAD
        dt = torch.float64
        # Dense per-head W_O blocks.
        w_blocks = [torch.randn(hd, hd, dtype=dt) / math.sqrt(hd)
                    for _ in range(H)]
        factors = []
        for h in range(H):
            u_r, v_r = svd_truncate(w_blocks[h], r)
            factors.append(u_r)
            factors.append(v_r)
        x = torch.randn(BATCH, SEQ, d, dtype=dt)
        # Dense reference output.
        y_dense = torch.cat(
            [x[..., h * hd:(h + 1) * hd] @ w_blocks[h] for h in range(H)],
            dim=-1)
        return factors, w_blocks, x, y_dense


def head_error_budget(y_h: torch.Tensor, y_hat_h: torch.Tensor,
                      u_h: torch.Tensor, v_h: torch.Tensor, rank: int):
    """Per-head additive relative-error budget (Eq. error-budget).

    y_h: (B, S, hd) target outputs for this head.
    y_hat_h: (B, S, hd) model outputs for this head.
    u_h: (hd, r) fixed left factor; v_h: (r, hd) fixed right factor.

    actual = rank loss (any rank-r model) + subspace selection
             + within-subspace fit, all relative to ||Y||_F^2, where S is the
    row space of v_h and P_S projects onto it. Every term is computed from
    the actual model output, never assumed to hit its floor.
    """
    vh = v_h.double()
    y = y_h.double().reshape(-1, y_h.shape[-1])
    y_hat = y_hat_h.double().reshape(-1, y_hat_h.shape[-1])
    denom = float((y ** 2).sum())
    # Orthogonal projector onto the column span of v_h^T (row space of v_h).
    P = vh.T @ torch.linalg.pinv(vh @ vh.T) @ vh  # hd x hd
    # Theorem premise: every model output row lies in the row space of v_h.
    if float(((y_hat - y_hat @ P) ** 2).sum()) > 1e-12 * max(
            1.0, float((y_hat ** 2).sum())):
        raise ValueError("model output leaves the final factor's row space")
    s = torch.linalg.svdvals(y)
    rank_loss = float((s[rank:] ** 2).sum()) / denom
    subspace_floor = float(((y - y @ P) ** 2).sum()) / denom
    actual = float(((y - y_hat) ** 2).sum()) / denom
    within = float(((y @ P - y_hat) ** 2).sum()) / denom
    subspace_selection = subspace_floor - rank_loss
    if abs(actual - (rank_loss + subspace_selection + within)) > 1e-9:
        raise ValueError("per-head error budget is not additive")
    return {"actual_rel": actual,
            "rank_loss_rel": rank_loss,
            "subspace_selection_rel": subspace_selection,
            "within_subspace_fit_rel": within,
            "subspace_floor_rel": subspace_floor}


def train_module(model: torch.nn.Module, x: torch.Tensor, y_dense: torch.Tensor,
                 steps: int = 400, lr: float = 1e-2) -> None:
    """Same optimizer, step count, and loss for every trainable arm (Q1)."""
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    for _ in range(steps):
        opt.zero_grad()
        loss = ((model(x) - y_dense) ** 2).mean()
        loss.backward()
        opt.step()


def measure_q1_contrast(seed: int):
    """Q1: matched-budget contrast, conditioned vs persistent vs static SVD.

    Arms (all trained on the same fixture with the same optimizer schedule):
    - persistent rank r per head (z = 1), trained;
    - conditioned rank r per head with per-head token-conditioned scales,
      trained;
    - capacity-compensated persistent rank r_c per head, where r_c is the
      largest rank whose per-head parameter count is no greater than the
      conditioned arm's (persistent rank r + controller), trained;
    - static SVD control: best rank-(H*r) truncation of the least-squares
      linear map fitting the dense target (untrained).
    Per-head error budgets (Eq. error-budget) are attributed for every
    trained arm term by term.
    """
    factors, w_blocks, x, y_dense = make_fixture(seed)
    H, hd, r = HEADS, HEAD_DIM, RANK_PER_HEAD

    def module(conditioned: bool, rank: int, per_head_factors):
        ctrl = (PerHeadController(H, hd, r, ALPHA)
                if conditioned else None)
        return PerHeadLowRankAttentionOut(per_head_factors, ctrl, H, rank,
                                          conditioned, torch.float64)

    # ---- persistent rank r (same factors as the fixture), trained ----
    model_p = module(False, r, factors)
    train_module(model_p, x, y_dense)
    with torch.no_grad():
        y_p = model_p(x)
    mse_p = float(((y_p - y_dense) ** 2).sum() / (y_dense ** 2).sum())

    # ---- conditioned rank r, trained ----
    model_c = module(True, r, factors)
    train_module(model_c, x, y_dense)
    with torch.no_grad():
        y_c = model_c(x)
    mse_c = float(((y_c - y_dense) ** 2).sum() / (y_dense ** 2).sum())

    # ---- capacity-compensated persistent rank r_c ----
    # Largest per-head rank whose persistent parameter count does not exceed
    # the trained conditioned arm's actual parameter count (measured from the
    # built modules, not from a hand-derived formula).
    cond_params = sum(t.numel() for t in model_c.parameters())

    def persistent_params(rank: int) -> int:
        return 2 * hd * rank * H

    r_c = r
    while (r_c + 1 <= hd and persistent_params(r_c + 1) <= cond_params):
        r_c += 1
    if persistent_params(r_c) > cond_params:
        raise ValueError("capacity compensation exceeds the conditioned budget")
    factors_c = []
    for h in range(H):
        u_r, v_r = svd_truncate(w_blocks[h], r_c)
        factors_c.append(u_r)
        factors_c.append(v_r)
    model_pc = module(False, r_c, factors_c)
    train_module(model_pc, x, y_dense)
    with torch.no_grad():
        y_pc = model_pc(x)
    mse_pc = float(((y_pc - y_dense) ** 2).sum() / (y_dense ** 2).sum())

    # ---- static SVD control (untrained) ----
    y_flat = y_dense.reshape(-1, D_MODEL).double()
    x_flat = x.reshape(-1, D_MODEL).double()
    w_ls = torch.linalg.lstsq(x_flat, y_flat).solution
    u, s, vh = torch.linalg.svd(w_ls, full_matrices=False)
    r_tot = H * r
    w_svd = u[:, :r_tot] @ torch.diag(s[:r_tot]) @ vh[:r_tot, :]
    y_svd = x_flat @ w_svd
    mse_svd = float(((y_svd - y_flat) ** 2).sum() / (y_flat ** 2).sum())

    # ---- per-head error budgets for every trained arm ----
    def budgets_for(y_hat, model, rank):
        rows = []
        for h in range(H):
            sl = slice(h * hd, (h + 1) * hd)
            rows.append(head_error_budget(
                y_dense[..., sl], y_hat[..., sl],
                model.factors[2 * h].detach().double(),
                model.factors[2 * h + 1].detach().double(), rank))
        return rows

    def param_count(model):
        return sum(t.numel() for t in model.parameters())

    return {"seed": seed,
            "persistent_rel_mse": mse_p,
            "conditioned_rel_mse": mse_c,
            "persistent_compensated_rel_mse": mse_pc,
            "static_svd_rel_mse": mse_svd,
            "conditioned_minus_persistent": mse_c - mse_p,
            "persistent_rank": r,
            "persistent_compensated_rank": r_c,
            "persistent_parameter_count": param_count(model_p),
            "conditioned_parameter_count": param_count(model_c),
            "persistent_compensated_parameter_count": param_count(model_pc),
            "head_error_budgets_conditioned": budgets_for(y_c, model_c, r),
            "head_error_budgets_persistent": budgets_for(y_p, model_p, r),
            "head_error_budgets_persistent_compensated":
                budgets_for(y_pc, model_pc, r_c)}


def measure_constant_core_control(seed: int):
    """Constant-core control per head (Proposition constant, CPU form).

    Fits the activation-weighted least-squares constant scale c* per head on
    the fixture activations and compares against the learned per-token
    scales of the fitted conditioned model.
    """
    factors, w_blocks, x, y_dense = make_fixture(seed)
    H, hd, r = HEADS, HEAD_DIM, RANK_PER_HEAD
    model = PerHeadLowRankAttentionOut(
        factors, PerHeadController(H, hd, r, ALPHA),
        H, r, True, torch.float64)
    train_module(model, x, y_dense)
    with torch.no_grad():
        y_cond = model(x)
    mse_cond = float(((y_cond - y_dense) ** 2).sum() / (y_dense ** 2).sum())

    # Per-head constant c* = argmin E||(a*(z(x)-c))V||^2 -> H c = b with
    # H = E[Q], b = E[Q z], Q = diag(a) V V^T diag(a) (Proposition constant).
    # The trained artifact is kept fixed: trained factors and trained
    # controller; only the dynamic scales are replaced by the best constant.
    per_head = []
    with torch.no_grad():
        for h in range(H):
            x_h = x[..., h * hd:(h + 1) * hd]
            u_h = model.factors[2 * h].detach().double()
            v_h = model.factors[2 * h + 1].detach().double()
            a = (x_h @ u_h).reshape(-1, r).double()
            z = model.head_scales(h, x_h).reshape(-1, r).double()
            V = v_h  # r x hd
            # Q_i = diag(a_i) V V^T diag(a_i); accumulate H_mat, b_vec.
            VVt = V @ V.T
            Q = a.unsqueeze(2) * VVt.unsqueeze(0) * a.unsqueeze(1)  # (N, r, r)
            H_mat = Q.mean(dim=0)
            b_vec = (Q * z.unsqueeze(1)).sum(dim=2).mean(dim=0)  # E[Q z]
            c_star = torch.linalg.solve(
                H_mat + 1e-12 * torch.eye(r, dtype=H_mat.dtype),
                b_vec).detach()
            # Constant-core output for this head.
            y_const = (a * c_star.unsqueeze(0)) @ V
            y_target = y_dense[..., h * hd:(h + 1) * hd].reshape(-1, hd).double()
            per_head.append({
                "c_star": [float(v) for v in c_star],
                "constant_core_rel_mse": float(
                    ((y_const - y_target) ** 2).sum() / (y_target ** 2).sum()),
            })
    # Aggregate constant-core output on the trained factors.
    with torch.no_grad():
        head_outs = []
        for h in range(H):
            x_h = x[..., h * hd:(h + 1) * hd]
            a = (x_h @ model.factors[2 * h]).double()
            c = torch.tensor(per_head[h]["c_star"], dtype=torch.float64)
            head_outs.append((a * c) @ model.factors[2 * h + 1].double())
        y_cc = torch.cat(head_outs, dim=-1)
    mse_cc = float(((y_cc - y_dense) ** 2).sum() / (y_dense ** 2).sum())
    return {"seed": seed,
            "conditioned_rel_mse": mse_cond,
            "constant_core_rel_mse": mse_cc,
            "constant_minus_conditioned": mse_cc - mse_cond,
            "per_head": per_head}


def measure_q3_checkpointing(seed: int):
    """Q3: checkpointing identity on the per-head module."""
    factors, w_blocks, x, y_dense = make_fixture(seed)
    H, hd, r = HEADS, HEAD_DIM, RANK_PER_HEAD

    def build():
        return PerHeadLowRankAttentionOut(
            [f.detach().clone() for f in factors],
            PerHeadController(H, hd, r, ALPHA),
            H, r, True, torch.float64)

    def build_from_state(state):
        model = build()
        model.load_state_dict(state)
        return model

    # Snapshot one initial state so both arms start identically.
    init_state = {k: v.detach().clone() for k, v in build().state_dict().items()}

    def run(checkpointed: bool):
        model = build_from_state(init_state)
        target = y_dense
        y = (torch.utils.checkpoint.checkpoint(model, x, use_reentrant=False)
             if checkpointed else model(x))
        loss = ((y - target) ** 2).mean()
        loss.backward()
        grads = {n: p.grad.detach().clone() for n, p in
                 model.named_parameters()}
        return float(loss.detach()), y.detach().clone(), grads

    loss_e, y_e, g_e = run(False)
    loss_c, y_c, g_c = run(True)
    max_out = float((y_e - y_c).abs().max())
    max_grad = max((float((g_e[k] - g_c[k]).abs().max())
                    for k in g_e), default=0.0)
    ok = (max_out <= ATOL and max_grad <= ATOL and
          abs(loss_e - loss_c) <= ATOL)
    return {"seed": seed, "eager_loss": loss_e, "checkpoint_loss": loss_c,
            "max_output_abs_delta": max_out,
            "max_gradient_abs_delta": max_grad, "passed": ok}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    started = time.perf_counter()
    q1 = [measure_q1_contrast(s) for s in SEEDS]
    cc = [measure_constant_core_control(s) for s in SEEDS]
    q3 = [measure_q3_checkpointing(s) for s in SEEDS]
    status = ("PASS" if all(row["passed"] for row in q3) else "FAIL")
    report = {
        "schema": "mwg-second-architecture-wo-audit-v2",
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_script_sha256": sha256_file(Path(__file__).resolve()),
        "evidence_kind": "cpu_synthetic_fixture_audit_demonstration",
        "architecture": ("causal self-attention output projection W_O with "
                         "per-head block-diagonal low-rank factors and "
                         "per-head token-conditioned diagonal modulation"),
        "pre_registered_in": ("manuscript limitations, 'Pre-registered "
                              "instantiation on a second architecture'"),
        "runtime": {"python": sys.version, "torch": torch.__version__,
                    "device": "cpu", "platform": platform.platform(),
                    "threads": torch.get_num_threads(), "dtype": "float64"},
        "fixture": {"d_model": D_MODEL, "heads": HEADS, "head_dim": HEAD_DIM,
                    "rank_per_head": RANK_PER_HEAD, "batch": BATCH,
                    "seq": SEQ, "alpha": ALPHA, "seeds": list(SEEDS)},
        "q1_matched_contrast": q1,
        "constant_core_control": cc,
        "q3_checkpointing_identity": q3,
        "claim_boundary": {
            "evidence_class": "CPU synthetic fixture; no accelerator, no "
                              "trained model, no dataset, no serving claim",
            "not_measured": ["accelerator latency", "HBM traffic",
                             "trained-model quality", "perplexity"],
        },
        "elapsed_seconds": time.perf_counter() - started,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({
        "status": status,
        "q1_rows": len(q1), "constant_core_rows": len(cc), "q3_rows": len(q3),
        "max_output_delta": max(r["max_output_abs_delta"] for r in q3),
        "max_gradient_delta": max(r["max_gradient_abs_delta"] for r in q3),
        "output": str(args.output)}))


if __name__ == "__main__":
    main()
