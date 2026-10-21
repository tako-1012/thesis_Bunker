"""Traversability features and cost from an elevation map.

The cost is normalised by *robot limits* (not by the per-map maximum), so the
same terrain receives the same cost on every map.
"""
import numpy as np
from scipy.ndimage import gaussian_filter, uniform_filter, binary_dilation

from .config import RESOLUTION, Robot, CostWeights


def slope_deg(elev):
    gx, gy = np.gradient(elev, RESOLUTION)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def roughness(elev):
    """Local std of the residual after removing smooth relief (3x3 window)."""
    resid = elev - gaussian_filter(elev, sigma=1.5)
    m = uniform_filter(resid, 3)
    m2 = uniform_filter(resid ** 2, 3)
    return np.sqrt(np.maximum(m2 - m ** 2, 0.0))


def inflate(mask, radius_m):
    r = int(np.ceil(radius_m / RESOLUTION))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    return binary_dilation(mask, structure=(xx ** 2 + yy ** 2) <= r * r)


class TraversabilityMap:
    def __init__(self, elev, rock, robot=Robot(), weights=CostWeights()):
        self.elev = elev
        self.robot = robot
        self.weights = weights
        self.slope = slope_deg(elev)
        self.rough = roughness(elev)
        self.rock = inflate(rock, robot.footprint_radius) if rock.any() else rock.copy()
        self.steep = self.slope > robot.max_slope_deg
        # lethal for terrain-aware planners: rocks or slopes beyond the limit
        self.lethal = self.rock | self.steep
        s_term = np.clip(self.slope / robot.max_slope_deg, 0, 1)
        r_term = np.clip(self.rough / robot.rough_sat, 0, 1)
        self.cost = weights.alpha * s_term + weights.beta * r_term

    @property
    def shape(self):
        return self.elev.shape
