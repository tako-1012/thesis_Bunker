import time
import json
import numpy as np
import os

# Try importing planner from package or local module
try:
    from path_planner_3d.adaptive_hybrid_astar_3d import AdaptiveHybridAStar3D
except Exception:
    try:
        from adaptive_hybrid_astar_3d import AdaptiveHybridAStar3D
    except Exception as e:
        print("Failed to import AdaptiveHybridAStar3D:", e)
        raise


class AHADebugger:
    """AHA*の詳細ログを取得するデバッグラッパー"""
    def __init__(self, scenario):
        self.scenario = scenario

    def run_with_detailed_logs(self):
        print("\n" + "="*80)
        sid = self.scenario.get('id', 'unknown')
        print(f"Scenario: {sid}")
        print("Environment:", self.scenario.get('environment_type', 'Unknown'))
        print("="*80 + "\n")

        # Use world-origin min_bound=(0,0,0) to match scenario coordinate convention
        planner = AdaptiveHybridAStar3D(
            voxel_size=self.scenario.get('voxel_size', 1.0),
            grid_size=tuple(self.scenario.get('grid_size', (64, 64, 8))),
            min_bound=(0.0, 0.0, 0.0)
        )

        # Enforce origin-aligned min_bound to match scenario coordinates
        try:
            import numpy as _np
            planner.min_bound = _np.array((0.0, 0.0, 0.0))
            planner.voxel_size = self.scenario.get('voxel_size', 1.0)
        except Exception:
            pass

        # If scenario includes voxel_grid/terrain, set it
        if 'voxel_grid' in self.scenario and 'terrain_data' in self.scenario:
            try:
                planner.set_terrain_data(self.scenario['voxel_grid'], self.scenario['terrain_data'])
            except Exception:
                pass

        print("=== 基本情報 ===")
        try:
            grid_dims = getattr(planner, 'grid_size', None)
            print(f"Grid dimensions: {grid_dims}")
            raw_start = self.scenario.get('start')
            raw_goal = self.scenario.get('goal')
            # Ensure 3D tuples (pad z=0 if missing)
            def pad3(v):
                if v is None:
                    return (0, 0, 0)
                if len(v) == 2:
                    return (v[0], v[1], 0)
                return tuple(v)

            start_world = pad3(raw_start)
            goal_world = pad3(raw_goal)

            print(f"Start (world): {start_world}")
            print(f"Goal (world): {goal_world}")
            start_grid = planner._world_to_voxel(start_world)
            goal_grid = planner._world_to_voxel(goal_world)
            print(f"Start (grid): {start_grid}")
            print(f"Goal (grid): {goal_grid}")
        except Exception as e:
            print("Error computing grid indices:", e)

        dist = np.linalg.norm(np.array(self.scenario.get('start')) - np.array(self.scenario.get('goal')))
        print(f"Euclidean distance: {dist:.2f}m")

        print("\n=== パラメータ ===")
        print(f"Max iterations: {getattr(planner, 'max_iterations', None)}")
        print(f"Initial epsilon: {getattr(planner, 'initial_epsilon', None)}")
        print(f"Heuristic weight: {getattr(planner, 'refinement_epsilon', None)}")
        print(f"Goal bias: {getattr(planner, 'goal_bias', None)}")
        print(f"Max samples: {getattr(planner, 'max_samples', None)}")

        # Monkeypatch _adaptive_hybrid_search to add phase headers (keeps original behavior)
        if hasattr(planner, '_adaptive_hybrid_search'):
            original_search = planner._adaptive_hybrid_search

            def logged_search(start, goal, terrain_complexity=None):
                print('\n=== 探索開始 ===')
                print('\nPhase 1: INITIAL_EXPLORATION (headers only)')
                print('\nPhase 2: REFINEMENT (headers only)')
                print('\nPhase 3: OPTIMIZATION (headers only)')
                if terrain_complexity is None:
                    # compute a default
                    try:
                        terrain_complexity = planner._analyze_terrain_complexity(start, goal)
                    except Exception:
                        terrain_complexity = 0.3
                return original_search(start, goal, terrain_complexity)

            planner._adaptive_hybrid_search = logged_search

        # Run planning
        start_time = time.time()
        try:
            # use padded coordinates for planning
            result_path = planner.plan_path(start_world, goal_world)
            elapsed = time.time() - start_time

            print('\n=== 結果 ===')
            success = result_path is not None
            print(f"Success: {success}")
            print(f"Elapsed: {elapsed:.3f}s")
            if success:
                print(f"Path length (nodes): {len(result_path)}")
            stats = planner.get_search_stats() if hasattr(planner, 'get_search_stats') else {}
            print(f"Nodes explored: {stats.get('nodes_explored', 'N/A')}")
            if not success:
                print('\n⚠️ 失敗理由:')
                # try to surface reason from last_search_stats or planner
                print(f" last_search_stats: {stats}")
        except Exception as e:
            print('Planning raised exception:', e)

        return None


if __name__ == '__main__':
    # Load scenarios
    scen_path = os.path.join(os.getcwd(), 'dataset2_scenarios.json')
    if not os.path.exists(scen_path):
        print('dataset2_scenarios.json not found in cwd:', os.getcwd())
        raise SystemExit(1)

    with open(scen_path, 'r') as f:
        scenarios = json.load(f)

    # scenarios may be list or dict
    if isinstance(scenarios, dict):
        scen_list = list(scenarios.values())
    else:
        scen_list = scenarios

    # Select indices that correspond to previously failing examples (safe-guard bounds)
    targets = []
    for idx in [48, 96]:
        if idx < len(scen_list):
            s = scen_list[idx]
            # Ensure each scenario has an id
            if 'id' not in s:
                s['id'] = f'idx_{idx}'
            targets.append(s)

    for s in targets:
        dbg = AHADebugger(s)
        dbg.run_with_detailed_logs()
        print('\n' + '='*80 + '\n')
