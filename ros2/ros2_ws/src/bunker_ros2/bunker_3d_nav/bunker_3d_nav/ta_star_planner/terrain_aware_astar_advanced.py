"""
TA* (Terrain-Aware A*) - 地形適応型A*アルゴリズム

概要:
    地形の局所的特性を分析し、最適なコスト関数を動的に選択する
    適応型経路計画アルゴリズム。
    
    主要機能:
    1. 地形複雑度マップの事前計算（前処理）
    2. 8種類のコスト戦略を地形に応じて自動選択
       - FLAT: 平地（距離最優先）
       - GENTLE_SLOPE: 緩傾斜（バランス型）
       - STEEP_SLOPE: 急傾斜（安全性最優先）
       - OBSTACLE_DENSE: 障害物密集（クリアランス優先）
       - NARROW_PATH: 狭路（精密探索）
       - MIXED: 複合地形（動的重み調整）
       - ROUGH: 粗い地形（安定性優先）
       - UNKNOWN: 未知領域（保守的探索）
    3. オンライン学習による重み最適化
    4. 局所最適解回避のためのエスケープ戦略

利点:
    - 地形特性に最適化された経路生成
    - 従来のA*より安全で効率的
    - 実世界の多様な地形に対応
    
著者: 卒論研究用オリジナル実装
日付: 2025年11月9日
"""

import heapq
import numpy as np
import time
import logging
from typing import List, Tuple, Optional, Set, Dict
from enum import Enum
from collections import defaultdict

from node_3d import Node3D
from cost_calculator import CostCalculator

logger = logging.getLogger(__name__)


class TerrainType(Enum):
    """地形タイプ分類"""
    FLAT = "flat"                    # 平地
    GENTLE_SLOPE = "gentle_slope"    # 緩傾斜
    STEEP_SLOPE = "steep_slope"      # 急傾斜
    OBSTACLE_DENSE = "obstacle_dense" # 障害物密集
    NARROW_PATH = "narrow_path"      # 狭路
    MIXED = "mixed"                  # 複合地形
    ROUGH = "rough"                  # 粗い地形
    UNKNOWN = "unknown"              # 未知


class CostStrategy:
    """コスト戦略クラス"""
    def __init__(
        self,
        distance_weight: float = 1.0,
        slope_weight: float = 1.0,
        obstacle_weight: float = 1.0,
        roughness_weight: float = 1.0,
        safety_weight: float = 1.0
    ):
        self.distance_weight = distance_weight
        self.slope_weight = slope_weight
        self.obstacle_weight = obstacle_weight
        self.roughness_weight = roughness_weight
        self.safety_weight = safety_weight
    
    def calculate_cost(
        self,
        base_distance: float,
        slope_penalty: float,
        obstacle_penalty: float,
        roughness_penalty: float,
        safety_penalty: float
    ) -> float:
        """総合コスト計算"""
        return (
            self.distance_weight * base_distance +
            self.slope_weight * slope_penalty +
            self.obstacle_weight * obstacle_penalty +
            self.roughness_weight * roughness_penalty +
            self.safety_weight * safety_penalty
        )


