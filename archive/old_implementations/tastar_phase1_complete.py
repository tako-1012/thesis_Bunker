#!/usr/bin/env python3
"""
TA-A* Phase 1 Complete: 地形適応型ヒューリスティック

改善内容:
1. 地形の難易度分析
2. 適応型ヒューリスティック
3. 方向性ボーナス
4. キャッシュによる高速化

期待効果: 12秒→5-6秒（2倍高速化）
"""
import sys
from pathlib import Path
import numpy as np
import time
from typing import Tuple, Dict

sys.path.insert(0, str(Path(__file__).parent))
from tastar_optimized import TerrainAwareAStarOptimized, Node3D, PlanningResult
import heapq

class TerrainDifficultyAnalyzer:
    """地形難易度分析"""
    
    def __init__(self, voxel_size=0.2):
        self.voxel_size = voxel_size
        self.cache = {}
    
    def analyze(self, position: Tuple[float, float, float]) -> Dict:
        """
        位置の地形難易度を分析
        
        Returns:
            {
                'elevation': 高度,
                'difficulty': 難易度(0-1),
                'is_obstacle': 障害物か
            }
        """
        pos_key = tuple(position)
        
        if pos_key in self.cache:
            return self.cache[pos_key]
        
        x, y, z = position
        
        # 簡易的な地形分析
        # 高度ベースの難易度
        elevation = z
        difficulty = min(abs(z - 0.2) / 2.0, 1.0)  # 標準高度からの偏差
        
        # 障害物判定（高度範囲外）
        is_obstacle = z < 0.0 or z > 2.0
        
        result = {
            'elevation': elevation,
            'difficulty': difficulty,
            'is_obstacle': is_obstacle
        }
        
        self.cache[pos_key] = result
        return result

class AdaptiveHeuristicCalculator:
    """適応型ヒューリスティック計算"""
    
    def __init__(self, difficulty_analyzer):
        self.analyzer = difficulty_analyzer
        self.cache = {}
    
    def calculate(self, current: Tuple, goal: Tuple) -> float:
        """
        地形を考慮したヒューリスティック
        
        h(n) = euclidean_distance × terrain_factor × direction_bonus
        """
        # キャッシュチェック
        cache_key = (tuple(current), tuple(goal))
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # 基本ユークリッド距離
        euclidean = np.linalg.norm(np.array(current) - np.array(goal))
        
        # 地形難易度分析
        current_info = self.analyzer.analyze(current)
        goal_info = self.analyzer.analyze(goal)
        
        # 地形ファクター（1.0-3.0）
        avg_difficulty = (current_info['difficulty'] + goal_info['difficulty']) / 2
        terrain_factor = 1.0 + avg_difficulty * 2.0
        
        # 方向性ボーナス（ゴール方向の考慮）
        direction_bonus = self._calculate_direction_bonus(current, goal)
        
        # 最終ヒューリスティック
        heuristic = euclidean * terrain_factor * direction_bonus
        
        self.cache[cache_key] = heuristic
        return heuristic
    
    def _calculate_direction_bonus(self, current: Tuple, goal: Tuple) -> float:
        """
        方向性ボーナス
        
        ゴール方向が良い地形 → 1.0（補正なし）
        難しい地形 → 1.2（少し補正）
        """
        # 簡易版：高さ差を考慮
        z_diff = abs(current[2] - goal[2])
        
        if z_diff < 0.2:  # ほぼ同じ高さ
            return 1.0
        elif z_diff < 0.5:  # 少し高さ差
            return 1.1
        else:  # 大きな高さ差
            return 1.2

