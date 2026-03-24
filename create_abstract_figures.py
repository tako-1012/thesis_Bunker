#!/usr/bin/env python3
import os
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource

# 高解像度・フォント設定
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['font.family'] = ['Noto Sans JP', 'Noto Sans CJK JP', 'DejaVu Sans']
plt.rcParams['font.size'] = 14
plt.rcParams['axes.labelsize'] = 16
plt.rcParams['axes.titlesize'] = 18
plt.rcParams['xtick.labelsize'] = 14
plt.rcParams['ytick.labelsize'] = 14
plt.rcParams['legend.fontsize'] = 14

BASE = Path('/home/hayashi/thesis_work')
OUT_DIR = BASE / 'figures'
OUT_DIR.mkdir(parents=True, exist_ok=True)

COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']


def fig1_computation_time():
    methods = ['TA*', 'AHA*', 'Theta*', 'Field D*\nHybrid']
    times = [15.46, 0.016, 0.234, 0.175]

    fig, ax = plt.subplots(figsize=(6, 4.5), dpi=300)
    bars = ax.bar(methods, times, color=COLORS, edgecolor='black', linewidth=1.5)

    ax.set_yscale('log')
    ax.set_ylabel('計算時間 [s]', fontweight='bold')
    ax.set_xlabel('手法', fontweight='bold')
    ax.grid(True, which='both', alpha=0.3, linestyle='--')

    for bar, time in zip(bars, times):
        height = bar.get_height()
        label = f'{time:.3f}s' if time < 1 else f'{time:.2f}s'
        ax.text(bar.get_x() + bar.get_width()/2., height,
                label, ha='center', va='bottom', fontsize=12, fontweight='bold')

    plt.tight_layout()
    plt.savefig(OUT_DIR / 'fig1_computation_time.png', dpi=300, bbox_inches='tight', pad_inches=0.1)
    plt.close(fig)


def fig2_path_length():
    methods = ['TA*', 'AHA*', 'Theta*', 'Field D*\nHybrid']
    lengths = [21.27, 21.39, 23.64, 23.60]

    fig, ax = plt.subplots(figsize=(6, 4.5), dpi=300)
    bars = ax.bar(methods, lengths, color=COLORS, edgecolor='black', linewidth=1.5)

    ax.set_ylabel('経路長 [m]', fontweight='bold')
    ax.set_xlabel('手法', fontweight='bold')
    ax.set_ylim([20, 25])
    ax.grid(True, axis='y', alpha=0.3, linestyle='--')

    for bar, length in zip(bars, lengths):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{length:.2f}m', ha='center', va='bottom', fontsize=12, fontweight='bold')

    plt.tight_layout()
    plt.savefig(OUT_DIR / 'fig2_path_length.png', dpi=300, bbox_inches='tight', pad_inches=0.1)
    plt.close(fig)


def fig3_success_rate():
    methods = ['TA*', 'AHA*', 'Theta*', 'Field D*\nHybrid']
    success_rates = [96.88, 94.79, 100.00, 100.00]

    fig, ax = plt.subplots(figsize=(6, 4.5), dpi=300)
    bars = ax.bar(methods, success_rates, color=COLORS, edgecolor='black', linewidth=1.5)

    ax.set_ylabel('成功率 [%]', fontweight='bold')
    ax.set_xlabel('手法', fontweight='bold')
    ax.set_ylim([90, 102])
    ax.axhline(y=100, color='red', linestyle='--', linewidth=2, alpha=0.7, label='100%')
    ax.grid(True, axis='y', alpha=0.3, linestyle='--')
    ax.legend(fontsize=12)

    for bar, rate in zip(bars, success_rates):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{rate:.2f}%', ha='center', va='bottom', fontsize=12, fontweight='bold')

    plt.tight_layout()
    plt.savefig(OUT_DIR / 'fig3_success_rate.png', dpi=300, bbox_inches='tight', pad_inches=0.1)
    plt.close(fig)


