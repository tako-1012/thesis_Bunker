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
    def _steer(self, from_node, to_node):
        """from_nodeからto_node方向にstep_sizeだけ進んだ新ノードを返す"""
        dx = to_node.x - from_node.x
        dy = to_node.y - from_node.y
        dz = to_node.z - from_node.z
        dist = math.sqrt(dx*dx + dy*dy + dz*dz)
        if dist == 0:
            return RRTNode(from_node.x, from_node.y, from_node.z, from_node.cost, from_node)
        scale = min(self.step_size, dist) / dist
        x = from_node.x + dx * scale
        y = from_node.y + dy * scale
        z = from_node.z + dz * scale
        return RRTNode(x, y, z)

    def _is_collision_free(self, node1, node2):
        """node1→node2間が障害物・傾斜的に通過可能か（暫定:常にTrue）"""
        # TODO: terrain_dataや傾斜・障害物判定を実装
        return True

    def _find_near_nodes(self, new_node, tree):
        """new_nodeからrewire_radius以内のノードを返す"""
        near_nodes = []
        for node in tree:
            if self._calculate_distance(node, new_node) < self.rewire_radius:
                near_nodes.append(node)
        return near_nodes

    def _rewire(self, new_node, near_nodes):
        """新ノードでコスト改善できる近傍ノードの親を付け替える"""
        for near_node in near_nodes:
            if self._is_collision_free(new_node, near_node):
                new_cost = new_node.cost + self._calculate_distance(new_node, near_node)
                if new_cost < near_node.cost:
                    near_node.parent = new_node
                    near_node.cost = new_cost
    def _sample_random_point(self):
        """マップ範囲内でランダムな点をサンプリング"""
        if hasattr(self, 'map_bounds') and self.map_bounds is not None:
            (x_min, y_min, z_min), (x_max, y_max, z_max) = self.map_bounds
        else:
            x_min, y_min, z_min = 0, 0, 0
            x_max = self.grid_size[0] * self.voxel_size
            y_max = self.grid_size[1] * self.voxel_size
            z_max = self.grid_size[2] * self.voxel_size
        x = random.uniform(x_min, x_max)
        y = random.uniform(y_min, y_max)
        z = random.uniform(z_min, z_max)
        return RRTNode(x, y, z)
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
        self.rewire_radius = rewire_radius
        self.goal_threshold = goal_threshold

    def plan_path(self, start, goal, terrain_data=None, timeout=None):
        """
        失敗時にパラメータを段階的に緩和して最大3回リトライ
        """
        param_sets = [
            dict(max_iterations=self.max_iterations, step_size=self.step_size, rewire_radius=self.rewire_radius, goal_threshold=self.goal_threshold),
            dict(max_iterations=int(self.max_iterations*2), step_size=self.step_size*1.5, rewire_radius=self.rewire_radius*1.5, goal_threshold=self.goal_threshold*2),
            dict(max_iterations=int(self.max_iterations*4), step_size=self.step_size*2, rewire_radius=self.rewire_radius*2, goal_threshold=self.goal_threshold*4)
        ]
        for params in param_sets:
            self.max_iterations = params['max_iterations']
            self.step_size = params['step_size']
            self.rewire_radius = params['rewire_radius']
            self.goal_threshold = params['goal_threshold']
            result = self._plan_path_core(start, goal, terrain_data, timeout)
            if result.success:
                return result
        # 全て失敗した場合
        return result

    def _plan_path_core(self, start, goal, terrain_data=None, timeout=None):
        import time
        start_time = time.time()
        # タイムアウト自動設定
        if timeout is None:
            if hasattr(self, 'map_size') and self.map_size < 30:
                timeout = 300
            elif hasattr(self, 'map_size') and self.map_size < 80:
                timeout = 600
            else:
                timeout = 1200
        logger.info(f"RRT* planning: {start} -> {goal}, timeout={timeout}s")
        try:
            # 位置の妥当性チェック
            if hasattr(self, '_is_valid_position') and not self._is_valid_position(start):
                start = self._clamp_position(start)
                logger.warning(f"Start clamped to {start}")
            if hasattr(self, '_is_valid_position') and not self._is_valid_position(goal):
                goal = self._clamp_position(goal)
                logger.warning(f"Goal clamped to {goal}")
            start_node = RRTNode(start[0], start[1], start[2], 0.0)
            goal_node = RRTNode(goal[0], goal[1], goal[2])
            tree = [start_node]
            goal_reached = False
            goal_node_in_tree = None
            nodes_explored = 0
            for iteration in range(self.max_iterations):
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
                if random.random() < getattr(self, 'goal_bias', 0.1):
                    random_point = goal_node
                else:
                    random_point = self._sample_random_point()
                nearest_node = self._find_nearest_node(random_point, tree)
                new_node = self._steer(nearest_node, random_point)
                if not self._is_collision_free(nearest_node, new_node):
                    continue
                near_nodes = self._find_near_nodes(new_node, tree)
                best_parent = nearest_node
                best_cost = nearest_node.cost + self._calculate_distance(nearest_node, new_node)
                for near_node in near_nodes:
                    if self._is_collision_free(near_node, new_node):
                        cost = near_node.cost + self._calculate_distance(near_node, new_node)
                        if cost < best_cost:
                            best_cost = cost
                            best_parent = near_node
                new_node.parent = best_parent
                new_node.cost = best_cost
                tree.append(new_node)
                nodes_explored += 1
                self._rewire(new_node, near_nodes)
                if self._calculate_distance(new_node, goal_node) < self.goal_threshold:
                    goal_reached = True
                    goal_node_in_tree = new_node
                    break
            computation_time = time.time() - start_time
            if goal_reached and goal_node_in_tree:
                path = self._reconstruct_path(goal_node_in_tree)
                path_length = self._calculate_path_length(path)
                logger.info(f"RRT* success! nodes={nodes_explored}, time={computation_time:.2f}s")
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
    
    # 重複した__init__定義を削除
    
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