"""Exact detected-square clearance for incremental mapping and path shortcuts."""

import math
from functools import cached_property

import numpy as np
from scipy.spatial import cKDTree

from .collision import line_of_sight_exact
from .config import RESOLUTION, Robot
from .obstacle_clearance import path_clearance
from .planners import smooth_cost_aware

R_HARD = Robot().footprint_radius
R_SOFT = 1.5
W_OBS = 1.


def validate_clearance(mode, soft_m):
    if not math.isfinite(soft_m) or soft_m <= R_HARD:
        raise ValueError('clearance-soft-m must be finite and greater than 0.5')
    if mode != 'distance' and soft_m != R_SOFT:
        raise ValueError('clearance-soft-m requires --obstacle-clearance distance')


def obstacle_cost(distance_m, soft_m=R_SOFT):
    distance_m = np.asarray(distance_m)
    band = (R_HARD < distance_m) & (distance_m < soft_m)
    return np.where(band, W_OBS*((soft_m-np.minimum(distance_m, soft_m))/(soft_m-R_HARD))**2, 0.)


class DistanceField:
    """Maintain the exact nearest-square distance, including outside the cost band."""

    def __init__(self, shape, fine_resolution, ratio, soft_m):
        self.distance_m = np.full(shape, np.inf)
        self.cost = np.zeros(shape)
        self.cells = np.empty((0, 2), dtype=int)
        self.fine_resolution, self.ratio, self.soft_m = fine_resolution, ratio, soft_m
        self._geometry = None
        self._offsets = np.stack(np.meshgrid(range(-1, 2), range(-1, 2), indexing='ij'), axis=-1).reshape(-1, 2)
        # Fixed, clipped tiles. Their centre/radius bound entire tiles at once,
        # including when the new squares are scattered around the map.
        self._x, self._y = (np.arange(0, n, 16) for n in shape)
        x_end, y_end = (np.minimum(start+16, n) for start, n in zip((self._x, self._y), shape))
        gx, gy = np.meshgrid((self._x+x_end-1)/2, (self._y+y_end-1)/2, indexing='ij')
        self._centres = np.stack((gx, gy), axis=-1)
        self._radius = RESOLUTION*np.hypot((x_end-self._x-1)[:, None]/2, (y_end-self._y-1)[None, :]/2)

    def add(self, cells):
        self.cells = np.concatenate((self.cells, cells))
        self._geometry = None
        # Both coarse centres and the projection of such a centre onto a
        # closed fine square lie on the half-fine lattice. A square's nine
        # lattice points therefore give its exact distance at every query.
        points = 2*cells[:, None]+self._offsets
        tree = cKDTree(points.reshape(-1, 2))
        scale = self.fine_resolution/2
        offset = 2*(self.ratio//2)
        tile_distance = tree.query(self._centres*(2*self.ratio)+offset)[0]*scale
        upper = np.maximum.reduceat(np.maximum.reduceat(self.distance_m, self._x, axis=0), self._y, axis=1)
        for i, j in np.argwhere(tile_distance-self._radius < upper+1e-10):
            x, y = self._x[i], self._y[j]
            region = np.s_[x:x+16, y:y+16]
            tile = self.distance_m[region]
            centres = (np.indices(tile.shape).transpose(1, 2, 0)+(x, y))*(2*self.ratio)+offset
            np.minimum(tile, tree.query(centres)[0]*scale, out=tile)
            self.cost[region] = obstacle_cost(tile, self.soft_m)

    def geometry(self):
        if self._geometry is None:
            lower = self.cells*self.fine_resolution-RESOLUTION/2
            self._geometry = SegmentClearance(lower, lower+self.fine_resolution)
        return self._geometry


class SegmentClearance:
    """Immutable rectangle geometry used by one or more planning snapshots."""

    def __init__(self, lower, upper):
        self.lower, self.upper = lower, upper

    @cached_property
    def tree(self):
        return cKDTree((self.lower+self.upper)/2)

    @cached_property
    def half_diagonal(self):
        return float(np.linalg.norm((self.upper-self.lower)/2, axis=1).max(initial=0.))

    def segment(self, a, b, limit=math.inf):
        """Exact minimum up to limit, with grid-cell endpoints (possibly fractional)."""
        if not len(self.lower) or limit <= 0.:
            return limit
        a, b = np.asarray([a, b], float)*RESOLUTION
        if not math.isfinite(limit):
            hints = self.tree.query([a, (a+b)/2, b])[1]
            limit = path_clearance([a, b], self.lower[hints], self.upper[hints])
        if limit == 0.:
            return 0.
        # Search overlapping balls along the segment. Any centre near the
        # segment is within one ball, including beyond either endpoint.
        radius = limit+self.half_diagonal
        length = float(np.linalg.norm(b-a))
        steps = max(1, int(math.ceil(length/max(radius, RESOLUTION))))
        samples = np.linspace(a, b, steps+1)
        groups = self.tree.query_ball_point(samples, math.hypot(radius, length/(2*steps))+1e-10)
        ids = np.unique(np.concatenate(groups)).astype(int)
        hit = path_clearance([a, b], self.lower[ids], self.upper[ids])
        return min(limit, hit) if hit is not None else limit

    def preserves(self, a, via, b):
        first = self.segment(a, via)
        minimum = min(first, self.segment(via, b, first))
        return self.segment(a, b, minimum) >= minimum-1e-10

    def smooth(self, path, blocked, mult, *, los=line_of_sight_exact):
        """Reuse cost-aware smoothing, accepting only clearance-preserving shortcuts."""
        indices = {tuple(point): i for i, point in enumerate(path)}
        edges = [self.segment(a, b) for a, b in zip(path, path[1:])]

        def safe_los(grid, a, b):
            if not los(grid, a, b):
                return False
            minimum = min(edges[indices[tuple(a)]:indices[tuple(b)]])
            return self.segment(a, b, minimum) >= minimum-1e-10

        return smooth_cost_aware(path, blocked, mult, los=safe_los)


def connector_clear(planner, blocked, start, via, end):
    """Keep both the usual hard check and the distance-mode clearance of the two legs."""
    geometry = getattr(planner, 'distance_geometry', None)
    return line_of_sight_exact(blocked, start, end) and (geometry is None or geometry.preserves(start, via, end))