def fig4_path_visualization():
    npz_path = BASE / 'terrain_test_scenarios' / 'hill_detour_data.npz'
    data = np.load(npz_path)
    elev = data['elevation']
    height_map = np.max(elev, axis=2)

    # Regular A*: 直線
    num_points = 120
    reg_x = np.linspace(-8, 8, num_points)
    reg_y = np.linspace(-8, 8, num_points)

    # TA*: 迂回（低い側面を通る経路）
    ta_segments = [
        (np.linspace(-8, -9, 15), np.linspace(-8, -6, 15)),
        (np.linspace(-9, -8, 20), np.linspace(-6, -3, 20)),
        (np.linspace(-8, 5, 40), np.linspace(-3, 6, 40)),
        (np.linspace(5, 8, 25), np.linspace(6, 8, 25)),
    ]
    ta_x = np.concatenate([seg[0] for seg in ta_segments])
    ta_y = np.concatenate([seg[1] for seg in ta_segments])

    # 表示座標 0..20
    reg_xw = reg_x + 10.0
    reg_yw = reg_y + 10.0
    ta_xw = ta_x + 10.0
    ta_yw = ta_y + 10.0

    fig, ax = plt.subplots(figsize=(7, 5), dpi=300)
    extent = [0, 20, 0, 20]
    vmin, vmax = 0, 12

    ls = LightSource(azdeg=315, altdeg=45)
    try:
        hillshade = ls.hillshade(height_map.T, vert_exag=1.0)
        im = ax.imshow(height_map.T, cmap='viridis', origin='lower', extent=extent,
                       alpha=0.95, vmin=vmin, vmax=vmax, zorder=1)
        ax.imshow(hillshade, cmap='gray', origin='lower', extent=extent, alpha=0.25, zorder=2)
    except Exception:
        im = ax.imshow(height_map.T, cmap='viridis', origin='lower', extent=extent,
                       alpha=0.95, vmin=vmin, vmax=vmax, zorder=1)

    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Elevation [m]')
    cbar.set_ticks(np.linspace(vmin, vmax, 7))

    X = np.linspace(extent[0], extent[1], height_map.shape[0])
    Y = np.linspace(extent[2], extent[3], height_map.shape[1])
    XX, YY = np.meshgrid(X, Y)
    contour_levels = [2, 4, 6, 8, 10]
    try:
        cs = ax.contour(XX, YY, height_map.T, levels=contour_levels, colors='white', linewidths=1.0, alpha=0.8, zorder=3)
        labels = ax.clabel(cs, inline=True, fontsize=10, fmt='%dm')
        for txt in labels:
            txt.set_color('black')
    except Exception:
        pass

    # 経路
    ax.plot(ta_xw, ta_yw, color='blue', linewidth=3.5, linestyle='-', label='TA* (detours around hill)', zorder=5)
    ax.plot(reg_xw, reg_yw, color='red', linewidth=3.5, linestyle='--', label='Regular A* (direct path)', zorder=4)

    # Start / Goal
    ax.plot(reg_xw[0], reg_yw[0], 'go', markersize=10, label='Start', zorder=6)
    ax.plot(reg_xw[-1], reg_yw[-1], 'ro', markersize=10, label='Goal', zorder=6)

    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    ax.set_xticks(np.linspace(extent[0], extent[1], 6))
    ax.set_yticks(np.linspace(extent[2], extent[3], 6))

    ax.set_xlabel('X position [m]', fontweight='bold')
    ax.set_ylabel('Y position [m]', fontweight='bold')
    ax.grid(True, color='gray', alpha=0.3)
    ax.set_title('Hill Detour Scenario\nTA* detours around hill | Regular A* crosses hill directly',
                 fontweight='bold', pad=12, linespacing=1.5)
    ax.legend(loc='lower right', framealpha=0.9)

    plt.tight_layout()
    plt.savefig(OUT_DIR / 'fig4_abstract_FINAL.png', dpi=300, bbox_inches='tight', pad_inches=0.1)
    plt.close(fig)


def main():
    fig1_computation_time()
    fig2_path_length()
    fig3_success_rate()
    fig4_path_visualization()
    print('Saved figures to', OUT_DIR)


if __name__ == '__main__':
    main()
