#!/usr/bin/env python3
"""
Run ablation experiment comparing ADAPTIVE vs FIXED_RRT.

Saves results to `results/phase2_ablation.json`.
"""
import os
import time
import json
import importlib.util
from pathlib import Path
import numpy as np


def load_module_from_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROOT = Path(__file__).resolve().parents[2]
ADAPTIVE_PY = ROOT / 'ros2' / 'ros2_ws' / 'src' / 'path_planner_3d' / 'path_planner_3d' / 'adaptive_terrain_planner.py'
RRT_PY = ROOT / 'ros2' / 'ros2_ws' / 'src' / 'path_planner_3d' / 'path_planner_3d' / 'terrain_guided_rrt_star.py'


def generate_random_terrain(seed: int, grid_size: int = 200) -> np.ndarray:
    np.random.seed(seed)
    # mix of flat + obstacles
    base = np.ones((grid_size, grid_size), dtype=np.float32) * 0.12
    # add some obstacles for variability
    for _ in range(np.random.randint(1, 6)):
        cx = np.random.randint(0, grid_size)
        cy = np.random.randint(0, grid_size)
        radius = np.random.randint(max(1, grid_size//50), max(2, grid_size//20))
        y, x = np.ogrid[:grid_size, :grid_size]
        mask = (x - cx)**2 + (y - cy)**2 <= radius**2
        base[mask] = np.random.uniform(0.4, 0.9)
    noise = np.random.normal(0, 0.02, (grid_size, grid_size))
    base = np.clip(base + noise, 0.0, 1.0)
    return base


def random_start_goal(cost_map: np.ndarray, seed: int = 0):
    rng = np.random.default_rng(seed)
    h, w = cost_map.shape
    while True:
        sx, sy = rng.integers(0, w), rng.integers(0, h)
        gx, gy = rng.integers(0, w), rng.integers(0, h)
        if np.linalg.norm(np.array([sx, sy]) - np.array([gx, gy])) < max(h, w) * 0.2:
            continue
        if cost_map[sy, sx] < 0.6 and cost_map[gy, gx] < 0.6:
            start = np.array([sx * 0.1, sy * 0.1, 0.0])
            goal = np.array([gx * 0.1, gy * 0.1, 0.0])
            bounds = ((0.0, w*0.1), (0.0, h*0.1), (0.0, 2.0))
            return start, goal, bounds


def path_length(path):
    if path is None or len(path) < 2:
        return 0.0
    return float(np.sum([np.linalg.norm(path[i+1] - path[i]) for i in range(len(path)-1)]))


def main():
    os.makedirs('results', exist_ok=True)

    if not ADAPTIVE_PY.exists() or not RRT_PY.exists():
        print("Required planner modules not found. Aborting.")
        return

    adaptive_mod = load_module_from_path('adaptive_terrain_planner', str(ADAPTIVE_PY))
    rrt_mod = load_module_from_path('terrain_guided_rrt_star', str(RRT_PY))

    AdaptiveTerrainPlanner = adaptive_mod.AdaptiveTerrainPlanner
    TerrainGuidedRRTStar = rrt_mod.TerrainGuidedRRTStar

    results = {'ADAPTIVE': [], 'FIXED_RRT': []}

    num_scenarios = 100
    for scenario_id in range(num_scenarios):
        seed = scenario_id
        terrain = generate_random_terrain(seed, grid_size=200)
        start, goal, bounds = random_start_goal(terrain, seed=seed)

        # ADAPTIVE
        planner_adaptive = AdaptiveTerrainPlanner(
            start=start,
            goal=goal,
            bounds=bounds,
            terrain_cost_map=terrain,
            resolution=0.1
        )
        t0 = time.time()
        path_adaptive = planner_adaptive.plan(timeout=30.0)
        t_ad = time.time() - t0
        res_ad = {
            'scenario': scenario_id,
            'success': path_adaptive is not None and len(path_adaptive) > 1,
            'computation_time': t_ad,
            'path_length': path_length(path_adaptive)
        }
        results['ADAPTIVE'].append(res_ad)

        # FIXED_RRT
        planner_rrt = TerrainGuidedRRTStar(
            start=start,
            goal=goal,
            bounds=bounds,
            terrain_cost_map=terrain,
            resolution=0.1,
            max_iterations=3000,
            step_size=0.5,
            goal_tolerance=0.5,
            rewire_radius=1.5
        )
        t0 = time.time()
        path_rrt = planner_rrt.plan(timeout=30.0)
        t_rrt = time.time() - t0
        res_rrt = {
            'scenario': scenario_id,
            'success': path_rrt is not None and len(path_rrt) > 1,
            'computation_time': t_rrt,
            'path_length': path_length(path_rrt)
        }
        results['FIXED_RRT'].append(res_rrt)

        if (scenario_id + 1) % 10 == 0:
            print(f"Completed {scenario_id+1}/{num_scenarios} scenarios")

    # Basic statistics
    try:
        from scipy import stats
        ad_times = [r['computation_time'] for r in results['ADAPTIVE']]
        rr_times = [r['computation_time'] for r in results['FIXED_RRT']]
        t_stat, p_value = stats.ttest_ind(ad_times, rr_times, equal_var=False)
    except Exception:
        t_stat, p_value = None, None

    out = {
        'results': results,
        'statistics': {
            't_statistic': t_stat,
            'p_value': p_value
        }
    }

    with open('results/phase2_ablation.json', 'w') as f:
        json.dump(out, f, indent=2)

    print('Ablation experiment saved to results/phase2_ablation.json')


if __name__ == '__main__':
    main()
