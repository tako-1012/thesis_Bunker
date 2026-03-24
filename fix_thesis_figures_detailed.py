#!/usr/bin/env python3
"""
卒論本体用図の修正スクリプト（詳細版）
- figB_path_length_boxplot.png: Y軸を0mからスタート
- figD_complexity_success_rate.png: Y軸を0%からスタート
- figF_tradeoff_path_terrain.png: 両軸とも0からスタート
- figG_time_vs_success.png: Y軸（成功率）を0%からスタート
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
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300

COLORS = {
    'TA*': '#8B4513',
    'AHA*': '#2E8B57',
    'Theta*': '#9370DB',
    'FieldD*Hybrid': '#FF8C00'
}

BASE = Path('/home/hayashi/thesis_work')
OUT_DIR = BASE / 'figures'

def load_data():
    """データをロード"""
    with open(BASE / 'benchmark_96_scenarios_combined.json', 'r') as f:
        combined = json.load(f)
    stats = pd.read_csv(BASE / 'statistical_results_4methods_96scenarios.csv')
    return combined, stats


def figure_b_path_length_boxplot_fixed(combined):
    """figB: 経路長の箱ひげ図（Y軸0m~）"""
    print("Generating Figure B: Path Length Box Plot (Y-axis from 0m)...")
    
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
                     showfliers=False)  # 外れ値を非表示
    
    for patch, method in zip(bp['boxes'], methods):
        patch.set_facecolor(COLORS[method])
        patch.set_alpha(0.7)
    
    ax.set_ylabel('Path Length [m]', fontsize=12, fontweight='bold')
    ax.set_xlabel('Planning Method', fontsize=12, fontweight='bold')
    ax.set_ylim([0, None])  # 修正: 0からスタート
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    fig.savefig(OUT_DIR / 'figB_path_length_boxplot.png', dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / 'figB_path_length_boxplot.pdf', bbox_inches='tight')
    plt.close(fig)
    print("  ✅ figB_path_length_boxplot.png/pdf saved")


def figure_d_complexity_success_rate_fixed(combined):
    """figD: 地形複雑度別の成功率（Y軸0%~）"""
    print("Generating Figure D: Success Rate by Terrain Complexity (Y-axis from 0%)...")
    
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
    ax.set_xticks(x)
    ax.set_xticklabels(complexity_levels)
    ax.legend(loc='lower left', fontsize=11, ncol=2)
    ax.set_ylim([0, 105])  # 修正: 0からスタート
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    fig.savefig(OUT_DIR / 'figD_complexity_success_rate.png', dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / 'figD_complexity_success_rate.pdf', bbox_inches='tight')
    plt.close(fig)
    print("  ✅ figD_complexity_success_rate.png/pdf saved")


def figure_g_time_vs_success_fixed(stats):
    """figG: 計算時間vs成功率（Y軸成功率を0%から）"""
    print("Generating Figure G: Computation Time vs Success Rate (Y-axis from 0%)...")
    
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
    ax.grid(True, alpha=0.3)
    ax.set_ylim([0, 105])  # 修正: 0からスタート
    
    # 理想位置を示す
    ax.annotate('Ideal\n(Fast & Reliable)', xy=(0, 0),
                xytext=(0.05, 0.95), textcoords='axes fraction',
                fontsize=10, color='gray', style='italic', va='top')
    
    plt.tight_layout()
    fig.savefig(OUT_DIR / 'figG_time_vs_success.png', dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / 'figG_time_vs_success.pdf', bbox_inches='tight')
    plt.close(fig)
    print("  ✅ figG_time_vs_success.png/pdf saved")


if __name__ == '__main__':
    print("="*60)
    print("修正: 卒論本体用図")
    print("="*60)
    
    combined, stats = load_data()
    
    figure_b_path_length_boxplot_fixed(combined)
    figure_d_complexity_success_rate_fixed(combined)
    figure_g_time_vs_success_fixed(stats)
    
    print("="*60)
    print("✅ 修正完了: B, D, G")
    print("="*60)
