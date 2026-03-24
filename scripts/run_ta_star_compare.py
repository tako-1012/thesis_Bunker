#!/usr/bin/env python3
import time
import json
import os
import math
import importlib.util
import numpy as np

# Path to TA* module
TA_PATH = os.path.join(os.getcwd(), 'ros2/ros2_ws/src/path_planner_3d/path_planner_3d/terrain_aware_astar_advanced.py')

ta_dir = os.path.dirname(TA_PATH)
import sys
if ta_dir not in sys.path:
    sys.path.insert(0, ta_dir)

spec = importlib.util.spec_from_file_location('terrain_aware_astar_advanced', TA_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
TerrainAwareAStar = module.TerrainAwareAStar

# Simple dummy voxel grid and terrain data
grid_size = (80, 80, 20)
voxel_grid = np.zeros(grid_size, dtype=np.uint8)
terrain_data = np.zeros((grid_size[0], grid_size[1]), dtype=np.float32)

# Representative scenarios (small/medium/large)
scenarios = {
    'SMALL': {'name': 'scenario_small_simple_001', 'start': (0.0, 0.0, 0.0), 'goal': (5.0, 0.0, 0.0)},
    'MEDIUM': {'name': 'scenario_medium_simple_001', 'start': (0.0, 0.0, 0.0), 'goal': (7.0, 7.0, 0.0)},
    'LARGE': {'name': 'scenario_large_simple_001', 'start': (0.0, 0.0, 0.0), 'goal': (15.0, 15.0, 0.0)}
}

results = {}

planner = TerrainAwareAStar(voxel_size=0.1, grid_size=grid_size)
planner.set_terrain_data(voxel_grid, terrain_data)

for key, s in scenarios.items():
    start = s['start']
    goal = s['goal']
    t0 = time.time()
    try:
        path = planner.plan_path(start, goal)
    except Exception as e:
        path = None
        print(f"Error running TA* on {key}: {e}")
    elapsed = time.time() - t0
    if path:
        # compute path length
        plen = 0.0
        for i in range(len(path)-1):
            a = np.array(path[i]); b = np.array(path[i+1])
            plen += math.dist(a, b)
        success = True
    else:
        plen = 0.0
        success = False
    nodes = planner.last_search_stats.get('nodes_explored', 0)
    results[s['name']] = {
        'env': key,
        'computation_time': elapsed,
        'path_length_meters': plen,
        'success': success,
        'nodes_explored': nodes
    }

out_file = os.path.join(os.getcwd(), 'ta_star_commit_test.json')
with open(out_file, 'w') as f:
    json.dump(results, f, indent=2)
print('Wrote', out_file)
print(json.dumps(results, indent=2))
