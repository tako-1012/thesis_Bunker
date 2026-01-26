import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import os

# データ読み込み
path = os.path.join(os.getcwd(), 'benchmark_results', 'complexity_method_comparison.json')
with open(path, 'r') as f:
    data = json.load(f)

# 複数フォーマット対応（list または {'results': [...]})
if isinstance(data, dict) and 'results' in data:
    data = data['results']

print('='*60)
print('COMPLEXITY METHOD COMPARISON')
print('='*60)

# 基本統計
methods = ['Method1_Slope', 'Method2_Obstacle', 'Method3_Balanced', 'Method4_Statistical']

for method in methods:
    complexities = [d['methods'][method]['complexity'] for d in data]

    print(f"\n{method}:")
    print(f"  Mean: {np.mean(complexities):.4f}")
    print(f"  Std: {np.std(complexities):.4f}")
    print(f"  Min: {np.min(complexities):.4f}")
    print(f"  Max: {np.max(complexities):.4f}")
    print(f"  Median: {np.median(complexities):.4f}")

# 環境別統計
print('\n' + '='*60)
print('BY ENVIRONMENT')
print('='*60)

env_types = ['steep', 'dense', 'complex']

for env_type in env_types:
    env_data = [d for d in data if env_type in str(d.get('scenario_id', '')).lower()]

    print(f"\n{env_type.upper()} ({len(env_data)} scenarios):")

    for method in methods:
        complexities = [d['methods'][method]['complexity'] for d in env_data] if len(env_data) > 0 else []
        mean = np.mean(complexities) if len(complexities) > 0 else float('nan')
        std = np.std(complexities) if len(complexities) > 0 else float('nan')
        print(f"  {method}: {mean:.4f} ± {std:.4f}")

# 可視化
fig = plt.figure(figsize=(16, 12))

# 1. 全体の分布（ヒストグラム）
for i, method in enumerate(methods):
    ax = plt.subplot(3, 4, i+1)

    complexities = [d['methods'][method]['complexity'] for d in data]

    ax.hist(complexities, bins=30, alpha=0.7, edgecolor='black')
    ax.set_xlabel('Complexity')
    ax.set_ylabel('Count')
    ax.set_title(f'{method}\nMean: {np.mean(complexities):.3f}')
    ax.grid(True, alpha=0.3)
    ax.axvline(np.mean(complexities), color='r', linestyle='--', 
               linewidth=2, label='Mean')
    ax.legend()

# 2. 環境別の箱ひげ図
for i, method in enumerate(methods):
    ax = plt.subplot(3, 4, i+5)

    env_data = []
    labels = []
    for env_type in env_types:
        env_scenarios = [d for d in data if env_type in str(d.get('scenario_id', '')).lower()]
        complexities = [d['methods'][method]['complexity'] for d in env_scenarios]
        env_data.append(complexities)
        labels.append(env_type)

    bp = ax.boxplot(env_data, labels=labels, patch_artist=True)

    # 色付け
    colors = ['lightblue', 'lightgreen', 'lightcoral']
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)

    ax.set_ylabel('Complexity')
    ax.set_title(f'{method} by Environment')
    ax.grid(True, alpha=0.3, axis='y')

# 3. 方法間の相関
ax = plt.subplot(3, 4, 9)

# 相関行列作成
correlation_matrix = np.zeros((4, 4))
for i, method1 in enumerate(methods):
    for j, method2 in enumerate(methods):
        comp1 = [d['methods'][method1]['complexity'] for d in data]
        comp2 = [d['methods'][method2]['complexity'] for d in data]
        correlation_matrix[i, j] = np.corrcoef(comp1, comp2)[0, 1]

sns.heatmap(correlation_matrix, annot=True, fmt='.3f', 
            xticklabels=['M1', 'M2', 'M3', 'M4'],
            yticklabels=['M1', 'M2', 'M3', 'M4'],
            cmap='coolwarm', center=0, ax=ax)
ax.set_title('Method Correlation')

