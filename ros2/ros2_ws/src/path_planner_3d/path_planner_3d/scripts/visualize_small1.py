#!/usr/bin/env python3
"""
Visualize SMALL_1: compare TA* and AHA* paths and produce cost breakdown.
Outputs:
 - /tmp/small1_paths.png
 - /tmp/small1_cost_breakdown.txt
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(__file__))
SRC_ROOT = os.path.abspath(os.path.join(ROOT, '..'))
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import time
import json
import numpy as np
import matplotlib.pyplot as plt

from path_planner_3d.config import PlannerConfig
from path_planner_3d.anytime_hierarchical_astar import AnytimeHierarchicalAStar
from path_planner_3d.terrain_aware_astar_advanced import TerrainAwareAStar
from path_planner_3d.cost_function import CostFunction

# replicate generate_scenarios from run_small_bench_local to ensure deterministic scenario
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


def segment_costs(path, cost_fn, terrain_data):
    # path: list of (x,y,z) tuples
    segs = []
    for i in range(len(path)-1):
        a = path[i]
        b = path[i+1]
        cb = cost_fn.get_cost_breakdown(tuple(a), tuple(b), terrain_data)
        segs.append({'from': tuple(a), 'to': tuple(b), 'breakdown': cb})
    return segs


def main():
    scenarios = generate_scenarios()
    scen = None
    for s in scenarios:
        if s['name'] == 'SMALL_1':
            scen = s
            break
    if scen is None:
        print('SMALL_1 not found')
        return

    print('Selected scenario:', scen['name'])

    # planner config
    bounds = scen['bounds']
    cfg = PlannerConfig(map_bounds=([bounds[0][0], bounds[1][0], bounds[2][0]],[bounds[0][1], bounds[1][1], bounds[2][1]]), voxel_size=0.5)

    # cost function
    weights = {'distance':1.0,'slope':1.0,'obstacle':1.0,'stability':1.0}
    safety = {'min_obstacle_distance':0.5}
    cost_fn = CostFunction(weights, safety)
    terrain_cost_fn = lambda f,t,d: float(cost_fn.calculate_total_cost(f,t,d if d is not None else {}))

    # run AHA*
    aha = AnytimeHierarchicalAStar(cfg, coarse_factor=3, initial_epsilon=2.0, epsilon_decay=0.5, terrain_cost_fn=terrain_cost_fn)
    res_aha = aha.plan_path(list(scen['start']), list(scen['goal']), terrain_data={'slopes':[0.0], 'terrain_cost_map': scen['terrain_cost_map']}, timeout=20.0)
    path_aha = res_aha.path if res_aha.success else []

    # run TA*
    z_dim = max(50, scen['grid_size'] // 10)
    ta = TerrainAwareAStar(voxel_size=0.5, grid_size=(scen['grid_size'], scen['grid_size'], z_dim), min_bound=(0.0, 0.0, 0.0), use_cost_calculator=False)
    voxel_grid = np.zeros((scen['grid_size'], scen['grid_size'], z_dim), dtype=np.uint8)
    ta.set_terrain_data(voxel_grid, {'slopes': np.array([0.0]), 'terrain_cost_map': scen['terrain_cost_map']})
    path_ta = ta.plan_path(tuple(scen['start']), tuple(scen['goal']))
    # apply Shortcut -> B-spline smoothing pipeline to TA* path
    try:
        from path_planner_3d.path_smoother import PathSmoother
        smoother = PathSmoother()
        # Step 1: Shortcut to remove unnecessary nodes
        path_ta_short = smoother.shortcut(path_ta, ta, max_iter=50)
        if path_ta_short is not None and len(path_ta_short) >= 2:
            path_ta = path_ta_short
        # Step 2: Gentle B-spline smoothing
        path_ta_smoothed = smoother.bspline(path_ta, ta, smoothing=0.2, num_points=100)
        if path_ta_smoothed is not None and len(path_ta_smoothed) >= 2:
            path_ta = path_ta_smoothed
    except Exception:
        pass

    # Prepare visualization
    cmap = scen['terrain_cost_map']
    grid_size = scen['grid_size']
    world_size = scen['world_size']

    fig, ax = plt.subplots(figsize=(8,8))
    extent = [0, world_size, 0, world_size]
    im = ax.imshow(np.flipud(cmap), cmap='viridis', extent=extent, origin='lower')
    fig.colorbar(im, ax=ax, label='terrain cost')

    # plot paths (project to XY)
    def plot_path(path, label, color):
        if not path:
            return
        xs = [p[0] for p in path]
        ys = [p[1] for p in path]
        ax.plot(xs, ys, '-', color=color, label=label)
        ax.scatter([xs[0]], [ys[0]], marker='o', color=color)
        ax.scatter([xs[-1]], [ys[-1]], marker='x', color=color)

    plot_path(path_ta, f'TA* (len={ta.last_search_stats.get("path_length",0):.2f})', 'red')
    plot_path(path_aha, f'AHA* (len={res_aha.path_length:.2f})', 'cyan')

    ax.set_title('SMALL_1: TA* (red) vs AHA* (cyan)')
    ax.legend()
    out_img = '/tmp/small1_paths.png'
    fig.savefig(out_img, dpi=150)
    # also save inside workspace for easy reading
    ws_out_dir = os.path.join(ROOT, 'output')
    os.makedirs(ws_out_dir, exist_ok=True)
    ws_img = os.path.join(ws_out_dir, 'small1_paths.png')
    fig.savefig(ws_img, dpi=150)
    print('Saved image to', out_img)
    print('Also saved image to', ws_img)

    # cost breakdown per segment
    terrain_data = {'slopes': [0.0], 'terrain_cost_map': scen['terrain_cost_map']}
    cb_ta = segment_costs(path_ta, cost_fn, terrain_data) if path_ta else []
    cb_aha = segment_costs(path_aha, cost_fn, terrain_data) if path_aha else []

    # build report string and write to both files
    out_txt = '/tmp/small1_cost_breakdown.txt'
    ws_txt = os.path.join(ws_out_dir, 'small1_cost_breakdown.txt')
    lines = []
    lines.append(f"Scenario: {scen['name']}")
    lines.append(f"Start: {scen['start']}")
    lines.append(f"Goal: {scen['goal']}")
    lines.append('\nTA* path segments breakdown:')
    total_ta = 0.0
    for i,seg in enumerate(cb_ta):
        b = seg['breakdown']
        lines.append(f"seg{i}: from={seg['from']} to={seg['to']} -> total={b['total_cost']:.4f} dist={b['distance_cost']:.4f} slope={b['slope_cost']:.4f} obstacle={b['obstacle_cost']:.4f} stability={b['stability_cost']:.4f}")
        total_ta += b['total_cost']
    lines.append(f"TA* total segment cost (sum): {total_ta:.4f}\n")

    lines.append('AHA* path segments breakdown:')
    total_aha = 0.0
    for i,seg in enumerate(cb_aha):
        b = seg['breakdown']
        lines.append(f"seg{i}: from={seg['from']} to={seg['to']} -> total={b['total_cost']:.4f} dist={b['distance_cost']:.4f} slope={b['slope_cost']:.4f} obstacle={b['obstacle_cost']:.4f} stability={b['stability_cost']:.4f}")
        total_aha += b['total_cost']
    lines.append(f"AHA* total segment cost (sum): {total_aha:.4f}\n")

    lines.append('Analysis:')
    lines.append(f"TA* path_length reported: {ta.last_search_stats.get('path_length',0):.2f}")
    lines.append(f"AHA* path_length reported: {res_aha.path_length:.2f}")
    lines.append('Compare dominant cost components per path:')
    def dominant_component(cb_list):
        sums = {'distance':0.0,'slope':0.0,'obstacle':0.0,'stability':0.0}
        for s in cb_list:
            b = s['breakdown']
            sums['distance'] += b['distance_cost']
            sums['slope'] += b['slope_cost']
            sums['obstacle'] += b['obstacle_cost']
            sums['stability'] += b['stability_cost']
        return sums
    sums_ta = dominant_component(cb_ta)
    sums_aha = dominant_component(cb_aha)
    lines.append(f"TA* sums: {sums_ta}")
    lines.append(f"AHA* sums: {sums_aha}")

    report = "\n".join(lines)
    with open(out_txt, 'w') as fh:
        fh.write(report)
    with open(ws_txt, 'w') as fh_ws:
        fh_ws.write(report)

    print('Saved cost breakdown to', out_txt)
    print('Also saved cost breakdown to', ws_txt)

if __name__ == '__main__':
    main()
