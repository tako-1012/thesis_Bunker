#!/usr/bin/env python3
"""Run Theta* on the 96 benchmark scenarios.
Saves results to benchmark_results/theta_star_96_results.json
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
                'start': s,
                'goal': g,
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
    # smoothness
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


def worker_run(scen, return_pipe):
    try:
        # import ThetaStar from file
        import importlib.util
        theta_path = os.path.join(ROOT, 'theta_star.py')
        spec = importlib.util.spec_from_file_location('theta_star', theta_path)
        theta_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(theta_mod)
        ThetaStar = theta_mod.ThetaStar

        t0 = time.time()
        # create planner instance
        z_dim = max(50, scen['grid_size'] // 10)
        grid = np.zeros((scen['grid_size'], scen['grid_size'], z_dim), dtype=np.uint8)
        th = ThetaStar(voxel_size=0.5, grid_size=(scen['grid_size'], scen['grid_size'], z_dim))
        # use same min_bound as TA* default mapping
        th.set_terrain_data(grid, None, min_bound=(0.0,0.0,0.0))
        path = th.plan_path(tuple(scen['start']), tuple(scen['goal']))
        metrics = compute_path_metrics_world(path, None) if path is not None else None
        t1 = time.time()
        res = {
            'scenario_id': scen['id'],
            'map_size': scen['name'],
            'success': path is not None,
            'computation_time': t1 - t0,
            'path_length_meters': metrics['length_meters'] if metrics else None,
            'nodes_explored': th.last_search_stats.get('nodes_explored', None) if hasattr(th, 'last_search_stats') else None
        }
        return_pipe.send(('ok', res))
    except Exception as e:
        try:
            return_pipe.send(('err', str(e)))
        except Exception:
            pass


def run_all():
    scenarios = generate_96_scenarios()
    out_dir = os.path.join(ROOT, 'benchmark_results')
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, 'theta_star_96_results.json')
    results = []
    total = len(scenarios)
    for i, scen in enumerate(scenarios):
        idx = i+1
        print(f"[{idx}/{total}] Running {scen['id']} ({scen['name']})...")
        parent_conn, child_conn = mp.Pipe()
        p = mp.Process(target=worker_run, args=(scen, child_conn))
        p.start()
        p.join(timeout=180)
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

    print('Finished all scenarios. Results saved to', out_file)


if __name__ == '__main__':
    run_all()
