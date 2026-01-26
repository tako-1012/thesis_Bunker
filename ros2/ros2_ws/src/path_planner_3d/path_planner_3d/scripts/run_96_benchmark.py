#!/usr/bin/env python3
"""Run full 96-scenario benchmark comparing TA* (with Shortcut) and AHA*.

Produces:
 - benchmark_results/ta_star_smoothed_96_results.json
 - benchmark_results/aha_star_96_results.json
 - benchmark_results/seven_planners_detailed.json (contains these two)
 - benchmark_results/seven_planners_comparison.csv
 - benchmark_results/statistical_analysis.txt
"""
import os
import sys
import time
import json
import math
import statistics
import csv
import numpy as np

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


def generate_96_scenarios():
    specs = [
        ('SMALL', 100, 10.0, 3.0, 30),
        ('MEDIUM', 500, 50.0, 15.0, 48),
        ('LARGE', 1000, 100.0, 30.0, 18),
    ]
    scenarios = []
    rng = np.random.default_rng(12345)
    for name, grid_size, world_size, min_dist, count in specs:
        for i in range(count):
            seed = (hash(f"{name}_{i}") % 100000)
            cmap = make_cost_map(seed, grid_size)
            s, g = sample_start_goal(world_size, min_dist, rng)
            bounds = ((0.0, world_size), (0.0, world_size), (0.0, 2.0))
            scenarios.append({
                'id': f'{name}_{i+1}',
                'name': name,
                'start': s.tolist(),
                'goal': g.tolist(),
                'bounds': bounds,
                'terrain_cost_map': cmap,
                'map_size': name,
                'grid_size': grid_size,
                'world_size': world_size,
            })
    return scenarios


def compute_path_metrics_world(path_world, ta_planner):
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

    total_cost = 0.0
    try:
        from path_planner_3d.terrain_aware_astar_advanced import TERRAIN_STRATEGIES, TerrainType
        for i in range(len(path_world) - 1):
            f_world = path_world[i]
            t_world = path_world[i+1]
            f_idx = ta_planner._world_to_voxel(f_world)
            t_idx = ta_planner._world_to_voxel(t_world)
            terrain_type = ta_planner._get_terrain_type(t_idx)
            strategy = TERRAIN_STRATEGIES.get(terrain_type, TERRAIN_STRATEGIES[TerrainType.UNKNOWN])
            seg_cost = ta_planner._calculate_terrain_aware_cost(f_idx, t_idx, strategy)
            total_cost += seg_cost
    except Exception:
        total_cost = total_dist

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


def summarize(results):
    by_size = {'SMALL': [], 'MEDIUM': [], 'LARGE': []}
    for r in results:
        sz = r['map_size']
        if r['path_length_meters'] is not None:
            by_size[sz].append(r['path_length_meters'])
    summary = {}
    all_vals = []
    for sz, vals in by_size.items():
        if vals:
            summary[sz] = {'mean': statistics.mean(vals), 'std': statistics.pstdev(vals), 'min': min(vals), 'max': max(vals), 'median': statistics.median(vals), 'count': len(vals)}
            all_vals.extend(vals)
        else:
            summary[sz] = {'mean': None, 'std': None, 'min': None, 'max': None, 'median': None, 'count': 0}
    if all_vals:
        summary['ALL'] = {'mean': statistics.mean(all_vals), 'std': statistics.pstdev(all_vals), 'min': min(all_vals), 'max': max(all_vals), 'median': statistics.median(all_vals), 'count': len(all_vals)}
    else:
        summary['ALL'] = {'mean': None, 'std': None, 'min': None, 'max': None, 'median': None, 'count': 0}
    return summary


