#!/usr/bin/env python3
"""
TA* プロファイリングスクリプト
Small/Medium/LargeシナリオでcProfileを実行
"""
import cProfile
import pstats
import sys
from pathlib import Path
# TA*実装ディレクトリをsys.pathに追加
ta_star_dir = Path(__file__).parent.parent / 'ros2' / 'ros2_ws' / 'src' / 'path_planner_3d' / 'path_planner_3d'
sys.path.insert(0, str(ta_star_dir))
sys.path.insert(0, str(Path(__file__).parent.parent))
from path_planner_3d.terrain_aware_astar_advanced import TerrainAwareAStar
import numpy as np

def run_ta_star(scenario_size):
    # ダミー地形・スタート/ゴール生成
    if scenario_size == 'SMALL':
        grid_size = (50, 50, 10)
        start = [0, 0, 0.2]
        goal = [40, 40, 0.2]
    elif scenario_size == 'MEDIUM':
        grid_size = (100, 100, 20)
        start = [0, 0, 0.2]
        goal = [80, 80, 0.2]
    elif scenario_size == 'LARGE':
        grid_size = (200, 200, 50)
        start = [0, 0, 0.2]
        goal = [180, 180, 0.2]
    else:
        raise ValueError('Unknown scenario size')
    terrain = np.zeros(grid_size)
    planner = TerrainAwareAStar(voxel_size=0.2, grid_size=grid_size)
    planner.set_terrain_data(terrain, None)
    path = planner.plan_path(start, goal)
    stats = getattr(planner, 'last_search_stats', {})
    success = path is not None
    time_sec = stats.get('computation_time', None)
    length_m = stats.get('path_length_meters', None)
    print(f"{scenario_size}: success={success}, time={time_sec:.3f}s, length={length_m}")

if __name__ == '__main__':
    for scenario in ['SMALL', 'MEDIUM', 'LARGE']:
        prof_file = f'ta_{scenario}.prof'
        print(f"Profiling TA* for {scenario}...")
        cProfile.run(f"run_ta_star('{scenario}')", prof_file)
        stats = pstats.Stats(prof_file)
        stats.sort_stats('cumulative').print_stats(30)
        print(f"Profile saved: {prof_file}")
