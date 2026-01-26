"""
Field D* - D*Lite を拡張しエッジ上の線形補間で任意角経路を生成する簡易実装

注: 教材的な最小実装。まず D*Lite を実行してグリッド経路を得た後、任意角化のため
視線短絡（any-angle shortcut）と、エッジ上の補間点を試して経路長を短縮する。
"""
import math
from typing import Tuple, List, Optional
import numpy as np

try:
    from .dstar_lite_3d import DStarLite3D
except Exception:
    from dstar_lite_3d import DStarLite3D

try:
    from .planning_result import PlanningResult
except Exception:
    from planning_result import PlanningResult


def _bresenham3d(a, b):
    x1, y1, z1 = a
    x2, y2, z2 = b
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    dz = abs(z2 - z1)
    xs = 1 if x2 > x1 else -1
    ys = 1 if y2 > y1 else -1
    zs = 1 if z2 > z1 else -1

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


class FieldDStar:
    def __init__(self, voxel_size=1.0, grid_size=(200,200,20)):
        self.voxel_size = voxel_size
        self.grid_size = grid_size
        self.voxel_grid = None
        self.terrain_data = None
        self.last_search_stats = {'nodes_explored':0,'computation_time':0.0,'path_length':0.0}

    def set_terrain_data(self, voxel_grid, terrain_data=None, min_bound=(0.0,0.0,0.0)):
        self.voxel_grid = voxel_grid
        self.terrain_data = terrain_data
        self.min_bound = np.array(min_bound)

    def _world_to_voxel(self, pos: Tuple[float,float,float]):
        wp = np.array(pos)
        vp = (wp - self.min_bound) / self.voxel_size
        return tuple(int(round(v)) for v in vp)

    def _voxel_to_world(self, idx):
        return tuple((i + 0.5) * self.voxel_size + self.min_bound[d] for d,i in enumerate(idx))

    def _is_free_voxel(self, idx):
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

    def _line_of_sight(self, a_idx, b_idx):
        for v in _bresenham3d(a_idx, b_idx):
            if not self._is_free_voxel(v):
                return False
        return True

    def _path_length(self, path_world: List[Tuple[float,float,float]]):
        if not path_world or len(path_world) < 2:
            return 0.0
        s = 0.0
        for i in range(len(path_world)-1):
            a = np.array(path_world[i])
            b = np.array(path_world[i+1])
            s += float(np.linalg.norm(b-a))
        return s

    def _world_to_voxel_index(self, p):
        # for arbitrary world point, map to voxel index (floor)
        v = (np.array(p) - self.min_bound) / self.voxel_size
        return tuple(int(math.floor(x)) for x in v)

    def _segment_collision_free_world(self, a_world, b_world):
        a_idx = self._world_to_voxel_index(a_world)
        b_idx = self._world_to_voxel_index(b_world)
        return self._line_of_sight(a_idx, b_idx)

    def plan_path(self, start, goal, **kwargs) -> PlanningResult:
        import time
        t0 = time.time()
        # Use D*Lite to get base grid path
        dstar = DStarLite3D(voxel_size=self.voxel_size, grid_size=self.grid_size)
        dstar.set_terrain_data(self.voxel_grid, self.terrain_data)
        base_result = dstar.plan_path(start, goal)
        if not base_result.success:
            return PlanningResult(success=False, path=[], computation_time=time.time()-t0, path_length=0.0, nodes_explored=0, error_message='D*Lite failed', algorithm_name='FieldD*')

        base_path = base_result.path
        base_len = base_result.path_length

        # Shortcut in world coordinates: for each index try to connect to farthest later point with LOS
        world_pts = base_path
        idx_pts = [self._world_to_voxel(p) for p in world_pts]
        new_world = [world_pts[0]]
        i = 0
        n = len(world_pts)
        while i < n-1:
            j = n-1
            while j > i:
                if self._line_of_sight(idx_pts[i], idx_pts[j]):
                    break
                j -= 1
            # connect to j (farthest visible)
            new_world.append(world_pts[j])
            i = j

        new_len = self._path_length(new_world)
        # choose shorter between base and new
        if new_len < base_len:
            final_path = new_world
            final_len = new_len
        else:
            final_path = base_path
            final_len = base_len

        # Post-process: try edge interpolation (sampled alphas) to reduce length
        improved = True
        path = final_path
        while improved:
            improved = False
            new_path = [path[0]]
            for k in range(1, len(path)-1):
                prev = new_path[-1]
                curr = path[k]
                nxt = path[k+1]
                # try interpolation from curr towards nxt (sampled alpha)
                best = curr
                best_len = self._path_length(new_path + [curr] + path[k+1:])
                for alpha in [0.25, 0.5, 0.75]:
                    interp = (curr[0]* (1-alpha) + nxt[0]*alpha,
                              curr[1]* (1-alpha) + nxt[1]*alpha,
                              curr[2]* (1-alpha) + nxt[2]*alpha)
                    if not self._segment_collision_free_world(prev, interp):
                        continue
                    if not self._segment_collision_free_world(interp, nxt):
                        continue
                    cand_path = new_path + [interp] + path[k+1:]
                    cand_len = self._path_length(cand_path)
                    if cand_len + 1e-6 < best_len:
                        best_len = cand_len
                        best = interp
                        improved = True
                new_path.append(best)
            new_path.append(path[-1])
            path = new_path

        return PlanningResult(success=True, path=path, computation_time=time.time()-t0, path_length=self._path_length(path), nodes_explored=len(path), algorithm_name='FieldD*')
