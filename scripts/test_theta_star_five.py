#!/usr/bin/env python3
"""Theta* vs TA* 5-scenario test harness

Runs Theta* and TA* on 5 representative scenarios and writes JSON results.
"""
import json
import time
from pathlib import Path
import sys
import numpy as np

# ensure planners are importable
repo_root = Path(__file__).parent.parent
ta_star_dir = repo_root / 'ros2' / 'ros2_ws' / 'src' / 'path_planner_3d' / 'path_planner_3d'
sys.path.insert(0, str(ta_star_dir))
sys.path.insert(0, str(repo_root))

from path_planner_3d.terrain_aware_astar_advanced import TerrainAwareAStar
import importlib.util
theta_src = ta_star_dir / 'theta_star.py'
spec = importlib.util.spec_from_file_location('theta_star', str(theta_src))
theta_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(theta_mod)
ThetaStar = getattr(theta_mod, 'ThetaStar')


def path_length_meters(path):
    if not path:
        return None
    total = 0.0
    for a, b in zip(path[:-1], path[1:]):
        dx = a[0] - b[0]
        dy = a[1] - b[1]
        dz = a[2] - b[2]
        total += (dx*dx + dy*dy + dz*dz) ** 0.5
    return total


def make_empty(grid_size):
    return np.zeros(grid_size)


def make_wall_with_gap(grid_size, axis=0, gap_pos=None, gap_size=2):
    grid = np.zeros(grid_size)
    if gap_pos is None:
        gap_pos = grid_size[1] // 2
    if axis == 0:
        x = grid_size[0] // 2
        grid[x, :, :] = 1.0
        # carve gap
        grid[x, gap_pos-gap_size:gap_pos+gap_size, :] = 0.0
    else:
        y = grid_size[1] // 2
        grid[:, y, :] = 1.0
        grid[gap_pos-gap_size:gap_pos+gap_size, y, :] = 0.0
    return grid


def run_scenario(name, grid_size, start_idx, goal_idx, terrain):
    results = {'scenario': name, 'grid_size': grid_size, 'start_idx': start_idx, 'goal_idx': goal_idx}

    # TA*
    ta = TerrainAwareAStar(voxel_size=0.2, grid_size=grid_size)
    ta.set_terrain_data(terrain, None)
    # convert voxel index -> world coords consistently for both planners
    start = ta._voxel_to_world(tuple(start_idx))
    goal = ta._voxel_to_world(tuple(goal_idx))
    t0 = time.time()
    path_ta = ta.plan_path(start, goal)
    ta_time = getattr(ta, 'last_search_stats', {}).get('computation_time', time.time() - t0)
    ta_nodes = getattr(ta, 'last_search_stats', {}).get('nodes_explored', None)
    ta_len = path_length_meters(path_ta) if path_ta else None
    results['TA_STAR'] = {'success': path_ta is not None, 'time': ta_time, 'nodes': ta_nodes, 'path_length_m': ta_len}

    # Theta*
    th = ThetaStar(voxel_size=0.2, grid_size=grid_size)
    # provide same min_bound as TA*
    th.set_terrain_data(terrain, None, min_bound=ta.min_bound)
    t0 = time.time()
    path_th = th.plan_path(start, goal)
    th_time = th.last_search_stats.get('computation_time', time.time() - t0)
    th_nodes = th.last_search_stats.get('nodes_explored', None)
    th_len = path_length_meters(path_th) if path_th else None
    results['THETA_STAR'] = {'success': path_th is not None, 'time': th_time, 'nodes': th_nodes, 'path_length_m': th_len}

    # include world start/goal in results
    results['start_world'] = start
    results['goal_world'] = goal
    return results


def main():
    scenarios = []

    # SMALL empty: start/goal voxel indices
    scenarios.append(('SMALL_EMPTY', (50, 50, 10), (1, 1, 1), (40, 40, 1), make_empty((50,50,10))))
    # MEDIUM empty
    scenarios.append(('MEDIUM_EMPTY', (100, 100, 20), (1, 1, 1), (80, 80, 1), make_empty((100,100,20))))
    # LARGE empty
    scenarios.append(('LARGE_EMPTY', (200, 200, 50), (1, 1, 1), (180, 180, 1), make_empty((200,200,50))))
    # MEDIUM wall with gap (start/goal voxel indices)
    scenarios.append(('MEDIUM_WALL', (100, 100, 20), (5, 5, 1), (90, 90, 1), make_wall_with_gap((100,100,20), axis=0)))
    # LARGE wall with gap
    scenarios.append(('LARGE_WALL', (200, 200, 50), (5, 5, 1), (190, 190, 1), make_wall_with_gap((200,200,50), axis=1)))

    results = []
    for name, grid_size, start, goal, terrain in scenarios:
        print(f"Running {name}...")
        res = run_scenario(name, grid_size, start, goal, terrain)
        results.append(res)

    out = Path(__file__).parent.parent / 'theta_star_test_results.json'
    with open(out, 'w') as f:
        json.dump(results, f, indent=2)
    print('Wrote', out)

    # simple summary comparison
    summary = []
    for r in results:
        ta = r['TA_STAR']
        th = r['THETA_STAR']
        summary.append({
            'scenario': r['scenario'],
            'ta_success': ta['success'], 'th_success': th['success'],
            'ta_time': ta['time'], 'th_time': th['time'],
            'ta_path_m': ta['path_length_m'], 'th_path_m': th['path_length_m']
        })

    out2 = Path(__file__).parent.parent / 'theta_vs_ta_summary.json'
    with open(out2, 'w') as f:
        json.dump(summary, f, indent=2)
    print('Wrote', out2)


if __name__ == '__main__':
    main()
