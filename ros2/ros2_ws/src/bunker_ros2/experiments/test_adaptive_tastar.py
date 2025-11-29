"""
Adaptive TA-A* テスト

A*, TA-A*, Adaptive TA-A*を比較
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from path_planner_3d.astar_planner import AStarPlanner3D
from path_planner_3d.adaptive_tastar import AdaptiveTAstar
from path_planner_3d.config import PlannerConfig
import numpy as np
import json

def comprehensive_test():
    """包括的テスト"""
    print("="*70)
    print("Adaptive TA-A* 包括的テスト")
    print("="*70)
    
    config = PlannerConfig.medium_scale()
    
    planners = {
        'A* (Baseline)': AStarPlanner3D(config),
        'Adaptive TA-A* (Proposed)': AdaptiveTAstar(config)
    }
    
    # テストシナリオ（多様な距離）
    scenarios = []
    np.random.seed(42)
    
    # Short distance
    for i in range(10):
        start = [np.random.uniform(-5, 5), np.random.uniform(-5, 5), 0.2]
        goal = [np.random.uniform(-5, 5), np.random.uniform(-5, 5), 0.2]
        scenarios.append({'name': f'Short-{i}', 'start': start, 'goal': goal})
    
    # Medium distance  
    for i in range(10):
        start = [np.random.uniform(-10, 10), np.random.uniform(-10, 10), 0.2]
        goal = [np.random.uniform(-10, 10), np.random.uniform(-10, 10), 0.2]
        scenarios.append({'name': f'Medium-{i}', 'start': start, 'goal': goal})
    
    # Long distance
    for i in range(10):
        start = [np.random.uniform(-20, 20), np.random.uniform(-20, 20), 0.2]
        goal = [np.random.uniform(-20, 20), np.random.uniform(-20, 20), 0.2]
        scenarios.append({'name': f'Long-{i}', 'start': start, 'goal': goal})
    
    results = {}
    
    for algo_name, planner in planners.items():
        print(f"\n【{algo_name}】")
        results[algo_name] = []
        
        for scenario in scenarios:
            result = planner.plan_path(
                scenario['start'],
                scenario['goal'],
                timeout=120
            )
            
            results[algo_name].append({
                'scenario': scenario['name'],
                'success': result.success,
                'time': result.computation_time,
                'length': result.path_length if result.success else None,
                'nodes': result.nodes_explored
            })
            
            status = "✅" if result.success else "❌"
            print(f"  {scenario['name']:15s}: {status} {result.computation_time:6.2f}s")
    
    # 統計分析
    print("\n" + "="*70)
    print("統計分析")
    print("="*70)
    
    for algo_name in planners.keys():
        algo_results = results[algo_name]
        
        successes = sum(1 for r in algo_results if r['success'])
        total = len(algo_results)
        success_rate = successes / total * 100
        
        successful_results = [r for r in algo_results if r['success']]
        
        if successful_results:
            avg_time = np.mean([r['time'] for r in successful_results])
            median_time = np.median([r['time'] for r in successful_results])
            avg_nodes = np.mean([r['nodes'] for r in successful_results])
            
            print(f"\n{algo_name}:")
            print(f"  成功率: {success_rate:5.1f}% ({successes}/{total})")
            print(f"  平均時間: {avg_time:6.2f}s")
            print(f"  中央値: {median_time:6.2f}s")
            print(f"  平均探索ノード: {avg_nodes:.0f}個")
    
    # 比較
    print("\n" + "="*70)
    print("A* vs Adaptive TA-A*")
    print("="*70)
    
    baseline_results = [r for r in results['A* (Baseline)'] if r['success']]
    adaptive_results = [r for r in results['Adaptive TA-A* (Proposed)'] if r['success']]
    
    if baseline_results and adaptive_results:
        baseline_avg_time = np.mean([r['time'] for r in baseline_results])
        adaptive_avg_time = np.mean([r['time'] for r in adaptive_results])
        
        speedup = baseline_avg_time / adaptive_avg_time if adaptive_avg_time > 0 else 0
        
        print(f"\nA* 平均時間: {baseline_avg_time:6.2f}s")
        print(f"Adaptive TA-A* 平均時間: {adaptive_avg_time:6.2f}s")
        
        if speedup > 1:
            print(f"→ Adaptive TA-A*が{speedup:.2f}倍高速")
        elif speedup < 1:
            print(f"→ A*が{1/speedup:.2f}倍高速")
        else:
            print(f"→ ほぼ同等")
    
    # 結果を保存
    output_file = Path('../results/adaptive_tastar_test.json')
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n結果保存: {output_file}")
    print("="*70)

if __name__ == '__main__':
    comprehensive_test()


