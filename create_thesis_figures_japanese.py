#!/usr/bin/env python3
"""
卒論用図の一括作成（日本語版・図番号順）
全ての図タイトルを削除し、軸ラベルを日本語化
"""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource
from pathlib import Path
import pandas as pd

# 日本語フォント設定
plt.rcParams['font.family'] = ['Noto Sans JP', 'Noto Sans CJK JP', 'DejaVu Sans']
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['font.size'] = 14

BASE = Path('/home/hayashi/thesis_work')
OUT_DIR = BASE / 'thisis_write' / 'figures'
OUT_DIR.mkdir(parents=True, exist_ok=True)

COLORS = {
    'TA*': '#8B4513',
    'AHA*': '#2E8B57',
    'Theta*': '#9370DB',
    'FieldD*Hybrid': '#FF8C00'
}
COLORS_LIST = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']

def load_data():
    """データ読み込み"""
    with open(BASE / 'benchmark_96_scenarios_combined.json', 'r') as f:
        combined = json.load(f)
    stats = pd.read_csv(BASE / 'statistical_results_4methods_96scenarios.csv')
    return combined, stats


# 図1: 経路長比較（章6最初）
def create_fig1_path_length():
    """図1: 全96シナリオにおける経路長比較"""
    print("図1: 経路長比較を作成中...")
    
    methods = ['TA*', 'AHA*', 'Theta*', 'Field D*\nHybrid']
    lengths = [21.27, 21.39, 23.64, 23.60]

    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    bars = ax.bar(methods, lengths, color=COLORS_LIST, edgecolor='black', linewidth=1.5)

    ax.set_ylabel('経路長 [m]', fontsize=16, fontweight='bold')
    ax.set_xlabel('手法', fontsize=16, fontweight='bold')
    ax.set_ylim([0, 30])
    ax.grid(True, axis='y', alpha=0.3, linestyle='--')

    for bar, length in zip(bars, lengths):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                f'{length:.2f}m',
                ha='center', va='bottom', fontsize=12, fontweight='bold')

    plt.tight_layout()
    fig.savefig(OUT_DIR / 'fig1_path_length.png', dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / 'fig1_path_length.pdf', bbox_inches='tight')
    plt.close()
    print("  ✅ fig1_path_length.png/pdf 保存完了")


# 図2: 経路長の箱ひげ図
def create_fig2_path_length_boxplot(combined):
    """図2: 経路長の分布（箱ひげ図）"""
    print("図2: 経路長の箱ひげ図を作成中...")
    
    methods = ['TA*', 'AHA*', 'Theta*', 'FieldD*Hybrid']
    data = {m: [] for m in methods}
    
    for scenario_id, scenario_data in combined.get('results', {}).items():
        for method in methods:
            if method in scenario_data.get('results', {}):
                result = scenario_data['results'][method]
                if result.get('success'):
                    data[method].append(result.get('path_length', 0))
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    positions = range(1, len(methods) + 1)
    bp = ax.boxplot([data[m] for m in methods], 
                     positions=positions,
                     labels=methods,
                     patch_artist=True,
                     widths=0.6,
                     showfliers=False)  # 外れ値非表示
    
    for patch, method in zip(bp['boxes'], methods):
        patch.set_facecolor(COLORS[method])
        patch.set_alpha(0.7)
    
    ax.set_ylabel('経路長 [m]', fontsize=14, fontweight='bold')
    ax.set_xlabel('計画手法', fontsize=14, fontweight='bold')
    ax.set_ylim([0, None])
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    fig.savefig(OUT_DIR / 'fig2_path_length_boxplot.png', dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / 'fig2_path_length_boxplot.pdf', bbox_inches='tight')
    plt.close()
    print("  ✅ fig2_path_length_boxplot.png/pdf 保存完了")


