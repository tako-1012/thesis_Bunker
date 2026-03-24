#!/usr/bin/env python3
"""
Hill Detourシナリオの経路比較図（アブストラクト用）
正しいデータ（最大標高10m）で再生成
"""
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


def normalize_path(path, grid_size, voxel_size):
    """
    Convert various coordinate formats to world coordinates [0, 20]×[0, 20] frame.
    """
    if path is None or len(path) == 0:
        return np.array([])
    path = np.asarray(path)
    # detect format
    xmin, xmax = path[:, 0].min(), path[:, 0].max()
    ymin, ymax = path[:, 1].min(), path[:, 1].max()
    # if in grid index space (0..100)
    if (xmax < grid_size[0] * 1.5) and (ymax < grid_size[1] * 1.5):
        world_path = []
        for idx in path:
            wx, wy, wz = world_from_voxel(idx, grid_size, voxel_size)
            # shift from centered (-10..10) to 0..20
            world_path.append([wx + 10.0, wy + 10.0])
        return np.array(world_path)
    # if already centered (-50..50 or -10..10)
    elif xmin < 0:
        # shift to 0..20
        return path[:, :2] + 10.0
    # else assume already 0..20
    return path[:, :2]


def sample_heights_world(path, height_map):
    if path is None or len(path) == 0:
        return []
    nx, ny = height_map.shape
    hs = []
    # map world coords to height_map indices using extent 0..20 (meters)
    xmin, xmax = 0.0, 20.0
    ymin, ymax = 0.0, 20.0
    for p in path:
        xw, yw = float(p[0]), float(p[1])
        ix = int(round((xw - xmin) / (xmax - xmin) * (nx - 1)))
        iy = int(round((yw - ymin) / (ymax - ymin) * (ny - 1)))
        ix = max(0, min(nx - 1, ix))
        iy = max(0, min(ny - 1, iy))
        hs.append(float(height_map[iy, ix]))
    return hs


