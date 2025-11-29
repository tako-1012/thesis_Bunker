#!/usr/bin/env python3
"""
Phase 1 Complete 50実験検証

TA-A* Optimized vs Phase 1 を比較
"""
import sys
import json
import time
import numpy as np
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from tastar_optimized import TerrainAwareAStarOptimized
from tastar_phase1_complete import TAStarPhase1Complete

def run_phase1_validation():
    """Phase 1の50実験検証"""
    print("="*70)
    print("Phase 1 Complete Validation")
    print("="*70)
    
    # プランナー初期化
    config = {
        'map_bounds': ([-50, -50, 0], [50, 50, 10]),
        'voxel_size': 0.2
    }
    
    tastar_optimized = TerrainAwareAStarOptimized(**config)
    tastar_phase1 = TAStarPhase1Complete(**config)
    
    # テストシナリオ生成
    np.random.seed(42)
    terrains = ['flat', 'gentle', 'steep', 'complex', 'extreme']
    scenarios = []
    
    for terrain in terrains:
        for trial in range(1, 11):  # 各地形10回
            start = [
                np.random.uniform(-40, 40),
                np.random.uniform(-40, 40),
                0.2
            ]
            goal = [
                np.random.uniform(-40, 40),
                np.random.uniform(-40, 40),
                0.2
            ]
            
            # 最低距離チェック
            dist = np.linalg.norm(np.array(goal) - np.array(start))
            if dist < 5.0:
                goal = [
                    start[0] + np.random.uniform(5, 15),
                    start[1] + np.random.uniform(5, 15),
                    0.2
                ]
            
            scenarios.append({
                'terrain': terrain,
                'trial': trial,
                'start': start,
                'goal': goal
            })
    
    print(f"\n総実験数: {len(scenarios)} × 2アルゴリズム = {len(scenarios) * 2}")
    print("\n実験開始...\n")
    
    results = []
    start_time = time.time()
    
    for i, scenario in enumerate(scenarios):
        print(f"\r[{i+1}/{len(scenarios)}] {scenario['terrain']} trial {scenario['trial']}", end='')
        
        # TA-A* Optimized
        try:
            result = tastar_optimized.plan_path(
                scenario['start'],
                scenario['goal'],
                timeout=60
            )
            
            results.append({
                'terrain': scenario['terrain'],
                'trial': scenario['trial'],
                'algorithm': 'TA-A* Optimized',
                'success': result.success,
                'computation_time': result.computation_time,
                'path_length': result.path_length if result.success else 0,
                'nodes_explored': result.nodes_explored
            })
        except Exception as e:
            results.append({
                'terrain': scenario['terrain'],
                'trial': scenario['trial'],
                'algorithm': 'TA-A* Optimized',
                'success': False,
                'computation_time': 0,
                'path_length': 0,
                'nodes_explored': 0,
                'error': str(e)
            })
        
        # TA-A* Phase 1
        try:
            result = tastar_phase1.plan_path(
                scenario['start'],
                scenario['goal'],
                timeout=60
            )
            
            results.append({
                'terrain': scenario['terrain'],
                'trial': scenario['trial'],
                'algorithm': 'TA-A* Phase 1',
                'success': result.success,
                'computation_time': result.computation_time,
                'path_length': result.path_length if result.success else 0,
                'nodes_explored': result.nodes_explored
            })
        except Exception as e:
            results.append({
                'terrain': scenario['terrain'],
                'trial': scenario['trial'],
                'algorithm': 'TA-A* Phase 1',
                'success': False,
                'computation_time': 0,
                'path_length': 0,
                'nodes_explored': 0,
                'error': str(e)
            })
    
    elapsed = time.time() - start_time
    print(f"\n\n実験完了: {elapsed:.1f}秒")
    
    # 結果保存
    output_dir = Path('../results/phase1_complete')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / 'validation_results.json'
    with open(output_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'total_time': elapsed,
            'results': results
        }, f, indent=2)
    
    print(f"✅ 結果保存: {output_file}")
    
    # 統計分析
    print("\n" + "="*70)
    print("統計分析")
    print("="*70)
    
    for algo_name in ['TA-A* Optimized', 'TA-A* Phase 1']:
        algo_results = [r for r in results if r['algorithm'] == algo_name]
        
        success_count = sum(1 for r in algo_results if r['success'])
        total = len(algo_results)
        success_rate = success_count / total * 100
        
        successful_results = [r for r in algo_results if r['success']]
        if successful_results:
            avg_time = np.mean([r['computation_time'] for r in successful_results])
            avg_nodes = np.mean([r['nodes_explored'] for r in successful_results])
        else:
            avg_time = avg_nodes = 0
        
        print(f"\n{algo_name}:")
        print(f"  成功率: {success_rate:.1f}% ({success_count}/{total})")
        print(f"  平均処理時間: {avg_time:.3f}秒")
        print(f"  平均探索ノード: {avg_nodes:.0f}")
    
    # 比較
    optimized_results = [r for r in results if r['algorithm'] == 'TA-A* Optimized' and r['success']]
    phase1_results = [r for r in results if r['algorithm'] == 'TA-A* Phase 1' and r['success']]
    
    if optimized_results and phase1_results:
        opt_avg_time = np.mean([r['computation_time'] for r in optimized_results])
        phase1_avg_time = np.mean([r['computation_time'] for r in phase1_results])
        speedup = opt_avg_time / phase1_avg_time if phase1_avg_time > 0 else 0
        
        print("\n" + "="*70)
        print("改善効果")
        print("="*70)
        print(f"TA-A* Optimized: {opt_avg_time:.3f}秒")
        print(f"TA-A* Phase 1: {phase1_avg_time:.3f}秒")
        if speedup > 1:
            print(f"→ Phase 1が{speedup:.2f}倍高速")
        else:
            print(f"→ Optimizedが{1/speedup:.2f}倍高速")

if __name__ == '__main__':
    run_phase1_validation()


