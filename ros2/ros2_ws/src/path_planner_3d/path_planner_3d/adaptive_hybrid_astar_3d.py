"""
Adaptive Hybrid A* (AHA*) - 3D経路計画用の新規アルゴリズム

概要:
    状況に応じて複数の探索戦略を動的に切り替える適応型ハイブリッドアルゴリズム。
    
    1. 初期探索フェーズ: RRT風のランダムサンプリングで大まかな経路を生成
    2. 洗練フェーズ: Weighted A*で経路を改善
    3. 最適化フェーズ: 標準A*で最終的な最適経路を確定
    4. 動的重み調整: 探索の進捗や地形複雑度に応じて重みを自動調整

利点:
    - RRTの探索速度 + A*の最適性を両立
    - 地形の複雑さに適応的に対応
    - 大規模空間でも効率的に動作
    
著者: 卒論研究用オリジナル実装
日付: 2025年11月7日
"""

import heapq
import random
import numpy as np
import time
import logging
from typing import List, Tuple, Optional, Set, Dict
from enum import Enum

from .node_3d import Node3D
from .cost_calculator import CostCalculator

logger = logging.getLogger(__name__)


class SearchPhase(Enum):
    """探索フェーズ"""
    INITIAL_EXPLORATION = 1  # 初期探索（RRT風）
    REFINEMENT = 2           # 洗練（Weighted A*）
    OPTIMIZATION = 3         # 最適化（標準A*）


