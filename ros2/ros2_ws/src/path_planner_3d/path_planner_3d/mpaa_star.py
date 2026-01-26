"""
mpaa_star.py
Multipath Adaptive A* (MPAA*) - 学習的にヒューリスティックを更新する簡易実装

挙動:
- 通常のグリッドA* を実行
- 探索終了後に訪問ノードのヒューリスティックを更新し保存
- 次回以降の探索で更新済みヒューリスティックを利用

注: 教育目的の最小実装。既存コードベースの `PlanningResult` とグリッド表現を使います。
"""
import time
import heapq
from typing import Tuple, List, Optional
import numpy as np

try:
    from .planning_result import PlanningResult
except Exception:
    from planning_result import PlanningResult


class MPAAStar:
    def __init__(self, voxel_size: float = 1.0, grid_size=(200,200,20)):
        self.voxel_size = voxel_size
        self.grid_size = grid_size
        self.voxel_grid = None
        self.min_bound = np.zeros(3)

        # 学習済みヒューリスティック値: key = voxel index tuple, value = heuristic (float)
        self.h_values = {}

    def set_terrain_data(self, voxel_grid, terrain_data=None, min_bound=None):
        self.voxel_grid = voxel_grid
        if min_bound is not None:
            self.min_bound = np.array(min_bound)

    def _world_to_voxel(self, pos: Tuple[float,float,float]):
        # dstar_lite と同様に round を使う
        return tuple(int(round((p - b) / self.voxel_size)) for p,b in zip(pos, self.min_bound))

    def _voxel_to_world(self, idx):
        return tuple((i + 0.5) * self.voxel_size + self.min_bound[d] for d,i in enumerate(idx))

    def _is_free(self, idx):
        if self.voxel_grid is None:
            return True
        x,y,z = idx
        x = min(max(int(x),0), self.voxel_grid.shape[0]-1)
        y = min(max(int(y),0), self.voxel_grid.shape[1]-1)
        z = min(max(int(z),0), self.voxel_grid.shape[2]-1)
        try:
            return self.voxel_grid[x,y,z] <= 0.5
        except Exception:
            return True

    def _get_neighbors(self, pos):
        x,y,z = pos
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

    def _distance(self, a, b):
        a = np.array(a, dtype=float)
        b = np.array(b, dtype=float)
        return float(np.linalg.norm(a - b) * self.voxel_size)

    def _path_length(self, path_voxels: List[Tuple[int,int,int]]):
        if not path_voxels or len(path_voxels) < 2:
            return 0.0
        s = 0.0
        for i in range(len(path_voxels)-1):
            s += self._distance(path_voxels[i], path_voxels[i+1])
        return s

    def _reconstruct_path(self, parent, current):
        path = [current]
        while current in parent and parent[current] != current:
            current = parent[current]
            path.append(current)
        return path[::-1]

    def _heuristic(self, node, goal):
        # 学習済みヒューリスティックがあれば使用、なければEuclid
        if node in self.h_values:
            return float(self.h_values[node])
        # 未学習: voxel-level Euclidean
        dx = node[0] - goal[0]
        dy = node[1] - goal[1]
        dz = node[2] - goal[2]
        return float((dx*dx + dy*dy + dz*dz) ** 0.5 * self.voxel_size)

    def _update_heuristics(self, closed_set, g_scores, goal):
        # goal は voxel index
        g_goal = g_scores.get(goal, float('inf'))
        if not np.isfinite(g_goal):
            return
        for node in closed_set:
            if node in g_scores:
                # h_new = g(goal) - g(node)
                val = g_goal - g_scores[node]
                # 安全のため下限0
                self.h_values[node] = float(max(0.0, val))

    def plan_path(self, start, goal, timeout: Optional[float]=None, max_nodes: int = 100000) -> PlanningResult:
        t0 = time.time()
        start_v = self._world_to_voxel(start)
        goal_v = self._world_to_voxel(goal)

        open_heap = []
        g_scores = {start_v: 0.0}
        f_scores = {start_v: self._heuristic(start_v, goal_v)}
        parent = {start_v: start_v}
        closed_set = set()

        heapq.heappush(open_heap, (f_scores[start_v], start_v))
        nodes = 0

        while open_heap and nodes < max_nodes:
            if timeout and (time.time() - t0) > timeout:
                break

            _, current = heapq.heappop(open_heap)
            nodes += 1

            if current == goal_v:
                # reconstruct voxel path and convert to world
                vox_path = self._reconstruct_path(parent, current)
                world_path = [self._voxel_to_world(v) for v in vox_path]
                path_length = self._path_length(vox_path)
                # update heuristics based on closed set
                self._update_heuristics(closed_set, g_scores, goal_v)
                return PlanningResult(
                    success=True,
                    path=world_path,
                    computation_time=time.time()-t0,
                    path_length=path_length,
                    nodes_explored=nodes,
                    algorithm_name='MPAA*'
                )

            if current in closed_set:
                continue
            closed_set.add(current)

            for neighbor in self._get_neighbors(current):
                if not self._is_free(neighbor):
                    continue
                tentative_g = g_scores[current] + self._distance(current, neighbor)
                if tentative_g < g_scores.get(neighbor, float('inf')):
                    g_scores[neighbor] = tentative_g
                    f_scores[neighbor] = tentative_g + self._heuristic(neighbor, goal_v)
                    parent[neighbor] = current
                    heapq.heappush(open_heap, (f_scores[neighbor], neighbor))

        # 失敗（タイムアウトまたはノード上限）
        # ヒューリスティックは部分的に更新しておく
        self._update_heuristics(closed_set, g_scores, goal_v)
        return PlanningResult(
            success=False,
            path=[],
            computation_time=time.time()-t0,
            path_length=0.0,
            nodes_explored=nodes,
            algorithm_name='MPAA*'
        )
