import time
import numpy as np
from typing import Optional, List, Dict
from dataclasses import dataclass
import json
from datetime import datetime

from adaptive_terrain_planner import AdaptiveTerrainPlanner
from terrain_guided_rrt_star import TerrainGuidedRRTStar
from dstar_lite_planner import DStarLitePlanner
from safety_first_planner import SafetyFirstPlanner

@dataclass
class AblationResult:
    """アブレーション実験結果"""
    variant_name: str
    scenario_name: str
    success: bool
    computation_time: float
    path_length: float
    num_waypoints: int
    complexity: str
    fallback_used: bool
    timestamp: str

class AdaptiveVariant:
    """ADAPTIVEプランナーのバリエーション基底クラス"""
    def __init__(self, start, goal, bounds, terrain_cost_map, resolution=0.1):
        self.start = start
        self.goal = goal
        self.bounds = bounds
        self.terrain_cost_map = terrain_cost_map
        self.resolution = resolution
        self.fallback_used = False
    def evaluate_terrain_complexity(self) -> float:
        if self.terrain_cost_map is None:
            return 0.0
        high_cost_ratio = np.sum(self.terrain_cost_map > 0.5) / self.terrain_cost_map.size
        cost_variance = np.var(self.terrain_cost_map)
        complexity = (high_cost_ratio * 0.7 + cost_variance * 0.3)
        return complexity
    def plan(self, timeout: float = 30.0) -> Optional[List[np.ndarray]]:
        raise NotImplementedError