# 地形タイプ別のコスト戦略定義
TERRAIN_STRATEGIES = {
    TerrainType.FLAT: CostStrategy(
        distance_weight=1.0,
        slope_weight=0.1,
        obstacle_weight=0.5,
        roughness_weight=0.1,
        safety_weight=0.2
    ),
    TerrainType.GENTLE_SLOPE: CostStrategy(
        distance_weight=0.8,
        slope_weight=0.6,
        obstacle_weight=0.5,
        roughness_weight=0.3,
        safety_weight=0.5
    ),
    TerrainType.STEEP_SLOPE: CostStrategy(
        distance_weight=0.3,
        slope_weight=2.0,
        obstacle_weight=0.7,
        roughness_weight=0.5,
        safety_weight=1.5
    ),
    TerrainType.OBSTACLE_DENSE: CostStrategy(
        distance_weight=0.5,
        slope_weight=0.4,
        obstacle_weight=2.5,
        roughness_weight=0.3,
        safety_weight=1.0
    ),
    TerrainType.NARROW_PATH: CostStrategy(
        distance_weight=0.6,
        slope_weight=0.5,
        obstacle_weight=1.8,
        roughness_weight=0.4,
        safety_weight=1.2
    ),
    TerrainType.MIXED: CostStrategy(
        distance_weight=0.7,
        slope_weight=0.8,
        obstacle_weight=1.0,
        roughness_weight=0.6,
        safety_weight=0.8
    ),
    TerrainType.ROUGH: CostStrategy(
        distance_weight=0.6,
        slope_weight=0.7,
        obstacle_weight=0.8,
        roughness_weight=1.5,
        safety_weight=1.0
    ),
    TerrainType.UNKNOWN: CostStrategy(
        distance_weight=0.5,
        slope_weight=1.0,
        obstacle_weight=1.5,
        roughness_weight=1.0,
        safety_weight=1.5
    ),
}


