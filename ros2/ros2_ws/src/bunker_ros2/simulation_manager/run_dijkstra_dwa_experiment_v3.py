#!/usr/bin/env python3

"""Dijkstra + DWA 実験ランナー（代表シナリオ自動選択・v3）

v2 からの改良点:
 - `RepresentativeTerrainGenerator` をパスから直接ロードしてパッケージ依存を回避
"""
import json
import time
import sys
import os
from pathlib import Path
from typing import Dict, Any, List

import numpy as np


def load_module_from_path(mod_name: str, path: str):
    import importlib.machinery, importlib.util
    loader = importlib.machinery.SourceFileLoader(mod_name, path)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def load_path_planner_modules(base_pkg_dir: str = 'ros2/ros2_ws/src/path_planner_3d/path_planner_3d'):
    import importlib.machinery, importlib.util, types

    base_dir = os.path.abspath(base_pkg_dir)
    pkg_name = 'path_planner_3d'
    pkg = types.ModuleType(pkg_name)
    pkg.__path__ = [base_dir]
    sys.modules[pkg_name] = pkg

    def _load(mod_name: str, filename: str):
        full_name = f"{pkg_name}.{mod_name}"
        path = os.path.join(base_dir, filename)
        loader = importlib.machinery.SourceFileLoader(full_name, path)
        spec = importlib.util.spec_from_loader(loader.name, loader)
        mod = importlib.util.module_from_spec(spec)
        mod.__package__ = pkg_name
        loader.exec_module(mod)
        sys.modules[full_name] = mod
        return mod

    _ = _load('planning_result', 'planning_result.py')
    _ = _load('dijkstra_planner_3d', 'dijkstra_planner_3d.py')
    _ = _load('simple_dwa_planner', 'simple_dwa_planner.py')
    dd_mod = _load('dijkstra_dwa_planner', 'dijkstra_dwa_planner.py')
    return dd_mod.DijkstraDWAPlanner


def load_benchmark_scenarios(scenarios_path: str = 'scenarios/benchmark_scenarios.json') -> List[Dict[str, Any]]:
    p = Path(scenarios_path)
    if not p.exists():
        raise FileNotFoundError(f"Scenarios file not found: {p}")
    with open(p, 'r') as f:
        scenarios = json.load(f)
    return scenarios