class AdaptiveFull(AdaptiveVariant):
    """フル機能ADAPTIVE（提案手法）"""
    def plan(self, timeout: float = 30.0) -> Optional[List[np.ndarray]]:
        start_time = time.time()
        complexity = self.evaluate_terrain_complexity()
        if complexity < 0.15:
            planner_type = "ASTAR"
        elif complexity < 0.55:
            planner_type = "RRT_STAR"
        else:
            planner_type = "SAFETY_FIRST"
        remaining_timeout = timeout - (time.time() - start_time)
        if planner_type == "ASTAR":
            path = self._plan_with_astar(remaining_timeout)
        elif planner_type == "RRT_STAR":
            path = self._plan_with_rrt(remaining_timeout)
        else:
            path = self._plan_with_safety_first(remaining_timeout)
        if path is None:
            self.fallback_used = True
            remaining_timeout = timeout - (time.time() - start_time)
            if remaining_timeout > 0:
                path = self._plan_with_rrt(remaining_timeout)
        else:
            self.fallback_used = False
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
        """RRT*での計画（benchmark_planners.pyと同じ方式）"""
        planner = TerrainGuidedRRTStar(
            start=self.start,
            goal=self.goal,
            bounds=self.bounds,
            terrain_cost_map=self.terrain_cost_map,
            resolution=self.resolution,
            max_iterations=3000,
            step_size=0.5
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

class AdaptiveNoFallback(AdaptiveFull):
    """フォールバック機構なし"""
    def plan(self, timeout: float = 30.0) -> Optional[List[np.ndarray]]:
        start_time = time.time()
        complexity = self.evaluate_terrain_complexity()
        if complexity < 0.15:
            planner_type = "ASTAR"
        elif complexity < 0.55:
            planner_type = "RRT_STAR"
        else:
            planner_type = "SAFETY_FIRST"
        remaining_timeout = timeout - (time.time() - start_time)
        if planner_type == "ASTAR":
            path = self._plan_with_astar(remaining_timeout)
        elif planner_type == "RRT_STAR":
            path = self._plan_with_rrt(remaining_timeout)
        else:
            path = self._plan_with_safety_first(remaining_timeout)
        self.fallback_used = False
        return path

class AdaptiveFixedAstar(AdaptiveVariant):
    """常にA*（複雑度判定なし）"""
    def plan(self, timeout: float = 30.0) -> Optional[List[np.ndarray]]:
        planner = DStarLitePlanner(
            start=self.start,
            goal=self.goal,
            bounds=self.bounds,
            terrain_cost_map=self.terrain_cost_map,
            resolution=self.resolution
        )
        self.fallback_used = False
        return planner.plan()

class AdaptiveFixedRRT(AdaptiveVariant):
    """常にRRT*（複雑度判定なし）"""
    def plan(self, timeout: float = 30.0) -> Optional[List[np.ndarray]]:
        planner = TerrainGuidedRRTStar(
            start=self.start,
            goal=self.goal,
            bounds=self.bounds,
            terrain_cost_map=self.terrain_cost_map,
            resolution=self.resolution,
            max_iterations=3000,
            step_size=0.5
        )
        self.fallback_used = False
        return planner.plan(timeout=timeout)

class AblationStudy:
    """アブレーションスタディ実行クラス"""
    def __init__(self, output_dir: str = "./ablation_results"):
        self.output_dir = output_dir
        import os
        os.makedirs(output_dir, exist_ok=True)
    def run_ablation(self, scenarios: List, variants: Dict[str, type]) -> List[AblationResult]:
        results = []
        total_runs = len(scenarios) * len(variants)
        current_run = 0
        for scenario in scenarios:
            for variant_name, VariantClass in variants.items():
                current_run += 1
                print(f"  Progress: {current_run}/{total_runs} - {variant_name} on {scenario.name}...", end=" ")
                planner = VariantClass(
                    start=scenario.start,
                    goal=scenario.goal,
                    bounds=scenario.bounds,
                    terrain_cost_map=scenario.terrain_cost_map,
                    resolution=0.1
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
                    fallback_used = hasattr(planner, 'fallback_used') and planner.fallback_used
                except Exception as e:
                    print(f"✗ (Error: {e})")
                    elapsed = time.time() - t0
                    success = False
                    path_length = 0.0
                    num_waypoints = 0
                    fallback_used = False
                result = AblationResult(
                    variant_name=variant_name,
                    scenario_name=scenario.name,
                    success=success,
                    computation_time=elapsed,
                    path_length=path_length,
                    num_waypoints=num_waypoints,
                    complexity=scenario.complexity,
                    fallback_used=fallback_used,
                    timestamp=datetime.now().isoformat()
                )
                results.append(result)
                print("✓" if success else "✗", f"({elapsed:.2f}s)")
        return results
    def save_results(self, results: List[AblationResult], filename: str):
        output_path = f"{self.output_dir}/{filename}"
        results_dict = [
            {
                'variant_name': r.variant_name,
                'scenario_name': r.scenario_name,
                'success': r.success,
                'computation_time': r.computation_time,
                'path_length': r.path_length,
                'num_waypoints': r.num_waypoints,
                'complexity': r.complexity,
                'fallback_used': r.fallback_used,
                'timestamp': r.timestamp
            }
            for r in results
        ]
        with open(output_path, 'w') as f:
            json.dump(results_dict, f, indent=2)
        print(f"\nResults saved to: {output_path}")

if __name__ == '__main__':
    from benchmark_planners import PlannerBenchmark, TestScenario
    print("="*60)
    print("Ablation Study: ADAPTIVE Planner Variants")
    print("="*60)
    print("\n[1/3] Generating test scenarios...")
    benchmark = PlannerBenchmark()
    scenarios = benchmark.generate_test_scenarios({
        "SMALL": 15,
        "MEDIUM": 15,
        "LARGE": 15
    })
    print(f"  Total scenarios: {len(scenarios)}")
    print("\n[2/3] Running ablation study...")
    study = AblationStudy()
    variants = {
        "ADAPTIVE_FULL": AdaptiveFull,
        "ADAPTIVE_NO_FALLBACK": AdaptiveNoFallback,
        "ADAPTIVE_FIXED_ASTAR": AdaptiveFixedAstar,
        "ADAPTIVE_FIXED_RRT": AdaptiveFixedRRT,
    }
    results = study.run_ablation(scenarios, variants)
    print("\n[3/3] Saving results...")
    study.save_results(results, "ablation_results.json")
    print("\n" + "="*60)
    print("Ablation Study Complete!")
    print("="*60)
