#!/usr/bin/env python3
"""Run 30 Small scenarios with DijkstraDWAPlanner and save results.

If fewer than 30 'easy' scenarios exist in scenarios/benchmark_scenarios.json,
this script will create reproducible small variations to reach 30 runs.
"""
import json
import time
import sys
import os
from pathlib import Path
import importlib.util
import importlib.machinery
import types
import random

import numpy as np

SCENARIOS_PATH = 'scenarios/benchmark_scenarios.json'
OUT_PATH = 'ros2/ros2_ws/src/path_planner_3d/path_planner_3d/benchmark_results/dijkstra_dwa_results.json'
BASE_PP_DIR = 'ros2/ros2_ws/src/path_planner_3d/path_planner_3d'

# Load planning_result into sys.modules to help Dijkstra import
pr_path = os.path.join(BASE_PP_DIR, 'planning_result.py')
spec_pr = importlib.util.spec_from_file_location('planning_result', pr_path)
mod_pr = importlib.util.module_from_spec(spec_pr)
spec_pr.loader.exec_module(mod_pr)
sys.modules['planning_result'] = mod_pr
sys.modules['path_planner_3d.planning_result'] = mod_pr

# helper: load DijkstraDWAPlanner class via source loader (safe lazy import)
def load_dijkstra_dwa():
    base_dir = os.path.abspath(BASE_PP_DIR)
    pkg_name = 'path_planner_3d'

    def _load(mod_name, filename):
        full_name = f"{pkg_name}.{mod_name}"
        path = os.path.join(base_dir, filename)
        loader = importlib.machinery.SourceFileLoader(full_name, path)
        spec = importlib.util.spec_from_loader(loader.name, loader)
        mod = importlib.util.module_from_spec(spec)
        mod.__package__ = pkg_name
        loader.exec_module(mod)
        sys.modules[full_name] = mod
        return mod

    _ = _load('planning_result', 'planning_result.py')
    _ = _load('dijkstra_planner_3d', 'dijkstra_planner_3d.py')
    _ = _load('simple_dwa_planner', 'simple_dwa_planner.py')
    dd_mod = _load('dijkstra_dwa_planner', 'dijkstra_dwa_planner.py')
    return dd_mod.DijkstraDWAPlanner

# reuse terrain maker from v3 runner if available
try:
    spec_runner = importlib.util.spec_from_file_location('runner_v3','ros2/ros2_ws/src/bunker_ros2/simulation_manager/run_dijkstra_dwa_experiment_v3.py')
    runner_v3 = importlib.util.module_from_spec(spec_runner)
    spec_runner.loader.exec_module(runner_v3)
    make_terrain = runner_v3.make_terrain_for_scenario
except Exception:
    # fallback simple maker
    def make_terrain(terrain_type, difficulty, map_size_m=20.0):
        class TM: pass
        grid_resolution = 0.5
        grid_size = max(3, int(map_size_m / grid_resolution))
        tm = TM()
        tm.size = map_size_m
        tm.height_map = np.zeros((grid_size, grid_size))
        tm.obstacle_map = np.zeros((grid_size, grid_size), dtype=bool)
        return tm

# load scenarios
with open(SCENARIOS_PATH, 'r') as f:
    scenarios = json.load(f)

# collect 'easy' entries
easy = [s for s in scenarios if s.get('difficulty') == 'easy']
print(f'Found {len(easy)} easy scenarios in {SCENARIOS_PATH}')

# Prepare 30 runs
runs = []
seed = 12345
rng = random.Random(seed)

# Use copies of easy scenarios; if insufficient, create slight variations
i = 0
while len(runs) < 30:
    if i < len(easy):
        sc = dict(easy[i])
        sc_name = sc.get('name')
        sc['run_id'] = f'{sc_name}_run1'
        runs.append(sc)
    else:
        # create variant from a random easy scenario
        base = easy[rng.randrange(len(easy))]
        sc = dict(base)
        idx = len(runs) + 1
        # slightly perturb goal within small map bounds (±0.5m)
        g = list(sc.get('goal', [5.0, 0.0, 0.0]))
        g[0] = g[0] + rng.uniform(-0.5, 0.5)
        g[1] = g[1] + rng.uniform(-0.5, 0.5)
        sc['goal'] = g
        sc['name'] = f"{base.get('name')}_var{idx}"
        sc['run_id'] = f'{sc["name"]}_run1'
        runs.append(sc)
    i += 1

