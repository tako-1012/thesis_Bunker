import os
import json
import numpy as np
import matplotlib
import matplotlib.pyplot as plt

# 日本語フォント対応（環境に応じてフォールバック）
matplotlib.rcParams['font.family'] = ['Noto Sans CJK JP', 'IPAPGothic', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

OUT_DIR = 'figures/final'
os.makedirs(OUT_DIR, exist_ok=True)

# データ読み込み
with open('benchmark_results/dataset3_astar_final_results.json') as f:
    astar = json.load(f)
with open('benchmark_results/dataset3_tastar_final_results.json') as f:
    tastar = json.load(f)
with open('benchmark_results/dataset3_dlite_final_results.json') as f:
    dlite = json.load(f)
with open('benchmark_results/dataset3_fieldd_final_results.json') as f:
    fieldd = json.load(f)

methods = ['A*', 'TA*', 'D*Lite', 'Field D*\nHybrid']
colors = ['#3498db', '#2ecc71', '#e74c3c', '#f39c12']

# 成功シナリオのみの平均計算時間と経路長
def mean_success(key, data):
    vals = [r[key] for r in data if r.get('success')]
    return float(np.mean(vals)) if len(vals) > 0 else 0.0

times = [
    mean_success('computation_time', astar),
    mean_success('computation_time', tastar),
    mean_success('computation_time', dlite),
    mean_success('computation_time', fieldd)
]

path_lengths = [
    mean_success('path_length_meters', astar),
    mean_success('path_length_meters', tastar),
    mean_success('path_length_meters', dlite),
    mean_success('path_length_meters', fieldd)
]

# 図1: 計算時間比較（対数スケール）
fig, ax = plt.subplots(figsize=(12, 6), dpi=300)
bars = ax.bar(methods, times, color=colors)
ax.set_ylabel('Computation Time (seconds)', fontsize=16)
ax.set_title('Average Computation Time Comparison (Log Scale)', fontsize=18, fontweight='bold')
ax.set_yscale('log')
ax.grid(True, alpha=0.3, axis='y')
for bar, time in zip(bars, times):
    ax.text(bar.get_x() + bar.get_width()/2, time * 1.2 if time > 0 else 0.01,
            f'{time:.2f}s', ha='center', va='bottom', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, 'computation_time_comparison.png'), dpi=300, bbox_inches='tight')
print('✓ 図1生成完了: computation_time_comparison.png')
plt.close(fig)

# 図1(FINAL版): 計算時間比較（中央値ベース、0-45秒）
# D*Liteは中央値36.47秒を使用
times_final = [times[0], times[1], 36.47, times[3]]  # A*, TA*, D*Lite(median), Field D*

fig, ax = plt.subplots(figsize=(12, 6), dpi=300)
bars = ax.bar(methods, times_final, color=colors)
ax.set_ylabel('Computation Time (seconds)', fontsize=16)
ax.set_title('Computation Time Comparison', fontsize=18, fontweight='bold')
ax.set_ylim([0, 45])
ax.grid(True, alpha=0.3, axis='y')

# 指定ラベルテキスト（D*Liteは中央値、79倍遅い）
label_texts = {
    'Field D*\nHybrid': '0.46s\n(fastest)',
    'A*': '5.14s\n(11× slower)',
    'TA*': '6.15s\n(13× slower)',
    'D*Lite': '36.47s\n(median, 79× slower)'
}

# 各バーにラベル表示
for bar, method in zip(bars, methods):
    height = bar.get_height()
    text = label_texts.get(method, f'{height:.2f}s')
    ax.text(bar.get_x() + bar.get_width()/2, height + 1.5,
            text, ha='center', va='bottom', fontsize=14, fontweight='bold')

# Field D*バーを強調（太枠）
try:
    idx = methods.index('Field D*\nHybrid')
    bars[idx].set_edgecolor('black')
    bars[idx].set_linewidth(3)
except ValueError:
    pass

plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, 'computation_time_comparison_FIXED.png'), dpi=300, bbox_inches='tight')
print('✓ 図1(FIXED)生成完了: computation_time_comparison_FIXED.png')
plt.close(fig)

# 図2: 経路長比較
fig, ax = plt.subplots(figsize=(12, 6), dpi=300)
bars = ax.bar(methods, path_lengths, color=colors)
ax.set_ylabel('Average Path Length (meters)', fontsize=16)
ax.set_title('Average Path Length Comparison', fontsize=18, fontweight='bold')
ax.grid(True, alpha=0.3, axis='y')
for bar, length in zip(bars, path_lengths):
    ax.text(bar.get_x() + bar.get_width()/2, length + max(1.0, 0.05 * (max(path_lengths) if max(path_lengths) > 0 else 1.0)),
            f'{length:.2f}m', ha='center', va='bottom', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, 'path_length_comparison.png'), dpi=300, bbox_inches='tight')
print('✓ 図2生成完了: path_length_comparison.png')
plt.close(fig)