def welch_ttest(a, b):
    # return t, p(two-sided), cohen_d
    na = len(a); nb = len(b)
    ma = statistics.mean(a); mb = statistics.mean(b)
    sa2 = statistics.pvariance(a); sb2 = statistics.pvariance(b)
    se = math.sqrt(sa2/na + sb2/nb)
    if se == 0:
        return None, None, None
    t = (ma - mb) / se
    # degrees of freedom (Welch–Satterthwaite)
    df = (sa2/na + sb2/nb)**2 / ((sa2*sa2)/((na*na)*(na-1)) + (sb2*sb2)/((nb*nb)*(nb-1))) if na>1 and nb>1 else 1
    # p-value not computed reliably without scipy/mpmath
    p = None
    try:
        pooled_sd = math.sqrt(((na-1)*sa2 + (nb-1)*sb2) / (na+nb-2)) if na+nb-2>0 else None
        cohen_d = (ma-mb)/pooled_sd if pooled_sd and pooled_sd>0 else None
    except Exception:
        cohen_d = None
    return t, p, cohen_d


def main():
    out_dir = os.path.join(ROOT, 'benchmark_results')
    os.makedirs(out_dir, exist_ok=True)

    scenarios = generate_96_scenarios()

    # prepare cost function
    weights = {'distance':1.0,'slope':1.0,'obstacle':0.7,'stability':1.0}
    safety = {'min_obstacle_distance':0.3}
    cost_fn = CostFunction(weights, safety)
    terrain_cost_fn = lambda f,t,d: float(cost_fn.calculate_total_cost(f,t,d if d is not None else {}))

    ta_results = []
    aha_results = []

    total = len(scenarios)
    for idx, scen in enumerate(scenarios, start=1):
        print(f"[{idx}/{total}] Running {scen['id']} ({scen['name']})")
        bounds = scen['bounds']
        cfg = PlannerConfig(map_bounds=([bounds[0][0], bounds[1][0], bounds[2][0]],[bounds[0][1], bounds[1][1], bounds[2][1]]), voxel_size=0.5)

        timeout = 20.0 if scen['name']=='SMALL' else (40.0 if scen['name']=='MEDIUM' else 60.0)
        # AHA* (safe call)
        try:
            aha = AnytimeHierarchicalAStar(cfg, coarse_factor=3, initial_epsilon=2.0, epsilon_decay=0.5, terrain_cost_fn=terrain_cost_fn)
            t0 = time.time()
            res_aha = aha.plan_path(list(scen['start']), list(scen['goal']), terrain_data={'slopes':[0.0]}, timeout=timeout)
            t_aha = time.time() - t0
            aha_entry = {
                'scenario_id': scen['id'], 'map_size': scen['name'], 'success': getattr(res_aha, 'success', False),
                'computation_time': getattr(res_aha, 'computation_time', t_aha), 'path_length': getattr(res_aha, 'path_length', None),
                'nodes_explored': getattr(res_aha, 'nodes_explored', None)
            }
        except Exception as e:
            aha_entry = {'scenario_id': scen['id'], 'map_size': scen['name'], 'success': False, 'computation_time': None, 'path_length': None, 'nodes_explored': None, 'error': str(e)}
        aha_results.append(aha_entry)

        # TA*
        z_dim = max(50, scen['grid_size'] // 10)
        ta = TerrainAwareAStar(voxel_size=0.5, grid_size=(scen['grid_size'], scen['grid_size'], z_dim), min_bound=(0.0, 0.0, 0.0), use_cost_calculator=False)
        voxel_grid = np.zeros((scen['grid_size'], scen['grid_size'], z_dim), dtype=np.uint8)
        ta.set_terrain_data(voxel_grid, {'slopes': np.array([0.0])})
        t0 = time.time()
        path_ta = ta.plan_path(tuple(scen['start']), tuple(scen['goal']))
        t_ta = time.time() - t0

        # apply Shortcut smoothing
        try:
            from path_planner_3d.path_smoother import PathSmoother
            if path_ta is not None:
                smoother = PathSmoother()
                smoothed = smoother.shortcut(path_ta, ta, max_iter=5)
                if smoothed is not None and len(smoothed) <= len(path_ta):
                    path_ta = smoothed
        except Exception:
            pass

        ta_entry = {'scenario_id': scen['id'], 'map_size': scen['name'], 'success': path_ta is not None,
                    'computation_time': ta.last_search_stats.get('computation_time', t_ta),
                    'path_length_nodes': ta.last_search_stats.get('path_length', 0),
                    'path_length_meters': None, 'path_total_cost': None, 'path_smoothness': None,
                    'nodes_explored': ta.last_search_stats.get('nodes_explored', 0)}
        if path_ta is not None:
            metrics = compute_path_metrics_world(path_ta, ta)
            if metrics is not None:
                ta_entry['path_length_meters'] = metrics['length_meters']
                ta_entry['path_total_cost'] = metrics['total_cost']
                ta_entry['path_smoothness'] = metrics['smoothness']
        ta_results.append(ta_entry)

    # write individual JSONs
    ta_file = os.path.join(out_dir, 'ta_star_smoothed_96_results.json')
    aha_file = os.path.join(out_dir, 'aha_star_96_results.json')
    with open(ta_file, 'w') as f:
        json.dump({'planner':'TA_STAR','scenarios':len(ta_results),'results':ta_results}, f, indent=2)
    with open(aha_file, 'w') as f:
        json.dump({'planner':'AHA_STAR','scenarios':len(aha_results),'results':aha_results}, f, indent=2)

    # combined detailed
    combined_file = os.path.join(out_dir, 'seven_planners_detailed.json')
    combined = {'TA_STAR': ta_results, 'AHA_STAR': aha_results}
    with open(combined_file, 'w') as f:
        json.dump(combined, f, indent=2)

    # create comparison CSV (per planner aggregated)
    def aggregate(results_list):
        vals = [r['path_length_meters'] for r in results_list if r.get('path_length_meters') is not None]
        times = [r['computation_time'] for r in results_list if r.get('computation_time') is not None]
        nodes = [r['nodes_explored'] for r in results_list if r.get('nodes_explored') is not None]
        return {'mean_length': statistics.mean(vals) if vals else None, 'mean_time': statistics.mean(times) if times else None, 'mean_nodes': statistics.mean(nodes) if nodes else None}

    agg_ta = aggregate(ta_results)
    for r in aha_results:
        r['path_length_meters'] = r.get('path_length')
    agg_aha = aggregate(aha_results)

    csv_file = os.path.join(out_dir, 'seven_planners_comparison.csv')
    with open(csv_file, 'w', newline='') as csvf:
        writer = csv.writer(csvf)
        writer.writerow(['planner','all_mean_length_m','all_mean_time_s','all_mean_nodes'])
        writer.writerow(['TA_STAR', agg_ta['mean_length'], agg_ta['mean_time'], agg_ta['mean_nodes']])
        writer.writerow(['AHA_STAR', agg_aha['mean_length'], agg_aha['mean_time'], agg_aha['mean_nodes']])

    # basic statistics and t-test
    ta_lengths = [r['path_length_meters'] for r in ta_results if r.get('path_length_meters') is not None]
    aha_lengths = [r['path_length_meters'] for r in aha_results if r.get('path_length_meters') is not None]
    stats = {
        'TA': summarize(ta_results),
        'AHA': summarize(aha_results)
    }
    t, p, d = welch_ttest(ta_lengths, aha_lengths)
    analysis_file = os.path.join(out_dir, 'statistical_analysis.txt')
    with open(analysis_file, 'w') as fa:
        fa.write('TA vs AHA path length comparison\n')
        fa.write(f't-statistic: {t}\n')
        fa.write(f'p-value(approx): {p}\n')
        fa.write(f"cohen_d: {d}\n")
        fa.write('\nSummary:\n')
        fa.write(json.dumps(stats, indent=2))

    print('Benchmark complete. Results in', out_dir)


if __name__ == '__main__':
    main()
