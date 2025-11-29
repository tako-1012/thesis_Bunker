"""
hierarchical_astar_3d.py
階層型A*（Hierarchical Pathfinding A*）の3D実装プロトタイプ
大域グリッドで粗い経路→局所グリッドで詳細経路を計画
既存TA*インターフェースに準拠
"""
import numpy as np
from typing import Tuple, List, Optional, Dict
from node_3d import Node3D

class HierarchicalAStar3D:
    def __init__(self, voxel_size=0.1, grid_size=(200,200,50), coarse_factor=5):
        self.voxel_size = voxel_size
        self.grid_size = grid_size
        self.coarse_factor = coarse_factor  # 粗グリッドの縮小率
        self.voxel_grid = None
        self.terrain_data = None

    def set_terrain_data(self, voxel_grid, terrain_data):
        self.voxel_grid = voxel_grid
        self.terrain_data = terrain_data

    def plan_path(self, start: Tuple[float, float, float], goal: Tuple[float, float, float], **kwargs):
        import time
        from planning_result import PlanningResult
        t0 = time.time()
        # coarse_factorを段階的に緩和して最大3回リトライ
        coarse_factors = [self.coarse_factor, max(1, self.coarse_factor//2), 1]
        for cf in coarse_factors:
            coarse_grid_size = tuple(max(1, s//cf) for s in self.grid_size)
            start_idx = self._world_to_voxel(start)
            goal_idx = self._world_to_voxel(goal)
            coarse_start = tuple(i//cf for i in start_idx)
            coarse_goal = tuple(i//cf for i in goal_idx)
            coarse_path = self._astar_on_grid(coarse_start, coarse_goal, coarse_grid_size)
            if not coarse_path:
                continue
            # 2. 各粗経路区間ごとに詳細グリッドでA*
            full_path = []
            for i in range(len(coarse_path)-1):
                local_start = tuple(x*cf for x in coarse_path[i])
                local_goal = tuple(x*cf for x in coarse_path[i+1])
                local_path = self._astar_on_grid(local_start, local_goal, self.grid_size)
                if not local_path:
                    break
                full_path.extend(local_path[:-1])
            else:
                full_path.append(tuple(x*cf for x in coarse_path[-1]))
                # 3. ボクセル→ワールド座標に変換
                path = [self._voxel_to_world(idx) for idx in full_path]
                path_length = 0.0
                for j in range(1, len(path)):
                    dx = path[j][0] - path[j-1][0]
                    dy = path[j][1] - path[j-1][1]
                    dz = path[j][2] - path[j-1][2]
                    path_length += (dx**2 + dy**2 + dz**2) ** 0.5
                return PlanningResult(
                    success=True,
                    path=path,
                    computation_time=time.time()-t0,
                    path_length=path_length,
                    nodes_explored=len(full_path),
                    error_message=""
                )
        # 全て失敗した場合
        return PlanningResult(
            success=False,
            path=[],
            computation_time=time.time()-t0,
            path_length=0.0,
            nodes_explored=0,
            error_message="coarse grid search failed (all retries)"
        )

    def _astar_on_grid(self, start, goal, grid_size):
        # シンプルな3D A*（障害物・傾斜は未考慮、後で拡張）
        open_list = []
        closed_set = set()
        node_map = {}
        start_node = Node3D(position=start, g_cost=0.0, h_cost=self._heuristic(start, goal), f_cost=0.0)
        open_list.append(start_node)
        node_map[start] = start_node
        while open_list:
            open_list.sort(key=lambda n: n.g_cost + n.h_cost)
            current = open_list.pop(0)
            if current.position == goal:
                return self._reconstruct_path(current)
            closed_set.add(current.position)
            for neighbor in self._get_neighbors(current.position, grid_size):
                if neighbor in closed_set:
                    continue
                g = current.g_cost + 1.0
                h = self._heuristic(neighbor, goal)
                if neighbor not in node_map or g < node_map[neighbor].g_cost:
                    neighbor_node = Node3D(position=neighbor, g_cost=g, h_cost=h, f_cost=g+h, parent=current)
                    node_map[neighbor] = neighbor_node
                    open_list.append(neighbor_node)
        return None

    def _get_neighbors(self, pos, grid_size):
        x, y, z = pos
        neighbors = []
        for dx in [-1,0,1]:
            for dy in [-1,0,1]:
                for dz in [-1,0,1]:
                    if dx==0 and dy==0 and dz==0:
                        continue
                    nx, ny, nz = x+dx, y+dy, z+dz
                    if 0<=nx<grid_size[0] and 0<=ny<grid_size[1] and 0<=nz<grid_size[2]:
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
