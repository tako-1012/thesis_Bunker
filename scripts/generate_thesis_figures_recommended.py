#!/usr/bin/env python3
"""
卒論第6章用の推奨図表生成スクリプト
図B: 経路長の箱ひげ図
図G: 計算時間 vs 成功率
図H: 失敗シナリオの分布
"""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
import pandas as pd

plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 10

COLORS = {
    'TA*': '#8B4513',
    'AHA*': '#2E8B57',
    'Theta*': '#9370DB',
    'FieldD*Hybrid': '#FF8C00'
}

def load_data():
    base = Path('/home/hayashi/thesis_work')
    with open(base / 'benchmark_96_scenarios_combined.json', 'r') as f:
        combined = json.load(f)
    stats = pd.read_csv(base / 'statistical_results_4methods_96scenarios.csv')
    return combined, stats

def figure_b_path_length_boxplot(combined, output_dir):
    """図B: 経路長の箱ひげ図"""
    print("Generating Figure B: Path Length Box Plot...")
    
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
                     widths=0.6)
    
    for patch, method in zip(bp['boxes'], methods):
        patch.set_facecolor(COLORS[method])
        patch.set_alpha(0.7)
    
    ax.set_ylabel('Path Length [m]', fontsize=12, fontweight='bold')
    ax.set_xlabel('Planning Method', fontsize=12, fontweight='bold')
    ax.set_title('Figure B: Path Length Distribution (96 Scenarios)', 
                 fontsize=13, fontweight='bold', pad=15)
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    fig.savefig(output_dir / 'figB_path_length_boxplot.png', dpi=300, bbox_inches='tight')
    fig.savefig(output_dir / 'figB_path_length_boxplot.pdf', bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: figB_path_length_boxplot.png/pdf")

def figure_g_time_vs_success(stats, output_dir):
    """図G: 計算時間 vs 成功率"""
    print("Generating Figure G: Computation Time vs Success Rate...")
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    for _, row in stats.iterrows():
        method = row['method']
        avg_time = row['mean']
        success_rate = row['success_rate']
        
        ax.scatter(avg_time, success_rate, 
                   color=COLORS.get(method, 'gray'), 
                   s=250, alpha=0.8, edgecolors='black', linewidths=2)
        ax.annotate(method, (avg_time, success_rate),
                    xytext=(15, 15), textcoords='offset points', 
                    fontsize=11, fontweight='bold',
                    bbox=dict(boxstyle='round', fc='white', alpha=0.8))
    
    ax.set_xscale('log')
    ax.set_xlabel('Average Computation Time [s] (log scale)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Success Rate [%]', fontsize=12, fontweight='bold')
    ax.set_title('Figure G: Computation Efficiency vs Reliability Trade-off', 
                 fontsize=13, fontweight='bold', pad=15)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(90, 102)
    
    # 理想位置を示す
    ax.annotate('Ideal\n(Fast & Reliable)', xy=(0, 0),
                xytext=(0.05, 0.95), textcoords='axes fraction',
                fontsize=10, color='gray', style='italic', va='top')
    
    plt.tight_layout()
    fig.savefig(output_dir / 'figG_time_vs_success.png', dpi=300, bbox_inches='tight')
    fig.savefig(output_dir / 'figG_time_vs_success.pdf', bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: figG_time_vs_success.png/pdf")

def figure_h_failure_distribution(combined, output_dir):
    """図H: 失敗シナリオの地形複雑度分布"""
    print("Generating Figure H: Failure Scenario Distribution...")
    
    # 失敗シナリオの抽出
    ta_failures = []
    aha_failures = []
    successes = []
    
    for scenario_id, scenario_data in combined.get('results', {}).items():
        # 簡易複雑度推定（サイズベース）
        complexity = 0.3  # デフォルト
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
        ax.hist(successes, bins=20, alpha=0.3, color='gray', label='Success (both methods)')
    
    # 失敗シナリオ
    if ta_failures:
        ax.scatter(ta_failures, [1]*len(ta_failures), 
                   color='red', s=150, alpha=0.8, marker='x', linewidths=3,
                   label=f'TA* Failures ({len(ta_failures)})', zorder=5)
    if aha_failures:
        ax.scatter(aha_failures, [0.5]*len(aha_failures), 
                   color='blue', s=150, alpha=0.8, marker='o',
                   label=f'AHA* Failures ({len(aha_failures)})', zorder=5)
    
    ax.set_xlabel('Terrain Complexity', fontsize=12, fontweight='bold')
    ax.set_ylabel('Frequency / Failure Markers', fontsize=12, fontweight='bold')
    ax.set_title('Figure H: Failure Scenario Distribution by Terrain Complexity', 
                 fontsize=13, fontweight='bold', pad=15)
    ax.legend(loc='upper right', fontsize=11)
    ax.grid(True, alpha=0.3, axis='x')
    ax.set_xlim(0, 1.0)
    
    plt.tight_layout()
    fig.savefig(output_dir / 'figH_failure_distribution.png', dpi=300, bbox_inches='tight')
    fig.savefig(output_dir / 'figH_failure_distribution.pdf', bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: figH_failure_distribution.png/pdf")

def main():
    print("="*60)
    print("卒論第6章用 推奨図表生成")
    print("="*60)
    
    output_dir = Path('/home/hayashi/thesis_work/figures')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    combined, stats = load_data()
    
    figure_b_path_length_boxplot(combined, output_dir)
    figure_g_time_vs_success(stats, output_dir)
    figure_h_failure_distribution(combined, output_dir)
    
    print("="*60)
    print("✅ 推奨図表（B, G, H）の生成完了")
    print(f"保存先: {output_dir}")
    print("="*60)

if __name__ == '__main__':
    main()
