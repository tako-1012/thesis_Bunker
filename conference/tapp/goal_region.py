"""Choose observed, reachable substitutes without relaxing the planning map."""

import numpy as np

from .config import RESOLUTION
from .planners import astar

GOAL_REGIONS = ('none', 'ring')
RING_RADIUS_M = 1.


def validate_goal_region(mode, endpoint_policy):
    if mode not in GOAL_REGIONS:
        raise ValueError('unknown goal region')
    if mode != 'none' and endpoint_policy != 'none':
        raise ValueError('--goal-region ring requires --endpoint-policy none')


def in_grid(cell, shape):
    return all(0 <= v < size for v, size in zip(cell, shape))


def eligible(cell, blocked, seen, steep_halo):
    return bool(in_grid(cell, blocked.shape) and seen[cell] and not (blocked[cell] or steep_halo[cell]))


def choose_goal(start, original, blocked, mult, seen, steep_halo):
    """Return (cell, A* result) for a blocked goal, or None."""
    if not in_grid(original, blocked.shape) or not blocked[original]:
        return None
    if not in_grid(start, blocked.shape) or blocked[start]:
        return None
    radius = int(RING_RADIUS_M / RESOLUTION)
    candidates = []
    for dx in range(-radius, radius+1):
        for dy in range(-radius, radius+1):
            d2 = dx*dx + dy*dy
            cell = (original[0]+dx, original[1]+dy)
            if 0 < d2 <= radius**2 and eligible(cell, blocked, seen, steep_halo):
                candidates.append((d2, cell))
    best, limit = None, radius**2
    for d2, cell in sorted(candidates):
        if d2 > limit:
            break
        result = astar(blocked, start, cell, mult)
        if result['success'] and (best is None or result['cost'] < best[1]['cost']):
            best, limit = (cell, result), d2
    return best


def blocked_reason(snapshot, original):
    layers = (('obstacle_halo', 'obstacle_halo'), ('steep', 'steep'), ('steep_halo', 'steep_halo'),
              ('prior_inflated', 'prior_rock_water_or_nodata'), ('retained_lethal', 'retained_lethal'))
    return '+'.join(reason for field, reason in layers if snapshot[field][original]) or 'hard_blocked'
