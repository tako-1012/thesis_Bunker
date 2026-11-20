"""Task023: fine evidence and robot-centre clearance, unchanged coarse DEM.

Five 0.1m cells tile each existing 0.5m cell, sharing its boundaries. Height
fusion and its 64-return history stay on the original coarse grid; each return
also retains its fine cell ID so only that cell's evidence can form a cluster.
Collision uses distance to the closed fine-cell square, sampled at coarse
cell centres by default. Task041 optionally pools fine squares intersecting
the same radius into their containing coarse cells.
Task029 optionally excludes obstacle returns from the ground median only.
"""

from copy import copy
import time
import numpy as np
from scipy.ndimage import binary_dilation, gaussian_filter, map_coordinates, uniform_filter1d

from .config import RESOLUTION
from .pointcloud_map import PointCloudMap as _LegacyPointCloudMap, transform_points
from .traversability import inflate

FINE_RESOLUTION = .1
RATIO = 5
GROUND_ESTIMATES = ('all_returns', 'non_obstacle')
OBSTACLE_CLEARANCES = ('centre', 'overlap')


def _ranges(points):
    # Same left-to-right sum of three squares as norm(axis=1). Comparisons
    # against finite range limits already reject NaN and infinity.
    x, y, z = points.T
    return np.sqrt(x*x+y*y+z*z)


