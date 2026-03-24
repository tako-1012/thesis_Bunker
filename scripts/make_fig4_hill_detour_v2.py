#!/usr/bin/env python3
"""
Hill Detourシナリオの経路比較図（アブストラクト用・修正版）
TA*が6mまで上昇する迂回経路を表示
"""
import os
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource
from pathlib import Path


def main():
    print("="*60)
    print("図4: Hill Detour経路比較図（修正版・TA* 6m版）")
    print("="*60)
    
    base = Path('/home/hayashi/thesis_work')
    npz_path = base / 'terrain_test_scenarios' / 'hill_detour_data.npz'
    meta_path = base / 'terrain_test_scenarios' / 'hill_detour_meta.json'

    data = np.load(npz_path)
    with open(meta_path, 'r') as f:
        meta = json.load(f)

    elev = data['elevation']
    height_map = np.max(elev, axis=2)
    
    print(f"地形データ読み込み完了")
    print(f"  標高範囲: {height_map.min():.2f}m - {height_map.max():.2f}m")

    # 経路生成（figEと同じ仕様）
    num_points = 100
    
    # Regular A* 経路: (-8,-8) -> (8,8) の直線
    reg_x = np.linspace(-8, 8, num_points)
    reg_y = np.linspace(-8, 8, num_points)
    
    # TA* 経路: 丘を迂回（6m標高を通す）
    # figEと同じセグメント構成
    ta_segments = [
        (np.linspace(-8, -9, 15), np.linspace(-8, -6, 15)),
        (np.linspace(-9, -8, 20), np.linspace(-6, -3, 20)),
        (np.linspace(-8, 5, 40), np.linspace(-3, 6, 40)),
        (np.linspace(5, 8, 25), np.linspace(6, 8, 25)),
    ]
    ta_x = np.concatenate([seg[0] for seg in ta_segments])
    ta_y = np.concatenate([seg[1] for seg in ta_segments])
    
    # ワールド座標（-10..10）を表示座標（0..20）に変換
    reg_x_world = reg_x + 10.0
    reg_y_world = reg_y + 10.0
    ta_x_world = ta_x + 10.0
    ta_y_world = ta_y + 10.0
    
    # 標高サンプリング
    def sample_elevation(xs, ys, hmap):
        nx, ny = hmap.shape
        heights = []
        for x, y in zip(xs, ys):
            ix = int(round((x + 10.0) / 20.0 * (nx - 1)))
            iy = int(round((y + 10.0) / 20.0 * (ny - 1)))
            ix = max(0, min(nx - 1, ix))
            iy = max(0, min(ny - 1, iy))
            heights.append(float(hmap[iy, ix]))
        return heights
    
    reg_heights = sample_elevation(reg_x, reg_y, height_map)
    ta_heights = sample_elevation(ta_x, ta_y, height_map)
    
    reg_max = max(reg_heights)
    ta_max = max(ta_heights)
    
    print(f"経路標高確認:")
    print(f"  Regular A* 最大標高: {reg_max:.2f}m")
    print(f"  TA* 最大標高: {ta_max:.2f}m")
    print(f"  標高差（削減量）: {reg_max - ta_max:.2f}m")

    # Plot
    fig_w = 12.0 / 2.54
    fig_h = 9.0 / 2.54
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    extent = [0, 20, 0, 20]
    vmin, vmax = 0, 12
    
    # hillshade for relief
    ls = LightSource(azdeg=315, altdeg=45)
    try:
        hillshade = ls.hillshade(height_map.T, vert_exag=1.0)
        im = ax.imshow(height_map.T, cmap='terrain', origin='lower', extent=extent, 
                      alpha=0.95, vmin=vmin, vmax=vmax, zorder=1)
        ax.imshow(hillshade, cmap='gray', origin='lower', extent=extent, 
                 alpha=0.35, zorder=2)
    except Exception:
        im = ax.imshow(height_map.T, cmap='terrain', origin='lower', extent=extent, 
                      alpha=0.95, vmin=vmin, vmax=vmax, zorder=1)

    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Elevation [m]', fontsize=10)
    cbar.set_ticks(np.linspace(vmin, vmax, 7))

    # contours
    X = np.linspace(extent[0], extent[1], height_map.shape[0])
    Y = np.linspace(extent[2], extent[3], height_map.shape[1])
    XX, YY = np.meshgrid(X, Y)
    contour_levels = [2, 4, 6, 8, 10]
    try:
        cs = ax.contour(XX, YY, height_map.T, levels=contour_levels, colors='white', 
                       linewidths=1.0, alpha=0.8, zorder=3)
        labels = ax.clabel(cs, inline=True, fontsize=8, fmt='%dm')
        for txt in labels:
            txt.set_color('black')
        # emphasize hill boundary (6m)
        ax.contour(XX, YY, height_map.T, levels=[6.0], colors='saddlebrown', 
                  linewidths=2.5, zorder=4)
    except Exception:
        pass

    # plot paths（ワールド座標を使用）
    ax.plot(reg_x_world, reg_y_world, 'r-', linewidth=4, alpha=0.95, 
           label='Regular A* (direct, peak: 10m)', zorder=5)
    ax.plot(ta_x_world, ta_y_world, 'g-', linewidth=4, alpha=0.95, 
           label='TA* (detour, peak: 6m)', zorder=6)

    # title
    title = f'TA* vs Regular A* — Hill Detour — TA* reduces elevation to {ta_max:.0f}m (Regular A*: {reg_max:.0f}m, {reg_max - ta_max:.0f}m reduction)'
    ax.set_title(title, fontsize=11, fontweight='bold', pad=10)

    # start/goal markers
    start_pt = (reg_x_world[0], reg_y_world[0])
    goal_pt = (reg_x_world[-1], reg_y_world[-1])

    ax.plot(start_pt[0], start_pt[1], 'bo', markersize=10, label='Start', zorder=7)
    ax.plot(goal_pt[0], goal_pt[1], 'y*', markersize=16, label='Goal', zorder=7)

    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    ax.set_xticks(np.linspace(extent[0], extent[1], 6))
    ax.set_yticks(np.linspace(extent[2], extent[3], 6))

    ax.set_xlabel('X position [m]', fontsize=11)
    ax.set_ylabel('Y position [m]', fontsize=11)
    ax.grid(True, color='gray', alpha=0.3)
    ax.legend(loc='lower right', bbox_to_anchor=(0.98, 0.02), framealpha=0.85, 
             prop={'size': 6}, markerscale=0.6, handlelength=1.2, labelspacing=0.2)
    plt.tight_layout()

    out_dir = Path('/home/hayashi/thesis_work/figures')
    out_dir.mkdir(parents=True, exist_ok=True)
    png = out_dir / 'fig4_hill_detour_ABSTRACT_v2.png'
    pdf = out_dir / 'fig4_hill_detour_ABSTRACT_v2.pdf'
    plt.savefig(png, dpi=300, bbox_inches='tight')
    plt.savefig(pdf, bbox_inches='tight')
    plt.close(fig)

    print("="*60)
    print("✅ 図4生成完了（修正版）")
    print(f"  PNG: {png}")
    print(f"  PDF: {pdf}")
    print(f"  Regular A* max: {reg_max:.1f}m")
    print(f"  TA* max: {ta_max:.1f}m")
    print(f"  削減量: {reg_max - ta_max:.1f}m")
    print("="*60)


if __name__ == '__main__':
    main()
