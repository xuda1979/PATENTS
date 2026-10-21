#!/usr/bin/env python3
"""Deterministic quality-table generator for the ICLR 2027 paper.

Emits Tables 10-12 (causal quality, shuffled-context control, rank-512 control)
plus the Table 1 / results.tex summary numbers, exclusively from the single
coherent run family `asi2_rank512_control_20260922T080042Z`.

Guards against the registry indiscipline identified in the ICLR 2027 review:
  - refuses to mix rows from different run families;
  - refuses to emit if the record files do not match the SHA-256 hashes
    recorded in results/REGISTRY.md (unless --no-verify);
  - recomputes every mean/std from per-seed values (never trusts aggregate
    blocks that cannot be cross-checked against per-seed data);
  - writes the run ID into each emitted caption so the binding is visible.

Usage:
  python3 scripts/make_tables.py --check     # verify hashes only
  python3 scripts/make_tables.py             # emit paper/generated_tables/*.tex
  python3 scripts/make_tables.py --stdout    # also print key numbers
"""

import argparse
import hashlib
import json
import math
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FAMILY_DIR = os.path.join(REPO, "results", "asi2_rank512_control_20260922")
RECORD_PATH = os.path.join(FAMILY_DIR, "VERIFIED_RESULT_RECORD.json")
PERSEED_PATH = os.path.join(FAMILY_DIR, "per_seed_results.json")

# Binding from results/REGISTRY.md (2026-10-09). Update both files together.
EXPECTED = {
    RECORD_PATH: "1153803d14339009b65a1648733d126ff2178541f8591b42952cc1f4fb3764ea",
    PERSEED_PATH: "6283b14cb63697c5f56404ffe4afccf50882504d63ed43fda8020af62a611a5a",
}

RUN_ID = "asi2_rank512_control_20260922T080042Z"
RUN_ID_TEX = RUN_ID.replace("_", "\\_")  # for use inside \texttt{}
SEEDS = ["seed_2026", "seed_2027", "seed_2028", "seed_2029"]
RANKS = [384, 401, 512]

# fp32 persistent-factor storage: 3*r*(d+m)*4 bytes, d=1536 m=8960
D_MODEL, M_FFN = 1536, 8960

ARM_PERSISTENT = "persistent_low_rank_r{r}"
ARM_CAUSAL = "mwg_token_diag_core_r{r}"
ARM_SHUFFLED = "mwg_shuffled_diag_core_r{r}"
ARM_STATIC = "static_svd_r{r}"

OUT_DIR = os.path.join(REPO, "paper", "generated_tables")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_hashes():
    ok = True
    for path, expected in EXPECTED.items():
        if not os.path.exists(path):
            print(f"MISSING {path}", file=sys.stderr)
            ok = False
            continue
        actual = sha256_file(path)
        if actual != expected:
            print(f"HASH MISMATCH {path}\n  expected {expected}\n  actual   {actual}",
                  file=sys.stderr)
            ok = False
        else:
            print(f"ok  {os.path.relpath(path, REPO)}")
    return ok


def mean(xs):
    return sum(xs) / len(xs)


def sample_std(xs):
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def t_stat(diffs):
    m = mean(diffs)
    s = sample_std(diffs)
    if s == 0:
        return 0.0
    return m / (s / math.sqrt(len(diffs)))


def load_family():
    """Load per-seed values and recompute all aggregates from them."""
    with open(PERSEED_PATH) as f:
        per_seed = json.load(f)

    # cross-check the record's aggregated_results block against recompute
    with open(RECORD_PATH) as f:
        record = json.load(f)
    if record.get("run_id") != RUN_ID:
        raise SystemExit(f"record run_id {record.get('run_id')!r} != {RUN_ID!r}")

    recompute = {}
    for arm in per_seed[SEEDS[0]]:
        if arm == "dense_teacher":
            continue
        rel = [per_seed[s][arm]["relative_mse"] for s in SEEDS]
        cos = [per_seed[s][arm]["cosine"] for s in SEEDS]
        recompute[arm] = {
            "rel_mean": mean(rel), "rel_std": sample_std(rel),
            "cos_mean": mean(cos), "cos_std": sample_std(cos),
        }
    stored = record.get("aggregated_results", {})
    for arm, st in recompute.items():
        s = stored.get(arm)
        if s is None:
            raise SystemExit(f"arm {arm} missing from aggregated_results")
        for key, val in (("relative_mse_mean", st["rel_mean"]),
                         ("cosine_mean", st["cos_mean"])):
            if abs(s[key] - val) > 5e-4:
                raise SystemExit(
                    f"aggregate drift for {arm}.{key}: stored {s[key]} vs "
                    f"recomputed {val:.6f} (per-seed is authoritative)")
    return recompute, per_seed, record


