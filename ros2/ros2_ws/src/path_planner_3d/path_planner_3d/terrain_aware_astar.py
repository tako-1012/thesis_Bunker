"""
Terrain-Aware A*
探索時点から地形コストを考慮したA*
"""
import heapq
import math
import time
import numpy as np
from typing import Tuple, List


class TerrainAwareAStar:
    """
    Terrain-Aware A*

    A*アルゴリズムに地形コストを統合。
    移動コストを「距離 × 地形コスト」として計算。
    """

    def __init__(self, voxel_size=1.0, grid_size=(200, 200, 20),
                 terrain_weight=0.3, heuristic_multiplier=1.5,
                 prune_distance_factor=2.0, cost_limit_factor=3.0):
        self.voxel_size = voxel_size
        self.grid_size = grid_size
        self.voxel_grid = None
        self.terrain_data = None
        self.min_bound = None
        # parameters for improvements
        self.terrain_weight = terrain_weight
        self.heuristic_multiplier = heuristic_multiplier
        self.prune_distance_factor = prune_distance_factor
        self.cost_limit_factor = cost_limit_factor
        self.last_search_stats = {
            'nodes_explored': 0,
            'computation_time': 0.0,
            'path_length': 0.0
        }

    def set_terrain_data(self, voxel_grid, terrain_data=None, min_bound=None):
        """地形データを設定"""
        self.voxel_grid = voxel_grid
        self.terrain_data = terrain_data

        if min_bound is not None:
            self.min_bound = np.array(min_bound)
        else:
            half_x = (self.grid_size[0] * self.voxel_size) / 2.0
            half_y = (self.grid_size[1] * self.voxel_size) / 2.0
            self.min_bound = np.array([-half_x, -half_y, 0.0])

    def _world_to_voxel(self, pos: Tuple[float, float, float]):
        wp = np.array(pos)
        vp = (wp - self.min_bound) / self.voxel_size
        return tuple(int(round(v)) for v in vp)

    def _voxel_to_world(self, idx: Tuple[int, int, int]):
        vi = np.array(idx)
        wp = self.min_bound + (vi + 0.5) * self.voxel_size
        return tuple(wp)

    def _clamp(self, idx):
        x, y, z = idx
        x = min(max(int(x), 0), self.grid_size[0] - 1)
        y = min(max(int(y), 0), self.grid_size[1] - 1)
        z = min(max(int(z), 0), self.grid_size[2] - 1)
        return (x, y, z)

    def _is_free(self, idx):
        if self.voxel_grid is None:
            return True
        cx, cy, cz = self._clamp(idx)
        try:
            return self.voxel_grid[cx, cy, cz] <= 0.5
        except Exception:
            return True

    def _heuristic(self, a, b):
        """
        改善版ヒューリスティック: 直線距離 × 想定平均地形コスト（保守的）
        """
        dx = a[0] - b[0]
        dy = a[1] - b[1]
        dz = a[2] - b[2]
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)
        return distance * float(self.heuristic_multiplier)

    def _compute_terrain_cost(self, idx):
        if self.terrain_data is None:
            return 1.0
        idx = self._clamp(idx)
        slope_cost = self._compute_slope_cost(idx)
        roughness_cost = self._compute_roughness_cost(idx)
        density_cost = self._compute_density_cost(idx)
        total = slope_cost * roughness_cost * density_cost
        return float(min(total, 10.0))

    def _compute_slope_cost(self, idx):
        if self.terrain_data is None:
            return 1.0
        # Support both 'elevation' and 'height_map' keys
        elevation = None
        if 'elevation' in self.terrain_data:
            elevation = self.terrain_data['elevation']
        elif 'height_map' in self.terrain_data:
            elevation = self.terrain_data['height_map']
        else:
            return 1.0
        try:
            x, y, z = idx
            current_elev = elevation[x, y, z]
            max_slope = 0.0
            neighbors = [
                (x+1, y, z), (x-1, y, z), (x, y+1, z), (x, y-1, z),
                (x+1, y+1, z), (x+1, y-1, z), (x-1, y+1, z), (x-1, y-1, z)
            ]
            for nx, ny, nz in neighbors:
                if (0 <= nx < elevation.shape[0] and 0 <= ny < elevation.shape[1] and 0 <= nz < elevation.shape[2]):
                    neighbor_elev = elevation[nx, ny, nz]
                    slope = abs(neighbor_elev - current_elev) / max(1e-6, self.voxel_size)
                    max_slope = max(max_slope, slope)
            slope_degrees = np.degrees(np.arctan(max_slope))
            if slope_degrees < 15:
                return 1.0 + slope_degrees / 30.0
            elif slope_degrees < 30:
                return 1.5 + (slope_degrees - 15) / 15.0
            else:
                return float(min(2.5 + (slope_degrees - 30) / 30.0, 3.0))
        except Exception:
            return 1.0

    def _compute_roughness_cost(self, idx):
        if self.terrain_data is None or 'roughness' not in self.terrain_data:
            return 1.0
        try:
            roughness = self.terrain_data['roughness']
            x, y, z = idx
            rough_value = float(roughness[x, y, z])
            return 1.0 + rough_value
        except Exception:
            return 1.0

    def _compute_density_cost(self, idx):
        if self.terrain_data is None or 'density' not in self.terrain_data:
            return 1.0
        try:
            density = self.terrain_data['density']
            x, y, z = idx
            density_value = float(density[x, y, z])
            return 1.0 + (1.0 - density_value)
        except Exception:
            return 1.0

    def _movement_cost(self, current_idx, neighbor_idx):
        dx = neighbor_idx[0] - current_idx[0]
        dy = neighbor_idx[1] - current_idx[1]
        dz = neighbor_idx[2] - current_idx[2]
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)
        terrain_cost = self._compute_terrain_cost(neighbor_idx)
        # adjusted terrain cost with weight (1.0 + w*(terrain-1.0))
        adjusted_terrain_cost = 1.0 + float(self.terrain_weight) * (terrain_cost - 1.0)
        return distance * adjusted_terrain_cost

    def plan_path(self, start: Tuple[float, float, float],
                  goal: Tuple[float, float, float],
                  voxel_grid=None,
                  max_iters=500000,
                  timeout=None):
        t0 = time.time()
        s = self._world_to_voxel(start)
        g = self._world_to_voxel(goal)
        s = self._clamp(s)
        g = self._clamp(g)
        open_heap = []
        g_score = {s: 0.0}
        parent = {s: s}
        # straight_distance (heuristic without extra multiplier for pruning)
        # use raw euclidean for distance-based pruning
        raw_dx = s[0] - g[0]
        raw_dy = s[1] - g[1]
        raw_dz = s[2] - g[2]
        straight_distance = math.sqrt(raw_dx * raw_dx + raw_dy * raw_dy + raw_dz * raw_dz)
        f0 = self._heuristic(s, g)
        heapq.heappush(open_heap, (f0, 0.0, s))
        closed = set()
        nodes = 0
        while open_heap and nodes < max_iters:
            if timeout and time.time() - t0 > timeout:
                break
            _, _, current = heapq.heappop(open_heap)
            nodes += 1
            if current == g:
                path = []
                node = current
                while True:
                    path.append(self._voxel_to_world(node))
                    if node == parent.get(node, node):
                        break
                    node = parent[node]
                path.reverse()
                path_length = 0.0
                for i in range(len(path) - 1):
                    p1 = np.array(path[i])
                    p2 = np.array(path[i + 1])
                    path_length += np.linalg.norm(p2 - p1)
                self.last_search_stats = {
                    'nodes_explored': nodes,
                    'computation_time': time.time() - t0,
                    'path_length': path_length
                }
                try:
                    from planning_result import PlanningResult
                    return PlanningResult(
                        success=True,
                        path=path,
                        computation_time=time.time() - t0,
                        path_length=path_length,
                        nodes_explored=nodes,
                        algorithm_name='TerrainAwareA*'
                    )
                except Exception:
                    return {
                        'success': True,
                        'path': path,
                        'computation_time': time.time() - t0,
                        'path_length': path_length,
                        'nodes_explored': nodes,
                        'algorithm_name': 'TerrainAwareA*'
                    }
            if current in closed:
                continue
            closed.add(current)
            cx, cy, cz = current
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    for dz in [-1, 0, 1]:
                        if dx == 0 and dy == 0 and dz == 0:
                            continue
                        nb = (cx + dx, cy + dy, cz + dz)
                        nb = self._clamp(nb)
                        if not self._is_free(nb):
                            continue
                        if nb in closed:
                            continue
                        move_cost = self._movement_cost(current, nb)
                        tentative_g = g_score[current] + move_cost
                        # 距離制限: ゴールから遠すぎるノードは展開しない
                        dist_to_goal_raw = math.sqrt((nb[0]-g[0])**2 + (nb[1]-g[1])**2 + (nb[2]-g[2])**2)
                        if dist_to_goal_raw > straight_distance * float(self.prune_distance_factor):
                            continue
                        # コスト上限: 過剰にコストの高い経路は破棄
                        if tentative_g > straight_distance * float(self.cost_limit_factor):
                            continue
                        if tentative_g < g_score.get(nb, float('inf')):
                            parent[nb] = current
                            g_score[nb] = tentative_g
                            f = tentative_g + self._heuristic(nb, g)
                            heapq.heappush(open_heap, (f, tentative_g, nb))
        try:
            from planning_result import PlanningResult
            return PlanningResult(
                success=False,
                path=[],
                computation_time=time.time() - t0,
                path_length=0.0,
                nodes_explored=nodes,
                algorithm_name='TerrainAwareA*'
            )
        except Exception:
            return {
                'success': False,
                'path': [],
                'computation_time': time.time() - t0,
                'path_length': 0.0,
                'nodes_explored': nodes,
                'algorithm_name': 'TerrainAwareA*'
            }
