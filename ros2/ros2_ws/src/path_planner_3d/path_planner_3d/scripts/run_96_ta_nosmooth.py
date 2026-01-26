#!/usr/bin/env python3
"""Run TA* over 96 scenarios without smoothing to measure pure search time.
Saves results to benchmark_results/ta_star_96_nosmooth_results.json
"""
import os, sys, time, json, math, multiprocessing as mp
import numpy as np

ROOT = os.path.dirname(os.path.dirname(__file__))
SRC_ROOT = os.path.abspath(os.path.join(ROOT, '..'))
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from path_planner_3d.config import PlannerConfig
from path_planner_3d.terrain_aware_astar_advanced import TerrainAwareAStar


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
        a = path_world[i]; b = path_world[i+1]
        dx = b[0]-a[0]; dy = b[1]-a[1]; dz = b[2]-a[2]
        total_dist += math.sqrt(dx*dx+dy*dy+dz*dz)
    return {'length_meters': total_dist}


def worker_run(scen, return_pipe):
    try:
        t0 = time.time()
        cfg = PlannerConfig(map_bounds=([0.0,0.0,0.0],[scen['world_size'],scen['world_size'],2.0]), voxel_size=0.5)
        z_dim = max(50, scen['grid_size'] // 10)
        ta = TerrainAwareAStar(voxel_size=0.5, grid_size=(scen['grid_size'], scen['grid_size'], z_dim), min_bound=(0.0, 0.0, 0.0), use_cost_calculator=False)
        voxel_grid = np.zeros((scen['grid_size'], scen['grid_size'], z_dim), dtype=np.uint8)
        ta.set_terrain_data(voxel_grid, {'slopes': np.array([0.0]), 'terrain_cost_map': scen['terrain_cost_map']})
        path = ta.plan_path(tuple(scen['start']), tuple(scen['goal']))
        # path may be PlanningResult or list
        if hasattr(path, 'path'):
            path_coords = path.path
            comp_time = getattr(path, 'computation_time', time.time()-t0)
            nodes = getattr(path, 'nodes_explored', None)
            success = bool(getattr(path,'success', False))
        else:
            path_coords = path
            comp_time = time.time()-t0
            nodes = ta.last_search_stats.get('nodes_explored', None) if hasattr(ta,'last_search_stats') else None
            success = path_coords is not None

        metrics = compute_path_metrics_world(path_coords) if path_coords else None
        res = {
            'scenario_id': scen['id'],
            'map_size': scen['name'],
            'success': success,
            'computation_time': comp_time,
            'path_length_meters': metrics['length_meters'] if metrics else None,
            'nodes_explored': nodes,
        }
        return_pipe.send(('ok', res))
    except Exception as e:
        try:
            return_pipe.send(('err', str(e)))
        except Exception:
            pass


def run_all():
    scenarios = generate_scenarios()
    out_dir = os.path.join(ROOT, 'benchmark_results')
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, 'ta_star_96_nosmooth_results.json')
    results = []
    total = len(scenarios)
    for i, scen in enumerate(scenarios):
        idx = i+1
        print(f"[{idx}/{total}] Running {scen['id']} ({scen['name']}) no-smooth...")
        parent_conn, child_conn = mp.Pipe()
        p = mp.Process(target=worker_run, args=(scen, child_conn))
        p.start()
        p.join(timeout=180)
        if p.is_alive():
            p.terminate(); p.join()
            print(' Timeout')
            results.append({'scenario_id':scen['id'],'error':'timeout'})
        else:
            try:
                status,payload = parent_conn.recv()
                if status=='ok': results.append(payload)
                else: results.append({'scenario_id':scen['id'],'error':payload})
            except EOFError:
                results.append({'scenario_id':scen['id'],'error':'no_result'})
        if idx%10==0 or idx==total:
            print(f' Progress {idx}/{total}')
        with open(out_file,'w') as fh: json.dump(results,fh,indent=2)
    print('Done. Saved to', out_file)


if __name__=='__main__':
    run_all()
