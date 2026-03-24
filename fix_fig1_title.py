#!/usr/bin/env python3
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# 高解像度設定
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['font.size'] = 14
plt.rcParams['axes.labelsize'] = 16
plt.rcParams['axes.titlesize'] = 18
plt.rcParams['xtick.labelsize'] = 14
plt.rcParams['ytick.labelsize'] = 14

# データ
methods = ['AHA*', 'Theta*', 'FieldD*Hybrid', 'TA*']
mean_times = [0.016, 0.234, 0.495, 15.46]
median_times = [0.016, 0.089, 0.406, 6.83]

x = np.arange(len(methods))
width = 0.35

fig, ax = plt.subplots(figsize=(10, 6), dpi=300)

# 平均値の棒（濃い色）
bars1 = ax.bar(x - width/2, mean_times, width, 
               label='Mean',
               color=['#2ca02c', '#ff7f0e', '#9467bd', '#8c564b'],
               edgecolor='black', linewidth=1.5)

# 中央値の棒（ハッチング）
bars2 = ax.bar(x + width/2, median_times, width,
               label='Median',
               color=['#2ca02c', '#ff7f0e', '#9467bd', '#8c564b'],
               alpha=0.6, hatch='///', edgecolor='black', linewidth=1.5)

# タイトル（簡潔に修正）
ax.set_title('Computation Time Comparison', fontsize=18, fontweight='bold', pad=20)

# 対数スケール
ax.set_yscale('log')
ax.set_ylabel('Computation Time (seconds)', fontsize=16, fontweight='bold')
ax.set_xlabel('Method', fontsize=16, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(methods)
ax.legend(fontsize=12, loc='upper left')
ax.grid(True, which='both', alpha=0.3, linestyle='--', axis='y')

# 数値表示（平均値）
for i, (bar, time) in enumerate(zip(bars1, mean_times)):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height * 1.2,
            f'{time:.3f}s' if time < 1 else f'{time:.2f}s',
            ha='center', va='bottom', fontsize=11, fontweight='bold')

# 数値表示（中央値）
for i, (bar, time) in enumerate(zip(bars2, median_times)):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height * 1.2,
            f'{time:.3f}s' if time < 1 else f'{time:.2f}s',
            ha='center', va='bottom', fontsize=11, fontweight='bold')

plt.tight_layout()
plt.savefig('figures/fig1_computation_time_4methods.png', dpi=300, bbox_inches='tight')
plt.close()
print("✅ fig1_computation_time_4methods.png タイトル修正版を作成完了")