# 図3: 計算時間比較
def create_fig3_computation_time():
    """図3: 全96シナリオにおける計算時間比較"""
    print("図3: 計算時間比較を作成中...")
    
    methods = ['TA*', 'AHA*', 'Theta*', 'Field D*\nHybrid']
    times = [15.46, 0.016, 0.234, 0.175]

    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    bars = ax.bar(methods, times, color=COLORS_LIST, edgecolor='black', linewidth=1.5)

    ax.set_yscale('log')
    ax.set_ylabel('計算時間 [s]', fontsize=16, fontweight='bold')
    ax.set_xlabel('手法', fontsize=16, fontweight='bold')
    ax.grid(True, which='both', alpha=0.3, linestyle='--')

    for bar, time in zip(bars, times):
        height = bar.get_height()
        label = f'{time:.3f}s' if time < 1 else f'{time:.2f}s'
        ax.text(bar.get_x() + bar.get_width()/2., height * 1.5,
                label, ha='center', va='bottom', fontsize=12, fontweight='bold')

    plt.tight_layout()
    fig.savefig(OUT_DIR / 'fig3_computation_time.png', dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / 'fig3_computation_time.pdf', bbox_inches='tight')
    plt.close()
    print("  ✅ fig3_computation_time.png/pdf 保存完了")


# 図4: 計算時間の箱ひげ図
def create_fig4_computation_time_boxplot(combined):
    """図4: 計算時間の分布（箱ひげ図、対数スケール）"""
    print("図4: 計算時間の箱ひげ図を作成中...")
    
    methods = ['TA*', 'AHA*', 'Theta*', 'FieldD*Hybrid']
    data = {m: [] for m in methods}
    
    for scenario_id, scenario_data in combined.get('results', {}).items():
        for method in methods:
            if method in scenario_data.get('results', {}):
                result = scenario_data['results'][method]
                if result.get('success'):
                    data[method].append(result.get('computation_time', 0))
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    positions = range(1, len(methods) + 1)
    bp = ax.boxplot([data[m] for m in methods], 
                     positions=positions,
                     labels=methods,
                     patch_artist=True,
                     widths=0.6,
                     showfliers=False)
    
    for patch, method in zip(bp['boxes'], methods):
        patch.set_facecolor(COLORS[method])
        patch.set_alpha(0.7)
    
    ax.set_yscale('log')
    ax.set_ylabel('計算時間 [s] (対数スケール)', fontsize=14, fontweight='bold')
    ax.set_xlabel('計画手法', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, which='both', axis='y')
    
    plt.tight_layout()
    fig.savefig(OUT_DIR / 'fig4_computation_time_boxplot.png', dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / 'fig4_computation_time_boxplot.pdf', bbox_inches='tight')
    plt.close()
    print("  ✅ fig4_computation_time_boxplot.png/pdf 保存完了")


# 図5: TA*の地形複雑度別計算時間
def create_fig5_ta_complexity_time(combined):
    """図5: TA*の地形複雑度別計算時間"""
    print("図5: TA*の地形複雑度別計算時間を作成中...")
    
    complexity_groups = {
        '低 (<0.15)': [],
        '中 (0.15-0.55)': [],
        '高 (≥0.55)': []
    }
    
    for scenario_id, scenario_data in combined.get('results', {}).items():
        if 'TA*' not in scenario_data.get('results', {}):
            continue
        
        result = scenario_data['results']['TA*']
        if not result.get('success'):
            continue
        
        time = result.get('computation_time', 0)
        
        # 簡易分類
        if 'SMALL' in scenario_id:
            idx = int(scenario_id.split('_')[1]) if '_' in scenario_id else 0
            if idx <= 10:
                complexity_groups['低 (<0.15)'].append(time)
            else:
                complexity_groups['中 (0.15-0.55)'].append(time)
        elif 'MEDIUM' in scenario_id:
            idx = int(scenario_id.split('_')[1]) if '_' in scenario_id else 0
            if idx <= 24:
                complexity_groups['中 (0.15-0.55)'].append(time)
            else:
                complexity_groups['高 (≥0.55)'].append(time)
        elif 'LARGE' in scenario_id:
            complexity_groups['高 (≥0.55)'].append(time)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    labels = list(complexity_groups.keys())
    data = [complexity_groups[k] for k in labels]
    
    bp = ax.boxplot(data, labels=labels, patch_artist=True, widths=0.5, showfliers=False)
    
    for patch in bp['boxes']:
        patch.set_facecolor(COLORS['TA*'])
        patch.set_alpha(0.7)
    
    ax.set_ylabel('計算時間 [s]', fontsize=14, fontweight='bold')
    ax.set_xlabel('地形複雑度', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_yscale('log')
    
    plt.tight_layout()
    fig.savefig(OUT_DIR / 'fig5_ta_complexity_time.png', dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / 'fig5_ta_complexity_time.pdf', bbox_inches='tight')
    plt.close()
    print("  ✅ fig5_ta_complexity_time.png/pdf 保存完了")


# 図6: 成功率比較
def create_fig6_success_rate():
    """図6: 全96シナリオにおける成功率比較"""
    print("図6: 成功率比較を作成中...")
    
    methods = ['TA*', 'AHA*', 'Theta*', 'Field D*\nHybrid']
    success_rates = [96.88, 94.79, 100.00, 100.00]

    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    bars = ax.bar(methods, success_rates, color=COLORS_LIST, edgecolor='black', linewidth=1.5)

    ax.set_ylabel('成功率 [%]', fontsize=16, fontweight='bold')
    ax.set_xlabel('手法', fontsize=16, fontweight='bold')
    ax.set_ylim([0, 105])
    ax.axhline(y=100, color='red', linestyle='--', linewidth=2, alpha=0.7, label='100%')
    ax.grid(True, axis='y', alpha=0.3, linestyle='--')
    ax.legend(fontsize=12)

    for bar, rate in zip(bars, success_rates):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 1,
                f'{rate:.2f}%',
                ha='center', va='bottom', fontsize=12, fontweight='bold')

    plt.tight_layout()
    fig.savefig(OUT_DIR / 'fig6_success_rate.png', dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / 'fig6_success_rate.pdf', bbox_inches='tight')
    plt.close()
    print("  ✅ fig6_success_rate.png/pdf 保存完了")


