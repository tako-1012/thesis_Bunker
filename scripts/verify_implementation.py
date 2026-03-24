#!/usr/bin/env python3
"""
TA* vs A* 実装検証スクリプト

実装の正確性を確認するためのデバッグツール:
1. プルーニングの効果を測定
2. パラメータ感度分析
3. ヒューリスティック関数の検証
4. A*での地形コスト無視の確認
"""

import sys
import json
import numpy as np
from pathlib import Path

# Add path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Try to import the implementations
try:
    from ros2.ros2_ws.src.path_planner_3d.path_planner_3d.terrain_aware_astar import TerrainAwareAStar
    from ros2.ros2_ws.src.path_planner_3d.path_planner_3d.astar_3d import AStar3D
except Exception as e:
    print(f"Warning: Could not import from ROS2 paths: {e}")
    print("Trying local imports...")


def test_pruning_effect():
    """
    テスト1: プルーニングの効果を測定
    
    目的: プルーニング距離係数 (1.5, 2.0, 2.5, 3.0) での
         ノード数の変化を観察
    """
    print("\n" + "="*70)
    print("テスト1: プルーニング距離の効果分析")
    print("="*70)
    
    # ダミーシナリオ作成
    grid_size = (100, 100, 10)
    voxel_grid = np.zeros(grid_size)
    
    # 簡単な地形データ
    terrain_data = {
        'elevation': np.random.rand(*grid_size),
        'roughness': np.random.rand(*grid_size) * 0.5,
        'density': np.random.rand(*grid_size)
    }
    
    # スタート/ゴール設定
    start = (10.0, 10.0, 1.0)
    goal = (90.0, 90.0, 1.0)
    
    prune_factors = [1.5, 2.0, 2.5, 3.0]
    results = {}
    
    for prune_factor in prune_factors:
        planner = TerrainAwareAStar(
            voxel_size=1.0,
            grid_size=grid_size,
            prune_distance_factor=prune_factor
        )
        planner.set_terrain_data(voxel_grid, terrain_data)
        
        try:
            result = planner.plan_path(start, goal, voxel_grid, max_iters=100000)
            nodes = result.get('nodes_explored', 0) if isinstance(result, dict) else result.nodes_explored
            success = result.get('success', False) if isinstance(result, dict) else result.success
            
            results[f"prune_{prune_factor}"] = {
                'nodes_explored': nodes,
                'success': success,
                'computation_time': result.get('computation_time', 0) if isinstance(result, dict) else result.computation_time
            }
            
            print(f"\nprune_distance_factor = {prune_factor}:")
            print(f"  成功: {success}")
            print(f"  探索ノード数: {nodes}")
            print(f"  計算時間: {results[f'prune_{prune_factor}']['computation_time']:.4f}秒")
            
        except Exception as e:
            print(f"\nprune_distance_factor = {prune_factor}: エラー - {e}")
            results[f"prune_{prune_factor}"] = {'error': str(e)}
    
    return results


def test_terrain_weight_sensitivity():
    """
    テスト2: 地形コスト重み付けの感度分析
    
    目的: terrain_weight = [0.1, 0.3, 0.5, 1.0] での
         計算性能とノード数の変化を観察
    """
    print("\n" + "="*70)
    print("テスト2: 地形コスト重み付けの感度分析")
    print("="*70)
    
    grid_size = (100, 100, 10)
    voxel_grid = np.zeros(grid_size)
    terrain_data = {
        'elevation': np.random.rand(*grid_size),
        'roughness': np.random.rand(*grid_size) * 0.5,
        'density': np.random.rand(*grid_size)
    }
    
    start = (10.0, 10.0, 1.0)
    goal = (90.0, 90.0, 1.0)
    
    weights = [0.1, 0.3, 0.5, 1.0]
    results = {}
    
    for weight in weights:
        planner = TerrainAwareAStar(
            voxel_size=1.0,
            grid_size=grid_size,
            terrain_weight=weight
        )
        planner.set_terrain_data(voxel_grid, terrain_data)
        
        try:
            result = planner.plan_path(start, goal, voxel_grid, max_iters=100000)
            nodes = result.get('nodes_explored', 0) if isinstance(result, dict) else result.nodes_explored
            success = result.get('success', False) if isinstance(result, dict) else result.success
            
            results[f"weight_{weight}"] = {
                'nodes_explored': nodes,
                'success': success,
                'computation_time': result.get('computation_time', 0) if isinstance(result, dict) else result.computation_time
            }
            
            print(f"\nterrain_weight = {weight}:")
            print(f"  成功: {success}")
            print(f"  探索ノード数: {nodes}")
            print(f"  計算時間: {results[f'weight_{weight}']['computation_time']:.4f}秒")
            
        except Exception as e:
            print(f"\nterrain_weight = {weight}: エラー - {e}")
            results[f"weight_{weight}"] = {'error': str(e)}
    
    return results


