#!/usr/bin/env python3
"""
経路の走行可能性評価スクリプト（簡易版）

経路データが結果ファイルに保存されていないため、
Dataset3の地形データから理論的な走行可能性を評価する。
"""

import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.family'] = ['Noto Sans CJK JP', 'IPAPGothic', 'DejaVu Sans']

# 走行可能な最大勾配（度）
MAX_SLOPE_DEG = 45

print("=" * 60)
print("経路の走行可能性評価（Dataset3）")
print("=" * 60)

# Dataset3のシナリオ情報を読み込み
with open('dataset3_scenarios.json', 'r') as f:
    scenarios = json.load(f)

print(f"\n総シナリオ数: {len(scenarios)}")

# 地形データの統計
avg_slopes = []
max_slopes = []
feasible_count = 0

for scenario in scenarios:
    if 'terrain_metadata' in scenario:
        terrain = scenario['terrain_metadata']
        avg_slope = terrain.get('avg_slope_deg', 0)
        max_slope = terrain.get('max_slope_deg', 0)
        
        avg_slopes.append(avg_slope)
        max_slopes.append(max_slope)
        
        # 平均勾配が45°以下なら理論的に走行可能
        if avg_slope <= MAX_SLOPE_DEG:
            feasible_count += 1

print("\n" + "=" * 60)
print("地形統計")
print("=" * 60)
print(f"平均勾配の平均: {np.mean(avg_slopes):.1f}°")
print(f"平均勾配の中央値: {np.median(avg_slopes):.1f}°")
print(f"平均勾配の範囲: {np.min(avg_slopes):.1f}° - {np.max(avg_slopes):.1f}°")
print(f"\n最大勾配の平均: {np.mean(max_slopes):.1f}°")
print(f"最大勾配の中央値: {np.median(max_slopes):.1f}°")
print(f"最大勾配の範囲: {np.min(max_slopes):.1f}° - {np.max(max_slopes):.1f}°")

print(f"\n平均勾配 ≤ {MAX_SLOPE_DEG}°のシナリオ: {feasible_count}/{len(scenarios)} ({feasible_count/len(scenarios)*100:.1f}%)")

# 勾配の分布
print("\n" + "=" * 60)
print("勾配分布")
print("=" * 60)

slope_bins = [0, 20, 30, 40, 45, 60, 90]
for i in range(len(slope_bins)-1):
    count = len([s for s in avg_slopes if slope_bins[i] <= s < slope_bins[i+1]])
    print(f"{slope_bins[i]:2d}° - {slope_bins[i+1]:2d}°: {count:2d}シナリオ ({count/len(scenarios)*100:5.1f}%)")

count_over = len([s for s in avg_slopes if s >= slope_bins[-1]])
print(f"{slope_bins[-1]:2d}° 以上  : {count_over:2d}シナリオ ({count_over/len(scenarios)*100:5.1f}%)")

# A*とTA*の結果を読み込み
with open('benchmark_results/dataset3_astar_final_results.json', 'r') as f:
    astar_results = json.load(f)

with open('benchmark_results/dataset3_tastar_final_results.json', 'r') as f:
    tastar_results = json.load(f)

# 成功シナリオの地形分析
print("\n" + "=" * 60)
print("成功シナリオの地形分析")
print("=" * 60)

