import json
import time
import sys
from pathlib import Path
PACKAGE_ROOT = '/home/hayashi/thesis_work/ros2/ros2_ws/src/path_planner_3d'
MODULE_DIR = '/home/hayashi/thesis_work/ros2/ros2_ws/src/path_planner_3d/path_planner_3d'
if PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, PACKAGE_ROOT)
if MODULE_DIR not in sys.path:
    sys.path.insert(0, MODULE_DIR)
import importlib
mod = importlib.import_module('path_planner_3d.adaptive_hybrid_astar_3d')
AdaptiveHybridAStar3D = getattr(mod, 'AdaptiveHybridAStar3D')
from adjusted_aha_params import ADJUSTED_PARAMS_V1, ADJUSTED_PARAMS_V2, ADJUSTED_PARAMS_V3


def safe_result_dict(result):
    if isinstance(result, dict):
        return result
    # fallback: try attribute access
    out = {}
    for key in ['success', 'nodes_explored', 'path', 'message']:
        out[key] = getattr(result, key, None)
    return out


def main():
    with open('dataset2_scenarios.json', 'r') as f:
        scenarios = json.load(f)

    test_scenarios = [
        scenarios[48],  # dense
        scenarios[96],  # complex
    ]

    param_sets = [
        ('V1_suppress', ADJUSTED_PARAMS_V1),
        ('V2_careful', ADJUSTED_PARAMS_V2),
        ('V3_greedy', ADJUSTED_PARAMS_V3),
    ]

    results = []

    for param_name, params in param_sets:
        print(f"\n{'='*60}")
        print(f"Testing: {param_name}")
        print(f"{'='*60}\n")

        for scenario in test_scenarios:
            sid = scenario.get('id', 'unknown')
            print(f"\nScenario: {sid}")

            # build voxel grid similar to dry_run_test expectations
            import numpy as _np
            obs = _np.array(scenario.get('obstacle_map', _np.zeros((32,32))), dtype=_np.uint8)
            size = int(scenario.get('map_size', max(obs.shape)))
            z_layers = max(8, size // 16)
            vg = _np.zeros((size, size, z_layers), dtype=_np.float32)
            # attempt to fill vg from obstacle_map (transpose to match indexing)
            try:
                h, w = obs.shape
                for z in range(z_layers):
                    vg[:, :, z] = obs.T
            except Exception:
                pass

            terrain_data = {'height_map': _np.array(scenario.get('height_map', obs.tolist()))}

            planner = AdaptiveHybridAStar3D(
                point_cloud=None,
                resolution=1.0,
                grid_size=(size, size, vg.shape[2]),
                min_bound=(0.0, 0.0, 0.0),
                **params
            )
            planner.set_terrain_data(vg, terrain_data)

            start_time = time.time()
            try:
                sx, sy = scenario.get('start', (0,0))
                gx, gy = scenario.get('goal', (0,0))
                start = (float(sx), float(sy), 0.0)
                goal = (float(gx), float(gy), 0.0)
                result = planner.plan_path(start=start, goal=goal)
            except Exception as e:
                elapsed = time.time() - start_time
                print(f"  Exception: {e}")
                results.append({
                    'param_set': param_name,
                    'scenario': sid,
                    'success': False,
                    'time': elapsed,
                    'nodes': 0,
                    'error': str(e)
                })
                continue

            elapsed = time.time() - start_time
            r = safe_result_dict(result)
            success = bool(r.get('success', False))
            nodes = r.get('nodes_explored', r.get('nodes', 0) or 0)

            print(f"  Success: {success}")
            print(f"  Time: {elapsed:.3f}s")
            print(f"  Nodes: {nodes}")

            results.append({
                'param_set': param_name,
                'scenario': sid,
                'success': success,
                'time': elapsed,
                'nodes': nodes
            })

            if elapsed > 30:
                print(f"  ⚠️ Too slow (>{elapsed:.1f}s)")

    with open('aha_param_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print('\nSaved results to aha_param_test_results.json')


if __name__ == '__main__':
    main()
