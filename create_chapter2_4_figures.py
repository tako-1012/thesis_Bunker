#!/usr/bin/env python3
"""
章2と章4の図作成
"""
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

plt.rcParams['font.family'] = ['Noto Sans JP', 'Noto Sans CJK JP', 'DejaVu Sans']
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['font.size'] = 12

BASE = Path('/home/hayashi/thesis_work')
OUT_DIR = BASE / 'thisis_write' / 'figures'

# 章4の図: wtパラメータチューニング
def create_wt_parameter_tuning():
    """地形重みwtと性能指標の関係（hill_detourシナリオ）"""
    print("章4の図: wtパラメータチューニングを作成中...")
    
    with open(BASE / 'results' / 'wt_tuning.json', 'r') as f:
        data = json.load(f)
    
    wt_values = np.array(data['wt'])
    path_lengths = np.array(data['path_length'])
    terrain_costs = np.array(data['terrain_cost_avg'])
    
    fig, ax1 = plt.subplots(figsize=(10, 6))
    
    # 経路長（左軸）
    color1 = '#1f77b4'
    ax1.set_xlabel('地形重み wt', fontsize=14, fontweight='bold')
    ax1.set_ylabel('経路長 [m]', color=color1, fontsize=14, fontweight='bold')
    line1 = ax1.plot(wt_values, path_lengths, color=color1, marker='o', 
                     linewidth=2.5, markersize=8, label='経路長')
    ax1.tick_params(axis='y', labelcolor=color1)
    ax1.set_xlim(-0.1, 2.1)
    ax1.set_ylim([0, max(path_lengths) * 1.1])
    ax1.grid(True, alpha=0.3, linestyle='--')
    
    # 地形コスト（右軸）
    ax2 = ax1.twinx()
    color2 = '#d62728'
    ax2.set_ylabel('地形コスト（平均）', color=color2, fontsize=14, fontweight='bold')
    line2 = ax2.plot(wt_values, terrain_costs, color=color2, marker='s', 
                     linewidth=2.5, markersize=8, label='地形コスト')
    ax2.tick_params(axis='y', labelcolor=color2)
    ax2.set_ylim([0, max(terrain_costs) * 1.1])
    
    # wt=1.0の推奨値を強調
    optimal_wt = 1.0
    optimal_idx = np.argmin(np.abs(wt_values - optimal_wt))
    ax1.axvline(x=optimal_wt, color='green', linestyle='--', linewidth=2, alpha=0.6)
    ax1.plot(optimal_wt, path_lengths[optimal_idx], 'g*', markersize=20, 
             label='最適値 (wt=1.0)', zorder=10)
    
    ax1.text(optimal_wt, max(path_lengths) * 0.95, '最適値\n(wt=1.0)', 
             ha='center', fontsize=11, fontweight='bold',
             bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.7))
    
    # 凡例
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left', fontsize=11, framealpha=0.95)
    
    fig.tight_layout()
    fig.savefig(OUT_DIR / 'fig_wt_parameter_tuning.png', dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / 'fig_wt_parameter_tuning.pdf', bbox_inches='tight')
    plt.close(fig)
    
    print("  ✅ fig_wt_parameter_tuning.png/pdf 保存完了")


# 章2の図: ロボット外観はコピー
def copy_robot_overview():
    """ロボット外観図をコピー"""
    print("章2の図: ロボット外観をコピー中...")
    
    import shutil
    src = BASE / 'figures' / 'robot_overview.png'
    
    if src.exists():
        dst = OUT_DIR / 'robot_overview.png'
        shutil.copy(src, dst)
        print(f"  ✅ robot_overview.png コピー完了")
    else:
        print(f"  ⚠️ robot_overview.png が見つかりません（{src}）")


def main():
    print("="*60)
    print("章2・章4の図作成")
    print("="*60)
    
    copy_robot_overview()
    create_wt_parameter_tuning()
    
    print("="*60)
    print("✅ 完了")
    print("="*60)


if __name__ == '__main__':
    main()