# 4. 累積分布
ax = plt.subplot(3, 4, 10)

for method in methods:
    complexities = sorted([d['methods'][method]['complexity'] for d in data])
    cumulative = np.arange(1, len(complexities) + 1) / len(complexities)
    ax.plot(complexities, cumulative, linewidth=2, label=method.split('_')[0])

# 閾値ライン
ax.axvline(0.3, color='gray', linestyle='--', alpha=0.5, label='Threshold 0.3')
ax.axvline(0.6, color='gray', linestyle=':', alpha=0.5, label='Threshold 0.6')

ax.set_xlabel('Complexity')
ax.set_ylabel('Cumulative Probability')
ax.set_title('Cumulative Distribution')
ax.legend()
ax.grid(True, alpha=0.3)

# 5. 環境別の複雑度比較（平均）
ax = plt.subplot(3, 4, 11)

x = np.arange(len(env_types))
width = 0.2

for i, method in enumerate(methods):
    means = []
    for env_type in env_types:
        env_scenarios = [d for d in data if env_type in str(d.get('scenario_id', '')).lower()]
        complexities = [d['methods'][method]['complexity'] for d in env_scenarios]
        means.append(np.mean(complexities) if len(complexities) > 0 else 0.0)

    ax.bar(x + i*width, means, width, label=method.split('_')[0])

ax.set_xlabel('Environment Type')
ax.set_ylabel('Mean Complexity')
ax.set_title('Mean Complexity by Environment')
ax.set_xticks(x + width * 1.5)
ax.set_xticklabels(env_types)
ax.legend()
ax.grid(True, alpha=0.3, axis='y')

# 6. 分散比較
ax = plt.subplot(3, 4, 12)

variances = []
for method in methods:
    complexities = [d['methods'][method]['complexity'] for d in data]
    variances.append(np.var(complexities))

colors = ['skyblue', 'lightgreen', 'lightcoral', 'plum']
bars = ax.bar(range(len(methods)), variances, color=colors, edgecolor='black')
ax.set_xticks(range(len(methods)))
ax.set_xticklabels([m.split('_')[0] for m in methods])
ax.set_ylabel('Variance')
ax.set_title('Complexity Variance by Method')
ax.grid(True, alpha=0.3, axis='y')

# 値をバーの上に表示
for i, (bar, var) in enumerate(zip(bars, variances)):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height,
            f'{var:.4f}', ha='center', va='bottom', fontsize=9)

plt.tight_layout()
out_path = os.path.join(os.getcwd(), 'benchmark_results', 'complexity_comparison_detailed.png')
plt.savefig(out_path, dpi=300, bbox_inches='tight')

print('\n' + '='*60)
print(f'Saved: {out_path}')
print('='*60)

# 判定
print('\n' + '='*60)
print('ASSESSMENT')
print('='*60)

for method in methods:
    complexities = [d['methods'][method]['complexity'] for d in data]

    low = sum(1 for c in complexities if c < 0.3)
    mid = sum(1 for c in complexities if 0.3 <= c < 0.6)
    high = sum(1 for c in complexities if c >= 0.6)

    print(f"\n{method}:")
    print(f"  Low (< 0.3): {low}/{len(data)} ({low/len(data)*100:.1f}%)")
    print(f"  Mid (0.3-0.6): {mid}/{len(data)} ({mid/len(data)*100:.1f}%)")
    print(f"  High (>= 0.6): {high}/{len(data)} ({high/len(data)*100:.1f}%)")

    if low > 0.8 * len(data):
        print('  ⚠️ WARNING: Too many low complexity scenarios')
        print('     → 正規化パラメータの調整が必要')
    elif high > 0.8 * len(data):
        print('  ⚠️ WARNING: Too many high complexity scenarios')
        print('     → 正規化パラメータの調整が必要')
    elif low > 10 and mid > 10 and high > 10:
        print('  ✓ GOOD: Balanced distribution')
    else:
        print('  △ MODERATE: Acceptable but could be improved')
