"""Dry-run for Dataset2: run 7 planners on 3 representative scenarios."""
import sys
from pathlib import Path
import json
import time
import multiprocessing as mp

import numpy as np
import importlib

# ensure planner modules importable
PACKAGE_ROOT = '/home/hayashi/thesis_work/ros2/ros2_ws/src/path_planner_3d'
MODULE_DIR = '/home/hayashi/thesis_work/ros2/ros2_ws/src/path_planner_3d/path_planner_3d'
if PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, PACKAGE_ROOT)
if MODULE_DIR not in sys.path:
    sys.path.insert(0, MODULE_DIR)


def build_voxel_grid(scenario, z_layers=8):
    obs = np.array(scenario['obstacle_map'], dtype=np.uint8)
    h, w = obs.shape
    vg = np.zeros((w, h, z_layers), dtype=np.float32)
    for z in range(z_layers):
        vg[:, :, z] = obs.T  # match planner indexing expectations
    return vg


def run_planner_on_scenario(args):
    planner_name, scenario, timeout = args
    sid = scenario.get('id', 'unknown')
    print(f"[{planner_name}] start {sid}")
    start_time = time.time()
    try:
        size = scenario['map_size']
        voxel_grid = build_voxel_grid(scenario, z_layers=max(8, size//16))
        terrain_data = {'height_map': np.array(scenario['height_map'])}

        sx, sy = scenario['start']
        gx, gy = scenario['goal']
        start = (float(sx), float(sy), 0.0)
        goal = (float(gx), float(gy), 0.0)

        if planner_name == 'TA*':
            from terrain_aware_astar_advanced import TerrainAwareAStar
            planner = TerrainAwareAStar(voxel_size=1.0, grid_size=(size, size, voxel_grid.shape[2]), min_bound=(0.0, 0.0, 0.0))
            planner.set_terrain_data(voxel_grid, terrain_data)
            path = planner.plan_path(start, goal)
            success = path is not None
            nodes = planner.last_search_stats.get('nodes_explored', 0)
            plen = planner.last_search_stats.get('path_length', 0)

        elif planner_name == 'Theta*':
            from theta_star import ThetaStar
            planner = ThetaStar(voxel_size=1.0, grid_size=(size, size, voxel_grid.shape[2]), min_bound=(0.0,0.0,0.0))
            planner.set_terrain_data(voxel_grid, None, min_bound=(0.0,0.0,0.0))
            path = planner.plan_path(start, goal)
            success = path is not None
            nodes = planner.last_search_stats.get('nodes_explored', 0)
            plen = planner.last_search_stats.get('path_length', 0)

        elif planner_name == 'AHA*':
            # import as package to satisfy relative imports inside module
            mod = importlib.import_module('path_planner_3d.adaptive_hybrid_astar_3d')
            AdaptiveHybridAStar3D = getattr(mod, 'AdaptiveHybridAStar3D')
            # Explicitly specify min_bound to match scenario world-origin coordinates
            planner = AdaptiveHybridAStar3D(point_cloud=None, resolution=1.0, grid_size=(size, size, voxel_grid.shape[2]), min_bound=(0.0, 0.0, 0.0))
            planner.set_terrain_data(voxel_grid, terrain_data)
            result = planner.plan_path(start, goal)
            # support new dict return and legacy list return
            if isinstance(result, dict):
                success = bool(result.get('success', False))
                nodes = int(result.get('nodes_explored', planner.last_search_stats.get('nodes_explored', 0)))
                plen = float(result.get('path_length_meters', planner.last_search_stats.get('path_length', 0)))
            else:
                success = result is not None
                nodes = planner.last_search_stats.get('nodes_explored', 0)
                plen = planner.last_search_stats.get('path_length', 0)

        elif planner_name == 'RRT*':
            try:
                mod = importlib.import_module('path_planner_3d.rrt_star_planner_3d')
                RRTClass = getattr(mod, 'RRTStarPlanner3D')
                rrt = RRTClass(grid_size=(size, size, voxel_grid.shape[2]), voxel_size=1.0)
                # pass terrain as needed
                res = rrt.plan_path(start, goal, terrain_data=terrain_data, timeout=timeout)
                # PlanningResult or similar
                if hasattr(res, 'to_dict'):
                    d = res.to_dict()
                    success = bool(d.get('success', False))
                    nodes = int(d.get('nodes_explored', 0))
                    plen = float(d.get('path_length', 0.0))
                    elapsed = float(d.get('computation_time', 0.0))
                else:
                    # fallback: treat truthiness
                    success = getattr(res, 'success', bool(res))
                    nodes = getattr(res, 'nodes_explored', 0)
                    plen = getattr(res, 'path_length', 0)
                # ensure variables set
            except Exception as e:
                print(f"[RRT*] error {sid}: {e}")
                return {
                    'planner': planner_name,
                    'scenario_id': sid,
                    'success': False,
                    'computation_time': 0.0,
                    'error': str(e)
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
                print(f"[D*Lite] error {sid}: {e}")
                return {
                    'planner': planner_name,
                    'scenario_id': sid,
                    'success': False,
                    'computation_time': 0.0,
                    'error': str(e)
                }

        elif planner_name == 'HPA*':
            try:
                mod = importlib.import_module('path_planner_3d.hpa_star_planner')
                HPAClass = getattr(mod, 'HPAStarPlanner')
                import numpy as _np
                start_np = _np.array([float(sx), float(sy), 0.0])
                goal_np = _np.array([float(gx), float(gy), 0.0])
                # bounds: ((x_min,x_max),(y_min,y_max),(z_min,z_max))
                bounds = ((0.0, float(size)), (0.0, float(size)), (0.0, float(voxel_grid.shape[2])))
                terrain_cost = None
                if 'height_map' in scenario:
                    try:
                        terrain_cost = _np.array(scenario['height_map'])
                    except Exception:
                        terrain_cost = None
                hpa = HPAClass(start=start_np, goal=goal_np, bounds=bounds, terrain_cost_map=terrain_cost, resolution=1.0)
                path = hpa.plan()
                success = path is not None
                nodes = len(path) if path is not None else 0
                plen = 0.0
                if path is not None and len(path) > 1:
                    for i in range(len(path)-1):
                        plen += float(_np.linalg.norm(_np.array(path[i+1]) - _np.array(path[i])))
            except Exception as e:
                print(f"[HPA*] error {sid}: {e}")
                return {
                    'planner': planner_name,
                    'scenario_id': sid,
                    'success': False,
                    'computation_time': 0.0,
                    'error': str(e)
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
                if 'height_map' in scenario:
                    try:
                        terrain_cost = _np.array(scenario['height_map'])
                    except Exception:
                        terrain_cost = None
                sp = SafetyClass(start=start_np, goal=goal_np, bounds=bounds, terrain_cost_map=terrain_cost, resolution=1.0)
                path = sp.plan()
                success = path is not None
                nodes = len(path) if path is not None else 0
                plen = 0.0
                if path is not None and len(path) > 1:
                    for i in range(len(path)-1):
                        plen += float(_np.linalg.norm(_np.array(path[i+1]) - _np.array(path[i])))
            except Exception as e:
                print(f"[SAFETY] error {sid}: {e}")
                return {
                    'planner': planner_name,
                    'scenario_id': sid,
                    'success': False,
                    'computation_time': 0.0,
                    'error': str(e)
                }

        else:
            # Not implemented planners: return graceful result
            return {
                'planner': planner_name,
                'scenario_id': sid,
                'success': False,
                'computation_time': 0.0,
                'error': 'Not implemented in dry run'
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
        print(f"[{planner_name}] done {sid}: {elapsed:.3f}s success={out['success']}")
        return out

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[{planner_name}] error {sid}: {e}")
        return {
            'planner': planner_name,
            'scenario_id': sid,
            'success': False,
            'computation_time': float(elapsed),
            'error': str(e)
        }


def main():
    print('=== Dry run start ===')
    with open('dataset2_scenarios.json') as f:
        all_scenarios = json.load(f)

    test_scenarios = [all_scenarios[0], all_scenarios[48], all_scenarios[96]]
    planners = ['TA*', 'Theta*', 'AHA*', 'RRT*', 'D*Lite', 'HPA*', 'SAFETY']
    tasks = []
    for p in planners:
        for s in test_scenarios:
            tasks.append((p, s, 180))

    print(f"Dry-run tasks: {len(tasks)}")
    results = []
    with mp.Pool(processes=min(4, mp.cpu_count())) as pool:
        for r in pool.imap_unordered(run_planner_on_scenario, tasks):
            results.append(r)

    outdir = Path('benchmark_results')
    outdir.mkdir(exist_ok=True)
    with open(outdir / 'dry_run_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    success_count = sum(1 for r in results if r.get('success'))
    error_count = sum(1 for r in results if 'error' in r)
    print('\n=== Dry run complete ===')
    print(f'Total tasks: {len(results)}')
    print(f'Success: {success_count}/{len(results)}')
    print(f'Errors: {error_count}/{len(results)}')

    for p in planners:
        pr = [r for r in results if r.get('planner') == p]
        if not pr:
            continue
        succ = sum(1 for r in pr if r.get('success'))
        avg_time = sum(r.get('computation_time', 0) for r in pr) / len(pr)
        print(f"{p}: {succ}/{len(pr)} success, avg {avg_time:.3f}s")


if __name__ == '__main__':
    main()
