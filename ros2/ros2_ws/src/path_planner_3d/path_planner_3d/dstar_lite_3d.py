"""
dstar_lite_3d.py
D* Liteアルゴリズムの3Dグリッド版プロトタイプ
既存TA*インターフェースに準拠
"""
import numpy as np
from typing import Tuple, List, Optional, Dict
from node_3d import Node3D
import heapq

class DStarLite3D:
    def __init__(self, voxel_size=0.1, grid_size=(200,200,50)):
        self.voxel_size = voxel_size
        self.grid_size = grid_size
        self.voxel_grid = None
        self.terrain_data = None
        self.min_bound = (0.0, 0.0, 0.0)
        self.nodes_explored = 0  # 探索ノード数カウンタ

    def set_terrain_data(self, voxel_grid, terrain_data, min_bound=(0.0, 0.0, 0.0)):
        self.voxel_grid = voxel_grid
        self.terrain_data = terrain_data
        self.min_bound = tuple(min_bound)

    def plan_path(self, start: Tuple[float, float, float], goal: Tuple[float, float, float], **kwargs):
        import time
        from planning_result import PlanningResult
        t0 = time.time()
        total_nodes_explored = 0  # 全リトライでの探索ノード数を累積
        # グリッドサイズを段階的に拡大して最大3回リトライ
        grid_sizes = [self.grid_size, tuple(int(s*1.5) for s in self.grid_size), tuple(int(s*2) for s in self.grid_size)]
        for gs in grid_sizes:
            self.grid_size = gs
            start_idx = self._world_to_voxel(start)
            goal_idx = self._world_to_voxel(goal)
            path = self._dstar_lite_on_grid(start_idx, goal_idx)
            total_nodes_explored += self.nodes_explored  # 累積
            if path:
                world_path = [self._voxel_to_world(idx) for idx in path]
                path_length = 0.0
                for j in range(1, len(world_path)):
                    dx = world_path[j][0] - world_path[j-1][0]
                    dy = world_path[j][1] - world_path[j-1][1]
                    dz = world_path[j][2] - world_path[j-1][2]
                    path_length += (dx**2 + dy**2 + dz**2) ** 0.5
                return PlanningResult(
                    success=True,
                    path=world_path,
                    computation_time=time.time()-t0,
                    path_length=path_length,
                    nodes_explored=total_nodes_explored,  # 累積ノード数を使用
                    error_message=""
                )
        # 全て失敗した場合
        return PlanningResult(
            success=False,
            path=[],
            computation_time=time.time()-t0,
            path_length=0.0,
            nodes_explored=0,
            error_message="dstar_lite grid search failed (all retries)"
        )

    def _dstar_lite_on_grid(self, start, goal):
        # 実装簡略化のためA*に近い動作（本来はrhs/g値・再計画対応）
        open_list = []
        closed_set = set()
        node_map = {}
        start_node = Node3D(position=start, g_cost=0.0, h_cost=self._heuristic(start, goal), f_cost=0.0)
        heapq.heappush(open_list, (start_node.g_cost + start_node.h_cost, start_node))
        node_map[start] = start_node
        self.nodes_explored = 0  # Reset counter
        while open_list:
            _, current = heapq.heappop(open_list)
            self.nodes_explored += 1  # Count explored nodes
            if current.position == goal:
                return self._reconstruct_path(current)
            closed_set.add(current.position)
            for neighbor in self._get_neighbors(current.position):
                if neighbor in closed_set:
                    continue
                move_cost = self._compute_movement_cost(current.position, neighbor)
                g = current.g_cost + move_cost
                h = self._heuristic(neighbor, goal)
                if neighbor not in node_map or g < node_map[neighbor].g_cost:
                    neighbor_node = Node3D(position=neighbor, g_cost=g, h_cost=h, f_cost=g+h, parent=current)
                    node_map[neighbor] = neighbor_node
                    heapq.heappush(open_list, (neighbor_node.g_cost + neighbor_node.h_cost, neighbor_node))
        return None

    def _get_neighbors(self, pos):
        x, y, z = pos
        neighbors = []
        for dx in [-1,0,1]:
            for dy in [-1,0,1]:
                for dz in [-1,0,1]:
                    if dx==0 and dy==0 and dz==0:
                        continue
                    nx, ny, nz = x+dx, y+dy, z+dz
                    if 0<=nx<self.grid_size[0] and 0<=ny<self.grid_size[1] and 0<=nz<self.grid_size[2]:
                        neighbors.append((nx,ny,nz))
        return neighbors

    def _heuristic(self, pos, goal):
        dx, dy, dz = [a-b for a,b in zip(pos, goal)]
        return np.sqrt(dx*dx + dy*dy + dz*dz)

    def _compute_movement_cost(self, current_pos, neighbor_pos):
        """移動コストを計算（Euclidean距離 × 地形コスト）"""
        # Euclidean distance
        dx = neighbor_pos[0] - current_pos[0]
        dy = neighbor_pos[1] - current_pos[1]
        dz = neighbor_pos[2] - current_pos[2]
        distance = np.sqrt(dx*dx + dy*dy + dz*dz)
        
        # Terrain cost
        terrain_cost = self._compute_terrain_cost(neighbor_pos)
        
        return distance * terrain_cost

    def _compute_terrain_cost(self, voxel_idx):
        """地形コストを計算（height_mapを使用、勾配に応じて段階的に増加）"""
        if self.terrain_data is None:
            return 1.0
        
        if 'height_map' not in self.terrain_data:
            return 1.0
        
        try:
            height_map = self.terrain_data['height_map']
            x, y, z = voxel_idx
            x = min(max(int(x), 0), height_map.shape[0] - 1)
            y = min(max(int(y), 0), height_map.shape[1] - 1)
            
            # Get current and neighbor heights to compute slope
            current_height = float(height_map[x, y])
            
            # Compute max slope to neighbors
            max_slope = 0.0
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    nx = x + dx
                    ny = y + dy
                    if 0 <= nx < height_map.shape[0] and 0 <= ny < height_map.shape[1]:
                        neighbor_height = float(height_map[nx, ny])
                        slope = abs(neighbor_height - current_height)
                        max_slope = max(max_slope, slope)
            
            # Convert to degrees and compute cost with fine-grained scaling
            slope_degrees = np.degrees(np.arctan(max_slope))
            
            # More granular cost function for extreme terrain
            if slope_degrees < 10:
                terrain_cost = 1.0
            elif slope_degrees < 20:
                terrain_cost = 1.0 + (slope_degrees - 10) / 20.0  # 1.0 to 1.5
            elif slope_degrees < 30:
                terrain_cost = 1.5 + (slope_degrees - 20) / 20.0  # 1.5 to 2.0
            elif slope_degrees < 40:
                terrain_cost = 2.0 + (slope_degrees - 30) / 20.0  # 2.0 to 2.5
            elif slope_degrees < 50:
                terrain_cost = 2.5 + (slope_degrees - 40) / 20.0  # 2.5 to 3.0
            else:
                terrain_cost = 3.0 + (slope_degrees - 50) / 40.0  # 3.0 to 4.0 for extreme slopes
                terrain_cost = min(terrain_cost, 5.0)  # Cap at 5.0
            
            return float(terrain_cost)
        except Exception as e:
            return 1.0

    def _reconstruct_path(self, node):
        path = []
        while node:
            path.append(node.position)
            node = node.parent
        return path[::-1]

    def _world_to_voxel(self, pos):
        # consider min_bound offset so that world coordinates can be centered
        mx, my, mz = self.min_bound
        wx, wy, wz = pos
        vx = int(round((wx - mx) / self.voxel_size))
        vy = int(round((wy - my) / self.voxel_size))
        vz = int(round((wz - mz) / self.voxel_size))
        return (vx, vy, vz)

    def _voxel_to_world(self, idx):
        mx, my, mz = self.min_bound
        return tuple((i+0.5)*self.voxel_size + off for i, off in zip(idx, (mx, my, mz)))
