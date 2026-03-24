#!/usr/bin/env python3
"""
Hill Detour シナリオの可視化図を作成
添付画像と同じスタイル：シンプルでクリーンな2D地形マップ
"""
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource
from pathlib import Path

# 日本語フォント設定
plt.rcParams['font.family'] = ['Noto Sans JP', 'Noto Sans CJK JP', 'DejaVu Sans']
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['font.size'] = 12

BASE = Path('/home/hayashi/thesis_work')
OUT_DIR = BASE / 'figures'
OUT_DIR_THESIS = BASE / 'thisis_write' / 'figures'
OUT_DIR_THESIS.mkdir(parents=True, exist_ok=True)


# 地形データ読み込み
npz_path = BASE / 'terrain_test_scenarios' / 'hill_detour_data.npz'
data = np.load(npz_path)
elev = data['elevation']
height_map = np.max(elev, axis=2)

# 経路データ（合成パス）
# TA*: 迂回経路（滑らかに左側を回る）
ta_path = np.array([
        [2, 2], [3, 3], [4, 4], [5, 5],
        [5.2, 6.2], [5.3, 7.5], [5.4, 8.8], [5.6, 10.0], [5.9, 11.2],
        [6.3, 12.3], [6.9, 13.3], [7.7, 14.1], [8.7, 14.7], [9.9, 15.0],
        [11.2, 15.1], [12.5, 15.1], [13.8, 14.9], [15.0, 14.6],
        [16.0, 15.3], [16.8, 16.2], [17.5, 17.1], [18.2, 18.0], [18.8, 18.8]
])

# Regular A*: 直線経路（丘を突っ切る）
reg_path = np.array([
        [2, 2], [4, 4], [6, 6], [8, 8], [10, 10], [12, 12],
        [14, 14], [16, 16], [18, 18], [18.8, 18.8]
])

# 図作成
fig, ax = plt.subplots(figsize=(10, 10), dpi=300)

# 地形を hillshade + contour で表示
ls = LightSource(azdeg=315, altdeg=45)
extent = [0, 20, 0, 20]

# Hillshade（陰影）
hillshade = ls.hillshade(height_map, vert_exag=2, dx=20/height_map.shape[0], dy=20/height_map.shape[1])
ax.imshow(hillshade, extent=extent, cmap='gray', alpha=0.3, origin='lower')

# 地形等高線
contour = ax.contourf(height_map, levels=15, cmap='viridis', alpha=0.7, 
                      extent=extent, origin='lower')

# カラーバー
cbar = plt.colorbar(contour, ax=ax, label='標高 [m]', pad=0.02)
cbar.ax.tick_params(labelsize=10)

# 経路プロット
ax.plot(reg_path[:, 0], reg_path[:, 1], 'r-', linewidth=4, 
        label='Regular A* (直線経路)', alpha=0.9, zorder=10)
ax.plot(ta_path[:, 0], ta_path[:, 1], 'g-', linewidth=4,
        label='TA* (地形回避)', alpha=0.9, zorder=10)

# スタート・ゴール
ax.plot(2, 2, 'bo', markersize=15, label='始点', zorder=15)
ax.plot(18.8, 18.8, 'y*', markersize=20, label='ゴール', zorder=15)

# 丘の中心に標高表示
ax.text(10, 10, '12m', fontsize=14, fontweight='bold', color='white',
        ha='center', va='center',
        bbox=dict(boxstyle='round', facecolor='black', alpha=0.5))
ax.text(12, 8, '8m', fontsize=12, fontweight='bold', color='white',
        ha='center', va='center',
        bbox=dict(boxstyle='round', facecolor='black', alpha=0.4))
ax.text(12, 12, '6m', fontsize=12, fontweight='bold', color='white',
        ha='center', va='center',
        bbox=dict(boxstyle='round', facecolor='black', alpha=0.4))

# 軸設定
ax.set_xlabel('X座標 [m]', fontsize=14, fontweight='bold')
ax.set_ylabel('Y座標 [m]', fontsize=14, fontweight='bold')
ax.set_xlim(0, 20)
ax.set_ylim(0, 20)
ax.set_aspect('equal')
ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)

# 凡例（白背景で見やすく）
legend = ax.legend(loc='lower right', fontsize=11, framealpha=0.95, 
                  edgecolor='black', fancybox=True)
legend.get_frame().set_facecolor('white')

plt.tight_layout()

# 保存先を thesis_write/figures に変更
fig.savefig(OUT_DIR_THESIS / 'fig8_path_visualization.png', dpi=300, bbox_inches='tight')
fig.savefig(OUT_DIR_THESIS / 'fig8_path_visualization.pdf', bbox_inches='tight')
print(f"  ✅ fig8_path_visualization.png/pdf saved")

# オリジナルの出力名でも保存（互換性のため）
for name in ['fig4_hill_detour_ABSTRACT.png', 'fig4_hill_detour_ABSTRACT_v3.png']:
    fig.savefig(OUT_DIR / name, dpi=300, bbox_inches='tight')
    print(f"  ✅ {name} saved")

plt.close()

print("\n✅ Hill Detour 可視化図の作成完了")
