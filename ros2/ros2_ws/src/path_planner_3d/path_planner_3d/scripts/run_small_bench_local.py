#!/usr/bin/env python3
"""Run small benchmark suite (SMALL=2, MEDIUM=2, LARGE=1) comparing AHA* and TA*.

Produces a JSON results file under /tmp/aha_small_bench_results.json
"""
import os
import sys
import time
import json
import numpy as np

# ensure package imports resolve
ROOT = os.path.dirname(os.path.dirname(__file__))
SRC_ROOT = os.path.abspath(os.path.join(ROOT, '..'))
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from path_planner_3d.config import PlannerConfig
from path_planner_3d.anytime_hierarchical_astar import AnytimeHierarchicalAStar
from path_planner_3d.terrain_aware_astar_advanced import TerrainAwareAStar
from path_planner_3d.cost_function import CostFunction


def make_cost_map(seed, grid_size):
    np.random.seed(seed)
    base = 0.1 if grid_size <= 100 else (0.12 if grid_size <= 500 else 0.35)
    noise = np.random.normal(0, 0.02, (grid_size, grid_size))
    cmap = np.clip(np.ones((grid_size, grid_size), dtype=np.float32) * base + noise, 0.0, 1.0)
    return cmap


def sample_start_goal(world_size, min_distance, rng):
    while True:
        s = np.array([rng.uniform(0.1 * world_size, 0.9 * world_size), rng.uniform(0.1 * world_size, 0.9 * world_size), 0.0])
        g = np.array([rng.uniform(0.1 * world_size, 0.9 * world_size), rng.uniform(0.1 * world_size, 0.9 * world_size), 0.0])
        if np.linalg.norm(s - g) >= min_distance:
            return s, g


def generate_scenarios():
    specs = [
        ('SMALL', 100, 10.0, 3.0, 2),
        ('MEDIUM', 500, 50.0, 15.0, 2),
        ('LARGE', 1000, 100.0, 30.0, 1),
    ]
    scenarios = []
    rng = np.random.default_rng(42)
    for name, grid_size, world_size, min_dist, count in specs:
        for i in range(count):
            seed = (hash(f"{name}_{i}") % 10000)
            cmap = make_cost_map(seed, grid_size)
            s, g = sample_start_goal(world_size, min_dist, rng)
            bounds = ((0.0, world_size), (0.0, world_size), (0.0, 2.0))
            scenarios.append({
                'name': f'{name}_{i+1}',
                'start': s.tolist(),
                'goal': g.tolist(),
                'bounds': bounds,
                'terrain_cost_map': cmap,
                'map_size': name,
                'grid_size': grid_size,
                'world_size': world_size,
            })
    return scenarios


