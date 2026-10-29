"""Coarse elevation priors, with local sensing left to override the map."""
from dataclasses import dataclass

import numpy as np
from scipy.ndimage import map_coordinates

from .config import RESOLUTION
from .traversability import TraversabilityMap


@dataclass
class PriorMap:
    cost: np.ndarray
    lethal: np.ndarray
    cell_m: float


def coarse_prior(tmap, cell_m, z_noise_m=0.0, seed=0) -> PriorMap:
    """Average blocks, then interpolate between their centres (clamped edges).

    Partial edge blocks use their actual centres. Noise is added independently
    to coarse elevations, never to the fine grid or the traversability cost.
    """
    if not np.isfinite(cell_m) or cell_m <= 0:
        raise ValueError("cell_m must be finite and positive")
    block = int(round(cell_m / RESOLUTION))
    if block < 1:
        raise ValueError("cell_m must round to at least one fine cell")
    if not np.isfinite(z_noise_m) or z_noise_m < 0:
        raise ValueError("z_noise_m must be finite and nonnegative")
    starts = [np.arange(0, n, block) for n in tmap.shape]
    counts = [np.minimum(block, n - s) for n, s in zip(tmap.shape, starts)]
    coarse = np.add.reduceat(np.add.reduceat(tmap.elev, starts[0], axis=0),
                             starts[1], axis=1)
    coarse = coarse / (counts[0][:, None] * counts[1][None, :])
    if z_noise_m:
        coarse = coarse + np.random.default_rng(seed).normal(0.0, z_noise_m, coarse.shape)
    coords = []
    for n, s, count in zip(tmap.shape, starts, counts):
        centres = s + (count - 1) / 2.0
        coords.append(np.interp(np.arange(n), centres, np.arange(len(s))))
    elev = map_coordinates(coarse, np.meshgrid(*coords, indexing="ij"), order=1, mode="nearest")
    tm = TraversabilityMap(elev, np.zeros(tmap.shape, dtype=bool), tmap.robot, tmap.weights)
    return PriorMap(cost=tm.cost, lethal=tm.lethal, cell_m=cell_m)
