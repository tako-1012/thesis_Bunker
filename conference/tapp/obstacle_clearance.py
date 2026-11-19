"""Planar clearance to closed, axis-aligned obstacle footprints."""

from itertools import product

import numpy as np


def cell_boxes(mask, resolution, origin):
    """Return lower/upper XY corners for grid cells; origin is the lower map edge."""
    lower = np.argwhere(mask)*resolution + origin
    return lower, lower+resolution


def point_clearance(point, lower, upper):
    if not len(lower):
        return None
    gap = np.maximum(np.maximum(lower-point, point-upper), 0.)
    return float(np.hypot(*gap.T).min())


def path_clearance(points, lower, upper):
    """Minimum over the polyline's closed segments and the obstacle rectangles."""
    points = np.asarray(points, float)
    if not len(points) or not len(lower):
        return None
    if len(points) == 1:
        return point_clearance(points[0], lower, upper)
    corners = np.where(np.array(list(product((False, True), repeat=2)))[None, :, :],
                       upper[:, None, :], lower[:, None, :])
    best = float('inf')
    for start, end in zip(points[:-1], points[1:]):
        delta = end-start
        enter, leave = np.zeros(len(lower)), np.ones(len(lower))
        for axis, step in enumerate(delta):
            if step:
                first, last = (lower[:, axis]-start[axis])/step, (upper[:, axis]-start[axis])/step
                enter = np.maximum(enter, np.minimum(first, last))
                leave = np.minimum(leave, np.maximum(first, last))
            else:
                outside = (start[axis] < lower[:, axis]) | (start[axis] > upper[:, axis])
                enter[outside] = np.inf
        if np.any(enter <= leave):
            return 0.
        length_sq = delta @ delta
        corner_gap = corners-start
        if length_sq:
            fractions = np.clip((corner_gap @ delta)/length_sq, 0., 1.)
            corner_gap -= fractions[..., None]*delta
        best = min(best, point_clearance(start, lower, upper), point_clearance(end, lower, upper),
                   float(np.linalg.norm(corner_gap, axis=-1).min()))
    return best
