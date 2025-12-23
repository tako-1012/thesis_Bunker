#!/usr/bin/env python3

"""Dijkstra + DWA 実験ランナー（代表シナリオ自動選択）
動作:
 - `scenarios/benchmark_scenarios.json` から代表シナリオを選択（easy/medium/hard）
 - RepresentativeTerrainGenerator を使って地形を生成
 - `DijkstraDWAPlanner` を呼び出して順に Small→Medium→Large を実行
 - 結果を `path_planner_3d/benchmark_results/dijkstra_dwa_results.json` に保存

このスクリプトはパッケージの相対インポート問題を回避するため、
必要なモジュールを明示的にロードします。
"""
import json
import time
import sys
import os
from pathlib import Path
from typing import Dict, Any, List

import numpy as np

def load_path_planner_modules(base_pkg_dir: str = 'ros2/ros2_ws/src/path_planner_3d/path_planner_3d'):
	"""`path_planner_3d` パッケージ相当を sys.modules に注入してモジュールをロードする。"""
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
	"""RepresentativeTerrainGenerator を使い terrain_map を返す。"""
	from bunker_ros2.simulation_manager.representative_terrain_generator import RepresentativeTerrainGenerator

	resolution = 0.5
	gen = RepresentativeTerrainGenerator(map_size=map_size_m, resolution=resolution)

	terrain_type_lower = (terrain_type or '').lower()
	if 'flat' in terrain_type_lower:
		return gen.generate_flat_agricultural_field()
	if 'slope' in terrain_type_lower or 'gentle' in terrain_type_lower:
		if difficulty == 'easy':
			return gen.generate_gentle_hills()
		elif difficulty == 'medium':
			return gen.generate_gentle_hills()
		else:
			return gen.generate_steep_terrain()
	if 'complex' in terrain_type_lower or 'obstacle' in terrain_type_lower:
		return gen.generate_complex_obstacles()
	if 'extreme' in terrain_type_lower or 'hazard' in terrain_type_lower:
		return gen.generate_extreme_hazards()

	return gen.generate_flat_agricultural_field()

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

def run_representative(timeout_small: int = 60, timeout_medium: int = 90, timeout_large: int = 120):
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

			final_path = None
			comp_time = round(time.time() - t0, 3)
			success = False
			if res is None:
				success = False
			elif hasattr(res, 'path'):
				final_path = getattr(res, 'path', None)
				success = bool(getattr(res, 'success', False))
				comp_time = float(getattr(res, 'computation_time', comp_time))
			elif isinstance(res, (list, tuple)):
				if len(res) >= 2:
					final_path, comp_time = res[0], float(res[1])
					success = bool(final_path and len(final_path) > 0)
				else:
					final_path = res[0]
					success = bool(final_path and len(final_path) > 0)
			else:
				final_path = res
				try:
					success = bool(final_path and len(final_path) > 0)
				except Exception:
					success = False

			path_length = 0.0
			if success and final_path:
				pts = np.array(final_path)
				if pts.shape[0] >= 2:
					diffs = np.diff(pts[:, :2], axis=0)
					seg_lengths = np.hypot(diffs[:, 0], diffs[:, 1])
					path_length = float(np.sum(seg_lengths))

			results.append({
				'scenario': sc.get('name'),
				'size_label': size_label,
				'success': success,
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

*** Begin Patch
*** End Patch