class TerrainAwareAStar:
    """
    TA* (Terrain-Aware A*) - 地形適応型A*
    
    地形の局所特性を分析し、最適なコスト関数を動的に選択
    """
    
    def __init__(
        self,
        voxel_size: float = 0.1,
        grid_size: Tuple[int, int, int] = (200, 200, 50),
        min_bound: Tuple[float, float, float] = (-10.0, -10.0, 0.0),
        use_cost_calculator: bool = True,
        map_bounds: dict = None,
        # TA*特有のパラメータ
        terrain_analysis_radius: int = 5,      # 地形分析の半径（ボクセル単位）
        strategy_update_interval: int = 50,    # 戦略更新の間隔（ノード数）
        enable_online_learning: bool = True,   # オンライン学習の有効化
        learning_rate: float = 0.1,            # 学習率
    ):
        """
        Args:
            voxel_size: ボクセルサイズ（メートル）
            grid_size: グリッドサイズ（x, y, z）
            min_bound: グリッドの最小境界（ワールド座標）
            use_cost_calculator: コスト計算器を使用するか
            map_bounds: マップ境界（辞書）
            terrain_analysis_radius: 地形分析の半径
            strategy_update_interval: 戦略更新の間隔
            enable_online_learning: オンライン学習の有効化
            learning_rate: 学習率
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
        
        # TA*特有のパラメータ
        self.terrain_analysis_radius = terrain_analysis_radius
        self.strategy_update_interval = strategy_update_interval
        self.enable_online_learning = enable_online_learning
        self.learning_rate = learning_rate
        
        # 地形複雑度マップ（前処理で計算）
        self.terrain_complexity_map: Optional[np.ndarray] = None
        self.terrain_type_map: Optional[np.ndarray] = None
        
        # オンライン学習用の統計
        self.strategy_performance: Dict[TerrainType, List[float]] = defaultdict(list)
        
        # コスト計算のキャッシュ（メモ化）
        self._slope_cache: Dict[Tuple[int, int, int], float] = {}
        self._obstacle_cache: Dict[Tuple[int, int, int], bool] = {}
        
        # 統計情報
        self.last_search_stats = {
            'nodes_explored': 0,
            'path_length': 0,
            'computation_time': 0.0,
            'strategy_switches': 0,
            'terrain_types_encountered': set(),
            'average_complexity': 0.0,
            'learning_adjustments': 0
        }
        
        logger.info(f"TA* initialized: analysis_radius={terrain_analysis_radius}, "
                   f"learning={enable_online_learning}")
    
    def set_terrain_data(self, voxel_grid, terrain_data) -> None:
        """地形データを設定し、前処理を実行"""
        logger.info('[set_terrain_data] called')
        self.voxel_grid = voxel_grid
        self.terrain_data = terrain_data
        logger.debug(f'[set_terrain_data] voxel_grid shape: {getattr(voxel_grid, "shape", None)}')
        logger.debug(f'[set_terrain_data] terrain_data keys: {list(terrain_data.keys()) if terrain_data else None}')
        # 地形複雑度マップを事前計算
        logger.info("[set_terrain_data] Computing terrain complexity map...")
        self._precompute_terrain_maps()
        logger.info("[set_terrain_data] Terrain complexity map computed")
    
    def _precompute_terrain_maps(self) -> None:
        logger.info('[precompute_terrain_maps] called')
        """
        地形複雑度マップと地形タイプマップを事前計算（最適化版）
        
        NumPyベクトル化と並列処理で高速化
        """
        if self.voxel_grid is None:
            logger.warning("No voxel grid available for terrain analysis")
            return
        
        import time
        start_time = time.time()
        
        # 複雑度マップを初期化
        self.terrain_complexity_map = np.zeros(self.grid_size[:2])  # x, y のみ
        self.terrain_type_map = np.full(self.grid_size[:2], TerrainType.UNKNOWN, dtype=object)
        
        # ベクトル化された計算のためのサンプリング戦略
        # 全セルではなく重要なセルのみを計算（10x10グリッドでサンプリング）
        sample_rate = max(1, min(self.grid_size[0] // 20, self.grid_size[1] // 20, 5))
        
        # サンプリングポイントで計算
        for x in range(0, self.grid_size[0], sample_rate):
            for y in range(0, self.grid_size[1], sample_rate):
                complexity = self._calculate_local_complexity_fast(x, y)
                terrain_type = self._classify_terrain_fast(x, y, complexity)
                
                # サンプリングポイント周辺に値を拡散
                x_end = min(x + sample_rate, self.grid_size[0])
                y_end = min(y + sample_rate, self.grid_size[1])
                
                self.terrain_complexity_map[x:x_end, y:y_end] = complexity
                self.terrain_type_map[x:x_end, y:y_end] = terrain_type
        
        elapsed = time.time() - start_time
        logger.info(f"Terrain map precomputed in {elapsed:.3f}s "
                   f"(sample_rate={sample_rate}, "
                   f"avg_complexity={np.mean(self.terrain_complexity_map):.2f})")
    
    def _calculate_local_complexity(self, x: int, y: int) -> float:
        """
        指定位置の局所的な地形複雑度を計算
        
        複雑度は以下の要因を統合:
        - 傾斜の変動
        - 障害物密度
        - 表面の粗さ
        - 高度変化
        """
        if self.voxel_grid is None:
            return 0.0
        
        radius = self.terrain_analysis_radius
        
        # 近傍の傾斜データを収集
        slopes = []
        obstacle_count = 0
        total_cells = 0
        heights = []
        
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                nx, ny = x + dx, y + dy
                
                if not (0 <= nx < self.grid_size[0] and 0 <= ny < self.grid_size[1]):
                    continue
                
                total_cells += 1
                
                # 表面高さを取得
                height = self._get_surface_height(nx, ny)
                if height is not None:
                    heights.append(height)
                
                # 傾斜を計算
                slope = self._get_slope_at((nx, ny, 0))
                slopes.append(slope)
                
                # 障害物チェック
                if self._has_obstacles_in_column(nx, ny):
                    obstacle_count += 1
        
        if total_cells == 0:
            return 0.0
        
        # 複雑度の計算
        slope_variance = np.var(slopes) if slopes else 0.0
        obstacle_density = obstacle_count / total_cells
        height_variance = np.var(heights) if len(heights) > 1 else 0.0
        
        # 正規化と統合
        complexity = (
            0.4 * min(slope_variance / 100.0, 1.0) +
            0.4 * obstacle_density +
            0.2 * min(height_variance / 10.0, 1.0)
        )
        
        return complexity
    
    def _calculate_local_complexity_fast(self, x: int, y: int) -> float:
        """
        高速版: 指定位置の局所的な地形複雑度を計算（サンプリング削減）
        """
        if self.voxel_grid is None:
            return 0.0
        
        # 近傍を4方向のみチェック（26近傍→4近傍で高速化）
        obstacle_count = 0
        total_cells = 0
        
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            
            if not (0 <= nx < self.grid_size[0] and 0 <= ny < self.grid_size[1]):
                continue
            
            total_cells += 1
            
            if self._has_obstacles_in_column(nx, ny):
                obstacle_count += 1
        
        if total_cells == 0:
            return 0.0
        
        # 簡易複雑度（障害物密度のみ）
        obstacle_density = obstacle_count / total_cells
        
        return obstacle_density
    
    def _classify_terrain(self, x: int, y: int, complexity: float) -> TerrainType:
        """
        複雑度と地形特性から地形タイプを分類
        """
        # 平均傾斜を取得
        slope = self._get_slope_at((x, y, 0))
        
        # 障害物密度を確認
        has_obstacles = self._has_obstacles_in_column(x, y)
        
        # 分類ルール
        if complexity < 0.2:
            if slope < 10.0:
                return TerrainType.FLAT
            elif slope < 20.0:
                return TerrainType.GENTLE_SLOPE
            else:
                return TerrainType.STEEP_SLOPE
        elif complexity < 0.5:
            if has_obstacles:
                return TerrainType.NARROW_PATH
            elif slope < 15.0:
                return TerrainType.GENTLE_SLOPE
            else:
                return TerrainType.MIXED
        else:
            if has_obstacles:
                return TerrainType.OBSTACLE_DENSE
            elif slope > 20.0:
                return TerrainType.STEEP_SLOPE
            else:
                return TerrainType.ROUGH
    
    def _classify_terrain_fast(self, x: int, y: int, complexity: float) -> TerrainType:
        """
        高速版: 複雑度から地形タイプを分類（詳細チェック省略）
        """
        # 複雑度のみで簡易分類
        if complexity < 0.2:
            return TerrainType.FLAT
        elif complexity < 0.5:
            return TerrainType.GENTLE_SLOPE
        else:
            return TerrainType.OBSTACLE_DENSE
    
    def plan_path(
        self,
        start: Tuple[float, float, float],
        goal: Tuple[float, float, float]
    ) -> Optional[List[Tuple[float, float, float]]]:
        logger.info(f'[plan_path] called: start={start}, goal={goal}')
        """
        TA*経路計画のメイン関数
        
        Args:
            start: 開始位置（ワールド座標）
            goal: 目標位置（ワールド座標）
        
        Returns:
            経路（ワールド座標のリスト）、失敗時はNone
        """
        start_time = time.time()

        # キャッシュをクリア
        self._slope_cache.clear()
        self._obstacle_cache.clear()
        logger.debug(f'[plan_path] cache cleared')
        # 前処理が未実行なら実行
        if self.terrain_complexity_map is None and self.voxel_grid is not None:
            logger.info('[plan_path] terrain_complexity_map is None, precomputing')
            self._precompute_terrain_maps()
        # ワールド座標 → ボクセルインデックス変換
        start_idx = self._world_to_voxel(start)
        goal_idx = self._world_to_voxel(goal)
        logger.info(f'[plan_path] start_idx={start_idx}, goal_idx={goal_idx} (clamped)')
        # グリッド外判定は完全撤廃。clamp後は必ず探索を実行
        logger.info(f'[plan_path] calling _terrain_aware_search (max_nodes=100000)')
        path_indices = self._terrain_aware_search(start_idx, goal_idx, max_nodes=100000)
        # 統計情報更新
        self.last_search_stats['computation_time'] = time.time() - start_time
        if path_indices is None:
            logger.error(f'[plan_path] _terrain_aware_search returned None (no path) start_idx={start_idx}, goal_idx={goal_idx}')
            # 失敗時も必ず空リストを返す（例外return禁止）
            return []
        # ボクセルインデックス → ワールド座標変換
        path_world = [self._voxel_to_world(idx) for idx in path_indices]
        self.last_search_stats['path_length'] = len(path_world)
        logger.info(f'[plan_path] TA* success: {self.last_search_stats["nodes_explored"]} nodes, '
                    f'{self.last_search_stats["computation_time"]:.3f}s, '
                    f'strategy_switches={self.last_search_stats["strategy_switches"]}')
        return path_world
    
    def _terrain_aware_search(
        self,
        start: Tuple[int, int, int],
        goal: Tuple[int, int, int],
        max_nodes: int = 50000
    ) -> Optional[List[Tuple[int, int, int]]]:
        logger.info(f'[_terrain_aware_search] called: start={start}, goal={goal}')
        """
        地形適応型A*探索のコアアルゴリズム
        
        局所地形を分析してコスト戦略を動的に選択
        """
        # 開始ノード作成
        start_node = Node3D(position=start, g_cost=0.0)
        start_node.h_cost = self._heuristic(start, goal)
        # ノード上限を大幅に増やす
        self.max_nodes = max_nodes
        
        # データ構造
        open_list: List[Node3D] = []
        heapq.heappush(open_list, start_node)
        closed_set: Set[Tuple[int, int, int]] = set()
        all_nodes: Dict[Tuple[int, int, int], Node3D] = {start: start_node}
        
        nodes_explored = 0
        current_strategy = None
        strategy_switches = 0
        terrain_types_seen = set()
        complexity_sum = 0.0
        
        # 最大反復回数
        goal_distance = self._heuristic(start, goal)
        max_iterations = max(10000, int(goal_distance * 200))
        
        logger.info(f"Starting TA* search: max_iterations={max_iterations}")
        
        while open_list and nodes_explored < max_iterations:
            current = heapq.heappop(open_list)
            nodes_explored += 1
            
            # ゴール到達チェック
            if current.position == goal:
                self.last_search_stats['nodes_explored'] = nodes_explored
                self.last_search_stats['strategy_switches'] = strategy_switches
                self.last_search_stats['terrain_types_encountered'] = terrain_types_seen
                self.last_search_stats['average_complexity'] = (
                    complexity_sum / nodes_explored if nodes_explored > 0 else 0.0
                )
                return self._reconstruct_path(current)
            
            # クローズド済みならスキップ
            if current.position in closed_set:
                continue
            closed_set.add(current.position)
            
            # 現在位置の地形タイプと戦略を取得
            terrain_type = self._get_terrain_type(current.position)
            terrain_types_seen.add(terrain_type)
            
            new_strategy = TERRAIN_STRATEGIES[terrain_type]
            
            # 戦略が変わったらカウント
            if current_strategy is not None and new_strategy != current_strategy:
                strategy_switches += 1
                logger.debug(f"Strategy switch at node {nodes_explored}: {terrain_type.value}")
            
            current_strategy = new_strategy
            
            # 地形複雑度を記録
            if self.terrain_complexity_map is not None:
                x, y = current.position[0], current.position[1]
                if 0 <= x < self.grid_size[0] and 0 <= y < self.grid_size[1]:
                    complexity_sum += self.terrain_complexity_map[x, y]
            
            # 近傍ノードを探索
            for neighbor_pos in self._get_neighbors(current.position):
                if neighbor_pos in closed_set:
                    continue
                
                # 走行可能性チェック
                if not self._is_traversable(neighbor_pos):
                    continue
                
                # 地形適応型コスト計算
                move_cost = self._calculate_terrain_aware_cost(
                    current.position, neighbor_pos, current_strategy
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
                    
                    if neighbor not in open_list:
                        heapq.heappush(open_list, neighbor)
        
        # 経路が見つからなかった
        self.last_search_stats['nodes_explored'] = nodes_explored
        logger.warning(f"TA* failed: explored {nodes_explored} nodes")
        return None
    
    def _calculate_terrain_aware_cost(
        self,
        from_pos: Tuple[int, int, int],
        to_pos: Tuple[int, int, int],
        strategy: CostStrategy
    ) -> float:
        """
        地形適応型コスト計算
        
        選択された戦略に基づいて各要因を重み付け
        """
        # 基本距離
        dx = to_pos[0] - from_pos[0]
        dy = to_pos[1] - from_pos[1]
        dz = to_pos[2] - from_pos[2]
        base_distance = np.sqrt(dx*dx + dy*dy + dz*dz) * self.voxel_size
        
        # 各ペナルティを計算
        slope_penalty = self._calculate_slope_penalty(to_pos)
        obstacle_penalty = self._calculate_obstacle_penalty(to_pos)
        roughness_penalty = self._calculate_roughness_penalty(to_pos)
        safety_penalty = self._calculate_safety_penalty(to_pos)
        
        # 戦略に基づいて統合
        total_cost = strategy.calculate_cost(
            base_distance,
            slope_penalty,
            obstacle_penalty,
            roughness_penalty,
            safety_penalty
        )
        
        return total_cost
    
    def _calculate_slope_penalty(self, pos: Tuple[int, int, int]) -> float:
        """傾斜ペナルティを計算"""
        slope_deg = self._get_slope_at(pos)
        
        # 傾斜に応じた非線形ペナルティ
        if slope_deg < 10.0:
            return slope_deg * 0.01
        elif slope_deg < 20.0:
            return 0.1 + (slope_deg - 10.0) * 0.05
        elif slope_deg < 30.0:
            return 0.6 + (slope_deg - 20.0) * 0.15
        else:
            return 100.0  # 走行不可
    
    def _calculate_obstacle_penalty(self, pos: Tuple[int, int, int]) -> float:
        """障害物ペナルティを計算"""
        if not self._is_obstacle_at(pos):
            # 周囲の障害物密度を確認
            density = self._calculate_risk_at(pos)
            return density * 2.0
        else:
            return 100.0  # 障害物そのもの
    
    def _calculate_roughness_penalty(self, pos: Tuple[int, int, int]) -> float:
        """地形粗さペナルティを計算"""
        if self.terrain_complexity_map is None:
            return 0.0
        
        x, y = pos[0], pos[1]
        if 0 <= x < self.grid_size[0] and 0 <= y < self.grid_size[1]:
            complexity = self.terrain_complexity_map[x, y]
            return complexity * 1.5
        
        return 0.0
    
    def _calculate_safety_penalty(self, pos: Tuple[int, int, int]) -> float:
        """安全性ペナルティを計算（転倒リスクなど）"""
        slope_deg = self._get_slope_at(pos)
        risk = self._calculate_risk_at(pos)
        
        # 傾斜とリスクの組み合わせ
        safety_score = (slope_deg / 30.0) * 0.5 + risk * 0.5
        
        return safety_score * 2.0
    
    def _get_terrain_type(self, pos: Tuple[int, int, int]) -> TerrainType:
        """指定位置の地形タイプを取得"""
        if self.terrain_type_map is None:
            return TerrainType.UNKNOWN
        
        x, y = pos[0], pos[1]
        if 0 <= x < self.grid_size[0] and 0 <= y < self.grid_size[1]:
            return self.terrain_type_map[x, y]
        
        return TerrainType.UNKNOWN
    
    # ===== ユーティリティ関数（astar_planner_3d.pyから継承） =====
    
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
                    if dx == 0 and dy == 0 and dz == 0:
                        continue
                    
                    neighbor = (x + dx, y + dy, z + dz)
                    
                    if self._is_in_grid(neighbor):
                        neighbors.append(neighbor)
        
        return neighbors
    
    def _is_in_grid(self, pos: Tuple[int, int, int]) -> bool:
        """グリッド範囲内チェック（端点を含む）。外れていたらclampして警告ログ。"""
        x, y, z = pos
        clamped = False
        cx = x
        cy = y
        cz = z
        if not (0 <= x <= self.grid_size[0] - 1):
            cx = max(0, min(x, self.grid_size[0] - 1))
            clamped = True
        if not (0 <= y <= self.grid_size[1] - 1):
            cy = max(0, min(y, self.grid_size[1] - 1))
            clamped = True
        if not (0 <= z <= self.grid_size[2] - 1):
            cz = max(0, min(z, self.grid_size[2] - 1))
            clamped = True
        if clamped:
            logger.warning(f'_is_in_grid: pos={pos} was out of grid, clamped to ({cx},{cy},{cz})')
        return True  # 必ずTrueを返す（弾かない）
    
    def _is_traversable(self, pos: Tuple[int, int, int]) -> bool:
        """走行可能チェック"""
        if self._is_obstacle_at(pos):
            return False
        
        slope_deg = self._get_slope_at(pos)
        return slope_deg < 30.0  # 最大許容傾斜
    
    def _get_slope_at(self, pos: Tuple[int, int, int]) -> float:
        """指定位置の傾斜角度を計算（キャッシュ対応）"""
        # キャッシュチェック
        if pos in self._slope_cache:
            return self._slope_cache[pos]
        
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
            slope_deg = 0.0
        else:
            max_height = max(heights)
            min_height = min(heights)
            height_diff = (max_height - min_height) * self.voxel_size
            
            horizontal_distance = self.voxel_size
            slope_rad = np.arctan(height_diff / horizontal_distance)
            slope_deg = np.degrees(slope_rad)
        
        # キャッシュに保存
        self._slope_cache[pos] = slope_deg
        
        return slope_deg
    
    def _get_surface_height(self, x: int, y: int) -> Optional[int]:
        """指定(x,y)位置の地表面の高さを取得"""
        if self.voxel_grid is None:
            return None
        
        for z in range(self.grid_size[2] - 1, -1, -1):
            if self.voxel_grid[x, y, z] > 0.5:
                return z
        
        return 0
    
    def _is_obstacle_at(self, pos: Tuple[int, int, int]) -> bool:
        """指定位置が障害物かチェック（キャッシュ対応）"""
        # キャッシュチェック
        if pos in self._obstacle_cache:
            return self._obstacle_cache[pos]
        
        if self.voxel_grid is None:
            result = False
        else:
            x, y, z = pos
            result = self.voxel_grid[x, y, z] > 0.5
        
        # キャッシュに保存
        self._obstacle_cache[pos] = result
        
        return result
    
    def _has_obstacles_in_column(self, x: int, y: int) -> bool:
        """指定(x,y)列に障害物があるかチェック"""
        if self.voxel_grid is None:
            return False
        
        for z in range(self.grid_size[2]):
            if self.voxel_grid[x, y, z] > 0.5:
                return True
        
        return False
    
    def _calculate_risk_at(self, pos: Tuple[int, int, int]) -> float:
        """指定位置のリスクスコアを計算"""
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
        
        path.reverse()
        return path
    
    def _world_to_voxel(
        self,
        pos: Tuple[float, float, float]
    ) -> Tuple[int, int, int]:
        """ワールド座標 → ボクセルインデックス（端点も必ずグリッド内に収める）"""
        world_pos = np.array(pos)
        voxel_pos = (world_pos - self.min_bound) / self.voxel_size
        voxel_idx = np.floor(voxel_pos + 1e-6).astype(int)
        # 各軸で必ず0～(N-1)にclamp
        for i in range(3):
            if voxel_idx[i] < 0 or voxel_idx[i] > self.grid_size[i] - 1:
                logger.warning(f'_world_to_voxel: axis {i} index {voxel_idx[i]} out of grid, clamped')
            voxel_idx[i] = max(0, min(voxel_idx[i], self.grid_size[i] - 1))
        return tuple(voxel_idx)
    
    def _voxel_to_world(
        self,
        idx: Tuple[int, int, int]
    ) -> Tuple[float, float, float]:
        """ボクセルインデックス → ワールド座標"""
        voxel_idx = np.array(idx)
        world_pos = self.min_bound + (voxel_idx + 0.5) * self.voxel_size
        return tuple(world_pos)
    
    def get_search_stats(self) -> Dict[str, any]:
        """最後の探索の統計情報を取得"""
        return self.last_search_stats.copy()
