import numpy as np
from typing import List, Optional, Tuple, Dict, Set
import heapq
from dataclasses import dataclass, field
import time

@dataclass(order=True)
class DStarNode:
    """D* Lite用ノード（A*ベース）"""
    f_cost: float  # f = g + h
    g_cost: float = field(compare=False)  # スタートからのコスト
    position: Tuple[int, int, int] = field(compare=False)
    parent: Optional['DStarNode'] = field(default=None, compare=False)

class DStarLitePlanner:
    """
    D* Lite簡易版（A*ベース実装）
    静的環境用にシンプル化したバージョン
    """
    def __init__(self,
                 start: np.ndarray,
                 goal: np.ndarray,
                 bounds: Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]],
                 terrain_cost_map: Optional[np.ndarray] = None,
                 resolution: float = 0.1):
        self.start = start
        self.goal = goal
        self.bounds = bounds
        self.terrain_cost_map = terrain_cost_map
        self.resolution = resolution
    
    def plan(self) -> Optional[List[np.ndarray]]:
        """
        A*ベースの経路計画
        Returns:
            成功: 経路点列, 失敗: None
        """
        start_grid = self.world_to_grid(self.start)
        goal_grid = self.world_to_grid(self.goal)
        # 開始ノード
        start_node = DStarNode(
            f_cost=self.heuristic(start_grid, goal_grid),
            g_cost=0.0,
            position=start_grid,
            parent=None
        )
        # 優先度キューと訪問済みセット
        open_list = [start_node]
        closed_set: Set[Tuple[int, int, int]] = set()
        g_costs: Dict[Tuple[int, int, int], float] = {start_grid: 0.0}
        while open_list:
            # 最小f_costのノードを取り出し
            current = heapq.heappop(open_list)
            # 既に訪問済みならスキップ
            if current.position in closed_set:
                continue
            # ゴールに到達
            if current.position == goal_grid:
                return self.reconstruct_path(current)
            # 訪問済みに追加
            closed_set.add(current.position)
            # 隣接ノードを探索
            for neighbor_pos in self.get_neighbors(current.position):
                if not self.is_valid(neighbor_pos):
                    continue
                if neighbor_pos in closed_set:
                    continue
                # 新しいg_costを計算
                edge_cost = self.get_edge_cost(current.position, neighbor_pos)
                new_g_cost = current.g_cost + edge_cost
                # より良いパスが見つかった場合のみ追加
                if neighbor_pos not in g_costs or new_g_cost < g_costs[neighbor_pos]:
                    g_costs[neighbor_pos] = new_g_cost
                    h_cost = self.heuristic(neighbor_pos, goal_grid)
                    f_cost = new_g_cost + h_cost
                    neighbor_node = DStarNode(
                        f_cost=f_cost,
                        g_cost=new_g_cost,
                        position=neighbor_pos,
                        parent=current
                    )
                    heapq.heappush(open_list, neighbor_node)
        # 経路が見つからない
        return None
    
    def reconstruct_path(self, goal_node: DStarNode) -> List[np.ndarray]:
        """
        ゴールノードから経路を再構築
        """
        path_grid = []
        current = goal_node
        while current is not None:
            path_grid.append(current.position)
            current = current.parent
        path_grid.reverse()
        # 世界座標に変換
        path_world = [self.grid_to_world(p) for p in path_grid]
        return path_world
    
    def get_neighbors(self, position: Tuple[int, int, int]) -> List[Tuple[int, int, int]]:
        """8方向の隣接セルを取得"""
        x, y, z = position
        neighbors = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                neighbor = (x + dx, y + dy, z)
                neighbors.append(neighbor)
        return neighbors
    
    def is_valid(self, position: Tuple[int, int, int]) -> bool:
        """位置が有効かチェック（緩和）"""
        if self.terrain_cost_map is None:
            return True
        x, y, _ = position
        height, width = self.terrain_cost_map.shape
        if not (0 <= x < width and 0 <= y < height):
            return False
        # コストが高すぎる場所は通行不可（0.85に緩和）
        return self.terrain_cost_map[y, x] < 0.85
    
    def get_edge_cost(self, from_pos: Tuple[int, int, int], to_pos: Tuple[int, int, int]) -> float:
        """エッジコストを計算"""
        x1, y1, _ = from_pos
        x2, y2, _ = to_pos
        distance = np.sqrt((x2 - x1)**2 + (y2 - y1)**2) * self.resolution
        if self.terrain_cost_map is not None:
            # 地形コストを考慮
            avg_cost = (self.terrain_cost_map[y1, x1] + self.terrain_cost_map[y2, x2]) / 2.0
            return distance * (1.0 + avg_cost * 2.0)
        else:
            return distance
    
    def heuristic(self, pos1: Tuple[int, int, int], pos2: Tuple[int, int, int]) -> float:
        """ヒューリスティック関数（ユークリッド距離）"""
        x1, y1, _ = pos1
        x2, y2, _ = pos2
        return np.sqrt((x2 - x1)**2 + (y2 - y1)**2) * self.resolution
    
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


if __name__ == '__main__':
    # テスト用コストマップ
    cost_map = np.ones((200, 200), dtype=np.float32) * 0.3
    cost_map[80:120, 0:200] = 0.1  # 横の通路
    start = np.array([2.0, 5.0, 0.0])
    goal = np.array([18.0, 15.0, 0.0])
    bounds = ((-1.0, 21.0), (-1.0, 21.0), (0.0, 2.0))
    planner = DStarLitePlanner(
        start=start,
        goal=goal,
        bounds=bounds,
        terrain_cost_map=cost_map,
        resolution=0.1
    )
    print("Planning with D* Lite (A* based)...")
    start_time = time.time()
    path = planner.plan()
    elapsed = time.time() - start_time
    if path:
        print(f"✓ Path found in {elapsed:.2f}s")
        print(f"  Waypoints: {len(path)}")
        total_dist = sum(np.linalg.norm(path[i+1] - path[i]) for i in range(len(path)-1))
        print(f"  Distance: {total_dist:.2f}m")
    else:
        print(f"✗ Path not found after {elapsed:.2f}s")
