"""Task023: fine evidence and robot-centre clearance, unchanged coarse DEM.

Five 0.1m cells tile each existing 0.5m cell, sharing its boundaries. Height
fusion and its 64-return history stay on the original coarse grid; each return
also retains its fine cell ID so only that cell's evidence can form a cluster.
Collision uses distance to the closed fine-cell square, sampled at coarse
cell centres by default. Task041 optionally pools fine squares intersecting
the same radius into their containing coarse cells.
Task029 optionally excludes obstacle returns from the ground median only.
Task062 optionally also excludes nearby returns from that median.
Task047 optionally uses fixed prior terrain for planning and retains the
fused elevation separately for diagnostics.
Task048 can add well-supported sensor steep cells to the prior steep mask.
Task066 optionally propagates ground height uncertainty to sensor slopes.
"""

from copy import copy
import time
import numpy as np
from scipy.ndimage import binary_dilation, gaussian_filter, map_coordinates, uniform_filter1d

from .config import RESOLUTION
from .distance_clearance import CombinedClearance, DistanceField, R_SOFT, validate_clearance
from .pointcloud_map import PointCloudMap as _LegacyPointCloudMap, transform_points
from .steep_clearance import SteepDistanceField, validate_steep_clearance
from .slope_uncertainty import SINGLE_HEIGHT_ERROR_M, ground_standard_errors, uncertain_steep, validate_slope_uncertainty
from .traversability import inflate, slope_deg

FINE_RESOLUTION = .1
RATIO = 5
GROUND_ESTIMATES = ('all_returns', 'non_obstacle')
GROUND_NEAR_OBSTACLE = ('keep', 'exclude')
GROUND_EXCLUSION_M = .2
OBSTACLE_CLEARANCES = ('centre', 'overlap', 'overlap_goal')  # Cohort retained by the 052 replay.
FINE_CLEARANCE_MODES = (*OBSTACLE_CLEARANCES, 'distance')
TERRAIN_SOURCES = ('sensor', 'prior', 'prior_veto')
STEEP_NEAR_OBSTACLE = ('keep', 'no_inflate')


def validate_ground_near_obstacle(mode, ground_estimate, *, map_method='fine'):
    if mode not in GROUND_NEAR_OBSTACLE:
        raise ValueError('unknown ground-near-obstacle policy')
    if mode == 'exclude' and (map_method != 'fine' or ground_estimate != 'non_obstacle'):
        raise ValueError('--ground-near-obstacle exclude requires --map fine and --ground-estimate non_obstacle')


def steep_inflation_sources(steep, obstacle_halo, prior_steep=None):
    """Exclude covered sensor slopes from inflation while retaining prior seeds."""
    sources = steep & ~obstacle_halo
    if prior_steep is not None:
        sources |= prior_steep
    return sources


def veto_steep(prior_steep, elev, supported, max_slope_deg):
    """Add sensor slopes at cells with enough returns, never clear prior slopes."""
    return prior_steep | (supported & (slope_deg(elev) > max_slope_deg))


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


def _obstacle_disk(radius_m, radius_cells, extra):
    x, y = np.mgrid[-radius_cells:radius_cells+1, -radius_cells:radius_cells+1]
    # In half-fine-cell units, measure to the edge of the occupied square,
    # and for overlap also to the edge of the query square.
    dx, dy = np.maximum(2*np.abs(x)-extra, 0), np.maximum(2*np.abs(y)-extra, 0)
    return dx*dx+dy*dy <= (2*radius_m/FINE_RESOLUTION)**2


