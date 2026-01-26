#!/usr/bin/env python3
"""Run AHA* baseline and optimized over 96 scenarios.
Saves results to benchmark_results/aha_star_96_baseline_results.json and
benchmark_results/aha_star_96_optimized_results.json and a selected final file.
Writes progress to progress_log.txt
"""
import os
import sys
import time
import json
import math
import multiprocessing as mp
import numpy as np

ROOT = os.path.dirname(os.path.dirname(__file__))
SRC_ROOT = os.path.abspath(os.path.join(ROOT, '..'))
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from path_planner_3d.config import PlannerConfig
from path_planner_3d.anytime_hierarchical_astar import AnytimeHierarchicalAStar


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
            return s.tolist(), g.tolist()


def generate_scenarios():
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
            scenarios.append({
                'id': f'{name}_{i+1}',
                'name': name,
                'start': s,
                'goal': g,
                'grid_size': grid_size,
                'world_size': world_size,
                'terrain_cost_map': cmap,
            })
    return scenarios


def compute_path_metrics_world(path_world):
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
    return {'length_meters': total_dist, 'smoothness': smoothness}


def worker_run(scen, params, return_pipe):
    try:
        t0 = time.time()
        cfg = PlannerConfig(map_bounds=([0.0,0.0,0.0],[scen['world_size'],scen['world_size'],2.0]), voxel_size=0.5)
        # AHA*
        aha = AnytimeHierarchicalAStar(cfg, coarse_factor=params.get('coarse_factor',3), initial_epsilon=params.get('initial_epsilon',2.0), epsilon_decay=params.get('epsilon_decay',0.8), min_epsilon=params.get('min_epsilon',1.0))
        # terrain data passed through
        terrain_data = {'terrain_cost_map': scen['terrain_cost_map']}
        result = aha.plan(list(scen['start']), list(scen['goal']), terrain_data=terrain_data, timeout=params.get('timeout',180.0))

        path = result.path if hasattr(result, 'path') else (result if isinstance(result, list) else None)
        metrics = compute_path_metrics_world(path) if path else None
        t1 = time.time()
        res = {
            'scenario_id': scen['id'],
            'map_size': scen['name'],
            'success': bool(getattr(result, 'success', False)),
            'computation_time': float(getattr(result, 'computation_time', t1 - t0)),
            'path_length_meters': metrics['length_meters'] if metrics else getattr(result, 'path_length', None),
            'path_total_cost': None,
            'path_smoothness': metrics['smoothness'] if metrics else None,
            'nodes_explored': int(getattr(result, 'nodes_explored', 0)),
            'iterations': int(getattr(result, 'iterations', 0)) if hasattr(result, 'iterations') else None,
            'early_exit_reason': getattr(result, 'early_exit_reason', None),
        }
        return_pipe.send(('ok', res))
    except Exception as e:
        try:
            return_pipe.send(('err', str(e)))
        except Exception:
            pass


def run_with_params(params, out_name):
    scenarios = generate_scenarios()
    out_dir = os.path.join(ROOT, 'benchmark_results')
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, out_name)
    results = []
    total = len(scenarios)
    with open(os.path.join(ROOT, 'progress_log.txt'),'a') as log:
        log.write(f"\nStarting run {out_name} at {time.ctime()} with params {params}\n")
    for i, scen in enumerate(scenarios):
        idx = i+1
        print(f"[{idx}/{total}] AHA* running {scen['id']} ({scen['name']})...")
        parent_conn, child_conn = mp.Pipe()
        p = mp.Process(target=worker_run, args=(scen, params, child_conn))
        p.start()
        p.join(timeout=params.get('per_scenario_timeout', 180))
        if p.is_alive():
            p.terminate()
            p.join()
            print(f"  Timeout: {scen['id']} skipped")
            results.append({'scenario_id': scen['id'], 'error': 'timeout'})
        else:
            try:
                status, payload = parent_conn.recv()
                if status == 'ok':
                    results.append(payload)
                else:
                    results.append({'scenario_id': scen['id'], 'error': payload})
            except EOFError:
                results.append({'scenario_id': scen['id'], 'error': 'no_result'})
        if idx % 10 == 0 or idx == total:
            print(f"  Progress: {idx}/{total} completed")
        with open(out_file, 'w') as fh:
            json.dump(results, fh, indent=2)
    print('Finished run, saved to', out_file)
    with open(os.path.join(ROOT, 'progress_log.txt'),'a') as log:
        log.write(f"Finished run {out_name} at {time.ctime()} (entries={len(results)})\n")
    return results


