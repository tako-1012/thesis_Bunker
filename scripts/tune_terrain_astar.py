#!/usr/bin/env python3
"""
Terrain-Aware A* のパラメータチューニング
"""
import json
import sys
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
# ensure path_planner_3d is importable
PP3D = ROOT / 'ros2' / 'ros2_ws' / 'src' / 'path_planner_3d' / 'path_planner_3d'
if str(PP3D) not in sys.path:
    sys.path.insert(0, str(PP3D))

# ensure scripts are importable
SCRIPTS = str(ROOT / 'scripts')
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

try:
    from terrain_aware_astar import TerrainAwareAStar
except Exception as e:
    print('Failed to import TerrainAwareAStar:', e)
    raise

from create_terrain_scenarios import (
    create_hill_detour_scenario,
    create_roughness_avoidance_scenario,
    create_combined_terrain_scenario
)


configs = [
    {'name': 'Config1_TerrainFocus', 'terrain_weight': 0.5, 'heuristic': 1.2},
    {'name': 'Config2_Balanced', 'terrain_weight': 0.4, 'heuristic': 1.5},
    {'name': 'Config3_SearchControl', 'terrain_weight': 0.2, 'heuristic': 2.0},
    {'name': 'Config4_StrongControl', 'terrain_weight': 0.1, 'heuristic': 2.5},
]

scenarios = {
    'hill_detour': create_hill_detour_scenario(),
    'roughness_avoidance': create_roughness_avoidance_scenario(),
    'combined_terrain': create_combined_terrain_scenario()
}

results = {}

for config in configs:
    cfg_name = config['name']
    results[cfg_name] = {}
    print('\n' + '=' * 60)
    print(f"Testing: {cfg_name}")
    print(f"  terrain_weight={config['terrain_weight']}")
    print(f"  heuristic_multiplier={config['heuristic']}")
    print('=' * 60)

    for sname, scen in scenarios.items():
        print(f"\n  Scenario: {sname}")
        planner = TerrainAwareAStar(
            voxel_size=scen['voxel_size'],
            grid_size=scen['grid_size'],
            terrain_weight=config['terrain_weight'],
            heuristic_multiplier=config['heuristic']
        )
        # compute min_bound like other scripts
        gx, gy = scen['grid_size'][0], scen['grid_size'][1]
        half_x = (gx * scen['voxel_size']) / 2.0
        half_y = (gy * scen['voxel_size']) / 2.0
        min_bound = (-half_x, -half_y, 0.0)
        planner.set_terrain_data(scen['voxel_grid'], terrain_data=scen['terrain_data'], min_bound=min_bound)

        t0 = time.time()
        res = planner.plan_path(scen['start'], scen['goal'], timeout=30.0)
        t1 = time.time()

        # normalize result fields (handle object or dict)
        if hasattr(res, 'success'):
            success = bool(getattr(res, 'success'))
            comp_time = float(getattr(res, 'computation_time', t1 - t0))
            path_len = float(getattr(res, 'path_length', 0.0))
            nodes = int(getattr(res, 'nodes_explored', 0) or 0)
            path = getattr(res, 'path', None)
        elif isinstance(res, dict):
            success = bool(res.get('success', False))
            comp_time = float(res.get('computation_time', t1 - t0) or (t1 - t0))
            path_len = float(res.get('path_length', 0.0) or 0.0)
            nodes = int(res.get('nodes_explored', 0) or 0)
            path = res.get('path')
        else:
            success = False
            comp_time = t1 - t0
            path_len = 0.0
            nodes = 0
            path = None

        # compute terrain cost along path sample
        terrain_cost = 0.0
        if success and path and len(path) > 1:
            for i in range(len(path) - 1):
                idx = planner._world_to_voxel(path[i])
                terrain_cost += planner._compute_terrain_cost(idx)

        results[cfg_name][sname] = {
            'success': success,
            'time': comp_time,
            'path_length': path_len,
            'nodes': nodes,
            'terrain_cost': terrain_cost
        }

        print(f"    Success: {success}")
        print(f"    Time: {comp_time:.2f}s")
        print(f"    Nodes: {nodes}")
        print(f"    Path: {path_len:.2f}m")
        print(f"    Terrain Cost: {terrain_cost:.2f}")

OUT_DIR = ROOT / 'benchmark_results'
OUT_DIR.mkdir(parents=True, exist_ok=True)
out_path = OUT_DIR / 'terrain_astar_tuning.json'
with open(out_path, 'w') as f:
    json.dump(results, f, indent=2)

print('\n' + '=' * 60)
print('SUMMARY')
print('=' * 60)
for cfg_name, scres in results.items():
    total_nodes = sum(r['nodes'] for r in scres.values())
    total_time = sum(r['time'] for r in scres.values())
    success_count = sum(1 for r in scres.values() if r['success'])
    print(f"\n{cfg_name}:")
    print(f"  Success: {success_count}/3")
    print(f"  Total nodes: {total_nodes}")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Avg nodes per scenario: {total_nodes/3:.0f}")

print(f"\nSaved tuning results to {out_path}")
