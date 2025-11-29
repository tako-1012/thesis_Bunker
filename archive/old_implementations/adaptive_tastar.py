"""
Adaptive TA-A*

地形の複雑さに応じて評価粒度を適応的に変える
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

class AdaptiveTAstar(BasePlanner3D):
    """
    Adaptive Terrain-Aware A*
    
    主な特徴:
    1. 地形の複雑さを動的に評価
    2. 簡単な地形 → 粗い評価（高速）
    3. 複雑な地形 → 詳細評価（精密）
    4. 計算量を大幅削減
    """
    
    def __init__(self, config: PlannerConfig):
        """初期化"""
        super().__init__(config)
        
        # Adaptive parameters
        self.simple_terrain_threshold = 0.3  # 簡単な地形の閾値
        self.complex_terrain_threshold = 0.7  # 複雑な地形の閾値
        
        # Evaluation levels
        self.EVAL_COARSE = 0  # 粗い評価（高速）
        self.EVAL_MEDIUM = 1  # 中程度の評価
        self.EVAL_FINE = 2    # 詳細評価（精密）
        
        self.goal_threshold = 1.0
        
        logger.info("Adaptive TA-A* initialized")
    
    def plan_path(self, start: List[float], goal: List[float],
                  terrain_data=None, timeout: Optional[float] = None) -> PlanningResult:
        """
        適応的経路計画
        """
        start_time = time.time()
        
        if timeout is None:
            timeout = 300
        
        logger.info(f"Adaptive TA-A* planning: {start} -> {goal}")
        
        try:
            result = self._adaptive_astar_search(start, goal, timeout, start_time)
            result.algorithm_name = "Adaptive TA-A*"
            return result
        
        except Exception as e:
            logger.error(f"Adaptive TA-A* error: {e}", exc_info=True)
            return PlanningResult(
                success=False,
                path=[],
                computation_time=time.time() - start_time,
                path_length=0,
                nodes_explored=0,
                error_message=f"Exception: {str(e)}",
                algorithm_name="Adaptive TA-A*"
            )
    
    def _assess_terrain_complexity(self, position: Tuple) -> float:
        """
        地形の複雑さを評価
        
        Returns:
            複雑さスコア（0-1）
            0: 非常に簡単（平坦）
            1: 非常に複雑（険しい）
        """
        x, y, z = position
        
        # 簡易版：高度変化を複雑さの指標に
        # 実装では、周辺の高度分散、傾斜、障害物密度などを統合
        
        # 平坦な場所は複雑度低い
        if abs(z - 0.2) < 0.1:
            return 0.2
        
        # 高い場所は複雑度中程度
        if abs(z - 0.2) < 0.3:
            return 0.5
        
        # それ以外は複雑
        return 0.8
    
    def _select_evaluation_level(self, complexity: float) -> int:
        """
        複雑さに応じて評価レベルを選択
        
        Args:
            complexity: 地形の複雑さ（0-1）
        
        Returns:
            評価レベル（COARSE/MEDIUM/FINE）
        """
        if complexity < self.simple_terrain_threshold:
            return self.EVAL_COARSE
        elif complexity < self.complex_terrain_threshold:
            return self.EVAL_MEDIUM
        else:
            return self.EVAL_FINE
    
    def _evaluate_terrain_cost(self, position: Tuple, eval_level: int) -> float:
        """
        地形コストを評価（評価レベルに応じて）
        
        Args:
            position: 位置
            eval_level: 評価レベル
        
        Returns:
            地形コスト
        """
        if eval_level == self.EVAL_COARSE:
            # 粗い評価：固定コスト（高速）
            return 0.1
        
        elif eval_level == self.EVAL_MEDIUM:
            # 中程度の評価：基本的な地形特性
            x, y, z = position
            
            # 高度によるコスト
            height_cost = abs(z - 0.2) * 0.5
            
            return height_cost
        
        else:  # EVAL_FINE
            # 詳細評価：複雑な地形分析
            x, y, z = position
            
            # 高度コスト
            height_cost = abs(z - 0.2) * 1.0
            
            # 傾斜コスト（簡易版）
            slope_cost = 0.0
            if z > 0.5:
                slope_cost = 0.5
            
            # 安全性コスト
            safety_cost = 0.0
            if z < 0.0 or z > 2.0:
                safety_cost = 1.0
            
            return height_cost + slope_cost + safety_cost
    
    def _calculate_node_cost(self, current_pos: Tuple, next_pos: Tuple) -> float:
        """
        ノード間コスト計算（適応的）
        """
        # 基本距離
        distance = np.linalg.norm(np.array(next_pos) - np.array(current_pos))
        
        # 地形の複雑さを評価
        complexity = self._assess_terrain_complexity(next_pos)
        
        # 評価レベルを選択
        eval_level = self._select_evaluation_level(complexity)
        
        # 地形コストを評価
        terrain_cost = self._evaluate_terrain_cost(next_pos, eval_level)
        
        # 合計コスト
        total_cost = distance + terrain_cost
        
        return total_cost
    
    def _adaptive_astar_search(self, start, goal, timeout, start_time):
        """適応的A*探索"""
        from .astar_planner import Node3D
        
        # 初期化
        start_node = Node3D(*start, g=0, h=self._heuristic(start, goal))
        
        open_set = [(start_node.f, id(start_node), start_node)]
        closed_set = set()
        g_scores = {start_node.position: 0}
        nodes_explored = 0
        
        # 統計情報
        eval_count = {
            self.EVAL_COARSE: 0,
            self.EVAL_MEDIUM: 0,
            self.EVAL_FINE: 0
        }
        
        while open_set:
            # タイムアウトチェック
            if time.time() - start_time > timeout:
                logger.warning(f"Timeout after {nodes_explored} nodes")
                logger.info(f"Evaluation distribution: {eval_count}")
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
                
                logger.info(f"Adaptive TA-A* success! nodes={nodes_explored}")
                logger.info(f"Evaluation distribution: {eval_count}")
                
                return PlanningResult(
                    success=True,
                    path=path,
                    computation_time=time.time() - start_time,
                    path_length=path_length,
                    nodes_explored=nodes_explored
                )
            
            closed_set.add(current.position)
            
            # 近傍ノード展開
            for neighbor in self._get_adaptive_neighbors(current, goal, eval_count):
                if neighbor.position in closed_set:
                    continue
                
                if (neighbor.position not in g_scores or
                    neighbor.g < g_scores[neighbor.position]):
                    g_scores[neighbor.position] = neighbor.g
                    heapq.heappush(open_set, (neighbor.f, id(neighbor), neighbor))
        
        logger.warning(f"No path found after {nodes_explored} nodes")
        logger.info(f"Evaluation distribution: {eval_count}")
        return PlanningResult(
            success=False,
            path=[],
            computation_time=time.time() - start_time,
            path_length=0,
            nodes_explored=nodes_explored,
            error_message="No path found"
        )
    
    def _get_adaptive_neighbors(self, node, goal, eval_count):
        """適応的に近傍ノードを取得"""
        from .astar_planner import Node3D
        
        neighbors = []
        
        # 26近傍探索
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
                    
                    # 適応的コスト計算
                    complexity = self._assess_terrain_complexity((nx, ny, nz))
                    eval_level = self._select_evaluation_level(complexity)
                    eval_count[eval_level] = eval_count.get(eval_level, 0) + 1
                    
                    cost = self._calculate_node_cost(
                        node.position,
                        (nx, ny, nz)
                    )
                    
                    g = node.g + cost
                    h = self._heuristic((nx, ny, nz), goal)
                    
                    neighbor = Node3D(nx, ny, nz, g=g, h=h, parent=node)
                    neighbors.append(neighbor)
        
        return neighbors
    
    def _is_goal(self, position: Tuple[float, float, float], 
                 goal: List[float]) -> bool:
        """ゴール判定"""
        distance = np.linalg.norm(np.array(position) - np.array(goal))
        return distance <= self.goal_threshold
    
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

if __name__ == '__main__':
    # テスト
    config = PlannerConfig.medium_scale()
    planner = AdaptiveTAstar(config)
    
    print("="*70)
    print("Adaptive TA-A* テスト")
    print("="*70)
    
    scenarios = [
        ([0, 0, 0.2], [10, 10, 0.2], "Short"),
        ([0, 0, 0.2], [20, 20, 0.2], "Medium"),
        ([-20, -20, 0.2], [20, 20, 0.2], "Long")
    ]
    
    for start, goal, name in scenarios:
        print(f"\n{name} distance:")
        result = planner.plan_path(start, goal, timeout=60)
        
        if result.success:
            print(f"  ✅ Success")
            print(f"     Time: {result.computation_time:.2f}s")
            print(f"     Length: {result.path_length:.2f}m")
            print(f"     Nodes: {result.nodes_explored}")
        else:
            print(f"  ❌ Failed: {result.error_message}")