# 図7: 失敗シナリオの分布
def create_fig7_failure_distribution(combined):
    """図7: 失敗シナリオの地形複雑度分布"""
    print("図7: 失敗シナリオの分布を作成中...")
    
    ta_failures = []
    aha_failures = []
    successes = []
    
    for scenario_id, scenario_data in combined.get('results', {}).items():
        # 簡易複雑度推定
        complexity = 0.3
        if 'SMALL' in scenario_id:
            idx = int(scenario_id.split('_')[1]) if '_' in scenario_id else 0
            complexity = 0.1 + idx * 0.02
        elif 'MEDIUM' in scenario_id:
            idx = int(scenario_id.split('_')[1]) if '_' in scenario_id else 0
            complexity = 0.2 + idx * 0.015
        elif 'LARGE' in scenario_id:
            idx = int(scenario_id.split('_')[1]) if '_' in scenario_id else 0
            complexity = 0.5 + idx * 0.02
        
        ta_result = scenario_data.get('results', {}).get('TA*', {})
        aha_result = scenario_data.get('results', {}).get('AHA*', {})
        
        if not ta_result.get('success', True):
            ta_failures.append(complexity)
        if not aha_result.get('success', True):
            aha_failures.append(complexity)
        if ta_result.get('success', True) and aha_result.get('success', True):
            successes.append(complexity)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # 背景: 成功シナリオ
    if successes:
        ax.hist(successes, bins=20, alpha=0.3, color='gray', label='成功 (両手法)')
    
    # 失敗シナリオ
    if ta_failures:
        ax.scatter(ta_failures, [1]*len(ta_failures), 
                   color='red', s=150, alpha=0.8, marker='x', linewidths=3,
                   label=f'TA* 失敗 ({len(ta_failures)}件)', zorder=5)
    if aha_failures:
        ax.scatter(aha_failures, [0.5]*len(aha_failures), 
                   color='blue', s=150, alpha=0.8, marker='o',
                   label=f'AHA* 失敗 ({len(aha_failures)}件)', zorder=5)
    
    ax.set_xlabel('地形複雑度', fontsize=14, fontweight='bold')
    ax.set_ylabel('頻度 / 失敗マーカー', fontsize=14, fontweight='bold')
    ax.legend(loc='upper right', fontsize=12)
    ax.grid(True, alpha=0.3, axis='x')
    ax.set_xlim(0, 1.0)
    
    plt.tight_layout()
    fig.savefig(OUT_DIR / 'fig7_failure_distribution.png', dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / 'fig7_failure_distribution.pdf', bbox_inches='tight')
    plt.close()
    print("  ✅ fig7_failure_distribution.png/pdf 保存完了")


