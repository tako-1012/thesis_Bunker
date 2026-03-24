#!/usr/bin/env python3
"""
経路の実用的な走行可能性評価（Dataset3）

結果JSONには経路データ（pathフィールド）が含まれていないため、
地形メタデータ（avg_slope_deg）を使用して理論的走行可能性を評価します。

評価基準:
- 平均勾配 ≤ 45°: 走行可能（一般的なロボットの限界）
- 平均勾配 > 45°: 走行不可能（滑落リスク）

重要な発見:
- A*は地形コストを完全に無視（障害物回避のみ）
- TA*は地形コストを考慮（急勾配を避けるルート探索）
- そのため、A*の「成功」には走行不可能な経路が含まれる可能性が高い
"""

import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

# 日本語フォント設定
try:
    plt.rcParams['font.family'] = 'Noto Sans CJK JP'
except:
    try:
        plt.rcParams['font.family'] = 'IPAPGothic'
    except:
        plt.rcParams['font.family'] = 'DejaVu Sans'

MAX_SLOPE_DEG = 45.0  # ロボットの一般的な登坂能力限界

def load_results(filename):
    """結果JSONファイルを読み込む"""
    with open(filename, 'r') as f:
        return json.load(f)

def load_scenarios():
    """シナリオJSONファイルを読み込む"""
    with open('dataset3_scenarios.json', 'r') as f:
        return json.load(f)