def fmt_pm(m, s, digits=4):
    return f"${m:.{digits}f}\\pm{s:.{digits}f}$"


def mib(rank):
    return 3 * rank * (D_MODEL + M_FFN) * 4 / (1 << 20)


def paired(recompute, per_seed, arm_a, arm_b):
    d = [per_seed[s][arm_a]["relative_mse"] - per_seed[s][arm_b]["relative_mse"]
         for s in SEEDS]
    return mean(d), sample_std(d), t_stat(d), d


# ---------------------------------------------------------------- Table 10
def emit_table10(rec, per_seed):
    rows = []
    for r in RANKS:
        rows.append(("Static SVD", r, mib(r), rec[ARM_STATIC.format(r=r)], False))
        rows.append(("Persistent low rank", r, mib(r), rec[ARM_PERSISTENT.format(r=r)], False))
        rows.append(("\\emph{Generated diagonal core}", r, mib(r) + 2.0,
                     rec[ARM_CAUSAL.format(r=r)], True))
    lines = [
        "\\begin{table}[h]",
        "\\centering",
        "\\footnotesize",
        "\\caption{Causal multi-seed quality of the generated diagonal core vs.\\ controls",
        "on layer~16 of Qwen2.5-1.5B (fp32). Mean$\\pm$std (sample s.d.) over four",
        "disjoint seeds (2026--2029), 5000 steps each, disjoint hash-bound splits;",
        "relative-MSE and cosine against the dense teacher (dense: relative-MSE $0$,",
        "cosine $1$). All rows from the single run family",
        "\\texttt{" + RUN_ID_TEX + "}.}",
        "\\label{tab:causalquality-app}",
        "\\begin{tabular}{lcccc}",
        "\\toprule",
        "Method & Rank & Params MiB & Rel.\\ MSE & Cosine \\\\",
        "\\midrule",
    ]
    prev_rank = None
    for name, r, mb, st, emph in rows:
        if prev_rank is not None and r != prev_rank:
            lines.append("\\midrule")
        bold = lambda x: f"\\textbf{{{x}}}" if emph else x
        lines.append(
            f"{name} & {r} & {mb:.1f} & "
            f"{bold(fmt_pm(st['rel_mean'], st['rel_std']))} & "
            f"{bold(fmt_pm(st['cos_mean'], st['cos_std']))} \\\\")
        prev_rank = r
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- Table 11
def emit_table11(rec, per_seed):
    lines = [
        "\\begin{table}[h]",
        "\\centering",
        "\\footnotesize",
        "\\caption{Shuffled-context control (4 seeds, 5000 steps each), drawn from",
        "the same run family as Table~\\ref{tab:causalquality-app}",
        "(\\texttt{" + RUN_ID_TEX + "}). The shuffled generator sees a random token's",
        "context; the real projection uses the true $x$. Paired per-seed",
        "differences: causal$-$shuffled $= -0.00021$ (t(3)$=-12.31$) at r384,",
        "$-0.00020$ (t(3)$=-10.13$) at r401, $+0.00002$ (t(3)$=+2.50$, n.s.) at",
        "r512: the context-conditioning effect is $\\sim$0.05\\% of MSE at r384/r401",
        "and is not detectable at r512.}",
        "\\label{tab:shuffled}",
        "\\begin{tabular}{lcc}",
        "\\toprule",
        "Method & Rel.\\ MSE & Cosine \\\\",
        "\\midrule",
    ]
    for r in RANKS:
        lines.append(f"\\multicolumn{{3}}{{l}}{{\\emph{{Rank {r}}}}} \\\\")
        for label, arm, emph in (
                ("Persistent low rank", ARM_PERSISTENT, False),
                ("Shuffled diag core", ARM_SHUFFLED, False),
                ("Causal diag core", ARM_CAUSAL, True)):
            st = rec[arm.format(r=r)]
            f = fmt_pm(st["rel_mean"], st["rel_std"])
            c = fmt_pm(st["cos_mean"], st["cos_std"])
            if emph:
                f, c = f"\\textbf{{{f}}}", f"\\textbf{{{c}}}"
            nm = f"\\emph{{{label}}}" if emph else label
            lines.append(f"{nm} & {f} & {c} \\\\")
        if r != RANKS[-1]:
            lines.append("\\midrule")
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- Table 12
def emit_table12(rec, per_seed):
    # paired cross-rank numbers, all within-family
    _, _, t_cs, _ = paired(rec, per_seed, ARM_CAUSAL.format(r=512),
                           ARM_SHUFFLED.format(r=512))
    _, _, t_cp, _ = paired(rec, per_seed, ARM_CAUSAL.format(r=512),
                           ARM_PERSISTENT.format(r=512))
    d_cross = [per_seed[s]["persistent_low_rank_r512"]["relative_mse"]
               - per_seed[s]["mwg_token_diag_core_r384"]["relative_mse"]
               for s in SEEDS]
    cross_mean, cross_std, cross_t = mean(d_cross), sample_std(d_cross), t_stat(d_cross)
    cap_pct = cross_mean / rec["mwg_token_diag_core_r384"]["rel_mean"] * 100

    cp512_mean = mean([per_seed[s]['mwg_token_diag_core_r512']['relative_mse']
                       - per_seed[s]['persistent_low_rank_r512']['relative_mse']
                       for s in SEEDS])
    lines = [
        "\\begin{table}[h]",
        "\\centering",
        "\\footnotesize",
        "\\caption{Rank-512 control (4 seeds, identical protocol",
        "and run family as Table~\\ref{tab:shuffled}, \\texttt{" + RUN_ID_TEX + "}).",
        "At matched rank the causal core is marginally better than persistent",
        f"(paired causal$-$persistent $= {cp512_mean:.5f}$, t(3)$={t_cp:.2f}$;",
        "the difference is statistically resolvable but is well inside any",
        "practical non-inferiority margin). A persistent r512 factor beats the",
        f"causal r384 core by {abs(cap_pct):.1f}\\% relative MSE",
        f"(paired t(3)$={cross_t:.0f}$), so capacity dominates generation at",
        "this scale.}",
        "\\label{tab:rank512control}",
        "\\begin{tabular}{lcc}",
        "\\toprule",
        "Method (r512) & Rel.\\ MSE & Cosine \\\\",
        "\\midrule",
    ]
    for label, arm, emph in (
            ("Static SVD", ARM_STATIC, False),
            ("Persistent low rank", ARM_PERSISTENT, False),
            ("Shuffled diag core", ARM_SHUFFLED, False),
            ("Causal diag core", ARM_CAUSAL, True)):
        st = rec[arm.format(r=512)]
        f = fmt_pm(st["rel_mean"], st["rel_std"])
        c = fmt_pm(st["cos_mean"], st["cos_std"])
        if emph:
            f, c = f"\\textbf{{{f}}}", f"\\textbf{{{c}}}"
            label = f"\\emph{{{label}}}"
        lines.append(f"{label} & {f} & {c} \\\\")
    lines += [
        "\\midrule",
        "\\multicolumn{3}{l}{Cross-rank (not parameter-matched at equal MiB):} \\\\",
        "Persistent low rank r512 & "
        + fmt_pm(rec["persistent_low_rank_r512"]["rel_mean"],
                 rec["persistent_low_rank_r512"]["rel_std"]) + " & "
        + fmt_pm(rec["persistent_low_rank_r512"]["cos_mean"],
                 rec["persistent_low_rank_r512"]["cos_std"]) + " \\\\",
        "Causal diag core r384 & "
        + fmt_pm(rec["mwg_token_diag_core_r384"]["rel_mean"],
                 rec["mwg_token_diag_core_r384"]["rel_std"]) + " & "
        + fmt_pm(rec["mwg_token_diag_core_r384"]["cos_mean"],
                 rec["mwg_token_diag_core_r384"]["cos_std"]) + " \\\\",
        "\\bottomrule",
        "\\end{tabular}",
        "\\end{table}",
        "",
    ]
    return "\n".join(lines)


