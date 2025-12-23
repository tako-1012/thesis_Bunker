#!/usr/bin/env python3
"""Run Medium and Large scenario experiments (48 medium, 22 large) and append results.
Progress printed every 10 runs.
"""
import json
import time
import sys
import os
from pathlib import Path
import importlib.util
import importlib.machinery
import random
import math

import numpy as np

SCENARIOS_PATH = 'scenarios/benchmark_scenarios.json'
OUT_PATH = 'ros2/ros2_ws/src/path_planner_3d/path_planner_3d/benchmark_results/dijkstra_dwa_results.json'
BASE_PP_DIR = 'ros2/ros2_ws/src/path_planner_3d/path_planner_3d'

# ensure planning_result module available for Dijkstra import
pr_path = os.path.join(BASE_PP_DIR, 'planning_result.py')
if os.path.exists(pr_path):
    spec_pr = importlib.util.spec_from_file_location('planning_result', pr_path)
    mod_pr = importlib.util.module_from_spec(spec_pr)
    spec_pr.loader.exec_module(mod_pr)
    sys.modules['planning_result'] = mod_pr
    sys.modules['path_planner_3d.planning_result'] = mod_pr

# loader for planner modules
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
    def make_terrain(terrain_type, difficulty, map_size_m=60.0):
        class TM: pass
        grid_resolution = 0.5
        grid_size = max(3, int(map_size_m / grid_resolution))
        tm = TM()
        tm.size = map_size_m
        tm.height_map = np.zeros((grid_size, grid_size))
        tm.obstacle_map = np.zeros((grid_size, grid_size), dtype=bool)
        tm.terrain_type = terrain_type
        return tm

# load scenarios
with open(SCENARIOS_PATH, 'r') as f:
    scenarios = json.load(f)

medium_pool = [s for s in scenarios if s.get('difficulty') == 'medium']
large_pool = [s for s in scenarios if s.get('difficulty') in ('hard','very_hard')]
print(f'Found medium={len(medium_pool)} large={len(large_pool)} in {SCENARIOS_PATH}')

# prepare required counts
MEDIAN_COUNT = 48
LARGE_COUNT = 22
seed = 999
rng = random.Random(seed)

def make_variants(pool, needed, map_size_m, difficulty_label):
    out = []
    i = 0
    while len(out) < needed:
        if i < len(pool):
            sc = dict(pool[i])
            sc['run_id'] = f"{sc.get('name')}_run{len(out)+1}"
            out.append(sc)
        else:
            base = pool[rng.randrange(len(pool))] if pool else {'name':'synthetic','start':[0,0,0],'goal':[map_size_m/2,0,0],'terrain_type':'flat','difficulty':difficulty_label}
            sc = dict(base)
            idx = len(out) + 1
            g = list(sc.get('goal', [map_size_m/2, 0.0, 0.0]))
            # perturb goal moderately (±1.0 m)
            g[0] = float(g[0]) + rng.uniform(-1.0, 1.0)
            g[1] = float(g[1]) + rng.uniform(-1.0, 1.0)
            sc['goal'] = g
            sc['name'] = f"{base.get('name','synthetic')}_var{idx}"
            sc['run_id'] = f"{sc['name']}_run{idx}"
            out.append(sc)
        i += 1
    return out

medium_runs = make_variants(medium_pool, MEDIAN_COUNT, map_size_m=60.0, difficulty_label='medium')
large_runs = make_variants(large_pool, LARGE_COUNT, map_size_m=120.0, difficulty_label='hard')

# load planner
DijkstraDWAPlanner = load_dijkstra_dwa()
planner = DijkstraDWAPlanner(config={'dwa': {'max_velocity': 1.0, 'max_angular_velocity': 1.0,
                                            'max_accel': 0.5, 'max_angular_accel': 0.5,
                                            'velocity_samples': 8, 'angular_samples': 8}})

# load existing results if present
if os.path.exists(OUT_PATH):
    try:
        with open(OUT_PATH, 'r') as f:
            existing = json.load(f)
    except Exception:
        existing = None
else:
    existing = None

if existing is None:
    existing = {'planner':'DIJKSTRA_DWA','total_runs':0,'successful_runs':0,'failed_runs':0,'runs':[]}

# helper to run list of scenarios with timeout and append results
def run_list(run_list, timeout, start_index=1, label='medium'):
    total = len(run_list)
    for idx, sc in enumerate(run_list, start=start_index):
        name = sc.get('name')
        print(f'[{label.upper()} {idx}/{total}] Running {name} (timeout={timeout}s)')
        map_size = 60.0 if label=='medium' else 120.0
        terrain = make_terrain(sc.get('terrain_type','flat'), sc.get('difficulty',label), map_size_m=map_size)
        start = tuple(sc.get('start', [0.0,0.0,0.0]))
        goal = tuple(sc.get('goal', [map_size*0.5, 0.0, 0.0]))

        t0 = time.time()
        try:
            res = planner.plan_path(start, goal, terrain, timeout=timeout)
            # normalize
            final_path = None
            comp_time = round(time.time() - t0, 3)
            success = False
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

            entry = {
                'scenario': name,
                'run_index': idx,
                'size_label': label,
                'success': bool(success),
                'computation_time': round(comp_time, 3),
                'path_length': round(path_length, 3),
                'error': None if success else 'No path'
            }
            existing['runs'].append(entry)
            existing['total_runs'] = existing.get('total_runs',0) + 1
            if success:
                existing['successful_runs'] = existing.get('successful_runs',0) + 1
            else:
                existing['failed_runs'] = existing.get('failed_runs',0) + 1

            print(f"  result: success={entry['success']} time={entry['computation_time']}s")
        except Exception as e:
            ct = round(time.time() - t0, 3)
            entry = {
                'scenario': name,
                'run_index': idx,
                'size_label': label,
                'success': False,
                'computation_time': ct,
                'path_length': 0.0,
                'error': str(e)
            }
            existing['runs'].append(entry)
            existing['total_runs'] = existing.get('total_runs',0) + 1
            existing['failed_runs'] = existing.get('failed_runs',0) + 1
            print(f"  ERROR: {e}")

        # progress every 10 runs
        if idx % 10 == 0:
            # write intermediate results
            out_dir = Path(OUT_PATH).parent
            out_dir.mkdir(parents=True, exist_ok=True)
            with open(OUT_PATH, 'w') as f:
                json.dump(existing, f, indent=2)
            print(f'  Progress saved after {idx} {label} runs to {OUT_PATH}')

    # final write after list
    out_dir = Path(OUT_PATH).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, 'w') as f:
        json.dump(existing, f, indent=2)
    print(f'Completed {label} runs; results flushed to {OUT_PATH}')

# Run Medium then Large
print('Starting MEDIUM experiments (48 runs, timeout=120s)')
start_time = time.time()
run_list(medium_runs, timeout=120, start_index=1, label='medium')
print('Medium experiments done. Elapsed:', round(time.time()-start_time,2),'s')

print('Starting LARGE experiments (22 runs, timeout=180s)')
start_time2 = time.time()
run_list(large_runs, timeout=180, start_index=1, label='large')
print('Large experiments done. Elapsed:', round(time.time()-start_time2,2),'s')

print('All experiments finished.')

if __name__ == '__main__':
    pass
