"""Evaluate Theorem 1 floors + Proposition 1 constant-core on regenerated checkpoints.

Runs on ASI2 CPU using the 2026-11-10 regeneration artifacts:
  * results/asi2_causal_quality_closing_20261110T155855Z/cache/mwg_valid_activations_eval_*.pt
  * results/asi2_causal_quality_closing_20261110T155855Z/cache/mwg_teacher_factors_*.pt
  * results/asi2_causal_quality_closing_20261110T155855Z/seed_{2026..2029}/checkpoints/*.pt

Computation (fp32 inputs, fp64 accumulation):
  (a) singular-value tail floor  sum_{j>r} sigma_j(Y)^2 / ||Y||_F^2  (Eckart-Young-Mirsky)
      for r in {384, 401, 512} on the teacher's dense FFN outputs Y over eval
      activations.
  (b) fixed-V_d subspace floor  ||Y(I-P_S)||_F^2 / ||Y||_F^2  for each trained
      student's final factor V_d (row-space projector of the down projection).
  (c) Proposition 1 activation-weighted constant-core baseline: per projection,
      fit c* = H^+ b with H = E[diag(a) V V^T diag(a)]  and  b = E[diag(a) V V^T
      diag(a) z(x)] over train-split calibration activations, then evaluate a
      full FFN with those frozen constants on eval-split activations. A plain
      mean-core baseline (c = mean_t z(x_t), fitted on train) is included as a
      reference.

No new training, no accelerator execution. Outputs one manifest-hashed JSON plus
ready-to-embed LaTeX rows for the bridging table between Sections 4 and 7.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from mwg_quality_distillation import LowRankFFN
except ModuleNotFoundError:
    # Remote staging may place this script in /tmp without the module beside it.
    sys.path.insert(0, "/vllm-workspace/mwg-ew-transformer-research/experiments")
    from mwg_quality_distillation import LowRankFFN

RANKS = [384, 401, 512]
SEEDS = [2026, 2027, 2028, 2029]
# name -> (generator mode, rank)
STUDENTS: dict[str, tuple[str, int]] = {
    "mwg_token_diag_core_r384": ("token_diag_core", 384),
    "mwg_token_diag_core_r401": ("token_diag_core", 401),
    "persistent_low_rank_r384": ("none", 384),
    "persistent_low_rank_r401": ("none", 401),
    "persistent_low_rank_r512": ("none", 512),
}

ROOT = Path("/vllm-workspace/mwg-ew-transformer-research/results/asi2_causal_quality_closing_20261110T155855Z")


@dataclass
class RankTailFloor:
    rank: int
    tail_energy_relmse: float


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def load_activations(split: str) -> torch.Tensor:
    caches = sorted((ROOT / "cache").glob(f"mwg_valid_activations_{split}_*.pt"))
    if not caches:
        raise FileNotFoundError(f"no {split} activation cache")
    payload = torch.load(caches[0], map_location="cpu", weights_only=False)
    return payload["activations"].float()


def load_teacher() -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    tf = sorted((ROOT / "cache").glob("mwg_teacher_factors_*.pt"))
    payload = torch.load(tf[0], map_location="cpu", weights_only=False)
    return payload["gate"].float(), payload["up"].float(), payload["down"].float()


def svd_factors(weight: torch.Tensor, rank: int) -> tuple[torch.Tensor, torch.Tensor]:
    u, s, vh = torch.linalg.svd(weight.float(), full_matrices=False)
    root = torch.sqrt(s[:rank])
    left = u[:, :rank] * root.view(1, -1)
    right = root.view(-1, 1) * vh[:rank, :]
    return left, right


def make_model(
    init: dict[str, Any],
    factors: dict[str, tuple[torch.Tensor, torch.Tensor]],
) -> LowRankFFN:
    return LowRankFFN(
        factors=factors,
        dtype=torch.float32,
        generator=init["generator_mode"],
        generator_hidden=init.get("generator_hidden"),
        residual_rank=init.get("residual_rank", 8),
        scale_amplitude=init.get("scale_amplitude", 0.05),
        basis_count=init.get("basis_count", 1),
    )


def load_checkpoint_model(
    seed_dir: Path,
    name: str,
    factors: dict[str, tuple[torch.Tensor, torch.Tensor]],
) -> tuple[LowRankFFN, dict[str, Any]]:
    ckpt_path = seed_dir / "checkpoints" / f"{name}.pt"
    payload = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    init = payload.get("init", {})
    model = make_model(init, factors)
    expected = set(model.state_dict().keys())
    provided = {k: v for k, v in payload["state_dict"].items() if k in expected}
    missing = expected - set(provided)
    if missing:
        raise RuntimeError(f"{name}: state_dict missing keys {sorted(missing)}")
    model.load_state_dict(provided)
    model.eval()
    return model, payload


def teacher_ffn(gate, up, down, x) -> torch.Tensor:
    return (torch.nn.functional.silu(x @ gate) * (x @ up)) @ down


@torch.no_grad()
def model_ffn(model: LowRankFFN, x: torch.Tensor) -> torch.Tensor:
    return model(x)


def calibrated_constant_cores(
    model: LowRankFFN,
    x_cal: torch.Tensor,
    z_genfn,
) -> dict[str, torch.Tensor]:
    """Fit c* = H^+ b per projection (Proposition 1) with vectorized moments.

    The three projections are fitted sequentially because the down-projection
    input is the gated hidden state produced by the (up, gate) projections:
    c_up + c_gate are fitted on x_cal, the constant-core hidden state is
    formed, and c_down is fitted on that hidden state.
    """
    def fit(avals: torch.Tensor, v: torch.Tensor, z: torch.Tensor) -> torch.Tensor:
        a = avals.float()  # (N, r)
        z = z.float()  # (N, r)
        vvt = v.float() @ v.float().T  # (r, r)
        # Q_t = diag(a_t) V V^T diag(a_t) = (a_t a_t^T) * V V^T.
        # H[k,j] = (1/N) sum_t a_t[k] a_t[j] * vvt[k,j] = ((a^T a)/N) * vvt
        H = (a.T @ a) * vvt / a.shape[0]
        # b[k] = E_t[ a_t[k] (vvt @ (a_t * z_t))[k] ]
        w = vvt @ (a * z).T  # (r, N)
        b = (a * w.T).mean(0)
        # PSD solve via eigh with truncated near-zero eigvals.
        vals, vecs = torch.linalg.eigh(H)
        vals = torch.where(vals > vals.max() * 1e-10, vals, torch.zeros_like(vals))
        return (vecs * (vals.reciprocal().unsqueeze(0))) @ (vecs.T @ b)

    n = x_cal.shape[0]
    one = torch.ones(model.rank, dtype=torch.float32)
    if model.generator_mode == "none":
        # No controller: constant scale is already absorbable into U.
        return {"up": one, "gate": one, "down": one}
    z_up, z_gate, z_down = z_genfn(x_cal)
    cores: dict[str, torch.Tensor] = {}
    cores["up"] = fit(x_cal @ model.up_u, model.up_v, z_up)
    cores["gate"] = fit(x_cal @ model.gate_u, model.gate_v, z_gate)
    # Form the calibrated hidden state (frozen up/gate cores), then fit down.
    up = ((x_cal @ model.up_u) * cores["up"].unsqueeze(0)) @ model.up_v
    gate = ((x_cal @ model.gate_u) * cores["gate"].unsqueeze(0)) @ model.gate_v
    hidden = torch.nn.functional.silu(gate) * up
    cores["down"] = fit(hidden @ model.down_u, model.down_v, z_down)
    return cores


def constant_core_ffn(
    model: LowRankFFN,
    x: torch.Tensor,
    cores: dict[str, torch.Tensor],
) -> torch.Tensor:
    cu, cg, cd = cores["up"], cores["gate"], cores["down"]
    up = ((x @ model.up_u) * cu.unsqueeze(0)) @ model.up_v
    gate = ((x @ model.gate_u) * cg.unsqueeze(0)) @ model.gate_v
    hidden = torch.nn.functional.silu(gate) * up
    out = ((hidden @ model.down_u) * cd.unsqueeze(0)) @ model.down_v
    return out


def mean_core_ffn(model: LowRankFFN, x_cal: torch.Tensor, x_eval: torch.Tensor) -> torch.Tensor:
    if model.generator_mode == "none":
        return model(x_eval)
    z_up, z_gate, z_down = model._token_diag_cores(x_cal)
    cores = {
        "up": z_up.float().mean(dim=0),
        "gate": z_gate.float().mean(dim=0),
        "down": z_down.float().mean(dim=0),
    }
    return constant_core_ffn(model, x_eval, cores)


def relative_mse(pred: torch.Tensor, target: torch.Tensor) -> float:
    denom = target.square().sum()
    return float(((pred - target).square().sum() / denom).item())


def subspace_floor_relmse(y: torch.Tensor, v_d: torch.Tensor) -> float:
    """||Y(I - P_S)||_F^2 / ||Y||_F^2 with S = rowspace(V_d).

    Computed in factorized form (Y - (Y Q) Q^T) with Q an orthonormal basis
    of S^T, so no (m, m) projector is ever materialized.
    """
    vs = v_d.float()  # (r, d); S = rowspace(V_d) is a subspace of the OUTPUT R^d
    basis, _ = torch.linalg.qr(vs.T)  # (d, r) orthonormal columns spanning S^T
    off = y - (y @ basis) @ basis.T
    return float((off.square().sum() / y.square().sum()).item())


def compute_tail_floors(y: torch.Tensor) -> list[RankTailFloor]:
    s = torch.linalg.svdvals(y.float())
    total = torch.sum(s.square())
    out = []
    for r in RANKS:
        tail = torch.sum(s[r:].square())
        out.append(RankTailFloor(rank=r, tail_energy_relmse=float((tail / total).item())))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-json", default="/tmp/floor_constant_results.json")
    ap.add_argument("--out-tex", default="/tmp/floor_constant_rows.tex")
    ap.add_argument("--seeds", default="2026")
    ap.add_argument("--max-eval-rows", type=int, default=0,
                    help="cap eval tokens (0 = use all 34301)")
    ap.add_argument("--write-tex", action="store_true")
    args = ap.parse_args()

    seeds = [int(s) for s in args.seeds.split(",")]
    x_eval_raw = load_activations("eval")
    total = x_eval_raw.shape[0]
    if args.max_eval_rows and args.max_eval_rows < total:
        torch.manual_seed(1729)
        perm = torch.randperm(total)
        x_eval = x_eval_raw[perm[: args.max_eval_rows]]
    else:
        x_eval = x_eval_raw
    x_cal = load_activations("train")
    print(json.dumps({"event": "loaded",
                      "eval_tokens": int(x_eval.shape[0]),
                      "cal_tokens": int(x_cal.shape[0]),
                      "d": int(x_eval.shape[1])}), flush=True)

    gate, up, down = load_teacher()
    y = teacher_ffn(gate, up, down, x_eval)

    tail_floors = compute_tail_floors(y)

    factors_by_rank: dict[int, dict[str, tuple[torch.Tensor, torch.Tensor]]] = {}
    for r in RANKS:
        factors_by_rank[r] = {
            "up": svd_factors(up, r),
            "gate": svd_factors(gate, r),
            "down": svd_factors(down, r),
        }

    rows: list[dict[str, Any]] = []
    for seed in seeds:
        seed_dir = ROOT / f"seed_{seed}"
        for name, (mode, rank) in STUDENTS.items():
            model, payload = load_checkpoint_model(seed_dir, name, factors_by_rank[rank])
            pred = model_ffn(model, x_eval)
            token_relmse = relative_mse(pred, y)

            v_d = getattr(model, "down_v")
            sub_relmse = subspace_floor_relmse(y, v_d)
            rank_tail = next(t for t in tail_floors if t.rank == rank).tail_energy_relmse

            if mode == "none":
                cc_relmse = token_relmse  # no controller: same fixed model
                mc_relmse = token_relmse
                gap = None
            else:
                cores = calibrated_constant_cores(model, x_cal, model._token_diag_cores)
                cc_out = constant_core_ffn(model, x_eval, cores)
                mc_out = mean_core_ffn(model, x_cal, x_eval)
                cc_relmse = relative_mse(cc_out, y)
                mc_relmse = relative_mse(mc_out, y)
                gap = token_relmse - cc_relmse

            rows.append(
                {
                    "seed": seed,
                    "name": name,
                    "rank": rank,
                    "token_relmse": token_relmse,
                    "constant_core_relmse": cc_relmse,
                    "mean_core_relmse": mc_relmse,
                    "subspace_relmse": sub_relmse,
                    "rank_tail_relmse": rank_tail,
                    "token_minus_constant_core": gap,
                    "model_digest": sha256_file(seed_dir / "checkpoints" / f"{name}.pt"),
                }
            )
            print(json.dumps({"event": "done", **rows[-1]}, default=str), flush=True)

    report = {
        "kind": "floor_and_constant_core_eval_v1",
        "max_eval_rows": args.max_eval_rows,
        "eval_valid_tokens_total": total,
        "eval_valid_tokens_used": int(x_eval.shape[0]),
        "calibration_split": "train",
        "calibration_tokens_used": int(x_cal.shape[0]),
        "seeds": seeds,
        "tail_floors": [asdict(t) for t in tail_floors],
        "rows": rows,
        "target_energy_sq": float((y.square().sum()).item()),
        "source_hashes": {
            "eval_cache": sha256_file(sorted((ROOT / "cache").glob("mwg_valid_activations_eval_*.pt"))[0]),
            "train_cache": sha256_file(sorted((ROOT / "cache").glob("mwg_valid_activations_train_*.pt"))[0]),
            "teacher_factors": sha256_file(sorted((ROOT / "cache").glob("mwg_teacher_factors_*.pt"))[0]),
        },
        "report_hash": None,
    }
    report["report_hash"] = canonical_sha256(
        {k: v for k, v in report.items() if k != "report_hash"}
    )
    out_path = Path(args.out_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    if args.write_tex:
        write_tex_rows(report, args.out_tex)

    print(json.dumps({"event": "complete", "out": str(out_path), "report_hash": report["report_hash"]}), flush=True)


def write_tex_rows(report: dict[str, Any], out_tex: str) -> None:
    grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in report["rows"]:
        g = grouped[row["name"]]
        for key in ("token_relmse", "constant_core_relmse", "mean_core_relmse",
                    "subspace_relmse", "rank_tail_relmse"):
            if row.get(key) is not None:
                g[key].append(row[key])

    def fmt(vals: list[float]) -> str:
        return f"{statistics.mean(vals):.6f}"

    lines = [
        r"\begin{tabular}{lrrrrr}",
        r"\toprule",
        r"Model & Token ctl. & Const.-core & Mean-core & Subspace & Rank tail \\",
        r"\midrule",
    ]
    order = [
        "mwg_token_diag_core_r384", "mwg_token_diag_core_r401",
        "persistent_low_rank_r384", "persistent_low_rank_r401",
        "persistent_low_rank_r512",
    ]
    for name in order:
        g = grouped.get(name)
        if not g or "token_relmse" not in g:
            continue
        lines.append(
            rf"{name} & {fmt(g['token_relmse'])} & {fmt(g.get('constant_core_relmse', []))}"
            rf" & {fmt(g.get('mean_core_relmse', []))}"
            rf" & {fmt(g['subspace_relmse'])} & {fmt(g['rank_tail_relmse'])} \\"
        )
    lines += [r"\bottomrule", r"\end{tabular}"]
    Path(out_tex).parent.mkdir(parents=True, exist_ok=True)
    Path(out_tex).write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
