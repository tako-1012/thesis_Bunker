#!/usr/bin/env python3
"""
バグ修正の動作確認テスト
dataset3_1_1_1で各手法を実行してノード数と計算時間を確認
"""
import sys
from pathlib import Path
import json
import time
import numpy as np

PACKAGE_ROOT = '/home/hayashi/thesis_work/ros2/ros2_ws/src/path_planner_3d'
MODULE_DIR = '/home/hayashi/thesis_work/ros2/ros2_ws/src/path_planner_3d/path_planner_3d'
if PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, PACKAGE_ROOT)
if MODULE_DIR not in sys.path:
    sys.path.insert(0, MODULE_DIR)

from astar_3d import AStar3D
from terrain_aware_astar import TerrainAwareAStar
from dstar_lite_3d import DStarLite3D

def build_voxel_grid(scenario, z_layers=8):
    obs = np.array(scenario.get('obstacle_map', np.zeros((32, 32))), dtype=np.uint8)
    h, w = obs.shape
    map_size_raw = scenario.get('map_size', max(h, w))
    size = int(max(map_size_raw)) if not isinstance(map_size_raw, (list, tuple)) else int(max(map_size_raw))
    vg = np.zeros((size, size, z_layers), dtype=np.float32)
    for z in range(z_layers):
        try:
            vg[:, :, z] = obs.T
        except Exception:
            pass
    return vg

def main():
    # Load dataset3_1_1_1
    with open('dataset3_scenarios.json', 'r') as f:
        scenarios = json.load(f)
    
    test_scenario = [s for s in scenarios if s.get('id') == 'dataset3_1_1_1'][0]
    
    map_size_raw = test_scenario.get('map_size', 64)
    size = int(max(map_size_raw)) if not isinstance(map_size_raw, (list, tuple)) else int(max(map_size_raw))
    z_layers = max(8, size // 16)
    voxel_grid = build_voxel_grid(test_scenario, z_layers=z_layers)
    
    sx, sy = test_scenario.get('start', (0, 0))
    gx, gy = test_scenario.get('goal', (0, 0))
    start = (float(sx), float(sy), 0.0)
    goal = (float(gx), float(gy), 0.0)
    
    print("=" * 70)
    print(f"テストシナリオ: {test_scenario.get('id')}")
    print(f"マップサイズ: {size}×{size}")
    print(f"開始: {start}, ゴール: {goal}")
    print("=" * 70)
    
    # Test A*
    print("\n【A* テスト】")
    try:
        planner = AStar3D(voxel_size=1.0, max_iterations=500_000)
        start_time = time.time()
        path = planner.plan_path(
            (int(round(start[0])), int(round(start[1])), 0),
            (int(round(goal[0])), int(round(goal[1])), 0),
            voxel_grid,
            cost_function=lambda *_: 1.0,
        )
        elapsed = time.time() - start_time
        
        print(f"✓ 成功: {path is not None}")
        print(f"  計算時間: {elapsed:.4f}秒")
        print(f"  探索ノード数: {planner.nodes_explored}")
        print(f"  経路長: {len(path) if path else 0} ノード")
        
        # 確認: nodes_explored > len(path) であるべき
        if path and planner.nodes_explored > len(path):
            print(f"  ✅ ノード数計測が正しい（探索数 > 経路長）")
        elif path:
            print(f"  ❌ ノード数計測が間違っている可能性（探索数={planner.nodes_explored} ≤ 経路長={len(path)}）")
    except Exception as e:
        print(f"✗ エラー: {e}")
        import traceback
        traceback.print_exc()
    
    # Test TA*
    print("\n【TA* テスト】")
    try:
        planner = TerrainAwareAStar(
            voxel_size=1.0, 
            grid_size=(size, size, z_layers),
            terrain_weight=1.0,
            heuristic_multiplier=1.0
        )
        planner.set_terrain_data(voxel_grid, None, min_bound=(0.0, 0.0, 0.0))
        
        start_time = time.time()
        result = planner.plan_path(start, goal, timeout=120)
        elapsed = time.time() - start_time
        
        success = bool(getattr(result, 'success', False)) if result is not None else False
        stats = getattr(planner, 'last_search_stats', {})
        
        print(f"✓ 成功: {success}")
        print(f"  計算時間: {elapsed:.4f}秒")
        print(f"  探索ノード数: {stats.get('nodes_explored', 0)}")
        print(f"  経路長: {stats.get('path_length', 0):.2f}m")
        
        # 確認: max_iterations=500000が有効か
        if stats.get('nodes_explored', 0) > 100000:
            print(f"  ✅ max_iterations=500000が有効（100,000超の探索が可能）")
        else:
            print(f"  ⚠️ 探索ノード数が少ない（{stats.get('nodes_explored', 0)}）")
    except Exception as e:
        print(f"✗ エラー: {e}")
        import traceback
        traceback.print_exc()
    
    # Test D*Lite
    print("\n【D*Lite テスト】")
    try:
        planner = DStarLite3D(voxel_size=1.0, grid_size=(size, size, z_layers))
        planner.set_terrain_data(voxel_grid, None, min_bound=(0.0, 0.0, 0.0))
        
        start_time = time.time()
        result = planner.plan_path(start, goal)
        elapsed = time.time() - start_time
        
        success = getattr(result, 'success', False)
        nodes = getattr(result, 'nodes_explored', 0)
        path_len = getattr(result, 'path_length', 0)
        
        print(f"✓ 成功: {success}")
        print(f"  計算時間: {elapsed:.4f}秒")
        print(f"  探索ノード数: {nodes}")
        print(f"  経路長: {path_len:.2f}m")
        
        # 確認: nodes_explored が経路長より大きいはず
        if success and nodes > path_len:
            print(f"  ✅ ノード数計測が正しい（探索数 > 経路長）")
        elif success:
            print(f"  ⚠️ ノード数が経路長と同程度（探索数={nodes}, 経路={path_len:.0f}m）")
    except Exception as e:
        print(f"✗ エラー: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("動作確認完了")
    print("=" * 70)

if __name__ == '__main__':
    main()
