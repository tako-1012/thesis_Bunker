#!/usr/bin/env python3
"""
Lazy TA-A* テストスクリプト

完全に独立したテスト
"""
import sys
from pathlib import Path

# lazy_tastarディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from lazy_tastar import LazyTAstar

def main():
    print("="*70)
    print("Lazy TA-A* 包括的テスト")
    print("="*70)
    
    planner = LazyTAstar(voxel_size=0.5, map_size=50.0, goal_threshold=1.0)
    
    # テストケース
    test_cases = [
        # 簡単
        {'name': 'Very Short', 'start': [0, 0, 0.2], 'goal': [5, 5, 0.2]},
        {'name': 'Short', 'start': [0, 0, 0.2], 'goal': [10, 10, 0.2]},
        
        # 中距離
        {'name': 'Medium-1', 'start': [0, 0, 0.2], 'goal': [15, 15, 0.2]},
        {'name': 'Medium-2', 'start': [0, 0, 0.2], 'goal': [20, 20, 0.2]},
        {'name': 'Medium-3', 'start': [-10, -10, 0.2], 'goal': [10, 10, 0.2]},
        
        # 長距離
        {'name': 'Long-1', 'start': [-15, -15, 0.2], 'goal': [15, 15, 0.2]},
        {'name': 'Long-2', 'start': [-20, -20, 0.2], 'goal': [20, 20, 0.2]},
        
        # 異なる高度
        {'name': 'Different Z-1', 'start': [0, 0, 0.2], 'goal': [10, 10, 0.5]},
        {'name': 'Different Z-2', 'start': [0, 0, 0.2], 'goal': [10, 10, 1.0]},
    ]
    
    results = []
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*70}")
        print(f"Test {i}/{len(test_cases)}: {test['name']}")
        print(f"  Start: {test['start']}")
        print(f"  Goal:  {test['goal']}")
        print(f"{'='*70}")
        
        result = planner.plan_path(test['start'], test['goal'], timeout=120)
        
        results.append({
            'name': test['name'],
            'success': result.success,
            'time': result.computation_time,
            'length': result.path_length,
            'nodes': result.nodes_explored,
            'phase': result.phase_used if result.success else 0
        })
        
        if result.success:
            print(f"\n✅ SUCCESS")
            print(f"  Phase: {result.phase_used}")
            print(f"  Time: {result.computation_time:.2f}s")
            print(f"  Path length: {result.path_length:.2f}m")
            print(f"  Nodes explored: {result.nodes_explored}")
        else:
            print(f"\n❌ FAILED: {result.error_message}")
    
    # サマリー
    print(f"\n{'='*70}")
    print("テストサマリー")
    print(f"{'='*70}")
    
    successes = sum(1 for r in results if r['success'])
    total = len(results)
    
    print(f"\n成功率: {successes}/{total} ({successes/total*100:.1f}%)")
    
    if successes > 0:
        successful = [r for r in results if r['success']]
        avg_time = sum(r['time'] for r in successful) / len(successful)
        avg_length = sum(r['length'] for r in successful) / len(successful)
        avg_nodes = sum(r['nodes'] for r in successful) / len(successful)
        
        print(f"\n成功したテストの統計:")
        print(f"  平均時間: {avg_time:.2f}s")
        print(f"  平均経路長: {avg_length:.2f}m")
        print(f"  平均探索ノード: {avg_nodes:.0f}個")
        
        # Phase別
        phase_counts = {}
        for r in successful:
            phase = r['phase']
            phase_counts[phase] = phase_counts.get(phase, 0) + 1
        
        print(f"\nPhase別成功数:")
        for phase in sorted(phase_counts.keys()):
            print(f"  Phase {phase}: {phase_counts[phase]}回")
    
    # 詳細結果
    print(f"\n{'='*70}")
    print("詳細結果")
    print(f"{'='*70}")
    
    print(f"\n{'No':<4} {'Name':<20} {'Status':<8} {'Time':>8} {'Length':>10} {'Phase':>6}")
    print("-"*70)
    
    for i, r in enumerate(results, 1):
        status = "✅ OK" if r['success'] else "❌ FAIL"
        time_str = f"{r['time']:.2f}s"
        length_str = f"{r['length']:.2f}m" if r['success'] else "-"
        phase_str = f"{r['phase']}" if r['success'] else "-"
        
        print(f"{i:<4} {r['name']:<20} {status:<8} {time_str:>8} {length_str:>10} {phase_str:>6}")
    
    print(f"\n{'='*70}")
    print("テスト完了！")
    print(f"{'='*70}")

if __name__ == '__main__':
    main()