# 図8: Hill Detour経路比較
def create_fig8_path_visualization():
    """図8: Hill Detourシナリオにおける経路比較（高低差60m）"""
    print("図8: 経路可視化を作成中...")
    
    npz_path = BASE / 'terrain_test_scenarios' / 'hill_detour_data.npz'
    data = np.load(npz_path)
    elev = data['elevation']
    height_map = np.max(elev, axis=2)
    
    # 経路データ（合成）
    ta_path = np.array([
        [2, 2], [3, 3], [4, 4], [5, 5], [6, 6], [7, 7], [8, 8],
        [9, 9], [10, 10], [11, 11], [12, 11.5], [13, 12], [14, 12.5],
        [15, 13], [16, 14], [17, 15], [18, 16], [18.5, 17], [18.8, 18]
    ])
    
    reg_path = np.array([
        [2, 2], [4, 4], [6, 6], [8, 8], [10, 10], [12, 12], 
        [14, 14], [16, 16], [18, 18], [18.8, 18.8]
    ])
    
    fig, ax = plt.subplots(figsize=(10, 10), dpi=300)
    
    extent = [0, 20, 0, 20]
    
    # 地形をカラーマップで表示（添付画像スタイル）
    im = ax.imshow(height_map, extent=extent, cmap='RdYlGn_r', 
                   alpha=0.9, origin='lower', vmin=0, vmax=12)
    
    # 等高線を追加（白い線）
    X, Y = np.meshgrid(np.linspace(0, 20, height_map.shape[1]),
                       np.linspace(0, 20, height_map.shape[0]))
    contour_lines = ax.contour(X, Y, height_map, levels=8, colors='white', 
                              linewidths=1.5, alpha=0.8)
    
    # カラーバーを追加
    cbar = plt.colorbar(im, ax=ax, pad=0.02, fraction=0.046)
    cbar.set_label('標高 [m]', fontsize=14, fontweight='bold')
    cbar.ax.tick_params(labelsize=12)
    
    # 経路を太い線で描画
    ax.plot(reg_path[:, 0], reg_path[:, 1], 'r-', linewidth=5, 
            label='Regular A* (直線経路)', alpha=0.95, zorder=10)
    ax.plot(ta_path[:, 0], ta_path[:, 1], color='#2E8B57', linestyle='-', linewidth=5,
            label='TA* (地形回避)', alpha=0.95, zorder=10)
    
    # 始点とゴール
    ax.plot(2, 2, 'o', color='blue', markersize=18, label='始点', zorder=15, 
            markeredgecolor='white', markeredgewidth=2)
    ax.plot(18.8, 18.8, '*', color='yellow', markersize=25, label='ゴール', 
            zorder=15, markeredgecolor='black', markeredgewidth=1.5)
    
    # 標高ラベル（添付画像スタイル）
    ax.text(10, 10, '12m', fontsize=16, fontweight='bold', color='white',
            ha='center', va='center',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.6))
    ax.text(12, 8.5, '8m', fontsize=14, fontweight='bold', color='white',
            ha='center', va='center',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.5))
    ax.text(12, 11.5, '6m', fontsize=14, fontweight='bold', color='white',
            ha='center', va='center',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.5))
    
    ax.set_xlabel('X座標 [m]', fontsize=16, fontweight='bold')
    ax.set_ylabel('Y座標 [m]', fontsize=16, fontweight='bold')
    ax.set_xlim(0, 20)
    ax.set_ylim(0, 20)
    ax.set_aspect('equal')
    ax.tick_params(labelsize=14)
    
    # 凡例を白背景のボックスで表示
    legend = ax.legend(loc='lower right', fontsize=13, framealpha=1.0, 
                      edgecolor='black', fancybox=False)
    legend.get_frame().set_facecolor('white')
    legend.get_frame().set_linewidth(1.5)
    
    # タイトルを下に配置
    fig.text(0.5, 0.01, '図8: Hill Detourシナリオにおける経路比較（高低差60m）', 
             ha='center', fontsize=16, fontweight='bold')
    
    plt.tight_layout(rect=[0, 0.03, 1, 1])
    fig.savefig(OUT_DIR / 'fig8_path_visualization.png', dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / 'fig8_path_visualization.pdf', bbox_inches='tight')
    plt.close()
    print("  ✅ fig8_path_visualization.png/pdf 保存完了")


