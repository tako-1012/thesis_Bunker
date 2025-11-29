#!/usr/bin/env python3
"""
TA-A* (Terrain-Aware A*) の基本テスト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from terrain_aware_astar_planner_3d import TerrainAwareAStarPlanner3D, TAStarResult
import numpy as np
import time

def test_ta_astar_basic():
    """TA-A*の基本テスト"""
    print("=== TA-A* Basic Test ===")
    
    # プランナー初期化
    planner = TerrainAwareAStarPlanner3D(
        grid_size=(50, 50, 20),
        voxel_size=0.1,
        max_slope=30.0
    )
    
    # テストシナリオ
    start = (0.0, 0.0, 0.0)
    goal = (2.0, 2.0, 0.5)
    
    # 簡易地形データ（クラスとして実装）
    class SimpleTerrainData:
        def __init__(self):
            self.terrain_type = 'Flat Terrain'
    
    terrain_data = SimpleTerrainData()
    
    print(f"Start: {start}")
    print(f"Goal: {goal}")
    print(f"Terrain type: {terrain_data.terrain_type}")
    
    # 経路計画実行
    start_time = time.time()
    result = planner.plan_path(start, goal, terrain_data)
    end_time = time.time()
    
    # 結果表示
    print(f"\n=== Results ===")
    print(f"Success: {result.success}")
    print(f"Computation time: {result.computation_time:.3f}s")
    print(f"Path length: {result.path_length:.3f}m")
    print(f"Nodes explored: {result.nodes_explored}")
    print(f"Risk score: {result.risk_score:.3f}")
    print(f"Terrain adaptations: {result.terrain_adaptations}")
    
    if result.success:
        print(f"Path points: {len(result.path)}")
        print(f"First few points: {result.path[:3]}")
    else:
        print(f"Error: {result.error_message}")
    
    return result

def test_ta_astar_terrain_types():
    """異なる地形タイプでのテスト"""
    print("\n=== TA-A* Terrain Types Test ===")
    
    planner = TerrainAwareAStarPlanner3D()
    
    terrain_types = [
        'Flat Terrain',
        'Gentle Slope', 
        'Steep Slope',
        'Mixed Terrain',
        'Obstacle Field',
        'Narrow Passage',
        'Complex 3D'
    ]
    
    start = (0.0, 0.0, 0.0)
    goal = (1.0, 1.0, 0.2)
    
    results = {}
    
    for terrain_type in terrain_types:
        print(f"\nTesting {terrain_type}...")
        
        class TerrainData:
            def __init__(self, terrain_type):
                self.terrain_type = terrain_type
        
        terrain_data = TerrainData(terrain_type)
        
        result = planner.plan_path(start, goal, terrain_data)
        
        results[terrain_type] = {
            'success': result.success,
            'computation_time': result.computation_time,
            'path_length': result.path_length,
            'risk_score': result.risk_score,
            'terrain_adaptations': result.terrain_adaptations
        }
        
        print(f"  Success: {result.success}")
        print(f"  Time: {result.computation_time:.3f}s")
        print(f"  Risk: {result.risk_score:.3f}")
        print(f"  Adaptations: {result.terrain_adaptations}")
    
    return results

def test_ta_astar_vs_astar():
    """TA-A*と標準A*の比較テスト"""
    print("\n=== TA-A* vs A* Comparison ===")
    
    # TA-A*プランナー
    ta_planner = TerrainAwareAStarPlanner3D()
    
    # 標準A*プランナー（簡易版）
    from astar_planner_3d import AStarPlanner3D
    astar_planner = AStarPlanner3D()
    
    start = (0.0, 0.0, 0.0)
    goal = (2.0, 2.0, 0.5)
    
    class TerrainData:
        def __init__(self):
            self.terrain_type = 'Mixed Terrain'
    
    terrain_data = TerrainData()
    
    # TA-A*実行
    print("Running TA-A*...")
    ta_result = ta_planner.plan_path(start, goal, terrain_data)
    
    # 標準A*実行
    print("Running A*...")
    astar_result = astar_planner.plan_path(start, goal)
    
    # 比較結果
    print(f"\n=== Comparison Results ===")
    print(f"TA-A* Success: {ta_result.success}")
    print(f"A* Success: {astar_result is not None}")
    
    if ta_result.success and astar_result is not None:
        print(f"\nTA-A*:")
        print(f"  Time: {ta_result.computation_time:.3f}s")
        print(f"  Path length: {ta_result.path_length:.3f}m")
        print(f"  Risk score: {ta_result.risk_score:.3f}")
        print(f"  Adaptations: {ta_result.terrain_adaptations}")
        
        print(f"\nA*:")
        print(f"  Time: {astar_planner.last_search_stats['computation_time']:.3f}s")
        print(f"  Path length: {len(astar_result)} points")
        print(f"  Nodes explored: {astar_planner.last_search_stats['nodes_explored']}")
    
    return ta_result, astar_result

if __name__ == "__main__":
    print("TA-A* (Terrain-Aware A*) Test Suite")
    print("=" * 50)
    
    # 基本テスト
    basic_result = test_ta_astar_basic()
    
    # 地形タイプテスト
    terrain_results = test_ta_astar_terrain_types()
    
    # 比較テスト
    comparison_results = test_ta_astar_vs_astar()
    
    print("\n" + "=" * 50)
    print("All tests completed!")
