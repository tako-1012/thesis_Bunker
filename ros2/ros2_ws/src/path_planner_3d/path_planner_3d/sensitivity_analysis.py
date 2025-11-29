import time
import numpy as np
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
import json
from datetime import datetime

from terrain_guided_rrt_star import TerrainGuidedRRTStar
from dstar_lite_planner import DStarLitePlanner
from safety_first_planner import SafetyFirstPlanner

@dataclass
class SensitivityResult:
    """感度分析結果"""
    threshold_set: str
    scenario_name: str
    success: bool
    computation_time: float
    path_length: float
    num_waypoints: int
    complexity: str
    selected_planner: str
    timestamp: str

class AdaptiveSensitivity:
    """閾値を変更可能なADAPTIVEプランナー"""
    def __init__(self, start, goal, bounds, terrain_cost_map, resolution=0.1,
                 threshold_simple=0.15, threshold_complex=0.55):
        self.start = start
        self.goal = goal
        self.bounds = bounds
        self.terrain_cost_map = terrain_cost_map
        self.resolution = resolution
        self.threshold_simple = threshold_simple
        self.threshold_complex = threshold_complex
        self.selected_planner = None
    def evaluate_terrain_complexity(self) -> float:
        """地形複雑度を評価"""
        if self.terrain_cost_map is None:
            return 0.0
        high_cost_ratio = np.sum(self.terrain_cost_map > 0.5) / self.terrain_cost_map.size
        cost_variance = np.var(self.terrain_cost_map)
        complexity = (high_cost_ratio * 0.7 + cost_variance * 0.3)
        return complexity
    def plan(self, timeout: float = 30.0) -> Optional[List[np.ndarray]]:
        start_time = time.time()
        complexity = self.evaluate_terrain_complexity()
        if complexity < self.threshold_simple:
            planner_type = "ASTAR"
            self.selected_planner = "A*"
        elif complexity < self.threshold_complex:
            planner_type = "RRT_STAR"
            self.selected_planner = "RRT*"
        else:
            planner_type = "SAFETY_FIRST"
            self.selected_planner = "SAFETY_FIRST"
        remaining_timeout = timeout - (time.time() - start_time)
        if planner_type == "ASTAR":
            path = self._plan_with_astar(remaining_timeout)
        elif planner_type == "RRT_STAR":
            path = self._plan_with_rrt(remaining_timeout)
        else:
            path = self._plan_with_safety_first(remaining_timeout)
        if path is None:
            remaining_timeout = timeout - (time.time() - start_time)
            if remaining_timeout > 0:
                path = self._plan_with_rrt(remaining_timeout)
                self.selected_planner += " (Fallback)"
        return path
    def _plan_with_astar(self, timeout: float) -> Optional[List[np.ndarray]]:
        planner = DStarLitePlanner(
            start=self.start,
            goal=self.goal,
            bounds=self.bounds,
            terrain_cost_map=self.terrain_cost_map,
            resolution=self.resolution
        )
        return planner.plan()
    def _plan_with_rrt(self, timeout: float) -> Optional[List[np.ndarray]]:
        planner = TerrainGuidedRRTStar(
            start=self.start,
            goal=self.goal,
            bounds=self.bounds,
            terrain_cost_map=self.terrain_cost_map,
            resolution=self.resolution,
            max_iterations=3000,
            step_size=0.5,
            goal_tolerance=0.5,
            rewire_radius=1.5
        )
        return planner.plan(timeout=timeout)
    def _plan_with_safety_first(self, timeout: float) -> Optional[List[np.ndarray]]:
        planner = SafetyFirstPlanner(
            start=self.start,
            goal=self.goal,
            bounds=self.bounds,
            terrain_cost_map=self.terrain_cost_map,
            resolution=self.resolution,
            max_slope=10.0,
            max_height_diff=0.15,
            safety_margin=1.2
        )
        return planner.plan()

