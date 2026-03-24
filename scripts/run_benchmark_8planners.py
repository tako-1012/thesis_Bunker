#!/usr/bin/env python3
"""
Run dataset3 benchmark with 8 planners (includes FieldD*Hybrid and MPAA*)

Saves:
- benchmark_results/dataset3_8planners_results.json
- benchmark_results/dataset3_8planners_summary.json
"""
import sys
from pathlib import Path
import json
import time
import multiprocessing as mp

import numpy as np
import importlib

PACKAGE_ROOT = '/home/hayashi/thesis_work/ros2/ros2_ws/src/path_planner_3d'
MODULE_DIR = '/home/hayashi/thesis_work/ros2/ros2_ws/src/path_planner_3d/path_planner_3d'
if PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, PACKAGE_ROOT)
if MODULE_DIR not in sys.path:
    sys.path.insert(0, MODULE_DIR)


def build_voxel_grid(scenario, z_layers=8):
    obs = np.array(scenario.get('obstacle_map', np.zeros((32, 32))), dtype=np.uint8)
    h, w = obs.shape
    map_size_raw = scenario.get('map_size', max(h, w))
    size = int(max(map_size_raw)) if not isinstance(map_size_raw, (list, tuple)) else int(max(map_size_raw))
    vg = np.zeros((size, size, z_layers), dtype=np.float32)
    for z in range(z_layers):
        try:
            vg[:, :, z] = obs.T
        except Exception:
            pass
    return vg


