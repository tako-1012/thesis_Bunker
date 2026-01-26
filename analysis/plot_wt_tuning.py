#!/usr/bin/env python3
"""
w_tパラメータ調整結果のグラフ生成

実行方法:
    python analysis/plot_wt_tuning.py
"""
import json
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
from pathlib import Path

# 日本語フォント設定
matplotlib.rcParams['font.family'] = 'DejaVu Sans'
matplotlib.rcParams['font.size'] = 12

def plot_wt_tuning():
    """w_tパラメータ調整結果のグラフを作成"""
    
    # 実験結果を読み込み
    project_root = Path(__file__).parent.parent
    results_file = project_root / 'results' / 'wt_tuning.json'
    
    if not results_file.exists():
        print(f"Error: {results_file} が見つかりません")
        print("先に experiments/parameter_tuning_wt.py を実行してください")
        return
    
    with open(results_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # データを取り出し
    wt = data['wt']
    path_length = data['path_length']
    terrain_cost_avg = data['terrain_cost_avg']
    computation_time = data['computation_time']
    
    # 図を作成（3つのサブプロット）
    fig, axes = plt.subplots(3, 1, figsize=(8, 10))
    
    # (a) 経路長 vs w_t
    axes[0].plot(wt, path_length, 'o-', linewidth=2, markersize=6, color='#1f77b4')
    axes[0].axvline(x=1.0, color='red', linestyle='--', linewidth=1.5, 
                    label='$w_t=1.0$ (adopted value)', alpha=0.7)
    axes[0].set_ylabel('Path Length [m]', fontsize=12)
    axes[0].set_title('(a) Path Length vs Terrain Weight $w_t$', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3, linestyle='--')
    axes[0].legend(fontsize=10)
    axes[0].set_xlim(-0.1, 2.1)
    axes[0].set_ylim(20, 35)
    
    # (b) 点平均地形コスト vs w_t
    axes[1].plot(wt, terrain_cost_avg, 'o-', linewidth=2, markersize=6, color='#2ca02c')
    axes[1].axvline(x=1.0, color='red', linestyle='--', linewidth=1.5, 
                    label='$w_t=1.0$ (adopted value)', alpha=0.7)
    axes[1].set_ylabel('Average Terrain Cost', fontsize=12)
    axes[1].set_title('(b) Average Terrain Cost vs Terrain Weight $w_t$', fontsize=12, fontweight='bold')
    axes[1].grid(True, alpha=0.3, linestyle='--')
    axes[1].legend(fontsize=10)
    axes[1].set_xlim(-0.1, 2.1)
    axes[1].set_ylim(1.5, 3.5)
    
    # (c) 計算時間 vs w_t
    axes[2].plot(wt, computation_time, 'o-', linewidth=2, markersize=6, color='#ff7f0e')
    axes[2].axvline(x=1.0, color='red', linestyle='--', linewidth=1.5, 
                    label='$w_t=1.0$ (adopted value)', alpha=0.7)
    axes[2].set_xlabel('Terrain Weight $w_t$', fontsize=12)
    axes[2].set_ylabel('Computation Time [s]', fontsize=12)
    axes[2].set_title('(c) Computation Time vs Terrain Weight $w_t$', fontsize=12, fontweight='bold')
    axes[2].grid(True, alpha=0.3, linestyle='--')
    axes[2].legend(fontsize=10)
    axes[2].set_xlim(-0.1, 2.1)
    axes[2].set_ylim(0, 20)
    
    plt.tight_layout()
    
    # 保存
    figures_dir = project_root / 'figures'
    figures_dir.mkdir(parents=True, exist_ok=True)
    
    png_file = figures_dir / 'fig_4_wt_parameter_tuning.png'
    pdf_file = figures_dir / 'fig_4_wt_parameter_tuning.pdf'
    
    plt.savefig(png_file, dpi=300, bbox_inches='tight')
    plt.savefig(pdf_file, bbox_inches='tight')
    
    print("="*70)
    print("グラフを生成しました")
    print("="*70)
    print(f"\nPNG: {png_file}")
    print(f"PDF: {pdf_file}")
    
    # 統計情報を表示
    print("\n" + "="*70)
    print("統計情報")
    print("="*70)
    
    wt_array = np.array(wt)
    
    idx_1_0 = np.argmin(np.abs(wt_array - 1.0))
    print(f"\nw_t=1.0 (採用値):")
    print(f"  経路長: {path_length[idx_1_0]:.1f} m")
    print(f"  点平均地形コスト: {terrain_cost_avg[idx_1_0]:.2f}")
    print(f"  計算時間: {computation_time[idx_1_0]:.2f} 秒")
    
    print(f"\nw_t=0.0 (地形考慮なし):")
    idx_0_0 = np.argmin(np.abs(wt_array - 0.0))
    print(f"  経路長: {path_length[idx_0_0]:.1f} m")
    print(f"  点平均地形コスト: {terrain_cost_avg[idx_0_0]:.2f}")
    print(f"  計算時間: {computation_time[idx_0_0]:.2f} 秒")
    
    print(f"\nw_t=0.8 (地形重視が不足):")
    idx_0_8 = np.argmin(np.abs(wt_array - 0.8))
    print(f"  経路長: {path_length[idx_0_8]:.1f} m")
    print(f"  点平均地形コスト: {terrain_cost_avg[idx_0_8]:.2f}")
    reduction_0_8 = (1 - terrain_cost_avg[idx_0_8]/terrain_cost_avg[idx_0_0]) * 100
    print(f"  地形コスト削減率: {reduction_0_8:.0f}%")
    
    print(f"\nw_t=1.2 (地形重視が過剰):")
    idx_1_2 = np.argmin(np.abs(wt_array - 1.2))
    print(f"  経路長: {path_length[idx_1_2]:.1f} m")
    print(f"  計算時間: {computation_time[idx_1_2]:.2f} 秒")
    
    # グラフを表示（オプション）
    # plt.show()


if __name__ == '__main__':
    plot_wt_tuning()
