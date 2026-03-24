"""
Field D* Hybrid - D*Lite 基路の滑動ウィンドウ局所最適化（any-angle postprocessing）

アルゴリズム:
- D*Lite で基路を取得
- スライディングウィンドウ（デフォルト幅 3）で局所補間を試行
- 中点・分割点で補間（alpha の集合）を試行し、衝突なしかつ経路短縮なら適用
- 最後に視線ショートカットを実施

この手法は Field D* の完全実装ではなく、実用的で高速な妥協案です。
"""
import time
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


class FieldDStarHybrid:
    def __init__(self, voxel_size: float = 1.0, grid_size=(200,200,20), use_terrain_cost: bool = True):
        self.voxel_size = voxel_size
        self.grid_size = grid_size
        self.voxel_grid = None
        self.terrain_data = None
        self.min_bound = np.array((0.0,0.0,0.0))
        self.last_search_stats = {'nodes_explored':0,'computation_time':0.0,'path_length':0.0}
        self.use_terrain_cost = use_terrain_cost

    def set_terrain_data(self, voxel_grid, terrain_data=None, min_bound=(0.0,0.0,0.0)):
        self.voxel_grid = voxel_grid
        self.terrain_data = terrain_data
        self.min_bound = np.array(min_bound)

    def _world_to_voxel(self, pos: Tuple[float,float,float]):
        wp = np.array(pos)
        vp = (wp - self.min_bound) / self.voxel_size
        return tuple(int(math.floor(v)) for v in vp)

    def _voxel_to_world_center(self, idx):
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

    def _line_of_sight(self, a_world, b_world):
        a_idx = self._world_to_voxel(a_world)
        b_idx = self._world_to_voxel(b_world)
        for v in _bresenham3d(a_idx, b_idx):
            if not self._is_free_voxel(v):
                return False
        return True

    def _interpolate(self, a, b, alpha: float):
        return (a[0]*(1-alpha)+b[0]*alpha, a[1]*(1-alpha)+b[1]*alpha, a[2]*(1-alpha)+b[2]*alpha)

    def _segment_length(self, a, b, c):
        # length of path a->b->c
        return float(np.linalg.norm(np.array(b)-np.array(a)) + np.linalg.norm(np.array(c)-np.array(b)))

    def _compute_terrain_cost(self, point_world, next_point_world):
        """
        Compute terrain cost multiplier between two world points.
        Returns 1.0 when no terrain data or terrain cost disabled.
        """
        if not getattr(self, 'use_terrain_cost', True):
            return 1.0

        if self.terrain_data is None:
            return 1.0

        # midpoint in world coords
        mid_point = (
            (point_world[0] + next_point_world[0]) / 2.0,
            (point_world[1] + next_point_world[1]) / 2.0,
            (point_world[2] + next_point_world[2]) / 2.0,
        )

        # get voxel index and clamp
        try:
            idx = self._world_to_voxel(mid_point)
        except Exception:
            return 1.0

        idx = self._clamp_index(idx)

        base_cost = 1.0
        slope_cost = self._compute_slope_cost(idx)
        roughness_cost = self._compute_roughness_cost(idx)
        density_cost = self._compute_density_cost(idx)

        total_cost = base_cost * slope_cost * roughness_cost * density_cost
        total_cost = min(total_cost, 10.0)
        return float(total_cost)

    def _compute_slope_cost(self, idx):
        if not self.terrain_data or 'elevation' not in self.terrain_data:
            return 1.0
        try:
            elevation = self.terrain_data['elevation']
            x, y, z = idx
            max_slope = 0.0
            neighbors = [
                (x+1, y, z), (x-1, y, z),
                (x, y+1, z), (x, y-1, z),
                (x+1, y+1, z), (x+1, y-1, z),
                (x-1, y+1, z), (x-1, y-1, z)
            ]
            current_elev = elevation[x, y, z]
            for nx, ny, nz in neighbors:
                if (0 <= nx < elevation.shape[0] and 0 <= ny < elevation.shape[1] and 0 <= nz < elevation.shape[2]):
                    neighbor_elev = elevation[nx, ny, nz]
                    slope = abs(neighbor_elev - current_elev) / max(1e-6, self.voxel_size)
                    max_slope = max(max_slope, slope)
            slope_degrees = np.degrees(np.arctan(max_slope))
            if slope_degrees < 15:
                cost = 1.0 + slope_degrees / 30.0
            elif slope_degrees < 30:
                cost = 1.5 + (slope_degrees - 15) / 15.0
            else:
                cost = min(2.5 + (slope_degrees - 30) / 30.0, 3.0)
            return float(cost)
        except Exception as e:
            print(f"Warning: Slope cost calculation failed: {e}")
            return 1.0

    def _compute_roughness_cost(self, idx):
        if not self.terrain_data or 'roughness' not in self.terrain_data:
            return 1.0
        try:
            roughness = self.terrain_data['roughness']
            x, y, z = idx
            rough_value = float(roughness[x, y, z])
            cost = 1.0 + float(rough_value)
            return float(cost)
        except Exception as e:
            print(f"Warning: Roughness cost calculation failed: {e}")
            return 1.0

    def _compute_density_cost(self, idx):
        if not self.terrain_data or 'density' not in self.terrain_data:
            return 1.0
        try:
            density = self.terrain_data['density']
            x, y, z = idx
            density_value = float(density[x, y, z])
            cost = 1.0 + (1.0 - density_value)
            return float(cost)
        except Exception as e:
            print(f"Warning: Density cost calculation failed: {e}")
            return 1.0

    def _clamp_index(self, idx):
        x, y, z = idx
        gx, gy, gz = self.grid_size
        x = max(0, min(int(x), gx - 1))
        y = max(0, min(int(y), gy - 1))
        z = max(0, min(int(z), gz - 1))
        return (x, y, z)

    def _path_length(self, path: List[Tuple[float,float,float]]):
        if not path or len(path)<2:
            return 0.0
        s=0.0
        for i in range(len(path)-1):
            s += float(np.linalg.norm(np.array(path[i+1]) - np.array(path[i])))
        return s

    def _collision_free(self, a, b):
        return self._line_of_sight(a,b)

    def _optimize_window(self, window_points: List[Tuple[float,float,float]], alphas=(0.2,0.4,0.6,0.8)) -> List[Tuple[float,float,float]]:
        optimized = [window_points[0]]
        for i in range(1, len(window_points)-1):
            prev = optimized[-1]
            curr = window_points[i]
            nxt = window_points[i+1]

            best_point = curr
            # base cost: length * terrain_cost for prev->curr + curr->nxt
            best_cost = (
                self._segment_length(prev, curr, nxt) *
                self._compute_terrain_cost(prev, curr)
            )

            # try prev-curr interpolation
            for alpha in alphas:
                interp = self._interpolate(prev, curr, alpha)
                if not self._collision_free(prev, interp):
                    continue
                if not self._collision_free(interp, nxt):
                    continue
                cost = (
                    np.linalg.norm(np.array(interp) - np.array(prev)) * self._compute_terrain_cost(prev, interp)
                    + np.linalg.norm(np.array(nxt) - np.array(interp)) * self._compute_terrain_cost(interp, nxt)
                )
                if cost + 1e-9 < best_cost:
                    best_cost = cost
                    best_point = interp

            # try curr-next interpolation
            for alpha in alphas:
                interp = self._interpolate(curr, nxt, alpha)
                if not self._collision_free(prev, interp):
                    continue
                if not self._collision_free(interp, nxt):
                    continue
                cost = (
                    np.linalg.norm(np.array(interp) - np.array(prev)) * self._compute_terrain_cost(prev, interp)
                    + np.linalg.norm(np.array(nxt) - np.array(interp)) * self._compute_terrain_cost(interp, nxt)
                )
                if cost + 1e-9 < best_cost:
                    best_cost = cost
                    best_point = interp

            optimized.append(best_point)
        optimized.append(window_points[-1])
        return optimized

    def _shortcut_path(self, path: List[Tuple[float,float,float]]) -> List[Tuple[float,float,float]]:
        if not path:
            return path
        newp = [path[0]]
        i=0
        n=len(path)
        while i < n-1:
            j = n-1
            while j>i:
                if self._collision_free(newp[-1], path[j]):
                    break
                j -= 1
            newp.append(path[j])
            i = j
        return newp

    def plan_path(self, start, goal, window_size: int = 3, max_iterations: int = 3, alphas=(0.2,0.4,0.6,0.8), do_shortcut: bool = True, timeout: Optional[float]=5.0) -> PlanningResult:
        t0 = time.time()
        d = DStarLite3D(voxel_size=self.voxel_size, grid_size=self.grid_size)
        # pass min_bound so D* uses same world origin
        try:
            d.set_terrain_data(self.voxel_grid, self.terrain_data, min_bound=tuple(self.min_bound))
        except TypeError:
            d.set_terrain_data(self.voxel_grid, self.terrain_data)
        base = d.plan_path(start, goal)
        if not base.success:
            return PlanningResult(success=False, path=[], computation_time=time.time()-t0, path_length=0.0, nodes_explored=0, error_message='D*Lite failed', algorithm_name='FieldD*Hybrid')

        path = base.path
        # ensure window_size at least 3
        window_size = max(3, min(window_size, len(path)))

        iterations = 0
        nodes_processed = 0
        while iterations < max_iterations and (time.time()-t0) < timeout:
            improved = False
            new_path = []
            i = 0
            while i < len(path):
                window = path[i:i+window_size]
                if len(window) < 3:
                    new_path.extend(window)
                    break
                optimized = self._optimize_window(window, alphas)
                nodes_processed += len(window)
                if self._path_length(optimized) + 1e-9 < self._path_length(window):
                    improved = True
                # append optimized without last to allow overlap
                new_path.extend(optimized[:-1])
                i += 1
            new_path.append(path[-1])
            path = new_path
            iterations += 1
            if not improved:
                break

        if do_shortcut:
            path = self._shortcut_path(path)

        comp_time = time.time()-t0
        path_len = self._path_length(path)
        # D*Liteの探索ノード数 + ウィンドウ処理ノード数
        total_nodes = base.nodes_explored + nodes_processed
        self.last_search_stats.update({'nodes_explored':total_nodes,'computation_time':comp_time,'path_length':path_len})
        return PlanningResult(success=True, path=path, computation_time=comp_time, path_length=path_len, nodes_explored=total_nodes, algorithm_name='FieldD*Hybrid')


def generate_test_terrain_data(grid_size):
    """
    Generate simple test terrain data: elevation (hills + noise), roughness, density
    grid_size: (nx, ny, nz)
    """
    nx, ny, nz = grid_size
    x = np.linspace(0, 4*np.pi, nx)
    y = np.linspace(0, 4*np.pi, ny)
    X, Y = np.meshgrid(x, y)

    elevation = np.zeros((nx, ny, nz))
    for z in range(nz):
        elevation[:, :, z] = (
            np.sin(X/2.0) * np.cos(Y/2.0) * 5.0 +
            np.random.randn(nx, ny) * 0.5
        )

    roughness = np.random.rand(nx, ny, nz) * 0.5 + 0.2
    density = np.ones((nx, ny, nz)) * 0.7

    return {'elevation': elevation, 'roughness': roughness, 'density': density}
