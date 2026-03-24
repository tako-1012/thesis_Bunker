"""Detailed AHA* debug for three representative scenarios.

Runs AdaptiveHybridAStar3D on three scenarios and prints detailed parameters
and last_search_stats for diagnosis.
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

import importlib


def build_voxel_grid(scenario, z_layers=8):
    obs = np.array(scenario['obstacle_map'], dtype=np.uint8)
    h, w = obs.shape
    vg = np.zeros((w, h, z_layers), dtype=np.float32)
    for z in range(z_layers):
        vg[:, :, z] = obs.T
    return vg


def run_detailed(scenario):
    mod = importlib.import_module('path_planner_3d.adaptive_hybrid_astar_3d')
    AHA = getattr(mod, 'AdaptiveHybridAStar3D')

    size = scenario['map_size']
    vg = build_voxel_grid(scenario, z_layers=max(8, size//16))

    planner = AHA(voxel_size=1.0, grid_size=(size, size, vg.shape[2]), min_bound=(0.0,0.0,0.0), max_iterations=50000, timeout=180.0)
    print('\n=== Scenario', scenario['id'], '===')
    print('env:', scenario.get('env'))
    print('grid_size:', planner.grid_size)
    print('min_bound:', planner.min_bound)
    print('voxel_size:', planner.voxel_size)
    print('max_iterations:', getattr(planner, 'max_iterations', 'N/A'))
    print('timeout:', getattr(planner, 'timeout', 'N/A'))

    planner.set_terrain_data(vg, {'height_map': np.array(scenario['height_map'])})

    start = tuple(list(scenario['start']) + [0])
    goal = tuple(list(scenario['goal']) + [0])
    print('start(world):', scenario['start'], '-> start_idx:', planner._world_to_voxel(start))
    print('goal(world):', scenario['goal'], '-> goal_idx:', planner._world_to_voxel(goal))

    t0 = time.time()
    path = planner.plan_path(start, goal)
    t1 = time.time()
    stats = planner.last_search_stats

    print('\nResult summary:')
    print('  elapsed:', f'{t1-t0:.3f}s')
    print('  path found:', path is not None)
    print('  nodes_explored:', stats.get('nodes_explored'))
    print('  path_length (nodes):', stats.get('path_length'))
    print('  computation_time (internal):', stats.get('computation_time'))

    return path, stats


def main():
    p = Path('dataset2_scenarios.json')
    if not p.exists():
        print('dataset2_scenarios.json missing')
        return
    scenarios = json.load(p.open())
    tests = [scenarios[0], scenarios[48], scenarios[96]]
    for s in tests:
        run_detailed(s)


if __name__ == '__main__':
    main()