print(f'Prepared {len(runs)} small runs')

# load planner
DijkstraDWAPlanner = load_dijkstra_dwa()
planner = DijkstraDWAPlanner(config={'dwa': {'max_velocity': 1.0, 'max_angular_velocity': 1.0,
                                            'max_accel': 0.5, 'max_angular_accel': 0.5,
                                            'velocity_samples': 8, 'angular_samples': 8}})

results = []
for idx, sc in enumerate(runs, start=1):
    name = sc.get('name')
    print(f'[{idx:02d}/30] Running {name}')
    map_size = 20.0
    terrain = make_terrain(sc.get('terrain_type','flat'), sc.get('difficulty','easy'), map_size_m=map_size)
    start = tuple(sc.get('start', [0.0,0.0,0.0]))
    goal = tuple(sc.get('goal', [map_size*0.5, 0.0, 0.0]))

    t0 = time.time()
    try:
        res = planner.plan_path(start, goal, terrain, timeout=60)
        # normalize
        final_path = None
        comp_time = round(time.time() - t0, 3)
        success = False
        # handle PlanningResult if present
        pr_mod = sys.modules.get('path_planner_3d.planning_result') or sys.modules.get('planning_result')
        if pr_mod and hasattr(pr_mod, 'PlanningResult') and isinstance(res, pr_mod.PlanningResult):
            final_path = getattr(res, 'path', None)
            success = bool(getattr(res, 'success', False))
            comp_time = float(getattr(res, 'computation_time', comp_time))
        elif isinstance(res, (list, tuple)):
            if len(res) >= 2:
                final_path, comp_time = res[0], float(res[1])
                try:
                    success = bool(final_path and len(final_path) > 0)
                except Exception:
                    success = False
            elif len(res) == 1:
                final_path = res[0]
                try:
                    success = bool(final_path and len(final_path) > 0)
                except Exception:
                    success = False
        elif hasattr(res, 'path'):
            final_path = getattr(res, 'path', None)
            success = bool(getattr(res, 'success', False))
            comp_time = float(getattr(res, 'computation_time', comp_time))
        else:
            try:
                if res is None:
                    success = False
                else:
                    final_path = list(res)
                    success = bool(final_path and len(final_path) > 0)
            except Exception:
                success = False

        path_length = 0.0
        if success and final_path:
            try:
                pts = np.array(final_path)
                if pts.shape[0] >= 2:
                    diffs = np.diff(pts[:, :2], axis=0)
                    seg_lengths = np.hypot(diffs[:, 0], diffs[:, 1])
                    path_length = float(np.sum(seg_lengths))
            except Exception:
                path_length = 0.0

        results.append({
            'scenario': name,
            'run_index': idx,
            'success': bool(success),
            'computation_time': round(comp_time, 3),
            'path_length': round(path_length, 3),
            'error': None if success else 'No path'
        })
        print(f'  success={success} time={comp_time:.3f}s path_len={path_length:.3f}')
    except Exception as e:
        ct = round(time.time() - t0, 3)
        results.append({
            'scenario': name,
            'run_index': idx,
            'success': False,
            'computation_time': ct,
            'path_length': 0.0,
            'error': str(e)
        })
        print(f'  ERROR: {e}')

out = {
    'planner': 'DIJKSTRA_DWA',
    'total_runs': len(results),
    'successful_runs': sum(1 for r in results if r['success']),
    'failed_runs': sum(1 for r in results if not r['success']),
    'runs': results
}

out_dir = Path(OUT_PATH).parent
out_dir.mkdir(parents=True, exist_ok=True)
with open(OUT_PATH, 'w') as f:
    json.dump(out, f, indent=2)

print(f'Saved results to {OUT_PATH}')

if __name__ == '__main__':
    pass
