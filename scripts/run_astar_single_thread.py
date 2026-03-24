#!/usr/bin/env python3
"""
Run A* on dataset3 - SINGLE THREAD VERSION
"""
import sys
from pathlib import Path
import json
import time
import numpy as np

PACKAGE_ROOT = '/home/hayashi/thesis_work/ros2/ros2_ws/src/path_planner_3d'
MODULE_DIR = '/home/hayashi/thesis_work/ros2/ros2_ws/src/path_planner_3d/path_planner_3d'
if PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, PACKAGE_ROOT)
if MODULE_DIR not in sys.path:
    sys.path.insert(0, MODULE_DIR)

from astar_3d import AStar3D

def build_voxel_grid(scenario, z_layers=8):
    """Build 3D voxel grid from scenario obstacle map"""
    obs = np.array(scenario.get('obstacle_map', np.zeros((32, 32))), dtype=np.uint8)
    h, w = obs.shape
    map_size_raw = scenario.get('map_size', max(h, w))
    size = int(max(map_size_raw)) if isinstance(map_size_raw, (list, tuple)) else int(map_size_raw)
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

def simple_cost_function(node, neighbor, voxel_grid):
    """Simple cost function: 1.0 for all transitions"""
    return 1.0

def run_astar_on_scenario(scenario, timeout=120):
    """Run A* on a single scenario"""
    sid = scenario.get('id', 'unknown')
    start_time = time.time()

    try:
        map_size_raw = scenario.get('map_size', 64)
        size = int(max(map_size_raw)) if isinstance(map_size_raw, (list, tuple)) else int(map_size_raw)
        z_layers = max(8, size // 16)
        voxel_grid = build_voxel_grid(scenario, z_layers=z_layers)

        sx, sy = scenario.get('start', (0, 0))
        gx, gy = scenario.get('goal', (0, 0))
        start_voxel = (int(sx), int(sy), 0)
        goal_voxel = (int(gx), int(gy), 0)

        planner = AStar3D(voxel_size=1.0, max_iterations=500000)
        # A*.plan_path は (start, goal, voxel_grid, cost_function) を要求
        result = planner.plan_path(start_voxel, goal_voxel, voxel_grid, simple_cost_function)

        success = bool(getattr(result, 'success', False)) if result is not None else False
        path = getattr(result, 'path', []) if result is not None else []
        path_length = _path_length_m(path) if path else 0.0
        nodes = int(getattr(result, 'nodes_explored', 0)) if result is not None else 0

        elapsed = time.time() - start_time
        return {
            'planner': 'A*',
            'scenario_id': sid,
            'environment_type': scenario.get('env'),
            'map_size': size,
            'success': bool(success),
            'computation_time': float(elapsed),
            'path_length_meters': float(path_length),
            'nodes_explored': int(nodes)
        }
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"  Error on {sid}: {e}")
        map_size_raw = scenario.get('map_size', 64)
        size_val = int(max(map_size_raw)) if isinstance(map_size_raw, (list, tuple)) else int(map_size_raw)
        return {
            'planner': 'A*',
            'scenario_id': sid,
            'environment_type': scenario.get('env'),
            'map_size': size_val,
            'success': False,
            'computation_time': float(elapsed),
            'path_length_meters': 0.0,
            'nodes_explored': 0
        }

def main():
    with open('dataset3_scenarios.json') as f:
        scenarios = json.load(f)

    print(f"Running A* on {len(scenarios)} scenarios (SINGLE THREAD)")
    print(f"Timeout: 120 seconds per task\n")

    results = []
    output_dir = Path('benchmark_results')
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / 'dataset3_astar_final_results.json'

    if output_file.exists():
        with open(output_file) as f:
            results = json.load(f)
        processed_ids = {r['scenario_id'] for r in results}
        print(f"Found {len(results)} existing results")
    else:
        processed_ids = set()

    success_count = 0
    total_start = time.time()
    
    for i, scenario in enumerate(scenarios):
        sid = scenario.get('id', 'unknown')
        
        if sid in processed_ids:
            print(f"{i+1}/{len(scenarios)} ({100.0*(i+1)/len(scenarios):.1f}%) | ✓ {sid} (cached)")
            continue
        
        result = run_astar_on_scenario(scenario, timeout=120)
        results.append(result)
        
        if result['success']:
            success_count += 1
            symbol = '✓'
        else:
            symbol = '✗'
        
        print(f"{i+1}/{len(scenarios)} ({100.0*(i+1)/len(scenarios):.1f}%) | {symbol} {sid}")
        print(f"  Time: {result['computation_time']:.2f}s | Length: {result['path_length_meters']:.2f}m | Nodes: {result['nodes_explored']}")
        
        if (i + 1) % 10 == 0 or (i + 1) == len(scenarios):
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2)
            total_elapsed = time.time() - total_start
            rate = total_elapsed / (i + 1)
            remaining = rate * (len(scenarios) - i - 1)
            print(f"  Saved {len(results)}/{len(scenarios)} results | ETA: {remaining:.0f}s\n")

    print(f"\n{'='*60}")
    print(f"A* Benchmark Complete!")
    print(f"Success rate: {success_count}/{len(scenarios)} ({100.0*success_count/len(scenarios):.1f}%)")
    print(f"Total time: {time.time() - total_start:.1f}s")
    print(f"Output: {output_file}")

if __name__ == '__main__':
    main()
