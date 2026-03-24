#!/usr/bin/env python3
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def make_terrain():
    x = np.linspace(0, 40, 400)
    y = np.linspace(0, 40, 400)
    X, Y = np.meshgrid(x, y)
    hill_center_x, hill_center_y = 20, 20
    hill_height = 9.0
    hill_width = 80.0
    terrain = hill_height * np.exp(-((X - hill_center_x) ** 2 + (Y - hill_center_y) ** 2) / hill_width)
    # add low background noise 0-2m
    rng = np.random.RandomState(0)
    terrain += rng.uniform(0.0, 2.0, size=terrain.shape) * 0.25
    return X, Y, terrain


def make_paths():
    reg_x = np.linspace(10, 30, 100)
    reg_y = np.linspace(10, 30, 100)
    # Use waypoint-based large left-side detour to ensure distance from hill
    ta_waypoints = [
        (10.0, 10.0),
        (8.0, 12.0),
        (6.0, 16.0),
        (6.0, 24.0),
        (10.0, 30.0),
        (20.0, 36.0),
        (30.0, 30.0),
    ]

    # piecewise-linear interpolation along waypoints to get 100 points
    pts = np.array(ta_waypoints)
    seg_lengths = np.sqrt(np.sum(np.diff(pts, axis=0) ** 2, axis=1))
    cumlen = np.concatenate(([0.0], np.cumsum(seg_lengths)))
    total = cumlen[-1]
    t_samples = np.linspace(0.0, total, 100)
    ta_x = np.interp(t_samples, cumlen, pts[:, 0])
    ta_y = np.interp(t_samples, cumlen, pts[:, 1])

    return (reg_x, reg_y), (ta_x, ta_y)


def save_fig(fig, png_path, pdf_path):
    try:
        d = os.path.dirname(png_path)
        os.makedirs(d, exist_ok=True)
        fig.savefig(png_path, dpi=300, bbox_inches='tight')
        fig.savefig(pdf_path, bbox_inches='tight')
        return png_path, pdf_path
    except PermissionError:
        return None, None


def main():
    X, Y, terrain = make_terrain()
    (reg_x, reg_y), (ta_x, ta_y) = make_paths()

    # helper: sample terrain heights at coordinates (x,y)
    def sample_heights(xs, ys):
        nx, ny = terrain.shape
        hs = []
        for x, y in zip(xs, ys):
            ix = int(round((x / 40.0) * (nx - 1)))
            iy = int(round((y / 40.0) * (ny - 1)))
            ix = max(0, min(nx - 1, ix))
            iy = max(0, min(ny - 1, iy))
            hs.append(float(terrain[iy, ix]))
        return hs

    # Validate TA* distance from hill center and heights
    hill_cx, hill_cy = 20.0, 20.0
    distances = np.sqrt((ta_x - hill_cx) ** 2 + (ta_y - hill_cy) ** 2)
    if np.any(distances < 12.0):
        raise RuntimeError('TA* is too close to hill; distances min={:.2f}m'.format(float(distances.min())))

    ta_heights = sample_heights(ta_x, ta_y)
    reg_heights = sample_heights(reg_x, reg_y)
    ta_max_h = max(ta_heights) if ta_heights else 0.0
    reg_max_h = max(reg_heights) if reg_heights else 0.0
    # Enforce critical requirements
    if ta_max_h >= 2.5:
        raise RuntimeError('TA* too high: max {:.2f}m >= 2.5m'.format(ta_max_h))
    if reg_max_h < 8.0:
        raise RuntimeError('Regular A* too low: max {:.2f}m < 8.0m'.format(reg_max_h))


    fig, ax = plt.subplots(figsize=(11, 10))

    im = ax.contourf(X, Y, terrain, levels=30, cmap='terrain', alpha=0.95)
    cbar = plt.colorbar(im, ax=ax, label='Height [m]')

    contours = ax.contour(X, Y, terrain, levels=[2, 4, 6, 8], colors='white', linewidths=1.5, alpha=0.7)
    ax.clabel(contours, inline=True, fontsize=10, fmt='%dm')

    ax.plot(reg_x, reg_y, 'r-', linewidth=5, label='Regular A* (direct path, max ~10m)', zorder=5, alpha=0.95)
    ax.plot(ta_x, ta_y, 'g-', linewidth=5, label='TA* (detour around terrain, max ~2m)', zorder=6, alpha=0.95)

    ax.plot(10, 10, 'bo', markersize=16, label='Start', zorder=7)
    ax.plot(30, 30, 'y*', markersize=22, label='Goal', zorder=7)

    ax.text(20, 20, 'Hill\n(8-10m)', fontsize=13, ha='center', va='center', color='white', weight='bold', bbox=dict(boxstyle='round', facecolor='saddlebrown', edgecolor='white', alpha=0.9, linewidth=2))

    ax.annotate('TA* avoids\nhigh terrain\n(stays low)', xy=(15, 10), xytext=(8, 15), fontsize=11, color='darkgreen', weight='bold', bbox=dict(boxstyle='round', facecolor='lightgreen', edgecolor='green', alpha=0.9, linewidth=2), arrowprops=dict(arrowstyle='->', color='green', lw=2.5))

    ax.annotate('Regular A*\ngoes through hill\n(reaches ~10m)', xy=(20, 20), xytext=(25, 15), fontsize=11, color='darkred', weight='bold', bbox=dict(boxstyle='round', facecolor='lightcoral', edgecolor='red', alpha=0.9, linewidth=2), arrowprops=dict(arrowstyle='->', color='red', lw=2.5))

    ax.set_xlabel('X position [m]', fontsize=13, weight='bold')
    ax.set_ylabel('Y position [m]', fontsize=13, weight='bold')
    ax.set_title('Terrain-Aware Path Planning: Conceptual Illustration\nTA* detours to avoid high terrain', fontsize=13, weight='bold', pad=15)
    ax.legend(loc='upper left', fontsize=11, framealpha=0.95, edgecolor='black', fancybox=True)
    ax.grid(True, alpha=0.25, linestyle='--', linewidth=0.8)
    ax.set_aspect('equal')
    ax.set_xlim(5, 35)
    ax.set_ylim(5, 35)

    plt.tight_layout()

    # try /mnt user outputs first, fallback to figures/
    out_png = '/mnt/user-data/outputs/fig4_path_conceptual.png'
    out_pdf = '/mnt/user-data/outputs/fig4_path_conceptual.pdf'
    png, pdf = save_fig(fig, out_png, out_pdf)
    if png is None:
        out_dir = os.path.join(os.path.dirname(__file__), '..', 'figures')
        os.makedirs(out_dir, exist_ok=True)
        png = os.path.join(out_dir, 'fig4_path_conceptual.png')
        pdf = os.path.join(out_dir, 'fig4_path_conceptual.pdf')
        fig.savefig(png, dpi=300, bbox_inches='tight')
        fig.savefig(pdf, bbox_inches='tight')

    plt.close(fig)
    print('Saved:', png, pdf)


if __name__ == '__main__':
    main()
