#!/usr/bin/env python3
"""
Re-run Regular A* benchmark only (fix import error)
"""
import sys
from pathlib import Path
import json
import time
import multiprocessing as mp
import numpy as np

PACKAGE_ROOT = '/home/hayashi/thesis_work/ros2/ros2_ws/src/path_planner_3d'
MODULE_DIR = '/home/hayashi/thesis_work/ros2/ros2_ws/src/path_planner_3d/path_planner_3d'
if PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, PACKAGE_ROOT)
if MODULE_DIR not in sys.path:
    sys.path.insert(0, MODULE_DIR)

# Use AStar3D (integer voxels) with a high iteration cap
from astar_3d import AStar3D


def build_voxel_grid(scenario, z_layers=8):
    """Build 3D voxel grid from scenario obstacle map"""
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


def _path_length_m(path):
    """Compute total Euclidean length of a voxel path (voxel_size=1.0)."""
    if not path or len(path) < 2:
        return 0.0
    length = 0.0
    for i in range(len(path) - 1):
        p1 = np.array(path[i], dtype=float)
        p2 = np.array(path[i + 1], dtype=float)
        length += float(np.linalg.norm(p2 - p1))
    return length


def run_astar_on_scenario(args):
    """Run Regular A* (AStar3D) on a single scenario"""
    scenario, timeout = args
    sid = scenario.get('id', 'unknown')
    start_time = time.time()
    
    try:
        map_size_raw = scenario.get('map_size', 64)
        size = int(max(map_size_raw)) if not isinstance(map_size_raw, (list, tuple)) else int(max(map_size_raw))
        z_layers = max(8, size // 16)
        voxel_grid = build_voxel_grid(scenario, z_layers=z_layers)

        sx, sy = scenario.get('start', (0, 0))
        gx, gy = scenario.get('goal', (0, 0))
        start = (float(sx), float(sy), 0.0)
        goal = (float(gx), float(gy), 0.0)

        planner = AStar3D(voxel_size=1.0, max_iterations=500_000)

        # AStar3D expects integer voxel coordinates; keep terrain cost flat (cost_function=1)
        path = planner.plan_path(
            (int(round(start[0])), int(round(start[1])), 0),
            (int(round(goal[0])), int(round(goal[1])), 0),
            voxel_grid,
            cost_function=lambda *_: 1.0,
        )

        success = path is not None
        plen = _path_length_m(path) if path else 0.0
        nodes = planner.nodes_explored  # 実際の探索ノード数を記録

        elapsed = time.time() - start_time
        return {
            'planner': 'A*',
            'scenario_id': sid,
            'environment_type': scenario.get('env'),
            'map_size': size,
            'success': bool(success),
            'computation_time': float(elapsed),
            'path_length_meters': float(plen),
            'nodes_explored': int(nodes)
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
            'error_detail': traceback.format_exc()
        }


def main():
    # Load scenarios
    with open('dataset3_scenarios.json', 'r') as f:
        all_scenarios = json.load(f)

    tasks = [(s, 120) for s in all_scenarios]

    outdir = Path('benchmark_results')
    results = []
    save_path = outdir / 'dataset3_correct_astar_results.json'

    pool_procs = min(8, mp.cpu_count())
    start_time = time.time()
    
    print(f"Re-running A* on {len(all_scenarios)} scenarios")
    print(f"Using {pool_procs} CPU cores")
    print(f"Timeout: 120 seconds per task\n")
    
    with mp.Pool(processes=pool_procs) as pool:
        for i, r in enumerate(pool.imap_unordered(run_astar_on_scenario, tasks, chunksize=1)):
            results.append(r)
            if (i+1) % 10 == 0:
                with open(save_path, 'w') as f:
                    json.dump(results, f, indent=2)
                print(f"Saved {i+1}/{len(tasks)} results")
                elapsed = time.time() - start_time
                progress = (i+1) / len(tasks)
                eta = (elapsed / progress - elapsed) if progress>0 else 0
                status = '✓' if r.get('success') else '✗'
                print(f'{i+1:3d}/90 ({progress*100:5.1f}%) | {status} {r.get("scenario_id"):20s} | '
                      f'Time: {r.get("computation_time", 0):6.2f}s | ETA: {eta:5.0f}s')

    # Final save
    with open(save_path, 'w') as f:
        json.dump(results, f, indent=2)

    # Summary
    success_count = sum(1 for r in results if r.get('success'))
    avg_time = sum(r.get('computation_time', 0) for r in results if r.get('success')) / success_count if success_count else 0
    avg_path = sum(r.get('path_length_meters', 0) for r in results if r.get('success')) / success_count if success_count else 0

    print(f'\n{"="*60}')
    print(f'A* Benchmark Complete!')
    print(f'{"="*60}')
    print(f'Success: {success_count}/90 ({success_count/90*100:.1f}%)')
    print(f'Avg Time: {avg_time:.4f}s')
    print(f'Avg Path: {avg_path:.2f}m')
    print(f'\nResults saved: {save_path}')


if __name__ == '__main__':
    main()
