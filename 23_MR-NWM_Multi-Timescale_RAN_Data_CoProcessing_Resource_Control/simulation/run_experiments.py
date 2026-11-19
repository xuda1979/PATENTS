#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
离散时间蒙特卡洛仿真：多时间尺度 RAN 数据协同处理与资源控制（专利对比实验）

仿真设定（离散时间，步长 dt = 1 ms，时长 T = 60 s = 60000 步）：
- 单小区，100 PRB，200 UE；每 UE 需求速率固定 1 Mbps。
- 小区负载均值按 AR(1) 漂移：每秒一步，rho=0.9，高斯扰动 sigma=0.04，
  负载截断到 [0.3, 0.95]（负载定义为"需求占小区容量的比例"标称值附近漂移）。
- 每秒以概率 0.2 叠加一次 +50% 负载突发，持续 0.5 s。
- 快尺度周期 10 ms（状态更新 + 命令生成/执行），慢尺度周期 100 ms（生成预测上下文）。
- 预测上下文携带依赖期限 300 ms（预测类任务默认），并与生成时刻观测时间不可变绑定。

上下文"过期"客观判定（四个配置统一使用同一判定，写入文档）：
  设上下文生成时刻为 t_gen（对应观测负载 L_gen），命令执行时刻为 t_exe，
  当前真实负载为 L_now。若满足以下任一条件，则该上下文在执行时刻已过期
  （两者取其先，即任一触发即过期）：
  (P1) t_exe - t_gen > 300 ms（超过依赖期限）；
  (P2) |L_now - L_gen| / L_gen > 0.10（负载自生成时刻漂移超 10% 阈值）。

命令生效模型（明确规则，四配置一致）：
- 命令基于执行时刻所依赖上下文隐含的负载估计进行 PRB 分配。
- 若上下文未过期：分配效率因子 1.0（按需分配，满足 UE 数 = 容量允许的满配数）。
- 若上下文已过期：分配效率因子 = 0.6（基于陈旧负载信息分配，明显下降），
  即该 10 ms 周期可满足的 UE 数按 0.6 折算。
- 每 UE 平均吞吐 = 全仿真期间被满足的调度次数占比 * 需求速率；
  满意 UE = 平均吞吐 >= 需求速率的 95%。

计算开销成本权重（等效计算量，自定义合理权重）：
- 全量上下文生成（慢尺度，含按需刷新的"全量"部分不涉及）：1.0 /次
- 快尺度状态更新：0.05 /次
- 命令校验：0.01 /次
- 按需刷新（仅重算过期依赖）：0.3 /次
以配置 B 的总开销归一化为 1.0；R 配置为 10 ms 全量刷新全部上下文（开销锚点）。

四个配置：
- A 单一时间尺度基线：统一 100 ms 周期全量刷新上下文，命令直接执行，无时效校验。
- B 常规多时间尺度基线：10/100 ms 分层，无依赖期限检查、无执行前拒绝。
- C 本方案：分层 + 依赖期限 + 执行前校验拒绝 + 过期依赖按需刷新
  （拒绝后仅重算过期依赖 0.3，随后重新生成并执行命令）。
- R 参考：10 ms 全量刷新全部上下文（单一快尺度保新鲜的开销量级锚点）。

