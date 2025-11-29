#!/usr/bin/env python3
"""
アルゴリズム比較テスト

Lazy TA-A* vs Bidirectional Lazy TA-A*
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from lazy_tastar import LazyTAstar
from bidirectional_lazy_tastar import BidirectionalLazyTAstar
import time

def main():
    print("="*70)
    print("アルゴリズム比較テスト")
    print("="*70)
    
    lazy = LazyTAstar(voxel_size=0.5, map_size=50.0)
    bidirectional = BidirectionalLazyTAstar(voxel_size=0.5, map_size=50.0)
    
    test_cases = [
        {'name': 'Short', 'start': [0, 0, 0.2], 'goal': [10, 10, 0.2]},
        {'name': 'Medium', 'start': [0, 0, 0.2], 'goal': [20, 20, 0.2]},
        {'name': 'Long', 'start': [-20, -20, 0.2], 'goal': [20, 20, 0.2]},
        {'name': 'L-Shape', 'start': [0, 0, 0.2], 'goal': [0, 20, 0.2]},
        {'name': 'Diagonal', 'start': [-15, -15, 0.2], 'goal': [15, 15, 0.2]},
    ]
    
    results = {
        'Lazy TA-A*': [],
        'Bidirectional Lazy TA-A*': []
    }
    
    for algo_name, planner in [('Lazy TA-A*', lazy), ('Bidirectional Lazy TA-A*', bidirectional)]:
        print(f"\n{'='*70}")
        print(f"{algo_name}")
        print(f"{'='*70}")
        
        for test in test_cases:
            print(f"\n{test['name']}:")
            
            result = planner.plan_path(test['start'], test['goal'], timeout=120)
            
            results[algo_name].append({
                'name': test['name'],
                'success': result.success,
                'time': result.computation_time,
                'nodes': result.nodes_explored,
                'length': result.path_length if result.success else 0
            })
            
            if result.success:
                print(f"  ✅ {result.computation_time:.3f}s, {result.nodes_explored} nodes")
            else:
                print(f"  ❌ Failed")
    
    # 比較
    print(f"\n{'='*70}")
    print("比較結果")
    print(f"{'='*70}")
    
    print(f"\n{'Test':<15} {'Lazy TA-A*':>15} {'Bidirectional':>15} {'Speedup':>10}")
    print("-"*70)
    
    for i, test in enumerate(test_cases):
        lazy_result = results['Lazy TA-A*'][i]
        bi_result = results['Bidirectional Lazy TA-A*'][i]
        
        if lazy_result['success'] and bi_result['success']:
            speedup = lazy_result['time'] / bi_result['time']
            
            print(f"{test['name']:<15} "
                  f"{lazy_result['time']:>14.3f}s "
                  f"{bi_result['time']:>14.3f}s "
                  f"{speedup:>9.2f}x")
    
    # 統計
    print(f"\n{'='*70}")
    print("統計サマリー")
    print(f"{'='*70}")
    
    for algo_name in results.keys():
        algo_results = results[algo_name]
        successful = [r for r in algo_results if r['success']]
        
        if successful:
            avg_time = sum(r['time'] for r in successful) / len(successful)
            total_nodes = sum(r['nodes'] for r in successful)
            
            print(f"\n{algo_name}:")
            print(f"  成功率: {len(successful)}/{len(algo_results)}")
            print(f"  平均時間: {avg_time:.3f}s")
            print(f"  総探索ノード: {total_nodes}")
    
    print(f"\n{'='*70}")

if __name__ == '__main__':
    main()