def test_heuristic_validity():
    """
    テスト3: ヒューリスティック関数の有効性
    
    目的: h(n) ≤ h*(n) が満たされているか検証
         （h(n)はヒューリスティック、h*(n)は実際のコスト）
    """
    print("\n" + "="*70)
    print("テスト3: ヒューリスティック関数の許容性検証")
    print("="*70)
    
    grid_size = (50, 50, 10)
    voxel_grid = np.zeros(grid_size)
    terrain_data = {
        'elevation': np.zeros(grid_size),
        'roughness': np.zeros(grid_size),
        'density': np.zeros(grid_size)
    }
    
    planner = TerrainAwareAStar(voxel_size=1.0, grid_size=grid_size)
    planner.set_terrain_data(voxel_grid, terrain_data)
    
    # テストケース: ゴールへのヒューリスティック値と実際のコスト
    goal = (40, 40, 5)
    test_positions = [
        (10, 10, 5),
        (20, 20, 5),
        (30, 30, 5),
        (35, 35, 5),
    ]
    
    print("\nヒューリスティック検証 (h(n) ≤ 実距離が必須):")
    print(f"  ゴール: {goal}")
    print()
    
    for pos in test_positions:
        h_value = planner._heuristic(pos, goal)
        # 実際の距離を計算
        dx = goal[0] - pos[0]
        dy = goal[1] - pos[1]
        dz = goal[2] - pos[2]
        actual_distance = np.sqrt(dx*dx + dy*dy + dz*dz)
        
        ratio = h_value / actual_distance if actual_distance > 0 else 0
        status = "✓ OK" if h_value <= actual_distance * 1.01 else "❌ OVER"  # 1% 許容誤差
        
        print(f"  位置 {pos}:")
        print(f"    h(n) = {h_value:.2f}, 実距離 = {actual_distance:.2f}, 比率 = {ratio:.2f}x {status}")


def test_astar_terrain_cost_usage():
    """
    テスト4: A*が地形コスト関数を使用しているか確認
    
    目的: A*がcost_function引数を実際に使用しているか検証
    """
    print("\n" + "="*70)
    print("テスト4: A*の地形コスト使用状況")
    print("="*70)
    
    grid_size = (50, 50, 10)
    voxel_grid = np.zeros(grid_size)
    
    # 地形コスト関数 (デバッグ用)
    call_count = [0]  # カウンター
    def debug_cost_function(from_pos, to_pos):
        call_count[0] += 1
        return 1.0
    
    planner = AStar3D(voxel_size=1.0, max_iterations=1000)
    
    start = (10, 10, 5)
    goal = (40, 40, 5)
    
    print(f"\nA*実行前: cost_function呼び出し数 = {call_count[0]}")
    
    try:
        # ダミーボクセルグリッド
        voxel_grid_test = np.zeros(grid_size, dtype=np.uint8)
        result = planner.plan_path(start, goal, voxel_grid_test, debug_cost_function)
        
        print(f"A*実行後: cost_function呼び出し数 = {call_count[0]}")
        
        if call_count[0] == 0:
            print("\n⚠️ 結論: A*は地形コスト関数を呼び出していない!")
            print("   これはPRACTICAL_FEASIBILITY_ANALYSIS.mdの指摘と一致")
        else:
            print(f"\n✓ A*は地形コスト関数を {call_count[0]} 回呼び出している")
            
    except Exception as e:
        print(f"エラー: {e}")


def main():
    """メイン実行"""
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*15 + "TA* vs A* 実装検証スイート" + " "*25 + "║")
    print("║" + " "*15 + "Implementation Verification Suite" + " "*20 + "║")
    print("╚" + "="*68 + "╝")
    
    results = {}
    
    try:
        results['test_1_pruning'] = test_pruning_effect()
    except Exception as e:
        print(f"テスト1 エラー: {e}")
        results['test_1_pruning'] = {'error': str(e)}
    
    try:
        results['test_2_terrain_weight'] = test_terrain_weight_sensitivity()
    except Exception as e:
        print(f"テスト2 エラー: {e}")
        results['test_2_terrain_weight'] = {'error': str(e)}
    
    try:
        test_heuristic_validity()
    except Exception as e:
        print(f"テスト3 エラー: {e}")
    
    try:
        test_astar_terrain_cost_usage()
    except Exception as e:
        print(f"テスト4 エラー: {e}")
    
    # 結果をJSONで保存
    output_file = Path(__file__).parent / "implementation_verification_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n" + "="*70)
    print(f"結果を保存: {output_file}")
    print("="*70 + "\n")


if __name__ == '__main__':
    main()