def run_planner_on_scenario(args):
    planner_name, scenario, timeout = args
    sid = scenario.get('id', 'unknown')
    start_time = time.time()
    try:
        map_size_raw = scenario.get('map_size', 64)
        size = int(max(map_size_raw)) if not isinstance(map_size_raw, (list, tuple)) else int(max(map_size_raw))
        z_layers = max(8, size // 16)
        voxel_grid = build_voxel_grid(scenario, z_layers=z_layers)
        terrain_data = {'height_map': np.array(scenario.get('height_map', np.zeros((size, size))))}

        sx, sy = scenario.get('start', (0, 0))
        gx, gy = scenario.get('goal', (0, 0))
        start = (float(sx), float(sy), 0.0)
        goal = (float(gx), float(gy), 0.0)

        # dispatch planners
        if planner_name == 'FieldD*Hybrid':
            from field_d_star_hybrid import FieldDStarHybrid
            planner = FieldDStarHybrid(voxel_size=1.0, grid_size=(size, size, z_layers))
            planner.set_terrain_data(voxel_grid, terrain_data, min_bound=(0.0,0.0,0.0))
            res = planner.plan_path(start, goal, timeout=timeout)
            success = bool(getattr(res, 'success', False))
            nodes = int(getattr(res, 'nodes_explored', planner.last_search_stats.get('nodes_explored', 0)))
            plen = float(getattr(res, 'path_length', planner.last_search_stats.get('path_length', 0)))

        elif planner_name == 'MPAA*':
            from mpaa_star import MPAAStar
            planner = MPAAStar(voxel_size=1.0, grid_size=(size, size, z_layers))
            planner.set_terrain_data(voxel_grid, terrain_data, min_bound=(0.0,0.0,0.0))
            res = planner.plan_path(start, goal, timeout=timeout)
            success = bool(getattr(res, 'success', False))
            nodes = int(getattr(res, 'nodes_explored', 0))
            plen = float(getattr(res, 'path_length', 0))

        else:
            # fallback to existing full_benchmark_6_planners dispatch by importing its helper
            # replicate necessary planners: TA*, Theta*, RRT*, D*Lite, HPA*, SAFETY
            if planner_name == 'TA*':
                from terrain_aware_astar_advanced import TerrainAwareAStar
                planner = TerrainAwareAStar(voxel_size=1.0, grid_size=(size, size, voxel_grid.shape[2]), min_bound=(0.0, 0.0, 0.0))
                planner.set_terrain_data(voxel_grid, terrain_data)
                path = planner.plan_path(start, goal, timeout=timeout)
                success = path is not None
                nodes = planner.last_search_stats.get('nodes_explored', 0)
                plen = planner.last_search_stats.get('path_length', 0)

            elif planner_name == 'Theta*':
                from theta_star import ThetaStar
                planner = ThetaStar(voxel_size=1.0, grid_size=(size, size, voxel_grid.shape[2]), min_bound=(0.0, 0.0, 0.0))
                try:
                    planner.set_terrain_data(voxel_grid, None, min_bound=(0.0, 0.0, 0.0))
                except TypeError:
                    planner.set_terrain_data(voxel_grid, None)
                if size >= 250:
                    max_iters = 100000
                elif size >= 100:
                    max_iters = 50000
                else:
                    max_iters = 200000
                path = planner.plan_path(start, goal, max_iters=max_iters)
                success = path is not None
                nodes = planner.last_search_stats.get('nodes_explored', 0)
                plen = planner.last_search_stats.get('path_length', 0)

            elif planner_name == 'RRT*':
                try:
                    mod = importlib.import_module('path_planner_3d.rrt_star_planner_3d')
                    RRTClass = getattr(mod, 'RRTStarPlanner3D')
                    rrt = RRTClass(grid_size=(size, size, voxel_grid.shape[2]), voxel_size=1.0)
                    res = rrt.plan_path(start, goal, terrain_data=terrain_data, voxel_grid=voxel_grid, timeout=timeout)
                    if hasattr(res, 'to_dict'):
                        d = res.to_dict()
                        success = bool(d.get('success', False))
                        nodes = int(d.get('nodes_explored', 0))
                        plen = float(d.get('path_length', 0.0))
                    else:
                        success = getattr(res, 'success', bool(res))
                        nodes = getattr(res, 'nodes_explored', 0)
                        plen = getattr(res, 'path_length', 0)
                except Exception as e:
                    import traceback
                    return {'planner': planner_name, 'scenario_id': sid, 'success': False, 'computation_time': 0.0, 'error': str(e), 'error_detail': traceback.format_exc()}

            elif planner_name == 'D*Lite':
                try:
                    mod = importlib.import_module('path_planner_3d.dstar_lite_3d')
                    DStarClass = getattr(mod, 'DStarLite3D')
                    ds = DStarClass(voxel_size=1.0, grid_size=(size, size, voxel_grid.shape[2]))
                    ds.set_terrain_data(voxel_grid, terrain_data)
                    res = ds.plan_path(start, goal)
                    success = getattr(res, 'success', bool(res))
                    nodes = getattr(res, 'nodes_explored', 0)
                    plen = getattr(res, 'path_length', 0)
                except Exception as e:
                    import traceback
                    return {'planner': planner_name, 'scenario_id': sid, 'success': False, 'computation_time': 0.0, 'error': str(e), 'error_detail': traceback.format_exc()}

            elif planner_name == 'HPA*':
                try:
                    mod = importlib.import_module('path_planner_3d.hpa_star_planner')
                    HPAClass = getattr(mod, 'HPAStarPlanner')
                    import numpy as _np
                    start_np = _np.array([float(sx), float(sy), 0.0])
                    goal_np = _np.array([float(gx), float(gy), 0.0])
                    bounds = ((0.0, float(size)), (0.0, float(size)), (0.0, float(voxel_grid.shape[2])))
                    terrain_cost = None
                    if 'height_map' in scenario and scenario.get('height_map') is not None:
                        try:
                            terrain_cost = _np.array(scenario['height_map'])
                        except Exception:
                            terrain_cost = None
                    if terrain_cost is None:
                        terrain_cost = _np.zeros((size, size), dtype=float)
                    hpa = HPAClass(start=start_np, goal=goal_np, bounds=bounds, terrain_cost_map=terrain_cost, resolution=1.0)
                    path = hpa.plan()
                    success = path is not None
                    nodes = len(path) if path is not None else 0
                    plen = 0.0
                    if path is not None and len(path) > 1:
                        for i in range(len(path)-1):
                            plen += float(np.linalg.norm(np.array(path[i+1]) - np.array(path[i])))
                except Exception as e:
                    import traceback
                    return {'planner': planner_name, 'scenario_id': sid, 'success': False, 'computation_time': 0.0, 'error': str(e), 'error_detail': traceback.format_exc()}

            elif planner_name == 'SAFETY':
                try:
                    mod = importlib.import_module('path_planner_3d.safety_first_planner')
                    SafetyClass = getattr(mod, 'SafetyFirstPlanner')
                    import numpy as _np
                    start_np = _np.array([float(sx), float(sy), 0.0])
                    goal_np = _np.array([float(gx), float(gy), 0.0])
                    bounds = ((0.0, float(size)), (0.0, float(size)), (0.0, float(voxel_grid.shape[2])))
                    terrain_cost = None
                    if 'height_map' in scenario and scenario.get('height_map') is not None:
                        try:
                            terrain_cost = _np.array(scenario['height_map'])
                        except Exception:
                            terrain_cost = None
                    if terrain_cost is None:
                        terrain_cost = _np.zeros((size, size), dtype=float)
                    sp = SafetyClass(start=start_np, goal=goal_np, bounds=bounds, terrain_cost_map=terrain_cost, resolution=1.0)
                    path = sp.plan()
                    success = path is not None
                    nodes = len(path) if path is not None else 0
                    plen = 0.0
                    if path is not None and len(path) > 1:
                        for i in range(len(path)-1):
                            plen += float(np.linalg.norm(np.array(path[i+1]) - np.array(path[i])))
                except Exception as e:
                    import traceback
                    return {'planner': planner_name, 'scenario_id': sid, 'success': False, 'computation_time': 0.0, 'error': str(e), 'error_detail': traceback.format_exc()}

            else:
                return {'planner': planner_name, 'scenario_id': sid, 'success': False, 'computation_time': 0.0, 'error': 'Not implemented'}

        elapsed = time.time() - start_time
        out = {
            'planner': planner_name,
            'scenario_id': sid,
            'environment_type': scenario.get('env'),
            'map_size': size,
            'success': bool(success),
            'computation_time': float(elapsed),
            'path_length_meters': float(plen),
            'nodes_explored': int(nodes)
        }
        return out

    except Exception as e:
        import traceback
        elapsed = time.time() - start_time
        return {'planner': planner_name, 'scenario_id': sid, 'success': False, 'computation_time': float(elapsed), 'error': str(e), 'error_detail': traceback.format_exc()}


def main():
    with open('dataset3_scenarios.json', 'r') as f:
        all_scenarios = json.load(f)

    planners = ['TA*', 'Theta*', 'RRT*', 'D*Lite', 'HPA*', 'SAFETY', 'FieldD*Hybrid', 'MPAA*']
    tasks = [(p, s, 60) for p in planners for s in all_scenarios]

    outdir = Path('benchmark_results')
    outdir.mkdir(exist_ok=True)
    results = []
    save_path = outdir / 'dataset3_8planners_results.json'

    pool_procs = max(1, mp.cpu_count())
    start_time = time.time()
    with mp.Pool(processes=pool_procs) as pool:
        for i, r in enumerate(pool.imap_unordered(run_planner_on_scenario, tasks)):
            results.append(r)
            if (i+1) % 50 == 0:
                with open(save_path, 'w') as f:
                    json.dump(results, f, indent=2)
                elapsed = time.time() - start_time
                progress = (i+1) / len(tasks)
                eta = (elapsed / progress - elapsed) if progress>0 else 0
                print(f'Completed {i+1}/{len(tasks)} tasks | Elapsed: {elapsed:.1f}s | ETA: {eta:.1f}s')

    with open(save_path, 'w') as f:
        json.dump(results, f, indent=2)

    # summary per planner
    from collections import defaultdict
    stats = defaultdict(list)
    for r in results:
        stats[r.get('planner')].append(r)

    summary = {}
    for planner, entries in stats.items():
        total = len(entries)
        succ = sum(1 for e in entries if e.get('success'))
        avg_time = sum(e.get('computation_time',0) for e in entries) / total if total else None
        avg_time_success = (sum(e.get('computation_time',0) for e in entries if e.get('success')) / succ) if succ else None
        avg_path = (sum(e.get('path_length_meters',0) for e in entries if e.get('success')) / succ) if succ else None
        summary[planner] = {'total': total, 'success': succ, 'success_rate': succ/total if total else 0.0, 'avg_time_s': avg_time, 'avg_time_success_s': avg_time_success, 'avg_path_m': avg_path}

    with open(outdir / 'dataset3_8planners_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)

    print('Benchmark finished. Results saved to', save_path)


if __name__ == '__main__':
    main()
