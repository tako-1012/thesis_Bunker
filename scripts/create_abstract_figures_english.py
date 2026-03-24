import matplotlib.pyplot as plt
import numpy as np

# 共通設定
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['font.size'] = 14
plt.rcParams['axes.labelsize'] = 16
plt.rcParams['axes.titlesize'] = 18
plt.rcParams['xtick.labelsize'] = 14
plt.rcParams['ytick.labelsize'] = 14

methods = ['TA*', 'AHA*', 'Theta*', 'Field D*\nHybrid']
colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']

# 図1: 計算時間
times = [15.46, 0.016, 0.234, 0.175]
fig, ax = plt.subplots(figsize=(6, 4.5), dpi=300)
bars = ax.bar(methods, times, color=colors, edgecolor='black', linewidth=1.5)
ax.set_yscale('log')
ax.set_ylabel('Computation Time [s]', fontsize=16, fontweight='bold')
ax.set_xlabel('Method', fontsize=16, fontweight='bold')
ax.grid(True, which='both', alpha=0.3, linestyle='--')
for bar, time in zip(bars, times):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height,
            f'{time:.3f}s' if time < 1 else f'{time:.2f}s',
            ha='center', va='bottom', fontsize=12, fontweight='bold')
plt.tight_layout()
plt.savefig('figures/fig1_computation_time.png', dpi=300, bbox_inches='tight')
plt.close()
print("✅ fig1_computation_time.png 作成完了")

# 図2: 経路長
lengths = [21.27, 21.39, 23.64, 23.60]
fig, ax = plt.subplots(figsize=(6, 4.5), dpi=300)
bars = ax.bar(methods, lengths, color=colors, edgecolor='black', linewidth=1.5)
ax.set_ylabel('Path Length [m]', fontsize=16, fontweight='bold')
ax.set_xlabel('Method', fontsize=16, fontweight='bold')
ax.set_ylim([20, 25])
ax.grid(True, axis='y', alpha=0.3, linestyle='--')
for bar, length in zip(bars, lengths):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height,
            f'{length:.2f}m',
            ha='center', va='bottom', fontsize=12, fontweight='bold')
plt.tight_layout()
plt.savefig('figures/fig2_path_length.png', dpi=300, bbox_inches='tight')
plt.close()
print("✅ fig2_path_length.png 作成完了")

# 図3: 成功率
success_rates = [96.88, 94.79, 100.00, 100.00]
fig, ax = plt.subplots(figsize=(6, 4.5), dpi=300)
bars = ax.bar(methods, success_rates, color=colors, edgecolor='black', linewidth=1.5)
ax.set_ylabel('Success Rate [%]', fontsize=16, fontweight='bold')
ax.set_xlabel('Method', fontsize=16, fontweight='bold')
ax.set_ylim([90, 102])
ax.axhline(y=100, color='red', linestyle='--', linewidth=2, alpha=0.7, label='100%')
ax.grid(True, axis='y', alpha=0.3, linestyle='--')
ax.legend(fontsize=12)
for bar, rate in zip(bars, success_rates):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height,
            f'{rate:.2f}%',
            ha='center', va='bottom', fontsize=12, fontweight='bold')
plt.tight_layout()
plt.savefig('figures/fig3_success_rate.png', dpi=300, bbox_inches='tight')
plt.close()
print("✅ fig3_success_rate.png 作成完了")

print("\n🎉 全ての図の作成が完了しました！")
