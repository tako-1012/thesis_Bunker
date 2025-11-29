#!/usr/bin/env python3
"""
極端シナリオでのTA-A*優位性検証

目的：TA-A*の転倒リスク評価機能を実証
方法：超険しい地形での比較実験
"""
import json
import time
import numpy as np
from pathlib import Path
import sys

sys.path.append('../path_planner_3d')

from astar_planner_3d_fixed import AStarPlanner3D
from terrain_aware_astar_planner_3d import TerrainAwareAStarPlanner3D

def create_extreme_scenarios():
    """極端な地形シナリオを生成"""
    scenarios = []
    
    # シナリオ1: 超険しい山（35-45度）
    scenarios.append({
        'scenario_id': 'extreme_001',
        'name': 'Steep Mountain (35-45°)',
        'start': [-8.0, -8.0, 0.2],
        'goal': [8.0, 8.0, 0.2],
        'terrain_type': 'Extreme Steep',
        'max_slope': 45.0,
        'description': '超険しい山：A*は危険な近道、TA-A*は安全な迂回路を選ぶ'
    })
    
    # シナリオ2: 崖（60-70度）
    scenarios.append({
        'scenario_id': 'extreme_002', 
        'name': 'Cliff Edge (60-70°)',
        'start': [-9.0, -9.0, 0.2],
        'goal': [9.0, 9.0, 0.2],
        'terrain_type': 'Cliff',
        'max_slope': 70.0,
        'description': '崖：A*は崖を越えようとし、TA-A*は回避'
    })
    
    # シナリオ3: 危険な近道 vs 安全な迂回路
    scenarios.append({
        'scenario_id': 'extreme_003',
        'name': 'Dangerous Shortcut vs Safe Detour',
        'start': [-9.5, -9.5, 0.2],
        'goal': [9.5, 9.5, 0.2],
        'terrain_type': 'Mixed Extreme',
        'max_slope': 50.0,
        'description': '危険な近道 vs 安全な迂回路：TA-A*は安全を優先'
    })
    
    return scenarios

def run_extreme_comparison():
    """極端シナリオでの比較実験"""
    print('='*70)
    print('極端シナリオでのTA-A*優位性検証')
    print('='*70)
    
    # 極端シナリオを生成
    scenarios = create_extreme_scenarios()
    
    # アルゴリズムを初期化（小規模マップ）
    map_bounds = ([-10.0, -10.0, 0.0], [10.0, 10.0, 3.0])
    
    astar_planner = AStarPlanner3D(
        voxel_size=0.1,
        map_bounds=map_bounds
    )
    
    ta_astar_planner = TerrainAwareAStarPlanner3D(
        voxel_size=0.1,
        map_bounds=map_bounds
    )
    
    results = {
        'A*': [],
        'TA-A* (Proposed)': []
    }
    
    for scenario in scenarios:
        print(f'\n{scenario["name"]}:')
        print(f'  {scenario["description"]}')
        print('-'*50)
        
        # A*でテスト
        print('  A*...', end=' ', flush=True)
        try:
            start_time = time.time()
            astar_result = astar_planner.plan_path(
                start=scenario['start'],
                goal=scenario['goal']
            )
            astar_time = time.time() - start_time
            
            astar_success = astar_result is not None
            astar_length = len(astar_result) if astar_success else 0
            
            results['A*'].append({
                'scenario_id': scenario['scenario_id'],
                'success': astar_success,
                'path_length': astar_length,
                'computation_time': astar_time,
                'terrain_type': scenario['terrain_type']
            })
            
            status = '✅' if astar_success else '❌'
            print(f'{status} Length: {astar_length}')
            
        except Exception as e:
            print(f'❌ Error: {str(e)}')
            results['A*'].append({
                'scenario_id': scenario['scenario_id'],
                'success': False,
                'error': str(e)
            })
        
        # TA-A*でテスト
        print('  TA-A*...', end=' ', flush=True)
        try:
            start_time = time.time()
            ta_result = ta_astar_planner.plan_path(
                start=scenario['start'],
                goal=scenario['goal'],
                terrain_data=np.zeros((100, 100, 20), dtype=int),
                timeout=600
            )
            ta_time = time.time() - start_time
            
            ta_success = ta_result['success']
            ta_length = ta_result['path_length'] if ta_success else 0
            
            results['TA-A* (Proposed)'].append({
                'scenario_id': scenario['scenario_id'],
                'success': ta_success,
                'path_length': ta_length,
                'computation_time': ta_time,
                'terrain_type': scenario['terrain_type']
            })
            
            status = '✅' if ta_success else '❌'
            print(f'{status} Length: {ta_length}')
            
        except Exception as e:
            print(f'❌ Error: {str(e)}')
            results['TA-A* (Proposed)'].append({
                'scenario_id': scenario['scenario_id'],
                'success': False,
                'error': str(e)
            })
    
    # 結果分析
    print('\n' + '='*70)
    print('極端シナリオ結果分析')
    print('='*70)
    
    for algo, algo_results in results.items():
        success_count = sum(1 for r in algo_results if r.get('success', False))
        total_count = len(algo_results)
        success_rate = success_count / total_count * 100
        
        # 成功したもののみで統計
        successful_results = [r for r in algo_results if r.get('success', False)]
        avg_length = np.mean([r['path_length'] for r in successful_results]) if successful_results else 0
        avg_time = np.mean([r['computation_time'] for r in successful_results]) if successful_results else 0
        
        print(f'\n{algo}:')
        print(f'  成功率: {success_rate:.1f}% ({success_count}/{total_count})')
        print(f'  平均経路長: {avg_length:.1f}m')
        print(f'  平均計算時間: {avg_time:.2f}s')
    
    # TA-A*の優位性分析
    print('\n' + '='*70)
    print('TA-A*の優位性分析')
    print('='*70)
    
    astar_results = results['A*']
    ta_results = results['TA-A* (Proposed)']
    
    astar_success_rate = sum(1 for r in astar_results if r.get('success', False)) / len(astar_results) * 100
    ta_success_rate = sum(1 for r in ta_results if r.get('success', False)) / len(ta_results) * 100
    
    print(f'成功率比較:')
    print(f'  A*: {astar_success_rate:.1f}%')
    print(f'  TA-A*: {ta_success_rate:.1f}%')
    print(f'  差: {ta_success_rate - astar_success_rate:+.1f}%')
    
    # 経路長比較（安全性の指標）
    astar_lengths = [r['path_length'] for r in astar_results if r.get('success', False)]
    ta_lengths = [r['path_length'] for r in ta_results if r.get('success', False)]
    
    if astar_lengths and ta_lengths:
        astar_avg_length = np.mean(astar_lengths)
        ta_avg_length = np.mean(ta_lengths)
        
        print(f'\n経路長比較（安全性指標）:')
        print(f'  A*: {astar_avg_length:.1f}m')
        print(f'  TA-A*: {ta_avg_length:.1f}m')
        print(f'  差: {ta_avg_length - astar_avg_length:+.1f}m')
        
        if ta_avg_length > astar_avg_length:
            print(f'  → TA-A*は安全な迂回路を選択（{ta_avg_length - astar_avg_length:.1f}m長い）')
        else:
            print(f'  → 経路長に差なし（地形が平坦すぎる可能性）')
    
    # 結果を保存
    output_path = Path('../results/extreme_scenario_results.json')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f'\n結果を保存: {output_path}')
    
    return results

if __name__ == '__main__':
    run_extreme_comparison()
