import numpy as np
from typing import List, Optional, Tuple, Dict
import time
from enum import Enum
from dataclasses import dataclass
from terrain_complexity_evaluator import TerrainComplexityEvaluator
from terrain_guided_rrt_star import TerrainGuidedRRTStar
from safety_first_planner import SafetyFirstPlanner
import heapq

class PlannerMode(Enum):
    """
    プランナーモード
    """
    ASTAR = "ASTAR"
    RRT_STAR = "RRT_STAR"
    SAFETY_FIRST = "SAFETY_FIRST"

@dataclass
class PlanningResult:
    """
    経路計画の結果
    """
    success: bool
    path: Optional[List[np.ndarray]]
    planner_mode: PlannerMode
    computation_time: float
    complexity: str  # "SIMPLE", "MODERATE", "COMPLEX"
    num_waypoints: int
    path_length: float
    fallback_used: bool = False

class AdaptiveTerrainPlanner:
    """
    地形複雑度に応じて3つのプランナーを自動切り替えする統合システム。
    """
    def __init__(
        self,
        start: np.ndarray,
        goal: np.ndarray,
        bounds: Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]],
        terrain_cost_map: Optional[np.ndarray] = None,
        resolution: float = 0.1,
        astar_timeout: float = 5.0,
        rrt_timeout: float = 10.0,
        safety_timeout: float = 30.0
    ) -> None:
        self.start = start
        self.goal = goal
        self.bounds = bounds
        self.terrain_cost_map = terrain_cost_map
        self.resolution = resolution
        self.astar_timeout = astar_timeout
        self.rrt_timeout = rrt_timeout
        self.safety_timeout = safety_timeout

    def plan(self, timeout: float = 30.0) -> Optional[List[np.ndarray]]:
        """
        適応的地形対応経路計画（タイムアウト対応）
        Args:
            timeout: タイムアウト時間（秒）
        Returns:
            経路点列、失敗時None
        """
        import time
        start_time = time.time()
        complexity = self.evaluate_terrain_complexity()
        # 複雑度に応じてプランナーを選択
        if complexity == "SIMPLE":
            planner_type = "ASTAR"
        elif complexity == "MODERATE":
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
        # フォールバック機構
        if path is None:
            self.fallback_used = True
            remaining_timeout = timeout - (time.time() - start_time)
            if remaining_timeout > 0:
                path = self._plan_with_rrt(remaining_timeout)
        else:
            self.fallback_used = False
        return path

    def _plan_with_astar(self, timeout: float) -> Optional[List[np.ndarray]]:
        """A*ベースの計画（簡易版・高速）"""
        from dstar_lite_planner import DStarLitePlanner
        planner = DStarLitePlanner(
            start=self.start,
            goal=self.goal,
            bounds=self.bounds,
            terrain_cost_map=self.terrain_cost_map,
            resolution=self.resolution
        )
        import time
        start_time = time.time()
        path = planner.plan()
        if time.time() - start_time > timeout:
            return None
        return path

    def _plan_with_rrt(self, timeout: float) -> Optional[List[np.ndarray]]:
        """RRT*での計画"""
        from terrain_guided_rrt_star import TerrainGuidedRRTStar
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
        """安全重視での計画"""
        from safety_first_planner import SafetyFirstPlanner
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
        import time
        start_time = time.time()
        path = planner.plan()
        if time.time() - start_time > timeout:
            return None
        return path

    def evaluate_terrain_complexity(self) -> str:
        """
        地形複雑度を評価（コストマップベース）
        Returns:
            "SIMPLE", "MODERATE", "COMPLEX"
        処理:
            コストマップの統計量から判定
        """
        if self.terrain_cost_map is None:
            # コストマップがない場合はSIMPLEとみなす
            return "SIMPLE"
        evaluation_radius = 5.0  # meter
        start_grid = self.world_to_grid(self.start)
        goal_grid = self.world_to_grid(self.goal)
        min_x = min(start_grid[0], goal_grid[0]) - int(evaluation_radius / self.resolution)
        max_x = max(start_grid[0], goal_grid[0]) + int(evaluation_radius / self.resolution)
        min_y = min(start_grid[1], goal_grid[1]) - int(evaluation_radius / self.resolution)
        max_y = max(start_grid[1], goal_grid[1]) + int(evaluation_radius / self.resolution)
        min_x = max(0, min_x)
        max_x = min(self.terrain_cost_map.shape[1], max_x)
        min_y = max(0, min_y)
        max_y = min(self.terrain_cost_map.shape[0], max_y)
        region = self.terrain_cost_map[min_y:max_y, min_x:max_x]
        mean_cost = np.mean(region)
        std_cost = np.std(region)
        high_cost_ratio = np.sum(region > 0.7) / region.size
        complexity_score = mean_cost * 0.4 + std_cost * 0.3 + high_cost_ratio * 0.3
        if complexity_score < 0.15:
            complexity = "SIMPLE"
        elif complexity_score < 0.55:
            complexity = "MODERATE"
        else:
            complexity = "COMPLEX"
        return complexity

    def world_to_grid(self, world_pos: np.ndarray) -> Tuple[int, int]:
        """
        世界座標 -> グリッド座標変換
        Args:
            world_pos: [x, y, z]
        Returns:
            (grid_x, grid_y)
        """
        origin_x = self.bounds[0][0]
        origin_y = self.bounds[1][0]
        grid_x = int((world_pos[0] - origin_x) / self.resolution)
        grid_y = int((world_pos[1] - origin_y) / self.resolution)
        return (grid_x, grid_y)

    def select_planner(self, complexity: str) -> PlannerMode:
        """
        地形複雑度からプランナーを選択
        """
        if complexity == "SIMPLE":
            return PlannerMode.ASTAR
        elif complexity == "MODERATE":
            return PlannerMode.RRT_STAR
        else:
            return PlannerMode.SAFETY_FIRST

    def execute_with_timeout(self, mode: PlannerMode, timeout: float) -> Tuple[Optional[List[np.ndarray]], float]:
        """
        指定されたプランナーをタイムアウト付きで実行
        Returns:
            (経路, 計算時間)
        """
        t0 = time.time()
        path = None
        if mode == PlannerMode.ASTAR:
            path = self.execute_astar()
        elif mode == PlannerMode.RRT_STAR:
            path = self.execute_rrt_star()
        elif mode == PlannerMode.SAFETY_FIRST:
            path = self.execute_safety_first()
        elapsed = time.time() - t0
        if elapsed > timeout:
            return None, elapsed
        return path, elapsed

    def execute_astar(self) -> Optional[List[np.ndarray]]:
        """
        Terrain-Aware A*を実行
        Returns:
            経路（失敗時None）
        """
        # 簡易グリッドA*実装
        if self.terrain_cost_map is None:
            return [self.start, self.goal]
        h, w = self.terrain_cost_map.shape
        start_grid = self.world_to_grid(self.start)
        goal_grid = self.world_to_grid(self.goal)
        open_set = []
        heapq.heappush(open_set, (0, start_grid))
        came_from: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {start_grid: None}
        g_score = {start_grid: 0.0}
        def heuristic(a, b):
            return np.linalg.norm(np.array(a) - np.array(b))
        while open_set:
            _, current = heapq.heappop(open_set)
            if current == goal_grid:
                # 経路復元
                path = []
                node = current
                while node is not None:
                    path.append(self.grid_to_world(node))
                    node = came_from[node]
                return path[::-1]
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    neighbor = (current[0] + dx, current[1] + dy)
                    if not (0 <= neighbor[0] < w and 0 <= neighbor[1] < h):
                        continue
                    terrain_cost = self.terrain_cost_map[neighbor[1], neighbor[0]]
                    if terrain_cost >= 1.0:
                        continue
                    tentative_g = g_score[current] + np.linalg.norm([dx, dy]) * self.resolution * (1.0 + terrain_cost)
                    if neighbor not in g_score or tentative_g < g_score[neighbor]:
                        g_score[neighbor] = tentative_g
                        f = tentative_g + heuristic(neighbor, goal_grid)
                        heapq.heappush(open_set, (f, neighbor))
                        came_from[neighbor] = current
        return None

    def execute_rrt_star(self) -> Optional[List[np.ndarray]]:
        """
        Terrain-Guided RRT*を実行
        Returns:
            経路（失敗時None）
        """
        planner = TerrainGuidedRRTStar(
            start=self.start,
            goal=self.goal,
            bounds=self.bounds,
            terrain_cost_map=self.terrain_cost_map,
            resolution=self.resolution,
            max_iterations=2000,
            step_size=0.5,
            goal_tolerance=0.5,
            rewire_radius=1.5
        )
        return planner.plan()

    def execute_safety_first(self, relaxed: bool = False) -> Optional[List[np.ndarray]]:
        """
        Safety-First Plannerを実行
        Returns:
            経路（失敗時None）
        """
        max_slope = 15.0 if relaxed else 10.0
        max_height_diff = 0.25 if relaxed else 0.15
        planner = SafetyFirstPlanner(
            start=self.start,
            goal=self.goal,
            bounds=self.bounds,
            terrain_cost_map=self.terrain_cost_map,
            resolution=self.resolution,
            max_slope=max_slope,
            max_height_diff=max_height_diff,
            safety_margin=1.2
        )
        return planner.plan()

    def compute_path_length(self, path: List[np.ndarray]) -> float:
        """
        経路の総距離を計算
        Returns:
            総距離 [meter]
        """
        if path is None or len(path) < 2:
            return 0.0
        return float(np.sum([np.linalg.norm(path[i+1] - path[i]) for i in range(len(path)-1)]))

    def get_fallback_sequence(self, initial_mode: PlannerMode) -> List[PlannerMode]:
        """
        フォールバックシーケンスを取得
        Returns:
            フォールバックの順序
        """
        if initial_mode == PlannerMode.ASTAR:
            return [PlannerMode.ASTAR, PlannerMode.RRT_STAR, PlannerMode.SAFETY_FIRST]
        elif initial_mode == PlannerMode.RRT_STAR:
            return [PlannerMode.RRT_STAR, PlannerMode.SAFETY_FIRST]
        else:
            return [PlannerMode.SAFETY_FIRST]

    def world_to_grid(self, world_pos: np.ndarray) -> Tuple[int, int]:
        x_idx = int((world_pos[0] - self.bounds[0][0]) / self.resolution)
        y_idx = int((world_pos[1] - self.bounds[1][0]) / self.resolution)
        return (x_idx, y_idx)

    def grid_to_world(self, grid_pos: Tuple[int, int]) -> np.ndarray:
        x = self.bounds[0][0] + grid_pos[0] * self.resolution
        y = self.bounds[1][0] + grid_pos[1] * self.resolution
        z = 0.0
        return np.array([x, y, z], dtype=np.float32)

