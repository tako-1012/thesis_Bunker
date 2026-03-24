#!/usr/bin/env python3
import os
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from importlib import util


def load_hill():
    base = os.path.join(os.path.dirname(__file__), '..')
    meta_path = os.path.join(base, 'terrain_test_scenarios', 'hill_detour_meta.json')
    data_path = os.path.join(base, 'terrain_test_scenarios', 'hill_detour_data.npz')
    with open(meta_path, 'r') as f:
        meta = json.load(f)
    data = np.load(data_path)
    elev = data['elevation']
    voxel_grid = data['voxel_grid']
    return meta, elev, voxel_grid


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


def make_2d(meta, elev, ta_path_world, reg_path_world, out_dir):
    # Height map: max over Z
    height_map = np.max(elev, axis=2)
    # convert world coords (centered at 0) to 0-100 by +50 shift
    def shift(points):
        return np.array([[p[0] + 50.0, p[1] + 50.0] for p in points]) if len(points) else np.empty((0,2))

    ta_xy = shift(ta_path_world)
    reg_xy = shift(reg_path_world)

    # compute zoom bounds
    if ta_xy.size and reg_xy.size:
        xs = np.concatenate([ta_xy[:,0], reg_xy[:,0]])
        ys = np.concatenate([ta_xy[:,1], reg_xy[:,1]])
        x_min = max(0, xs.min() - 10)
        x_max = min(100, xs.max() + 10)
        y_min = max(0, ys.min() - 10)
        y_max = min(100, ys.max() + 10)
    else:
        x_min, x_max, y_min, y_max = 0, 100, 0, 100

    fig_w = 12.0 / 2.54
    fig_h = 9.0 / 2.54
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    im = ax.imshow(height_map.T, cmap='terrain', origin='lower', extent=[0, 100, 0, 100], alpha=0.85, zorder=1)
    # add contours
    try:
        X = np.linspace(0, 100, height_map.shape[0])
        Y = np.linspace(0, 100, height_map.shape[1])
        XX, YY = np.meshgrid(X, Y)
        cs = ax.contour(XX, YY, height_map.T, levels=6, colors='white', alpha=0.35, linewidths=0.6, zorder=2)
    except Exception:
        pass

    if ta_xy.size:
        ax.plot(ta_xy[:,0], ta_xy[:,1], 'g-', linewidth=4, alpha=0.95, label='TA* (detours around terrain)', zorder=5)
    if reg_xy.size:
        ax.plot(reg_xy[:,0], reg_xy[:,1], 'r-', linewidth=4, alpha=0.95, label='Regular A* (direct path)', zorder=5)

    sx, sy, _ = meta['start']
    gx, gy, _ = meta['goal']
    ax.plot(sx + 50.0, sy + 50.0, 'bo', markersize=12, label='Start', zorder=6)
    ax.plot(gx + 50.0, gy + 50.0, color='yellow', marker='*', markersize=18, label='Goal', zorder=6)

    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.set_xlabel('X position [m]', fontsize=11)
    ax.set_ylabel('Y position [m]', fontsize=11)
    ax.grid(True, color='gray', alpha=0.3)
    leg = ax.legend(loc='upper right', framealpha=0.8)
    for t in leg.get_texts():
        t.set_fontsize(10)

    plt.tight_layout()
    png = os.path.join(out_dir, 'fig4_path_visualization_v2.png')
    pdf = os.path.join(out_dir, 'fig4_path_visualization_v2.pdf')
    plt.savefig(png, dpi=300, bbox_inches='tight')
    plt.savefig(pdf, bbox_inches='tight')
    plt.close(fig)