def coarse_overlap(fine):
    """Any occupied fine subcell makes its containing coarse cell unavailable."""
    nx, ny = fine.shape
    if nx % RATIO or ny % RATIO:
        raise ValueError('fine dimensions must tile the coarse map')
    return fine.reshape(nx//RATIO, RATIO, ny//RATIO, RATIO).any(axis=(1, 3))


class PointCloudMapFine(_LegacyPointCloudMap):
    def __init__(self, *args, ground_estimate='all_returns', obstacle_reference='prior',
                 obstacle_clearance='centre', **kwargs):
        if obstacle_clearance not in OBSTACLE_CLEARANCES:
            raise ValueError('unknown obstacle clearance')
        if obstacle_reference not in ('prior', 'local'):
            raise ValueError('unknown obstacle reference')
        if ground_estimate not in GROUND_ESTIMATES:
            raise ValueError('unknown ground estimate')
        super().__init__(*args, **kwargs)
        self.ground_estimate = ground_estimate
        self.obstacle_reference = obstacle_reference
        self.obstacle_clearance = obstacle_clearance
        if obstacle_reference == 'local':
            self._local_points = {}
        if self.obstacle_height_m != .3 or self.min_obstacle_points != 3 or self.robot.footprint_radius != .5:
            raise ValueError('task023 fixes 0.1m, 0.3m, 3 returns, and 0.5m; do not tune')
        self.fine_shape = tuple(n*RATIO for n in self.prior.shape)
        self.fine_obstacle = np.zeros(self.fine_shape, bool)
        self.fine_inflated = np.zeros(self.fine_shape, bool)
        self._fine_ids = {}
        self._inflated_coarse = np.zeros(self.prior.shape, bool)
        radius_cells = int(np.ceil(self.robot.footprint_radius/FINE_RESOLUTION))
        # An overlap query is a square, with an extra half cell on each axis.
        extra = 2 if obstacle_clearance == 'overlap' else 1
        radius_cells += int(obstacle_clearance == 'overlap')
        x, y = np.mgrid[-radius_cells:radius_cells+1, -radius_cells:radius_cells+1]
        # In half-fine-cell units, distance from a query centre to the nearest
        # point of an occupied square is max(2*abs(offset)-1, 0) on each axis.
        # Integer offsets retain the cell edges, including diagonal corners;
        # subtracting just 0.05m from a scalar centre distance would not.
        dx, dy = np.maximum(2*np.abs(x)-extra, 0), np.maximum(2*np.abs(y)-extra, 0)
        self._disk = dx*dx+dy*dy <= (2*self.robot.footprint_radius/FINE_RESOLUTION)**2
        self._radius_cells = radius_cells
        self._prior_rock = self.tm.rock.copy()
        self._last_new_obstacles = []
        self._disk_offsets = np.argwhere(self._disk) - radius_cells
        self._dilated_steep = inflate(self.tm.steep, self.robot.footprint_radius)
        self._residual = self.elev - gaussian_filter(self.elev, sigma=1.5)
        self._rough_mean_x = uniform_filter1d(self._residual, 3, axis=0)
        self._rough_square_x = uniform_filter1d(self._residual**2, 3, axis=0)

    def _add_obstacles(self, keys):
        self._last_new_obstacles = keys
        if not keys:
            return
        cells = np.column_stack(np.unravel_index(keys, self.fine_shape))
        self.fine_obstacle[tuple(cells.T)] = True
        self.detected_obstacle[tuple((cells//RATIO).T)] = True
        lo = np.maximum(cells.min(axis=0)-self._radius_cells, 0)
        hi = np.minimum(cells.max(axis=0)+self._radius_cells+1, self.fine_shape)
        if len(cells)*len(self._disk_offsets) < np.prod(hi-lo):
            # Sparse seeds can span a large rectangle. Stamp the same disk
            # offsets explicitly and keep its in-map cells.
            halo = (cells[:, None]+self._disk_offsets).reshape(-1, 2)
            halo = halo[((halo >= 0) & (halo < self.fine_shape)).all(axis=1)]
            self.fine_inflated[tuple(halo.T)] = True
            if self.obstacle_clearance == 'centre':
                halo = halo[(halo % RATIO == RATIO//2).all(axis=1)]
            self._inflated_coarse[tuple((halo//RATIO).T)] = True
        else:
            seeds = np.zeros(tuple(hi-lo), bool)
            seeds[tuple((cells-lo).T)] = True
            region = tuple(slice(int(a), int(b)) for a, b in zip(lo, hi))
            self.fine_inflated[region] |= binary_dilation(seeds, structure=self._disk)
            if self.obstacle_clearance == 'overlap':
                # Include whole coarse cells intersecting the changed fine region.
                coarse_lo, coarse_hi = lo//RATIO, (hi+RATIO-1)//RATIO
                coarse = tuple(slice(a, b) for a, b in zip(coarse_lo, coarse_hi))
                fine = tuple(slice(a*RATIO, b*RATIO) for a, b in zip(coarse_lo, coarse_hi))
                self._inflated_coarse[coarse] = coarse_overlap(self.fine_inflated[fine])
                return
            # Each coarse centre is the middle fine centre.
            coarse_lo = (lo+RATIO//2)//RATIO
            coarse_hi = (hi+RATIO//2)//RATIO
            coarse = tuple(slice(a, b) for a, b in zip(coarse_lo, coarse_hi))
            fine = tuple(slice(a*RATIO+RATIO//2, b*RATIO+RATIO//2, RATIO)
                         for a, b in zip(coarse_lo, coarse_hi))
            self._inflated_coarse[coarse] = self.fine_inflated[fine]

    def planning_seen(self, seen):
        """Include inferred obstacle halo cells without marking terrain observed.

        The caller holds the update lock so the halo matches the snapshot.
        """
        if self.obstacle_clearance == 'overlap':
            return seen | self._inflated_coarse
        return seen

    def planning_snapshot(self):
        if self.obstacle_clearance == 'centre':
            return self.snapshot()
        with self._update_lock:
            seen, cost, lethal = self.snapshot()
            return self.planning_seen(seen), cost, lethal

    def _update_roughness(self, elev, lo, hi):
        # scipy's sigma=1.5 Gaussian has radius 6 at its default truncate=4.
        # The first halo bounds changed residuals; the second supplies inputs
        # for the same Gaussian sums, including reflection at true map edges.
        lo = np.maximum(lo-6, 0)
        hi = np.minimum(hi+6, elev.shape)
        start = np.maximum(lo-6, 0)
        stop = np.minimum(hi+6, elev.shape)
        region = tuple(slice(a, b) for a, b in zip(lo, hi))
        input_region = tuple(slice(a, b) for a, b in zip(start, stop))
        core = tuple(slice(a, b) for a, b in zip(lo-start, hi-start))
        self._residual[region] = elev[region]-gaussian_filter(elev[input_region], sigma=1.5)[core]

        # Uniform filtering uses running sums. A changed input can affect
        # roundoff beyond the local stencil, so filter whole affected lines.
        cols = region[1]
        residual = self._residual[:, cols]
        self._rough_mean_x[:, cols] = uniform_filter1d(residual, 3, axis=0)
        self._rough_square_x[:, cols] = uniform_filter1d(residual**2, 3, axis=0)
        # Before the first affected residual row's one-cell halo, the
        # axis-0 running sums have yet to encounter any changed value.
        rows = slice(max(lo[0]-1, 0), None)
        mean = uniform_filter1d(self._rough_mean_x[rows], 3, axis=1)
        square = uniform_filter1d(self._rough_square_x[rows], 3, axis=1)
        np.subtract(square, mean**2, out=square)
        np.maximum(square, 0., out=square)
        rough = self.tm.rough.copy()
        np.sqrt(square, out=rough[rows])
        return rough

    def _publish(self, touched, heights, *, observed=None):
        # Keep old snapshots valid. Reuse the elevation and its derived
        # fields when the written heights have identical bits (including -0).
        observed = touched if observed is None else observed
        old_heights = self.elev.flat[touched]
        changed = old_heights.view(np.uint64) != heights.view(np.uint64)
        seen = self.seen
        if not seen.flat[observed].all():
            seen = seen.copy()
            seen.flat[observed] = True
        tm, lethal = self.tm, self.lethal
        elev_changed = changed.any()
        if elev_changed or self._last_new_obstacles:
            tm = copy(tm)
            if elev_changed:
                tm.elev = self.elev.copy()
                tm.elev.flat[touched[changed]] = heights[changed]
                cells = np.asarray(np.unravel_index(touched[changed], self.prior.shape))
                lo, hi = cells.min(axis=1), cells.max(axis=1)+1
                # One cell of affected gradients plus one input cell
                # preserve the central differences at the crop boundary.
                out_lo = np.maximum(lo-1, 0)
                out_hi = np.minimum(hi+1, tm.shape)
                in_lo = np.maximum(lo-2, 0)
                in_hi = np.minimum(hi+2, tm.shape)
                region = tuple(slice(a, b) for a, b in zip(out_lo, out_hi))
                inputs = tuple(slice(a, b) for a, b in zip(in_lo, in_hi))
                core = tuple(slice(a, b) for a, b in zip(out_lo-in_lo, out_hi-in_lo))
                gx, gy = np.gradient(tm.elev[inputs], RESOLUTION)
                tm.gx, tm.gy, tm.slope = tm.gx.copy(), tm.gy.copy(), tm.slope.copy()
                tm.gx[region], tm.gy[region] = gx[core], gy[core]
                tm.slope[region] = np.degrees(np.arctan(np.hypot(gx[core], gy[core])))
                tm.rough = self._update_roughness(tm.elev, lo, hi)
                tm.steep = tm.slope > self.robot.max_slope_deg
                if not np.array_equal(tm.steep, self.tm.steep):
                    self._dilated_steep = inflate(tm.steep, self.robot.footprint_radius)
                slope = tm.slope / self.robot.max_slope_deg
                rough = tm.rough / self.robot.rough_sat
                np.clip(slope, 0, 1, out=slope)
                np.clip(rough, 0, 1, out=rough)
                tm.cost = self.weights.alpha * slope + self.weights.beta * rough
            if self._last_new_obstacles:
                tm.rock = self._prior_rock | self._inflated_coarse
            tm.lethal = tm.rock | tm.steep
            lethal = tm.lethal | self._dilated_steep
        with self._lock:
            self.elev, self.seen, self.tm, self.lethal = tm.elev, seen, tm, lethal
            self.version += 1

    def _update_prior(self, world, cells, input_points, reference=None):
        with self._update_lock:
            self._last_new_obstacles = []
            if len(cells):
                offset = np.floor((world[:, :2]-(cells*RESOLUTION-RESOLUTION/2))/FINE_RESOLUTION).astype(np.int64)
                # This local expression preserves the legacy coarse bin at ties.
                fine_cells = cells*RATIO+np.clip(offset, 0, RATIO-1)
                self._fuse_prior(world, cells, fine_cells, reference)
            with self._lock:
                return dict(version=self.version, input_points=input_points, accepted_points=len(cells),
                            observed_cells=int(self.seen.sum()))

    def _fuse_prior(self, world, cells, fine_cells, reference):
        flat = np.ravel_multi_index(cells.T, self.prior.shape)
        fine_flat = np.ravel_multi_index(fine_cells.T, self.fine_shape)
        order = np.argsort(flat, kind='stable')
        sorted_flat = flat[order]
        starts = np.r_[0, np.flatnonzero(np.diff(sorted_flat))+1]
        counts = np.diff(starts, append=len(order))
        touched = sorted_flat[starts]
        limit = self.samples_per_cell
        incoming = np.minimum(counts, limit)
        keys = touched.tolist()
        previous = list(map(self.samples.get, keys))
        retained = np.minimum(limit-incoming, [len(old) if old is not None else 0
                                               for old in previous])
        ends = np.cumsum(incoming+retained)
        offsets = ends-incoming-retained
        # Drop the discarded prefix before interpolation and history assembly.
        positions = np.arange(len(order))
        use = positions >= np.repeat(starts+counts-incoming, counts)
        indices = order[use]
        target = np.arange(len(indices)) + np.repeat(np.cumsum(retained), incoming)
        xyz = world[indices]
        prior = (map_coordinates(self.prior, xyz[:, :2].T/RESOLUTION, order=1, mode='nearest')
                 if reference is None else reference[indices])
        history = np.empty((ends[-1], 2))
        ids = np.empty(ends[-1], np.int64)
        history[target, 0] = xyz[:, 2]
        history[target, 1] = xyz[:, 2]-prior
        ids[target] = fine_flat[indices]
        if retained.any():
            was_retained = np.flatnonzero(retained)
            old_keys = touched[was_retained].tolist()
            old_counts = retained[was_retained]
            old_values = np.concatenate([previous[i][-n:] for i, n in zip(was_retained.tolist(), old_counts.tolist())])
            old_ids = np.concatenate([self._fine_ids[k][-n:] for k, n in zip(old_keys, old_counts.tolist())])
            old_target = np.arange(len(old_ids)) + np.repeat(
                offsets[was_retained] - (np.cumsum(old_counts)-old_counts), old_counts)
            history[old_target], ids[old_target] = old_values, old_ids
        # Slices share small batches. Copies at the batch boundary prevent
        # one surviving cell from keeping an entire previous scan alive.
        batch_size = 32
        starts, stops = offsets.tolist(), ends.tolist()
        for first in range(0, len(keys), batch_size):
            last = min(first+batch_size, len(keys))
            base = starts[first]
            value_batch = history[base:stops[last-1]].copy()
            id_batch = ids[base:stops[last-1]].copy()
            for key, start, stop in zip(keys[first:last], starts[first:last], stops[first:last]):
                part = slice(start-base, stop-base)
                self.samples[key], self._fine_ids[key] = value_batch[part], id_batch[part]

        z = history[:, 0]
        lengths = incoming+retained
        groups = np.repeat(np.arange(len(touched)), lengths)
        heights = self.prior.flat[touched]
        if self.ground_estimate == 'non_obstacle':
            ground = history[:, 1] < self.obstacle_height_m
            z, groups = z[ground], groups[ground]
            lengths = np.bincount(groups, minlength=len(touched))
        offsets = np.cumsum(lengths)-lengths
        occupied = np.flatnonzero(lengths)
        counts = lengths[occupied]
        width = lengths.max()
        nan_mask = np.isnan(z)
        has_nan = nan_mask.any()
        if width*len(touched) <= 4*len(history) and not has_nan:
            # Histories are already grouped. Sorting short padded rows avoids
            # sorting all returns together by both group and height.
            rows = np.full((len(touched), width), np.inf)
            rows[groups, np.arange(len(z))-offsets[groups]] = z
            rows.sort(axis=1)
            low = rows[occupied, (counts-1)//2]
            high = rows[occupied, counts//2]
        else:
            order = np.lexsort((z, groups))
            start = offsets[occupied]
            low = z[order[start+(counts-1)//2]]
            high = z[order[start+counts//2]]
        # np.median takes the mean of one or two middle values.
        even = counts % 2 == 0
        low[even] = (low[even]+high[even])/2
        low += 0.
        if has_nan:
            # Match NumPy's per-cell NaN propagation and payload selection.
            for key in np.unique(groups[nan_mask]):
                low[np.searchsorted(occupied, key)] = np.median(z[offsets[key]:offsets[key]+lengths[key]])
        heights[occupied] = low
        high_ids = ids[history[:, 1] >= self.obstacle_height_m]
        unique, totals = np.unique(high_ids, return_counts=True)
        new = unique[(totals >= self.min_obstacle_points) & ~self.fine_obstacle.flat[unique]]
        self._add_obstacles(new.tolist())
        self._publish(touched, heights)

    def update(self, sensor_points, pose):
        if self.obstacle_reference == 'local':
            from .local_ground import update_local
            return update_local(self, sensor_points, pose)
        began = time.perf_counter()
        points = np.asarray(sensor_points, float)
        if points.ndim != 2 or points.shape[1] != 3:
            raise ValueError('points must be N x 3')
        distance = _ranges(points)
        use = (distance >= self.min_range_m) & (distance < self.max_range_m-.5*self.range_resolution_m)
        world = transform_points(points if use.all() else points[use], pose, self.sensor_height_m)
        cells = np.floor(world[:, :2]/RESOLUTION+.5).astype(np.int64)
        inside = ((cells >= 0) & (cells < np.asarray(self.prior.shape))).all(axis=1)
        if not inside.all():
            world, cells = world[inside], cells[inside]
        result = self._update_prior(world, cells, len(points))
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