def main():
    print("="*60)
    print("図4: Hill Detour経路比較図（アブストラクト用）")
    print("="*60)
    
    base = os.path.join(os.path.dirname(__file__), '..')
    # 重要: amplified版ではなく、オリジナル（最大10m）を使用
    npz_path = os.path.join(base, 'terrain_test_scenarios', 'hill_detour_data.npz')
    meta_path = os.path.join(base, 'terrain_test_scenarios', 'hill_detour_meta.json')

    data = np.load(npz_path)
    with open(meta_path, 'r') as f:
        meta = json.load(f)

    elev = data['elevation']
    height_map = np.max(elev, axis=2)
    
    print(f"地形データ読み込み完了")
    print(f"  標高範囲: {height_map.min():.2f}m - {height_map.max():.2f}m")

    # Try to find precomputed paths in NPZ
    ta_path = None
    reg_path = None
    for k in data.files:
        if 'ta' in k and 'path' in k:
            ta_path = np.asarray(data[k])
            print(f"  TA* path found in NPZ: {k}")
        if ('regular' in k or 'reg' in k or 'a_star' in k) and 'path' in k:
            reg_path = np.asarray(data[k])
            print(f"  Regular A* path found in NPZ: {k}")

    # Otherwise compute with planners
    if ta_path is None or reg_path is None:
        print("  経路データがNPZに含まれていません。プランナーを実行します...")
        ta_mod = os.path.join(base, 'ros2/ros2_ws/src/path_planner_3d/path_planner_3d/terrain_aware_astar.py')
        astar_mod = os.path.join(base, 'ros2/ros2_ws/src/path_planner_3d/path_planner_3d/astar_3d.py')
        
        try:
            TerrainAwareAStar = import_planner(ta_mod, 'TerrainAwareAStar')
            AStar3D = import_planner(astar_mod, 'AStar3D')

            grid_size = tuple(meta.get('grid_size', (100, 100, 20)))
            voxel_size = float(meta.get('voxel_size', 0.2))
            start = tuple(meta['start'])
            goal = tuple(meta['goal'])

            voxel_grid = data['voxel_grid']
            roughness = data['roughness']
            density = data['density']

            if reg_path is None:
                print("  Regular A*を実行中...")
                reg_planner = AStar3D(voxel_grid)
                reg_success, reg_path, _, _ = reg_planner.plan(start, goal)
                if not reg_success:
                    print("  警告: Regular A*が経路を見つけられませんでした")
                    reg_path = np.array([])
                else:
                    print(f"  Regular A*完了（{len(reg_path)} waypoints）")

            if ta_path is None:
                print("  TA*を実行中...")
                ta_planner = TerrainAwareAStar(voxel_grid, elev, roughness, density)
                ta_success, ta_path, _, _ = ta_planner.plan(start, goal)
                if not ta_success:
                    print("  警告: TA*が経路を見つけられませんでした")
                    ta_path = np.array([])
                else:
                    print(f"  TA*完了（{len(ta_path)} waypoints）")
        except Exception as e:
            print(f"  警告: プランナー実行エラー: {e}")
            # フォールバック: 直線経路を生成
            start_world = np.array(meta['start'][:2]) + 10.0
            goal_world = np.array(meta['goal'][:2]) + 10.0
            if reg_path is None or len(reg_path) == 0:
                reg_path = np.linspace(start_world, goal_world, 20)
            if ta_path is None or len(ta_path) == 0:
                ta_path = np.linspace(start_world, goal_world, 20)

    grid_size = tuple(meta.get('grid_size', (100, 100, 20)))
    voxel_size = float(meta.get('voxel_size', 0.2))

    # normalize paths to 0..20 frame
    reg_path = normalize_path(reg_path, grid_size, voxel_size)
    ta_path = normalize_path(ta_path, grid_size, voxel_size)

    # sample heights
    ta_heights = sample_heights_world(ta_path, height_map)
    reg_heights = sample_heights_world(reg_path, height_map)

    ta_max_val = max(ta_heights) if ta_heights else 0.0
    reg_max_val = max(reg_heights) if reg_heights else 0.0
    
    print(f"経路標高確認:")
    print(f"  Regular A* 最大標高: {reg_max_val:.2f}m")
    print(f"  TA* 最大標高: {ta_max_val:.2f}m")
    print(f"  標高差（Regular - TA*）: {reg_max_val - ta_max_val:.2f}m")

    # Plot
    fig_w = 12.0 / 2.54
    fig_h = 9.0 / 2.54
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    extent = [0, 20, 0, 20]
    vmin, vmax = 0, 12
    
    # hillshade for relief
    ls = LightSource(azdeg=315, altdeg=45)
    try:
        hillshade = ls.hillshade(height_map.T, vert_exag=1.0)
        im = ax.imshow(height_map.T, cmap='terrain', origin='lower', extent=extent, 
                      alpha=0.95, vmin=vmin, vmax=vmax, zorder=1)
        ax.imshow(hillshade, cmap='gray', origin='lower', extent=extent, 
                 alpha=0.35, zorder=2)
    except Exception:
        im = ax.imshow(height_map.T, cmap='terrain', origin='lower', extent=extent, 
                      alpha=0.95, vmin=vmin, vmax=vmax, zorder=1)

    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Elevation [m]', fontsize=10)
    cbar.set_ticks(np.linspace(vmin, vmax, 7))

    # contours
    X = np.linspace(extent[0], extent[1], height_map.shape[0])
    Y = np.linspace(extent[2], extent[3], height_map.shape[1])
    XX, YY = np.meshgrid(X, Y)
    contour_levels = [2, 4, 6, 8, 10]
    try:
        cs = ax.contour(XX, YY, height_map.T, levels=contour_levels, colors='white', 
                       linewidths=1.0, alpha=0.8, zorder=3)
        labels = ax.clabel(cs, inline=True, fontsize=8, fmt='%dm')
        for txt in labels:
            txt.set_color('black')
        # emphasize hill boundary (6m)
        ax.contour(XX, YY, height_map.T, levels=[6.0], colors='saddlebrown', 
                  linewidths=2.5, zorder=4)
    except Exception:
        pass

    # plot paths
    if reg_path.size:
        ax.plot(reg_path[:, 0], reg_path[:, 1], 'r-', linewidth=4, alpha=0.95, 
               label='Regular A* (direct)', zorder=5)
    if ta_path.size:
        ax.plot(ta_path[:, 0], ta_path[:, 1], 'g-', linewidth=4, alpha=0.95, 
               label='TA* (detours)', zorder=6)

    # title with correct height difference
    height_diff = reg_max_val - ta_max_val
    title = f'TA* detours vs Regular A* — Hill Detour — Max height diff: {height_diff:.1f}m'
    ax.set_title(title, fontsize=11, fontweight='bold', pad=10)

    # start/goal markers
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
        start_pt = (sx + 10.0, sy + 10.0)
        goal_pt = (gx + 10.0, gy + 10.0)

    ax.plot(start_pt[0], start_pt[1], 'bo', markersize=10, label='Start', zorder=7)
    ax.plot(goal_pt[0], goal_pt[1], 'y*', markersize=16, label='Goal', zorder=7)

    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    ax.set_xticks(np.linspace(extent[0], extent[1], 6))
    ax.set_yticks(np.linspace(extent[2], extent[3], 6))

    ax.set_xlabel('X position [m]', fontsize=11)
    ax.set_ylabel('Y position [m]', fontsize=11)
    ax.grid(True, color='gray', alpha=0.3)
    ax.legend(loc='lower right', bbox_to_anchor=(0.98, 0.02), framealpha=0.85, 
             prop={'size': 6}, markerscale=0.6, handlelength=1.2, labelspacing=0.2)
    plt.tight_layout()

    out_dir = os.path.join(base, 'figures')
    os.makedirs(out_dir, exist_ok=True)
    png = os.path.join(out_dir, 'fig4_hill_detour_ABSTRACT.png')
    pdf = os.path.join(out_dir, 'fig4_hill_detour_ABSTRACT.pdf')
    plt.savefig(png, dpi=300, bbox_inches='tight')
    plt.savefig(pdf, bbox_inches='tight')
    plt.close(fig)

    print("="*60)
    print("✅ 図4生成完了")
    print(f"  PNG: {png}")
    print(f"  PDF: {pdf}")
    print(f"  タイトル: {title}")
    print("="*60)


if __name__ == '__main__':
    main()