def make_3d(meta, elev, ta_path_world, reg_path_world, out_dir):
    # 3D surface
    height_map = np.max(elev, axis=2)
    nx, ny = height_map.shape
    X = np.linspace(0, 100, nx)
    Y = np.linspace(0, 100, ny)
    XX, YY = np.meshgrid(X, Y)
    ZZ = height_map.T

    fig = plt.figure(figsize=(10,8))
    ax = fig.add_subplot(111, projection='3d')
    ax.plot_surface(XX, YY, ZZ, cmap='terrain', alpha=0.8, linewidth=0, zorder=1)

    def proj3(path):
        if not path:
            return None
        xs = [p[0] + 50.0 for p in path]
        ys = [p[1] + 50.0 for p in path]
        zs = []
        for p in path:
            # sample height from map
            ix = int(round((p[0] + 50.0) / 100.0 * (nx - 1)))
            iy = int(round((p[1] + 50.0) / 100.0 * (ny - 1)))
            zs.append(np.max(elev[ix, iy, :]))
        return xs, ys, zs

    t3 = proj3(ta_path_world)
    r3 = proj3(reg_path_world)
    if t3:
        ax.plot(t3[0], t3[1], t3[2], color='green', linewidth=3, alpha=0.9, label='TA*', zorder=5)
    if r3:
        ax.plot(r3[0], r3[1], r3[2], color='red', linewidth=3, alpha=0.9, label='Regular A*', zorder=5)

    sx, sy, _ = meta['start']
    gx, gy, _ = meta['goal']
    # sample start/goal heights
    si = int(round((sx + 50.0)/100.0*(nx-1)))
    sj = int(round((sy + 50.0)/100.0*(ny-1)))
    gi = int(round((gx + 50.0)/100.0*(nx-1)))
    gj = int(round((gy + 50.0)/100.0*(ny-1)))
    sz = np.max(elev[si, sj, :])
    gz = np.max(elev[gi, gj, :])
    ax.scatter([sx+50.0], [sy+50.0], [sz], color='blue', s=60, label='Start', zorder=6)
    ax.scatter([gx+50.0], [gy+50.0], [gz], color='yellow', s=120, marker='*', label='Goal', zorder=6)

    ax.set_xlabel('X [m]')
    ax.set_ylabel('Y [m]')
    ax.set_zlabel('Height [m]')
    ax.view_init(elev=30, azim=45)
    ax.legend()
    plt.tight_layout()
    png = os.path.join(out_dir, 'fig4_path_visualization_3d.png')
    pdf = os.path.join(out_dir, 'fig4_path_visualization_3d.pdf')
    plt.savefig(png, dpi=300, bbox_inches='tight')
    plt.savefig(pdf, bbox_inches='tight')
    plt.close(fig)


def main():
    meta, elev, voxel_grid = load_hill()
    grid_size = tuple(meta['grid_size'])
    voxel_size = float(meta['voxel_size'])
    start = tuple(meta['start'])
    goal = tuple(meta['goal'])

    repo_root = os.path.join(os.path.dirname(__file__), '..')
    ta_path = os.path.join(repo_root, 'ros2/ros2_ws/src/path_planner_3d/path_planner_3d/terrain_aware_astar.py')
    astar_path = os.path.join(repo_root, 'ros2/ros2_ws/src/path_planner_3d/path_planner_3d/astar_3d.py')
    TerrainAwareAStar = import_planner(ta_path, 'TerrainAwareAStar')
    AStar3D = import_planner(astar_path, 'AStar3D')

    ta = TerrainAwareAStar(voxel_size=voxel_size, grid_size=grid_size)
    ta.set_terrain_data(voxel_grid, {'elevation': elev, 'roughness': np.zeros_like(elev), 'density': np.ones_like(elev)})
    ta_res = ta.plan_path(start, goal)
    ta_path_world = ta_res.get('path', []) if isinstance(ta_res, dict) else getattr(ta_res, 'path', [])

    astar = AStar3D(voxel_size=voxel_size, max_iterations=200000)
    s_vox = world_to_voxel(start, grid_size, voxel_size)
    g_vox = world_to_voxel(goal, grid_size, voxel_size)
    try:
        astar_res = astar.plan_path(s_vox, g_vox, voxel_grid, cost_function=None)
    except Exception:
        astar_res = None
    if astar_res is None:
        reg_path_world = []
    else:
        path_vox = getattr(astar_res, 'path', None)
        if path_vox is None and isinstance(astar_res, dict):
            path_vox = astar_res.get('path', [])
        reg_path_world = [voxel_to_world(p, grid_size, voxel_size) for p in path_vox]

    out_dir = '/mnt/user-data/outputs'
    try:
        os.makedirs(out_dir, exist_ok=True)
    except PermissionError:
        out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'figures')
        os.makedirs(out_dir, exist_ok=True)

    make_2d(meta, elev, ta_path_world, reg_path_world, out_dir)
    make_3d(meta, elev, ta_path_world, reg_path_world, out_dir)
    print('Saved v2 2D and 3D figures to', out_dir)


if __name__ == '__main__':
    main()
