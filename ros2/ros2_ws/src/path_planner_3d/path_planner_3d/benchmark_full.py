import numpy as np
from typing import List, Dict, Tuple, Optional
import time
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from adaptive_terrain_planner import AdaptiveTerrainPlanner, PlanningResult
from terrain_guided_rrt_star import TerrainGuidedRRTStar
from safety_first_planner import SafetyFirstPlanner
from hpa_star_planner import HPAStarPlanner
from dstar_lite_planner import DStarLitePlanner

@dataclass
class TestScenario:
    """
    テストシナリオ
    """
    name: str
    start: np.ndarray
    goal: np.ndarray
    bounds: Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]]
    terrain_cost_map: np.ndarray
    complexity: str
    description: str
    map_size: str  # "SMALL", "MEDIUM", "LARGE"

@dataclass
class BenchmarkResult:
    """
    ベンチマーク結果
    """
    planner_name: str
    scenario_name: str
    success: bool
    computation_time: float
    path_length: float
    num_waypoints: int
    complexity: str
    timestamp: str

class PlannerBenchmark:
    def __init__(self, output_dir: str = "./benchmark_results"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_test_scenarios(self, num_scenarios_per_scale: Dict[str, int] = None) -> List[TestScenario]:
        """
        マルチスケールのテストシナリオを生成（boundsとworld_sizeの整合性を強化）
        """
        if num_scenarios_per_scale is None:
            num_scenarios_per_scale = {
                "SMALL": 10,
                "MEDIUM": 10,
                "LARGE": 5
            }
        scenarios = []
        for map_size, num_scenarios in num_scenarios_per_scale.items():
            if map_size == "SMALL":
                grid_size = 100
                world_size = 10.0
                resolution = world_size / grid_size
                bounds = ((0.0, world_size), (0.0, world_size), (0.0, 2.0))
                min_distance = 3.0
            elif map_size == "MEDIUM":
                grid_size = 500
                world_size = 50.0
                resolution = world_size / grid_size
                bounds = ((0.0, world_size), (0.0, world_size), (0.0, 2.0))
                min_distance = 15.0
            elif map_size == "LARGE":
                grid_size = 1000
                world_size = 100.0
                resolution = world_size / grid_size
                bounds = ((0.0, world_size), (0.0, world_size), (0.0, 2.0))
                min_distance = 30.0
            else:
                continue
            scenarios_per_complexity = num_scenarios // 3
            for complexity in ["SIMPLE", "MODERATE", "COMPLEX"]:
                for i in range(scenarios_per_complexity):
                    seed = hash(f"{map_size}_{complexity}_{i}") % 10000
                    # 地形生成
                    if complexity == "SIMPLE":
                        cost_map = self._generate_simple_terrain(seed, grid_size)
                    elif complexity == "MODERATE":
                        cost_map = self._generate_moderate_terrain(seed, grid_size)
                    else:
                        cost_map = self._generate_complex_terrain(seed, grid_size)
                    # 始点・終点を確実に通行可能エリアに配置
                    max_attempts = 200
                    found = False
                    for attempt in range(max_attempts):
                        start = np.array([
                            np.random.uniform(world_size * 0.1, world_size * 0.9),
                            np.random.uniform(world_size * 0.1, world_size * 0.9),
                            0.0
                        ])
                        goal = np.array([
                            np.random.uniform(world_size * 0.1, world_size * 0.9),
                            np.random.uniform(world_size * 0.1, world_size * 0.9),
                            0.0
                        ])
                        if np.linalg.norm(goal - start) < min_distance:
                            continue
                        start_grid_x = int(start[0] / resolution)
                        start_grid_y = int(start[1] / resolution)
                        goal_grid_x = int(goal[0] / resolution)
                        goal_grid_y = int(goal[1] / resolution)
                        if not (0 <= start_grid_x < grid_size and 0 <= start_grid_y < grid_size):
                            continue
                        if not (0 <= goal_grid_x < grid_size and 0 <= goal_grid_y < grid_size):
                            continue
                        start_cost = cost_map[start_grid_y, start_grid_x]
                        goal_cost = cost_map[goal_grid_y, goal_grid_x]
                        if start_cost < 0.3 and goal_cost < 0.3:
                            found = True
                            break
                    if not found:
                        start = np.array([world_size * 0.3, world_size * 0.5, 0.0])
                        goal = np.array([world_size * 0.7, world_size * 0.5, 0.0])
                    scenario = TestScenario(
                        name=f"scenario_{map_size.lower()}_{complexity.lower()}_{i+1:03d}",
                        start=start,
                        goal=goal,
                        bounds=bounds,
                        terrain_cost_map=cost_map,
                        complexity=complexity,
                        description=f"{map_size} {complexity} terrain",
                        map_size=map_size
                    )
                    scenarios.append(scenario)
        return scenarios

    def _random_start_goal(self, cost_map: np.ndarray, min_dist: int = 50) -> Tuple[np.ndarray, np.ndarray]:
        h, w = cost_map.shape
        rng = np.random.default_rng()
        while True:
            s = rng.integers(0, w, size=2)
            g = rng.integers(0, w, size=2)
            if np.linalg.norm(s - g) > min_dist and cost_map[s[1], s[0]] < 0.5 and cost_map[g[1], g[0]] < 0.5:
                start = np.array([s[0] * 0.1, s[1] * 0.1, 0.0])
                goal = np.array([g[0] * 0.1, g[1] * 0.1, 0.0])
                return start, goal

    def _generate_simple_terrain(self, seed: int, grid_size: int = 100) -> np.ndarray:
        np.random.seed(seed)
        cost_map = np.ones((grid_size, grid_size), dtype=np.float32) * 0.05
        noise = np.random.normal(0, 0.01, (grid_size, grid_size))
        cost_map = np.clip(cost_map + noise, 0.0, 1.0)
        return cost_map

    def _generate_moderate_terrain(self, seed: int, grid_size: int = 100) -> np.ndarray:
        np.random.seed(seed)
        cost_map = np.ones((grid_size, grid_size), dtype=np.float32) * 0.12
        num_obstacles = np.random.randint(1, 3)
        for _ in range(num_obstacles):
            cx = np.random.randint(0, grid_size)
            cy = np.random.randint(0, grid_size)
            radius = np.random.randint(grid_size//40, grid_size//25)
            y, x = np.ogrid[:grid_size, :grid_size]
            mask = (x - cx)**2 + (y - cy)**2 <= radius**2
            cost_map[mask] = np.random.uniform(0.4, 0.6)
        return cost_map

    def _generate_complex_terrain(self, seed: int, grid_size: int = 100) -> np.ndarray:
        np.random.seed(seed)
        cost_map = np.ones((grid_size, grid_size), dtype=np.float32) * 0.35
        num_corridors = max(6, grid_size // 25)
        corridor_width = max(5, grid_size // 60)
        for _ in range(num_corridors):
            y = np.random.randint(0, grid_size)
            cost_map[max(0, y-corridor_width):min(grid_size, y+corridor_width), :] = 0.10
            x = np.random.randint(0, grid_size)
            cost_map[:, max(0, x-corridor_width):min(grid_size, x+corridor_width)] = 0.10
        return cost_map

    def run_benchmark(self, scenarios: List[TestScenario], 
                     planners: List[str] = None) -> List[BenchmarkResult]:
        if planners is None:
            planners = ["ADAPTIVE", "RRT_STAR", "SAFETY_FIRST", "HPA_STAR", "DSTAR_LITE"]
        results = []
        total_runs = len(scenarios) * len(planners)
        for idx, scenario in enumerate(scenarios):
            for planner in planners:
                run_number = idx * len(planners) + planners.index(planner) + 1
                print(f"  Progress: {run_number}/{total_runs} - {planner} on {scenario.name}... ", end="", flush=True)
                try:
                    if planner == "ADAPTIVE":
                        result = self._run_adaptive_planner(scenario)
                    elif planner == "RRT_STAR":
                        result = self._run_rrt_star(scenario)
                    elif planner == "SAFETY_FIRST":
                        result = self._run_safety_first(scenario)
                    elif planner == "HPA_STAR":
                        result = self._run_hpa_star(scenario)
                    elif planner == "DSTAR_LITE":
                        result = self._run_dstar_lite(scenario)
                    else:
                        continue
                    print(f"✓ ({result.computation_time:.2f}s)")
                except Exception as e:
                    print(f"✗ (error: {e})")
                    result = BenchmarkResult(
                        planner_name=planner,
                        scenario_name=scenario.name,
                        success=False,
                        computation_time=0.0,
                        path_length=0.0,
                        num_waypoints=0,
                        complexity=scenario.complexity,
                        timestamp=datetime.now().isoformat()
                    )
                results.append(result)
                self.save_results(results, filename="benchmark_results.json")
        return results

    def _run_dstar_lite(self, scenario: TestScenario) -> BenchmarkResult:
        planner = DStarLitePlanner(
            start=scenario.start,
            goal=scenario.goal,
            bounds=scenario.bounds,
            terrain_cost_map=scenario.terrain_cost_map,
            resolution=0.1
        )
        t0 = time.time()
        path = planner.plan()
        elapsed = time.time() - t0
        success = path is not None and len(path) > 1
        path_length = float(np.sum([np.linalg.norm(path[i+1] - path[i]) 
                                    for i in range(len(path)-1)])) if success else 0.0
        num_waypoints = len(path) if success else 0
        return BenchmarkResult(
            planner_name="DSTAR_LITE",
            scenario_name=scenario.name,
            success=success,
            computation_time=elapsed,
            path_length=path_length,
            num_waypoints=num_waypoints,
            complexity=scenario.complexity,
            timestamp=datetime.now().isoformat()
        )

    def _run_adaptive_planner(self, scenario: TestScenario) -> BenchmarkResult:
        if scenario.map_size == "SMALL":
            timeout = 30.0
        elif scenario.map_size == "MEDIUM":
            timeout = 60.0
        else:
            timeout = 120.0
        planner = AdaptiveTerrainPlanner(
            start=scenario.start,
            goal=scenario.goal,
            bounds=scenario.bounds,
            terrain_cost_map=scenario.terrain_cost_map,
            resolution=0.1
        )
        t0 = time.time()
        path = planner.plan(timeout=timeout)
        elapsed = time.time() - t0
        if path is None or len(path) <= 1:
            success = False
            path_length = 0.0
            num_waypoints = 0
            fallback_used = False
        else:
            success = True
            path_length = float(np.sum([np.linalg.norm(path[i+1] - path[i]) 
                                        for i in range(len(path)-1)]))
            num_waypoints = len(path)
            fallback_used = hasattr(planner, 'fallback_used') and planner.fallback_used
        return BenchmarkResult(
            planner_name="ADAPTIVE",
            scenario_name=scenario.name,
            success=success,
            computation_time=elapsed,
            path_length=path_length,
            num_waypoints=num_waypoints,
            complexity=scenario.complexity,
            timestamp=datetime.now().isoformat()
        )

    def _run_rrt_star(self, scenario: TestScenario) -> BenchmarkResult:
        if scenario.map_size == "SMALL":
            max_iterations = 5000
            timeout = 30.0
        elif scenario.map_size == "MEDIUM":
            max_iterations = 3000
            timeout = 60.0
        else:
            max_iterations = 2000
            timeout = 120.0
        planner = TerrainGuidedRRTStar(
            start=scenario.start,
            goal=scenario.goal,
            bounds=scenario.bounds,
            terrain_cost_map=scenario.terrain_cost_map,
            resolution=0.1,
            max_iterations=max_iterations,
            step_size=0.5,
            goal_tolerance=0.5,
            rewire_radius=1.5
        )
        t0 = time.time()
        path = planner.plan(timeout=timeout)
        elapsed = time.time() - t0
        success = path is not None and len(path) > 1
        path_length = float(np.sum([np.linalg.norm(path[i+1] - path[i]) for i in range(len(path)-1)])) if success else 0.0
        num_waypoints = len(path) if success else 0
        return BenchmarkResult(
            planner_name="RRT_STAR",
            scenario_name=scenario.name,
            success=success,
            computation_time=elapsed,
            path_length=path_length,
            num_waypoints=num_waypoints,
            complexity=scenario.complexity,
            timestamp=datetime.now().isoformat()
        )

    def _run_safety_first(self, scenario: TestScenario) -> BenchmarkResult:
        planner = SafetyFirstPlanner(
            start=scenario.start,
            goal=scenario.goal,
            bounds=scenario.bounds,
            terrain_cost_map=scenario.terrain_cost_map,
            resolution=0.1,
            max_slope=10.0,
            max_height_diff=0.15,
            safety_margin=1.2
        )
        t0 = time.time()
        path = planner.plan()
        elapsed = time.time() - t0
        success = path is not None and len(path) > 1
        path_length = float(np.sum([np.linalg.norm(path[i+1] - path[i]) for i in range(len(path)-1)])) if success else 0.0
        num_waypoints = len(path) if success else 0
        return BenchmarkResult(
            planner_name="SAFETY_FIRST",
            scenario_name=scenario.name,
            success=success,
            computation_time=elapsed,
            path_length=path_length,
            num_waypoints=num_waypoints,
            complexity=scenario.complexity,
            timestamp=datetime.now().isoformat()
        )

    def _run_hpa_star(self, scenario: TestScenario) -> BenchmarkResult:
        if scenario.map_size == "SMALL":
            cluster_size = 25
        elif scenario.map_size == "MEDIUM":
            cluster_size = 100
        else:
            cluster_size = 200
        planner = HPAStarPlanner(
            start=scenario.start,
            goal=scenario.goal,
            bounds=scenario.bounds,
            terrain_cost_map=scenario.terrain_cost_map,
            resolution=0.1,
            cluster_size=cluster_size
        )
        t0 = time.time()
        path = planner.plan()
        elapsed = time.time() - t0
        success = path is not None and len(path) > 1
        path_length = float(np.sum([np.linalg.norm(path[i+1] - path[i]) 
                                    for i in range(len(path)-1)])) if success else 0.0
        num_waypoints = len(path) if success else 0
        return BenchmarkResult(
            planner_name="HPA_STAR",
            scenario_name=scenario.name,
            success=success,
            computation_time=elapsed,
            path_length=path_length,
            num_waypoints=num_waypoints,
            complexity=scenario.complexity,
            timestamp=datetime.now().isoformat()
        )

    def save_results(self, results: List[BenchmarkResult], filename: str = "benchmark_results.json"):
        path = os.path.join(self.output_dir, filename)
        with open(path, "w") as f:
            json.dump([asdict(r) for r in results], f, indent=2, default=str)

    def generate_statistics(self, results: List[BenchmarkResult]) -> Dict:
        stats = {}
        grouped = {}
        for result in results:
            try:
                map_size = result.scenario_name.split('_')[1].upper()
            except Exception:
                map_size = getattr(result, 'map_size', 'SMALL')
            key = f"{result.planner_name}_{map_size}_{result.complexity}"
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(result)
        for key, group_results in grouped.items():
            total = len(group_results)
            successful = sum(1 for r in group_results if r.success)
            success_rate = successful / total if total > 0 else 0.0
            times = [r.computation_time for r in group_results if r.success]
            paths = [r.path_length for r in group_results if r.success]
            stats[key] = {
                'success_rate': success_rate,
                'total_runs': total,
                'successful_runs': successful,
                'avg_time': np.mean(times) if times else 0.0,
                'std_time': np.std(times) if times else 0.0,
                'avg_path': np.mean(paths) if paths else 0.0,
            }
        return stats

    def print_summary(self, stats: Dict):
        print("\n" + "="*100)
        print(f"{'Planner':<15} {'Map Size':<10} {'Complexity':<12} {'Success':<10} {'Avg Time (s)':<15} {'Std Time (s)':<15} {'Avg Path (m)':<15}")
        print("="*100)
        for key, data in sorted(stats.items()):
            planner, map_size, complexity = key.rsplit('_', 2)
            print(f"{planner:<15} {map_size:<10} {complexity:<12} "
                  f"{data['success_rate']*100:>6.1f}%    "
                  f"{data['avg_time']:>10.2f}      "
                  f"{data['std_time']:>10.2f}      "
                  f"{data['avg_path']:>10.2f}")
        print("="*100)

if __name__ == '__main__':
    print("="*60)
    print("FULL-SCALE Benchmark (100 Scenarios × 5 Planners)")
    print("="*60)
    
    benchmark = PlannerBenchmark(output_dir="./benchmark_results")
    
    # 本番規模のシナリオ生成
    print("\n[1/3] Generating scenarios...")
    scenarios = benchmark.generate_test_scenarios({
        "SMALL": 30,    # 10m×10m
        "MEDIUM": 50,   # 50m×50m ← メイン
        "LARGE": 20     # 100m×100m
    })
    
    print(f"  Total scenarios: {len(scenarios)}")
    print(f"  Total runs: {len(scenarios) * 5}")
    for map_size in ["SMALL", "MEDIUM", "LARGE"]:
        count = sum(1 for s in scenarios if s.map_size == map_size)
        print(f"    {map_size}: {count} scenarios")
    
    # ベンチマーク実行
    print("\n[2/3] Running full-scale benchmark...")
    print("  This will take 2-3 hours...")
    planners = ["ADAPTIVE", "RRT_STAR", "SAFETY_FIRST", "HPA_STAR", "DSTAR_LITE"]
    results = benchmark.run_benchmark(scenarios, planners)
    
    # 結果保存
    print("\n[3/3] Saving results...")
    benchmark.save_results(results, "full_benchmark_results.json")
    
    # 統計生成・表示
    stats = benchmark.generate_statistics(results)
    benchmark.print_summary(stats)
    
    print("\n" + "="*60)
    print("BENCHMARK COMPLETED!")
    print("="*60)
