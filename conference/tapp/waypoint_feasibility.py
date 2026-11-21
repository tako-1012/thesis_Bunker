"""Preflight reachability and nearest reachable waypoint on the prior map."""

import numpy as np
from scipy.ndimage import label

from .config import RESOLUTION

WAYPOINT_RADIUS_M = 1.0


def _point_and_cell(xy, shape):
    point = np.asarray(xy, dtype=float)
    if point.shape != (2,) or not np.isfinite(point).all():
        raise ValueError('座標は有限な数値の x, y で指定してください')
    if (point < 0).any() or (point > (np.asarray(shape)-1)*RESOLUTION).any():
        return point, None
    return point, tuple(map(int, np.rint(point/RESOLUTION)))


def _nearest(point, reachable):
    # Enumerate just the centre positions within the square around the goal;
    # argwhere orders ties by (x, y). Filter candidates by the exact disk.
    axes = [np.flatnonzero(abs(np.arange(n)*RESOLUTION-value) <= WAYPOINT_RADIUS_M)
            for n, value in zip(reachable.shape, point)]
    offsets = np.argwhere(reachable[np.ix_(*axes)])
    if not len(offsets):
        return None, None
    cells = np.column_stack([axis[offset] for axis, offset in zip(axes, offsets.T)])
    squared = np.sum((cells*RESOLUTION-point)**2, axis=1)
    first = int(squared.argmin())
    if squared[first] > WAYPOINT_RADIUS_M**2:
        return None, None
    return cells[first].tolist(), float(np.sqrt(squared[first]))


def check_waypoints(blocked, cost, start_xy, points_xy):
    """Check metre coordinates against a prepared TA*-S planning mask.

    The caller supplies the mask with the footprint already applied. All
    four-neighbour links are legal, and every allowed diagonal has a legal
    four-neighbour detour, so connected components match A* reachability.
    Finite nonnegative costs change the route ranking only. Every accepted
    replacement stays in the start component, regardless of visit order.
    """
    blocked, cost = np.asarray(blocked, bool), np.asarray(cost, float)
    if (blocked.ndim != 2 or not all(blocked.shape) or cost.shape != blocked.shape
            or not np.isfinite(cost[~blocked]).all() or (cost[~blocked] < 0).any()):
        raise ValueError('通行不可マスクと計画コストが不正です')
    start, start_cell = _point_and_cell(start_xy, blocked.shape)
    if start_cell is None:
        start_status, start_reason = 'blocked_cell', 'outside_map'
    elif blocked[start_cell]:
        start_status, start_reason = 'blocked_cell', 'prior_lethal'
    else:
        start_status, start_reason = 'ok', 'reachable'
    reachable = None
    if start_status == 'ok':
        components, _ = label(~blocked)
        reachable = components == components[start_cell]

    checks = []
    for index, xy in enumerate(points_xy, 1):
        point, cell = _point_and_cell(xy, blocked.shape)
        if cell is None:
            status, reason = 'blocked_cell', 'outside_map'
        elif blocked[cell]:
            status, reason = 'blocked_cell', 'prior_lethal'
        elif reachable is None:
            status, reason = 'unreachable', 'invalid_start'
        elif not reachable[cell]:
            status, reason = 'unreachable', 'disconnected'
        else:
            status, reason = 'ok', 'reachable'
        candidate, shift = (None, None)
        if status != 'ok' and reachable is not None:
            candidate, shift = _nearest(point, reachable)
        checks.append(dict(index=index, original_m=point.tolist(), cell=list(cell) if cell is not None else None,
                           status=status, reason=reason, replacement_cell=candidate,
                           replacement_m=(np.asarray(candidate)*RESOLUTION).tolist() if candidate is not None else None,
                           shift_m=shift))
    return dict(radius_m=WAYPOINT_RADIUS_M,
                start=dict(original_m=start.tolist(), cell=list(start_cell) if start_cell is not None else None,
                           status=start_status, reason=start_reason),
                points=checks)
