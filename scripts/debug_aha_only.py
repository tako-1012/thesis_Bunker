"""Debug AHA* coordinate transform and grid bounds for representative scenarios."""
import sys
from pathlib import Path
import json
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
    vg = np.zeros((h, w, z_layers), dtype=np.float32)
    for z in range(z_layers):
        vg[:, :, z] = obs  # keep natural orientation
    return vg


def main():
    p = Path('dataset2_scenarios.json')
    if not p.exists():
        print('dataset2_scenarios.json not found')
        return
    scenarios = json.load(p.open())
    tests = [scenarios[0], scenarios[48], scenarios[96]]

    mod = importlib.import_module('path_planner_3d.adaptive_hybrid_astar_3d')
    AHA = getattr(mod, 'AdaptiveHybridAStar3D')

    for s in tests:
        print('\n=== Scenario', s['id'], '===')
        print('env:', s['env'], 'map_size:', s['map_size'])
        print('start (raw):', s['start'], 'goal (raw):', s['goal'])
        obs = np.array(s['obstacle_map'])
        print('obstacle_map.shape=', obs.shape)

        vg = build_voxel_grid(s, z_layers=max(8, s['map_size']//16))
        print('voxel_grid.shape=', vg.shape)

        planner = AHA(voxel_size=1.0, grid_size=(s['map_size'], s['map_size'], vg.shape[2]), min_bound=(0.0,0.0,0.0))
        print('planner.min_bound=', planner.min_bound)
        print('planner.voxel_size=', planner.voxel_size)
        print('planner.grid_size=', planner.grid_size)

        # set voxel grid
        planner.set_terrain_data(vg, {'height_map': np.array(s['height_map'])})

        try:
            start_grid = planner._world_to_voxel(tuple(list(s['start']) + [0]))
            goal_grid = planner._world_to_voxel(tuple(list(s['goal']) + [0]))
            print('world_to_voxel -> start_grid=', start_grid, 'goal_grid=', goal_grid)
            print('_is_in_grid start=', planner._is_in_grid(start_grid), 'goal=', planner._is_in_grid(goal_grid))
        except Exception as e:
            print('Error during conversion:', e)


if __name__ == '__main__':
    main()