# ------------------------------------------------------- results.tex numbers
def emit_summary_numbers(rec, per_seed):
    """Key single-family numbers referenced by results.tex / abstract."""
    out = []
    cs384 = paired(rec, per_seed, ARM_CAUSAL.format(r=384), ARM_SHUFFLED.format(r=384))
    cs401 = paired(rec, per_seed, ARM_CAUSAL.format(r=401), ARM_SHUFFLED.format(r=401))
    cs512 = paired(rec, per_seed, ARM_CAUSAL.format(r=512), ARM_SHUFFLED.format(r=512))
    cp384 = paired(rec, per_seed, ARM_CAUSAL.format(r=384), ARM_PERSISTENT.format(r=384))
    out.append(f"% context-conditioning effect (causal - shuffled, rel-MSE):")
    out.append(f"%   r384: {cs384[0]:+.5f} (t(3)={cs384[2]:+.2f})")
    out.append(f"%   r401: {cs401[0]:+.5f} (t(3)={cs401[2]:+.2f})")
    out.append(f"%   r512: {cs512[0]:+.5f} (t(3)={cs512[2]:+.2f})")
    out.append(f"% same-rank causal - persistent r384: {cp384[0]:+.5f} (t(3)={cp384[2]:+.2f})")
    pb = rec["persistent_low_rank_r401"]["rel_mean"]
    cb = rec["mwg_token_diag_core_r384"]["rel_mean"]
    out.append(f"% equal-budget pair (persistent r401 48.2 MiB vs causal r384 48.1 MiB):")
    out.append(f"%   persistent r401 rel-MSE {pb:.4f}; causal r384 {cb:.4f};")
    out.append(f"%   generated arm worse by {(cb - pb) / pb * 100:+.2f}% relative")
    d_cross = [per_seed[s]["persistent_low_rank_r512"]["relative_mse"]
               - per_seed[s]["mwg_token_diag_core_r384"]["relative_mse"] for s in SEEDS]
    out.append(f"% capacity effect persistent r512 vs causal r384: {mean(d_cross):+.5f}"
               f" ({mean(d_cross) / cb * 100:+.1f}%), t(3)={t_stat(d_cross):.0f}")
    out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify hashes only")
    ap.add_argument("--no-verify", action="store_true", help="skip hash check")
    ap.add_argument("--stdout", action="store_true", help="print summary numbers")
    args = ap.parse_args()

    if args.check:
        sys.exit(0 if verify_hashes() else 1)
    if not args.no_verify and not verify_hashes():
        print("hash verification failed; refusing to emit (use --no-verify to override)",
              file=sys.stderr)
        sys.exit(1)

    rec, per_seed, record = load_family()

    os.makedirs(OUT_DIR, exist_ok=True)
    tables = {
        "table10_causalquality.tex": emit_table10(rec, per_seed),
        "table11_shuffled.tex": emit_table11(rec, per_seed),
        "table12_rank512control.tex": emit_table12(rec, per_seed),
        "summary_numbers.tex": emit_summary_numbers(rec, per_seed),
    }
    for name, content in tables.items():
        path = os.path.join(OUT_DIR, name)
        with open(path, "w") as f:
            f.write(f"% AUTO-GENERATED by scripts/make_tables.py -- DO NOT EDIT BY HAND\n")
            f.write(f"% Source: {RUN_ID} (results/asi2_rank512_control_20260922/)\n")
            f.write(content)
        print(f"wrote {os.path.relpath(path, REPO)}")
    if args.stdout:
        print()
        print(tables["summary_numbers.tex"])


if __name__ == "__main__":
    main()
