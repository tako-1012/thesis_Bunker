import heapq
import math
import time
from typing import Tuple, List, Optional, Dict
import numpy as np


def _bresenham3d(a, b):
    """3D Bresenham integer voxel traversal between integer voxel coordinates a->b.
    Yields voxel indices including both endpoints."""
    x1, y1, z1 = a
    x2, y2, z2 = b
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    dz = abs(z2 - z1)
    xs = 1 if x2 > x1 else -1
    ys = 1 if y2 > y1 else -1
    zs = 1 if z2 > z1 else -1

    # Drive axis X
    if dx >= dy and dx >= dz:
        py = 2 * dy - dx
        pz = 2 * dz - dx
        y = y1
        z = z1
        for x in range(x1, x2 + xs, xs):
            yield (x, y, z)
            if py >= 0:
                y += ys
                py -= 2 * dx
            if pz >= 0:
                z += zs
                pz -= 2 * dx
            py += 2 * dy
            pz += 2 * dz

    # Drive axis Y
    elif dy >= dx and dy >= dz:
        px = 2 * dx - dy
        pz = 2 * dz - dy
        x = x1
        z = z1
        for y in range(y1, y2 + ys, ys):
            yield (x, y, z)
            if px >= 0:
                x += xs
                px -= 2 * dy
            if pz >= 0:
                z += zs
                pz -= 2 * dy
            px += 2 * dx
            pz += 2 * dz

    # Drive axis Z
    else:
        px = 2 * dx - dz
        py = 2 * dy - dz
        x = x1
        y = y1
        for z in range(z1, z2 + zs, zs):
            yield (x, y, z)
            if px >= 0:
                x += xs
                px -= 2 * dz
            if py >= 0:
                y += ys
                py -= 2 * dz
            px += 2 * dx
            py += 2 * dy


class ThetaStar:
    def __init__(self, voxel_size=0.1, grid_size=(200, 200, 50), min_bound=None):
        self.voxel_size = voxel_size
        self.grid_size = tuple(grid_size)
        self.min_bound = np.array(min_bound) if min_bound is not None else None
        self.voxel_grid = None
        self.last_search_stats = {'nodes_explored': 0, 'computation_time': 0.0, 'path_length': 0}

    def set_terrain_data(self, voxel_grid, terrain_data=None, min_bound=None):
        self.voxel_grid = voxel_grid
        if min_bound is not None:
            self.min_bound = np.array(min_bound)
        # if min_bound still None, default to center-based same as TA*
        if self.min_bound is None:
            half_x = (self.grid_size[0] * self.voxel_size) / 2.0
            half_y = (self.grid_size[1] * self.voxel_size) / 2.0
            self.min_bound = np.array([-half_x, -half_y, 0.0])

    def _world_to_voxel(self, pos: Tuple[float, float, float]) -> Tuple[int, int, int]:
        wp = np.array(pos)
        vp = (wp - self.min_bound) / self.voxel_size
        return tuple(vp.astype(int))

    def _voxel_to_world(self, idx: Tuple[int, int, int]) -> Tuple[float, float, float]:
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
        # align with TA* occupancy: occupied if > 0.5
        try:
            return self.voxel_grid[cx, cy, cz] <= 0.5
        except Exception:
            return True

    def _heuristic(self, a, b):
        dx = a[0] - b[0]
        dy = a[1] - b[1]
        dz = a[2] - b[2]
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    def _line_of_sight(self, a, b):
        # a, b are integer voxel indices
        for v in _bresenham3d(a, b):
            if not self._is_free(v):
                return False
        return True

    def plan_path(self, start: Tuple[float, float, float], goal: Tuple[float, float, float], max_iters=200000):
        t0 = time.time()
        s = self._world_to_voxel(start)
        g = self._world_to_voxel(goal)

        # clamp into grid
        s = self._clamp(s)
        g = self._clamp(g)

        open_heap = []  # (f, g_cost, node)
        g_score: Dict[Tuple[int, int, int], float] = {s: 0.0}
        parent: Dict[Tuple[int, int, int], Tuple[int, int, int]] = {s: s}
        f0 = self._heuristic(s, g)
        heapq.heappush(open_heap, (f0, 0.0, s))
        closed = set()
        nodes = 0

        while open_heap and nodes < max_iters:
            _, _, current = heapq.heappop(open_heap)
            nodes += 1
            if current == g:
                # reconstruct path in world coords
                path = []
                node = current
                while True:
                    path.append(self._voxel_to_world(node))
                    if node == parent.get(node, node):
                        break
                    node = parent[node]
                path.reverse()
                self.last_search_stats = {'nodes_explored': nodes, 'computation_time': time.time() - t0, 'path_length': len(path)}
                return path

            closed.add(current)

            cx, cy, cz = current
            # neighbors 26-neighborhood
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    for dz in [-1, 0, 1]:
                        if dx == 0 and dy == 0 and dz == 0:
                            continue
                        nb = (cx + dx, cy + dy, cz + dz)
                        nb_clamped = self._clamp(nb)
                        if nb_clamped in closed:
                            continue
                        if not self._is_free(nb_clamped):
                            continue

                        # Theta* parent update
                        p = parent[current]
                        if self._line_of_sight(p, nb_clamped):
                            tentative_g = g_score[p] + self._heuristic(p, nb_clamped)
                            if tentative_g < g_score.get(nb_clamped, float('inf')):
                                parent[nb_clamped] = p
                                g_score[nb_clamped] = tentative_g
                                f = tentative_g + self._heuristic(nb_clamped, g)
                                heapq.heappush(open_heap, (f, tentative_g, nb_clamped))
                        else:
                            tentative_g = g_score[current] + self._heuristic(current, nb_clamped)
                            if tentative_g < g_score.get(nb_clamped, float('inf')):
                                parent[nb_clamped] = current
                                g_score[nb_clamped] = tentative_g
                                f = tentative_g + self._heuristic(nb_clamped, g)
                                heapq.heappush(open_heap, (f, tentative_g, nb_clamped))

        # failed
        self.last_search_stats = {'nodes_explored': nodes, 'computation_time': time.time() - t0, 'path_length': 0}
        return None

