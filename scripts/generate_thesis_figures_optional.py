#!/usr/bin/env python3
"""
卒論第6章用のオプション図表生成スクリプト
図D: 地形複雑度別の成功率
図I: TA*計算時間のヒストグラム
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
    return combined

def figure_d_complexity_success_rate(combined, output_dir):
    """図D: 地形複雑度別の成功率"""
    print("Generating Figure D: Success Rate by Terrain Complexity...")
    
    methods = ['TA*', 'AHA*', 'Theta*', 'FieldD*Hybrid']
    complexity_levels = ['Low', 'Medium', 'High']
    
    # データ集計
    data = {level: {m: {'success': 0, 'total': 0} for m in methods} 
            for level in complexity_levels}
    
    for scenario_id, scenario_data in combined.get('results', {}).items():
        # 簡易複雑度推定
        if 'SMALL' in scenario_id:
            idx = int(scenario_id.split('_')[1]) if '_' in scenario_id else 0
            if idx < 10:
                level = 'Low'
            elif idx < 20:
                level = 'Medium'
            else:
                level = 'High'
        elif 'MEDIUM' in scenario_id:
            idx = int(scenario_id.split('_')[1]) if '_' in scenario_id else 0
            if idx < 10:
                level = 'Low'
            else:
                level = 'Medium'
        elif 'LARGE' in scenario_id:
            level = 'High'
        else:
            level = 'Medium'
        
        for method in methods:
            if method in scenario_data.get('results', {}):
                result = scenario_data['results'][method]
                data[level][method]['total'] += 1
                if result.get('success', True):
                    data[level][method]['success'] += 1
    
    # 成功率計算
    success_rates = {level: [] for level in complexity_levels}
    for level in complexity_levels:
        for method in methods:
            total = data[level][method]['total']
            success = data[level][method]['success']
            rate = (success / total * 100) if total > 0 else 0
            success_rates[level].append(rate)
    
    # プロット
    fig, ax = plt.subplots(figsize=(10, 6))
    
    x = np.arange(len(complexity_levels))
    width = 0.2
    
    for i, method in enumerate(methods):
        rates = [success_rates[level][i] for level in complexity_levels]
        offset = (i - 1.5) * width
        bars = ax.bar(x + offset, rates, width, 
                      label=method, color=COLORS[method], alpha=0.8)
        
        # 値表示
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}%',
                    ha='center', va='bottom', fontsize=8)
    
    ax.set_ylabel('Success Rate [%]', fontsize=12, fontweight='bold')
    ax.set_xlabel('Terrain Complexity', fontsize=12, fontweight='bold')
    ax.set_title('Figure D: Success Rate by Terrain Complexity Level', 
                 fontsize=13, fontweight='bold', pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(complexity_levels)
    ax.legend(loc='lower left', fontsize=11, ncol=2)
    ax.set_ylim(90, 102)
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    fig.savefig(output_dir / 'figD_complexity_success_rate.png', dpi=300, bbox_inches='tight')
    fig.savefig(output_dir / 'figD_complexity_success_rate.pdf', bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: figD_complexity_success_rate.png/pdf")

def figure_i_ta_time_histogram(combined, output_dir):
    """図I: TA*計算時間のヒストグラム"""
    print("Generating Figure I: TA* Computation Time Histogram...")
    
    times = []
    for scenario_id, scenario_data in combined.get('results', {}).items():
        ta_result = scenario_data.get('results', {}).get('TA*', {})
        if ta_result.get('success'):
            times.append(ta_result.get('computation_time', 0))
    
    times = np.array(times)
    mean_time = np.mean(times)
    median_time = np.median(times)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # ヒストグラム
    n, bins, patches = ax.hist(times, bins=30, color=COLORS['TA*'], 
                               alpha=0.7, edgecolor='black')
    
    # 平均・中央値
    ax.axvline(mean_time, color='red', linestyle='--', linewidth=2.5,
               label=f'Mean: {mean_time:.2f}s')
    ax.axvline(median_time, color='blue', linestyle='--', linewidth=2.5,
               label=f'Median: {median_time:.2f}s')
    
    ax.set_xlabel('Computation Time [s]', fontsize=12, fontweight='bold')
    ax.set_ylabel('Frequency', fontsize=12, fontweight='bold')
    ax.set_title('Figure I: TA* Computation Time Distribution (93 Successful Runs)', 
                 fontsize=13, fontweight='bold', pad=15)
    ax.legend(loc='upper right', fontsize=11)
    ax.grid(True, alpha=0.3, axis='y')
    
    # 統計情報
    stats_text = f'n = {len(times)}\nStd: {np.std(times):.2f}s\nMax: {np.max(times):.2f}s'
    ax.text(0.98, 0.65, stats_text, transform=ax.transAxes,
            fontsize=10, verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    fig.savefig(output_dir / 'figI_ta_time_histogram.png', dpi=300, bbox_inches='tight')
    fig.savefig(output_dir / 'figI_ta_time_histogram.pdf', bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: figI_ta_time_histogram.png/pdf")

def main():
    print("="*60)
    print("卒論第6章用 オプション図表生成")
    print("="*60)
    
    output_dir = Path('/home/hayashi/thesis_work/figures')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    combined = load_data()
    
    figure_d_complexity_success_rate(combined, output_dir)
    figure_i_ta_time_histogram(combined, output_dir)
    
    print("="*60)
    print("✅ オプション図表（D, I）の生成完了")
    print(f"保存先: {output_dir}")
    print("="*60)

if __name__ == '__main__':
    main()
