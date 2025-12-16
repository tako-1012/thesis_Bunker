#!/usr/bin/env python3
"""
Run sensitivity experiment for complexity threshold parameters.

Saves results to `results/phase2_sensitivity.json`.
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


def generate_random_terrain(seed: int, grid_size: int = 200) -> np.ndarray:
    np.random.seed(seed)
    base = np.ones((grid_size, grid_size), dtype=np.float32) * 0.12
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

    if not ADAPTIVE_PY.exists():
        print("Adaptive planner module not found. Aborting.")
        return

    adaptive_mod = load_module_from_path('adaptive_terrain_planner', str(ADAPTIVE_PY))
    BasePlanner = adaptive_mod.AdaptiveTerrainPlanner

    # Create a small subclass that allows custom thresholds
    class CustomAdaptivePlanner(BasePlanner):
        def __init__(self, *args, complexity_threshold_low=0.15, complexity_threshold_high=0.55, **kwargs):
            super().__init__(*args, **kwargs)
            self.complexity_threshold_low = complexity_threshold_low
            self.complexity_threshold_high = complexity_threshold_high

        def evaluate_terrain_complexity(self) -> str:
            if self.terrain_cost_map is None:
                return "SIMPLE"
            region = self.terrain_cost_map
            mean_cost = np.mean(region)
            std_cost = np.std(region)
            high_cost_ratio = np.sum(region > 0.7) / region.size
            complexity_score = mean_cost * 0.4 + std_cost * 0.3 + high_cost_ratio * 0.3
            if complexity_score < self.complexity_threshold_low:
                return "SIMPLE"
            elif complexity_score < self.complexity_threshold_high:
                return "MODERATE"
            else:
                return "COMPLEX"


    threshold_configs = {
        'NARROW': (0.10, 0.50),
        'BASELINE': (0.15, 0.55),
        'WIDE': (0.20, 0.60)
    }

    results = {}

    for name, (low, high) in threshold_configs.items():
        results[name] = []
        for scenario_id in range(50):
            seed = scenario_id
            terrain = generate_random_terrain(seed, grid_size=200)
            start, goal, bounds = random_start_goal(terrain, seed=seed)

            planner = CustomAdaptivePlanner(
                start=start,
                goal=goal,
                bounds=bounds,
                terrain_cost_map=terrain,
                resolution=0.1,
                complexity_threshold_low=low,
                complexity_threshold_high=high
            )

            t0 = time.time()
            path = planner.plan(timeout=30.0)
            elapsed = time.time() - t0

            results[name].append({
                'scenario': scenario_id,
                'success': path is not None and len(path) > 1,
                'computation_time': elapsed,
                'path_length': path_length(path)
            })

        print(f"Completed config {name}")

    # ANOVA on computation_time
    try:
        from scipy import stats
        groups = [ [r['computation_time'] for r in results[k]] for k in ['NARROW','BASELINE','WIDE'] ]
        f_stat, p_value = stats.f_oneway(*groups)
    except Exception:
        f_stat, p_value = None, None

    out = {'results': results, 'anova': {'f_statistic': f_stat, 'p_value': p_value}}
    with open('results/phase2_sensitivity.json', 'w') as f:
        json.dump(out, f, indent=2)

    print('Sensitivity experiment saved to results/phase2_sensitivity.json')


if __name__ == '__main__':
    main()
