#!/usr/bin/env python3
"""
Benchmark Dataset3 with correct Regular A* (AStar3D)
- Pure A* (no terrain cost)
- Uses astar_3d.AStar3D directly
- Outputs: benchmark_results/dataset3_correct_astar_results.json
"""
import sys
import json
import time
from pathlib import Path
import numpy as np

# Ensure path_planner_3d is importable
PACKAGE_ROOT = '/home/hayashi/thesis_work/ros2/ros2_ws/src/path_planner_3d'
MODULE_DIR = '/home/hayashi/thesis_work/ros2/ros2_ws/src/path_planner_3d/path_planner_3d'
for p in (PACKAGE_ROOT, MODULE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from astar_3d import AStar3D


def build_voxel_grid(scenario, z_layers=8):
    """Build 3D voxel grid from 2D obstacle map."""
    obs = np.array(scenario.get('obstacle_map', np.zeros((32, 32))), dtype=np.uint8)
    h, w = obs.shape
    map_size_raw = scenario.get('map_size', max(h, w))
    size = int(max(map_size_raw)) if not isinstance(map_size_raw, (list, tuple)) else int(max(map_size_raw))
    vg = np.zeros((size, size, z_layers), dtype=np.float32)
    for z in range(z_layers):
        try:
            vg[:, :, z] = obs.T
        except Exception:
            pass
    return vg


def clamp_int(v, lo, hi):
    return max(lo, min(int(round(v)), hi))


def path_length_from_voxels(path, voxel_size):
    if not path or len(path) < 2:
        return 0.0
    total = 0.0
    for a, b in zip(path[:-1], path[1:]):
        dx = b[0] - a[0]
        dy = b[1] - a[1]
        dz = b[2] - a[2]
        total += (dx * dx + dy * dy + dz * dz) ** 0.5
    return total * voxel_size


def run_astar_on_scenario(scenario, timeout_s=120):
    sid = scenario.get('id', 'unknown')
    start_time = time.time()
    try:
        map_size_raw = scenario.get('map_size', 64)
        size = int(max(map_size_raw)) if not isinstance(map_size_raw, (list, tuple)) else int(max(map_size_raw))
        z_layers = max(8, size // 16)
        voxel_grid = build_voxel_grid(scenario, z_layers=z_layers)

        sx, sy = scenario.get('start', (0, 0))
        gx, gy = scenario.get('goal', (0, 0))
        start_voxel = (
            clamp_int(sx, 0, voxel_grid.shape[0] - 1),
            clamp_int(sy, 0, voxel_grid.shape[1] - 1),
            0,
        )
        goal_voxel = (
            clamp_int(gx, 0, voxel_grid.shape[0] - 1),
            clamp_int(gy, 0, voxel_grid.shape[1] - 1),
            0,
        )

        planner = AStar3D(voxel_size=1.0, max_iterations=200000)

        def simple_cost(_from, _to):
            dx = _to[0] - _from[0]
            dy = _to[1] - _from[1]
            dz = _to[2] - _from[2]
            return (dx * dx + dy * dy + dz * dz) ** 0.5

        path = planner.plan_path(start_voxel, goal_voxel, voxel_grid, simple_cost)
        success = path is not None
        path_len = path_length_from_voxels(path, planner.voxel_size) if success else 0.0
        nodes = len(path) if success else 0
        elapsed = time.time() - start_time

        return {
            'planner': 'A*',
            'scenario_id': sid,
            'environment_type': scenario.get('env'),
            'map_size': size,
            'success': success,
            'computation_time': float(elapsed),
            'path_length_meters': float(path_len),
            'nodes_explored': int(nodes),
        }

    except Exception as e:
        import traceback
        elapsed = time.time() - start_time
        return {
            'planner': 'A*',
            'scenario_id': sid,
            'success': False,
            'computation_time': float(elapsed),
            'error': str(e),
            'error_detail': traceback.format_exc(),
        }


def main():
    with open('dataset3_scenarios.json', 'r') as f:
        scenarios = json.load(f)

    outdir = Path('benchmark_results')
    outdir.mkdir(exist_ok=True)
    save_path = outdir / 'dataset3_correct_astar_results.json'

    results = []
    start_time = time.time()

    print(f"Running A* (AStar3D) on {len(scenarios)} scenarios")
    for i, scenario in enumerate(scenarios, 1):
        res = run_astar_on_scenario(scenario, timeout_s=120)
        results.append(res)
        if i % 10 == 0 or i == len(scenarios):
            with open(save_path, 'w') as f:
                json.dump(results, f, indent=2)
            elapsed = time.time() - start_time
            progress = i / len(scenarios)
            eta = (elapsed / progress - elapsed) if progress > 0 else 0
            status = '✓' if res.get('success') else '✗'
            print(f"{i:3d}/{len(scenarios)} ({progress*100:5.1f}%) | {status} {res.get('scenario_id','')} | Time {res.get('computation_time',0):.2f}s | ETA {eta:5.1f}s")

    # Final save
    with open(save_path, 'w') as f:
        json.dump(results, f, indent=2)

    succ = sum(1 for r in results if r.get('success'))
    avg_time = sum(r.get('computation_time', 0) for r in results if r.get('success')) / succ if succ else 0.0
    avg_path = sum(r.get('path_length_meters', 0) for r in results if r.get('success')) / succ if succ else 0.0
    print('\n' + '='*70)
    print('A* Benchmark Complete (AStar3D)')
    print('='*70)
    print(f'Success: {succ}/{len(scenarios)} ({succ/len(scenarios)*100:.1f}%)')
    print(f'Avg Time: {avg_time:.4f}s')
    print(f'Avg Path: {avg_path:.2f}m')
    print(f'Results saved: {save_path}')


if __name__ == '__main__':
    main()
