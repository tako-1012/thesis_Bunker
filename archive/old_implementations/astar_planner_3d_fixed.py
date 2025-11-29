"""
A*法による3D経路計画（API統一版）
"""
import numpy as np
import heapq
import time
import logging
from typing import Tuple, List, Optional

# 共通PlanningResultをインポート
import sys
sys.path.append('../path_planner_3d')
from planning_result import PlanningResult

logger = logging.getLogger(__name__)

class Node3D:
    """3Dノード"""
    def __init__(self, x, y, z, g=0, h=0, parent=None):
        self.x = x
        self.y = y
        self.z = z
        self.g = g
        self.h = h
        self.f = g + h
        self.parent = parent
    
    def __lt__(self, other):
        return self.f < other.f

class AStarPlanner3D:
    """A*法による3D経路計画"""
    
    def __init__(self, grid_size=(100, 100, 30), voxel_size=0.1, max_slope=30.0,
                 map_bounds=None):
        """
        初期化
        
        Args:
            grid_size: グリッドサイズ
            voxel_size: ボクセルサイズ [m]
            max_slope: 最大許容勾配 [度]
            map_bounds: マップ範囲 ((x_min, y_min, z_min), (x_max, y_max, z_max))
        """
        self.grid_size = grid_size
        self.voxel_size = voxel_size
        self.max_slope_deg = max_slope
        self.max_slope_rad = np.deg2rad(max_slope)
        
        # マップ範囲設定
        if map_bounds is not None:
            self.min_bound = np.array(map_bounds[0])
            self.max_bound = np.array(map_bounds[1])
        else:
            self.min_bound = np.array([-5.0, -5.0, 0.0])
            self.max_bound = np.array([5.0, 5.0, 3.0])
        
        # マップサイズ計算
        self.map_size = np.linalg.norm(self.max_bound - self.min_bound)
        
        # ゴール閾値（マップサイズに応じて動的設定）
        if self.map_size < 30:
            self.goal_threshold = 0.3
        elif self.map_size < 80:
            self.goal_threshold = 0.8
        else:
            self.goal_threshold = 1.5
        
        logger.info(f"A* initialized: map_size={self.map_size:.1f}m, "
                   f"goal_threshold={self.goal_threshold:.2f}m")
    
    def plan_path(self, start, goal, terrain_data=None, timeout=None):
        """
        経路計画（統一API）
        
        Args:
            start: スタート位置 [x, y, z]
            goal: ゴール位置 [x, y, z]
            terrain_data: 地形データ（A*では未使用、API統一のため）
            timeout: タイムアウト [秒]（Noneなら自動設定）
        
        Returns:
            PlanningResult: 経路計画結果
        """
        start_time = time.time()
        
        # タイムアウト自動設定
        if timeout is None:
            if self.map_size < 30:
                timeout = 300   # 5分
            elif self.map_size < 80:
                timeout = 900   # 15分
            else:
                timeout = 1800  # 30分
        
        logger.info(f"A* planning: {start} -> {goal}, timeout={timeout}s")
        
        try:
            # 位置の妥当性チェック
            if not self._is_valid_position(start):
                start = self._clamp_position(start)
                logger.warning(f"Start clamped to {start}")
            
            if not self._is_valid_position(goal):
                goal = self._clamp_position(goal)
                logger.warning(f"Goal clamped to {goal}")
            
            # A*探索
            start_node = Node3D(x=start[0], y=start[1], z=start[2], g=0, h=0)
            
            open_set = [(0, id(start_node), start_node)]
            closed_set = set()
            g_scores = {(start[0], start[1], start[2]): 0}
            nodes_explored = 0
            
            # ゴールまでの直線距離
            goal_distance = np.linalg.norm(np.array(goal) - np.array(start))
            max_search_distance = goal_distance * 2.0  # 探索範囲制限
            
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
                        error_message="Timeout",
                        algorithm_name="A*"
                    )
                
                _, _, current = heapq.heappop(open_set)
                current_pos = (current.x, current.y, current.z)
                
                if current_pos in closed_set:
                    continue
                
                nodes_explored += 1
                
                # ゴール判定
                if self._is_goal(current, goal):
                    path = self._reconstruct_path(current)
                    path_length = self._calculate_path_length(path)
                    
                    logger.info(f"A* success! nodes={nodes_explored}, "
                               f"time={time.time()-start_time:.2f}s")
                    
                    return PlanningResult(
                        success=True,
                        path=path,
                        computation_time=time.time() - start_time,
                        path_length=path_length,
                        nodes_explored=nodes_explored,
                        algorithm_name="A*"
                    )
                
                closed_set.add(current_pos)
                
                # 26近傍展開
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        for dz in [-1, 0, 1]:
                            if dx == 0 and dy == 0 and dz == 0:
                                continue
                            
                            nx = current.x + dx * self.voxel_size
                            ny = current.y + dy * self.voxel_size
                            nz = current.z + dz * self.voxel_size
                            neighbor_pos = (nx, ny, nz)
                            
                            if not self._is_valid_position(neighbor_pos):
                                continue
                            
                            if neighbor_pos in closed_set:
                                continue
                            
                            # 移動コスト
                            distance = np.sqrt(dx**2 + dy**2 + dz**2) * self.voxel_size
                            
                            # 勾配チェック
                            slope = self._calculate_slope(current_pos, neighbor_pos)
                            if slope > self.max_slope_rad:
                                continue
                            
                            slope_penalty = (slope / self.max_slope_rad) * 1.5
                            tentative_g = current.g + distance + slope_penalty
                            
                            # 探索範囲制限
                            if tentative_g > max_search_distance:
                                continue
                            
                            if neighbor_pos in g_scores and tentative_g >= g_scores[neighbor_pos]:
                                continue
                            
                            # A*: f(n) = g(n) + h(n)
                            h_score = self._calculate_heuristic(neighbor_pos, goal)
                            f_score = tentative_g + h_score
                            
                            neighbor_node = Node3D(
                                x=nx, y=ny, z=nz,
                                g=tentative_g,
                                h=h_score,
                                parent=current
                            )
                            
                            g_scores[neighbor_pos] = tentative_g
                            heapq.heappush(open_set, (f_score, id(neighbor_node), neighbor_node))
            
            # 経路が見つからなかった
            logger.warning("A*: No path found")
            return PlanningResult(
                success=False,
                path=[],
                computation_time=time.time() - start_time,
                path_length=0,
                nodes_explored=nodes_explored,
                error_message="No path found",
                algorithm_name="A*"
            )
        
        except Exception as e:
            logger.error(f"A* error: {e}")
            import traceback
            traceback.print_exc()
            
            return PlanningResult(
                success=False,
                path=[],
                computation_time=time.time() - start_time,
                path_length=0,
                nodes_explored=0,
                error_message=f"Exception: {str(e)}",
                algorithm_name="A*"
            )
    
    def _calculate_heuristic(self, pos, goal):
        """ヒューリスティック関数（ユークリッド距離）"""
        return np.sqrt(
            (pos[0] - goal[0])**2 +
            (pos[1] - goal[1])**2 +
            (pos[2] - goal[2])**2
        )
    
    def _calculate_slope(self, pos1, pos2):
        """勾配を計算"""
        dz = pos2[2] - pos1[2]
        dxy = np.sqrt((pos2[0] - pos1[0])**2 + (pos2[1] - pos1[1])**2)
        return abs(np.arctan(dz / dxy)) if dxy > 1e-6 else 0.0
    
    def _is_valid_position(self, pos):
        """位置の妥当性チェック"""
        return (self.min_bound[0] <= pos[0] <= self.max_bound[0] and
                self.min_bound[1] <= pos[1] <= self.max_bound[1] and
                self.min_bound[2] <= pos[2] <= self.max_bound[2])
    
    def _clamp_position(self, pos):
        """位置を有効範囲内にクランプ"""
        return (
            np.clip(pos[0], self.min_bound[0], self.max_bound[0]),
            np.clip(pos[1], self.min_bound[1], self.max_bound[1]),
            np.clip(pos[2], self.min_bound[2], self.max_bound[2])
        )
    
    def _is_goal(self, node, goal):
        """ゴール判定"""
        dist = np.sqrt(
            (node.x - goal[0])**2 +
            (node.y - goal[1])**2 +
            (node.z - goal[2])**2
        )
        return dist < self.goal_threshold
    
    def _reconstruct_path(self, node):
        """経路を再構築"""
        path = []
        current = node
        while current is not None:
            path.append((current.x, current.y, current.z))
            current = current.parent
        return list(reversed(path))
    
    def _calculate_path_length(self, path):
        """経路長を計算"""
        if len(path) < 2:
            return 0.0
        
        length = 0.0
        for i in range(len(path) - 1):
            p1 = np.array(path[i])
            p2 = np.array(path[i + 1])
            length += np.linalg.norm(p2 - p1)
        
        return length