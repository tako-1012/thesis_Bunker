"""Opt-in steep-cell dilation with the existing rock-radius raster convention.

Radii are rounded up to grid cells by traversability.inflate, exactly as rocks
are. On the 0.5m grid the requested 0.39m and 0.5m radii both give one cell.
Costs, elevation, start/goal and all original maps remain unchanged.
"""

from copy import copy
import math
import numpy as np

from .config import RESOLUTION
from .traversability import inflate


def _radius(tm, radius_m):
    radius = tm.robot.footprint_radius if radius_m is None else float(radius_m)
    if not math.isfinite(radius) or radius < 0:
        raise ValueError("footprint radius must be finite and nonnegative")
    return radius


def inflate_steep(tm, radius_m=None):
    """Return a fresh lethal mask, adding only dilated steep cells."""
    radius = _radius(tm, radius_m)
    if radius == 0:
        return tm.lethal.copy()
    return tm.lethal | inflate(tm.steep, radius)


def with_inflated_steep(sc, radius_m=None):
    """Shallow-copy the scenario/map; replace lethal only, sharing unchanged cost."""
    result = dict(sc)
    result["tmap"] = copy(sc["tmap"])
    result["tmap"].lethal = inflate_steep(sc["tmap"], radius_m)
    return result


def blocked_endpoints(tm, start, goals):
    """Do not snap endpoints after inflation; return their unchanged indices."""
    points = [tuple(start)] + [tuple(p) for p in goals]
    return [i for i, p in enumerate(points) if tm.lethal[p]]


def run_footprint_mission(truth_tm, prior, prior_tm, start, goals, *,
                          footprint_radius_m=None, radius_m=10, **kwargs):
    """Task-014 sensing/integration on opt-in inflated traversability labels.

    The sensor still reveals the map's traversability labels within its radius,
    as in task014 (no occlusion/raw-point sensing). Precomputed dilation can label
    a cell blocked by a steep neighbour just outside the observation boundary.
    """
    from .online_mission import run_online_mission
    from .prior import PriorMap
    radius = _radius(truth_tm, footprint_radius_m)
    if radius == 0:
        return run_online_mission(truth_tm, prior, start, goals,
                                  radius_m=radius_m, **kwargs)
    truth = with_inflated_steep(dict(tmap=truth_tm), radius)["tmap"]
    blocked = blocked_endpoints(truth, start, goals)
    if blocked:
        return dict(success=False, reason="blocked_endpoint", blocked_endpoint_indices=blocked,
                    traj=[tuple(start)], n_plans=0, n_replans=0, plan_times=[],
                    plan_time=0.0, max_plan_time=0.0, legs=[], events=[])
    inflated_prior = None
    if prior is not None:
        inflated_prior = PriorMap(prior.cost, prior.lethal | inflate(prior_tm.steep, radius),
                                  prior.cell_m)
    return run_online_mission(truth, inflated_prior, start, goals,
                              radius_m=radius_m, **kwargs)


def steep_proximity_fraction(path_cells, tm, radius_m=None):
    """Exact arc-length fraction within radius of at least one steep cell centre.

    Intersect each straight path segment with the circles and merge overlapping
    intervals. This avoids a sampling-step parameter and double-counted lengths.
    The metric uses the nominal radius, not the dilation's cell-rounded radius.
    """
    radius = _radius(tm, radius_m)
    path = np.asarray(path_cells, float) * RESOLUTION
    if path.ndim != 2 or path.shape[1] != 2 or not np.isfinite(path).all():
        raise ValueError("path must be finite N x 2 grid coordinates")
    covered = total = 0.0
    for a, b in zip(path[:-1], path[1:]):
        delta = b - a
        length2 = float(delta @ delta)
        if not length2:
            continue
        length = math.sqrt(length2)
        total += length
        lo = np.maximum(0, np.floor((np.minimum(a, b)-radius)/RESOLUTION).astype(int))
        hi = np.minimum(tm.shape, np.ceil((np.maximum(a, b)+radius)/RESOLUTION).astype(int)+1)
        if np.any(lo >= hi):
            continue
        cells = np.argwhere(tm.steep[lo[0]:hi[0], lo[1]:hi[1]]) + lo
        if not len(cells):
            continue
        offsets = cells*RESOLUTION-a
        centre = offsets @ delta / length2
        perpendicular2 = np.maximum(np.sum(offsets*offsets, axis=1)-centre*centre*length2, 0)
        hit = perpendicular2 <= radius*radius
        centre = centre[hit]
        half = np.sqrt(np.maximum(radius*radius-perpendicular2[hit], 0)/length2)
        starts = np.maximum(centre-half, 0)
        ends = np.minimum(centre+half, 1)
        valid = ends > starts
        starts, ends = starts[valid], ends[valid]
        if len(starts):
            order = np.argsort(starts)
            starts, ends = starts[order], ends[order]
            previous = np.r_[-np.inf, np.maximum.accumulate(ends)[:-1]]
            covered += length * float(np.maximum(ends-np.maximum(starts, previous), 0).sum())
    return covered/total if total else 0.0
