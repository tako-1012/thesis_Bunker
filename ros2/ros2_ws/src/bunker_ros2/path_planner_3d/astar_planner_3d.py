"""
A* 3D経路計画クラス
"""
import heapq
from typing import List, Tuple, Optional, Set, Dict
import numpy as np
from node_3d import Node3D
from cost_calculator import CostCalculator

class AStarPlanner3D:
    """A* 3D経路計画"""
    
    def __init__(
        self,
        voxel_size: float = 0.1,
        grid_size: Tuple[int, int, int] = (100, 100, 30),
        min_bound: Tuple[float, float, float] = (-5.0, -5.0, 0.0),
        use_cost_calculator: bool = True
    ):
        """
        Args:
            voxel_size: ボクセルサイズ（メートル）
            grid_size: グリッドサイズ（x, y, z）
            min_bound: グリッドの最小境界（ワールド座標）
            use_cost_calculator: コスト計算器を使用するか
        """
        self.voxel_size = voxel_size
        self.grid_size = grid_size
        self.min_bound = np.array(min_bound)
        
        # 地形データ（後で設定）
        self.voxel_grid = None
        self.terrain_data = None
        
        # コスト計算器の初期化
        self.use_cost_calculator = use_cost_calculator
        if use_cost_calculator:
            self.cost_calculator = CostCalculator()
        else:
            self.cost_calculator = None
        
        # 統計情報
        self.last_search_stats = {
            'nodes_explored': 0,
            'path_length': 0,
            'computation_time': 0.0
        }
    
    def set_terrain_data(self, voxel_grid, terrain_data) -> None:
        """地形データを設定"""
        self.voxel_grid = voxel_grid
        self.terrain_data = terrain_data
    
    def plan_path(
        self,
        start: Tuple[float, float, float],
        goal: Tuple[float, float, float]
    ) -> Optional[List[Tuple[float, float, float]]]:
        """
        経路計画のメイン関数
        
        Args:
            start: 開始位置（ワールド座標）
            goal: 目標位置（ワールド座標）
        
        Returns:
            経路（ワールド座標のリスト）、失敗時はNone
        """
        import time
        start_time = time.time()
        
        # ワールド座標 → ボクセルインデックス変換
        start_idx = self._world_to_voxel(start)
        goal_idx = self._world_to_voxel(goal)
        
        # 境界チェック
        if not self._is_in_grid(start_idx) or not self._is_in_grid(goal_idx):
            print(f"エラー: 開始点または目標点がグリッド外です")
            return None
        
        # A*アルゴリズム実行
        path_indices = self._astar_search(start_idx, goal_idx)
        
        # 統計情報更新
        self.last_search_stats['computation_time'] = time.time() - start_time
        
        if path_indices is None:
            return None
        
        # ボクセルインデックス → ワールド座標変換
        path_world = [self._voxel_to_world(idx) for idx in path_indices]
        
        self.last_search_stats['path_length'] = len(path_world)
        
        return path_world
    
    def _astar_search(
        self,
        start: Tuple[int, int, int],
        goal: Tuple[int, int, int]
    ) -> Optional[List[Tuple[int, int, int]]]:
        """A*探索アルゴリズム"""
        
        # 開始ノード作成
        start_node = Node3D(position=start, g_cost=0.0)
        start_node.h_cost = self._heuristic(start, goal)
        
        # オープンリスト（優先度キュー）
        open_list: List[Node3D] = []
        heapq.heappush(open_list, start_node)
        
        # クローズドセット
        closed_set: Set[Tuple[int, int, int]] = set()
        
        # ノードの記録（位置 → ノード）
        all_nodes: Dict[Tuple[int, int, int], Node3D] = {start: start_node}
        
        # 探索ループ
        nodes_explored = 0
        
        while open_list:
            # f_costが最小のノードを取り出し
            current = heapq.heappop(open_list)
            nodes_explored += 1
            
            # ゴール到達チェック
            if current.position == goal:
                self.last_search_stats['nodes_explored'] = nodes_explored
                return self._reconstruct_path(current)
            
            # クローズドセットに追加
            closed_set.add(current.position)
            
            # 近傍ノードを探索
            for neighbor_pos in self._get_neighbors(current.position):
                # クローズド済みならスキップ
                if neighbor_pos in closed_set:
                    continue
                
                # 障害物チェック
                if not self._is_traversable(neighbor_pos):
                    continue
                
                # 移動コスト計算
                move_cost = self._calculate_move_cost(
                    current.position, neighbor_pos
                )
                tentative_g = current.g_cost + move_cost
                
                # 近傍ノードを取得または作成
                if neighbor_pos not in all_nodes:
                    neighbor = Node3D(position=neighbor_pos)
                    neighbor.h_cost = self._heuristic(neighbor_pos, goal)
                    all_nodes[neighbor_pos] = neighbor
                else:
                    neighbor = all_nodes[neighbor_pos]
                
                # より良い経路が見つかった場合
                if tentative_g < neighbor.g_cost:
                    neighbor.parent = current
                    neighbor.g_cost = tentative_g
                    
                    # オープンリストに追加
                    if neighbor not in open_list:
                        heapq.heappush(open_list, neighbor)
        
        # 経路が見つからなかった
        self.last_search_stats['nodes_explored'] = nodes_explored
        print(f"警告: 経路が見つかりませんでした（{nodes_explored}ノード探索）")
        return None
    
    def _heuristic(
        self,
        pos: Tuple[int, int, int],
        goal: Tuple[int, int, int]
    ) -> float:
        """ヒューリスティック関数（ユークリッド距離）"""
        dx = pos[0] - goal[0]
        dy = pos[1] - goal[1]
        dz = pos[2] - goal[2]
        return np.sqrt(dx*dx + dy*dy + dz*dz) * self.voxel_size
    
    def _get_neighbors(
        self,
        pos: Tuple[int, int, int]
    ) -> List[Tuple[int, int, int]]:
        """26近傍を取得"""
        x, y, z = pos
        neighbors = []
        
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                for dz in [-1, 0, 1]:
                    # 自分自身はスキップ
                    if dx == 0 and dy == 0 and dz == 0:
                        continue
                    
                    neighbor = (x + dx, y + dy, z + dz)
                    
                    # グリッド範囲内チェック
                    if self._is_in_grid(neighbor):
                        neighbors.append(neighbor)
        
        return neighbors
    
    def _calculate_move_cost(
        self,
        from_pos: Tuple[int, int, int],
        to_pos: Tuple[int, int, int]
    ) -> float:
        """移動コスト計算（地形データを考慮）"""
        # 基本距離計算
        dx = from_pos[0] - to_pos[0]
        dy = from_pos[1] - to_pos[1]
        dz = from_pos[2] - to_pos[2]
        base_distance = np.sqrt(dx*dx + dy*dy + dz*dz) * self.voxel_size
        
        # コスト計算器を使用しない場合は基本距離のみ
        if not self.use_cost_calculator or self.cost_calculator is None:
            return base_distance
        
        # 地形データがない場合は基本距離のみ
        if self.terrain_data is None:
            return base_distance
        
        # 地形情報取得（将来の実装用の準備）
        # TODO: 実際の地形データから取得
        slope_deg = 0.0
        is_obstacle = False
        risk_score = 0.0
        
        # 統合コスト計算
        total_cost = self.cost_calculator.calculate_total_cost(
            base_distance=base_distance,
            slope_deg=slope_deg,
            is_obstacle=is_obstacle,
            risk_score=risk_score
        )
        
        return total_cost
    
    def _is_traversable(self, pos: Tuple[int, int, int]) -> bool:
        """走行可能チェック（地形データを考慮）"""
        # コスト計算器を使用しない場合は全て走行可能
        if not self.use_cost_calculator or self.cost_calculator is None:
            return True
        
        # 地形データがない場合は全て走行可能
        if self.terrain_data is None:
            return True
        
        # 地形情報取得（将来の実装用の準備）
        # TODO: 実際の地形データから取得
        slope_deg = 0.0
        risk_score = 0.0
        
        # 走行可能性判定
        return self.cost_calculator.get_traversability(slope_deg, risk_score)
    
    def _is_in_grid(self, pos: Tuple[int, int, int]) -> bool:
        """グリッド範囲内チェック"""
        x, y, z = pos
        return (0 <= x < self.grid_size[0] and
                0 <= y < self.grid_size[1] and
                0 <= z < self.grid_size[2])
    
    def _reconstruct_path(
        self,
        node: Node3D
    ) -> List[Tuple[int, int, int]]:
        """経路を復元"""
        path = []
        current = node
        
        while current is not None:
            path.append(current.position)
            current = current.parent
        
        # 逆順なので反転
        path.reverse()
        return path
    
    def _world_to_voxel(
        self,
        pos: Tuple[float, float, float]
    ) -> Tuple[int, int, int]:
        """ワールド座標 → ボクセルインデックス"""
        world_pos = np.array(pos)
        voxel_pos = (world_pos - self.min_bound) / self.voxel_size
        return tuple(voxel_pos.astype(int))
    
    def _voxel_to_world(
        self,
        idx: Tuple[int, int, int]
    ) -> Tuple[float, float, float]:
        """ボクセルインデックス → ワールド座標（ボクセル中心）"""
        voxel_idx = np.array(idx)
        world_pos = self.min_bound + (voxel_idx + 0.5) * self.voxel_size
        return tuple(world_pos)
    
    def get_search_stats(self) -> Dict[str, any]:
        """最後の探索の統計情報を取得"""
        return self.last_search_stats.copy()