class SensitivityAnalysis:
    """パラメータ感度分析実行クラス"""
    def __init__(self, output_dir: str = "./sensitivity_results"):
        self.output_dir = output_dir
        import os
        os.makedirs(output_dir, exist_ok=True)
    def run_sensitivity(self, scenarios: List, threshold_sets: Dict[str, Tuple[float, float]]) -> List[SensitivityResult]:
        results = []
        total_runs = len(scenarios) * len(threshold_sets)
        current_run = 0
        for scenario in scenarios:
            for set_name, (thresh_simple, thresh_complex) in threshold_sets.items():
                current_run += 1
                print(f"  Progress: {current_run}/{total_runs} - {set_name} on {scenario.name}...", end=" ")
                planner = AdaptiveSensitivity(
                    start=scenario.start,
                    goal=scenario.goal,
                    bounds=scenario.bounds,
                    terrain_cost_map=scenario.terrain_cost_map,
                    resolution=0.1,
                    threshold_simple=thresh_simple,
                    threshold_complex=thresh_complex
                )
                if scenario.map_size == "SMALL":
                    timeout = 30.0
                elif scenario.map_size == "MEDIUM":
                    timeout = 60.0
                else:
                    timeout = 120.0
                t0 = time.time()
                try:
                    path = planner.plan(timeout=timeout)
                    elapsed = time.time() - t0
                    if path is None or len(path) <= 1:
                        success = False
                        path_length = 0.0
                        num_waypoints = 0
                    else:
                        success = True
                        path_length = float(np.sum([np.linalg.norm(path[i+1] - path[i]) 
                                                    for i in range(len(path)-1)]))
                        num_waypoints = len(path)
                    selected = planner.selected_planner if hasattr(planner, 'selected_planner') else "Unknown"
                except Exception as e:
                    print(f"✗ (Error: {e})")
                    elapsed = time.time() - t0
                    success = False
                    path_length = 0.0
                    num_waypoints = 0
                    selected = "Error"
                result = SensitivityResult(
                    threshold_set=set_name,
                    scenario_name=scenario.name,
                    success=success,
                    computation_time=elapsed,
                    path_length=path_length,
                    num_waypoints=num_waypoints,
                    complexity=scenario.complexity,
                    selected_planner=selected,
                    timestamp=datetime.now().isoformat()
                )
                results.append(result)
                print("✓" if success else "✗", f"({elapsed:.2f}s)")
        return results
    def save_results(self, results: List[SensitivityResult], filename: str):
        output_path = f"{self.output_dir}/{filename}"
        results_dict = [
            {
                'threshold_set': r.threshold_set,
                'scenario_name': r.scenario_name,
                'success': r.success,
                'computation_time': r.computation_time,
                'path_length': r.path_length,
                'num_waypoints': r.num_waypoints,
                'complexity': r.complexity,
                'selected_planner': r.selected_planner,
                'timestamp': r.timestamp
            }
            for r in results
        ]
        with open(output_path, 'w') as f:
            json.dump(results_dict, f, indent=2)
        print(f"\nResults saved to: {output_path}")

if __name__ == '__main__':
    from benchmark_planners import PlannerBenchmark
    print("="*60)
    print("Sensitivity Analysis: Threshold Parameters")
    print("="*60)
    print("\n[1/3] Generating test scenarios...")
    benchmark = PlannerBenchmark()
    scenarios = benchmark.generate_test_scenarios({
        "SMALL": 15,
        "MEDIUM": 15,
        "LARGE": 15
    })
    print(f"  Total scenarios: {len(scenarios)}")
    print("\n[2/3] Running sensitivity analysis...")
    analysis = SensitivityAnalysis()
    threshold_sets = {
        "NARROW": (0.10, 0.50),
        "BASELINE": (0.15, 0.55),
        "WIDE": (0.20, 0.60),
    }
    results = analysis.run_sensitivity(scenarios, threshold_sets)
    print("\n[3/3] Saving results...")
    analysis.save_results(results, "sensitivity_results.json")
    print("\n" + "="*60)
    print("Sensitivity Analysis Complete!")
    print("="*60)
