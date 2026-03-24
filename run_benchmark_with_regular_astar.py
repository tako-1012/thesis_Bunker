#!/usr/bin/env python3
"""
Dataset3 Benchmark with Regular A* (9 planners total)

Extends run_benchmark_8planners.py to include Regular A*

Planners:
  1. A* (Regular A* - no terrain consideration)
  2. D*Lite
  3. RRT*
  4. HPA*
  5. SAFETY
  6. FieldD*Hybrid
  7. TA* (proposed method)
  8. Theta*
  9. MPAA*

Saves:
  - benchmark_results/dataset3_9planners_results.json
  - benchmark_results/dataset3_9planners_summary.json
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
    """Build 3D voxel grid from scenario obstacle map"""
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
    """Run a single planner on a single scenario"""
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

        # ===== Regular A* (NEW) =====
        if planner_name == 'A*':
            # Use TerrainAwareAStar with terrain_weight=0 to emulate plain A*
            try:
                from path_planner_3d.terrain_aware_astar import TerrainAwareAStar
            except ImportError:
                from terrain_aware_astar import TerrainAwareAStar

            planner = TerrainAwareAStar(voxel_size=1.0, grid_size=(size, size, z_layers))
            planner.set_terrain_data(voxel_grid, None, min_bound=(0.0, 0.0, 0.0))

            if hasattr(planner, 'terrain_weight'):
                planner.terrain_weight = 0.0

            result = planner.plan_path(start, goal, timeout=timeout)
            stats = getattr(planner, 'last_search_stats', {})
            success = bool(getattr(result, 'success', False))
            nodes = int(getattr(result, 'nodes_explored', stats.get('nodes_explored', 0)))
            plen = float(getattr(result, 'path_length', stats.get('path_length', 0.0)))

        # ===== FieldD*Hybrid =====
        elif planner_name == 'FieldD*Hybrid':
            from field_d_star_hybrid import FieldDStarHybrid
            planner = FieldDStarHybrid(voxel_size=1.0, grid_size=(size, size, z_layers))
            planner.set_terrain_data(voxel_grid, terrain_data, min_bound=(0.0, 0.0, 0.0))
            res = planner.plan_path(start, goal, timeout=timeout)
            success = bool(getattr(res, 'success', False))
            nodes = int(getattr(res, 'nodes_explored', planner.last_search_stats.get('nodes_explored', 0)))
            plen = float(getattr(res, 'path_length', planner.last_search_stats.get('path_length', 0)))

        # ===== MPAA* =====
        elif planner_name == 'MPAA*':
            from mpaa_star import MPAAStar
            planner = MPAAStar(voxel_size=1.0, grid_size=(size, size, z_layers))
            planner.set_terrain_data(voxel_grid, terrain_data, min_bound=(0.0, 0.0, 0.0))
            res = planner.plan_path(start, goal, timeout=timeout)
            success = bool(getattr(res, 'success', False))
            nodes = int(getattr(res, 'nodes_explored', 0))
            plen = float(getattr(res, 'path_length', 0))

        # ===== TA* =====
        elif planner_name == 'TA*':
            try:
                from path_planner_3d.terrain_aware_astar import TerrainAwareAStar
            except ImportError:
                from terrain_aware_astar import TerrainAwareAStar

            planner = TerrainAwareAStar(voxel_size=1.0, grid_size=(size, size, voxel_grid.shape[2]))
            planner.set_terrain_data(voxel_grid, terrain_data)

            # Use terrain-aware cost as described in the thesis
            if hasattr(planner, 'terrain_weight'):
                planner.terrain_weight = 1.0

            result = planner.plan_path(start, goal, timeout=timeout)
            stats = getattr(planner, 'last_search_stats', {})
            success = bool(getattr(result, 'success', False))
            nodes = int(getattr(result, 'nodes_explored', stats.get('nodes_explored', 0)))
            plen = float(getattr(result, 'path_length', stats.get('path_length', 0.0)))

        # ===== Theta* =====
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

        # ===== RRT* =====
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

        # ===== D*Lite =====
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

        # ===== HPA* =====
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

        # ===== SAFETY =====
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
    # Load scenarios
    with open('dataset3_scenarios.json', 'r') as f:
        all_scenarios = json.load(f)

    # 9 planners including Regular A* (reordered for reliability)
    planners = ['A*', 'D*Lite', 'RRT*', 'HPA*', 'SAFETY', 'FieldD*Hybrid', 'TA*', 'MPAA*', 'Theta*']
    
    tasks = [(p, s, 120) for p in planners for s in all_scenarios]  # Increased timeout to 120s

    outdir = Path('benchmark_results')
    outdir.mkdir(exist_ok=True)
    results = []
    save_path = outdir / 'dataset3_9planners_results.json'

    pool_procs = min(8, mp.cpu_count())  # Limit to 8 cores to avoid resource issues
    start_time = time.time()
    
    print(f"Starting benchmark with {len(planners)} planners × {len(all_scenarios)} scenarios = {len(tasks)} tasks")
    print(f"Using {pool_procs} CPU cores")
    print(f"Timeout per task: 120 seconds")
    print()
    
    try:
        with mp.Pool(processes=pool_procs) as pool:
            for i, r in enumerate(pool.imap_unordered(run_planner_on_scenario, tasks, chunksize=1)):
                results.append(r)
                if (i+1) % 50 == 0 or (i+1) % 10 == 0:
                    with open(save_path, 'w') as f:
                        json.dump(results, f, indent=2)
                    elapsed = time.time() - start_time
                    progress = (i+1) / len(tasks)
                    eta = (elapsed / progress - elapsed) if progress>0 else 0
                    print(f'Completed {i+1}/{len(tasks)} tasks ({progress*100:.1f}%) | Elapsed: {elapsed:.1f}s | ETA: {eta:.1f}s')
                    
                    # Print recent planner
                    if r:
                        status = '✓' if r.get('success') else '✗'
                        print(f'  Latest: {r.get("planner"):20s} Scenario {r.get("scenario_id"):3s} {status} ({r.get("computation_time", 0):.2f}s)')
    except KeyboardInterrupt:
        print('\n\nInterrupted by user. Saving partial results...')
    except Exception as e:
        print(f'\n\nError during benchmark: {e}')
        import traceback
        traceback.print_exc()

    # Final save
    with open(save_path, 'w') as f:
        json.dump(results, f, indent=2)

    # Generate summary per planner
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
        
        # Calculate median, min, max for successful paths
        success_paths = [e.get('path_length_meters', 0) for e in entries if e.get('success') and e.get('path_length_meters')]
        if success_paths:
            success_paths_sorted = sorted(success_paths)
            median_path = success_paths_sorted[len(success_paths_sorted)//2]
            min_path = min(success_paths)
            max_path = max(success_paths)
        else:
            median_path = None
            min_path = None
            max_path = None
        
        summary[planner] = {
            'total': total,
            'success': succ,
            'success_rate': succ/total if total else 0.0,
            'avg_time_all_s': avg_time,
            'avg_time_success_s': avg_time_success,
            'avg_path_success_m': avg_path,
            'median_path_m': median_path,
            'min_path_m': min_path,
            'max_path_m': max_path
        }

    summary_output = {'summary': summary}
    with open(outdir / 'dataset3_9planners_summary.json', 'w') as f:
        json.dump(summary_output, f, indent=2)

    print()
    print('='*80)
    print('Benchmark finished!')
    print(f'Results: {save_path}')
    print(f'Summary: {outdir / "dataset3_9planners_summary.json"}')
    print('='*80)
    print()
    print('Summary:')
    for planner in planners:
        s = summary.get(planner, {})
        print(f"  {planner:20s} Success: {s.get('success',0):2d}/{s.get('total',0):2d} ({s.get('success_rate',0)*100:5.1f}%) | "
              f"Time: {s.get('avg_time_success_s',0):6.3f}s | Path: {s.get('avg_path_success_m',0):7.2f}m")


if __name__ == '__main__':
    main()