if __name__ == '__main__':
    # ダミー地形コストマップ（3種類テスト）
    cost_map_simple = np.ones((100, 100), dtype=np.float32) * 0.1
    cost_map_moderate = np.ones((100, 100), dtype=np.float32) * 0.3
    cost_map_moderate[40:60, 40:60] = 0.6
    cost_map_complex = np.ones((100, 100), dtype=np.float32) * 0.8
    cost_map_complex[30:35, :] = 0.1  # 狭い通路
    start = np.array([0.0, 0.0, 0.0])
    goal = np.array([9.0, 9.0, 0.0])
    bounds = ((-1.0, 10.0), (-1.0, 10.0), (0.0, 2.0))
    for name, cost_map in [("SIMPLE", cost_map_simple), 
                           ("MODERATE", cost_map_moderate), 
                           ("COMPLEX", cost_map_complex)]:
        print(f"\n{'='*50}")
        print(f"Testing {name} terrain")
        print(f"{'='*50}")
        planner = AdaptiveTerrainPlanner(
            start=start,
            goal=goal,
            bounds=bounds,
            terrain_cost_map=cost_map,
            resolution=0.1,
            astar_timeout=5.0,
            rrt_timeout=10.0,
            safety_timeout=30.0
        )
        result = planner.plan()
        print(f"✓ Planning succeeded")
        print(f"  Complexity: {result.complexity}")
        print(f"  Planner used: {result.planner_mode.value}")
        print(f"  Computation time: {result.computation_time:.2f}s")
        print(f"  Path length: {result.num_waypoints} waypoints")
        print(f"  Total distance: {result.path_length:.2f}m")
        print(f"  Fallback used: {result.fallback_used}")