# 図3: カテゴリ別成功率（詳細版）
def get_category_stats(data):
    categories = {1: {'total': 0, 'success': 0},
                  2: {'total': 0, 'success': 0},
                  3: {'total': 0, 'success': 0}}
    for r in data:
        parts = r.get('scenario_id', '').split('_')
        if len(parts) >= 3:
            try:
                cat = int(parts[1])
            except ValueError:
                continue
            if cat in categories:
                categories[cat]['total'] += 1
                if r.get('success'):
                    categories[cat]['success'] += 1
    rates = []
    for i in [1, 2, 3]:
        total = categories[i]['total']
        success = categories[i]['success']
        rates.append(100.0 * success / total if total > 0 else 0.0)
    return rates

astar_rates = get_category_stats(astar)
tastar_rates = get_category_stats(tastar)
dlite_rates = get_category_stats(dlite)
fieldd_rates = get_category_stats(fieldd)

x = np.arange(3)
width = 0.2
fig, ax = plt.subplots(figsize=(12, 6), dpi=300)
bars1 = ax.bar(x - 1.5*width, astar_rates, width, label='A*', color=colors[0])
bars2 = ax.bar(x - 0.5*width, tastar_rates, width, label='TA*', color=colors[1])
bars3 = ax.bar(x + 0.5*width, dlite_rates, width, label='D*Lite', color=colors[2])
bars4 = ax.bar(x + 1.5*width, fieldd_rates, width, label='Field D* Hybrid', color=colors[3])
ax.set_ylabel('Success Rate (%)', fontsize=16)
ax.set_xlabel('Map Size Category', fontsize=16)
ax.set_title('Success Rate by Map Size Category', fontsize=18, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(['150×150m\n(Category 1)', '250×250m\n(Category 2)', '400×400m\n(Category 3)'])
ax.legend(fontsize=14, loc='lower left')
ax.set_ylim([0, 110])
ax.grid(True, alpha=0.3, axis='y')
for bars in [bars1, bars2, bars3, bars4]:
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, height + 2,
                f'{height:.0f}%', ha='center', va='bottom', fontsize=10)
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, 'category_success_rate.png'), dpi=300, bbox_inches='tight')
print('✓ 図3生成完了: category_success_rate.png')
plt.close(fig)

# 図4: トレードオフ図（計算時間 vs 経路長）
fig, ax = plt.subplots(figsize=(12, 8), dpi=300)
ax.scatter(times[0], path_lengths[0], s=400, alpha=0.7,
           color=colors[0], marker='o', label='A*', edgecolors='black', linewidth=2)
ax.scatter(times[1], path_lengths[1], s=400, alpha=0.7,
           color=colors[1], marker='s', label='TA*', edgecolors='black', linewidth=2)
ax.scatter(times[2], path_lengths[2], s=400, alpha=0.7,
           color=colors[2], marker='^', label='D*Lite', edgecolors='black', linewidth=2)
ax.scatter(times[3], path_lengths[3], s=400, alpha=0.7,
           color=colors[3], marker='D', label='Field D* Hybrid', edgecolors='black', linewidth=2)
ax.text(times[0] + max(0.5, 0.05*times[0] if times[0] > 0 else 0.5), path_lengths[0] + 3, 'A*', fontsize=14, fontweight='bold')
ax.text(times[1] + max(0.5, 0.05*times[1] if times[1] > 0 else 0.5), path_lengths[1] + 3, 'TA*', fontsize=14, fontweight='bold')
ax.text(times[2] + max(5, 0.05*times[2] if times[2] > 0 else 5), path_lengths[2] + 3, 'D*Lite', fontsize=14, fontweight='bold')
ax.text(times[3] + max(0.05, 0.05*times[3] if times[3] > 0 else 0.05), path_lengths[3] + 3, 'Field D* Hybrid', fontsize=14, fontweight='bold')
ax.set_xlabel('Average Computation Time (seconds)', fontsize=16)
ax.set_ylabel('Average Path Length (meters)', fontsize=16)
ax.set_title('Performance Trade-off: Computation Time vs Path Length', fontsize=18, fontweight='bold')
ax.set_xscale('log')
ax.grid(True, alpha=0.3)
ax.legend(fontsize=14, loc='upper right')
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, 'performance_tradeoff.png'), dpi=300, bbox_inches='tight')
print('✓ 図4生成完了: performance_tradeoff.png')
plt.close(fig)

# 図5: 全体成功率（円グラフ）
success_rates = [100, 88.9, 100, 100]
fig, ax = plt.subplots(figsize=(10, 10), dpi=300)
wedges, texts, autotexts = ax.pie(success_rates, labels=methods, autopct='%1.1f%%',
                                  colors=colors, startangle=90, textprops={'fontsize': 14})
for autotext in autotexts:
    autotext.set_color('white')
    autotext.set_fontweight('bold')
    autotext.set_fontsize(16)
ax.set_title('Overall Success Rate', fontsize=18, fontweight='bold')
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, 'overall_success_rate.png'), dpi=300, bbox_inches='tight')
print('✓ 図5生成完了: overall_success_rate.png')
plt.close(fig)
