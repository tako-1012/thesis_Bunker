"""
RRT*法による3D経路計画（API統一版）
"""
import numpy as np
import time
import random
import logging
import math
from typing import Tuple, List, Optional

# 共通PlanningResultをインポート
try:
    from .planning_result import PlanningResult
except ImportError:
    from planning_result import PlanningResult

logger = logging.getLogger(__name__)

class RRTNode:
    """RRT*のノード"""
    def __init__(self, x, y, z, cost=0.0, parent=None):
        self.x = x
        self.y = y
        self.z = z
        self.cost = cost
        self.parent = parent
    
    def __eq__(self, other):
        return (abs(self.x - other.x) < 1e-6 and 
                abs(self.y - other.y) < 1e-6 and 
                abs(self.z - other.z) < 1e-6)
    
    def __hash__(self):
        return hash((round(self.x, 6), round(self.y, 6), round(self.z, 6)))

class RRTStarPlanner3D:
    """RRT*法による3D経路計画"""
    
    def __init__(self, grid_size=(100, 100, 30), voxel_size=0.1, max_slope=30.0,
                 max_iterations=10000, step_size=0.5, goal_threshold=0.5,
                 rewire_radius=1.0, map_bounds=None):
        """
        初期化
        
        Args:
            grid_size: グリッドサイズ
            voxel_size: ボクセルサイズ [m]
            max_slope: 最大許容勾配 [度]
            max_iterations: 最大反復回数
            step_size: ステップサイズ [m]
            goal_threshold: ゴール到達判定の閾値 [m]
            rewire_radius: 再配線の半径 [m]
            map_bounds: マップ範囲 ((x_min, y_min, z_min), (x_max, y_max, z_max))
        """
        self.grid_size = grid_size
        self.voxel_size = voxel_size
        self.max_slope_deg = max_slope
        self.max_slope_rad = np.deg2rad(max_slope)
        self.max_iterations = max_iterations
        self.step_size = step_size
        self.goal_threshold = goal_threshold
        self.rewire_radius = rewire_radius
        
        # マップ範囲設定
        if map_bounds is not None:
            self.min_bound = np.array(map_bounds[0])
            self.max_bound = np.array(map_bounds[1])
        else:
            # 負の座標も扱えるように中心を原点に設定
            half_x = (grid_size[0] * voxel_size) / 2.0
            half_y = (grid_size[1] * voxel_size) / 2.0
            
            self.min_bound = np.array([-half_x, -half_y, 0.0])
            self.max_bound = np.array([half_x, half_y, float(grid_size[2] * voxel_size)])
        
        # マップサイズ計算
        self.map_size = np.linalg.norm(self.max_bound - self.min_bound)
        
        # ゴール閾値（マップサイズに応じて動的設定）
        if self.map_size < 30:
            self.goal_threshold = 0.5
        elif self.map_size < 80:
            self.goal_threshold = 1.0
        else:
            self.goal_threshold = 2.0
        
        # RRT*パラメータ調整
        self.goal_bias = 0.1  # ゴールバイアス
        
        logger.info(f"RRT* initialized: map_size={self.map_size:.1f}m, "
                   f"goal_threshold={self.goal_threshold:.2f}m, "
                   f"max_iterations={max_iterations}")
    
    def plan_path(self, start, goal, terrain_data=None, timeout=None):
        """
        経路計画（統一API）
        
        Args:
            start: スタート位置 [x, y, z]
            goal: ゴール位置 [x, y, z]
            terrain_data: 地形データ（RRT*では未使用、API統一のため）
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
                timeout = 600   # 10分
            else:
                timeout = 1200  # 20分
        
        logger.info(f"RRT* planning: {start} -> {goal}, timeout={timeout}s")
        
        try:
            # 位置の妥当性チェック
            if not self._is_valid_position(start):
                start = self._clamp_position(start)
                logger.warning(f"Start clamped to {start}")
            
            if not self._is_valid_position(goal):
                goal = self._clamp_position(goal)
                logger.warning(f"Goal clamped to {goal}")
            
            # RRT*探索
            start_node = RRTNode(start[0], start[1], start[2], 0.0)
            goal_node = RRTNode(goal[0], goal[1], goal[2])
            
            tree = [start_node]
            goal_reached = False
            goal_node_in_tree = None
            nodes_explored = 0
            
            for iteration in range(self.max_iterations):
                # タイムアウトチェック
                if time.time() - start_time > timeout:
                    logger.warning("RRT* timeout")
                    return PlanningResult(
                        success=False,
                        path=[],
                        computation_time=time.time() - start_time,
                        path_length=0,
                        nodes_explored=nodes_explored,
                        error_message="Timeout",
                        algorithm_name="RRT*"
                    )
                
                # 1. ランダムサンプリング
                if random.random() < self.goal_bias:
                    random_point = goal_node
                else:
                    random_point = self._sample_random_point()
                
                # 2. 最近傍ノード検索
                nearest_node = self._find_nearest_node(random_point, tree)
                
                # 3. ステアリング
                new_node = self._steer(nearest_node, random_point)
                
                # 4. 衝突チェック（簡略化）
                if not self._is_collision_free(nearest_node, new_node):
                    continue
                
                # 5. 近傍ノード検索（再配線用）
                near_nodes = self._find_near_nodes(new_node, tree)
                
                # 6. 最適な親ノード選択
                best_parent = nearest_node
                best_cost = nearest_node.cost + self._calculate_distance(nearest_node, new_node)
                
                for near_node in near_nodes:
                    if self._is_collision_free(near_node, new_node):
                        cost = near_node.cost + self._calculate_distance(near_node, new_node)
                        if cost < best_cost:
                            best_cost = cost
                            best_parent = near_node
                
                # 7. ノードをツリーに追加
                new_node.parent = best_parent
                new_node.cost = best_cost
                tree.append(new_node)
                nodes_explored += 1
                
                # 8. 再配線
                self._rewire(new_node, near_nodes)
                
                # 9. ゴール到達チェック
                if self._calculate_distance(new_node, goal_node) < self.goal_threshold:
                    goal_reached = True
                    goal_node_in_tree = new_node
                    break
            
            computation_time = time.time() - start_time
            
            if goal_reached and goal_node_in_tree:
                path = self._reconstruct_path(goal_node_in_tree)
                path_length = self._calculate_path_length(path)
                
                logger.info(f"RRT* success! nodes={nodes_explored}, "
                           f"time={computation_time:.2f}s")
                
                return PlanningResult(
                    success=True,
                    path=path,
                    computation_time=computation_time,
                    path_length=path_length,
                    nodes_explored=nodes_explored,
                    algorithm_name="RRT*"
                )
            else:
                logger.warning("RRT*: No path found")
                return PlanningResult(
                    success=False,
                    path=[],
                    computation_time=computation_time,
                    path_length=0,
                    nodes_explored=nodes_explored,
                    error_message="No path found",
                    algorithm_name="RRT*"
                )
        
        except Exception as e:
            logger.error(f"RRT* error: {e}")
            import traceback
            traceback.print_exc()
            
            return PlanningResult(
                success=False,
                path=[],
                computation_time=time.time() - start_time,
                path_length=0,
                nodes_explored=0,
                error_message=f"Exception: {str(e)}",
                algorithm_name="RRT*"
            )
    
    def _sample_random_point(self):
        """ランダムサンプリング"""
        x = random.uniform(self.min_bound[0], self.max_bound[0])
        y = random.uniform(self.min_bound[1], self.max_bound[1])
        z = random.uniform(self.min_bound[2], self.max_bound[2])
        return RRTNode(x, y, z)
    
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
    
    def _find_nearest_node(self, point, tree):
        """最近傍ノードを検索"""
        min_distance = float('inf')
        nearest_node = None
        
        for node in tree:
            distance = self._calculate_distance(node, point)
            if distance < min_distance:
                min_distance = distance
                nearest_node = node
        
        return nearest_node
    
    def _steer(self, from_node, to_node):
        """ステアリング（ステップサイズで制限）"""
        distance = self._calculate_distance(from_node, to_node)
        
        if distance <= self.step_size:
            return RRTNode(to_node.x, to_node.y, to_node.z)
        
        # ステップサイズで制限
        ratio = self.step_size / distance
        new_x = from_node.x + ratio * (to_node.x - from_node.x)
        new_y = from_node.y + ratio * (to_node.y - from_node.y)
        new_z = from_node.z + ratio * (to_node.z - from_node.z)
        
        return RRTNode(new_x, new_y, new_z)
    
    def _is_collision_free(self, from_node, to_node):
        """衝突チェック（簡略化版）"""
        # 簡略化：傾斜チェックのみ
        dz = to_node.z - from_node.z
        dxy = math.sqrt((to_node.x - from_node.x)**2 + (to_node.y - from_node.y)**2)
        
        if dxy > 1e-6:
            slope = abs(math.atan(dz / dxy))
            if slope > self.max_slope_rad:
                return False
        
        return True
    
    def _find_near_nodes(self, node, tree):
        """再配線用の近傍ノードを検索"""
        near_nodes = []
        
        for tree_node in tree:
            if self._calculate_distance(node, tree_node) <= self.rewire_radius:
                near_nodes.append(tree_node)
        
        return near_nodes
    
    def _rewire(self, new_node, near_nodes):
        """再配線"""
        for near_node in near_nodes:
            if near_node == new_node.parent:
                continue
            
            # 衝突チェック
            if not self._is_collision_free(near_node, new_node):
                continue
            
            # コスト改善チェック
            new_cost = new_node.cost + self._calculate_distance(new_node, near_node)
            if new_cost < near_node.cost:
                near_node.parent = new_node
                near_node.cost = new_cost
    
    def _calculate_distance(self, node1, node2):
        """2点間の距離を計算"""
        dx = node2.x - node1.x
        dy = node2.y - node1.y
        dz = node2.z - node1.z
        return math.sqrt(dx*dx + dy*dy + dz*dz)
    
    def _reconstruct_path(self, goal_node):
        """経路を再構築"""
        path = []
        current = goal_node
        
        while current is not None:
            path.append((current.x, current.y, current.z))
            current = current.parent
        
        path.reverse()
        return path
    
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