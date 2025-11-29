"""
Theta* 3D経路計画

Any-angle planningで滑らかな経路を生成
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

class ThetaStarPlanner3D(BasePlanner3D):
    """Theta* 3D経路計画"""
    
    def __init__(self, config: PlannerConfig):
        """
        初期化
        
        Args:
            config: プランナー設定
        """
        super().__init__(config)
        logger.info("Theta* Planner initialized")
    
    def plan_path(self, start: List[float], goal: List[float],
                  terrain_data=None, timeout: Optional[float] = None) -> PlanningResult:
        """
        Theta*経路計画
        
        Args:
            start: スタート位置
            goal: ゴール位置
            terrain_data: 地形データ
            timeout: タイムアウト
        
        Returns:
            PlanningResult: 計画結果
        """
        start_time = time.time()
        
        if timeout is None:
            timeout = self._calculate_timeout()
        
        logger.info(f"Theta* planning: {start} -> {goal}")
        
        # 位置の妥当性チェック
        if not self._is_valid_position(start):
            start = self._clamp_position(start)
        
        if not self._is_valid_position(goal):
            goal = self._clamp_position(goal)
        
        try:
            result = self._theta_star_search(start, goal, timeout, start_time)
            result.algorithm_name = "Theta*"
            return result
        
        except Exception as e:
            logger.error(f"Theta* error: {e}", exc_info=True)
            return PlanningResult(
                success=False,
                path=[],
                computation_time=time.time() - start_time,
                path_length=0,
                nodes_explored=0,
                error_message=f"Exception: {str(e)}",
                algorithm_name="Theta*"
            )
    
    def _theta_star_search(self, start, goal, timeout, start_time):
        """Theta*探索の本体"""
        from .astar_planner import Node3D
        
        # 初期化
        start_node = Node3D(*start, g=0, h=self._heuristic(start, goal))
        
        open_set = [(start_node.f, id(start_node), start_node)]
        closed_set = set()
        g_scores = {start_node.position: 0}
        nodes_explored = 0
        
        goal_distance = np.linalg.norm(np.array(goal) - np.array(start))
        max_search_distance = goal_distance * 3.0
        
        while open_set:
            # タイムアウトチェック
            if time.time() - start_time > timeout:
                return PlanningResult(
                    success=False,
                    path=[],
                    computation_time=time.time() - start_time,
                    path_length=0,
                    nodes_explored=nodes_explored,
                    error_message="Timeout"
                )
            
            _, _, current = heapq.heappop(open_set)
            
            if current.position in closed_set:
                continue
            
            nodes_explored += 1
            
            # ゴール判定
            if self._is_goal(current.position, goal):
                path = self._reconstruct_path(current)
                path_length = self._calculate_path_length(path)
                
                logger.info(f"Theta* success! nodes={nodes_explored}")
                
                return PlanningResult(
                    success=True,
                    path=path,
                    computation_time=time.time() - start_time,
                    path_length=path_length,
                    nodes_explored=nodes_explored
                )
            
            closed_set.add(current.position)
            
            # 近傍ノード展開
            for neighbor in self._get_neighbors(current):
                if neighbor.position in closed_set:
                    continue
                
                # Line-of-sight check
                if current.parent and self._line_of_sight(current.parent.position, neighbor.position):
                    # 親の親から直接繋げる（Theta*の特徴）
                    parent_pos = current.parent.position
                    direct_dist = np.linalg.norm(np.array(neighbor.position) - np.array(parent_pos))
                    
                    tentative_g = current.parent.g + direct_dist
                    
                    if (neighbor.position not in g_scores or 
                        tentative_g < g_scores[neighbor.position]):
                        g_scores[neighbor.position] = tentative_g
                        h = self._heuristic(neighbor.position, goal)
                        
                        new_node = Node3D(
                            *neighbor.position,
                            g=tentative_g,
                            h=h,
                            parent=current.parent
                        )
                        heapq.heappush(open_set, (new_node.f, id(new_node), new_node))
                else:
                    # 通常のA*と同じ
                    if (neighbor.position not in g_scores or 
                        neighbor.g < g_scores[neighbor.position]):
                        g_scores[neighbor.position] = neighbor.g
                        heapq.heappush(open_set, (neighbor.f, id(neighbor), neighbor))
        
        return PlanningResult(
            success=False,
            path=[],
            computation_time=time.time() - start_time,
            path_length=0,
            nodes_explored=nodes_explored,
            error_message="No path found"
        )
    
    def _line_of_sight(self, pos1: Tuple, pos2: Tuple) -> bool:
        """
        2点間の見通しをチェック
        
        Args:
            pos1: 位置1
            pos2: 位置2
        
        Returns:
            bool: 見通しがあればTrue
        """
        # Bresenham's line algorithm的なアプローチ
        # 簡易版: 勾配チェックのみ
        
        slope = self._calculate_slope(pos1, pos2)
        
        # 勾配が大きすぎる場合はNG
        if slope > self.max_slope_rad:
            return False
        
        # TODO: より詳細な障害物チェック
        
        return True
    
    def _get_neighbors(self, node):
        """近傍ノードを取得（A*と同じ）"""
        from .astar_planner import Node3D
        
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
                    
                    distance = np.sqrt(dx**2 + dy**2 + dz**2) * self.voxel_size
                    
                    g = node.g + distance
                    h = self._heuristic((nx, ny, nz), (node.x, node.y, node.z))
                    
                    neighbor = Node3D(nx, ny, nz, g=g, h=h, parent=node)
                    neighbors.append(neighbor)
        
        return neighbors
    
    def _heuristic(self, pos1, pos2):
        """ヒューリスティック関数"""
        return np.linalg.norm(np.array(pos1) - np.array(pos2))
    
    def _reconstruct_path(self, node):
        """経路を再構築"""
        path = []
        current = node
        while current is not None:
            path.append(current.position)
            current = current.parent
        return list(reversed(path))



