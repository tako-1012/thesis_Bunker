#!/usr/bin/env python3
import os
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource
from importlib import util


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


def sample_heights_world(path, elevation_3d, grid_size=(100, 100, 20), voxel_size=0.2):
    """
    経路の各点における地形標高を取得
    path: world coordinates (x, y, z) in centered frame (-10..10)
    elevation_3d: 3D array [x, y, z] with elevation values (各XY位置で全Zレイヤー同じ標高)
    """
    if path is None or len(path) == 0:
        return []
    
    hs = []
    half_x = (grid_size[0] * voxel_size) / 2.0
    half_y = (grid_size[1] * voxel_size) / 2.0
    min_bound = np.array([-half_x, -half_y, 0.0])
    
    for p in path:
        # World coords to voxel indices (XY座標のみを使用)
        vox_idx = np.round((np.array(p) - min_bound) / voxel_size).astype(int)
        ix = max(0, min(grid_size[0] - 1, vox_idx[0]))
        iy = max(0, min(grid_size[1] - 1, vox_idx[1]))
        
        # Get elevation at this XY position (Z=0レイヤーから取得、全Zで同じ)
        h = float(elevation_3d[ix, iy, 0])
        hs.append(h)
    
    return hs


def main():
    base = os.path.join(os.path.dirname(__file__), '..')
    # 重要: amplified版ではなく、オリジナル（最大10m）を使用
    npz_path = os.path.join(base, 'terrain_test_scenarios', 'hill_detour_data.npz')
    meta_path = os.path.join(base, 'terrain_test_scenarios', 'hill_detour_meta.json')

    data = np.load(npz_path)
    with open(meta_path, 'r') as f:
        meta = json.load(f)

    elev = data['elevation']
    height_map = np.max(elev, axis=2)

    # Try to find precomputed paths in NPZ
    ta_path = None
    reg_path = None
    for k in data.files:
        if 'ta' in k and 'path' in k:
            ta_path = np.asarray(data[k])
        if ('regular' in k or 'reg' in k or 'a_star' in k) and 'path' in k:
            reg_path = np.asarray(data[k])

    # Otherwise compute with planners
    if ta_path is None or reg_path is None:
        ta_mod = os.path.join(base, 'ros2/ros2_ws/src/path_planner_3d/path_planner_3d/terrain_aware_astar.py')
        astar_mod = os.path.join(base, 'ros2/ros2_ws/src/path_planner_3d/path_planner_3d/astar_3d.py')
        TerrainAwareAStar = import_planner(ta_mod, 'TerrainAwareAStar')
        AStar3D = import_planner(astar_mod, 'AStar3D')

        grid_size = tuple(meta.get('grid_size', (100, 100, 20)))
        voxel_size = float(meta.get('voxel_size', 0.2))
        start = tuple(meta['start'])
        goal = tuple(meta['goal'])

        ta = TerrainAwareAStar(voxel_size=voxel_size, grid_size=grid_size)
        ta.set_terrain_data(data['voxel_grid'], {'elevation': elev, 'roughness': data.get('roughness', np.zeros_like(elev)), 'density': data.get('density', np.ones_like(elev))})
        ta_res = ta.plan_path(start, goal)
        ta_path = ta_res.get('path', []) if isinstance(ta_res, dict) else getattr(ta_res, 'path', [])

        # compute voxel indices for astar
        half_x = (grid_size[0] * voxel_size) / 2.0
        half_y = (grid_size[1] * voxel_size) / 2.0
        min_bound = np.array([-half_x, -half_y, 0.0])
        s_vox = tuple(np.round((np.array(start) - min_bound) / voxel_size).astype(int))
        g_vox = tuple(np.round((np.array(goal) - min_bound) / voxel_size).astype(int))

        astar = AStar3D(voxel_size=voxel_size, max_iterations=200000)
        try:
            astar_res = astar.plan_path(s_vox, g_vox, data['voxel_grid'], cost_function=None)
        except Exception:
            astar_res = None
        if astar_res is None:
            reg_path = []
        else:
            path_vox = getattr(astar_res, 'path', None)
            if path_vox is None and isinstance(astar_res, dict):
                path_vox = astar_res.get('path', [])
            reg_path = [world_from_voxel(p, grid_size, voxel_size) for p in path_vox]

    ta_path = np.asarray(ta_path)
    reg_path = np.asarray(reg_path)

    # Normalize path coordinates to world frame 0..20.
    def normalize_path(path):
        if path is None or path.size == 0:
            return path
        pts = np.array(path).astype(float)
        maxval = pts[:, :2].max()
        minval = pts[:, :2].min()
        # If coordinates are in 0..100 range (max > 20), convert to -10..10
        if maxval > 20:
            # convert 0..100 -> 0..20
            pts[:, 0] = (pts[:, 0] / 100.0) * 20.0
            pts[:, 1] = (pts[:, 1] / 100.0) * 20.0
        # If coordinates are in a large centered range (-50..50), scale to -10..10 then shift to 0..20
        elif minval < -20 and maxval > 20:
            pts[:, 0] = pts[:, 0] / 5.0 + 10.0
            pts[:, 1] = pts[:, 1] / 5.0 + 10.0
        # If coordinates are in centered small range (-10..10), shift to 0..20
        elif minval < 0 and maxval <= 20:
            pts[:, 0] = pts[:, 0] + 10.0
            pts[:, 1] = pts[:, 1] + 10.0
        return pts

    ta_path_raw = np.asarray(ta_path) if ta_path is not None else np.array([])
    reg_path_raw = np.asarray(reg_path) if reg_path is not None else np.array([])
    
    # デバッグ: 生経路の形状を確認
    if len(ta_path_raw) > 0:
        print(f"TA* raw path shape: {ta_path_raw.shape}, first point: {ta_path_raw[0]}")
    if len(reg_path_raw) > 0:
        print(f"Regular A* raw path shape: {reg_path_raw.shape}, first point: {reg_path_raw[0]}")
    
    # 標高サンプリング用に生の経路（正規化前）を保存
    ta_path_for_height = ta_path_raw.copy() if len(ta_path_raw) > 0 else np.array([])
    reg_path_for_height = reg_path_raw.copy() if len(reg_path_raw) > 0 else np.array([])
    
    ta_path = normalize_path(ta_path)
    reg_path = normalize_path(reg_path)
    
    # デバッグ: 経路データを確認
    print(f"TA* path: {len(ta_path)} points")
    if len(ta_path) > 0:
        print(f"  First point: {ta_path[0][:2]}, Last point: {ta_path[-1][:2]}")
        print(f"  X range: {ta_path[:, 0].min():.2f} - {ta_path[:, 0].max():.2f}")
        print(f"  Y range: {ta_path[:, 1].min():.2f} - {ta_path[:, 1].max():.2f}")
    print(f"Regular A* path: {len(reg_path)} points")
    if len(reg_path) > 0:
        print(f"  First point: {reg_path[0][:2]}, Last point: {reg_path[-1][:2]}")
        print(f"  X range: {reg_path[:, 0].min():.2f} - {reg_path[:, 0].max():.2f}")
        print(f"  Y range: {reg_path[:, 1].min():.2f} - {reg_path[:, 1].max():.2f}")

    # sample heights using 3D elevation data
    grid_size = tuple(meta.get('grid_size', (100, 100, 20)))
    voxel_size = float(meta.get('voxel_size', 0.2))
    
    ta_heights = sample_heights_world(ta_path_for_height, elev, grid_size, voxel_size)
    reg_heights = sample_heights_world(reg_path_for_height, elev, grid_size, voxel_size)
    
    # デバッグ: 標高サンプリング結果を確認
    if ta_heights:
        print(f"TA* heights sampled: {len(ta_heights)} points, range: {min(ta_heights):.2f} - {max(ta_heights):.2f}m")
    if reg_heights:
        print(f"Regular A* heights sampled: {len(reg_heights)} points, range: {min(reg_heights):.2f} - {max(reg_heights):.2f}m")

    # determine max indices and values
    ta_max_val = max(ta_heights) if ta_heights else None
    reg_max_val = max(reg_heights) if reg_heights else None
    ta_max_idx = int(np.argmax(ta_heights)) if ta_heights else None
    reg_max_idx = int(np.argmax(reg_heights)) if reg_heights else None

    # Plot with narrowed colormap and contours
    fig_w = 12.0 / 2.54
    fig_h = 9.0 / 2.54
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    extent = [0, 20, 0, 20]
    # Use a domain appropriate for these scenarios
    vmin, vmax = 0, 12
    im = ax.imshow(height_map.T, cmap='terrain', origin='lower', extent=extent, alpha=0.9, vmin=vmin, vmax=vmax, zorder=1)
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Height [m]')
    cbar.set_ticks(np.linspace(vmin, vmax, 7))

    # Add hillshade for relief to avoid 'pudding' appearance
    ls = LightSource(azdeg=315, altdeg=45)
    # hillshade returns 2D array in 0..1; overlay with low alpha
    try:
        hillshade = ls.hillshade(height_map.T, vert_exag=1.0)
        # show base colormap
        im = ax.imshow(height_map.T, cmap='terrain', origin='lower', extent=extent, alpha=0.95, vmin=vmin, vmax=vmax, zorder=1)
        # overlay hillshade in gray to add relief
        ax.imshow(hillshade, cmap='gray', origin='lower', extent=extent, alpha=0.35, zorder=2)
    except Exception:
        # fallback to plain image
        im = ax.imshow(height_map.T, cmap='terrain', origin='lower', extent=extent, alpha=0.95, vmin=vmin, vmax=vmax, zorder=1)

    # contours — choose levels inside 0..12
    X = np.linspace(extent[0], extent[1], height_map.shape[0])
    Y = np.linspace(extent[2], extent[3], height_map.shape[1])
    XX, YY = np.meshgrid(X, Y)
    contour_levels = [2, 4, 6, 8, 10]
    try:
        cs = ax.contour(XX, YY, height_map.T, levels=contour_levels, colors='white', linewidths=1.0, alpha=0.8, zorder=3)
        labels = ax.clabel(cs, inline=True, fontsize=8, fmt='%dm')
        # make contour labels black for readability
        try:
            for txt in labels:
                txt.set_color('black')
        except Exception:
            pass
        # emphasize hill boundary (e.g., elevation ~6m)
        hill_boundary = ax.contour(XX, YY, height_map.T, levels=[6.0], colors='saddlebrown', linewidths=2.5, zorder=4)
    except Exception:
        pass

    # plot paths
    if reg_path.size:
        ax.plot(reg_path[:, 0], reg_path[:, 1], 'r-', linewidth=4, alpha=0.95, label='Regular A* (direct path)', zorder=4)
    if ta_path.size:
        ax.plot(ta_path[:, 0], ta_path[:, 1], 'g-', linewidth=4, alpha=0.95, label='TA* (detours around terrain)', zorder=5)

    # (Removed per user request: TA*/Reg max annotations and explicit peak marker.)

    # title with 2-line format
    title_line1 = 'Hill Detour Scenario'
    title_line2 = 'TA* detours around hill  |  Regular A* crosses hill directly'
    ax.set_title(f'{title_line1}\n{title_line2}', fontsize=11, fontweight='bold', pad=12, linespacing=1.5)

    # start/goal markers: derive from available path (prefer ta, else reg), fallback to meta
    start_pt = None
    goal_pt = None
    if ta_path.size:
        start_pt = (ta_path[0, 0], ta_path[0, 1])
        goal_pt = (ta_path[-1, 0], ta_path[-1, 1])
    elif reg_path.size:
        start_pt = (reg_path[0, 0], reg_path[0, 1])
        goal_pt = (reg_path[-1, 0], reg_path[-1, 1])
    else:
        sx, sy, _ = meta['start']
        gx, gy, _ = meta['goal']
        # meta likely in centered coords (-10..10); shift to 0..20 plot frame
        start_pt = (sx + 10.0, sy + 10.0)
        goal_pt = (gx + 10.0, gy + 10.0)

    ax.plot(start_pt[0], start_pt[1], 'bo', markersize=10, label='Start', zorder=6)
    ax.plot(goal_pt[0], goal_pt[1], 'y*', markersize=16, label='Goal', zorder=6)

    # force axes origin at (0,0) and consistent plotting range
    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    ax.set_xticks(np.linspace(extent[0], extent[1], 6))
    ax.set_yticks(np.linspace(extent[2], extent[3], 6))

    ax.set_xlabel('X position [m]', fontsize=11)
    ax.set_ylabel('Y position [m]', fontsize=11)
    ax.grid(True, color='gray', alpha=0.3)
    # move legend to lower right and smaller
    ax.legend(loc='lower right', bbox_to_anchor=(0.98, 0.02), framealpha=0.85, prop={'size': 6}, markerscale=0.6, handlelength=1.2, labelspacing=0.2)
    plt.tight_layout()

    out_dir = os.path.join(base, 'figures')
    os.makedirs(out_dir, exist_ok=True)
    png = os.path.join(out_dir, 'fig4_hill_detour_ABSTRACT_v3.png')
    pdf = os.path.join(out_dir, 'fig4_hill_detour_ABSTRACT_v3.pdf')
    plt.savefig(png, dpi=300, bbox_inches='tight')
    plt.savefig(pdf, bbox_inches='tight')
    plt.close(fig)

    print('Saved:', png, pdf)
    print(f'Regular A* max height: {reg_max_val:.2f}m')
    print(f'TA* max height: {ta_max_val:.2f}m')
    print(f'Height difference: {reg_max_val - ta_max_val:.2f}m')


if __name__ == '__main__':
    main()
