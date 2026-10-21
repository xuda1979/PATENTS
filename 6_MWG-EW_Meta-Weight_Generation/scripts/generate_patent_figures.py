"""Generate all 7 patent figures for the MWG-EW disclosure."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
import os

OUT = os.path.join(os.path.dirname(__file__), '..', 'figures')
os.makedirs(OUT, exist_ok=True)

# -- Common style --
plt.rcParams.update({
    'font.size': 10,
    'font.family': 'sans-serif',
    'figure.dpi': 200,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.15,
})
COLORS = {
    'dense': '#D32F2F',
    'mwg': '#1976D2',
    'sram': '#4CAF50',
    'hbm': '#FF9800',
    'gen': '#7B1FA2',
    'release': '#607D8B',
    'kv': '#00BCD4',
    'allreduce': '#E91E63',
    'bg': '#FAFAFA',
    'arrow': '#333333',
}

def box(ax, xy, w, h, text, color, fontsize=8, textcolor='white', alpha=1.0):
    r = FancyBboxPatch(xy, w, h, boxstyle="round,pad=0.05", fc=color, ec='#333', lw=0.8, alpha=alpha)
    ax.add_patch(r)
    ax.text(xy[0]+w/2, xy[1]+h/2, text, ha='center', va='center', fontsize=fontsize, color=textcolor, weight='bold')
    return r

def arrow(ax, x0, y0, x1, y1, color='#333', style='->', lw=1.2):
    ax.annotate('', xy=(x1,y1), xytext=(x0,y0),
                arrowprops=dict(arrowstyle=style, color=color, lw=lw))

# ============================================================
# Figure 1: Traditional vs MWG-EW forward path comparison
# ============================================================
def fig1():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
    for ax, title in [(ax1, '(a) Traditional: Static Dense Weight Path'),
                       (ax2, '(b) MWG-EW: Ephemeral Descriptor Path')]:
        ax.set_xlim(0, 5)
        ax.set_ylim(0, 5)
        ax.set_aspect('equal')
        ax.axis('off')
        ax.set_title(title, fontsize=10, weight='bold', pad=10)

    # (a) Traditional
    box(ax1, (0.2,3.8), 1.5, 0.8, 'Activation\nx', COLORS['mwg'])
    box(ax1, (0.2,1.8), 1.5, 0.8, 'Dense W\n(HBM)', COLORS['hbm'])
    box(ax1, (3.0,2.8), 1.5, 0.8, 'MatMul\nx·W', COLORS['dense'])
    box(ax1, (3.0,0.8), 1.5, 0.8, 'Output\ny', '#555')
    arrow(ax1, 1.7, 4.2, 3.0, 3.4)
    arrow(ax1, 1.7, 2.2, 3.0, 3.0)
    arrow(ax1, 3.75, 2.8, 3.75, 1.6)
    ax1.text(2.3, 3.0, 'HBM\nRead\n336 MiB', fontsize=7, ha='center', color=COLORS['dense'], style='italic')

    # (b) MWG-EW
    box(ax2, (0.2,3.8), 1.2, 0.7, 'Activation\nx', COLORS['mwg'])
    box(ax2, (0.2,2.6), 1.2, 0.7, 'Condition\nSignal', '#795548', fontsize=7)
    box(ax2, (1.8,2.6), 1.2, 0.7, 'Meta-Gen\n(HBM)', COLORS['gen'], fontsize=7)
    box(ax2, (1.8,1.2), 1.2, 0.7, 'U,V\n(SRAM)', COLORS['sram'], fontsize=7)
    box(ax2, (3.4,2.6), 1.2, 0.7, 'x·U·V\n(SRAM)', COLORS['mwg'], fontsize=7)
    box(ax2, (3.4,1.2), 1.2, 0.7, 'Output\ny', '#555', fontsize=7)
    box(ax2, (3.4,0.1), 1.2, 0.5, 'Release\n/Zero', COLORS['release'], fontsize=6)
    arrow(ax2, 1.4, 4.1, 1.8, 3.1)
    arrow(ax2, 1.4, 3.0, 1.8, 3.0)
    arrow(ax2, 3.0, 2.9, 3.4, 2.9)
    arrow(ax2, 2.4, 2.6, 2.4, 1.9)
    arrow(ax2, 3.0, 1.55, 3.4, 2.6)
    arrow(ax2, 4.0, 2.6, 4.0, 1.9)
    arrow(ax2, 4.0, 1.2, 4.0, 0.6)
    ax2.text(2.4, 2.2, 'On-chip\nonly', fontsize=6, ha='center', color=COLORS['sram'], style='italic')
    ax2.annotate('HBM Read\n3.4–13.5 MiB', xy=(2.0, 3.3), fontsize=6, ha='center', color=COLORS['gen'], style='italic')
    # Red X for no HBM write-back
    ax2.text(4.6, 0.35, '✗ No HBM\n   Write-back', fontsize=7, color=COLORS['dense'], weight='bold')

    fig.savefig(os.path.join(OUT, 'fig1_traditional_vs_mwg_forward.png'))
    plt.close(fig)
    print('  fig1 done')

# ============================================================
# Figure 2: System architecture
# ============================================================
def fig2():
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.set_xlim(0, 9)
    ax.set_ylim(0, 6.5)
    ax.axis('off')
    ax.set_title('Fig.2  MWG-EW System Architecture', fontsize=11, weight='bold', pad=8)

    # Accelerator boundary
    rect = mpatches.FancyBboxPatch((0.3, 0.3), 8.4, 5.8, boxstyle="round,pad=0.1",
                                    fc='#E3F2FD', ec='#1565C0', lw=1.5, ls='--')
    ax.add_patch(rect)
    ax.text(4.5, 5.9, 'Accelerator (GPU / NPU / TPU)', ha='center', fontsize=9, color='#1565C0', weight='bold')

    # Modules
    box(ax, (0.5,4.5), 1.5, 0.9, 'Condition\nModule', '#795548')
    box(ax, (2.5,4.5), 1.8, 0.9, 'Meta-\nGenerator', COLORS['gen'])
    box(ax, (5.0,4.5), 1.8, 0.9, 'Fused Exec\nEngine', COLORS['mwg'])
    box(ax, (7.2,4.5), 1.3, 0.9, 'Monitor', '#607D8B', fontsize=7)

    box(ax, (0.5,3.0), 1.5, 0.9, 'ALU-1\n(Vector)', '#FF7043', fontsize=7)
    box(ax, (2.5,3.0), 1.8, 0.9, 'ALU-2\n(Tensor Core)', COLORS['dense'], fontsize=7)
    box(ax, (5.0,3.0), 1.8, 0.9, 'On-chip\nSRAM', COLORS['sram'])
    box(ax, (7.2,3.0), 1.3, 0.9, 'Lifecycle\nController', COLORS['release'], fontsize=7)

    box(ax, (0.5,1.2), 3.0, 0.9, 'External Memory (HBM)', COLORS['hbm'], fontsize=9)
    box(ax, (4.0,1.2), 2.0, 0.9, 'KV Cache\nAllocator', COLORS['kv'], fontsize=8)
    box(ax, (6.5,1.2), 2.0, 0.9, 'Optimizer &\nComm Gate', COLORS['allreduce'], fontsize=8)

    box(ax, (2.5,0.0), 4.0, 0.6, 'Inter-node Bus (NVLink / HCCS / IB)', '#333', fontsize=8)

    # Arrows
    arrow(ax, 2.0, 4.9, 2.5, 4.9)
    arrow(ax, 4.3, 4.9, 5.0, 4.9)
    arrow(ax, 5.9, 4.5, 5.9, 3.9)
    arrow(ax, 5.9, 3.0, 5.9, 2.1)  # SRAM -> HBM blocked
    ax.text(6.1, 2.5, '✗', fontsize=14, color='red', weight='bold')
    arrow(ax, 7.8, 3.0, 7.8, 2.1)
    arrow(ax, 2.0, 1.65, 4.0, 1.65)
    arrow(ax, 7.5, 1.2, 5.5, 0.6)

    fig.savefig(os.path.join(OUT, 'fig2_system_architecture.png'))
    plt.close(fig)
    print('  fig2 done')

# ============================================================
# Figure 3: No-writeback data flow
# ============================================================
def fig3():
    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.set_xlim(0, 8)
    ax.set_ylim(0, 3.5)
    ax.axis('off')
    ax.set_title('Fig.3  Weight Data Flow — No External Materialization', fontsize=10, weight='bold')

    steps = ['Condition\nInput', 'Meta-Gen\n→ Descriptor', 'Write\nSRAM', 'On-chip\nTransform', 'MatMul\nConsume', 'Accumulate\nResult', 'Release /\nOverwrite']
    colors = ['#795548', COLORS['gen'], COLORS['sram'], COLORS['mwg'], COLORS['dense'], '#555', COLORS['release']]
    xs = np.linspace(0.3, 7.0, 7)
    for i, (x, s, c) in enumerate(zip(xs, steps, colors)):
        box(ax, (x-0.4, 1.0), 0.9, 1.0, s, c, fontsize=6.5)
        if i < 6:
            arrow(ax, x+0.5, 1.5, xs[i+1]-0.4, 1.5)

    # HBM zone below
    ax.axhline(0.6, color=COLORS['hbm'], ls='--', lw=1)
    ax.text(4.0, 0.3, 'External Memory (HBM) — No write-back in entire lifecycle', ha='center',
            fontsize=8, color=COLORS['dense'], weight='bold', style='italic')
    # Crossed arrow from step 6 down
    ax.annotate('', xy=(6.6, 0.6), xytext=(6.6, 1.0),
                arrowprops=dict(arrowstyle='->', color='red', lw=1.5, ls='--'))
    ax.text(7.0, 0.7, '✗', fontsize=14, color='red', weight='bold')

    fig.savefig(os.path.join(OUT, 'fig3_no_writeback_dataflow.png'))
    plt.close(fig)
    print('  fig3 done')

# ============================================================
# Figure 4: Block lifecycle timeline
# ============================================================
def fig4():
    fig, ax = plt.subplots(figsize=(9, 3))
    ax.set_xlim(0, 9)
    ax.set_ylim(0, 3)
    ax.axis('off')
    ax.set_title('Fig.4  Descriptor Block Lifecycle (Per-tile)', fontsize=10, weight='bold')

    phases = [('Generate\nU_i, V_i', COLORS['gen'], 0.3, 1.2),
              ('Write\nSRAM', COLORS['sram'], 1.7, 0.8),
              ('Compute\nx·U_i·V_i', COLORS['mwg'], 2.7, 1.5),
              ('Accumulate\ny += partial', '#555', 4.4, 1.2),
              ('Release /\nZero / Overwrite', COLORS['release'], 5.8, 1.5),
              ('Next\ntile i+1', '#795548', 7.5, 1.0)]
    for text, c, x, w in phases:
        box(ax, (x, 0.8), w, 1.2, text, c, fontsize=7)
    for i in range(len(phases)-1):
        x0 = phases[i][2] + phases[i][3]
        x1 = phases[i+1][2]
        arrow(ax, x0, 1.4, x1, 1.4)

    ax.text(4.5, 0.3, '← Tile granularity: buffer reused before next tile →', ha='center',
            fontsize=7, style='italic', color='#666')

    fig.savefig(os.path.join(OUT, 'fig4_block_lifecycle.png'))
    plt.close(fig)
    print('  fig4 done')

# ============================================================
# Figure 5: KV Cache reallocation + double buffering
# ============================================================
def fig5():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

    # (a) KV Cache reallocation
    ax1.set_title('(a) KV Cache HBM Reallocation', fontsize=9, weight='bold')
    categories = ['Dense\nBaseline', 'MWG-EW\nr=128']
    weights = [336, 13.5]
    kv = [964, 1286.5]  # assuming 1300 total
    other = [0, 0]
    bars1 = ax1.bar(categories, weights, color=COLORS['hbm'], label='FFN Weight')
    bars2 = ax1.bar(categories, kv, bottom=weights, color=COLORS['kv'], label='KV Cache')
    ax1.set_ylabel('HBM Usage (MiB)')
    ax1.legend(fontsize=7, loc='upper right')
    ax1.text(1, 336+643, f'+430\ntokens', ha='center', va='bottom', fontsize=8, color=COLORS['kv'], weight='bold')
    ax1.axhline(1300, color='#999', ls=':', lw=0.8)
    ax1.text(1.5, 1310, 'HBM budget', fontsize=7, color='#999')

    # (b) Double buffering timeline
    ax2.set_title('(b) Ping-Pong Double Buffering', fontsize=9, weight='bold')
    ax2.set_xlim(0, 8)
    ax2.set_ylim(0, 3.5)
    ax2.axis('off')
    # Buffer A
    box(ax2, (0.2, 2.2), 1.5, 0.8, 'Buf A: Gen\ntile i', COLORS['gen'], fontsize=7)
    box(ax2, (2.0, 2.2), 1.5, 0.8, 'Buf A:\nCompute i', COLORS['mwg'], fontsize=7)
    box(ax2, (3.8, 2.2), 1.2, 0.8, 'Release A', COLORS['release'], fontsize=7)
    box(ax2, (5.3, 2.2), 1.5, 0.8, 'Buf A: Gen\ntile i+2', COLORS['gen'], fontsize=7)
    # Buffer B
    box(ax2, (2.0, 0.8), 1.5, 0.8, 'Buf B: Gen\ntile i+1', COLORS['gen'], fontsize=7)
    box(ax2, (3.8, 0.8), 1.5, 0.8, 'Buf B:\nCompute i+1', COLORS['mwg'], fontsize=7)
    box(ax2, (5.6, 0.8), 1.2, 0.8, 'Release B', COLORS['release'], fontsize=7)
    # Time arrow
    arrow(ax2, 0.2, 0.3, 7.5, 0.3, color='#999')
    ax2.text(3.8, 0.1, 'Time →', fontsize=8, color='#999')
    ax2.text(0.2, 2.2, 'Buffer A', fontsize=7, color='#333', rotation=90, va='bottom')
    ax2.text(0.2, 0.8, 'Buffer B', fontsize=7, color='#333', rotation=90, va='bottom')

    fig.tight_layout()
    fig.savefig(os.path.join(OUT, 'fig5_kv_cache_double_buffer.png'))
    plt.close(fig)
    print('  fig5 done')

# ============================================================
# Figure 6: Training backward recompute + sync truncation
# ============================================================
def fig6():
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.set_xlim(0, 9)
    ax.set_ylim(0, 4.5)
    ax.axis('off')
    ax.set_title('Fig.6  Training: Backward Recompute + Communication Gating', fontsize=10, weight='bold')

    # Forward path
    ax.text(0.3, 3.8, 'Forward:', fontsize=8, weight='bold', color=COLORS['mwg'])
    box(ax, (1.5,3.4), 1.3, 0.6, 'Gen U,V\n(SRAM)', COLORS['gen'], fontsize=7)
    box(ax, (3.2,3.4), 1.3, 0.6, 'x·U·V\n→ y', COLORS['mwg'], fontsize=7)
    box(ax, (4.9,3.4), 1.0, 0.6, 'Release', COLORS['release'], fontsize=7)
    arrow(ax, 2.8, 3.7, 3.2, 3.7)
    arrow(ax, 4.5, 3.7, 4.9, 3.7)

    # Backward path
    ax.text(0.3, 2.5, 'Backward:', fontsize=8, weight='bold', color=COLORS['dense'])
    box(ax, (1.5,2.1), 1.3, 0.6, 'Re-Gen\nU,V (SRAM)', COLORS['gen'], fontsize=7)
    box(ax, (3.2,2.1), 1.3, 0.6, '∂L/∂x\nvia U,V', COLORS['dense'], fontsize=7)
    box(ax, (4.9,2.1), 1.0, 0.6, 'Release', COLORS['release'], fontsize=7)
    arrow(ax, 2.8, 2.4, 3.2, 2.4)
    arrow(ax, 4.5, 2.4, 4.9, 2.4)

    # Gradient routing
    box(ax, (6.5,3.0), 1.8, 0.8, 'Meta-Gen\nGrad → Sync', COLORS['allreduce'], fontsize=7)
    box(ax, (6.5,1.5), 1.8, 0.8, 'Target Layer\nGrad → ✗ Block', '#999', fontsize=7, textcolor='#333')
    arrow(ax, 5.9, 3.7, 6.5, 3.4)
    arrow(ax, 5.9, 2.4, 6.5, 1.9)
    ax.text(7.4, 2.3, '✗ No All-Reduce', fontsize=7, color='red', weight='bold')
    ax.text(7.4, 3.85, '✓ All-Reduce', fontsize=7, color=COLORS['sram'], weight='bold')

    # Optimizer
    box(ax, (3.0,0.3), 2.5, 0.6, 'Optimizer: only meta-gen states', COLORS['gen'], fontsize=7)
    arrow(ax, 7.4, 3.0, 4.25, 0.9)

    fig.savefig(os.path.join(OUT, 'fig6_backward_recompute_sync.png'))
    plt.close(fig)
    print('  fig6 done')

# ============================================================
# Figure 7: Observable characteristics — real data
# ============================================================
def fig7():
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))

    # (a) HBM traffic
    ax = axes[0]
    ranks = ['Dense', 'r=32', 'r=64', 'r=128', 'r=256']
    traffic = [336, 3.38, 6.75, 13.5, 27.0]
    bars = ax.bar(ranks, traffic, color=[COLORS['dense']]+[COLORS['mwg']]*4)
    ax.set_ylabel('HBM Traffic (MiB/layer)')
    ax.set_title('(a) HBM Traffic Reduction', fontsize=9, weight='bold')
    ax.set_yscale('log')
    for b, v in zip(bars, traffic):
        ax.text(b.get_x()+b.get_width()/2, v*1.3, f'{v}', ha='center', fontsize=7)
    ax.text(2, 200, '99.6× ↓', fontsize=10, color=COLORS['mwg'], weight='bold', ha='center')

    # (b) Latency speedup
    ax = axes[1]
    scenarios = ['B1S1', 'B1S128', 'B4S512', 'B8S512']
    dense_lat = [0.3213, 0.3771, 2.8077, 5.4145]
    r64_lat = [0.1580, 0.1737, 0.3298, 0.7779]
    x = np.arange(len(scenarios))
    w = 0.35
    ax.bar(x-w/2, dense_lat, w, color=COLORS['dense'], label='Dense')
    ax.bar(x+w/2, r64_lat, w, color=COLORS['mwg'], label='MWG-EW r=64')
    ax.set_ylabel('Latency (ms)')
    ax.set_title('(b) Latency Comparison (8B)', fontsize=9, weight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(scenarios, fontsize=8)
    ax.legend(fontsize=7)
    for i, (d, m) in enumerate(zip(dense_lat, r64_lat)):
        ax.text(i+w/2, m+0.05, f'{d/m:.1f}×', ha='center', fontsize=7, color=COLORS['mwg'], weight='bold')

    # (c) Communication savings
    ax = axes[2]
    ranks_c = ['Dense', 'r=32', 'r=64', 'r=128', 'r=256']
    grad = [336, 3.38, 6.75, 13.5, 27.0]
    bars = ax.bar(ranks_c, grad, color=[COLORS['allreduce']]+[COLORS['mwg']]*4)
    ax.set_ylabel('Gradient per Layer (MiB)')
    ax.set_title('(c) All-Reduce Volume', fontsize=9, weight='bold')
    ax.set_yscale('log')
    for b, v in zip(bars, grad):
        ax.text(b.get_x()+b.get_width()/2, v*1.3, f'{v}', ha='center', fontsize=7)
    ax.text(2, 180, '96% saved\n(r=128)', fontsize=9, color=COLORS['mwg'], weight='bold', ha='center')

    fig.tight_layout()
    fig.savefig(os.path.join(OUT, 'fig7_observable_characteristics.png'))
    plt.close(fig)
    print('  fig7 done')

# ============================================================
if __name__ == '__main__':
    print('Generating patent figures...')
    fig1()
    fig2()
    fig3()
    fig4()
    fig5()
    fig6()
    fig7()
    print(f'All figures saved to {OUT}/')
