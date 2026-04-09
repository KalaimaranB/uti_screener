import json
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from pathlib import Path

def plot_calibration_curve(analyte="sp_gravity", model_path="models/model.json", output_dir="tools"):
    # Load Model
    with open(model_path, 'r') as f:
        model = json.load(f)
    
    if analyte not in model:
        raise ValueError(f"Analyte {analyte} not found in model.")
    
    swatches = model[analyte]["swatches"]
    
    # Extract data
    r_vals, g_vals, b_vals = [], [], []
    colors, labels, values = [], [], []
    
    for s in swatches:
        r, g, b = s["rgb"]
        r_vals.append(r / 255.0)
        g_vals.append(g / 255.0)
        b_vals.append(b / 255.0)
        colors.append((r/255.0, g/255.0, b/255.0))
        labels.append(s["label"])
        values.append(s["value"])
        
    pts = np.column_stack((r_vals, g_vals, b_vals))
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # ─── CALCULATE DYNAMIC PROJECTION ───────────────────────────────────────────
    best_proj = None
    best_val = 0.0
    measured = None
    seg_idx = 0
    
    if len(pts) > 1:
        # Pick random segment
        seg_idx = np.random.randint(0, len(pts)-1)
        A = pts[seg_idx]
        B = pts[seg_idx+1]
        
        # Pick point exactly on segment + jitter
        frac = np.random.uniform(0.15, 0.85)
        exact_pt = A + frac * (B - A)
        jitter = np.random.normal(0, 0.04, 3)
        measured = exact_pt + jitter
        
        # Re-run true projection logic
        min_dist = float('inf')
        
        for i in range(len(pts) - 1):
            Pa = pts[i]
            Pb = pts[i+1]
            v = Pb - Pa
            w = measured - Pa
            c1 = np.dot(w, v)
            if c1 <= 0:
                proj, b_frac = Pa, 0.0
            else:
                c2 = np.dot(v, v)
                if c2 <= c1:
                    proj, b_frac = Pb, 1.0
                else:
                    b_frac = c1 / c2
                    proj = Pa + b_frac * v
                    
            dist = np.linalg.norm(measured - proj)
            if dist < min_dist:
                min_dist = dist
                best_proj = proj
                v_a = float(values[i])
                v_b = float(values[i+1])
                best_val = v_a + b_frac * (v_b - v_a)
                seg_idx = i # update true segment hit

    # ─── PLOTTING HELPER ────────────────────────────────────────────────────────
    def _create_base_plot():
        plt.style.use('dark_background')
        fig = plt.figure(figsize=(10, 8), dpi=150)
        fig.patch.set_facecolor('#1a1c23')
        ax = fig.add_subplot(111, projection='3d')
        ax.set_facecolor('#1a1c23')
        ax.xaxis.pane.fill = ax.yaxis.pane.fill = ax.zaxis.pane.fill = False
        ax.xaxis.pane.set_edgecolor('#333842')
        ax.yaxis.pane.set_edgecolor('#333842')
        ax.zaxis.pane.set_edgecolor('#333842')
        ax.grid(color='#333842', linestyle='-', linewidth=0.5)
        
        # Labels
        ax.set_xlabel('RED (X-axis)', fontsize=11, fontweight='bold', color='#b0bec5', labelpad=10)
        ax.set_ylabel('GREEN (Y-axis)', fontsize=11, fontweight='bold', color='#b0bec5', labelpad=10)
        ax.set_zlabel('BLUE (Z-axis)', fontsize=11, fontweight='bold', color='#b0bec5', labelpad=5)
        return fig, ax

    # ════════════════════════════════════════════════════════════════════════════
    # PLOT 1: THE FULL CURVE (Zoomed Out)
    # ════════════════════════════════════════════════════════════════════════════
    fig1, ax1 = _create_base_plot()
    
    # Glowing line
    ax1.plot(r_vals, g_vals, b_vals, color='#ffb74d', linewidth=6, alpha=0.3)
    ax1.plot(r_vals, g_vals, b_vals, color='#ffa726', linewidth=3, alpha=0.6)
    ax1.plot(r_vals, g_vals, b_vals, color='#ffffff', linewidth=1.5, alpha=1.0)
    
    # Nodes
    ax1.scatter(r_vals, g_vals, b_vals, c=colors, s=100, edgecolor='white', linewidth=1.5, depthshade=False, zorder=5)
    
    for i in range(len(swatches)):
        valign = 'bottom' if i % 2 == 0 else 'top'
        z_off = 0.04 if i % 2 == 0 else -0.04
        ax1.text(r_vals[i], g_vals[i], b_vals[i] + z_off, f"{values[i]}\n{labels[i]}", 
                color='#ffcc80', fontsize=9, ha='center', va=valign, zorder=10)

    ax1.set_xlim(0, 1)
    ax1.set_ylim(0, 1)
    ax1.set_zlim(0, 1)
    plt.title(f"3D CALIBRATION CURVE: {analyte.upper()}\nMacroscopic View", fontsize=14, fontweight='bold', color='white', y=1.05)
    
    out1 = out_dir / f"{analyte}_3d_macro.png"
    plt.savefig(out1, facecolor=fig1.get_facecolor(), bbox_inches='tight', pad_inches=0.4)
    plt.close(fig1)

    # ════════════════════════════════════════════════════════════════════════════
    # PLOT 2: THE PROJECTION ZOOM (Microscopic View)
    # ════════════════════════════════════════════════════════════════════════════
    if measured is not None:
        fig2, ax2 = _create_base_plot()
        
        # Only plot the segment we hit
        Pa = pts[seg_idx]
        Pb = pts[seg_idx+1]
        
        # Draw the target segment heavily, and neighboring ones faintly
        ax2.plot([Pa[0], Pb[0]], [Pa[1], Pb[1]], [Pa[2], Pb[2]], color='#ffa726', linewidth=5, alpha=0.9)
        
        if seg_idx > 0:
            Pprev = pts[seg_idx-1]
            ax2.plot([Pprev[0], Pa[0]], [Pprev[1], Pa[1]], [Pprev[2], Pa[2]], color='#ffb74d', linewidth=2, alpha=0.3)
        if seg_idx < len(pts) - 2:
            Pnext = pts[seg_idx+2]
            ax2.plot([Pb[0], Pnext[0]], [Pb[1], Pnext[1]], [Pb[2], Pnext[2]], color='#ffb74d', linewidth=2, alpha=0.3)

        # Plot segment nodes
        ax2.scatter(*Pa, color=colors[seg_idx], s=250, edgecolor='white', linewidth=2, zorder=5)
        ax2.scatter(*Pb, color=colors[seg_idx+1], s=250, edgecolor='white', linewidth=2, zorder=5)
        
        # Text for the nodes (Pushed outward to avoid overlap)
        ax2.text(Pa[0]-0.01, Pa[1], Pa[2], f"Node A\n({values[seg_idx]})", color='#ffcc80', fontsize=12, ha='right', va='center')
        ax2.text(Pb[0]+0.01, Pb[1], Pb[2], f"Node B\n({values[seg_idx+1]})", color='#ffcc80', fontsize=12, ha='left', va='center')

        # Plot Measured Point Q
        ax2.scatter(*measured, color='#00e5ff', s=200, edgecolor='white', linewidth=1.5, zorder=6)
        
        # Push Measured Q text high above the dot
        ax2.text(measured[0], measured[1], measured[2] + 0.015, f"Measured 'Q'\n(Raw Camera)", 
                 color='#00e5ff', fontsize=12, ha='center', va='bottom', fontweight='bold')
        
        # Plot physical hit-point on the segment
        ax2.scatter(*best_proj, color='#b2ff59', s=150, edgecolor='white', linewidth=1.5, zorder=7)
        ax2.text(best_proj[0], best_proj[1], best_proj[2] - 0.015, f"Est: {best_val:.3f}", 
                color='#b2ff59', fontsize=12, ha='center', va='top', fontweight='bold', zorder=10)
        
        # Draw dashed projection line
        ax2.plot([measured[0], best_proj[0]], 
                 [measured[1], best_proj[1]], 
                 [measured[2], best_proj[2]], 
                 color='#00e5ff', linestyle='--', linewidth=3, alpha=0.9)
        
        # Zoom camera bounds tightly around this local event
        all_local_pts = np.vstack([Pa, Pb, measured, best_proj])
        mins = all_local_pts.min(axis=0) - 0.03
        maxs = all_local_pts.max(axis=0) + 0.03
        
        ax2.set_xlim(mins[0], maxs[0])
        ax2.set_ylim(mins[1], maxs[1])
        ax2.set_zlim(mins[2], maxs[2])
        
        plt.title(f"PROJECTION MAPPING (ZOOMED)\nFinding minimum distance to curve segment", fontsize=14, fontweight='bold', color='white', y=1.05)
        
        out2 = out_dir / f"{analyte}_3d_zoom.png"
        plt.savefig(out2, facecolor=fig2.get_facecolor(), bbox_inches='tight', pad_inches=0.4)
        plt.close(fig2)
        
        print(f"[SUCCESS] Macro plot: {out1}")
        print(f"[SUCCESS] Zoom plot: {out2}")

if __name__ == "__main__":
    plot_calibration_curve()
