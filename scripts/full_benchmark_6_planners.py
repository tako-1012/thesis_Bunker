"""Full benchmark: run 6 planners (AHA* excluded) over dataset2 scenarios in parallel.

Saves intermediate results periodically to `benchmark_results/dataset2_6planners_results.json`.
"""
import sys
from pathlib import Path
import json
import time
import multiprocessing as mp

import numpy as np
import importlib

# ensure workspace planner modules importable (same as dry_run_test)
PACKAGE_ROOT = '/home/hayashi/thesis_work/ros2/ros2_ws/src/path_planner_3d'
MODULE_DIR = '/home/hayashi/thesis_work/ros2/ros2_ws/src/path_planner_3d/path_planner_3d'
if PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, PACKAGE_ROOT)
if MODULE_DIR not in sys.path:
    sys.path.insert(0, MODULE_DIR)


def build_voxel_grid(scenario, z_layers=8):
    obs = np.array(scenario.get('obstacle_map', np.zeros((32, 32))), dtype=np.uint8)
    h, w = obs.shape
    # handle map_size scalar or [w,h]
    map_size_raw = scenario.get('map_size', max(h, w))
    if isinstance(map_size_raw, (list, tuple)):
        size = int(max(map_size_raw))
    else:
        size = int(map_size_raw)
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
        # Dataset2/3 compatibility: accept scalar or [w,h]
        map_size_raw = scenario.get('map_size', 64)
        if isinstance(map_size_raw, (list, tuple)):
            size = int(max(map_size_raw))
        else:
            size = int(map_size_raw)
        z_layers = max(8, size // 16)
        voxel_grid = build_voxel_grid(scenario, z_layers=z_layers)
        terrain_data = {'height_map': np.array(scenario.get('height_map', np.zeros((size, size))))}

        sx, sy = scenario.get('start', (0, 0))
        gx, gy = scenario.get('goal', (0, 0))
        start = (float(sx), float(sy), 0.0)
        goal = (float(gx), float(gy), 0.0)

        # Planner dispatch (TA*, Theta*, RRT*, D*Lite, HPA*, SAFETY)
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
            # adjust max iterations by map size
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
                # pass voxel_grid so planner can perform occupancy checks
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
                error_detail = {
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'traceback': traceback.format_exc(),
                    'last_search_stats': getattr(locals().get('rrt', None), 'last_search_stats', None)
                }
                return {
                    'planner': planner_name,
                    'scenario_id': sid,
                    'success': False,
                    'computation_time': 0.0,
                    'error': str(e),
                    'error_detail': error_detail
                }

        elif planner_name == 'D*Lite':
            try:
                mod = importlib.import_module('path_planner_3d.dstar_lite_3d')
                DStarClass = getattr(mod, 'DStarLite3D')
                ds = DStarClass(voxel_size=1.0, grid_size=(size, size, voxel_grid.shape[2]))
                ds.set_terrain_data(voxel_grid, terrain_data)
                res = ds.plan_path(start, goal)
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
                error_detail = {
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'traceback': traceback.format_exc(),
                    'last_search_stats': getattr(locals().get('ds', None), 'last_search_stats', None)
                }
                return {
                    'planner': planner_name,
                    'scenario_id': sid,
                    'success': False,
                    'computation_time': 0.0,
                    'error': str(e),
                    'error_detail': error_detail
                }

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
                # if missing, provide a zero-cost map sized to 'size'
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
                error_detail = {
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'traceback': traceback.format_exc(),
                    'last_search_stats': getattr(locals().get('hpa', None), 'last_search_stats', None)
                }
                return {
                    'planner': planner_name,
                    'scenario_id': sid,
                    'success': False,
                    'computation_time': 0.0,
                    'error': str(e),
                    'error_detail': error_detail
                }

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
                error_detail = {
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'traceback': traceback.format_exc(),
                    'last_search_stats': getattr(locals().get('sp', None), 'last_search_stats', None)
                }
                return {
                    'planner': planner_name,
                    'scenario_id': sid,
                    'success': False,
                    'computation_time': 0.0,
                    'error': str(e),
                    'error_detail': error_detail
                }

        elif planner_name == 'AHA*':
            try:
                mod = importlib.import_module('path_planner_3d.adaptive_hybrid_astar_3d')
                AHAClass = getattr(mod, 'AdaptiveHybridAStar3D')
                planner = AHAClass(point_cloud=None, resolution=1.0, grid_size=(size, size, voxel_grid.shape[2]), min_bound=(0.0,0.0,0.0))
                planner.set_terrain_data(voxel_grid, terrain_data)
                result = planner.plan_path(start, goal)
                if isinstance(result, dict):
                    success = bool(result.get('success', False))
                    nodes = int(result.get('nodes_explored', planner.last_search_stats.get('nodes_explored', 0)))
                    plen = float(result.get('path_length_meters', planner.last_search_stats.get('path_length', 0)))
                else:
                    success = result is not None
                    nodes = planner.last_search_stats.get('nodes_explored', 0)
                    plen = planner.last_search_stats.get('path_length', 0)
            except Exception as e:
                import traceback
                error_detail = {
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'traceback': traceback.format_exc(),
                    'last_search_stats': getattr(locals().get('planner', None), 'last_search_stats', None)
                }
                return {
                    'planner': planner_name,
                    'scenario_id': sid,
                    'success': False,
                    'computation_time': 0.0,
                    'error': str(e),
                    'error_detail': error_detail
                }
        else:
            return {
                'planner': planner_name,
                'scenario_id': sid,
                'success': False,
                'computation_time': 0.0,
                'error': 'Not implemented'
            }

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
        error_detail = {
            'error_type': type(e).__name__,
            'error_message': str(e),
            'traceback': traceback.format_exc(),
            'last_search_stats': None
        }
        return {
            'planner': planner_name,
            'scenario_id': sid,
            'success': False,
            'computation_time': float(elapsed),
            'error': str(e),
            'error_detail': error_detail
        }


def main():
    print('=== Full benchmark (7 planners) start ===')
    with open('dataset3_scenarios.json', 'r') as f:
        all_scenarios = json.load(f)

    # Run without AHA* (excluded by request)
    planners = ['TA*', 'Theta*', 'RRT*', 'D*Lite', 'HPA*', 'SAFETY']
    # timeout per task: 60 seconds as requested for this run
    tasks = [(p, s, 60) for p in planners for s in all_scenarios]

    print(f"Total scenarios: {len(all_scenarios)}")
    print(f"Total tasks: {len(tasks)} (7 planners × {len(all_scenarios)})")
    print(f"CPU count: {mp.cpu_count()}")

    results = []
    outdir = Path('benchmark_results')
    outdir.mkdir(exist_ok=True)
    save_path = outdir / 'dataset3_benchmark_intermediate.json'

    start_time = time.time()
    chunk_save = 50
    processed = 0

    pool_procs = max(1, mp.cpu_count())
    with mp.Pool(processes=pool_procs) as pool:
        for i, r in enumerate(pool.imap_unordered(run_planner_on_scenario, tasks)):
            results.append(r)
            processed += 1

                    # periodic save
            if processed % chunk_save == 0:
                with open(save_path, 'w') as f:
                    json.dump(results, f, indent=2)

            # progress print every 50 tasks as requested
            if processed % 50 == 0:
                elapsed = time.time() - start_time
                progress = processed / len(tasks)
                eta = (elapsed / progress - elapsed) if progress > 0 else 0
                print(f"Completed {processed}/{len(tasks)} tasks ({progress*100:.1f}%) | Elapsed: {elapsed/3600:.2f}h | ETA: {eta/3600:.2f}h")

    # final save (transform to required output schema)
    out_path = outdir / 'dataset3_benchmark_results.json'
    # normalize keys to user-requested schema
    normalized = []
    for r in results:
        rec = {
            'scenario_id': r.get('scenario_id') or r.get('scenario_name') or r.get('scenario') or r.get('scenario_id'),
            'planner': r.get('planner') or r.get('planner_name') or r.get('planner'),
            'success': bool(r.get('success', False)),
            'time': r.get('computation_time') or r.get('computation_time', r.get('time')) or None,
            'path_length': r.get('path_length_meters') or r.get('path_length') or r.get('path_length_meters') or None,
            'error_message': r.get('error') or r.get('error_message') or None
        }
        normalized.append(rec)
    with open(out_path, 'w') as f:
        json.dump(normalized, f, indent=2)

    # --- Additional postprocessing: summary per type/planner and fastest-by-scenario ---
    # Use raw `results` which contains scenario metadata (type_group, type_sub)
    summary = {}
    from collections import defaultdict
    stats = defaultdict(list)
    for r in results:
        scen = r.get('scenario_id')
        # attempt to retrieve type_group/type_sub from original scenario entry
        # some runners preserved environment_type; fall back to 'unknown'
        tg = None
        try:
            tg = r.get('environment_type') or r.get('type_group')
        except Exception:
            tg = None
        # group key as string
        type_key = str(tg) if tg is not None else 'unknown'
        planner = r.get('planner')
        stats[(type_key, planner)].append(r)

    # build summary structure
    summary_out = {}
    for (type_key, planner), entries in stats.items():
        total = len(entries)
        succ = sum(1 for e in entries if e.get('success'))
        times = [e.get('computation_time', 0.0) for e in entries if e.get('success')]
        avg_time_success = (sum(times) / len(times)) if times else None
        avg_time_all = (sum(e.get('computation_time', 0.0) for e in entries) / total) if total else None
        avg_path = (sum(e.get('path_length_meters', 0.0) for e in entries if e.get('success')) / len(times)) if times else None
        summary_out.setdefault(type_key, {})[planner] = {
            'total_tasks': total,
            'success_count': succ,
            'success_rate': succ/total if total else 0.0,
            'avg_time_success_s': avg_time_success,
            'avg_time_all_s': avg_time_all,
            'avg_path_length_m': avg_path
        }

    # fastest-by-scenario
    fastest = {}
    # build map scenario_id -> list of entries
    by_scenario = {}
    for r in results:
        sid = r.get('scenario_id')
        by_scenario.setdefault(sid, []).append(r)
    for sid, entries in by_scenario.items():
        succs = [e for e in entries if e.get('success')]
        if not succs:
            fastest[sid] = None
            continue
        best = min(succs, key=lambda x: x.get('computation_time', float('inf')))
        fastest[sid] = {
            'planner': best.get('planner'),
            'time_s': best.get('computation_time'),
            'path_length_m': best.get('path_length_meters')
        }

    # save summary files
    with open(outdir / 'dataset3_benchmark_summary.json', 'w') as f:
        json.dump(summary_out, f, indent=2)
    with open(outdir / 'dataset3_fastest_by_scenario.json', 'w') as f:
        json.dump(fastest, f, indent=2)

    total_time = time.time() - start_time
    print('\n' + '='*60)
    print('BENCHMARK COMPLETE')
    print('='*60)
    print(f'Total time: {total_time/3600:.2f} hours')
    print(f'Total tasks: {len(results)}')
    print(f'Output: {out_path}')

    success_count = sum(1 for r in results if r.get('success', False))
    print(f'\nOverall success: {success_count}/{len(results)} ({success_count/len(results)*100:.1f}%)')

    for planner in planners:
        pr = [r for r in results if r.get('planner') == planner]
        if not pr:
            continue
        succ = sum(1 for r in pr if r.get('success'))
        avg_time = sum(r.get('computation_time', 0) for r in pr) / len(pr)
        print(f"\n{planner}:\n  Success: {succ}/{len(pr)}\n  Avg time: {avg_time:.3f}s")


if __name__ == '__main__':
    main()
