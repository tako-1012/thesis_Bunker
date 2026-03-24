#!/usr/bin/env python3
"""
Run D*Lite on dataset3 - SINGLE THREAD VERSION
"""
import sys
from pathlib import Path
import json
import time
import numpy as np
import importlib

PACKAGE_ROOT = '/home/hayashi/thesis_work/ros2/ros2_ws/src/path_planner_3d'
MODULE_DIR = '/home/hayashi/thesis_work/ros2/ros2_ws/src/path_planner_3d/path_planner_3d'
if PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, PACKAGE_ROOT)
if MODULE_DIR not in sys.path:
    sys.path.insert(0, MODULE_DIR)

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

def run_dlite_on_scenario(scenario, timeout=120):
    """Run D*Lite on a single scenario"""
    sid = scenario.get('id', 'unknown')
    start_time = time.time()

    try:
        map_size_raw = scenario.get('map_size', 64)
        size = int(max(map_size_raw)) if not isinstance(map_size_raw, (list, tuple)) else int(max(map_size_raw))
        z_layers = max(8, size // 16)
        voxel_grid = build_voxel_grid(scenario, z_layers=z_layers)
        terrain_data = {'height_map': np.array(scenario.get('height_map', np.zeros((size, size))))}

        sx, sy = scenario.get('start', (0, 0))
        gx, gy = scenario.get('goal', (0, 0))
        start = (float(sx), float(sy), 0.0)
        goal = (float(gx), float(gy), 0.0)

        # D*Lite uses importlib to avoid import issues
        mod = importlib.import_module('path_planner_3d.dstar_lite_3d')
        DStarClass = getattr(mod, 'DStarLite3D')
        planner = DStarClass(voxel_size=1.0, grid_size=(size, size, z_layers))
        planner.set_terrain_data(voxel_grid, terrain_data)
        result = planner.plan_path(start, goal)

        stats = getattr(planner, 'last_search_stats', {})
        success = bool(getattr(result, 'success', False)) if result is not None else False
        path_length = 0.0
        if result is not None:
            path_length = float(getattr(result, 'path_length', stats.get('path_length', 0.0)))
        nodes = int(getattr(result, 'nodes_explored', stats.get('nodes_explored', 0))) if result is not None else int(stats.get('nodes_explored', 0))

        elapsed = time.time() - start_time
        return {
            'planner': 'D*Lite',
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
            'planner': 'D*Lite',
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

    print(f"Running D*Lite on {len(scenarios)} scenarios (SINGLE THREAD)")
    print(f"Timeout: 120 seconds per task\n")

    results = []
    output_dir = Path('benchmark_results')
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / 'dataset3_dlite_final_results.json'

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
        
        result = run_dlite_on_scenario(scenario, timeout=120)
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
    print(f"D*Lite Benchmark Complete!")
    print(f"Success rate: {success_count}/{len(scenarios)} ({100.0*success_count/len(scenarios):.1f}%)")
    print(f"Total time: {time.time() - total_start:.1f}s")
    print(f"Output: {output_file}")

if __name__ == '__main__':
    main()