def create_scenario_terrain_map(scenarios):
    """シナリオIDから地形メタデータへのマップを作成"""
    terrain_map = {}
    for i, scenario in enumerate(scenarios):
        # シナリオIDを直接取得（id_numから推定）
        # 90シナリオ: 3カテゴリ × 3サブカテゴリ × 10インスタンス
        category = (i // 30) + 1
        subcategory = ((i % 30) // 10) + 1
        instance = (i % 10) + 1
        scenario_id = f"dataset3_{category}_{subcategory}_{instance}"
        
        terrain_map[scenario_id] = scenario['terrain_metadata']
    
    return terrain_map

def evaluate_feasibility(results, terrain_map, planner_name):
    """
    結果の実用的走行可能性を評価
    
    Returns:
        dict: {
            'total': 総シナリオ数,
            'path_found': 経路が見つかったシナリオ数,
            'feasible': 走行可能と判定されたシナリオ数,
            'practical_success_rate': 実用的成功率,
            'unfeasible_paths': 走行不可能だが経路が見つかったシナリオ数,
            'feasible_scenarios': 走行可能シナリオのIDリスト
        }
    """
    total = len(results)
    path_found = sum(1 for r in results if r['success'])
    feasible_scenarios = []
    unfeasible_paths = []
    
    for result in results:
        scenario_id = result['scenario_id']
        
        if scenario_id not in terrain_map:
            print(f"警告: {scenario_id}の地形データが見つかりません")
            continue
        
        terrain = terrain_map[scenario_id]
        avg_slope = terrain['avg_slope_deg']
        
        # 経路が見つかっていて、かつ走行可能な地形
        if result['success'] and avg_slope <= MAX_SLOPE_DEG:
            feasible_scenarios.append(scenario_id)
        # 経路は見つかったが、走行不可能な地形
        elif result['success'] and avg_slope > MAX_SLOPE_DEG:
            unfeasible_paths.append({
                'scenario_id': scenario_id,
                'avg_slope': avg_slope,
                'max_slope': terrain['max_slope_deg'],
                'path_length': result['path_length_meters'],
                'computation_time': result['computation_time']
            })
    
    feasible = len(feasible_scenarios)
    practical_success_rate = (feasible / total) * 100
    
    return {
        'total': total,
        'path_found': path_found,
        'feasible': feasible,
        'practical_success_rate': practical_success_rate,
        'unfeasible_paths': unfeasible_paths,
        'feasible_scenarios': feasible_scenarios
    }

def analyze_terrain_stats(terrain_map):
    """地形統計を分析"""
    avg_slopes = [t['avg_slope_deg'] for t in terrain_map.values()]
    max_slopes = [t['max_slope_deg'] for t in terrain_map.values()]
    
    return {
        'avg_slope_mean': np.mean(avg_slopes),
        'avg_slope_median': np.median(avg_slopes),
        'avg_slope_min': np.min(avg_slopes),
        'avg_slope_max': np.max(avg_slopes),
        'max_slope_mean': np.mean(max_slopes),
        'max_slope_median': np.median(max_slopes),
        'feasible_terrain_count': sum(1 for s in avg_slopes if s <= MAX_SLOPE_DEG),
        'total_count': len(avg_slopes)
    }

def print_results(astar_eval, tastar_eval, terrain_stats):
    """評価結果を表示"""
    print("=" * 70)
    print("実用的走行可能性評価（Dataset3）")
    print("=" * 70)
    print(f"\n評価基準: 平均勾配 ≤ {MAX_SLOPE_DEG}°")
    print()
    
    print("=" * 70)
    print("地形統計")
    print("=" * 70)
    print(f"平均勾配の平均: {terrain_stats['avg_slope_mean']:.1f}°")
    print(f"平均勾配の中央値: {terrain_stats['avg_slope_median']:.1f}°")
    print(f"平均勾配の範囲: {terrain_stats['avg_slope_min']:.1f}° - {terrain_stats['avg_slope_max']:.1f}°")
    print(f"最大勾配の平均: {terrain_stats['max_slope_mean']:.1f}°")
    print(f"最大勾配の中央値: {terrain_stats['max_slope_median']:.1f}°")
    print(f"走行可能地形（≤{MAX_SLOPE_DEG}°）: {terrain_stats['feasible_terrain_count']}/{terrain_stats['total_count']} ({terrain_stats['feasible_terrain_count']/terrain_stats['total_count']*100:.1f}%)")
    print()
    
    print("=" * 70)
    print("A* 評価結果")
    print("=" * 70)
    print(f"総シナリオ数: {astar_eval['total']}")
    print(f"経路発見成功: {astar_eval['path_found']}/{astar_eval['total']} ({astar_eval['path_found']/astar_eval['total']*100:.1f}%)")
    print(f"実用的成功: {astar_eval['feasible']}/{astar_eval['total']} ({astar_eval['practical_success_rate']:.1f}%)")
    print(f"走行不可能だが経路発見: {len(astar_eval['unfeasible_paths'])} シナリオ")
    print()
    
    if astar_eval['unfeasible_paths']:
        print(f"【重要】A*が走行不可能な経路を返したシナリオ（上位10件）:")
        sorted_unfeasible = sorted(astar_eval['unfeasible_paths'], 
                                   key=lambda x: x['avg_slope'], reverse=True)[:10]
        for i, u in enumerate(sorted_unfeasible, 1):
            print(f"  {i}. {u['scenario_id']}: 平均勾配 {u['avg_slope']:.1f}°, 最大勾配 {u['max_slope']:.1f}°")
    print()
    
    print("=" * 70)
    print("TA* 評価結果")
    print("=" * 70)
    print(f"総シナリオ数: {tastar_eval['total']}")
    print(f"経路発見成功: {tastar_eval['path_found']}/{tastar_eval['total']} ({tastar_eval['path_found']/tastar_eval['total']*100:.1f}%)")
    print(f"実用的成功: {tastar_eval['feasible']}/{tastar_eval['total']} ({tastar_eval['practical_success_rate']:.1f}%)")
    print(f"走行不可能だが経路発見: {len(tastar_eval['unfeasible_paths'])} シナリオ")
    print()
    
    print("=" * 70)
    print("比較分析")
    print("=" * 70)
    print(f"経路発見率の差: {astar_eval['path_found']/astar_eval['total']*100 - tastar_eval['path_found']/tastar_eval['total']*100:.1f}% ポイント（A* - TA*）")
    print(f"実用的成功率の差: {astar_eval['practical_success_rate'] - tastar_eval['practical_success_rate']:.1f}% ポイント（A* - TA*）")
    print()
    
    # A*の「見かけ上の成功」が実際にどれだけ無意味か
    astar_false_positives = len(astar_eval['unfeasible_paths'])
    astar_true_success_rate = (astar_eval['feasible'] / astar_eval['total']) * 100
    print(f"【重要な発見】")
    print(f"A*の経路発見率: {astar_eval['path_found']/astar_eval['total']*100:.1f}%")
    print(f"A*の実用的成功率: {astar_true_success_rate:.1f}%")
    print(f"A*の偽陽性（走行不可能だが経路発見）: {astar_false_positives}シナリオ")
    print()
    print(f"TA*の経路発見率: {tastar_eval['path_found']/tastar_eval['total']*100:.1f}%")
    print(f"TA*の実用的成功率: {tastar_eval['practical_success_rate']:.1f}%")
    
    if tastar_eval['practical_success_rate'] >= astar_true_success_rate:
        diff = tastar_eval['practical_success_rate'] - astar_true_success_rate
        print(f"\n→ TA*の実用的成功率はA*より {diff:.1f}% ポイント高い！")
    else:
        diff = astar_true_success_rate - tastar_eval['practical_success_rate']
        print(f"\n→ A*の実用的成功率はTA*より {diff:.1f}% ポイント高い")

def create_comparison_figure(astar_eval, tastar_eval):
    """比較図を作成"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), dpi=300)
    
    planners = ['A*', 'TA*']
    
    # 左図: 経路発見率 vs 実用的成功率
    path_found_rates = [
        astar_eval['path_found'] / astar_eval['total'] * 100,
        tastar_eval['path_found'] / tastar_eval['total'] * 100
    ]
    practical_rates = [
        astar_eval['practical_success_rate'],
        tastar_eval['practical_success_rate']
    ]
    
    x = np.arange(len(planners))
    width = 0.35
    
    bars1 = ax1.bar(x - width/2, path_found_rates, width, label='経路発見率', color='#2ecc71', alpha=0.8)
    bars2 = ax1.bar(x + width/2, practical_rates, width, label='実用的成功率', color='#3498db', alpha=0.8)
    
    ax1.set_ylabel('成功率 (%)', fontsize=12, fontweight='bold')
    ax1.set_title('経路発見率 vs 実用的成功率', fontsize=14, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(planners, fontsize=12, fontweight='bold')
    ax1.legend(fontsize=11)
    ax1.set_ylim(0, 105)
    ax1.grid(axis='y', alpha=0.3)
    
    # 値をバーの上に表示
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + 1,
                    f'{height:.1f}%',
                    ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    # 右図: 走行不可能経路の数
    unfeasible_counts = [
        len(astar_eval['unfeasible_paths']),
        len(tastar_eval['unfeasible_paths'])
    ]
    
    bars3 = ax2.bar(planners, unfeasible_counts, color=['#e74c3c', '#95a5a6'], alpha=0.8)
    ax2.set_ylabel('走行不可能経路の数', fontsize=12, fontweight='bold')
    ax2.set_title('走行不可能だが経路発見したシナリオ数', fontsize=14, fontweight='bold')
    ax2.set_ylim(0, max(unfeasible_counts) * 1.2)
    ax2.grid(axis='y', alpha=0.3)
    
    # 値をバーの上に表示
    for bar in bars3:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                f'{int(height)}',
                ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig('figures/final/practical_feasibility_comparison.png', dpi=300, bbox_inches='tight')
    print("\n図を保存しました: figures/final/practical_feasibility_comparison.png")

def main():
    # データ読み込み
    print("データ読み込み中...")
    astar_results = load_results('benchmark_results/dataset3_astar_final_results.json')
    tastar_results = load_results('benchmark_results/dataset3_tastar_final_results.json')
    scenarios = load_scenarios()
    
    # 地形マップ作成
    terrain_map = create_scenario_terrain_map(scenarios)
    
    # 地形統計
    terrain_stats = analyze_terrain_stats(terrain_map)
    
    # 走行可能性評価
    astar_eval = evaluate_feasibility(astar_results, terrain_map, 'A*')
    tastar_eval = evaluate_feasibility(tastar_results, terrain_map, 'TA*')
    
    # 結果表示
    print_results(astar_eval, tastar_eval, terrain_stats)
    
    # 図作成
    create_comparison_figure(astar_eval, tastar_eval)
    
    # 詳細レポート保存
    report = {
        'evaluation_criteria': f'avg_slope <= {MAX_SLOPE_DEG} degrees',
        'terrain_statistics': terrain_stats,
        'astar': astar_eval,
        'tastar': tastar_eval
    }
    
    with open('analysis/practical_feasibility_report.json', 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    
    print("\n詳細レポート保存: analysis/practical_feasibility_report.json")

if __name__ == '__main__':
    main()
