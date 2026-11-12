"""Specified lab GeometryLayer and Jazzy NavFn cost conversion on a grid.

This is an eight-neighbour graph surrogate, not NavFn's potential/gradient
solver. Unknown elevations stay unknown; no terrain constants are calibrated.
"""
import numpy as np
from time import perf_counter
from scipy.ndimage import binary_dilation
from .planners import astar

UNKNOWN = 255
LETHAL = 254


def geometry_layer_cost(elev, res):
    """Return mean absolute neighbour gradient (NaN unknown), uint8 ROS cost.

    Diagonal distance is exactly 1.41*res and degrees use exactly 57.3.
    Fractional stage costs are truncated at the uint8 costmap boundary.
    """
    z = np.asarray(elev, float)
    if z.ndim != 2 or not np.isfinite(res) or res <= 0:
        raise ValueError('expected a 2D elevation and positive resolution')
    total, count = np.zeros(z.shape), np.zeros(z.shape, int)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == dy == 0:
                continue
            a = (slice(max(0, -dx), min(z.shape[0], z.shape[0]-dx)),
                 slice(max(0, -dy), min(z.shape[1], z.shape[1]-dy)))
            b = (slice(max(0, dx), min(z.shape[0], z.shape[0]+dx)),
                 slice(max(0, dy), min(z.shape[1], z.shape[1]+dy)))
            valid = np.isfinite(z[a]) & np.isfinite(z[b])
            total[a] += np.where(valid, np.abs(z[b]-z[a])/(res*(1.41 if dx and dy else 1.)), 0.)
            count[a] += valid
    slope = np.full(z.shape, np.nan)
    known = np.isfinite(z) & (count > 3)
    slope[known] = total[known]/count[known]
    angle = np.arctan(slope)*57.3
    cost = np.full(z.shape, UNKNOWN, np.uint8)
    cost[known] = np.select([angle[known] <= t for t in (5, 10, 15, 20, 25)],
                           [0., .1*LETHAL, .2*LETHAL, .5*LETHAL, .8*LETHAL],
                           default=LETHAL).astype(np.uint8)
    return slope, cost


def navfn_cell_cost(costmap):
    """NavFn::setCostmap(isROS=true, allow_unknown=true), Jazzy 1.3.14.

    Upstream commit 94d1c2a345dda6ff637e6a72c9101d927ee99f19:
    nav2_navfn_planner/src/navfn.cpp and include/.../navfn.hpp.
    """
    c = np.asarray(costmap)
    if not np.isfinite(c).all() or np.any((c < 0) | (c > 255) | (c != np.floor(c))):
        raise ValueError('ROS costmap must contain integer values 0..255')
    out = np.full(c.shape, 254, np.uint8)
    free = c < 253
    out[free] = np.minimum((50.+.8*c[free]).astype(int), 253).astype(np.uint8)
    out[c == 255] = 253
    return out


def obstacle_mask(raw, res, radius_m=0.):
    """Block centres within radius of the closed raw obstacle cell squares."""
    raw = np.asarray(raw, bool)
    if not np.isfinite(radius_m) or radius_m < 0 or not np.isfinite(res) or res <= 0:
        raise ValueError('invalid radius/resolution')
    if radius_m == 0:
        return raw.copy()
    n = int(np.ceil(radius_m/res+.5))
    x, y = np.mgrid[-n:n+1, -n:n+1]
    dx, dy = np.maximum(np.abs(x)*res-res/2, 0), np.maximum(np.abs(y)*res-res/2, 0)
    return binary_dilation(raw, structure=dx*dx+dy*dy <= radius_m*radius_m)


def plan_lab(elev, raw_obstacles, start, goal, res=.5, radius_m=0.):
    began = perf_counter()
    shape = np.asarray(elev).shape
    if len(shape) != 2 or shape[0] != shape[1] or np.asarray(raw_obstacles).shape != shape:
        raise ValueError('planner requires equal square elevation/obstacle grids')
    _, costs = geometry_layer_cost(elev, res)
    costs[obstacle_mask(raw_obstacles, res, radius_m)] = LETHAL
    cells = navfn_cell_cost(costs)
    # NavFn::setupNavFn(true) sets the outermost rows/columns to COST_OBS.
    cells[[0, -1], :] = LETHAL
    cells[:, [0, -1]] = LETHAL
    for point in (start, goal):
        if any(v < 0 or v >= n for v, n in zip(point, shape)) or cells[tuple(point)] >= LETHAL:
            return dict(success=False, path=None, time=perf_counter()-began, expansions=0)
    # Existing A*: Euclidean h is admissible since all free cell costs >=50.
    # Edges use mean endpoint cost * Euclidean grid-step length, no corner cuts.
    return astar(cells >= LETHAL, start, goal, cells.astype(float))
