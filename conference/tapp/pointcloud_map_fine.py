"""Task023: fine obstacle evidence, one fine-grid dilation, unchanged coarse DEM.

Five 0.1m cells tile each existing 0.5m cell, sharing its boundaries. Height
fusion and its 64-return history stay on the original coarse grid; each return
also retains its fine cell ID so only that cell's evidence can form a cluster.
"""

import time
import numpy as np
from scipy.ndimage import binary_dilation, map_coordinates

from .config import RESOLUTION
from .pointcloud_map import PointCloudMap as _LegacyPointCloudMap, transform_points
from .traversability import TraversabilityMap
from .footprint import inflate_steep

FINE_RESOLUTION = .1
RATIO = 5


def coarse_overlap(fine):
    """Any occupied fine subcell makes its containing coarse cell unavailable."""
    nx, ny = fine.shape
    if nx % RATIO or ny % RATIO:
        raise ValueError('fine dimensions must tile the coarse map')
    return fine.reshape(nx//RATIO, RATIO, ny//RATIO, RATIO).any(axis=(1, 3))


class PointCloudMapFine(_LegacyPointCloudMap):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.obstacle_height_m != .3 or self.min_obstacle_points != 3 or self.robot.footprint_radius != .5:
            raise ValueError('task023 fixes 0.1m, 0.3m, 3 returns, and 0.5m; do not tune')
        self.fine_shape = tuple(n*RATIO for n in self.prior.shape)
        self.fine_obstacle = np.zeros(self.fine_shape, bool)
        self.fine_inflated = np.zeros(self.fine_shape, bool)
        self._fine_ids = {}
        self._inflated_coarse = np.zeros(self.prior.shape, bool)
        radius_cells = int(np.ceil(self.robot.footprint_radius/FINE_RESOLUTION))
        x, y = np.mgrid[-radius_cells:radius_cells+1, -radius_cells:radius_cells+1]
        self._disk = x*x+y*y <= (self.robot.footprint_radius/FINE_RESOLUTION)**2
        self._radius_cells = radius_cells

    def _add_obstacles(self, keys):
        if not keys:
            return
        cells = np.array(np.unravel_index(np.asarray(keys, dtype=np.int64), self.fine_shape)).T
        self.fine_obstacle[tuple(cells.T)] = True
        lo = np.maximum(cells.min(axis=0)-self._radius_cells, 0)
        hi = np.minimum(cells.max(axis=0)+self._radius_cells+1, self.fine_shape)
        seeds = np.zeros(tuple(hi-lo), bool)
        seeds[tuple((cells-lo).T)] = True
        region = tuple(slice(int(a), int(b)) for a, b in zip(lo, hi))
        # D(A union B) = D(A) union D(B). Only NEW RAW seeds are dilated;
        # the already dilated mask is never a dilation input.
        self.fine_inflated[region] |= binary_dilation(seeds, structure=self._disk)
        self.detected_obstacle = coarse_overlap(self.fine_obstacle)
        self._inflated_coarse = coarse_overlap(self.fine_inflated)

    def update(self, sensor_points, pose):
        began = time.perf_counter()
        points = np.asarray(sensor_points, float)
        if points.ndim != 2 or points.shape[1] != 3:
            raise ValueError('points must be N x 3')
        finite = np.isfinite(points).all(axis=1)
        distance = np.linalg.norm(points, axis=1)
        use = finite & (distance >= self.min_range_m) & (distance < self.max_range_m-.5*self.range_resolution_m)
        world = transform_points(points[use], pose, self.sensor_height_m)
        cells = np.floor(world[:, :2]/RESOLUTION+.5).astype(np.int64)
        inside = ((cells >= 0) & (cells < np.asarray(self.prior.shape))).all(axis=1)
        world, cells = world[inside], cells[inside]
        offset = np.floor((world[:, :2]-(cells*RESOLUTION-RESOLUTION/2))/FINE_RESOLUTION).astype(np.int64)
        # The local expression agrees with the old coarse bin at floating ties.
        # It preserves subcell positions; it is not coarse obstacle rounding.
        fine_cells = cells*RATIO+np.clip(offset, 0, RATIO-1)
        with self._update_lock:
            with self._lock:
                elev, seen = self.elev.copy(), self.seen.copy()
            if len(cells):
                flat = np.ravel_multi_index(cells.T, elev.shape)
                fine_flat = np.ravel_multi_index(fine_cells.T, self.fine_shape)
                reference = map_coordinates(self.prior, world[:, :2].T/RESOLUTION, order=1, mode='nearest')
                order = np.argsort(flat, kind='stable')
                boundaries = np.r_[0, np.flatnonzero(np.diff(flat[order]))+1, len(order)]
                new = []
                for a, b in zip(boundaries[:-1], boundaries[1:]):
                    indices = order[a:b]
                    key = int(flat[indices[0]])
                    values = np.column_stack((world[indices, 2], world[indices, 2]-reference[indices]))
                    old = self.samples.get(key, np.empty((0, 2)))
                    values = np.vstack((old, values))[-self.samples_per_cell:]
                    ids = np.r_[self._fine_ids.get(key, np.empty(0, np.int64)), fine_flat[indices]][-self.samples_per_cell:]
                    self.samples[key], self._fine_ids[key] = values, ids
                    cell = np.unravel_index(key, elev.shape)
                    elev[cell] = float(np.median(values[:, 0]))
                    seen[cell] = True
                    high_ids = ids[values[:, 1] >= self.obstacle_height_m]
                    unique, counts = np.unique(high_ids, return_counts=True)
                    for candidate in unique[counts >= self.min_obstacle_points]:
                        if not self.fine_obstacle.flat[int(candidate)]:
                            new.append(int(candidate))
                self._add_obstacles(new)
                # Prior obstacles retain their original one-time dilation. New
                # obstacles enter only AFTER that constructor has run.
                tm = TraversabilityMap(elev, self.raw_obstacle, self.robot, self.weights)
                tm.rock |= self._inflated_coarse
                tm.lethal = tm.rock | tm.steep
                lethal = inflate_steep(tm, self.robot.footprint_radius)
                with self._lock:
                    self.elev, self.seen, self.tm, self.lethal = elev, seen, tm, lethal
                    self.version += 1
            with self._lock:
                result = dict(version=self.version, input_points=len(points), accepted_points=len(cells),
                              observed_cells=int(self.seen.sum()))
        result['update_s'] = time.perf_counter()-began
        return result

    def save(self, path):
        with self._update_lock, self._lock:
            np.savez_compressed(path, elev=self.elev, seen=self.seen, obstacle=self.detected_obstacle,
                                cost=self.tm.cost, lethal=self.lethal, version=self.version,
                                fine_shape=np.asarray(self.fine_shape), fine_resolution_m=FINE_RESOLUTION,
                                fine_origin_xy=np.full(2, -RESOLUTION/2),
                                fine_obstacle_bits=np.packbits(self.fine_obstacle.ravel()),
                                fine_inflated_bits=np.packbits(self.fine_inflated.ravel()))
