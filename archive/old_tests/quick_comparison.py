#!/usr/bin/env python3
"""
TA* vs A* vs AHA* の簡易比較ベンチマーク
"""

import sys
import json
import time
import numpy as np
from datetime import datetime
sys.path.append('/home/hayashi/thesis_work/ros2/ros2_ws/src/bunker_ros2')

from path_planner_3d.astar_planner_3d import AStarPlanner3D
from path_planner_3d.adaptive_hybrid_astar_3d import AdaptiveHybridAStar3D
from path_planner_3d.terrain_aware_astar_advanced import TerrainAwareAStar

def main():
    print("=" * 70)
    print("TA* vs AHA* vs A* 簡易ベンチマーク")
    print("=" * 70)
    
    # 共通設定
    voxel_size = 0.1
    grid_size = (200, 200, 50)
    
    # マップ境界設定
    half_x = (grid_size[0] * voxel_size) / 2.0
    half_y = (grid_size[1] * voxel_size) / 2.0
    z_max = grid_size[2] * voxel_size
    
    map_bounds = {
        'x_min': -half_x,
        'x_max': half_x,
        'y_min': -half_y,
        'y_max': half_y,
        'z_min': 0.0,
        'z_max': z_max
    }
    
    # プランナー初期化
    print("\nプランナー初期化中...")
    
    planners = {
        'A*': AStarPlanner3D(
            voxel_size=voxel_size,
            grid_size=grid_size,
            use_cost_calculator=False,
            map_bounds=map_bounds
        ),
        'AHA*': AdaptiveHybridAStar3D(
            voxel_size=voxel_size,
            grid_size=grid_size,
            use_cost_calculator=False,
            map_bounds=map_bounds,
            initial_epsilon=3.0,
            refinement_epsilon=1.5,
            exploration_ratio=0.3
        ),
        'TA*': TerrainAwareAStar(
            voxel_size=voxel_size,
            grid_size=grid_size,
            use_cost_calculator=False,
            map_bounds=map_bounds,
            terrain_analysis_radius=5,
            enable_online_learning=True
        )
    }
    
    # ダミー地形データ
    voxel_grid = np.zeros(grid_size)
    
    for name, planner in planners.items():
        if hasattr(planner, 'set_terrain_data'):
            planner.set_terrain_data(voxel_grid, None)
    
    print(f"✓ {len(planners)} 個のプランナーを初期化")
    
    # テストシナリオ
    scenarios = [
        {
            'name': 'short',
            'start': (0.0, 0.0, 0.0),
            'goal': (5.0, 0.0, 0.0),
            'description': '短距離（5m）'
        },
        {
            'name': 'medium',
            'start': (0.0, 0.0, 0.0),
            'goal': (7.0, 7.0, 0.0),
            'description': '中距離斜め（約10m）'
        },
        {
            'name': 'long',
            'start': (-5.0, -5.0, 0.0),
            'goal': (5.0, 5.0, 0.0),
            'description': '長距離（約14m）'
        },
        {
            'name': 'very_long',
            'start': (-8.0, -8.0, 0.0),
            'goal': (8.0, 8.0, 0.0),
            'description': '超長距離（約23m）'
        }
    ]
    
    print(f"\n実行シナリオ: {len(scenarios)} 個")
    print("=" * 70)
    
    results = {}
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n[{i}/{len(scenarios)}] {scenario['description']}")
        print(f"スタート: {scenario['start']} → ゴール: {scenario['goal']}")
        print("-" * 70)
        
        scenario_results = {}
        
        for planner_name, planner in planners.items():
            print(f"  {planner_name:10s} ", end='', flush=True)
            
            try:
                path = planner.plan_path(
                    tuple(scenario['start']),
                    tuple(scenario['goal'])
                )
                stats = planner.get_search_stats()
                
                if path is not None:
                    # 経路距離計算
                    distance = 0.0
                    for j in range(len(path) - 1):
                        p1 = np.array(path[j])
                        p2 = np.array(path[j + 1])
                        distance += np.linalg.norm(p2 - p1)
                    
                    result = {
                        'success': True,
                        'path_length': len(path),
                        'path_distance': distance,
                        'nodes_explored': stats.get('nodes_explored', 0),
                        'computation_time': stats.get('computation_time', 0.0)
                    }
                    
                    # 追加情報
                    if planner_name == 'AHA*':
                        result['phase_transitions'] = len(stats.get('phase_transitions', []))
                    elif planner_name == 'TA*':
                        result['strategy_switches'] = stats.get('strategy_switches', 0)
                        result['terrain_types'] = len(stats.get('terrain_types_encountered', set()))
                    
                    print(f"✓ {result['computation_time']:.3f}秒, "
                          f"{result['nodes_explored']}ノード, "
                          f"{result['path_distance']:.2f}m")
                else:
                    result = {
                        'success': False,
                        'computation_time': stats.get('computation_time', 0.0)
                    }
                    print("✗ 失敗")
                
                scenario_results[planner_name] = result
            
            except Exception as e:
                print(f"✗ エラー: {e}")
                scenario_results[planner_name] = {
                    'success': False,
                    'error': str(e)
                }
        
        results[scenario['name']] = {
            'scenario': scenario,
            'results': scenario_results
        }
    
    # サマリー表示
    print("\n" + "=" * 70)
    print("ベンチマーク結果サマリー")
    print("=" * 70)
    
    for planner_name in planners.keys():
        success_count = 0
        total_time = 0.0
        total_nodes = 0
        total_distance = 0.0
        count = 0
        
        for scenario_name, data in results.items():
            result = data['results'].get(planner_name, {})
            if result.get('success'):
                success_count += 1
                total_time += result.get('computation_time', 0.0)
                total_nodes += result.get('nodes_explored', 0)
                total_distance += result.get('path_distance', 0.0)
                count += 1
        
        print(f"\n【{planner_name}】")
        print(f"  成功率: {success_count}/{len(scenarios)} ({100*success_count/len(scenarios):.1f}%)")
        
        if count > 0:
            print(f"  平均計算時間: {total_time/count:.3f}秒")
            print(f"  平均探索ノード数: {total_nodes/count:.0f}ノード")
            print(f"  平均経路長: {total_distance/count:.2f}m")
    
    # 結果保存
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f'/home/hayashi/thesis_work/results/quick_comparison_{timestamp}.json'
    
    output_data = {
        'metadata': {
            'timestamp': timestamp,
            'planners': list(planners.keys()),
            'scenarios': len(scenarios)
        },
        'results': results
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n結果を保存: {output_file}")
    print("=" * 70)

if __name__ == '__main__':
    main()