def analyze_success_terrain(results, name):
    success_scenarios = [r['scenario_id'] for r in results if r['success']]
    
    # 成功シナリオの地形統計
    success_avg_slopes = []
    success_max_slopes = []
    
    # シナリオIDから地形データをマッチング
    scenario_dict = {}
    for scenario in scenarios:
        # シナリオIDの構築を修正
        if 'id' in scenario:
            sid = scenario['id']
        else:
            # データ構造に応じて別の方法でIDを取得
            # 仮にインデックスを使用
            continue
        
        scenario_dict[sid] = scenario
    
    # 結果のscenario_idから直接マッチング
    for r in results:
        if r['success'] and r['scenario_id'] in scenario_dict:
            scenario = scenario_dict[r['scenario_id']]
            if 'terrain_metadata' in scenario:
                terrain = scenario['terrain_metadata']
                success_avg_slopes.append(terrain.get('avg_slope_deg', 0))
                success_max_slopes.append(terrain.get('max_slope_deg', 0))
    
    print(f"\n{name}:")
    print(f"  成功数: {len(success_scenarios)}/90")
    print(f"  成功シナリオの平均勾配:")
    print(f"    平均: {np.mean(success_avg_slopes):.1f}°")
    print(f"    中央値: {np.median(success_avg_slopes):.1f}°")
    print(f"    範囲: {np.min(success_avg_slopes):.1f}° - {np.max(success_avg_slopes):.1f}°")
    print(f"  成功シナリオの最大勾配:")
    print(f"    平均: {np.mean(success_max_slopes):.1f}°")
    print(f"    中央値: {np.median(success_max_slopes):.1f}°")
    
    # 走行可能（平均勾配≤45°）なシナリオ
    feasible = len([s for s in success_avg_slopes if s <= MAX_SLOPE_DEG])
    print(f"  理論的に走行可能（平均勾配≤45°）: {feasible}/{len(success_scenarios)} ({feasible/len(success_scenarios)*100:.1f}%)")
    
    return len(success_scenarios), feasible

astar_success, astar_feasible = analyze_success_terrain(astar_results, "A*")
tastar_success, tastar_feasible = analyze_success_terrain(tastar_results, "TA*")

# 比較グラフ生成
print("\n" + "=" * 60)
print("比較グラフ生成中...")
print("=" * 60)

fig, ax = plt.subplots(figsize=(12, 6), dpi=300)

methods = ['A*', 'TA*']
path_found = [astar_success, tastar_success]
theoretically_feasible = [astar_feasible, tastar_feasible]

x = np.arange(len(methods))
width = 0.35

bars1 = ax.bar(x - width/2, path_found, width, label='Path Found', color='#3498db', edgecolor='black', linewidth=1.5)
bars2 = ax.bar(x + width/2, theoretically_feasible, width, label='Theoretically Feasible (≤45°)', color='#2ecc71', edgecolor='black', linewidth=1.5)

ax.set_ylabel('Number of Successful Scenarios', fontsize=14)
ax.set_title('Success Rate Comparison: Path Found vs Theoretically Feasible', fontsize=16, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(methods, fontsize=14)
ax.legend(fontsize=12)
ax.set_ylim([0, 100])
ax.grid(True, alpha=0.3, axis='y')

# 値を表示
for bar in bars1:
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height + 1,
            f'{int(height)}',
            ha='center', va='bottom', fontsize=12, fontweight='bold')

for bar in bars2:
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height + 1,
            f'{int(height)}',
            ha='center', va='bottom', fontsize=12, fontweight='bold')

plt.tight_layout()
plt.savefig('figures/final/practical_feasibility_comparison.png', dpi=300, bbox_inches='tight')
print("✓ 図を保存: figures/final/practical_feasibility_comparison.png")

# 結果サマリー
print("\n" + "=" * 60)
print("結果サマリー")
print("=" * 60)

summary = {
    "A*": {
        "path_found": astar_success,
        "path_found_rate": astar_success / 90 * 100,
        "theoretically_feasible": astar_feasible,
        "feasible_rate": astar_feasible / 90 * 100
    },
    "TA*": {
        "path_found": tastar_success,
        "path_found_rate": tastar_success / 90 * 100,
        "theoretically_feasible": tastar_feasible,
        "feasible_rate": tastar_feasible / 90 * 100
    }
}

for method, stats in summary.items():
    print(f"\n{method}:")
    print(f"  経路発見成功: {stats['path_found']}/90 ({stats['path_found_rate']:.1f}%)")
    print(f"  理論的走行可能: {stats['theoretically_feasible']}/90 ({stats['feasible_rate']:.1f}%)")
    
    if stats['path_found'] > 0:
        practical_ratio = stats['theoretically_feasible'] / stats['path_found'] * 100
        print(f"  実用性比率: {practical_ratio:.1f}% (経路発見成功のうち走行可能な割合)")

# JSON出力
with open('benchmark_results/practical_feasibility_summary.json', 'w') as f:
    json.dump(summary, f, indent=2)

print("\n✓ サマリーを保存: benchmark_results/practical_feasibility_summary.json")
print("\n処理完了！")
