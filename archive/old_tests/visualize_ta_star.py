#!/usr/bin/env python3
"""
TA* vs A* vs AHA* の比較可視化スクリプト
"""

import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from pathlib import Path

# 日本語フォント設定
matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans', 'IPAexGothic', 'Noto Sans CJK JP']
matplotlib.rcParams['axes.unicode_minus'] = False

def load_latest_result():
    """最新の比較結果をロード"""
    results_dir = Path('/home/hayashi/thesis_work/results')
    result_files = sorted(results_dir.glob('quick_comparison_*.json'), reverse=True)
    
    if not result_files:
        raise FileNotFoundError("No comparison results found")
    
    latest_file = result_files[0]
    print(f"Loading: {latest_file}")
    
    with open(latest_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def plot_computation_time_comparison(data):
    """計算時間の比較グラフ"""
    planners = ['A*', 'AHA*', 'TA*']
    colors = {'A*': '#FF6B6B', 'AHA*': '#9B59B6', 'TA*': '#2ECC71'}
    
    scenarios = []
    times = {planner: [] for planner in planners}
    
    for scenario_name, scenario_data in data['results'].items():
        scenarios.append(scenario_data['scenario']['description'])
        
        for planner in planners:
            result = scenario_data['results'].get(planner, {})
            time_val = result.get('computation_time', None) if result.get('success') else None
            times[planner].append(time_val)
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    x = np.arange(len(scenarios))
    width = 0.25
    
    for i, planner in enumerate(planners):
        offset = width * (i - 1)
        values = [t if t is not None else 0 for t in times[planner]]
        bars = ax.bar(x + offset, values, width, label=planner, 
                     color=colors[planner], alpha=0.8)
        
        # 値ラベル
        for bar, val in zip(bars, times[planner]):
            if val is not None:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{val:.2f}s', ha='center', va='bottom', fontsize=9)
    
    ax.set_xlabel('シナリオ', fontsize=12)
    ax.set_ylabel('計算時間（秒）', fontsize=12)
    ax.set_title('計算時間比較：TA* vs A* vs AHA*', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(scenarios, rotation=15, ha='right')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    output_path = '/home/hayashi/thesis_work/figures/ta_star_time_comparison.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✓ 保存: {output_path}")
    plt.close()

def plot_nodes_comparison(data):
    """探索ノード数の比較グラフ（対数スケール）"""
    planners = ['A*', 'AHA*', 'TA*']
    colors = {'A*': '#FF6B6B', 'AHA*': '#9B59B6', 'TA*': '#2ECC71'}
    
    scenarios = []
    nodes = {planner: [] for planner in planners}
    
    for scenario_name, scenario_data in data['results'].items():
        scenarios.append(scenario_data['scenario']['description'])
        
        for planner in planners:
            result = scenario_data['results'].get(planner, {})
            node_val = result.get('nodes_explored', None) if result.get('success') else None
            nodes[planner].append(node_val if node_val else 0)
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    x = np.arange(len(scenarios))
    width = 0.25
    
    for i, planner in enumerate(planners):
        offset = width * (i - 1)
        ax.bar(x + offset, nodes[planner], width, label=planner,
              color=colors[planner], alpha=0.8)
    
    ax.set_xlabel('シナリオ', fontsize=12)
    ax.set_ylabel('探索ノード数（対数スケール）', fontsize=12)
    ax.set_title('探索効率比較：TA* vs A* vs AHA*', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(scenarios, rotation=15, ha='right')
    ax.legend(fontsize=11)
    ax.set_yscale('log')
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    output_path = '/home/hayashi/thesis_work/figures/ta_star_nodes_comparison.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✓ 保存: {output_path}")
    plt.close()

def plot_success_rate(data):
    """成功率の比較"""
    planners = ['A*', 'AHA*', 'TA*']
    colors = {'A*': '#FF6B6B', 'AHA*': '#9B59B6', 'TA*': '#2ECC71'}
    
    success_counts = {planner: 0 for planner in planners}
    total_scenarios = len(data['results'])
    
    for scenario_name, scenario_data in data['results'].items():
        for planner in planners:
            result = scenario_data['results'].get(planner, {})
            if result.get('success'):
                success_counts[planner] += 1
    
    success_rates = {planner: (count / total_scenarios) * 100 
                    for planner, count in success_counts.items()}
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    bars = ax.bar(planners, [success_rates[p] for p in planners],
                 color=[colors[p] for p in planners], alpha=0.8, edgecolor='black')
    
    for bar, planner in zip(bars, planners):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
               f'{success_rates[planner]:.1f}%\n({success_counts[planner]}/{total_scenarios})',
               ha='center', va='bottom', fontsize=12, fontweight='bold')
    
    ax.set_ylabel('成功率（%）', fontsize=12)
    ax.set_title('成功率比較：TA* vs A* vs AHA*', fontsize=14, fontweight='bold')
    ax.set_ylim(0, 110)
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    output_path = '/home/hayashi/thesis_work/figures/ta_star_success_rate.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✓ 保存: {output_path}")
    plt.close()

def plot_speedup_analysis(data):
    """TA*の高速化分析"""
    planners = ['A*', 'AHA*', 'TA*']
    
    scenarios = []
    speedups_vs_aha = []
    speedups_vs_a = []
    
    for scenario_name, scenario_data in data['results'].items():
        scenarios.append(scenario_data['scenario']['description'])
        
        ta_time = scenario_data['results'].get('TA*', {}).get('computation_time')
        aha_time = scenario_data['results'].get('AHA*', {}).get('computation_time')
        a_time = scenario_data['results'].get('A*', {}).get('computation_time')
        
        if ta_time and aha_time:
            speedups_vs_aha.append(aha_time / ta_time)
        else:
            speedups_vs_aha.append(0)
        
        if ta_time and a_time:
            speedups_vs_a.append(a_time / ta_time)
        else:
            speedups_vs_a.append(0)
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # vs AHA*
    x = np.arange(len(scenarios))
    bars1 = ax1.bar(x, speedups_vs_aha, color='#9B59B6', alpha=0.7, edgecolor='black')
    
    for bar, val in zip(bars1, speedups_vs_aha):
        if val > 0:
            ax1.text(bar.get_x() + bar.get_width()/2., bar.get_height(),
                    f'{val:.1f}x', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    ax1.axhline(y=1, color='r', linestyle='--', label='同速度', linewidth=2)
    ax1.set_xlabel('シナリオ', fontsize=12)
    ax1.set_ylabel('高速化率（倍）', fontsize=12)
    ax1.set_title('TA* vs AHA* 高速化率', fontsize=13, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(scenarios, rotation=15, ha='right')
    ax1.legend()
    ax1.grid(True, alpha=0.3, axis='y')
    
    # vs A*
    bars2 = ax2.bar(x, speedups_vs_a, color='#FF6B6B', alpha=0.7, edgecolor='black')
    
    for bar, val in zip(bars2, speedups_vs_a):
        if val > 0:
            ax2.text(bar.get_x() + bar.get_width()/2., bar.get_height(),
                    f'{val:.2f}x', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    ax2.axhline(y=1, color='r', linestyle='--', label='同速度', linewidth=2)
    ax2.set_xlabel('シナリオ', fontsize=12)
    ax2.set_ylabel('速度比（A*/TA*）', fontsize=12)
    ax2.set_title('TA* vs A* 速度比較', fontsize=13, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(scenarios, rotation=15, ha='right')
    ax2.legend()
    ax2.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    output_path = '/home/hayashi/thesis_work/figures/ta_star_speedup_analysis.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✓ 保存: {output_path}")
    plt.close()

def main():
    print("=" * 70)
    print("TA* 比較可視化スクリプト")
    print("=" * 70)
    
    # 出力ディレクトリ作成
    Path('/home/hayashi/thesis_work/figures').mkdir(parents=True, exist_ok=True)
    
    # 結果ロード
    data = load_latest_result()
    print(f"\nシナリオ数: {len(data['results'])}")
    print(f"プランナー数: {len(data['metadata']['planners'])}")
    
    print("\nグラフ生成中...")
    
    # グラフ生成
    plot_computation_time_comparison(data)
    plot_nodes_comparison(data)
    plot_success_rate(data)
    plot_speedup_analysis(data)
    
    print("\n" + "=" * 70)
    print("すべてのグラフ生成が完了しました！")
    print("出力先: /home/hayashi/thesis_work/figures/")
    print("=" * 70)

if __name__ == '__main__':
    main()
