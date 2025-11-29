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

    def set_terrain_data(self, voxel_grid, terrain_data):
        self.voxel_grid = voxel_grid
        self.terrain_data = terrain_data

    def plan_path(self, start: Tuple[float, float, float], goal: Tuple[float, float, float], **kwargs):
        import time
        from planning_result import PlanningResult
        t0 = time.time()
        # グリッドサイズを段階的に拡大して最大3回リトライ
        grid_sizes = [self.grid_size, tuple(int(s*1.5) for s in self.grid_size), tuple(int(s*2) for s in self.grid_size)]
        for gs in grid_sizes:
            self.grid_size = gs
            start_idx = self._world_to_voxel(start)
            goal_idx = self._world_to_voxel(goal)
            path = self._dstar_lite_on_grid(start_idx, goal_idx)
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
                    nodes_explored=len(path),
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
        while open_list:
            _, current = heapq.heappop(open_list)
            if current.position == goal:
                return self._reconstruct_path(current)
            closed_set.add(current.position)
            for neighbor in self._get_neighbors(current.position):
                if neighbor in closed_set:
                    continue
                g = current.g_cost + 1.0
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

    def _reconstruct_path(self, node):
        path = []
        while node:
            path.append(node.position)
            node = node.parent
        return path[::-1]

    def _world_to_voxel(self, pos):
        return tuple(int(round(x/self.voxel_size)) for x in pos)

    def _voxel_to_world(self, idx):
        return tuple((i+0.5)*self.voxel_size for i in idx)
