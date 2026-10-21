import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.path import Path
import matplotlib.lines as lines

def setup_figure(figsize=(8.27, 11.69)): # A4 size in inches roughly
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(0, 160)
    ax.set_ylim(0, 220) # Adjusted for coordinate system
    ax.set_aspect('equal')
    ax.axis('off')
    return fig, ax

def draw_box(ax, x, y, w, h, text='', label=''):
    rect = patches.Rectangle((x, y), w, h, linewidth=1, edgecolor='black', facecolor='none')
    ax.add_patch(rect)
    if text:
        ax.text(x + w/2, y + h/2, text, ha='center', va='center', fontsize=8, wrap=True)
    if label:
        ax.text(x + w - 2, y + 2, label, ha='right', va='bottom', fontsize=6)
    return x+w/2, y, x+w/2, y+h # return connection points (bottom, top)

def draw_arrow(ax, x1, y1, x2, y2):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', lw=1, color='black'))

def generate_fig1():
    fig, ax = setup_figure(figsize=(8, 10))
    
    # Top: Source Chain
    ax.text(10, 210, 'Source Blockchain [110]', fontsize=10, fontweight='bold')
    draw_box(ax, 10, 190, 140, 25, '')
    
    cx1, cy1_b, cx1_t, cy1_t = draw_box(ax, 20, 195, 40, 15, 'Cross-chain\nRequest\n[111]')
    cx2, cy2_b, cx2_t, cy2_t = draw_box(ax, 90, 195, 40, 15, 'Message Hash\nUnit\n[112]')
    draw_arrow(ax, 60, 202.5, 90, 202.5)
    
    # Arrow down
    draw_arrow(ax, 80, 190, 80, 175)
    ax.text(82, 182, '[170]', fontsize=6)

    # Middle: Threshold System
    ax.text(10, 175, 'Threshold Signature System [120]', fontsize=10, fontweight='bold')
    draw_box(ax, 10, 65, 140, 115, '')
    
    # Nodes
    node_y = 145
    node_w = 20
    node_h = 25
    spacing = 10
    
    nodes = []
    for i, (name, label) in enumerate([('P1', '[121]'), ('P2', '[122]'), ('P3', '[123]'), ('Pn', '[12n]')]):
        x = 20 + i * (node_w + spacing)
        if i == 3: x += 10 # Gap for ...
        
        # Node box
        draw_box(ax, x, node_y, node_w, node_h, f'Node {name}\n{label}')
        
        # Share box inside or below? Drawing spec says below
        draw_box(ax, x, node_y - 15, node_w, 10, f'[f]{i+1}\n[13{i+1}]')
        
        nodes.append((x + node_w/2, node_y - 15))

    ax.text(100, 155, '...', fontsize=12)

    # MPC Module
    mpc_y = 80
    draw_box(ax, 20, mpc_y, 120, 40, '', '[140]')
    ax.text(25, mpc_y + 35, 'MPC Coordination Module', fontsize=9)
    
    draw_box(ax, 25, mpc_y + 5, 30, 25, 'Arith-NTT\n[141]')
    draw_box(ax, 65, mpc_y + 5, 30, 25, 'Collab Reject\nSample [142]')
    draw_box(ax, 105, mpc_y + 5, 30, 25, 'Sig Agg\n[143]')

    # Connections from nodes to MPC
    for nx, ny in nodes:
        draw_arrow(ax, nx, ny, nx, mpc_y + 40)

    # Output Signature
    draw_arrow(ax, 80, mpc_y, 80, 50)
    draw_box(ax, 50, 35, 60, 15, 'Falcon Signature (r, s) [150]')

    # Arrow down
    draw_arrow(ax, 80, 35, 80, 25)
    ax.text(82, 30, '[180]', fontsize=6)

    # Bottom: Target Chain
    ax.text(10, 25, 'Target Blockchain [160]', fontsize=10, fontweight='bold')
    draw_box(ax, 10, 0, 140, 25, '')
    
    draw_box(ax, 20, 5, 40, 15, 'Falcon Verify\nContract [161]')
    draw_box(ax, 90, 5, 40, 15, 'Execute\nModule [162]')
    draw_arrow(ax, 60, 12.5, 90, 12.5)

    plt.tight_layout()
    plt.savefig('Figure_1.png', dpi=300, bbox_inches='tight')
    plt.close()

