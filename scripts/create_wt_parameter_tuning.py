#!/usr/bin/env python3
"""
fig_4_wt_parameter_tuning.pdf 新規作成スクリプト
wt_tuning.json の実データを使用した二軸グラフ
"""
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['font.size'] = 12

BASE = Path('/home/hayashi/thesis_work')
OUT_DIR = BASE / 'figures'

def create_wt_parameter_tuning_figure():
    """wtパラメータチューニング図を作成"""
    print("Creating fig_4_wt_parameter_tuning.pdf...")
    
    # wt_tuning.json から実データを読み込み
    with open(BASE / 'results' / 'wt_tuning.json', 'r') as f:
        data = json.load(f)
    
    wt_values = np.array(data['wt'])
    path_lengths = np.array(data['path_length'])
    terrain_costs = np.array(data['terrain_cost_avg'])
    computation_times = np.array(data['computation_time'])
    
    # 図作成
    fig, ax1 = plt.subplots(figsize=(10, 6))
    
    # 経路長（左軸）
    color1 = '#1f77b4'  # 青
    ax1.set_xlabel('Terrain Weight wt', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Path Length [m]', color=color1, fontsize=14, fontweight='bold')
    line1 = ax1.plot(wt_values, path_lengths, color=color1, marker='o', 
                     linewidth=2.5, markersize=8, label='Path Length')
    ax1.tick_params(axis='y', labelcolor=color1)
    ax1.set_xlim(-0.1, 2.1)
    ax1.set_ylim([0, max(path_lengths) * 1.1])  # 修正: 0からスタート
    ax1.grid(True, alpha=0.3, linestyle='--')
    
    # 地形コスト（右軸）
    ax2 = ax1.twinx()
    color2 = '#d62728'  # 赤
    ax2.set_ylabel('Terrain Cost (Average)', color=color2, fontsize=14, fontweight='bold')
    line2 = ax2.plot(wt_values, terrain_costs, color=color2, marker='s', 
                     linewidth=2.5, markersize=8, label='Terrain Cost')
    ax2.tick_params(axis='y', labelcolor=color2)
    ax2.set_ylim([0, max(terrain_costs) * 1.1])  # 修正: 0からスタート
    
    # wt=1.0の推奨値を強調
    optimal_wt = 1.0
    optimal_idx = np.argmin(np.abs(wt_values - optimal_wt))
    ax1.axvline(x=optimal_wt, color='green', linestyle='--', linewidth=2, alpha=0.6)
    ax1.plot(optimal_wt, path_lengths[optimal_idx], 'g*', markersize=20, 
             label='Optimal (wt=1.0)', zorder=10)
    
    ax1.text(optimal_wt, max(path_lengths) * 0.95, 'Optimal\n(wt=1.0)', 
             ha='center', fontsize=11, fontweight='bold',
             bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.7))
    
    # 凡例
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left', fontsize=11, framealpha=0.95)
    
    # レイアウト調整
    fig.tight_layout()
    
    # PDF 保存（ベクター形式）
    fig.savefig(OUT_DIR / 'fig_4_wt_parameter_tuning.pdf', format='pdf', bbox_inches='tight')
    # PNG も保存（参考用）
    fig.savefig(OUT_DIR / 'fig_4_wt_parameter_tuning.png', dpi=300, bbox_inches='tight')
    plt.close(fig)
    
    print("  ✅ fig_4_wt_parameter_tuning.pdf saved")
    print("  ✅ fig_4_wt_parameter_tuning.png saved (for reference)")
    
    # 統計情報を表示
    print("\n  数値データ:")
    print(f"    wt値: {wt_values}")
    print(f"    経路長: {np.round(path_lengths, 2)}")
    print(f"    地形コスト: {np.round(terrain_costs, 2)}")
    print(f"    最適値: wt={optimal_wt} (path_length={path_lengths[optimal_idx]:.2f}m, terrain_cost={terrain_costs[optimal_idx]:.2f})")


if __name__ == '__main__':
    print("="*60)
    print("新規作成: fig_4_wt_parameter_tuning.pdf")
    print("="*60)
    
    create_wt_parameter_tuning_figure()
    
    print("="*60)
    print("✅ wtパラメータチューニング図の作成完了")
    print("="*60)
