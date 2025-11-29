"""
A* 3D経路計画（リファクタリング版）

BasePlanner3Dを継承した綺麗な実装
"""
import heapq
import time
from typing import List, Tuple, Optional
import numpy as np
import logging

from .base_planner import BasePlanner3D
from .planning_result import PlanningResult
from .config import PlannerConfig

logger = logging.getLogger(__name__)

class Node3D:
    """3Dノード（不変）"""
    __slots__ = ['x', 'y', 'z', 'g', 'h', 'f', 'parent']
    
    def __init__(self, x: float, y: float, z: float, 
                 g: float = 0, h: float = 0, parent: Optional['Node3D'] = None):
        self.x = x
        self.y = y
        self.z = z
        self.g = g
        self.h = h
        self.f = g + h
        self.parent = parent
    
    def __lt__(self, other: 'Node3D') -> bool:
        return self.f < other.f
    
    @property
    def position(self) -> Tuple[float, float, float]:
        """位置タプルを取得"""
        return (self.x, self.y, self.z)

class AStarPlanner3D(BasePlanner3D):
    """A* 3D経路計画"""
    
    def __init__(self, config: PlannerConfig):
        """
        初期化
        
        Args:
            config: プランナー設定
        """
        super().__init__(config)
        logger.info("A* Planner initialized")
    
    def plan_path(self, start: List[float], goal: List[float],
                  terrain_data=None, timeout: Optional[float] = None) -> PlanningResult:
        """
        A*経路計画
        
        Args:
            start: スタート位置 [x, y, z]
            goal: ゴール位置 [x, y, z]
            terrain_data: 地形データ（未使用）
            timeout: タイムアウト [秒]
        
        Returns:
            PlanningResult: 計画結果
        """
        start_time = time.time()
        
        # タイムアウト設定
        if timeout is None:
            timeout = self._calculate_timeout()
        
        logger.info(f"A* planning: {start} -> {goal}, timeout={timeout}s")
        
        # 位置の妥当性チェック
        if not self._is_valid_position(start):
            start = self._clamp_position(start)
            logger.warning(f"Start clamped to {start}")
        
        if not self._is_valid_position(goal):
            goal = self._clamp_position(goal)
            logger.warning(f"Goal clamped to {goal}")
        
        try:
            # A*探索実行
            result = self._astar_search(start, goal, timeout, start_time)
            
            # 結果に追加情報を設定
            result.algorithm_name = "A*"
            
            return result
        
        except Exception as e:
            logger.error(f"A* error: {e}", exc_info=True)
            return PlanningResult(
                success=False,
                path=[],
                computation_time=time.time() - start_time,
                path_length=0,
                nodes_explored=0,
                error_message=f"Exception: {str(e)}",
                algorithm_name="A*"
            )
    
    def _astar_search(self, start: List[float], goal: List[float],
                     timeout: float, start_time: float) -> PlanningResult:
        """
        A*探索の本体
        
        Args:
            start: スタート位置
            goal: ゴール位置
            timeout: タイムアウト
            start_time: 開始時刻
        
        Returns:
            PlanningResult: 計画結果
        """
        # 初期化
        start_node = Node3D(*start, g=0, h=self._heuristic(start, goal))
        
        open_set = [(start_node.f, id(start_node), start_node)]
        closed_set = set()
        g_scores = {start_node.position: 0}
        nodes_explored = 0
        
        # ゴールまでの直線距離
        goal_distance = np.linalg.norm(np.array(goal) - np.array(start))
        max_search_distance = goal_distance * 3.0
        
        # 探索ループ
        while open_set:
            # タイムアウトチェック
            if time.time() - start_time > timeout:
                logger.warning("A* timeout")
                return PlanningResult(
                    success=False,
                    path=[],
                    computation_time=time.time() - start_time,
                    path_length=0,
                    nodes_explored=nodes_explored,
                    error_message="Timeout"
                )
            
            # 最小f値のノードを取得
            _, _, current = heapq.heappop(open_set)
            
            if current.position in closed_set:
                continue
            
            nodes_explored += 1
            
            # ゴール判定
            if self._is_goal(current.position, goal):
                path = self._reconstruct_path(current)
                path_length = self._calculate_path_length(path)
                
                logger.info(f"A* success! nodes={nodes_explored}, "
                           f"time={time.time()-start_time:.2f}s")
                
                return PlanningResult(
                    success=True,
                    path=path,
                    computation_time=time.time() - start_time,
                    path_length=path_length,
                    nodes_explored=nodes_explored
                )
            
            closed_set.add(current.position)
            
            # 近傍ノード展開
            for neighbor in self._get_neighbors(current, goal):
                if neighbor.position in closed_set:
                    continue
                
                # 勾配チェック
                slope = self._calculate_slope(current.position, neighbor.position)
                if slope > self.max_slope_rad:
                    continue
                
                # 探索範囲制限
                if neighbor.g > max_search_distance:
                    continue
                
                # g値更新
                if (neighbor.position not in g_scores or 
                    neighbor.g < g_scores[neighbor.position]):
                    g_scores[neighbor.position] = neighbor.g
                    heapq.heappush(open_set, (neighbor.f, id(neighbor), neighbor))
        
        # 経路が見つからなかった
        logger.warning("A*: No path found")
        return PlanningResult(
            success=False,
            path=[],
            computation_time=time.time() - start_time,
            path_length=0,
            nodes_explored=nodes_explored,
            error_message="No path found"
        )
    
    def _get_neighbors(self, node: Node3D, goal: List[float]) -> List[Node3D]:
        """
        近傍ノードを取得（26近傍）
        
        Args:
            node: 現在のノード
            goal: ゴール位置
        
        Returns:
            List[Node3D]: 近傍ノードのリスト
        """
        neighbors = []
        
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                for dz in [-1, 0, 1]:
                    if dx == 0 and dy == 0 and dz == 0:
                        continue
                    
                    nx = node.x + dx * self.voxel_size
                    ny = node.y + dy * self.voxel_size
                    nz = node.z + dz * self.voxel_size
                    
                    if not self._is_valid_position((nx, ny, nz)):
                        continue
                    
                    # 移動コスト
                    distance = np.sqrt(dx**2 + dy**2 + dz**2) * self.voxel_size
                    
                    # g, h, f計算
                    g = node.g + distance
                    h = self._heuristic((nx, ny, nz), goal)
                    
                    neighbor = Node3D(nx, ny, nz, g=g, h=h, parent=node)
                    neighbors.append(neighbor)
        
        return neighbors
    
    def _heuristic(self, pos1: Tuple[float, float, float],
                   pos2: Tuple[float, float, float]) -> float:
        """
        ヒューリスティック関数（ユークリッド距離）
        
        Args:
            pos1: 位置1
            pos2: 位置2
        
        Returns:
            float: ヒューリスティック値
        """
        return np.linalg.norm(np.array(pos1) - np.array(pos2))
    
    def _reconstruct_path(self, node: Node3D) -> List[Tuple[float, float, float]]:
        """
        経路を再構築
        
        Args:
            node: ゴールノード
        
        Returns:
            List[Tuple]: 経路（座標のリスト）
        """
        path = []
        current = node
        while current is not None:
            path.append(current.position)
            current = current.parent
        return list(reversed(path))