class PointCloudMapFine(_LegacyPointCloudMap):
    def __init__(self, *args, ground_estimate='all_returns', obstacle_reference='prior',
                 obstacle_clearance='centre', terrain_source='sensor', steep_near_obstacle='keep',
                 clearance_soft_m=R_SOFT, ground_near_obstacle='keep', steep_clearance='centre', slope_uncertainty='none', **kwargs):
        validate_clearance(obstacle_clearance, clearance_soft_m)
        validate_steep_clearance(steep_clearance)
        validate_ground_near_obstacle(ground_near_obstacle, ground_estimate)
        validate_slope_uncertainty(slope_uncertainty, terrain_source)
        if steep_near_obstacle not in STEEP_NEAR_OBSTACLE:
            raise ValueError('unknown steep-near-obstacle policy')
        if terrain_source not in TERRAIN_SOURCES:
            raise ValueError('unknown terrain source')
        if obstacle_clearance not in FINE_CLEARANCE_MODES:
            raise ValueError('unknown obstacle clearance')
        if obstacle_reference not in ('prior', 'local'):
            raise ValueError('unknown obstacle reference')
        if ground_estimate not in GROUND_ESTIMATES:
            raise ValueError('unknown ground estimate')
        super().__init__(*args, **kwargs)
        self.ground_estimate = ground_estimate
        self.ground_near_obstacle = ground_near_obstacle
        self.obstacle_reference = obstacle_reference
        self.obstacle_clearance = obstacle_clearance
        self.terrain_source = terrain_source
        self.steep_near_obstacle = steep_near_obstacle
        self.slope_uncertainty = slope_uncertainty
        if slope_uncertainty == 'soft':
            self.sigma_h = np.zeros_like(self.elev)
            self.uncertain_steep = np.zeros_like(self.seen)
            self._sensor_height = np.zeros_like(self.seen)
        if steep_near_obstacle == 'no_inflate' and terrain_source != 'prior':
            self._steep_sources = self.tm.steep
        if obstacle_reference == 'local':
            self._local_points = {}
        if self.obstacle_height_m != .3 or self.min_obstacle_points != 3 or self.robot.footprint_radius != .5:
            raise ValueError('task023 fixes 0.1m, 0.3m, 3 returns, and 0.5m; do not tune')
        self.fine_shape = tuple(n*RATIO for n in self.prior.shape)
        self.fine_obstacle = np.zeros(self.fine_shape, bool)
        self.fine_inflated = np.zeros(self.fine_shape, bool)
        self._fine_ids = {}
        if ground_near_obstacle == 'exclude':
            self._ground_excluded = np.zeros(self.fine_shape, bool)
            radius = int(round(GROUND_EXCLUSION_M/FINE_RESOLUTION))
            self._ground_offsets = np.argwhere(_obstacle_disk(GROUND_EXCLUSION_M, radius, 0))-radius
        self._inflated_coarse = np.zeros(self.prior.shape, bool)
        radius_cells = int(np.ceil(self.robot.footprint_radius/FINE_RESOLUTION))
        # An overlap query is a square, with an extra half cell on each axis.
        overlap = obstacle_clearance in ('overlap', 'overlap_goal')
        self._radius_cells = radius_cells + int(overlap)
        self._disk = _obstacle_disk(self.robot.footprint_radius, self._radius_cells, 2 if overlap else 1)
        if obstacle_clearance == 'overlap_goal':
            centre_disk = _obstacle_disk(self.robot.footprint_radius, radius_cells, 1)
            self._centre_offsets = np.argwhere(centre_disk) - radius_cells
        self._prior_rock = self.tm.rock.copy()
        self._last_new_obstacles = []
        self._disk_offsets = np.argwhere(self._disk) - self._radius_cells
        if obstacle_clearance == 'distance':
            self.distance_field = DistanceField(self.prior.shape, FINE_RESOLUTION, RATIO, clearance_soft_m)
        if steep_clearance == 'distance':
            self.steep_distance_field = SteepDistanceField(self.tm.steep)
        if terrain_source == 'sensor':
            self._residual = self.elev - gaussian_filter(self.elev, sigma=1.5)
            self._rough_mean_x = uniform_filter1d(self._residual, 3, axis=0)
            self._rough_square_x = uniform_filter1d(self._residual**2, 3, axis=0)
        elif terrain_source == 'prior_veto':
            self._prior_steep = self.tm.steep
            self._veto_supported = np.zeros(self.prior.shape, bool)

    def _initial_lethal(self):
        self._dilated_steep = inflate(self.tm.steep, self.robot.footprint_radius)
        return self.tm.lethal | self._dilated_steep

    def _add_obstacles(self, keys):
        self._last_new_obstacles = keys
        if not keys:
            return
        cells = np.column_stack(np.unravel_index(keys, self.fine_shape))
        self.fine_obstacle[tuple(cells.T)] = True
        self.detected_obstacle[tuple((cells//RATIO).T)] = True
        if self.obstacle_clearance == 'distance':
            self.distance_field.add(cells)
        lo = np.maximum(cells.min(axis=0)-self._radius_cells, 0)
        hi = np.minimum(cells.max(axis=0)+self._radius_cells+1, self.fine_shape)
        if len(cells)*len(self._disk_offsets) < np.prod(hi-lo):
            # Sparse seeds can span a large rectangle. Stamp the same disk
            # offsets explicitly and keep its in-map cells.
            halo = (cells[:, None]+self._disk_offsets).reshape(-1, 2)
            halo = halo[((halo >= 0) & (halo < self.fine_shape)).all(axis=1)]
            self.fine_inflated[tuple(halo.T)] = True
            if self.obstacle_clearance in ('centre', 'distance'):
                halo = halo[(halo % RATIO == RATIO//2).all(axis=1)]
            self._inflated_coarse[tuple((halo//RATIO).T)] = True
        else:
            seeds = np.zeros(tuple(hi-lo), bool)
            seeds[tuple((cells-lo).T)] = True
            region = tuple(slice(int(a), int(b)) for a, b in zip(lo, hi))
            self.fine_inflated[region] |= binary_dilation(seeds, structure=self._disk)
            if self.obstacle_clearance in ('overlap', 'overlap_goal'):
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

    def planning_seen(self, seen, *, known=None):
        """Give the planner inferred hazards without changing measured coverage.

        The caller holds the update lock so the halo matches the snapshot.
        """
        if self.terrain_source != 'sensor':
            # The soft prior would otherwise allow unobserved steep cells.
            seen = seen | self._dilated_steep
            if self.steep_near_obstacle == 'no_inflate' and self.terrain_source == 'prior_veto' and known is not None:
                # Overwrite earlier inferred halo cells if the sensor veto retracts.
                seen |= known
        if self.obstacle_clearance in ('overlap', 'overlap_goal'):
            return seen | self._inflated_coarse
        return seen

    def planning_snapshot(self, *, known=None):
        if self.obstacle_clearance == 'centre' and self.terrain_source == 'sensor':
            return self.snapshot()
        with self._update_lock:
            return self._planning_snapshot_locked(known)

    def _planning_snapshot_locked(self, known):
        seen, cost, lethal = self.snapshot()
        if self.obstacle_clearance == 'distance':
            cost = cost+self.distance_field.cost
        return self.planning_seen(seen, known=known), cost, lethal

    def planning_distance_snapshot(self, *, known=None):
        with self._update_lock:
            return self._planning_snapshot_locked(known), self.distance_field.geometry()

    def steep_distance_snapshot(self):
        """Capture both guards and steep cost while the caller holds the update lock."""
        field = self.steep_distance_field
        geometry = field.geometry()
        if self.obstacle_clearance == 'distance':
            geometry = CombinedClearance(self.distance_field.geometry(), geometry)
        return geometry, field.cost.copy()

    def planning_steep_snapshot(self, *, known=None, goals=None):
        with self._update_lock:
            return (self._planning_snapshot_locked(known), self.steep_distance_snapshot(),
                    self.goal_obstacle_overrides(goals) if goals is not None else None)

    def planning_goal_snapshot(self, cells, *, known=None):
        with self._update_lock:
            return self._planning_snapshot_locked(known), self.goal_obstacle_overrides(cells)

    def goal_obstacle_overrides(self, cells):
        """For each affected endpoint, return whether rock or steepness still blocks it.

        The caller holds the update lock. Probe only the fine cells around the
        requested centres with the same disk as the centre mapper.
        """
        overrides = {}
        for cell in cells:
            if (not all(0 <= v < n for v, n in zip(cell, self.prior.shape))
                    or not self._inflated_coarse[cell]):
                continue
            fine = np.asarray(cell)*RATIO + RATIO//2 + self._centre_offsets
            fine = fine[((fine >= 0) & (fine < self.fine_shape)).all(axis=1)]
            if not self.fine_obstacle[tuple(fine.T)].any():
                overrides[cell] = bool(self._prior_rock[cell] or self.tm.steep[cell] or self._dilated_steep[cell])
        return overrides

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

    def _refresh_steep_halo(self, steep):
        # overlap_goal stores the overlap map here; its endpoint exception
        # is applied to the obstacle layer by the planner.
        sources = steep_inflation_sources(steep, self._inflated_coarse, getattr(self, '_prior_steep', None))
        changed = np.asarray(np.nonzero(sources ^ self._steep_sources))
        if not changed.size:
            return
        # One radius bounds affected outputs. A second supplies the unchanged
        # sources that can still reach those outputs, including at map edges.
        radius = self.robot.footprint_radius
        cells = int(np.ceil(radius/RESOLUTION))
        lo = np.maximum(changed.min(axis=1)-cells, 0)
        hi = np.minimum(changed.max(axis=1)+1+cells, sources.shape)
        start = np.maximum(lo-cells, 0)
        stop = np.minimum(hi+cells, sources.shape)
        region = tuple(slice(a, b) for a, b in zip(lo, hi))
        inputs = tuple(slice(a, b) for a, b in zip(start, stop))
        core = tuple(slice(a, b) for a, b in zip(lo-start, hi-start))
        halo = self._dilated_steep.copy()
        halo[region] = inflate(sources[inputs], radius)[core]
        self._dilated_steep, self._steep_sources = halo, sources

    def _publish(self, touched, heights, *, observed=None, height_error=None):
        # Keep old snapshots valid. Reuse the elevation and its derived
        # fields when the written heights have identical bits (including -0).
        observed = touched if observed is None else observed
        old_heights = self.elev.flat[touched]
        changed = old_heights.view(np.uint64) != heights.view(np.uint64)
        seen = self.seen
        if not seen.flat[observed].all():
            seen = seen.copy()
            seen.flat[observed] = True
        elev, tm, lethal = self.elev, self.tm, self.lethal
        elev_changed = changed.any()
        if elev_changed:
            elev = elev.copy()
            elev.flat[touched[changed]] = heights[changed]
        update_terrain = elev_changed and self.terrain_source == 'sensor'
        uncertainty_changed = False
        if height_error is not None:
            sigma_h, uncertain = self.sigma_h, self.uncertain_steep
            uncertainty_changed = np.any(sigma_h.flat[touched] != height_error)
            if uncertainty_changed:
                sigma_h = sigma_h.copy()
                sigma_h.flat[touched] = height_error
        refresh_terrain = update_terrain or uncertainty_changed
        steep = self._updated_veto(elev, observed, elev_changed) if self.terrain_source == 'prior_veto' else None
        if refresh_terrain or steep is not None or self._last_new_obstacles:
            tm = copy(tm)
            if update_terrain:
                tm.elev = elev
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
            if refresh_terrain:
                tm.steep = tm.slope > self.robot.max_slope_deg
                slope = tm.slope / self.robot.max_slope_deg
                rough = tm.rough / self.robot.rough_sat
                np.clip(slope, 0, 1, out=slope)
                np.clip(rough, 0, 1, out=rough)
                tm.cost = self.weights.alpha * slope + self.weights.beta * rough
                if height_error is not None:
                    uncertain = uncertain_steep(tm.gx, tm.gy, tm.steep, sigma_h, self.robot.max_slope_deg)
                    tm.steep &= ~uncertain
                    tm.cost[uncertain] = 1.
            if steep is not None:
                tm.steep = steep
            if self.steep_near_obstacle == 'no_inflate' and self.terrain_source != 'prior':
                self._refresh_steep_halo(tm.steep)
            elif steep is not None or (refresh_terrain and not np.array_equal(tm.steep, self.tm.steep)):
                self._dilated_steep = inflate(tm.steep, self.robot.footprint_radius)
            if self._last_new_obstacles:
                tm.rock = self._prior_rock | self._inflated_coarse
            tm.lethal = tm.rock | tm.steep
            lethal = tm.lethal | self._dilated_steep
            if hasattr(self, 'steep_distance_field') and tm.steep is not self.tm.steep:
                self.steep_distance_field.refresh(tm.steep)
        with self._lock:
            self.elev, self.seen, self.tm, self.lethal = elev, seen, tm, lethal
            if height_error is not None:
                self.sigma_h, self.uncertain_steep = sigma_h, uncertain
            self.version += 1

    def _updated_veto(self, elev, observed, elev_changed):
        # Histories only append and trim to the cap. A cell that reached the
        # support threshold cannot fall below it during this mapper's life.
        pending = observed[~self._veto_supported.flat[observed]]
        half = (self.samples_per_cell+1)//2
        newly_supported = [cell for cell in pending if len(self.samples[int(cell)]) >= half]
        self._veto_supported.flat[newly_supported] = True
        if elev_changed or newly_supported:
            steep = veto_steep(self._prior_steep, elev, self._veto_supported, self.robot.max_slope_deg)
            if not np.array_equal(steep, self.tm.steep):
                return steep
        return None

    def _publish_soft_ground(self, touched, heights, errors, *, observed):
        # An excluded or unsupported estimate leaves its previous height.
        # A held sensor height now has at most one supporting ground return.
        estimated = np.isfinite(heights)
        self._sensor_height.flat[touched[estimated]] = True
        held = touched[~estimated]
        heights[~estimated] = self.elev.flat[held]
        errors[~estimated] = np.where(self._sensor_height.flat[held], SINGLE_HEIGHT_ERROR_M, 0.)
        self._publish(touched, heights, observed=observed, height_error=errors)

    def _publish_excluded_ground(self, touched):
        # Detection consumed the unfiltered history. Dirty coarse cells include
        # those whose old returns are newly covered, even without new samples.
        dirty = touched
        if self._last_new_obstacles:
            new = np.column_stack(np.unravel_index(self._last_new_obstacles, self.fine_shape))
            halo = (new[:, None]+self._ground_offsets).reshape(-1, 2)
            halo = halo[((halo >= 0) & (halo < self.fine_shape)).all(axis=1)]
            halo = halo[~self._ground_excluded[tuple(halo.T)]]
            self._ground_excluded[tuple(halo.T)] = True
            affected = np.ravel_multi_index((halo//RATIO).T, self.prior.shape)
            dirty = np.union1d(touched, affected)
        updated, heights, errors = [], [], []
        soft = self.slope_uncertainty == 'soft'
        for key in dirty.tolist():
            samples = self.samples.get(key)
            if samples is None:
                continue
            ground = ((samples[:, 1] < self.obstacle_height_m)
                      & ~self._ground_excluded.flat[self._fine_ids[key]])
            # As in the existing median, one eligible return suffices.
            # With none, preserve the previous estimate (initially the prior).
            if ground.any():
                z = samples[ground, 0]
                updated.append(key)
                heights.append(np.median(z))
                if soft:
                    errors.append(np.std(z-z[0], ddof=1)/np.sqrt(len(z)) if len(z) > 1 else SINGLE_HEIGHT_ERROR_M)
            elif soft:
                updated.append(key)
                heights.append(np.nan)
                errors.append(SINGLE_HEIGHT_ERROR_M)
        keys, values = np.asarray(updated, dtype=np.intp), np.asarray(heights)
        if soft:
            self._publish_soft_ground(keys, values, np.asarray(errors), observed=touched)
        else:
            self._publish(keys, values, observed=touched)

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

        high_ids = ids[history[:, 1] >= self.obstacle_height_m]
        unique, totals = np.unique(high_ids, return_counts=True)
        new = unique[(totals >= self.min_obstacle_points) & ~self.fine_obstacle.flat[unique]].tolist()
        if self.ground_near_obstacle == 'exclude':
            self._add_obstacles(new)
            self._publish_excluded_ground(touched)
            return

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
        self._add_obstacles(new)
        options = {}
        if self.slope_uncertainty == 'soft':
            errors = ground_standard_errors(z, groups, lengths)
            errors[lengths == 0] = 0.  # This branch falls back to the prior height.
            options['height_error'] = errors
        self._publish(touched, heights, **options)

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
            terrain = dict(terrain_steep=self.tm.steep) if self.terrain_source != 'sensor' else {}
            if self.terrain_source == 'prior_veto':
                terrain['veto_supported'] = self._veto_supported
            if self.slope_uncertainty == 'soft':
                terrain.update(sigma_h=self.sigma_h, uncertain_steep=self.uncertain_steep)
            np.savez_compressed(path, elev=self.elev, seen=self.seen, obstacle=self.detected_obstacle,
                                cost=self.tm.cost, lethal=self.lethal, version=self.version,
                                fine_shape=np.asarray(self.fine_shape), fine_resolution_m=FINE_RESOLUTION,
                                fine_origin_xy=np.full(2, -RESOLUTION/2),
                                fine_obstacle_bits=np.packbits(self.fine_obstacle.ravel()),
                                fine_inflated_bits=np.packbits(self.fine_inflated.ravel()), **terrain)