def make_terrain_for_scenario(terrain_type: str, difficulty: str, map_size_m: float = 50.0):
    """軽量版地形生成（numpy のみ）。RepresentativeTerrainGenerator の簡易置き換え。

    戻り値: オブジェクト with attributes `size` and `obstacle_map`（最低限 SimpleDWA が必要とする形）
    """
    grid_resolution = 0.5
    grid_size = max(3, int(map_size_m / grid_resolution))

    class TM:
        pass

    tm = TM()
    tm.size = map_size_m
    # height_map not required by DWA prototype, but keep placeholder
    height_map = np.zeros((grid_size, grid_size))

    terrain_type_lower = (terrain_type or '').lower()

    if 'flat' in terrain_type_lower:
        obstacle_map = np.zeros((grid_size, grid_size), dtype=bool)
    elif 'slope' in terrain_type_lower or 'gentle' in terrain_type_lower:
        obstacle_map = np.zeros((grid_size, grid_size), dtype=bool)
        # sprinkle a few sparse obstacles for medium/hard
        if difficulty in ('medium', 'hard'):
            num_obs = max(1, grid_size // 10)
            rng = np.random.default_rng(42)
            xs = rng.integers(0, grid_size, size=num_obs)
            ys = rng.integers(0, grid_size, size=num_obs)
            obstacle_map[xs, ys] = True
    elif 'complex' in terrain_type_lower or 'obstacle' in terrain_type_lower:
        obstacle_map = np.zeros((grid_size, grid_size), dtype=bool)
        rng = np.random.default_rng(43)
        # place block obstacles
        for _ in range(max(5, grid_size // 6)):
            x = rng.integers(0, grid_size - 3)
            y = rng.integers(0, grid_size - 3)
            obstacle_map[x:x+3, y:y+3] = True
        # random debris
        debris = rng.integers(0, grid_size*grid_size, size=max(10, grid_size))
        obstacle_map.flat[debris] = True
    elif 'extreme' in terrain_type_lower or 'hazard' in terrain_type_lower:
        obstacle_map = np.zeros((grid_size, grid_size), dtype=bool)
        rng = np.random.default_rng(44)
        for _ in range(max(10, grid_size // 4)):
            x = rng.integers(0, grid_size)
            y = rng.integers(0, grid_size)
            obstacle_map[x, y] = True
    else:
        obstacle_map = np.zeros((grid_size, grid_size), dtype=bool)

    tm.height_map = height_map
    tm.obstacle_map = obstacle_map
    tm.terrain_type = terrain_type or 'flat'
    tm.max_slope = 5.0
    return tm


def pick_representative(scenarios: List[Dict[str, Any]]):
    small = next((s for s in scenarios if s.get('difficulty') == 'easy'), None)
    medium = next((s for s in scenarios if s.get('difficulty') == 'medium'), None)
    large = next((s for s in scenarios if s.get('difficulty') in ('hard', 'very_hard')), None)

    if small is None and scenarios:
        small = scenarios[0]
    if medium is None and len(scenarios) > 1:
        medium = scenarios[1]
    if large is None and len(scenarios) > 2:
        large = scenarios[2]

    chosen = []
    if small: chosen.append(('small', small))
    if medium: chosen.append(('medium', medium))
    if large: chosen.append(('large', large))
    return chosen


def run_representative(timeout_small: int = 60, timeout_medium: int = 120, timeout_large: int = 180):
    DijkstraDWAPlanner = load_path_planner_modules()

    planner = DijkstraDWAPlanner(config={'dwa': {'max_velocity': 1.0, 'max_angular_velocity': 1.0,
                                                'max_accel': 0.5, 'max_angular_accel': 0.5,
                                                'velocity_samples': 8, 'angular_samples': 8}})

    scenarios = load_benchmark_scenarios()
    chosen = pick_representative(scenarios)

    results = []

    for size_label, sc in chosen:
        print(f"Running representative: {sc.get('name')} as {size_label}")
        if size_label == 'small':
            map_size = 20.0
            timeout = timeout_small
        elif size_label == 'medium':
            map_size = 60.0
            timeout = timeout_medium
        else:
            map_size = 120.0
            timeout = timeout_large

        terrain = make_terrain_for_scenario(sc.get('terrain_type', 'flat'), sc.get('difficulty', 'easy'), map_size_m=map_size)

        start = tuple(sc.get('start', [0.0, 0.0, 0.0]))
        goal = tuple(sc.get('goal', [map_size * 0.5, 0.0, 0.0]))

        t0 = time.time()
        try:
            res = planner.plan_path(start, goal, terrain, timeout=timeout)

            # --- Normalize result safely ---
            def _normalize_result(res_obj, default_comp_time):
                final_path = None
                comp_time = default_comp_time
                success = False

                # try to recognize PlanningResult class if loaded
                planning_cls = None
                pr_mod = sys.modules.get('path_planner_3d.planning_result')
                if pr_mod and hasattr(pr_mod, 'PlanningResult'):
                    planning_cls = getattr(pr_mod, 'PlanningResult')

                # None
                if res_obj is None:
                    return final_path, comp_time, False

                # If it's an instance of known PlanningResult
                if planning_cls is not None and isinstance(res_obj, planning_cls):
                    final_path = getattr(res_obj, 'path', None)
                    success = bool(getattr(res_obj, 'success', False))
                    comp_time = float(getattr(res_obj, 'computation_time', default_comp_time))
                    return final_path, comp_time, success

                # Generic object with attributes
                if hasattr(res_obj, 'path') or hasattr(res_obj, 'computation_time'):
                    final_path = getattr(res_obj, 'path', None)
                    success = bool(getattr(res_obj, 'success', False))
                    comp_time = float(getattr(res_obj, 'computation_time', default_comp_time))
                    return final_path, comp_time, success

                # dict-like
                if isinstance(res_obj, dict):
                    final_path = res_obj.get('path')
                    comp_time = float(res_obj.get('computation_time', default_comp_time))
                    success = bool(res_obj.get('success', final_path and len(final_path) > 0))
                    return final_path, comp_time, success

                # sequence-like (list/tuple) - guard against non-sequence objects
                if isinstance(res_obj, (list, tuple)):
                    if len(res_obj) >= 2:
                        final_path = res_obj[0]
                        try:
                            comp_time = float(res_obj[1])
                        except Exception:
                            comp_time = default_comp_time
                        try:
                            success = bool(final_path and len(final_path) > 0)
                        except Exception:
                            success = False
                    elif len(res_obj) == 1:
                        final_path = res_obj[0]
                        try:
                            success = bool(final_path and len(final_path) > 0)
                        except Exception:
                            success = False
                    return final_path, comp_time, success

                # Fallback: try to treat as path-like (iterable of pts)
                try:
                    # don't call len() on arbitrary objects without guarding
                    if hasattr(res_obj, '__iter__'):
                        final_path = list(res_obj)
                        success = bool(final_path and len(final_path) > 0)
                        return final_path, comp_time, success
                except Exception:
                    pass

                return None, default_comp_time, False

            comp_time_guess = round(time.time() - t0, 3)
            final_path, comp_time, success = _normalize_result(res, comp_time_guess)

            path_length = 0.0
            if success and final_path:
                try:
                    pts = np.array(final_path)
                    if pts.shape[0] >= 2:
                        diffs = np.diff(pts[:, :2], axis=0)
                        seg_lengths = np.hypot(diffs[:, 0], diffs[:, 1])
                        path_length = float(np.sum(seg_lengths))
                except Exception:
                    path_length = 0.0

            results.append({
                'scenario': sc.get('name'),
                'size_label': size_label,
                'success': bool(success),
                'computation_time': round(comp_time, 3),
                'path_length': round(path_length, 3),
                'error': None if success else 'No path'
            })

            print(f"  success={success} time={comp_time:.3f}s path_len={path_length:.3f}")
        except Exception as e:
            results.append({
                'scenario': sc.get('name'),
                'size_label': size_label,
                'success': False,
                'computation_time': round(time.time() - t0, 3),
                'path_length': 0.0,
                'error': str(e)
            })
            print(f"  ERROR running {sc.get('name')}: {e}")

    out = {
        'planner': 'DIJKSTRA_DWA',
        'total_runs': len(results),
        'successful_runs': sum(1 for r in results if r['success']),
        'failed_runs': sum(1 for r in results if not r['success']),
        'runs': results
    }

    out_dir = Path('ros2/ros2_ws/src/path_planner_3d/path_planner_3d/benchmark_results')
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / 'dijkstra_dwa_results.json'
    with open(out_file, 'w') as f:
        json.dump(out, f, indent=2)

    print(f"Saved results to {out_file}")


if __name__ == '__main__':
    run_representative()