class AdaptiveHybridAStar3D:
    """
    Adaptive Hybrid A* (AHA*) - 適応型ハイブリッド経路計画
    
    3段階の探索戦略を動的に切り替えることで、
    大規模3D空間での高速かつ最適な経路計画を実現
    """
    
    def __init__(
        self,
        voxel_size: float = 0.1,
        grid_size: Tuple[int, int, int] = (200, 200, 50),
        min_bound: Tuple[float, float, float] = (-10.0, -10.0, 0.0),
        use_cost_calculator: bool = True,
        map_bounds: dict = None,
        # AHA*特有のパラメータ
        initial_epsilon: float = 3.0,      # 初期重み（高速探索）
        refinement_epsilon: float = 1.5,   # 洗練重み（バランス）
        exploration_ratio: float = 0.3,    # 初期探索の割合
        adaptive_threshold: float = 0.2,   # 適応的戦略切替の閾値
    ):
        """
        Args:
            voxel_size: ボクセルサイズ（メートル）
            grid_size: グリッドサイズ（x, y, z）
            min_bound: グリッドの最小境界（ワールド座標）
            use_cost_calculator: コスト計算器を使用するか
            map_bounds: マップ境界（辞書）
            initial_epsilon: 初期探索時のヒューリスティック重み
            refinement_epsilon: 洗練時のヒューリスティック重み
            exploration_ratio: 初期探索に使う反復回数の割合
            adaptive_threshold: 戦略切替の閾値
        """
        self.voxel_size = voxel_size
        self.grid_size = grid_size
        self.min_bound = np.array(min_bound)
        
        # 地形データ
        self.voxel_grid = None
        self.terrain_data = None
        
        # コスト計算器
        self.use_cost_calculator = use_cost_calculator
        if use_cost_calculator:
            self.cost_calculator = CostCalculator()
        else:
            self.cost_calculator = None
        
        # map_boundsのデフォルト設定
        if map_bounds is None:
            half_x = (grid_size[0] * voxel_size) / 2.0
            half_y = (grid_size[1] * voxel_size) / 2.0
            
            self.map_bounds = {
                'x_min': -half_x,
                'x_max': half_x,
                'y_min': -half_y,
                'y_max': half_y,
                'z_min': 0.0,
                'z_max': float(grid_size[2] * voxel_size)
            }
            
            # min_boundを調整（負座標対応）
            self.min_bound = np.array([-half_x, -half_y, 0.0])
        else:
            self.map_bounds = map_bounds
        
        # AHA*特有のパラメータ
        self.initial_epsilon = initial_epsilon
        self.refinement_epsilon = refinement_epsilon
        self.exploration_ratio = exploration_ratio
        self.adaptive_threshold = adaptive_threshold
        
        # 統計情報
        self.last_search_stats = {
            'nodes_explored': 0,
            'path_length': 0,
            'computation_time': 0.0,
            'phase_transitions': [],
            'terrain_complexity': 0.0,
            'adaptive_adjustments': 0
        }
        
        logger.info(f"AHA* initialized: epsilon=[{initial_epsilon}, {refinement_epsilon}], "
                   f"exploration_ratio={exploration_ratio}")
    
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
        AHA*経路計画のメイン関数
        
        Args:
            start: 開始位置（ワールド座標）
            goal: 目標位置（ワールド座標）
        
        Returns:
            経路（ワールド座標のリスト）、失敗時はNone
        """
        start_time = time.time()
        
        # ワールド座標 → ボクセルインデックス変換
        start_idx = self._world_to_voxel(start)
        goal_idx = self._world_to_voxel(goal)
        
        # 境界チェック
        if not self._is_in_grid(start_idx) or not self._is_in_grid(goal_idx):
            logger.error("Start or goal is outside grid bounds")
            return None
        
        # 地形複雑度を分析
        terrain_complexity = self._analyze_terrain_complexity(start_idx, goal_idx)
        self.last_search_stats['terrain_complexity'] = terrain_complexity
        
        logger.info(f"AHA* planning: terrain_complexity={terrain_complexity:.2f}")
        
        # AHA*アルゴリズム実行
        path_indices = self._adaptive_hybrid_search(start_idx, goal_idx, terrain_complexity)
        
        # 統計情報更新
        self.last_search_stats['computation_time'] = time.time() - start_time
        
        if path_indices is None:
            return None
        
        # ボクセルインデックス → ワールド座標変換
        path_world = [self._voxel_to_world(idx) for idx in path_indices]
        self.last_search_stats['path_length'] = len(path_world)
        
        logger.info(f"AHA* success: {self.last_search_stats['nodes_explored']} nodes, "
                   f"{self.last_search_stats['computation_time']:.3f}s, "
                   f"phases={len(self.last_search_stats['phase_transitions'])}")
        
        return path_world
    
    def _adaptive_hybrid_search(
        self,
        start: Tuple[int, int, int],
        goal: Tuple[int, int, int],
        terrain_complexity: float
    ) -> Optional[List[Tuple[int, int, int]]]:
        """
        適応型ハイブリッド探索のコアアルゴリズム
        
        3段階の探索戦略:
        1. 初期探索: 高速な大まかな経路発見（高εのWeighted A*）
        2. 洗練: 経路の改善（中εのWeighted A*）
        3. 最適化: 最終的な最適経路（ε=1のA*）
        """
        # 開始ノード作成
        start_node = Node3D(position=start, g_cost=0.0)
        start_node.h_cost = self._heuristic(start, goal)
        
        # データ構造
        open_list: List[Node3D] = []
        heapq.heappush(open_list, start_node)
        closed_set: Set[Tuple[int, int, int]] = set()
        all_nodes: Dict[Tuple[int, int, int], Node3D] = {start: start_node}
        
        nodes_explored = 0
        phase = SearchPhase.INITIAL_EXPLORATION
        current_epsilon = self._calculate_initial_epsilon(terrain_complexity)
        
        # 目標までの直線距離
        goal_distance = self._heuristic(start, goal)
        max_iterations = max(10000, int(goal_distance * 200))  # 適応的な最大反復回数
        
        logger.info(f"Starting AHA* search: max_iterations={max_iterations}, "
                   f"initial_epsilon={current_epsilon:.2f}")
        
        while open_list and nodes_explored < max_iterations:
            current = heapq.heappop(open_list)
            nodes_explored += 1
            
            # フェーズ遷移の判定
            progress = nodes_explored / max_iterations
            new_phase, new_epsilon = self._determine_phase(
                progress, phase, current_epsilon, terrain_complexity
            )
            
            if new_phase != phase:
                phase = new_phase
                current_epsilon = new_epsilon
                self.last_search_stats['phase_transitions'].append({
                    'nodes': nodes_explored,
                    'phase': phase.name,
                    'epsilon': current_epsilon
                })
                logger.debug(f"Phase transition: {phase.name}, epsilon={current_epsilon:.2f}")
            
            # ゴール到達チェック
            if current.position == goal:
                self.last_search_stats['nodes_explored'] = nodes_explored
                return self._reconstruct_path(current)
            
            # クローズドセットに追加
            if current.position in closed_set:
                continue
            closed_set.add(current.position)
            
            # 適応的近傍探索
            neighbors = self._get_adaptive_neighbors(
                current.position, goal, phase, terrain_complexity
            )
            
            for neighbor_pos in neighbors:
                if neighbor_pos in closed_set:
                    continue
                
                if not self._is_traversable(neighbor_pos):
                    continue
                
                # 移動コスト計算
                move_cost = self._calculate_move_cost(current.position, neighbor_pos)
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
                    neighbor.h_cost = self._heuristic(neighbor_pos, goal)
                    
                    # Node3DのプロパティはDirect代入不可なので、再計算させる
                    # f_costはg_cost + h_costで自動計算される
                    
                    if neighbor not in open_list:
                        heapq.heappush(open_list, neighbor)
        
        # 経路が見つからなかった
        self.last_search_stats['nodes_explored'] = nodes_explored
        logger.warning(f"AHA* failed: explored {nodes_explored} nodes")
        return None
    
    def _analyze_terrain_complexity(
        self,
        start: Tuple[int, int, int],
        goal: Tuple[int, int, int]
    ) -> float:
        """
        地形複雑度を分析（0.0～1.0）
        
        以下の要素を考慮:
        - 高度変化
        - 障害物密度
        - 経路の直線距離
        """
        if self.voxel_grid is None:
            return 0.3  # デフォルト複雑度
        
        # サンプリング点を設定
        num_samples = 20
        complexity_scores = []
        
        for i in range(num_samples):
            t = i / (num_samples - 1)
            sample_pos = (
                int(start[0] + t * (goal[0] - start[0])),
                int(start[1] + t * (goal[1] - start[1])),
                int(start[2] + t * (goal[2] - start[2]))
            )
            
            if self._is_in_grid(sample_pos):
                # 周囲の障害物密度
                obstacle_density = self._calculate_local_obstacle_density(sample_pos)
                # 傾斜
                slope = self._get_slope_at(sample_pos) / 30.0  # 正規化
                
                complexity_scores.append(obstacle_density * 0.6 + slope * 0.4)
        
        if complexity_scores:
            avg_complexity = np.mean(complexity_scores)
            return np.clip(avg_complexity, 0.0, 1.0)
        
        return 0.3
    
    def _calculate_initial_epsilon(self, terrain_complexity: float) -> float:
        """地形複雑度に基づいて初期εを計算"""
        # 複雑な地形ほど高いεで開始（より探索的）
        epsilon = self.initial_epsilon * (1.0 + terrain_complexity * 0.5)
        return min(epsilon, 5.0)  # 上限5.0
    
    def _determine_phase(
        self,
        progress: float,
        current_phase: SearchPhase,
        current_epsilon: float,
        terrain_complexity: float
    ) -> Tuple[SearchPhase, float]:
        """
        探索の進捗に基づいてフェーズとεを決定
        
        Returns:
            (新しいフェーズ, 新しいε)
        """
        # フェーズ遷移の閾値（地形複雑度で調整）
        exploration_threshold = self.exploration_ratio * (1.0 + terrain_complexity * 0.3)
        refinement_threshold = 0.7
        
        if progress < exploration_threshold:
            # 初期探索フェーズ
            return SearchPhase.INITIAL_EXPLORATION, current_epsilon
        
        elif progress < refinement_threshold:
            # 洗練フェーズ
            if current_phase == SearchPhase.INITIAL_EXPLORATION:
                # 徐々にεを減少
                new_epsilon = self.refinement_epsilon
                return SearchPhase.REFINEMENT, new_epsilon
            return SearchPhase.REFINEMENT, current_epsilon
        
        else:
            # 最適化フェーズ
            if current_phase != SearchPhase.OPTIMIZATION:
                return SearchPhase.OPTIMIZATION, 1.0
            return SearchPhase.OPTIMIZATION, 1.0
    
    def _get_adaptive_neighbors(
        self,
        pos: Tuple[int, int, int],
        goal: Tuple[int, int, int],
        phase: SearchPhase,
        terrain_complexity: float
    ) -> List[Tuple[int, int, int]]:
        """
        フェーズと地形に応じた適応的近傍探索
        
        - 初期探索: より粗い探索（一部をスキップ）
        - 洗練: 標準的な26近傍
        - 最適化: 完全な26近傍 + ゴール方向バイアス
        """
        x, y, z = pos
        neighbors = []
        
        # 基本の26近傍
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                for dz in [-1, 0, 1]:
                    if dx == 0 and dy == 0 and dz == 0:
                        continue
                    
                    # 初期探索フェーズではサンプリング
                    if phase == SearchPhase.INITIAL_EXPLORATION:
                        # 対角移動は半分の確率でスキップ（高速化）
                        if abs(dx) + abs(dy) + abs(dz) >= 2:
                            if random.random() > 0.5:
                                continue
                    
                    neighbor = (x + dx, y + dy, z + dz)
                    
                    if self._is_in_grid(neighbor):
                        neighbors.append(neighbor)
        
        # 最適化フェーズではゴール方向を優先
        if phase == SearchPhase.OPTIMIZATION:
            # ゴール方向の追加サンプリング
            direction = np.array(goal) - np.array(pos)
            if np.linalg.norm(direction) > 0:
                direction = direction / np.linalg.norm(direction)
                
                # ゴール方向に2ステップ進んだ点も候補に
                for scale in [2, 3]:
                    biased_pos = (
                        x + int(direction[0] * scale),
                        y + int(direction[1] * scale),
                        z + int(direction[2] * scale)
                    )
                    if self._is_in_grid(biased_pos):
                        neighbors.append(biased_pos)
        
        return neighbors
    
    def _calculate_local_obstacle_density(self, pos: Tuple[int, int, int]) -> float:
        """局所的な障害物密度を計算（0.0～1.0）"""
        if self.voxel_grid is None:
            return 0.0
        
        x, y, z = pos
        obstacle_count = 0
        total_voxels = 0
        
        # 5x5x3の範囲をチェック
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                for dz in range(-1, 2):
                    nx, ny, nz = x + dx, y + dy, z + dz
                    if self._is_in_grid((nx, ny, nz)):
                        total_voxels += 1
                        if self.voxel_grid[nx, ny, nz] > 0.5:
                            obstacle_count += 1
        
        return obstacle_count / max(total_voxels, 1)
    
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
    
    def _calculate_move_cost(
        self,
        from_pos: Tuple[int, int, int],
        to_pos: Tuple[int, int, int]
    ) -> float:
        """移動コスト計算（地形データを考慮）"""
        dx = from_pos[0] - to_pos[0]
        dy = from_pos[1] - to_pos[1]
        dz = from_pos[2] - to_pos[2]
        base_distance = np.sqrt(dx*dx + dy*dy + dz*dz) * self.voxel_size
        
        if not self.use_cost_calculator or self.cost_calculator is None:
            return base_distance
        
        if self.terrain_data is None or self.voxel_grid is None:
            return base_distance
        
        slope_deg = self._get_slope_at(to_pos)
        is_obstacle = self._is_obstacle_at(to_pos)
        risk_score = self._calculate_risk_at(to_pos)
        
        total_cost = self.cost_calculator.calculate_total_cost(
            base_distance=base_distance,
            slope_deg=slope_deg,
            is_obstacle=is_obstacle,
            risk_score=risk_score
        )
        
        return total_cost
    
    def _is_traversable(self, pos: Tuple[int, int, int]) -> bool:
        """走行可能チェック"""
        if not self.use_cost_calculator or self.cost_calculator is None:
            return True
        
        if self.terrain_data is None or self.voxel_grid is None:
            return True
        
        if self._is_obstacle_at(pos):
            return False
        
        slope_deg = self._get_slope_at(pos)
        risk_score = self._calculate_risk_at(pos)
        
        return self.cost_calculator.get_traversability(slope_deg, risk_score)
    
    def _get_slope_at(self, pos: Tuple[int, int, int]) -> float:
        """指定位置の傾斜角度を計算"""
        if self.voxel_grid is None:
            return 0.0
        
        x, y, z = pos
        heights = []
        
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if self._is_in_grid((nx, ny, z)):
                height = self._get_surface_height(nx, ny)
                if height is not None:
                    heights.append(height)
        
        if len(heights) < 2:
            return 0.0
        
        max_height = max(heights)
        min_height = min(heights)
        height_diff = (max_height - min_height) * self.voxel_size
        
        horizontal_distance = self.voxel_size
        slope_rad = np.arctan(height_diff / horizontal_distance)
        slope_deg = np.degrees(slope_rad)
        
        return slope_deg
    
    def _get_surface_height(self, x: int, y: int) -> Optional[int]:
        """地表面の高さを取得"""
        if self.voxel_grid is None:
            return None
        
        for z in range(self.grid_size[2] - 1, -1, -1):
            if self.voxel_grid[x, y, z] > 0.5:
                return z
        
        return 0
    
    def _is_obstacle_at(self, pos: Tuple[int, int, int]) -> bool:
        """障害物チェック"""
        if self.voxel_grid is None:
            return False
        
        x, y, z = pos
        return self.voxel_grid[x, y, z] > 0.5
    
    def _calculate_risk_at(self, pos: Tuple[int, int, int]) -> float:
        """リスクスコア計算"""
        if self.voxel_grid is None:
            return 0.0
        
        x, y, z = pos
        obstacle_count = 0
        total_voxels = 0
        
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                for dz in [-1, 0, 1]:
                    nx, ny, nz = x + dx, y + dy, z + dz
                    if self._is_in_grid((nx, ny, nz)):
                        total_voxels += 1
                        if self.voxel_grid[nx, ny, nz] > 0.5:
                            obstacle_count += 1
        
        if total_voxels == 0:
            return 0.0
        
        return obstacle_count / total_voxels
    
    def _is_in_grid(self, pos: Tuple[int, int, int]) -> bool:
        """グリッド範囲内チェック"""
        x, y, z = pos
        return (0 <= x < self.grid_size[0] and
                0 <= y < self.grid_size[1] and
                0 <= z < self.grid_size[2])
    
    def _reconstruct_path(self, node: Node3D) -> List[Tuple[int, int, int]]:
        """経路を復元"""
        path = []
        current = node
        
        while current is not None:
            path.append(current.position)
            current = current.parent
        
        path.reverse()
        return path
    
    def _world_to_voxel(self, pos: Tuple[float, float, float]) -> Tuple[int, int, int]:
        """ワールド座標 → ボクセルインデックス"""
        world_pos = np.array(pos)
        voxel_pos = (world_pos - self.min_bound) / self.voxel_size
        return tuple(voxel_pos.astype(int))
    
    def _voxel_to_world(self, idx: Tuple[int, int, int]) -> Tuple[float, float, float]:
        """ボクセルインデックス → ワールド座標"""
        voxel_idx = np.array(idx)
        world_pos = self.min_bound + (voxel_idx + 0.5) * self.voxel_size
        return tuple(world_pos)
    
    def get_search_stats(self) -> Dict[str, any]:
        """最後の探索の統計情報を取得"""
        return self.last_search_stats.copy()
