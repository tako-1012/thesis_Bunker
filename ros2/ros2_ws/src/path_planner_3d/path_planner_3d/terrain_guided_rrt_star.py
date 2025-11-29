import numpy as np
from typing import List, Optional, Tuple
import time
from dataclasses import dataclass
from terrain_guided_sampler import TerrainGuidedSampler

@dataclass
class RRTNode:
    """
    RRT*のノード
    """
    position: np.ndarray  # [x, y, z]
    parent: Optional['RRTNode'] = None
    cost: float = 0.0  # スタートからの累積コスト

    def __hash__(self):
        return id(self)

class TerrainGuidedRRTStar:
    """
    地形コストを考慮したRRT*アルゴリズム。
    TerrainGuidedSamplerを使用して効率的に探索し、不整地での経路計画を実現。
    """
    def __init__(
        self,
        start: np.ndarray,
        goal: np.ndarray,
        bounds: Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]],
        terrain_cost_map: Optional[np.ndarray] = None,
        resolution: float = 0.1,
        max_iterations: int = 5000,
        step_size: float = 0.5,
        goal_tolerance: float = 0.3,
        rewire_radius: float = 1.5,
        max_slope: float = 30.0,
        terrain_cost_weight: float = 1.0
    ) -> None:
        """
        Args:
            start: 始点 [x, y, z]
            goal: 終点 [x, y, z]
            bounds: 探索範囲 ((x_min, x_max), (y_min, y_max), (z_min, z_max))
            terrain_cost_map: 地形コストマップ
            resolution: グリッド解像度
            max_iterations: 最大反復回数
            step_size: 1ステップの最大距離 [meter]
            goal_tolerance: ゴール到達判定の許容誤差 [meter]
            rewire_radius: Rewireする近傍探索の半径 [meter]
            max_slope: 通行可能な最大傾斜 [degree]
            terrain_cost_weight: 地形コストの重み
        """
        self.start = start
        self.goal = goal
        self.bounds = bounds
        self.terrain_cost_map = terrain_cost_map
        self.resolution = resolution
        self.max_iterations = max_iterations
        self.step_size = step_size
        self.goal_tolerance = goal_tolerance
        self.rewire_radius = rewire_radius
        self.max_slope = max_slope
        self.terrain_cost_weight = terrain_cost_weight
        self.tree: List[RRTNode] = []
        self.sampler = TerrainGuidedSampler(
            bounds=bounds,
            terrain_cost_map=terrain_cost_map,
            resolution=resolution
        )
        self.best_goal_node: Optional[RRTNode] = None

    def plan(self, timeout: float = 30.0) -> Optional[List[np.ndarray]]:
        """
        RRT*経路計画（タイムアウト対応）
        Args:
            timeout: タイムアウト時間（秒）
        Returns:
            経路点列、失敗時None
        """
        import time
        start_time = time.time()
        self.tree = [RRTNode(position=self.start, parent=None, cost=0.0)]
        self.best_goal_node = None
        best_path = None
        best_cost = float('inf')
        for i in range(self.max_iterations):
            # タイムアウトチェック
            if time.time() - start_time > timeout:
                if best_path is not None:
                    return best_path
                else:
                    return None
            sample = self.sampler.sample(self.goal)
            new_node = self.extend(sample)
            if new_node is not None:
                self.rewire(new_node, self.rewire_radius)
                if self.is_goal_reached(new_node):
                    path = self.extract_path(new_node)
                    path_cost = new_node.cost
                    if path_cost < best_cost:
                        best_cost = path_cost
                        best_path = path
        return best_path

    def extend(self, sample: np.ndarray) -> Optional[RRTNode]:
        """
        ツリーをサンプル点に向けて伸ばす
        Args:
            sample: サンプル点 [x, y, z]
        Returns:
            成功: 新しく追加されたノード
            失敗: None
        """
        nearest = self.find_nearest_node(sample)
        new_pos = self.steer(nearest, sample)
        if not self.is_collision_free(nearest.position, new_pos):
            return None
        cost = nearest.cost + self.compute_path_cost(nearest, new_pos)
        new_node = RRTNode(position=new_pos, parent=nearest, cost=cost)
        self.tree.append(new_node)
        return new_node

    def rewire(self, new_node: RRTNode, radius: float) -> None:
        """
        新ノード周辺のノードを再配線
        Args:
            new_node: 新しく追加されたノード
            radius: 近傍探索の半径
        """
        near_nodes = self.find_near_nodes(new_node, radius)
        for node in near_nodes:
            if node is new_node or node.parent is None:
                continue
            new_cost = new_node.cost + self.compute_path_cost(new_node, node.position)
            if new_cost < node.cost and self.is_collision_free(new_node.position, node.position):
                node.parent = new_node
                node.cost = new_cost

    def find_nearest_node(self, position: np.ndarray) -> RRTNode:
        """
        指定位置に最も近いノードを探索
        Args:
            position: 対象位置 [x, y, z]
        Returns:
            最近傍ノード
        """
        return min(self.tree, key=lambda n: np.linalg.norm(n.position - position))

    def find_near_nodes(self, node: RRTNode, radius: float) -> List[RRTNode]:
        """
        指定ノードの近傍にあるノードを探索
        Args:
            node: 中心ノード
            radius: 探索半径
        Returns:
            近傍ノードのリスト
        """
        return [n for n in self.tree if np.linalg.norm(n.position - node.position) <= radius]

    def steer(self, from_node: RRTNode, to_pos: np.ndarray) -> np.ndarray:
        """
        from_nodeからto_posに向けてstep_size分進んだ位置を計算
        Args:
            from_node: 始点ノード
            to_pos: 目標位置
        Returns:
            新しい位置 [x, y, z]
        """
        direction = to_pos - from_node.position
        dist = np.linalg.norm(direction)
        if dist == 0:
            return from_node.position.copy()
        direction = direction / dist
        step = min(self.step_size, dist)
        new_pos = from_node.position + direction * step
        # bounds内にクリップ
        for i in range(3):
            new_pos[i] = np.clip(new_pos[i], self.bounds[i][0], self.bounds[i][1])
        return new_pos

    def compute_path_cost(self, from_node: RRTNode, to_pos: np.ndarray) -> float:
        """
        2点間の移動コストを計算（距離 × 地形コスト）
        Args:
            from_node: 始点ノード
            to_pos: 終点位置
        Returns:
            移動コスト
        """
        distance = np.linalg.norm(to_pos - from_node.position)
        terrain_cost = self.get_terrain_cost(to_pos)
        return distance * (1.0 + terrain_cost * self.terrain_cost_weight)

    def is_collision_free(self, from_pos: np.ndarray, to_pos: np.ndarray) -> bool:
        """
        2点間が衝突なく通行可能かチェック
        Args:
            from_pos: 始点
            to_pos: 終点
        Returns:
            True: 通行可能, False: 衝突あり
        """
        steps = int(np.ceil(np.linalg.norm(to_pos - from_pos) / self.resolution))
        if steps == 0:
            steps = 1
        for i in range(steps + 1):
            pos = from_pos + (to_pos - from_pos) * (i / steps)
            # boundsチェック
            for j in range(3):
                if not (self.bounds[j][0] <= pos[j] <= self.bounds[j][1]):
                    return False
            # 地形コストチェック
            terrain_cost = self.get_terrain_cost(pos)
            if terrain_cost >= 1.0:
                return False
            # 傾斜チェック（z方向の変化量から近似）
            if i > 0:
                prev_pos = from_pos + (to_pos - from_pos) * ((i - 1) / steps)
                dz = pos[2] - prev_pos[2]
                dx = np.linalg.norm(pos[:2] - prev_pos[:2])
                if dx > 0:
                    slope = np.degrees(np.arctan2(abs(dz), dx))
                    if slope > self.max_slope:
                        return False
        return True

    def is_goal_reached(self, node: RRTNode) -> bool:
        """
        ノードがゴールに到達したか判定
        Args:
            node: 判定対象ノード
        Returns:
            True: 到達, False: 未到達
        """
        return np.linalg.norm(node.position - self.goal) <= self.goal_tolerance

    def extract_path(self, goal_node: RRTNode) -> List[np.ndarray]:
        """
        ゴールノードから始点まで遡って経路を抽出
        Args:
            goal_node: ゴールに到達したノード
        Returns:
            経路の点列（始点→ゴール順）
        """
        path = []
        node = goal_node
        while node is not None:
            path.append(node.position)
            node = node.parent
        return path[::-1]

    def get_terrain_cost(self, position: np.ndarray) -> float:
        """
        指定位置の地形コストを取得
        Args:
            position: [x, y, z]
        Returns:
            地形コスト [0.0, 1.0]
        """
        if self.terrain_cost_map is None:
            return 0.0
        x_idx = int((position[0] - self.bounds[0][0]) / self.resolution)
        y_idx = int((position[1] - self.bounds[1][0]) / self.resolution)
        h, w = self.terrain_cost_map.shape
        if 0 <= y_idx < h and 0 <= x_idx < w:
            return float(self.terrain_cost_map[y_idx, x_idx])
        return 1.0  # 範囲外は通行不可扱い