def run():
    scenarios = generate_scenarios()
    results = []

    for scen in scenarios:
        print(f"Running scenario {scen['name']} ({scen['map_size']})")
        bounds = scen['bounds']
        cfg = PlannerConfig(map_bounds=([bounds[0][0], bounds[1][0], bounds[2][0]],[bounds[0][1], bounds[1][1], bounds[2][1]]), voxel_size=0.5)

        # CostFunction for terrain_cost_fn (adjusted per user request)
        weights = {'distance':1.0,'slope':1.0,'obstacle':0.7,'stability':1.0}
        safety = {'min_obstacle_distance':0.3}
        cost_fn = CostFunction(weights, safety)
        terrain_cost_fn = lambda f,t,d: float(cost_fn.calculate_total_cost(f,t,d if d is not None else {}))

        # AHA*
        aha = AnytimeHierarchicalAStar(cfg, coarse_factor=3, initial_epsilon=2.0, epsilon_decay=0.5, terrain_cost_fn=terrain_cost_fn)
        timeout = 20.0 if scen['map_size']=='SMALL' else (40.0 if scen['map_size']=='MEDIUM' else 60.0)
        t0 = time.time()
        res_aha = aha.plan_path(list(scen['start']), list(scen['goal']), terrain_data={'slopes':[0.0]}, timeout=timeout)
        t_aha = time.time() - t0

        # TA*
        z_dim = max(50, scen['grid_size'] // 10)
        ta = TerrainAwareAStar(voxel_size=0.5, grid_size=(scen['grid_size'], scen['grid_size'], z_dim), min_bound=(0.0, 0.0, 0.0), use_cost_calculator=False)
        voxel_grid = np.zeros((scen['grid_size'], scen['grid_size'], z_dim), dtype=np.uint8)
        ta.set_terrain_data(voxel_grid, {'slopes': np.array([0.0])})
        t0 = time.time()
        path_ta = ta.plan_path(tuple(scen['start']), tuple(scen['goal']))
        t_ta = time.time() - t0

        # Compute TA* additional metrics from returned world path (if available)
        def compute_path_metrics_world(path_world, ta_planner):
            import math
            from path_planner_3d.terrain_aware_astar_advanced import TERRAIN_STRATEGIES, TerrainType
            if not path_world or len(path_world) < 2:
                return None
            total_dist = 0.0
            for i in range(len(path_world) - 1):
                a = path_world[i]
                b = path_world[i+1]
                dx = b[0] - a[0]
                dy = b[1] - a[1]
                dz = b[2] - a[2]
                total_dist += math.sqrt(dx*dx + dy*dy + dz*dz)

            # total cost using TA* internal cost calculator per-segment
            total_cost = 0.0
            for i in range(len(path_world) - 1):
                f_world = path_world[i]
                t_world = path_world[i+1]
                f_idx = ta_planner._world_to_voxel(f_world)
                t_idx = ta_planner._world_to_voxel(t_world)
                terrain_type = ta_planner._get_terrain_type(t_idx)
                strategy = TERRAIN_STRATEGIES.get(terrain_type, TERRAIN_STRATEGIES[TerrainType.UNKNOWN])
                seg_cost = ta_planner._calculate_terrain_aware_cost(f_idx, t_idx, strategy)
                total_cost += seg_cost

            # smoothness: average turn angle
            angles = []
            def vec(u, v):
                return (v[0]-u[0], v[1]-u[1], v[2]-u[2])
            def norm(w):
                return math.sqrt(w[0]*w[0] + w[1]*w[1] + w[2]*w[2])
            for i in range(len(path_world) - 2):
                v1 = vec(path_world[i], path_world[i+1])
                v2 = vec(path_world[i+1], path_world[i+2])
                n1 = norm(v1)
                n2 = norm(v2)
                if n1 < 1e-9 or n2 < 1e-9:
                    continue
                dot = (v1[0]*v2[0] + v1[1]*v2[1] + v1[2]*v2[2]) / (n1 * n2)
                dot = max(-1.0, min(1.0, dot))
                angle = math.acos(dot) * 180.0 / math.pi
                angles.append(abs(angle))
            smoothness = float(sum(angles) / len(angles)) if angles else 0.0
            return {'length_meters': total_dist, 'total_cost': total_cost, 'smoothness': smoothness}

        # apply Shortcut -> B-Spline smoothing pipeline to TA* path
        try:
            from path_planner_3d.path_smoother import PathSmoother
            if path_ta is not None:
                smoother = PathSmoother()
                # Step 1: Shortcut (small number of iterations)
                smoothed_ta = smoother.shortcut(path_ta, ta, max_iter=5)
                if smoothed_ta is not None and len(smoothed_ta) <= len(path_ta):
                    path_ta = smoothed_ta
                # Step 2: Gentle B-spline smoothing
                bspline_ta = smoother.bspline(path_ta, ta, smoothing=0.2, num_points=100)
                if bspline_ta is not None and len(bspline_ta) >= 2:
                    path_ta = bspline_ta
        except Exception:
            # if smoother not available, continue
            pass

        result = {
            'scenario': scen['name'],
            'map_size': scen['map_size'],
            'aha': {
                'success': res_aha.success,
                'computation_time': res_aha.computation_time,
                'path_length': res_aha.path_length,
                'nodes_explored': res_aha.nodes_explored,
                'iterations': getattr(res_aha, 'iterations', None),
                'early_exit_reason': getattr(res_aha, 'early_exit_reason', None),
            },
            'ta': {
                'success': path_ta is not None,
                'computation_time': ta.last_search_stats.get('computation_time', t_ta),
                'path_length': ta.last_search_stats.get('path_length', 0),
                'path_length_meters': None,
                'path_total_cost': None,
                'path_smoothness': None,
                'nodes_explored': ta.last_search_stats.get('nodes_explored', 0),
            }
        }
        # if ta returned a world path, compute metrics directly
        if path_ta is not None:
            metrics_ta = compute_path_metrics_world(path_ta, ta)
            if metrics_ta is not None:
                result['ta']['path_length_meters'] = metrics_ta['length_meters']
                result['ta']['path_total_cost'] = metrics_ta['total_cost']
                result['ta']['path_smoothness'] = metrics_ta['smoothness']
        print('  AHA*: ', result['aha'])
        print('  TA*:  ', result['ta'])
        results.append(result)

    out = '/tmp/aha_small_bench_results.json'
    with open(out, 'w') as fh:
        json.dump(results, fh, indent=2)
    print('Saved results to', out)


if __name__ == '__main__':
    run()
