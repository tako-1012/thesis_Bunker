"""Task032 opt-in stale terrain; evaluation/world arrays are never inputs here."""

import numpy as np
from .config import RESOLUTION
from .traversability import TraversabilityMap

OBSTACLE_REFERENCES = ('prior', 'local')
PRIOR_VARIANTS = ('exact', 'perturbed', 'none')
DEBRIS_BOX_HEIGHTS = ('plus_half', 'true')


def prior_variant(scenario, variant='exact'):
    """Return a new scenario and measured perturbation statistics.

    Patch number is the zero-based LAS index used by build_real. Centres
    are uniform over grid-centre bounds; each hill draws x, y, then height.
    Exact returns the original object, with no recomputation or RNG draw.
    """
    if variant not in PRIOR_VARIANTS:
        raise ValueError('unknown prior variant')
    if variant == 'exact':
        return scenario, None
    tm = scenario['tmap']
    terrain = scenario['terrain']
    z = tm.elev.copy()
    land = ~(terrain['water'] | terrain['nodata'])
    if not land.any():
        raise ValueError('no valid land for prior variant')
    if variant == 'none':
        # Flatten all heights; only the original water/nodata flags remain.
        z.fill(float(np.median(z[land])))
    else:
        rng = np.random.default_rng(np.random.SeedSequence([32, int(scenario['patch_index'])]))
        xx, yy = np.indices(z.shape)*RESOLUTION
        delta = np.zeros(z.shape)
        for _ in range(20):
            x = rng.uniform(0., (z.shape[0]-1)*RESOLUTION)
            y = rng.uniform(0., (z.shape[1]-1)*RESOLUTION)
            height = rng.uniform(-.3, .3)
            delta += height*np.exp(-((xx-x)**2+(yy-y)**2)/(2*5.**2))
        z[land] += delta[land]
    rock = np.zeros(z.shape, bool) if variant == 'none' else terrain['rock'].copy()
    raw = rock | terrain['water'] | terrain['nodata']
    updated_tm = TraversabilityMap(z, raw, tm.robot, tm.weights)
    updated = dict(scenario, tmap=updated_tm, raw_elev=z,
                   terrain=dict(terrain, elev=z, rock=rock))
    if 'obstacle' in updated:
        updated['obstacle'] = rock
    difference = z[land]-tm.elev[land]
    statistics = dict(variant=variant, patch_index=int(scenario['patch_index']),
                      max_abs_m=float(np.max(np.abs(difference))),
                      mean_abs_m=float(np.mean(np.abs(difference))),
                      changed_land_cells=int(np.count_nonzero(difference)))
    return updated, statistics
