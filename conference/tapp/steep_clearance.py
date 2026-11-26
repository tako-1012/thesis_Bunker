"""Maintain exact distance to the current planning steep squares."""

import numpy as np

from .config import RESOLUTION
from .distance_clearance import DistanceField, R_SOFT

STEEP_CLEARANCES = ('centre', 'distance')


def validate_steep_clearance(mode, *, map_method='fine'):
    if mode not in STEEP_CLEARANCES:
        raise ValueError('unknown steep clearance')
    if mode == 'distance' and map_method != 'fine':
        raise ValueError('--steep-clearance distance requires --map fine')


class SteepDistanceField(DistanceField):
    def __init__(self, steep):
        super().__init__(steep.shape, RESOLUTION, 1, R_SOFT)
        self._steep = np.zeros_like(steep)
        self.refresh(steep)

    def refresh(self, steep):
        changed = np.argwhere(steep ^ self._steep)
        if not len(changed):
            return
        # A removed square matters only where it could have attained the
        # old minimum. An added square has the same lower-bound test.
        if np.any(self._steep[tuple(changed.T)]):
            affected = self._affected_tiles(self._tree(changed))
            self.cells = np.argwhere(steep)
            self._geometry = None
            self._update_tiles(self._tree(self.cells), affected, merge=False)
        else:
            self.add(changed)
        self._steep = steep.copy()