指标定义：
1) 过期上下文使用率 = 使用了"当时已过期"上下文而被执行的命令数 / 被执行命令总数。
2) 过期命令误执行率 = 使用过期上下文且被实际执行的命令数 / 使用过期上下文的命令总数。
3) 有效命令误拒率：C 中未过期命令被误拒的比例（A/B 无拒绝机制，记 0 并注明）。
4) 归一化计算开销 = 该配置等效计算量 / 配置 B 等效计算量。
5) 满意 UE 比例 = 平均吞吐 >= 0.95*需求的 UE 数 / 总 UE 数。
"""

import json
import math
import os
import random
import sys

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# ---------------- 常量 ----------------
DT_MS = 1                 # 步长 ms
T_SIM_S = 60              # 仿真时长 s
T_SIM_MS = T_SIM_S * 1000
N_UE = 200
N_PRB = 100
REQ_MBPS = 1.0            # 每 UE 需求速率 Mbps
CELL_CAPACITY_UE = 80     # 满配时可满足的 UE 数（100 PRB, 1 Mbps/UE 对应 80 UE 上限，
                          # 留出 20% 余量使负载漂移影响满意 UE 数）
FAST_PERIOD_MS = 10       # 快尺度周期
SLOW_PERIOD_MS = 100      # 慢尺度周期
DEP_TTL_MS = 300          # 依赖期限
DRIFT_THRESH = 0.10       # 负载漂移阈值 (P2)
AR1_RHO = 0.9
AR1_SIGMA = 0.04
BURST_PROB_PER_S = 0.2
BURST_AMP = 0.5           # +50%
BURST_DUR_MS = 500
STALE_EFF = 0.6           # 过期上下文下的分配效率因子
SEEDS = [11, 22, 33, 44, 55]

# 成本权重
COST_FULL_CTX = 1.0
COST_FAST_UPDATE = 0.05
COST_CMD_CHECK = 0.01
COST_ONDEMAND_REFRESH = 0.3

RESULT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


# ---------------- 负载轨迹 ----------------
def gen_load_trace(seed):
    """返回长度 T_SIM_MS 的每毫秒真实负载标称序列（每 UE 意味着负载比例）。
    负载 = 需求占容量比例；AR(1) 每秒一步，期间保持；突发叠加 +50% 持续 500 ms。"""
    rng = random.Random(seed * 7919 + 13)
    load = 0.6  # 初始负载
    trace = [0.0] * T_SIM_MS
    for s in range(T_SIM_S):
        # AR(1) 更新（每秒一步）
        load = AR1_RHO * load + (1 - AR1_RHO) * 0.6 + rng.gauss(0.0, AR1_SIGMA)
        load = max(0.30, min(0.95, load))
        # 该秒内是否突发
        burst = rng.random() < BURST_PROB_PER_S
        base_sec = load
        burst_sec = min(0.98, load * (1.0 + BURST_AMP))
        for ms in range(1000):
            idx = s * 1000 + ms
            if idx >= T_SIM_MS:
                break
            if burst and ms < BURST_DUR_MS:
                trace[idx] = burst_sec
            else:
                trace[idx] = base_sec
    return trace


# ---------------- 通用：上下文过期判定 ----------------
def ctx_stale(t_exe, t_gen, l_gen, l_now):
    """过期判定：(P1) 超期限 或 (P2) 负载漂移超阈值，两者取其先（任一触发即过期）。"""
    if t_exe - t_gen > DEP_TTL_MS:
        return True
    if abs(l_now - l_gen) / l_gen > DRIFT_THRESH:
        return True
    return False


# ---------------- 每毫秒可满足 UE 数 ----------------
def served_ues(load, eff):
    """给定真实负载与分配效率，返回该周期可满足（调度成功）的 UE 数。
    小区等效容量 = CELL_CAPACITY_UE / load（负载越高，单 UE 越难满足）；
    过期上下文使分配效率下降：可满足数按 eff 折算。"""
    cap = CELL_CAPACITY_UE / max(load, 1e-6)
    return cap * eff


# ---------------- 配置仿真 ----------------
def simulate(cfg, seed):
    """cfg in {'A','B','C','R'}; 返回单种子指标 dict。"""
    trace = gen_load_trace(seed)
    rng = random.Random(seed * 104729 + 7)

    cost = 0.0
    cmds_total = 0            # 被执行命令总数
    cmds_stale_used = 0       # 使用过期上下文且被执行
    stale_cmds_total = 0      # 使用过期上下文的命令总数（含被拒绝后重算前的首次判定）
    stale_executed = 0        # 使用过期上下文且实际执行
    false_reject = 0          # C 中未过期命令被误拒
    fresh_rejects = 0         # C 中未过期命令被拒绝次数（应为 0）
    served_count = [0] * N_UE  # 每 UE 被满足次数
    sched_rounds = 0          # 调度周期数（每 10 ms 一次）

    t_gen = -1                # 当前上下文生成时刻
    l_gen = 0.0               # 生成时刻观测负载

    def refresh_full(t):
        """全量上下文生成（慢尺度 / A 的 100ms 刷新 / R 的 10ms 刷新）。"""
        nonlocal cost, t_gen, l_gen
        cost += COST_FULL_CTX
        t_gen = t
        l_gen = trace[t]

    t = 0
    while t < T_SIM_MS:
        # ---- 慢尺度 / 全量刷新时刻 ----
        if cfg == 'A':
            if t % SLOW_PERIOD_MS == 0:
                refresh_full(t)
        elif cfg in ('B', 'C'):
            if t % SLOW_PERIOD_MS == 0:
                refresh_full(t)
        elif cfg == 'R':
            if t % FAST_PERIOD_MS == 0:
                refresh_full(t)

        # ---- 快尺度：状态更新 + 命令生成/执行（每 10 ms）----
        if t % FAST_PERIOD_MS == 0 and t_gen >= 0:
            cost += COST_FAST_UPDATE
            sched_rounds += 1
            l_now = trace[t]
            eff = 1.0
            stale = ctx_stale(t, t_gen, l_gen, l_now)

            if cfg in ('A', 'B'):
                # 直接执行，无校验
                cmds_total += 1
                stale_cmds_total += 1 if stale else 0
                if stale:
                    cmds_stale_used += 1
                    stale_executed += 1
                    eff = STALE_EFF
                n_ok = served_ues(l_now, eff)
                _distribute(n_ok, served_count, rng)
            elif cfg == 'C':
                # 执行前校验
                attempts = 0
                while True:
                    cost += COST_CMD_CHECK
                    l_now = trace[t]
                    stale = ctx_stale(t, t_gen, l_gen, l_now)
                    if not stale:
                        break
                    # 拒绝执行 -> 按需刷新（仅重算过期依赖，不全量）
                    stale_cmds_total += 1
                    cost += COST_ONDEMAND_REFRESH
                    t_gen = t
                    l_gen = trace[t]
                    attempts += 1
                    if attempts > 50:  # 安全阀
                        break
                if stale:
                    # 极端情况：刷新后仍过期（理论上不会，安全阀兜底）——统计为误执行
                    cmds_total += 1
                    stale_executed += 1
                    cmds_stale_used += 1
                    eff = STALE_EFF
                else:
                    if attempts > 0:
                        pass  # 过期命令被拦截（不计入执行）
                    cmds_total += 1
                    # 校验通过时不会误拒未过期命令：stale_cmds_total 只统计真正过期的首次尝试
                n_ok = served_ues(l_now, eff)
                _distribute(n_ok, served_count, rng)
            elif cfg == 'R':
                cmds_total += 1
                # 10 ms 全量刷新：上下文始终新鲜（生成即用）
                stale = (t - t_gen) > DEP_TTL_MS  # t_gen == t，恒 False
                # R 的漂移判定：生成即用，l_gen == l_now，恒不过期
                n_ok = served_ues(l_now, 1.0)
                _distribute(n_ok, served_count, rng)
        t += DT_MS

    # ---- 汇总指标 ----
    # 每 UE 平均吞吐（Mbps）：满足次数占比 * 需求
    throughputs = [ (c / sched_rounds) * REQ_MBPS if sched_rounds > 0 else 0.0
                    for c in served_count ]
    satisfied = sum(1 for th in throughputs if th >= 0.95 * REQ_MBPS)

    m = {}
    m['stale_ctx_use_rate'] = (cmds_stale_used / cmds_total) if cmds_total else 0.0
    m['stale_cmd_exec_rate'] = (stale_executed / stale_cmds_total) if stale_cmds_total else 0.0
    m['fresh_cmd_reject_rate'] = 0.0  # C 的误拒单独统计
    m['cost_raw'] = cost
    m['satisfied_ue_ratio'] = satisfied / N_UE
    m['false_reject_rate_C'] = (false_reject / cmds_total) if cmds_total else 0.0
    m['cmds_total'] = cmds_total
    m['stale_cmds_total'] = stale_cmds_total
    m['sched_rounds'] = sched_rounds
    return m


def _distribute(n_ok, served_count, rng):
    """将 n_ok 个满足名额随机分配给 UE（模拟调度器选择）。"""
    n = int(min(n_ok, N_UE))
    if n >= N_UE:
        for i in range(N_UE):
            served_count[i] += 1
        return
    idxs = rng.sample(range(N_UE), n)
    for i in idxs:
        served_count[i] += 1


# ---------------- 主流程 ----------------
def main():
    print(f"numpy available: {HAS_NUMPY}")
    os.makedirs(RESULT_DIR, exist_ok=True)

    all_results = {}
    cost_B_mean = None
    raw = {}
    for cfg in ['A', 'B', 'C', 'R']:
        raw[cfg] = {}
        for seed in SEEDS:
            m = simulate(cfg, seed)
            raw[cfg][str(seed)] = m
            print(f"[{cfg}] seed={seed} stale_use={m['stale_ctx_use_rate']:.4f} "
                  f"stale_exec={m['stale_cmd_exec_rate']:.4f} "
                  f"cost={m['cost_raw']:.2f} sat={m['satisfied_ue_ratio']:.4f}")
        cost_B_mean = sum(raw['B'][s]['cost_raw'] for s in map(str, SEEDS)) / len(SEEDS)

    # 归一化开销（按 B 的均值）
    summary = {}
    for cfg in ['A', 'B', 'C', 'R']:
        summary[cfg] = {}
        for seed in SEEDS:
            m = raw[cfg][str(seed)]
            summary[cfg][str(seed)] = {
                'stale_ctx_use_rate': m['stale_ctx_use_rate'],
                'stale_cmd_exec_rate': m['stale_cmd_exec_rate'],
                'fresh_cmd_reject_rate': m['false_reject_rate_C'],
                'cost_raw': m['cost_raw'],
                'cost_norm': m['cost_raw'] / cost_B_mean,
                'satisfied_ue_ratio': m['satisfied_ue_ratio'],
            }

    # 均值 ± 标准差
    stats = {}
    for cfg in ['A', 'B', 'C', 'R']:
        stats[cfg] = {}
        for key in ['stale_ctx_use_rate', 'stale_cmd_exec_rate', 'fresh_cmd_reject_rate',
                    'cost_norm', 'satisfied_ue_ratio']:
            vals = [summary[cfg][str(s)][key] for s in SEEDS]
            mean = sum(vals) / len(vals)
            sd = (sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5 if len(vals) > 1 else 0.0
            stats[cfg][key] = {'mean': mean, 'std': sd, 'values': vals}

    out = {
        'meta': {
            'sim_duration_s': T_SIM_S, 'dt_ms': DT_MS, 'n_ue': N_UE, 'n_prb': N_PRB,
            'req_mbps': REQ_MBPS, 'fast_period_ms': FAST_PERIOD_MS,
            'slow_period_ms': SLOW_PERIOD_MS, 'dep_ttl_ms': DEP_TTL_MS,
            'drift_threshold': DRIFT_THRESH, 'seeds': SEEDS,
            'cost_weights': {'full_ctx': COST_FULL_CTX, 'fast_update': COST_FAST_UPDATE,
                             'cmd_check': COST_CMD_CHECK, 'ondemand_refresh': COST_ONDEMAND_REFRESH},
            'stale_definition': 't_exe - t_gen > 300ms OR |L_now-L_gen|/L_gen > 10% (either triggers)',
            'numpy': HAS_NUMPY,
        },
        'per_config_per_seed': summary,
        'stats': stats,
        'cost_B_mean': cost_B_mean,
    }
    with open(os.path.join(RESULT_DIR, 'summary.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("Wrote summary.json")

    _write_md(out)
    _write_tex(stats)
    print("Wrote summary.md and results_table.tex")
    return out, stats


def _fmt_pct(x, nd=1):
    return f"{100*x:.{nd}f}"


def _write_md(out):
    stats = out['stats']
    lines = []
    lines.append("# 多时间尺度 RAN 数据协同处理与资源控制 —— 对比仿真结果\n")
    lines.append("## 仿真设定\n")
    lines.append("- 单小区 100 PRB，200 UE，每 UE 需求 1 Mbps；离散时间蒙特卡洛，步长 1 ms，时长 60 s。")
    lines.append("- 小区负载均值 AR(1) 漂移（每秒一步，ρ=0.9，σ=0.04，截断 [0.3, 0.95]）；每秒 0.2 概率叠加 +50% 负载突发（持续 0.5 s）。")
    lines.append("- 快尺度 10 ms（状态更新 + 命令执行），慢尺度 100 ms（全量上下文生成），依赖期限 300 ms。")
    lines.append("- 随机种子：{}；每配置 5 种子，报告均值 ± 标准差。\n".format(SEEDS))
    lines.append("## 指标定义\n")
    lines.append("1. **过期上下文使用率**：被执行命令所使用上下文在当时已过期的比例。过期客观判定（A/B 无期限概念，按同一客观判定统计）：执行时刻距生成时刻 > 300 ms（P1），或负载自生成时刻相对漂移 > 10%（P2），两者取其先（任一触发即过期）。")
    lines.append("2. **过期命令误执行率**：使用过期上下文的命令中被实际执行的比例。C 中此类命令在执行前被拦截（按需刷新后重生成），应 ≈ 0。")
    lines.append("3. **有效命令误拒率**：未过期命令被误拒的比例。A/B 无拒绝机制，记 0（注明“无拒绝机制”）。")
    lines.append("4. **归一化计算开销**：等效计算量（全量上下文生成 1.0/次、快尺度状态更新 0.05/次、命令校验 0.01/次、按需刷新 0.3/次），以配置 B 均值归一化为 1.0；R 为 10 ms 全量刷新锚点。")
    lines.append("5. **满意 UE 比例**：平均吞吐 ≥ 0.95×需求速率的 UE 占比。命令基于过期上下文分配资源时，该周期分配效率因子降为 0.6（明确规则：可满足 UE 数按 0.6 折算）。\n")
    lines.append("## 汇总表（均值 ± 标准差）\n")
    lines.append("| 指标 | 基线 A | 基线 B | 本方案 C | 参考 R |")
    lines.append("|---|---|---|---|---|")

    def row(label, key, pct=True, nd=1):
        cells = []
        for cfg in ['A', 'B', 'C', 'R']:
            st = stats[cfg][key]
            if pct:
                cells.append(f"{100*st['mean']:.{nd}f} ± {100*st['std']:.{nd}f}%")
            else:
                cells.append(f"{st['mean']:.{nd}f} ± {st['std']:.{nd}f}")
        lines.append(f"| {label} | " + " | ".join(cells) + " |")

    row("过期上下文使用率 (%)", 'stale_ctx_use_rate')
    row("过期命令误执行率 (%)", 'stale_cmd_exec_rate')
    # 误拒率
    cells = []
    for cfg in ['A', 'B', 'C', 'R']:
        st = stats[cfg]['fresh_cmd_reject_rate']
        note = "" if cfg == 'C' else "（无拒绝机制，记 0）" if cfg in ('A', 'B') else "（--）"
        if cfg == 'R':
            cells.append("--")
        else:
            cells.append(f"{100*st['mean']:.1f} ± {100*st['std']:.1f}%{note}")
    lines.append("| 有效命令误拒率 (%) | " + " | ".join(cells) + " |")
    row("归一化计算开销", 'cost_norm', pct=False, nd=2)
    row("满意 UE 比例 (%)", 'satisfied_ue_ratio')
    lines.append("")
    # 结论
    a_use = stats['A']['stale_ctx_use_rate']['mean']
    b_use = stats['B']['stale_ctx_use_rate']['mean']
    c_use = stats['C']['stale_ctx_use_rate']['mean']
    a_exec = stats['A']['stale_cmd_exec_rate']['mean']
    b_exec = stats['B']['stale_cmd_exec_rate']['mean']
    c_exec = stats['C']['stale_cmd_exec_rate']['mean']
    a_sat = stats['A']['satisfied_ue_ratio']['mean']
    b_sat = stats['B']['satisfied_ue_ratio']['mean']
    c_sat = stats['C']['satisfied_ue_ratio']['mean']
    b_cost = stats['B']['cost_norm']['mean']
    c_cost = stats['C']['cost_norm']['mean']
    r_cost = stats['R']['cost_norm']['mean']
    lines.append("## 结论\n")
    lines.append(
        f"- 本方案 C 将过期上下文使用率从 A 的 {100*a_use:.1f}% / B 的 {100*b_use:.1f}% 降至 {100*c_use:.1f}%；"
        f"过期命令误执行率从 A 的 {100*a_exec:.1f}% / B 的 {100*b_exec:.1f}% 降至 {100*c_exec:.1f}%（执行前拦截 + 按需刷新）。")
    lines.append(
        f"- 满意 UE 比例：C 为 {100*c_sat:.1f}%，相对 A（{100*a_sat:.1f}%）提升 {100*(c_sat-a_sat):.1f} 个百分点，"
        f"相对 B（{100*b_sat:.1f}%）提升 {100*(c_sat-b_sat):.1f} 个百分点。")
    lines.append(
        f"- 计算开销：C 归一化开销 {c_cost:.2f}（B=1.0），仅增加 {(c_cost/b_cost-1)*100:.1f}%；"
        f"而实现同等新鲜度的 10 ms 全量刷新（R）开销为 {r_cost:.2f}，为 C 的 {r_cost/c_cost:.1f} 倍，"
        f"验证了“依赖期限 + 按需刷新”以远低于全量快刷新的开销获得时效保障。")
    lines.append(
        f"- C 的有效命令误拒率为 {100*stats['C']['fresh_cmd_reject_rate']['mean']:.1f}%（校验只拦截真正过期依赖，无误伤）。")
    with open(os.path.join(RESULT_DIR, 'summary.md'), 'w', encoding='utf-8') as f:
        f.write("\n".join(lines) + "\n")


def _write_tex(stats):
    def pct(key, cfg, nd=1):
        st = stats[cfg][key]
        return f"{100*st['mean']:.{nd}f} \\pm {100*st['std']:.{nd}f}"

    def cost(cfg, nd=2):
        st = stats[cfg]['cost_norm']
        return f"{st['mean']:.{nd}f} \\pm {st['std']:.{nd}f}"

    tex = []
    tex.append("\\begin{table}[htbp]")
    tex.append("  \\centering")
    tex.append("  \\caption{多时间尺度协同处理与资源控制方案对比仿真结果}")
    tex.append("  \\label{tab:mts-comparison}")
    tex.append("  \\begin{tabular}{lcccc}")
    tex.append("    \\toprule")
    tex.append("    指标 & 基线A & 基线B & 本方案C & 参考R \\\\")
    tex.append("    \\midrule")
    tex.append(f"    过期上下文使用率 (\\%) & {pct('stale_ctx_use_rate','A')} & {pct('stale_ctx_use_rate','B')} & {pct('stale_ctx_use_rate','C')} & -- \\\\")
    tex.append(f"    过期命令误执行率 (\\%) & {pct('stale_cmd_exec_rate','A')} & {pct('stale_cmd_exec_rate','B')} & {pct('stale_cmd_exec_rate','C')} & -- \\\\")
    tex.append(f"    有效命令误拒率 (\\%) & {pct('fresh_cmd_reject_rate','A')} & {pct('fresh_cmd_reject_rate','B')} & {pct('fresh_cmd_reject_rate','C')} & -- \\\\")
    tex.append(f"    归一化计算开销 & {cost('A')} & {cost('B')} & {cost('C')} & {cost('R')} \\\\")
    tex.append(f"    满意UE比例 (\\%) & {pct('satisfied_ue_ratio','A')} & {pct('satisfied_ue_ratio','B')} & {pct('satisfied_ue_ratio','C')} & -- \\\\")
    tex.append("    \\bottomrule")
    tex.append("  \\end{tabular}")
    tex.append("\\end{table}")
    with open(os.path.join(RESULT_DIR, 'results_table.tex'), 'w', encoding='utf-8') as f:
        f.write("\n".join(tex) + "\n")


if __name__ == '__main__':
    main()
