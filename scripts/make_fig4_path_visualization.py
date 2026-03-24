#!/usr/bin/env python3
import os
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from importlib import util


def load_scenario():
    base = os.path.join(os.path.dirname(__file__), '..')
    meta_path = os.path.join(base, 'terrain_test_scenarios', 'hill_detour_meta.json')
    data_path = os.path.join(base, 'terrain_test_scenarios', 'hill_detour_data.npz')
    with open(meta_path, 'r') as f:
        meta = json.load(f)
    data = np.load(data_path)
    voxel_grid = data['voxel_grid']
    elevation = data['elevation']
    roughness = data['roughness']
    density = data['density']
    terrain = {
        'elevation': elevation,
        'roughness': roughness,
        'density': density
    }
    return meta, voxel_grid, terrain


def import_planner(module_path, symbol):
    spec = util.spec_from_file_location(symbol, module_path)
    mod = util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, symbol)


def world_to_voxel(world, grid_size, voxel_size, min_bound=None):
    wp = np.array(world)
    if min_bound is None:
        half_x = (grid_size[0] * voxel_size) / 2.0
        half_y = (grid_size[1] * voxel_size) / 2.0
        min_bound = np.array([-half_x, -half_y, 0.0])
    vp = (wp - min_bound) / voxel_size
    return tuple(int(round(v)) for v in vp)


def voxel_to_world(idx, grid_size, voxel_size, min_bound=None):
    vi = np.array(idx)
    if min_bound is None:
        half_x = (grid_size[0] * voxel_size) / 2.0
        half_y = (grid_size[1] * voxel_size) / 2.0
        min_bound = np.array([-half_x, -half_y, 0.0])
    wp = min_bound + (vi + 0.5) * voxel_size
    return tuple(wp)


def main():
    meta, voxel_grid, terrain = load_scenario()
    grid_size = tuple(meta['grid_size'])
    voxel_size = float(meta['voxel_size'])
    start = tuple(meta['start'])
    goal = tuple(meta['goal'])

    # Import planners from repo
    repo_root = os.path.join(os.path.dirname(__file__), '..')
    ta_path = os.path.join(repo_root, 'ros2/ros2_ws/src/path_planner_3d/path_planner_3d/terrain_aware_astar.py')
    astar_path = os.path.join(repo_root, 'ros2/ros2_ws/src/path_planner_3d/path_planner_3d/astar_3d.py')
    TerrainAwareAStar = import_planner(ta_path, 'TerrainAwareAStar')
    AStar3D = import_planner(astar_path, 'AStar3D')

    # Run TA*
    ta = TerrainAwareAStar(voxel_size=voxel_size, grid_size=grid_size)
    ta.set_terrain_data(voxel_grid, terrain)
    ta_res = ta.plan_path(start, goal)
    # plan_path may return dict or PlanningResult-like object
    if isinstance(ta_res, dict):
        ta_path_world = ta_res.get('path', [])
    else:
        ta_path_world = getattr(ta_res, 'path', [])

    # Run regular A* (ignoring terrain) using AStar3D
    astar = AStar3D(voxel_size=voxel_size, max_iterations=200000)
    # Convert start/goal to voxel indices
    s_vox = world_to_voxel(start, grid_size, voxel_size)
    g_vox = world_to_voxel(goal, grid_size, voxel_size)

    # AStar3D.plan_path expects (x,y,z) ints and voxel_grid and cost_function (unused)
    try:
        astar_res = astar.plan_path(s_vox, g_vox, voxel_grid, cost_function=None)
    except Exception:
        astar_res = None
    if astar_res is None:
        regular_path_world = []
    else:
        # astar returns PlanningResult or object with .path of voxel coords
        path_vox = getattr(astar_res, 'path', None)
        if path_vox is None and isinstance(astar_res, dict):
            path_vox = astar_res.get('path', [])
        regular_path_world = [voxel_to_world(p, grid_size, voxel_size) for p in path_vox]

    # Extract 2D height map for plotting: use max elevation across z as single height grid
    elev = terrain['elevation']
    # elevation shape: (X,Y,Z) -> take max along Z
    height_map = np.max(elev, axis=2)

    # Prepare figure
    fig_w = 12.0 / 2.54  # 12 cm to inches
    fig_h = 9.0 / 2.54   # 9 cm (between 8-10)
    plt.figure(figsize=(fig_w, fig_h))
    ax = plt.gca()
    im = ax.imshow(height_map.T, cmap='terrain', origin='lower', extent=[0, 100, 0, 100], aspect='equal')
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Height [m]')

    # Plot TA* and Regular A* paths (project to X,Y)
    if ta_path_world:
        ta_xy = np.array([[p[0], p[1]] for p in ta_path_world])
        ax.plot(ta_xy[:, 0] + 50.0, ta_xy[:, 1] + 50.0, color='green', linewidth=3, alpha=0.8, label='TA*')
    if regular_path_world:
        reg_xy = np.array([[p[0], p[1]] for p in regular_path_world])
        ax.plot(reg_xy[:, 0] + 50.0, reg_xy[:, 1] + 50.0, color='red', linewidth=3, alpha=0.8, label='Regular A*')

    # The scenario world coordinates are centered around 0; our extent [0,100] mapping expects shift
    # start/goal are in world coords; shift by +50 to map to 0-100
    sx, sy, _ = start
    gx, gy, _ = goal
    ax.plot(sx + 50.0, sy + 50.0, 'bo', markersize=10, label='Start')
    ax.plot(gx + 50.0, gy + 50.0, color='yellow', marker='*', markersize=15, label='Goal')

    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_xlabel('X position [m]', fontsize=11)
    ax.set_ylabel('Y position [m]', fontsize=11)
    ax.grid(True, color='gray', alpha=0.3)
    legend = ax.legend(loc='upper right', framealpha=0.8)
    for text in legend.get_texts():
        text.set_fontsize(10)

    plt.tight_layout()

    out_dir = '/mnt/user-data/outputs'
    try:
        os.makedirs(out_dir, exist_ok=True)
    except PermissionError:
        # fallback to workspace figures directory if /mnt is not writable
        out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'figures')
        os.makedirs(out_dir, exist_ok=True)
        print('Warning: cannot write to /mnt/user-data/outputs; saving to', out_dir)
    png_path = os.path.join(out_dir, 'fig4_path_visualization.png')
    pdf_path = os.path.join(out_dir, 'fig4_path_visualization.pdf')
    plt.savefig(png_path, dpi=300, bbox_inches='tight')
    plt.savefig(pdf_path, bbox_inches='tight')
    print('Saved', png_path, pdf_path)


if __name__ == '__main__':
    main()
