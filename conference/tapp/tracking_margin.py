"""Plan-local hard clearance and endpoint exceptions for task070."""

import numpy as np

from .distance_clearance import R_HARD, R_SOFT, W_OBS
from .goal_region import in_grid

TRACKING_MARGINS = ('none', 'fixed', 'slope')
FIXED_ERROR_M = .274
SLOPE_ERROR_M = .614
SLOPE_CUTOFF_DEG = 10.
FIXED_HARD_M = .774
SLOPE_HARD_M = 1.114


def validate_tracking_margin(mode, obstacle, steep, soft_m=R_SOFT):
    if mode not in TRACKING_MARGINS:
        raise ValueError('unknown tracking margin')
    if mode == 'none':
        return
    if 'distance' not in (obstacle, steep):
        raise ValueError('--tracking-margin requires --obstacle-clearance distance or --steep-clearance distance')
    if soft_m != R_SOFT:
        raise ValueError('--tracking-margin fixes --clearance-soft-m at 1.5')


def radius_map(mode, slope):
    if mode == 'slope':
        return np.where(slope >= SLOPE_CUTOFF_DEG, SLOPE_HARD_M, FIXED_HARD_M)
    return np.full(slope.shape, FIXED_HARD_M if mode == 'fixed' else R_HARD)


def distance_cost(distance, radius):
    """Quadratic cost on the closed inner edge and up to the soft radius."""
    return np.where(distance >= radius,
                    W_OBS*((R_SOFT-np.minimum(distance, R_SOFT))/(R_SOFT-radius))**2, 0.)


class TrackingClearance:
    """A frozen set of distance layers from a single mapper publication."""

    def __init__(self, mode, slope, distances):
        self.radius = radius_map(mode, slope)
        self.base_hard = np.zeros(slope.shape, bool)
        self.bands, self.costs, self.relaxed_costs = {}, {}, {}
        for name, distance in distances.items():
            base = distance < R_HARD
            self.base_hard |= base
            self.bands[name] = ~base & (distance < self.radius)
            self.costs[name] = distance_cost(distance, self.radius)
            self.relaxed_costs[name] = distance_cost(distance, R_HARD)

    def protected(self, relaxed):
        blocked = self.base_hard.copy()
        for name, band in self.bands.items():
            if name not in relaxed:
                blocked |= band
        return blocked

    def project(self, blocked, mult, start, goal, weight):
        roles = []
        relaxed = set()
        base = blocked | self.base_hard
        for role, cell in (('start', start), ('goal', goal)):
            if cell is None or not in_grid(cell, base.shape) or base[cell]:
                continue
            layers = {name for name, band in self.bands.items() if band[cell]}
            if layers:
                roles.append(role)
                relaxed.update(layers)
        protected = self.protected(relaxed)
        mult = mult.copy()
        for name, cost in self.costs.items():
            mult += weight*(self.relaxed_costs[name] if name in relaxed else cost)
        return base | protected, mult, '|'.join(roles), frozenset(relaxed), protected
