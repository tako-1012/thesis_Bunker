#!/usr/bin/env python3
"""
卒論本体用図の修正スクリプト
- fig2_path_length.png: Y軸を0mからスタート
- fig3_success_rate.png: Y軸を0%からスタート
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['font.size'] = 14
plt.rcParams['axes.labelsize'] = 16
plt.rcParams['axes.titlesize'] = 18
plt.rcParams['xtick.labelsize'] = 14
plt.rcParams['ytick.labelsize'] = 14

OUT_DIR = Path('/home/hayashi/thesis_work/figures')
OUT_DIR.mkdir(parents=True, exist_ok=True)

COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']

def fig2_path_length_fixed():
    """fig2: 経路長比較（Y軸0m~30m）"""
    print("Creating fig2_path_length.png (Y-axis from 0m)...")
    
    methods = ['TA*', 'AHA*', 'Theta*', 'Field D*\nHybrid']
    lengths = [21.27, 21.39, 23.64, 23.60]

    fig, ax = plt.subplots(figsize=(6, 4.5), dpi=300)
    bars = ax.bar(methods, lengths, color=COLORS, edgecolor='black', linewidth=1.5)

    ax.set_ylabel('Path Length [m]', fontsize=16, fontweight='bold')
    ax.set_xlabel('Method', fontsize=16, fontweight='bold')
    ax.set_ylim([0, 30])  # 修正: 0からスタート
    ax.grid(True, axis='y', alpha=0.3, linestyle='--')

    for bar, length in zip(bars, lengths):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{length:.2f}m',
                ha='center', va='bottom', fontsize=12, fontweight='bold')

    plt.tight_layout()
    plt.savefig(OUT_DIR / 'fig2_path_length.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("  ✅ fig2_path_length.png saved")


def fig3_success_rate_fixed():
    """fig3: 成功率比較（Y軸0%~105%）"""
    print("Creating fig3_success_rate.png (Y-axis from 0%)...")
    
    methods = ['TA*', 'AHA*', 'Theta*', 'Field D*\nHybrid']
    success_rates = [96.88, 94.79, 100.00, 100.00]

    fig, ax = plt.subplots(figsize=(6, 4.5), dpi=300)
    bars = ax.bar(methods, success_rates, color=COLORS, edgecolor='black', linewidth=1.5)

    ax.set_ylabel('Success Rate [%]', fontsize=16, fontweight='bold')
    ax.set_xlabel('Method', fontsize=16, fontweight='bold')
    ax.set_ylim([0, 105])  # 修正: 0からスタート
    ax.axhline(y=100, color='red', linestyle='--', linewidth=2, alpha=0.7, label='100%')
    ax.grid(True, axis='y', alpha=0.3, linestyle='--')
    ax.legend(fontsize=12)

    for bar, rate in zip(bars, success_rates):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{rate:.2f}%',
                ha='center', va='bottom', fontsize=12, fontweight='bold')

    plt.tight_layout()
    plt.savefig(OUT_DIR / 'fig3_success_rate.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("  ✅ fig3_success_rate.png saved")


if __name__ == '__main__':
    print("="*60)
    print("修正: アブストラクト用図（fig2, fig3）")
    print("="*60)
    
    fig2_path_length_fixed()
    fig3_success_rate_fixed()
    
    print("="*60)
    print("✅ アブストラクト用図の修正完了")
    print("="*60)
