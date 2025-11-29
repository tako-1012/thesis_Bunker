#!/usr/bin/env python3
"""
A* 3D Path Planner (Enhanced with Statistics)
統計情報を強化したA*実装
"""

import numpy as np
import heapq
import time
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
import logging

@dataclass
class Node3D:
    """3D空間のノード"""
    x: int
    y: int
    z: int
    g_score: float = float('inf')
    f_score: float = float('inf')
    parent: Optional['Node3D'] = None
    
    def __lt__(self, other):
        return self.f_score < other.f_score
    
    def __eq__(self, other):
        return (self.x, self.y, self.z) == (other.x, other.y, other.z)
    
    def __hash__(self):
        return hash((self.x, self.y, self.z))

class AStarPlanner3D:
    """
    統計情報を強化したA* 3D経路計画
    """
    
    def __init__(self, grid_size: Tuple[int, int, int], 
                 voxel_size: float = 0.1, 
                 max_slope: float = 30.0):
        """
        初期化
        
        Args:
            grid_size: (width, height, depth) グリッドサイズ
            voxel_size: ボクセルサイズ [m]
            max_slope: 最大傾斜角度 [度]
        """
        self.grid_size = grid_size
        self.voxel_size = voxel_size
        self.max_slope = max_slope
        
        # 26近傍（3x3x3 - 自分自身）
        self.neighbors = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                for dz in [-1, 0, 1]:
                    if dx == 0 and dy == 0 and dz == 0:
                        continue
                    self.neighbors.append((dx, dy, dz))
        
        # 統計情報
        self.stats = {
            'nodes_explored': 0,
            'computation_time': 0.0,
            'memory_usage': 0.0,
            'path_length': 0.0,
            'success': False
        }
        
        self.logger = logging.getLogger(__name__)
    
    def plan_path(self, start: Tuple[float, float, float], 
                  goal: Tuple[float, float, float]) -> List[Tuple[float, float, float]]:
        """
        A*法で経路計画（元のA*と同じAPI）
        
        Args:
            start: スタート位置 (x, y, z) [m]
            goal: ゴール位置 (x, y, z) [m]
            
        Returns:
            List[Tuple[float, float, float]]: 経路の点のリスト、失敗時はNone
        """
        start_time = time.time()
        
        # グリッド座標に変換
        start_grid = self.world_to_grid(start)
        goal_grid = self.world_to_grid(goal)
        
        # 境界チェック
        if not self.is_valid_position(start_grid, terrain_data):
            return self._create_failure_result("Invalid start position")
        if not self.is_valid_position(goal_grid, terrain_data):
            return self._create_failure_result("Invalid goal position")
        
        # 初期化
        start_node = Node3D(start_grid[0], start_grid[1], start_grid[2], 0.0, 0.0)
        goal_node = Node3D(goal_grid[0], goal_grid[1], goal_grid[2])
        
        # オープンリスト（優先度キュー）
        open_list = [start_node]
        heapq.heapify(open_list)
        
        # クローズドリスト
        closed_set = set()
        
        # 全ノードのスコア管理
        all_nodes = {}
        all_nodes[(start_node.x, start_node.y, start_node.z)] = start_node
        
        self.stats['nodes_explored'] = 0
        
        while open_list:
            current = heapq.heappop(open_list)
            
            # ゴール到達チェック
            if current == goal_node:
                path = self._reconstruct_path(current)
                computation_time = time.time() - start_time
                
                return self._create_success_result(path, computation_time)
            
            # クローズドリストに追加
            closed_set.add((current.x, current.y, current.z))
            self.stats['nodes_explored'] += 1
            
            # 26近傍を探索
            for dx, dy, dz in self.neighbors:
                neighbor_pos = (current.x + dx, current.y + dy, current.z + dz)
                
                # 境界チェック
                if not self._is_in_bounds(neighbor_pos):
                    continue
                
                # 既にクローズドリストにある場合はスキップ
                if neighbor_pos in closed_set:
                    continue
                
                # 障害物チェック
                if not self.is_valid_position(neighbor_pos, terrain_data):
                    continue
                
                # 移動コスト計算
                move_cost = self._calculate_move_cost(
                    (current.x, current.y, current.z), 
                    neighbor_pos, 
                    terrain_data
                )
                
                if move_cost == float('inf'):
                    continue
                
                tentative_g = current.g_score + move_cost
                
                # ノードが既に存在するかチェック
                if neighbor_pos in all_nodes:
                    neighbor = all_nodes[neighbor_pos]
                else:
                    neighbor = Node3D(neighbor_pos[0], neighbor_pos[1], neighbor_pos[2])
                    all_nodes[neighbor_pos] = neighbor
                
                # より良い経路が見つかった場合
                if tentative_g < neighbor.g_score:
                    neighbor.parent = current
                    neighbor.g_score = tentative_g
                    
                    # A*: f(n) = g(n) + h(n)
                    h_score = self._calculate_heuristic(neighbor_pos, goal_grid)
                    neighbor.f_score = tentative_g + h_score
                    
                    # オープンリストに追加（重複チェック）
                    if neighbor not in open_list:
                        heapq.heappush(open_list, neighbor)
        
        # 経路が見つからない
        computation_time = time.time() - start_time
        return self._create_failure_result("No path found", computation_time)
    
    def _calculate_heuristic(self, pos: Tuple[int, int, int], 
                           goal: Tuple[int, int, int]) -> float:
        """
        ヒューリスティック関数（ユークリッド距離）
        
        Args:
            pos: 現在位置のグリッド座標
            goal: ゴール位置のグリッド座標
            
        Returns:
            ヒューリスティック値
        """
        dx = goal[0] - pos[0]
        dy = goal[1] - pos[1]
        dz = goal[2] - pos[2]
        
        # ユークリッド距離
        distance = np.sqrt(dx*dx + dy*dy + dz*dz) * self.voxel_size
        
        return distance
    
    def _calculate_move_cost(self, from_pos: Tuple[int, int, int], 
                           to_pos: Tuple[int, int, int], 
                           terrain_data: np.ndarray) -> float:
        """
        移動コスト計算
        
        Args:
            from_pos: 移動元のグリッド座標
            to_pos: 移動先のグリッド座標
            terrain_data: 地形データ
            
        Returns:
            移動コスト
        """
        # 基本移動距離
        dx, dy, dz = to_pos[0] - from_pos[0], to_pos[1] - from_pos[1], to_pos[2] - from_pos[2]
        distance = np.sqrt(dx*dx + dy*dy + dz*dz) * self.voxel_size
        
        # 傾斜コスト
        slope_cost = self._calculate_slope_cost(from_pos, to_pos, terrain_data)
        
        # 障害物近接コスト
        obstacle_cost = self._calculate_obstacle_cost(to_pos, terrain_data)
        
        # 総コスト
        total_cost = distance + slope_cost + obstacle_cost
        
        return total_cost
    
    def _calculate_slope_cost(self, from_pos: Tuple[int, int, int], 
                            to_pos: Tuple[int, int, int], 
                            terrain_data: np.ndarray) -> float:
        """傾斜コスト計算"""
        try:
            # 高さ差から傾斜角度を計算
            height_diff = abs(to_pos[2] - from_pos[2]) * self.voxel_size
            horizontal_dist = np.sqrt((to_pos[0] - from_pos[0])**2 + (to_pos[1] - from_pos[1])**2) * self.voxel_size
            
            if horizontal_dist == 0:
                return 0.0
            
            slope_angle = np.degrees(np.arctan(height_diff / horizontal_dist))
            
            # 傾斜コスト（非線形）
            if slope_angle < 10:
                return 1.0
            elif slope_angle < 20:
                return 2.0
            elif slope_angle < self.max_slope:
                return 5.0
            else:
                return float('inf')  # 通行不可
                
        except (IndexError, ValueError):
            return float('inf')
    
    def _calculate_obstacle_cost(self, pos: Tuple[int, int, int], 
                               terrain_data: np.ndarray) -> float:
        """障害物近接コスト計算"""
        try:
            # 周囲の障害物密度をチェック
            obstacle_count = 0
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    for dz in [-1, 0, 1]:
                        check_pos = (pos[0] + dx, pos[1] + dy, pos[2] + dz)
                        if self._is_in_bounds(check_pos):
                            if terrain_data[check_pos] == 2:  # 障害物
                                obstacle_count += 1
            
            # 障害物が多いほどコストが高い
            if obstacle_count > 5:
                return 10.0
            elif obstacle_count > 2:
                return 2.0
            else:
                return 0.0
                
        except (IndexError, ValueError):
            return float('inf')
    
    def _is_in_bounds(self, pos: Tuple[int, int, int]) -> bool:
        """境界チェック"""
        x, y, z = pos
        return (0 <= x < self.grid_size[0] and 
                0 <= y < self.grid_size[1] and 
                0 <= z < self.grid_size[2])
    
    def is_valid_position(self, pos: Tuple[int, int, int], 
                         terrain_data: np.ndarray) -> bool:
        """
        有効な位置かチェック
        
        Args:
            pos: グリッド座標
            terrain_data: 地形データ
            
        Returns:
            有効な位置かどうか
        """
        if not self._is_in_bounds(pos):
            return False
        
        try:
            # 障害物でないことを確認
            return terrain_data[pos] != 2
        except (IndexError, ValueError):
            return False
    
    def world_to_grid(self, world_pos: Tuple[float, float, float]) -> Tuple[int, int, int]:
        """ワールド座標をグリッド座標に変換（適切な範囲）"""
        # 適切な範囲での座標変換
        min_bound = np.array([-2.5, -2.5, 0.0])  # 適切な範囲
        voxel_pos = (np.array(world_pos) - min_bound) / self.voxel_size
        return tuple(voxel_pos.astype(int))
    
    def grid_to_world(self, grid_pos: Tuple[int, int, int]) -> Tuple[float, float, float]:
        """グリッド座標をワールド座標に変換"""
        x, y, z = grid_pos
        world_x = (x - self.grid_size[0] // 2) * self.voxel_size
        world_y = (y - self.grid_size[1] // 2) * self.voxel_size
        world_z = (z - self.grid_size[2] // 2) * self.voxel_size
        return (world_x, world_y, world_z)
    
    def _reconstruct_path(self, goal_node: Node3D) -> List[Tuple[float, float, float]]:
        """経路を再構築"""
        path = []
        current = goal_node
        
        while current is not None:
            world_pos = self.grid_to_world((current.x, current.y, current.z))
            path.append(world_pos)
            current = current.parent
        
        path.reverse()
        return path
    
    def _create_success_result(self, path: List[Tuple[float, float, float]], 
                             computation_time: float) -> Dict[str, Any]:
        """成功結果を作成"""
        path_length = self._calculate_path_length(path)
        
        return {
            'success': True,
            'path': path,
            'path_length': path_length,
            'computation_time': computation_time,
            'nodes_explored': self.stats['nodes_explored'],
            'algorithm': 'A*',
            'error_message': ''
        }
    
    def _create_failure_result(self, error_message: str, 
                             computation_time: float = 0.0) -> Dict[str, Any]:
        """失敗結果を作成"""
        return {
            'success': False,
            'path': [],
            'path_length': 0.0,
            'computation_time': computation_time,
            'nodes_explored': self.stats['nodes_explored'],
            'algorithm': 'A*',
            'error_message': error_message
        }
    
    def _calculate_path_length(self, path: List[Tuple[float, float, float]]) -> float:
        """経路長を計算"""
        if len(path) < 2:
            return 0.0
        
        total_length = 0.0
        for i in range(len(path) - 1):
            p1, p2 = path[i], path[i + 1]
            distance = np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2 + (p2[2] - p1[2])**2)
            total_length += distance
        
        return total_length

def main():
    """テスト用メイン関数"""
    # テスト用の地形データ
    grid_size = (100, 100, 50)
    terrain_data = np.zeros(grid_size, dtype=int)
    
    # 障害物を配置
    terrain_data[50:60, 50:60, 20:30] = 2
    
    planner = AStarPlanner3D(grid_size)
    
    start = (0.0, 0.0, 0.0)
    goal = (5.0, 5.0, 2.0)
    
    result = planner.plan_path(start, goal, terrain_data)
    
    print("A* 3D Path Planning Result:")
    print(f"Success: {result['success']}")
    print(f"Path Length: {result['path_length']:.2f}m")
    print(f"Computation Time: {result['computation_time']:.3f}s")
    print(f"Nodes Explored: {result['nodes_explored']}")
    print(f"Error: {result['error_message']}")

if __name__ == "__main__":
    main()