class TAStarPhase1Complete(TerrainAwareAStarOptimized):
    """
    TA-A* Phase 1 Complete
    
    地形適応型ヒューリスティックの完全実装
    """
    
    def __init__(self, grid_size=(100, 100, 30), voxel_size=0.1, max_slope=30.0,
                 map_bounds=None):
        super().__init__(grid_size, voxel_size, max_slope, map_bounds)
        self.difficulty_analyzer = TerrainDifficultyAnalyzer(voxel_size=self.voxel_size)
        self.heuristic_calculator = AdaptiveHeuristicCalculator(self.difficulty_analyzer)
        print("TA-A* Phase 1 Complete initialized")
    
    def plan_path(self, start, goal, terrain_data=None, timeout=None):
        """経路計画（Phase 1版）"""
        if timeout is None:
            timeout = 60
        
        start_time = time.time()
        
        try:
            result = self._astar_search_with_terrain_heuristic(start, goal, timeout, start_time)
            result.algorithm_name = "TA-A* Phase 1"
            return result
        except Exception as e:
            return self._create_result(False, [], 0, f"Exception: {str(e)}")
    
    def _astar_search_with_terrain_heuristic(self, start, goal, timeout, start_time):
        """地形考慮A*探索"""
        start_node = Node3D(*start, g=0, h=self._terrain_heuristic(start, goal))
        
        open_set = [(start_node.f, id(start_node), start_node)]
        closed_set = set()
        g_scores = {start_node.position: 0}
        nodes_explored = 0
        
        while open_set:
            if time.time() - start_time > timeout:
                return self._create_result(False, [], nodes_explored, "Timeout")
            
            _, _, current = heapq.heappop(open_set)
            
            if current.position in closed_set:
                continue
            
            nodes_explored += 1
            
            # ゴール判定
            if np.linalg.norm(np.array(current.position) - np.array(goal)) <= self.goal_threshold:
                path = self._reconstruct_path(current)
                path_length = self._calculate_path_length(path)
                
                return self._create_result(
                    True, path, nodes_explored,
                    path_length=path_length,
                    computation_time=time.time() - start_time
                )
            
            closed_set.add(current.position)
            
            # 近傍展開
            for neighbor in self._get_neighbors_with_heuristic(current, goal):
                if neighbor.position in closed_set:
                    continue
                
                if (neighbor.position not in g_scores or
                    neighbor.g < g_scores[neighbor.position]):
                    g_scores[neighbor.position] = neighbor.g
                    heapq.heappush(open_set, (neighbor.f, id(neighbor), neighbor))
        
        return self._create_result(False, [], nodes_explored, "No path found")
    
    def _terrain_heuristic(self, pos1, pos2):
        """地形考慮ヒューリスティック"""
        return self.heuristic_calculator.calculate(pos1, pos2)
    
    def _get_neighbors_with_heuristic(self, node, goal):
        """ヒューリスティック付き近傍取得"""
        neighbors = []
        x, y, z = node.position
        
        # 14近傍探索
        directions = [
            (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0),
            (1, 1, 0), (-1, 1, 0), (1, -1, 0), (-1, -1, 0),
            (1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1),
            (1, 1, 1), (-1, -1, 1)
        ]
        
        for dx, dy, dz in directions:
            nx = x + dx * self.voxel_size
            ny = y + dy * self.voxel_size
            nz = z + dz * self.voxel_size
            
            if not self._is_valid_position((nx, ny, nz)):
                continue
            
            # コスト計算
            cost = self._simple_terrain_cost((x, y, z), (nx, ny, nz))
            
            g = node.g + cost
            h = self._terrain_heuristic((nx, ny, nz), goal)
            
            neighbor = Node3D(nx, ny, nz, g=g, h=h, parent=node)
            neighbors.append(neighbor)
        
        return neighbors
    
    def _is_valid_position(self, pos):
        """位置の有効性チェック"""
        x, y, z = pos
        
        if not (self.min_bound[0] <= x <= self.max_bound[0] and
                self.min_bound[1] <= y <= self.max_bound[1] and
                self.min_bound[2] <= z <= self.max_bound[2]):
            return False
        
        if z < 0.0 or z > 5.0:
            return False
        
        return True
    
    def _simple_terrain_cost(self, pos1, pos2):
        """簡易地形コスト"""
        distance = np.linalg.norm(np.array(pos2) - np.array(pos1))
        height_diff = abs(pos1[2] - pos2[2])
        terrain_cost = height_diff * 2.0
        
        if pos2[2] < 0.0 or pos2[2] > 2.0:
            terrain_cost += 5.0
        
        return distance + terrain_cost * 0.1
    
    def _reconstruct_path(self, node):
        """経路再構築"""
        path = []
        current = node
        while current is not None:
            path.append([current.x, current.y, current.z])
            current = current.parent
        return list(reversed(path))
    
    def _calculate_path_length(self, path):
        """経路長計算"""
        if len(path) < 2:
            return 0.0
        
        total = 0.0
        for i in range(len(path) - 1):
            total += np.linalg.norm(np.array(path[i + 1]) - np.array(path[i]))
        return total
    
    def _create_result(self, success, path, nodes, error="", **kwargs):
        """結果作成"""
        return PlanningResult(
            success=success,
            path=path,
            computation_time=kwargs.get('computation_time', 0),
            path_length=kwargs.get('path_length', 0),
            nodes_explored=nodes,
            error_message=error,
            algorithm_name="TA-A* Phase 1"
        )

if __name__ == '__main__':
    """テスト"""
    print("="*70)
    print("TA-A* Phase 1 Complete テスト")
    print("="*70)
    
    planner = TAStarPhase1Complete(
        map_bounds=([-50, -50, 0], [50, 50, 10]),
        voxel_size=0.2
    )
    
    test_cases = [
        ([0, 0, 0.2], [5, 5, 0.2], "Short"),
        ([0, 0, 0.2], [10, 10, 0.2], "Medium"),
        ([-10, -10, 0.2], [10, 10, 0.2], "Long")
    ]
    
    for start, goal, name in test_cases:
        print(f"\n{name} distance:")
        result = planner.plan_path(start, goal, timeout=60)
        
        if result.success:
            print(f"  ✅ Success: {result.computation_time:.3f}s")
            print(f"     Path length: {result.path_length:.2f}m")
            print(f"     Nodes: {result.nodes_explored}")
        else:
            print(f"  ❌ Failed: {result.error_message}")


