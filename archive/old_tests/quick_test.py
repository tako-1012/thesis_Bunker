#!/usr/bin/env python3
"""クイックテスト - 3シナリオのみで高速実行"""

import sys
sys.path.append('/home/hayashi/thesis_work/ros2/ros2_ws/src/bunker_ros2')

import numpy as np
import time
from path_planner_3d.astar_planner_3d import AStarPlanner3D
from path_planner_3d.adaptive_hybrid_astar_3d import AdaptiveHybridAStar3D

print("=" * 60)
print("クイックテスト: A* vs AHA*")
print("=" * 60)

# 簡単なテストシナリオ
scenarios = [
    {"name": "短距離", "start": (0, 0, 0), "goal": (5, 0, 0)},
    {"name": "中距離", "start": (0, 0, 0), "goal": (7, 7, 0)},
    {"name": "長距離", "start": (-5, -5, 0), "goal": (5, 5, 0)},
]

# プランナー初期化（負の座標に対応）
map_bounds = {
    'x_min': -10.0, 'x_max': 10.0,
    'y_min': -10.0, 'y_max': 10.0,
    'z_min': 0.0, 'z_max': 3.0
}

astar = AStarPlanner3D(
    voxel_size=0.1, 
    grid_size=(200, 200, 30),
    min_bound=(-10.0, -10.0, 0.0),
    map_bounds=map_bounds
)
aha = AdaptiveHybridAStar3D(
    voxel_size=0.1, 
    grid_size=(200, 200, 30),
    min_bound=(-10.0, -10.0, 0.0),
    map_bounds=map_bounds
)

print("\n実行中...")
results = {}

for scenario in scenarios:
    print(f"\n【{scenario['name']}】 {scenario['start']} → {scenario['goal']}")
    
    # A*
    start_time = time.time()
    path_astar = astar.plan_path(scenario['start'], scenario['goal'])
    time_astar = time.time() - start_time
    stats_astar = astar.get_search_stats()
    
    # AHA*
    start_time = time.time()
    path_aha = aha.plan_path(scenario['start'], scenario['goal'])
    time_aha = time.time() - start_time
    stats_aha = aha.get_search_stats()
    
    # 結果表示
    print(f"  A*  : {time_astar:.3f}秒, {stats_astar['nodes_explored']}ノード")
    print(f"  AHA*: {time_aha:.3f}秒, {stats_aha['nodes_explored']}ノード", end="")
    
    if path_astar and path_aha:
        speedup = (time_astar / time_aha - 1) * 100
        if speedup > 0:
            print(f" → {speedup:.1f}% 高速化！ ✓")
        else:
            print(f" → {-speedup:.1f}% 遅い")
    else:
        print(" → 失敗")

print("\n" + "=" * 60)
print("テスト完了！")
print("=" * 60)