if __name__ == '__main__':
    # ダミー地形コストマップ
    cost_map = np.ones((100, 100), dtype=np.float32) * 0.3
    cost_map[30:70, 30:70] = 0.1  # 中央は低コスト
    cost_map[45:55, 45:55] = 0.9  # 中央に障害物

    start = np.array([0.0, 0.0, 0.0])
    goal = np.array([9.0, 9.0, 0.0])
    bounds = ((-1.0, 10.0), (-1.0, 10.0), (0.0, 2.0))

    planner = TerrainGuidedRRTStar(
        start=start,
        goal=goal,
        bounds=bounds,
        terrain_cost_map=cost_map,
        resolution=0.1,
        max_iterations=2000,
        step_size=0.5,
        goal_tolerance=0.5,
        rewire_radius=1.5
    )

    print("Planning path...")
    start_time = time.time()
    path = planner.plan()
    elapsed = time.time() - start_time

    if path is not None:
        print(f"✓ Path found in {elapsed:.2f}s")
        print(f"  Path length: {len(path)} waypoints")
        print(f"  Start: {path[0]}")
        print(f"  Goal: {path[-1]}")
        print(f"  Total cost: {planner.tree[-1].cost:.2f}")
    else:
        print(f"✗ Path not found after {elapsed:.2f}s")
