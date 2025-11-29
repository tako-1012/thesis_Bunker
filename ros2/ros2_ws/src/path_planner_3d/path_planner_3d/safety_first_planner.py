
import numpy as np
from typing import List, Optional, Tuple, Set, Dict
import heapq
from dataclasses import dataclass, field
import time

@dataclass(order=True)
class SafetyNode:
    """ダイクストラ法用のノード"""
    cost: float
    position: Tuple[int, int, int] = field(compare=False)
    parent: Optional['SafetyNode'] = field(default=None, compare=False)

class SafetyFirstPlanner:
    def __init__(self, 
                 start: np.ndarray,
                 goal: np.ndarray,
                 bounds: Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]],
                 terrain_cost_map: Optional[np.ndarray] = None,
                 resolution: float = 0.1,
                 max_slope: float = 10.0,
                 max_height_diff: float = 0.15,
                 safety_margin: float = 1.2):
        self.start = start
        self.goal = goal
        self.bounds = bounds
        self.terrain_cost_map = terrain_cost_map
        self.resolution = resolution
        self.max_slope = max_slope
        self.max_height_diff = max_height_diff
        self.safety_margin = safety_margin

    def plan(self) -> Optional[List[np.ndarray]]:
        """
        メイン経路計画関数
        
        始点・終点が安全エリア外の場合、最近傍の安全セルを探索
        """
        # 安全エリア抽出
        safe_zones = self.extract_safe_zones()
        safe_ratio = np.sum(safe_zones) / safe_zones.size
        if safe_ratio < 0.001:
            return None
        # グラフ構築
        graph = self.build_safe_graph(safe_zones)
        if not graph:
            return None
        # 始点・終点をグリッド座標に変換
        start_grid_original = self.world_to_grid(self.start)
        goal_grid_original = self.world_to_grid(self.goal)
        # 始点・終点が安全エリア内にあるか確認
        start_grid = start_grid_original
        goal_grid = goal_grid_original
        # 始点が安全エリア外なら、最近傍の安全セルを探索
        if start_grid not in graph:
            start_grid = self.find_nearest_safe_cell(start_grid_original, safe_zones)
            if start_grid is None or start_grid not in graph:
                return None
        # 終点が安全エリア外なら、最近傍の安全セルを探索
        if goal_grid not in graph:
            goal_grid = self.find_nearest_safe_cell(goal_grid_original, safe_zones)
            if goal_grid is None or goal_grid not in graph:
                return None
        # ダイクストラで経路探索
        path_grid = self.dijkstra(graph, start_grid, goal_grid)
        if path_grid is None:
            return None
        # 世界座標に変換
        path_world = [self.grid_to_world(p) for p in path_grid]
        # 元の始点・終点を経路の両端に追加
        path_world[0] = self.start.copy()
        path_world[-1] = self.goal.copy()
        return path_world

    def find_nearest_safe_cell(self, target_grid: Tuple[int, int, int], 
                               safe_zones: np.ndarray, 
                               max_search_radius: int = 50) -> Optional[Tuple[int, int, int]]:
        """
        指定グリッド座標に最も近い安全セルを探索
        Args:
            target_grid: 目標グリッド座標
            safe_zones: 安全エリアのブール配列
            max_search_radius: 最大探索半径（グリッドセル数）
        Returns:
            最近傍の安全セル、見つからなければNone
        """
        tx, ty, _ = target_grid
        height, width = safe_zones.shape
        from collections import deque
        queue = deque([(tx, ty, 0)])  # (x, y, distance)
        visited = set()
        visited.add((tx, ty))
        while queue:
            x, y, dist = queue.popleft()
            # 探索半径を超えたら終了
            if dist > max_search_radius:
                break
            # 範囲内かチェック
            if not (0 <= x < width and 0 <= y < height):
                continue
            # 安全セルが見つかったら返す
            if safe_zones[y, x]:
                return (x, y, 0)
            # 8方向の隣接セルをキューに追加
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if (nx, ny) not in visited:
                        visited.add((nx, ny))
                        queue.append((nx, ny, dist + 1))
        return None

    def extract_safe_zones(self) -> np.ndarray:
        """
        安全エリア抽出（地形コスト < 0.85のみ、緩和）
        """
        if self.terrain_cost_map is None:
            return np.ones((100, 100), dtype=bool)
        safe_zones = self.terrain_cost_map < 0.85
        return safe_zones

    def build_safe_graph(self, safe_zones: np.ndarray) -> Dict:
        """
        安全エリア内でグラフ構築
        Returns:
            {(x, y, z): [(neighbor, cost), ...], ...}
        """
        graph = {}
        height, width = safe_zones.shape
        directions = [(-1,-1), (-1,0), (-1,1), (0,-1), (0,1), (1,-1), (1,0), (1,1)]
        for y in range(height):
            for x in range(width):
                if not safe_zones[y, x]:
                    continue
                pos = (x, y, 0)
                neighbors = []
                for dx, dy in directions:
                    nx, ny = x + dx, y + dy
                    if self.is_valid_grid(nx, ny, width, height) and safe_zones[ny, nx]:
                        neighbor_pos = (nx, ny, 0)
                        cost = np.sqrt(dx**2 + dy**2) * self.resolution * self.safety_margin
                        neighbors.append((neighbor_pos, cost))
                if neighbors:
                    graph[pos] = neighbors
        return graph

    def dijkstra(self, graph: Dict, start_grid: Tuple[int, int, int], goal_grid: Tuple[int, int, int]) -> Optional[List[Tuple[int, int, int]]]:
        """
        ダイクストラ法で最短経路探索
        """
        if start_grid not in graph or goal_grid not in graph:
            return None
        pq = [(0.0, start_grid)]
        visited = set()
        cost_so_far = {start_grid: 0.0}
        came_from = {}
        while pq:
            current_cost, current = heapq.heappop(pq)
            if current in visited:
                continue
            visited.add(current)
            if current == goal_grid:
                path = []
                node = goal_grid
                while node in came_from:
                    path.append(node)
                    node = came_from[node]
                path.append(start_grid)
                return list(reversed(path))
            if current not in graph:
                continue
            for neighbor, edge_cost in graph[current]:
                new_cost = current_cost + edge_cost
                if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                    cost_so_far[neighbor] = new_cost
                    heapq.heappush(pq, (new_cost, neighbor))
                    came_from[neighbor] = current
        return None

    def world_to_grid(self, world_pos: np.ndarray) -> Tuple[int, int, int]:
        """世界座標 -> グリッド座標"""
        origin_x = self.bounds[0][0]
        origin_y = self.bounds[1][0]
        grid_x = int((world_pos[0] - origin_x) / self.resolution)
        grid_y = int((world_pos[1] - origin_y) / self.resolution)
        return (grid_x, grid_y, 0)

    def grid_to_world(self, grid_pos: Tuple[int, int, int]) -> np.ndarray:
        """グリッド座標 -> 世界座標"""
        origin_x = self.bounds[0][0]
        origin_y = self.bounds[1][0]
        world_x = grid_pos[0] * self.resolution + origin_x
        world_y = grid_pos[1] * self.resolution + origin_y
        return np.array([world_x, world_y, 0.0])

    def is_valid_grid(self, grid_x: int, grid_y: int, width: int, height: int) -> bool:
        """グリッド座標が範囲内かチェック"""
        return 0 <= grid_x < width and 0 <= grid_y < height

if __name__ == '__main__':
    cost_map = np.ones((100, 100), dtype=np.float32) * 0.8
    cost_map[10:90, 45:55] = 0.1
    cost_map[45:55, 10:90] = 0.1
    start = np.array([1.0, 5.0, 0.0])
    goal = np.array([8.0, 5.0, 0.0])
    bounds = ((-1.0, 10.0), (-1.0, 10.0), (0.0, 2.0))
    planner = SafetyFirstPlanner(
        start=start, goal=goal, bounds=bounds,
        terrain_cost_map=cost_map, resolution=0.1
    )
    print("Planning safe path...")
    start_time = time.time()
    path = planner.plan()
    elapsed = time.time() - start_time
    if path:
        print(f"✓ Safe path found in {elapsed:.2f}s")
        print(f"  Path length: {len(path)} waypoints")
        total_dist = sum(np.linalg.norm(path[i+1] - path[i]) for i in range(len(path)-1))
        print(f"  Total distance: {total_dist:.2f}m")
    else:
        print(f"✗ Safe path not found after {elapsed:.2f}s")
    # 旧実装・重複部分を全て削除（新実装のみ残す）