def summarize_results(results):
    success = [r for r in results if r.get('success')]
    failed = [r for r in results if not r.get('success')]
    import statistics
    vals = [r['path_length_meters'] for r in success if r.get('path_length_meters') is not None]
    times = [r['computation_time'] for r in success if r.get('computation_time') is not None]
    summary = {
        'total': len(results),
        'success': len(success),
        'failed': len(failed),
        'mean_path_length': statistics.mean(vals) if vals else None,
        'mean_time': statistics.mean(times) if times else None,
    }
    return summary


def main():
    # Baseline
    baseline_params = {'coarse_factor':3, 'initial_epsilon':2.0, 'epsilon_decay':0.5, 'min_epsilon':1.0, 'timeout':180.0, 'per_scenario_timeout':180}
    baseline_file = 'aha_star_96_baseline_results.json'
    baseline_results = run_with_params(baseline_params, baseline_file)
    baseline_summary = summarize_results(baseline_results)
    with open(os.path.join(ROOT,'benchmark_results','aha_star_96_baseline_summary.json'),'w') as fh:
        json.dump(baseline_summary, fh, indent=2)

    # Optimized
    opt_params = {'coarse_factor':3, 'initial_epsilon':2.0, 'epsilon_decay':0.5, 'min_epsilon':1.0, 'good_solution_threshold':1.05, 'no_improvement_limit':3, 'min_iterations':2, 'timeout':180.0, 'per_scenario_timeout':180}
    opt_file = 'aha_star_96_optimized_results.json'
    optimized_results = run_with_params(opt_params, opt_file)
    opt_summary = summarize_results(optimized_results)
    with open(os.path.join(ROOT,'benchmark_results','aha_star_96_optimized_summary.json'),'w') as fh:
        json.dump(opt_summary, fh, indent=2)

    # Decide which to adopt
    chosen = None
    # Compare mean path length (lower better)
    b_len = baseline_summary.get('mean_path_length')
    o_len = opt_summary.get('mean_path_length')
    b_time = baseline_summary.get('mean_time')
    o_time = opt_summary.get('mean_time')
    if b_len is not None and o_len is not None:
        if o_len < b_len:
            chosen = ('optimized', optimized_results)
        else:
            # equal or worse -> pick shorter computation time
            if (abs(o_len - b_len) / max(b_len,1e-9)) <= 0.01:
                # within 1% consider equal
                chosen = ('baseline' if b_time <= o_time else 'optimized', baseline_results if b_time <= o_time else optimized_results)
            else:
                chosen = ('baseline', baseline_results)
    else:
        chosen = ('optimized' if optimized_results else 'baseline', optimized_results if optimized_results else baseline_results)

    chosen_name, chosen_results = chosen
    chosen_path = os.path.join(ROOT,'benchmark_results', f'aha_star_96_selected_{chosen_name}.json')
    with open(chosen_path, 'w') as fh:
        json.dump(chosen_results, fh, indent=2)
    with open(os.path.join(ROOT,'progress_log.txt'),'a') as log:
        log.write(f"AHA* runs complete. Chosen={chosen_name} saved to {chosen_path}\n")
    print('AHA* Phase complete. Chosen:', chosen_name)


if __name__ == '__main__':
    main()