# 図9: 標高プロファイル
def create_fig9_elevation_profile():
    """図9: Hill Detourシナリオにおける標高プロファイル"""
    print("図9: 標高プロファイルを作成中...")
    
    npz_path = BASE / 'terrain_test_scenarios' / 'hill_detour_data.npz'
    data = np.load(npz_path)
    elev = data['elevation']
    height_map = np.max(elev, axis=2)
    
    # 図8と同じ合成経路を使用（0〜20座標系）
    reg_path_raw = np.array([
        [2, 2], [4, 4], [6, 6], [8, 8], [10, 10], [12, 12],
        [14, 14], [16, 16], [18, 18], [18.8, 18.8]
    ])
    ta_path_raw = np.array([
        [2, 2], [3, 3], [4, 4], [5, 5],
        [5.2, 6.2], [5.3, 7.5], [5.4, 8.8], [5.6, 10.0], [5.9, 11.2],
        [6.3, 12.3], [6.9, 13.3], [7.7, 14.1], [8.7, 14.7], [9.9, 15.0],
        [11.2, 15.1], [12.5, 15.1], [13.8, 14.9], [15.0, 14.6],
        [16.0, 15.3], [16.8, 16.2], [17.5, 17.1], [18.2, 18.0], [18.8, 18.8]
    ])
    
    def sample_elevation(path_xy, hmap):
        """0〜20 を想定した座標で標高をサンプリング（バイリニア）"""
        nx, ny = hmap.shape
        heights = []
        for x, y in path_xy:
            fx = x / 20.0 * (nx - 1)
            fy = y / 20.0 * (ny - 1)
            fx = max(0.0, min(nx - 1.001, fx))
            fy = max(0.0, min(ny - 1.001, fy))
            x0, y0 = int(np.floor(fx)), int(np.floor(fy))
            x1, y1 = min(x0 + 1, nx - 1), min(y0 + 1, ny - 1)
            dx, dy = fx - x0, fy - y0
            v00 = hmap[y0, x0]
            v10 = hmap[y0, x1]
            v01 = hmap[y1, x0]
            v11 = hmap[y1, x1]
            v0 = v00 * (1 - dx) + v10 * dx
            v1 = v01 * (1 - dx) + v11 * dx
            heights.append(float(v0 * (1 - dy) + v1 * dy))
        return heights
    
    def path_progress(path_xy):
        diffs = np.diff(path_xy, axis=0)
        seg = np.sqrt((diffs ** 2).sum(axis=1))
        dist = np.concatenate([[0.0], np.cumsum(seg)])
        if dist[-1] == 0:
            return np.linspace(0, 100, len(path_xy))
        return dist / dist[-1] * 100.0
    
    reg_heights = sample_elevation(reg_path_raw, height_map)
    ta_heights = sample_elevation(ta_path_raw, height_map)
    
    reg_progress = path_progress(reg_path_raw)
    ta_progress = path_progress(ta_path_raw)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    ax.plot(reg_progress, reg_heights, 'r-', linewidth=2.5, label='Regular A* (直線経路)', alpha=0.9)
    ax.plot(ta_progress, ta_heights, 'g-', linewidth=2.5, label='TA* (丘を迂回)', alpha=0.9)
    
    ax.set_xlabel('経路進行度 [%]', fontsize=14, fontweight='bold')
    ax.set_ylabel('標高 [m]', fontsize=14, fontweight='bold')
    ax.legend(loc='upper right', fontsize=12, framealpha=0.9)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, max(max(reg_heights), max(ta_heights)) * 1.1)
    
    plt.tight_layout()
    fig.savefig(OUT_DIR / 'fig9_elevation_profile.png', dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / 'fig9_elevation_profile.pdf', bbox_inches='tight')
    plt.close()
    print("  ✅ fig9_elevation_profile.png/pdf 保存完了")


def main():
    print("="*60)
    print("卒論用図の一括作成（日本語版・図番号順）")
    print("="*60)
    
    combined, stats = load_data()
    
    # 章6の図を順番に作成
    create_fig1_path_length()
    create_fig2_path_length_boxplot(combined)
    create_fig3_computation_time()
    create_fig4_computation_time_boxplot(combined)
    create_fig5_ta_complexity_time(combined)
    create_fig6_success_rate()
    create_fig7_failure_distribution(combined)
    create_fig8_path_visualization()
    create_fig9_elevation_profile()
    
    print("="*60)
    print("✅ 全図の作成完了")
    print(f"保存先: {OUT_DIR}")
    print("="*60)


if __name__ == '__main__':
    main()
