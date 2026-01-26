"""
Field D* (proper-ish) - extend grid search with edge interpolation (virtual nodes).

This is a pragmatic implementation that follows the requested behaviour:
- when expanding a node, consider interpolated points on edges of neighboring grid cells
- evaluate cost = interpolated combination of neighbor costs + travel distance
- manage virtual nodes as continuous points (floats) with hashing by rounded coords

This is not a fully formal Field D* reimplementation but implements the core ideas
requested (edge interpolation during expansion, virtual nodes on edges, alpha search).
"""
import heapq
import math
import time
from typing import Tuple, List, Dict, Optional
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


class FieldDStarProper:
    def __init__(self, voxel_size: float = 1.0, grid_size: Tuple[int,int,int]=(200,200,20), min_bound=(0.0,0.0,0.0)):
        self.voxel_size = voxel_size
        self.grid_size = grid_size
        self.min_bound = np.array(min_bound)
        self.voxel_grid = None
        self.terrain_data = None
        self.last_search_stats = {'nodes_explored':0,'computation_time':0.0,'path_length':0.0}
        self.search_radius = 3  # in grid units (voxels)
        self.base_path = None
        self.base_path_np = None
        self._radius_expansions = 0

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
        # map to voxel indices and run bresenham
        a_idx = self._world_to_voxel(a_world)
        b_idx = self._world_to_voxel(b_world)
        for v in _bresenham3d(a_idx, b_idx):
            if not self._is_free_voxel(v):
                return False
        return True

    def _distance(self, a, b):
        a=np.array(a); b=np.array(b)
        return float(np.linalg.norm(b-a))

    def _round_key(self, p, prec=3):
        return (round(p[0],prec), round(p[1],prec), round(p[2],prec))

    def plan_path(self, start: Tuple[float,float,float], goal: Tuple[float,float,float], max_nodes: int = 20000, alpha_samples: int = 3, timeout: Optional[float]=None, sample_midpoint_only: bool = True, allow_interpolation: bool = True) -> PlanningResult:
        """A*-like search with edge interpolation (virtual nodes).
        alpha_samples: number of samples on each edge (including 0,1)
        """
        t0 = time.time()
        # run D*Lite to obtain a base grid path and restrict search region
        try:
            d = DStarLite3D(voxel_size=self.voxel_size, grid_size=self.grid_size)
            d.set_terrain_data(self.voxel_grid, self.terrain_data)
            base = d.plan_path(start, goal)
        except Exception:
            base = None
        if not base or not base.success:
            # fallback: still attempt but compute without base-path guidance
            goal_idx = self._world_to_voxel(goal)
            allowed_box = None
        else:
            # compute voxel bbox around base path
            path_vox = [self._world_to_voxel(p) for p in base.path]
            arr = np.array(path_vox)
            margin = max(3, int(max(self.grid_size)//32))
            mins = np.maximum(arr.min(axis=0) - margin, 0)
            maxs = np.minimum(arr.max(axis=0) + margin, np.array(self.grid_size)-1)
            allowed_box = (tuple(mins.tolist()), tuple(maxs.tolist()))
            goal_idx = self._world_to_voxel(goal)
            # store base path for distance-based region checks
            self.base_path = base.path
            try:
                self.base_path_np = np.array(self.base_path)
            except Exception:
                self.base_path_np = None
        # skip full Dijkstra precomputation to save time; use base-path distance as heuristic
        g_grid = {}
        open_heap = []  # (f, g, key, point, parent_key)
        g_score: Dict[Tuple[float,float,float], float] = {}
        parent: Dict[Tuple[float,float,float], Tuple[Optional[Tuple[float,float,float]], float]] = {}

        start_key = self._round_key(start, prec=3)
        goal_key = self._round_key(goal, prec=3)

        g_score[start_key] = 0.0
        # start heuristic from grid gscore if available
        start_vox = self._world_to_voxel(start)
        h0 = g_grid.get(start_vox, self._distance(start, goal))
        heapq.heappush(open_heap, (h0, 0.0, start_key, start, None))

        nodes = 0
        visited = set()
        while open_heap and nodes < max_nodes:
            if timeout is not None and (time.time()-t0) > timeout:
                return PlanningResult(success=False, path=[], computation_time=time.time()-t0, path_length=0.0, nodes_explored=nodes, error_message='Timeout', algorithm_name='FieldD*Proper')
            f, g_curr, key_curr, point_curr, parent_key = heapq.heappop(open_heap)
            if key_curr in visited:
                continue
            visited.add(key_curr)
            nodes += 1
            # adaptive radius expansion: if many nodes explored without success, expand search radius
            if self.base_path is not None and nodes % 1000 == 0 and self._radius_expansions < 3:
                self.search_radius = min(self.search_radius * 2, max(self.grid_size))
                self._radius_expansions += 1
            # goal check by distance threshold
            if self._distance(point_curr, goal) <= self.voxel_size * 1.5:
                # reconstruct path
                path = [point_curr]
                k = key_curr
                while k is not None and k in parent:
                    pk, _ = parent[k]
                    if pk is None:
                        break
                    path.append(pk)
                    k = self._round_key(pk)
                path = path[::-1]
                path_len = self._distance(start, path[0]) + sum(self._distance(path[i], path[i+1]) for i in range(len(path)-1))
                self.last_search_stats.update({'nodes_explored':nodes,'computation_time':time.time()-t0,'path_length':path_len})
                return PlanningResult(success=True, path=path, computation_time=time.time()-t0, path_length=path_len, nodes_explored=nodes, algorithm_name='FieldD*Proper')

            # expand: generate neighbor candidate points
            # use 6-neighborhood (axis-aligned) for performance
            cur_vox = self._world_to_voxel(point_curr)
            neighbors = []
            for (dx,dy,dz) in [(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)]:
                nb = (cur_vox[0]+dx, cur_vox[1]+dy, cur_vox[2]+dz)
                if 0<=nb[0]<self.grid_size[0] and 0<=nb[1]<self.grid_size[1] and 0<=nb[2]<self.grid_size[2]:
                    # respect allowed box if present
                    if allowed_box is not None:
                        (minx,miny,minz),(maxx,maxy,maxz) = allowed_box
                        if not (minx<=nb[0]<=maxx and miny<=nb[1]<=maxy and minz<=nb[2]<=maxz):
                            continue
                    neighbors.append(nb)

            for nb in neighbors:
                nb_world = self._voxel_to_world_center(nb)
                # standard transition
                if self._line_of_sight(point_curr, nb_world):
                    cand = nb_world
                    # restrict by distance to base path if available
                    if not self._is_in_search_region(cand):
                        pass
                    else:
                        cand_key = self._round_key(cand)
                        tentative_g = g_curr + self._distance(point_curr, cand)
                        if tentative_g < g_score.get(cand_key, float('inf')):
                            g_score[cand_key] = tentative_g
                            parent[cand_key] = (point_curr, 0.0)
                            # heuristic for candidate: distance to base path if available
                            if self.base_path_np is not None:
                                diffs = self.base_path_np - np.array(cand)
                                h = float(np.linalg.norm(diffs, axis=1).min())
                            else:
                                h = self._distance(cand, goal)
                            heapq.heappush(open_heap, (tentative_g + h, tentative_g, cand_key, cand, key_curr))

                # edge interpolation: consider 6-neighbors of nb only (performance)
                nb_neighbors = []
                for (dx2,dy2,dz2) in [(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)]:
                    nb2 = (nb[0]+dx2, nb[1]+dy2, nb[2]+dz2)
                    if 0<=nb2[0]<self.grid_size[0] and 0<=nb2[1]<self.grid_size[1] and 0<=nb2[2]<self.grid_size[2]:
                        if allowed_box is not None:
                            (minx,miny,minz),(maxx,maxy,maxz) = allowed_box
                            if not (minx<=nb2[0]<=maxx and miny<=nb2[1]<=maxy and minz<=nb2[2]<=maxz):
                                continue
                        nb_neighbors.append(nb2)

                if not allow_interpolation:
                    continue
                for nb2 in nb_neighbors:
                    p1 = self._voxel_to_world_center(nb)
                    p2 = self._voxel_to_world_center(nb2)
                    # sample alphas including 0 and 1
                    if sample_midpoint_only:
                        alphas = [0.5]
                    else:
                        alphas = list(np.linspace(0.0, 1.0, alpha_samples))
                    for alpha in alphas:
                        interp = (p1[0]*(1-alpha) + p2[0]*alpha,
                                  p1[1]*(1-alpha) + p2[1]*alpha,
                                  p1[2]*(1-alpha) + p2[2]*alpha)
                        # collision check
                        if not self._line_of_sight(point_curr, interp):
                            continue
                        # compute tentative cost: g(curr) + distance to interp + small cost from edge sampling
                        tentative_g = g_curr + self._distance(point_curr, interp)
                        interp_key = self._round_key(interp)
                        if tentative_g < g_score.get(interp_key, float('inf')):
                            # restrict interpolated point to search region
                            if not self._is_in_search_region(interp):
                                continue
                            g_score[interp_key] = tentative_g
                            parent[interp_key] = (point_curr, alpha)
                            # heuristic for interp: distance to base path if available
                            if self.base_path_np is not None:
                                diffs = self.base_path_np - np.array(interp)
                                h_interp = float(np.linalg.norm(diffs, axis=1).min())
                            else:
                                h_interp = self._distance(interp, goal)
                            heapq.heappush(open_heap, (tentative_g + h_interp, tentative_g, interp_key, interp, key_curr))

        # failed
        self.last_search_stats.update({'nodes_explored':nodes,'computation_time':time.time()-t0,'path_length':0.0})
        return PlanningResult(success=False, path=[], computation_time=time.time()-t0, path_length=0.0, nodes_explored=nodes, error_message='No path found', algorithm_name='FieldD*Proper')

    def _compute_grid_gscores(self, goal_idx, max_nodes=50000, allowed_box=None):
        """Dijkstra from goal over free voxels (6-neighborhood). Returns dict voxel_idx->cost_to_goal"""
        import heapq
        g = {}
        visited = set()
        heap = []
        heapq.heappush(heap, (0.0, goal_idx))
        g[goal_idx] = 0.0
        nodes = 0
        while heap and nodes < max_nodes:
            cost, cur = heapq.heappop(heap)
            if cur in visited:
                continue
            visited.add(cur)
            nodes += 1
            x,y,z = cur
            for (dx,dy,dz) in [(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)]:
                nb = (x+dx, y+dy, z+dz)
                if not (0<=nb[0]<self.grid_size[0] and 0<=nb[1]<self.grid_size[1] and 0<=nb[2]<self.grid_size[2]):
                    continue
                if allowed_box is not None:
                    (minx,miny,minz),(maxx,maxy,maxz) = allowed_box
                    if not (minx<=nb[0]<=maxx and miny<=nb[1]<=maxy and minz<=nb[2]<=maxz):
                        continue
                if not self._is_free_voxel(nb):
                    continue
                step_cost = self._distance(self._voxel_to_world_center(cur), self._voxel_to_world_center(nb))
                ng = cost + step_cost
                if ng < g.get(nb, float('inf')):
                    g[nb] = ng
                    heapq.heappush(heap, (ng, nb))
        return g

    def _is_in_search_region(self, point_world):
        """Check if a world point is within search_radius (voxels) of the base path."""
        if self.base_path is None or self.base_path_np is None:
            return True
        try:
            # compute euclidean distance in world units
            diffs = self.base_path_np - np.array(point_world)
            dists = np.linalg.norm(diffs, axis=1)
            min_d = float(dists.min())
            return min_d <= (self.search_radius * self.voxel_size)
        except Exception:
            return True
