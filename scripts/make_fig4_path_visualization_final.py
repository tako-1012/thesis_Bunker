#!/usr/bin/env python3
import os
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from importlib import util


def try_load_paths(npz):
    # common possible keys
    candidates = ['ta_star_path', 'ta_path', 'ta_path_world', 'ta_path_vox',
                  'regular_a_star_path', 'regular_path', 'reg_path', 'a_star_path']
    found = {}
    for k in candidates:
        if k in npz.files:
            found[k] = npz[k]
    return found


def import_planner(module_path, symbol):
    spec = util.spec_from_file_location(symbol, module_path)
    mod = util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, symbol)


def world_from_voxel(idx, grid_size, voxel_size):
    vi = np.array(idx)
    half_x = (grid_size[0] * voxel_size) / 2.0
    half_y = (grid_size[1] * voxel_size) / 2.0
    min_bound = np.array([-half_x, -half_y, 0.0])
    wp = min_bound + (vi + 0.5) * voxel_size
    return tuple(wp)


def main():
    base = os.path.join(os.path.dirname(__file__), '..')
    # Prefer amplified dataset if present
    amplified = os.path.join(base, 'terrain_test_scenarios', 'hill_detour_amplified_data.npz')
    default = os.path.join(base, 'terrain_test_scenarios', 'hill_detour_data.npz')
    npz_path = amplified if os.path.exists(amplified) else default
    meta_path = os.path.join(base, 'terrain_test_scenarios', 'hill_detour_meta.json')
    analysis_path = os.path.join(base, 'benchmark_results', 'hill_detour_path_analysis.json')

    print('Loading:', npz_path)
    data = np.load(npz_path)
    print('Available keys in NPZ:', data.files)

    # Attempt to load precomputed paths
    found = try_load_paths(data)

    with open(meta_path, 'r') as f:
        meta = json.load(f)

    elev = data.get('elevation')
    if elev is None:
        raise RuntimeError('Elevation data not found in NPZ')
    # collapse to 2D height map
    height_map = np.max(elev, axis=2)

    # initialize variables
    ta_path_world = None
    reg_path_world = None

    # If NPZ contains explicit paths, use them
    if found:
        print('Found potential path arrays in NPZ:', list(found.keys()))
        # Heuristics: pick first ta-like and first reg-like
        for k in found:
            if 'ta' in k and ta_path_world is None:
                ta_path_world = np.asarray(found[k])
            if ('regular' in k or 'reg' in k or 'a_star' in k) and reg_path_world is None:
                reg_path_world = np.asarray(found[k])

    # If missing, compute using planners
    if ta_path_world is None or reg_path_world is None:
        print('Precomputed paths not found for both planners — computing using planner implementations')
        repo_root = os.path.join(base)
        ta_path = os.path.join(repo_root, 'ros2/ros2_ws/src/path_planner_3d/path_planner_3d/terrain_aware_astar.py')
        astar_path = os.path.join(repo_root, 'ros2/ros2_ws/src/path_planner_3d/path_planner_3d/astar_3d.py')
        TerrainAwareAStar = import_planner(ta_path, 'TerrainAwareAStar')
        AStar3D = import_planner(astar_path, 'AStar3D')

        grid_size = tuple(meta.get('grid_size', (100,100,20)))
        voxel_size = float(meta.get('voxel_size', 0.2))
        start = tuple(meta['start'])
        goal = tuple(meta['goal'])

        # TA*
        ta = TerrainAwareAStar(voxel_size=voxel_size, grid_size=grid_size)
        ta.set_terrain_data(data['voxel_grid'], {'elevation': elev, 'roughness': data.get('roughness', np.zeros_like(elev)), 'density': data.get('density', np.ones_like(elev))})
        ta_res = ta.plan_path(start, goal)
        if isinstance(ta_res, dict):
            ta_path_world = ta_res.get('path', [])
        else:
            ta_path_world = getattr(ta_res, 'path', [])

        # Regular A* (voxel-based)
        s_vox = (int(round((start[0] + (grid_size[0]*voxel_size)/2.0)/voxel_size)),
                 int(round((start[1] + (grid_size[1]*voxel_size)/2.0)/voxel_size)),
                 int(round(start[2]/voxel_size)))
        g_vox = (int(round((goal[0] + (grid_size[0]*voxel_size)/2.0)/voxel_size)),
                 int(round((goal[1] + (grid_size[1]*voxel_size)/2.0)/voxel_size)),
                 int(round(goal[2]/voxel_size)))
        astar = AStar3D(voxel_size=voxel_size, max_iterations=200000)
        try:
            astar_res = astar.plan_path(s_vox, g_vox, data['voxel_grid'], cost_function=None)
        except Exception:
            astar_res = None
        if astar_res is None:
            reg_path_world = []
        else:
            path_vox = getattr(astar_res, 'path', None)
            if path_vox is None and isinstance(astar_res, dict):
                path_vox = astar_res.get('path', [])
            reg_path_world = [world_from_voxel(p, grid_size, voxel_size) for p in path_vox]

    # Ensure numpy arrays
    ta_path_world = np.asarray(ta_path_world)
    reg_path_world = np.asarray(reg_path_world)

    # Debug info: sizes and ranges
    print('\nTA* path info:')
    if ta_path_world.size:
        print('  Number of points:', len(ta_path_world))
        print(f"  X range: {ta_path_world[:,0].min():.2f} to {ta_path_world[:,0].max():.2f}")
        print(f"  Y range: {ta_path_world[:,1].min():.2f} to {ta_path_world[:,1].max():.2f}")
    else:
        print('  TA* path empty')

    print('\nRegular A* path info:')
    if reg_path_world.size:
        print('  Number of points:', len(reg_path_world))
        print(f"  X range: {reg_path_world[:,0].min():.2f} to {reg_path_world[:,0].max():.2f}")
        print(f"  Y range: {reg_path_world[:,1].min():.2f} to {reg_path_world[:,1].max():.2f}")
    else:
        print('  Regular A* path empty')

    # compute heights along paths (map sampling)
    def sample_heights(path):
        if path is None or len(path)==0:
            return []
        heights = []
        hm = height_map
        nx, ny = hm.shape
        for p in path:
            xw, yw = p[0], p[1]
            # world coords are centered at 0; shift to 0-100 then convert to map indices
            ix = int(round((xw + 50.0)/100.0*(nx-1)))
            iy = int(round((yw + 50.0)/100.0*(ny-1)))
            ix = max(0, min(nx-1, ix))
            iy = max(0, min(ny-1, iy))
            heights.append(float(hm[ix, iy]))
        return heights

    ta_heights = sample_heights(ta_path_world)
    reg_heights = sample_heights(reg_path_world)

    if ta_heights:
        print(f"\nTA* max height: {max(ta_heights):.2f}m")
    if reg_heights:
        print(f"Regular A* max height: {max(reg_heights):.2f}m")
    if ta_heights and reg_heights:
        print(f"Height difference (Reg - TA): {max(reg_heights)-max(ta_heights):.2f}m")

    # Plot final figure per user spec
    fig_w = 12.0/2.54
    fig_h = 9.0/2.54
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    # compute zoom bounds in world coords (assume paths are in world coords)
    def bounds_from_paths(a, b):
        xs = np.array([])
        ys = np.array([])
        if a.size:
            xs = np.concatenate([xs, a[:,0]])
            ys = np.concatenate([ys, a[:,1]])
        if b.size:
            xs = np.concatenate([xs, b[:,0]])
            ys = np.concatenate([ys, b[:,1]])
        if xs.size:
            x_min = xs.min() - 10
            x_max = xs.max() + 10
            y_min = ys.min() - 10
            y_max = ys.max() + 10
        else:
            x_min, x_max, y_min, y_max = 0, 100, 0, 100
        return x_min, x_max, y_min, y_max

    x_min, x_max, y_min, y_max = bounds_from_paths(ta_path_world, reg_path_world)

    # Plot terrain with extent mapping to 0-100
    im = ax.imshow(height_map.T, cmap='terrain', origin='lower', extent=[0, 100, 0, 100], alpha=0.8, zorder=1)
    plt.colorbar(im, ax=ax, label='Height [m]')

    # Regular first
    if reg_path_world.size:
        ax.plot(reg_path_world[:,0], reg_path_world[:,1], 'r-', linewidth=4, alpha=0.95, label='Regular A* (direct path)', zorder=4)
    # TA* on top
    if ta_path_world.size:
        ax.plot(ta_path_world[:,0], ta_path_world[:,1], 'g-', linewidth=4, alpha=0.95, label='TA* (detours around terrain)', zorder=5)

    # Start/Goal from TA* path if available else meta
    if ta_path_world.size:
        ax.plot(ta_path_world[0,0], ta_path_world[0,1], 'bo', markersize=12, label='Start', zorder=6)
        ax.plot(ta_path_world[-1,0], ta_path_world[-1,1], 'y*', markersize=18, label='Goal', zorder=6)
    else:
        sx, sy, _ = meta['start']
        gx, gy, _ = meta['goal']
        ax.plot(sx+50.0, sy+50.0, 'bo', markersize=12, label='Start', zorder=6)
        ax.plot(gx+50.0, gy+50.0, 'y*', markersize=18, label='Goal', zorder=6)

    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.set_xlabel('X position [m]', fontsize=11)
    ax.set_ylabel('Y position [m]', fontsize=11)
    ax.grid(True, color='gray', alpha=0.3)
    ax.legend(loc='upper right', framealpha=0.8)
    plt.tight_layout()

    out_dir = '/mnt/user-data/outputs'
    try:
        os.makedirs(out_dir, exist_ok=True)
    except PermissionError:
        out_dir = os.path.join(base, 'figures')
        os.makedirs(out_dir, exist_ok=True)
        print('Note: /mnt not writable; saved to', out_dir)

    png = os.path.join(out_dir, 'fig4_path_visualization_FINAL.png')
    pdf = os.path.join(out_dir, 'fig4_path_visualization_FINAL.pdf')
    plt.savefig(png, dpi=300, bbox_inches='tight')
    plt.savefig(pdf, bbox_inches='tight')
    plt.close(fig)

    print('\nSaved final figures:')
    print(' ', png)
    print(' ', pdf)


if __name__ == '__main__':
    main()