def generate_fig2():
    fig, ax = setup_figure(figsize=(8, 12))
    
    # Start
    ax.text(80, 215, 'START [200]', ha='center', fontsize=9, bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="black"))
    draw_arrow(ax, 80, 212, 80, 205)

    # Phase 1
    draw_box(ax, 30, 175, 100, 30, '', 'Phase 1 [210]')
    draw_box(ax, 40, 190, 80, 10, 'Generate local sample s_i [211]')
    draw_arrow(ax, 80, 190, 80, 185)
    draw_box(ax, 40, 178, 80, 7, 'Generate mask m_i [212]')
    
    draw_arrow(ax, 80, 175, 80, 165)

    # Phase 2
    draw_box(ax, 30, 125, 100, 40, '', 'Phase 2 [220]')
    draw_box(ax, 40, 150, 80, 10, 'Compute C_i = H(m_i || s_i) [221]')
    draw_arrow(ax, 80, 150, 80, 145)
    draw_box(ax, 40, 138, 80, 7, 'Broadcast C_i [222]')
    draw_arrow(ax, 80, 138, 80, 133)
    draw_box(ax, 40, 128, 80, 5, 'Collect Commitments [223]')

    draw_arrow(ax, 80, 125, 80, 115)

    # Phase 3
    draw_box(ax, 30, 75, 100, 40, '', 'Phase 3 [230]')
    draw_box(ax, 40, 100, 80, 10, 'Exchange masked stats [231]')
    draw_arrow(ax, 80, 100, 80, 95)
    draw_box(ax, 40, 88, 80, 7, 'Secure Aggregation [232]')
    draw_arrow(ax, 80, 88, 80, 83)
    draw_box(ax, 40, 78, 80, 5, 'Compute Global Norm [233]')

    draw_arrow(ax, 80, 75, 80, 65)

    # Decision
    # Diamond shape manually
    d_x, d_y = 80, 55
    d_w, d_h = 20, 10
    path_data = [
        (Path.MOVETO, (d_x, d_y + d_h)),
        (Path.LINETO, (d_x + d_w, d_y)),
        (Path.LINETO, (d_x, d_y - d_h)),
        (Path.LINETO, (d_x - d_w, d_y)),
        (Path.CLOSEPOLY, (d_x, d_y + d_h)),
    ]
    codes, verts = zip(*path_data)
    path = Path(verts, codes)
    patch = patches.PathPatch(path, facecolor='none', lw=1)
    ax.add_patch(patch)
    ax.text(d_x, d_y, 'Check\nPass?\n[240]', ha='center', va='center', fontsize=8)

    # Yes branch
    ax.text(75, 45, 'Yes', fontsize=8)
    draw_arrow(ax, 80, 45, 80, 35)
    
    draw_box(ax, 50, 25, 60, 10, 'Reveal & Agg [250-252]')
    draw_arrow(ax, 80, 25, 80, 15)
    
    draw_box(ax, 50, 5, 60, 10, 'Output Signature [270]')

    # No branch
    ax.text(105, 55, 'No', fontsize=8)
    draw_arrow(ax, 100, 55, 120, 55)
    draw_arrow(ax, 120, 55, 120, 180) # Loop back up
    draw_arrow(ax, 120, 180, 130, 180) # To side
    ax.text(125, 100, 'Retry Path [260]', rotation=90, fontsize=8)
    
    # Loop back connection
    draw_arrow(ax, 120, 190, 110, 190) # Back to Phase 1

    plt.tight_layout()
    plt.savefig('Figure_2.png', dpi=300, bbox_inches='tight')
    plt.close()

def generate_fig3():
    fig, ax = setup_figure(figsize=(8, 6))
    
    # Scenario A: Addition
    ax.text(10, 200, '(A) Node Addition [310]', fontweight='bold')
    
    # Circle of nodes
    import numpy as np
    center_x, center_y = 40, 170
    radius = 20
    
    for i in range(7):
        angle = 2 * np.pi * i / 7
        nx = center_x + radius * np.cos(angle)
        ny = center_y + radius * np.sin(angle)
        circle = patches.Circle((nx, ny), 3, fill=False, edgecolor='black')
        ax.add_patch(circle)
        ax.text(nx, ny, f'P{i+1}', ha='center', va='center', fontsize=6)
        
    # New node
    nx = center_x + radius + 10
    ny = center_y
    circle = patches.Circle((nx, ny), 3, fill=False, edgecolor='black', linestyle='--')
    ax.add_patch(circle)
    ax.text(nx, ny, 'P8\n[311]', ha='center', va='center', fontsize=6)
    
    draw_arrow(ax, nx-3, ny, center_x+radius, center_y)

    # Scenario B: Revocation
    ax.text(90, 200, '(B) Node Revocation [320]', fontweight='bold')
    center_x = 120
    
    for i in range(7):
        angle = 2 * np.pi * i / 7
        nx = center_x + radius * np.cos(angle)
        ny = center_y + radius * np.sin(angle)
        circle = patches.Circle((nx, ny), 3, fill=False, edgecolor='black')
        ax.add_patch(circle)
        ax.text(nx, ny, f'P{i+1}', ha='center', va='center', fontsize=6)
        
        if i == 2: # P3
            # Cross out
            ax.plot([nx-2, nx+2], [ny-2, ny+2], 'k-')
            ax.plot([nx-2, nx+2], [ny+2, ny-2], 'k-')
            ax.text(nx, ny-5, '[321]', ha='center', fontsize=6)

    # Scenario C: Recovery
    ax.text(10, 120, '(C) Offline Recovery [330]', fontweight='bold')
    center_x, center_y = 80, 90
    
    for i in range(7):
        angle = 2 * np.pi * i / 7
        nx = center_x + radius * np.cos(angle)
        ny = center_y + radius * np.sin(angle)
        circle = patches.Circle((nx, ny), 3, fill=False, edgecolor='black')
        ax.add_patch(circle)
        
        if i == 4: # P5
            ax.text(nx, ny, '?', ha='center', va='center', fontsize=8)
            ax.text(nx, ny-5, '[331]', ha='center', fontsize=6)
        else:
            ax.text(nx, ny, f'P{i+1}', ha='center', va='center', fontsize=6)
            # Arrow to center
            draw_arrow(ax, nx, ny, center_x, center_y)
            
    ax.text(center_x, center_y, 'Reconstruct\n[332]', ha='center', va='center', fontsize=6)

    plt.tight_layout()
    plt.savefig('Figure_3.png', dpi=300, bbox_inches='tight')
    plt.close()

if __name__ == '__main__':
    generate_fig1()
    generate_fig2()
    generate_fig3()
    print("Figures generated successfully.")
