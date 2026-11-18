"""Task032: two-pass local ground planes from retained sensor returns only.

Windows are 1.5m squares centred on 0.1m fine cells, in world x/y.
One actual lowest return per 0.1m cell enters the fit (ties keep the first).
Insufficient or collinear support is unknown, never a prior-based decision.
"""

import time
import numpy as np
from scipy.ndimage import maximum_filter
from scipy.spatial import cKDTree
from .config import RESOLUTION
from .pointcloud_map import transform_points
from .pointcloud_map_fine import FINE_RESOLUTION, RATIO
from .traversability import TraversabilityMap
from .footprint import inflate_steep

WINDOW_M = 1.5
TRIM_M = .15


def fine_cells(points):
    coarse = np.floor(points[:, :2]/RESOLUTION+.5).astype(np.int64)
    offset = np.floor((points[:, :2]-(coarse*RESOLUTION-RESOLUTION/2))/FINE_RESOLUTION).astype(np.int64)
    return coarse*RATIO+np.clip(offset, 0, RATIO-1)


def local_planes(support, queries):
    """Fit at 0.1m cell centres and evaluate each plane at the actual query."""
    heights = np.full(len(queries), np.nan)
    if not len(support) or not len(queries):
        return heights
    ids = fine_cells(support)
    order = np.lexsort((support[:, 2], ids[:, 1], ids[:, 0]))
    sorted_ids = ids[order]
    first = np.r_[True, np.any(np.diff(sorted_ids, axis=0), axis=1)]
    minima = support[order[first]]
    minimum_ids = sorted_ids[first]
    query_cells = fine_cells(queries)

    # A centre-aligned 1.5m window spans 15 x 15 whole fine cells.
    radius = int(WINDOW_M / (2*FINE_RESOLUTION))
    offsets = np.arange(-radius, radius+1)
    lower = np.minimum(minimum_ids.min(axis=0), query_cells.min(axis=0))-radius
    upper = np.maximum(minimum_ids.max(axis=0), query_cells.max(axis=0))+radius
    shape = tuple(upper-lower+1)
    # Bound the lookup allocation for widely separated input points.
    grid = None
    if shape[0]*shape[1] <= 5_000_000:
        grid = np.full(shape, -1, np.int32)
        grid[tuple((minimum_ids-lower).T)] = np.arange(len(minima))
        window = (offsets[:, None]*shape[1]+offsets).ravel()
        bases, inverse = np.unique(np.ravel_multi_index((query_cells-lower).T, shape),
                                   return_inverse=True)
        query_ids = np.column_stack(np.unravel_index(bases, shape))+lower
    else:
        tree = cKDTree(minimum_ids)
        query_ids, inverse = np.unique(query_cells, axis=0, return_inverse=True)

    centres = query_ids*FINE_RESOLUTION - RESOLUTION/2 + FINE_RESOLUTION/2
    planes = np.empty((len(query_ids), 3))
    for start in range(0, len(query_ids), 1024):
        batch = slice(start, start+1024)
        n = len(query_ids[batch])
        if grid is not None:
            indices = grid.ravel()[bases[batch, None]+window].ravel()
            active = np.flatnonzero(indices >= 0)
            row = active//len(window)
            neighbours = indices[active]
        else:
            windows = tree.query_ball_point(query_ids[batch], radius, p=np.inf)
            row = np.repeat(np.arange(n), [len(group) for group in windows])
            neighbours = np.concatenate(windows).astype(np.intp)

        points = minima[neighbours]
        points[:, :2] -= centres[start+row]
        first_fit = _fit_planes(points, row, n)
        x, y, z = points.T
        a, b, c = first_fit.T
        keep = z-(a[row]*x+b[row]*y+c[row]) < TRIM_M
        trimmed = np.zeros(n, bool)
        trimmed[row[~keep]] = True
        if trimmed.any():
            # With no rejected minima the second fit has identical inputs.
            refit = keep & trimmed[row]
            row_for_fit = np.cumsum(trimmed)-1
            first_fit[trimmed] = _fit_planes(points[refit], row_for_fit[row[refit]], int(trimmed.sum()))
        planes[batch] = first_fit
    displacement = queries[:, :2]-centres[inverse]
    return np.einsum('ij,ij->i', planes[inverse, :2], displacement)+planes[inverse, 2]


def _fit_planes(points, row, n):
    """Batched centred least squares, with SVD for ill-conditioned windows."""
    def total(values):
        return np.bincount(row, weights=values, minlength=n)

    count = np.bincount(row, minlength=n)
    scale = 1/np.maximum(count, 1)
    x, y, z = points.T
    mx, my, mz = total(x)*scale, total(y)*scale, total(z)*scale
    x, y, z = x-mx[row], y-my[row], z-mz[row]
    xx, yy, xy = total(x*x), total(y*y), total(x*y)
    xz, yz = total(x*z), total(y*z)
    det = xx*yy-xy*xy
    enough = count >= 3
    # For nearly singular XY covariance, use the original rank-aware solver.
    stable = enough & (det > 1e-10*(xx+yy)**2)
    a = np.divide(yy*xz-xy*yz, det, out=np.full(n, np.nan), where=stable)
    b = np.divide(xx*yz-xy*xz, det, out=np.full(n, np.nan), where=stable)
    planes = np.column_stack((a, b, mz-a*mx-b*my))
    starts = np.r_[0, count.cumsum()]
    for i in np.flatnonzero(enough & ~stable):
        selected = points[starts[i]:starts[i+1]]
        design = np.column_stack((selected[:, :2], np.ones(len(selected))))
        coefficients, _, rank, _ = np.linalg.lstsq(design, selected[:, 2], rcond=None)
        if rank == 3:
            planes[i] = coefficients
    return planes


def update_local(mapper, sensor_points, pose):
    """Opt-in fusion with the same last-64 history and existing inflation/cost."""
    began = time.perf_counter()
    points = np.asarray(sensor_points, float)
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError('points must be N x 3')
    distance = np.linalg.norm(points, axis=1)
    use = (np.isfinite(points).all(axis=1) & (distance >= mapper.min_range_m)
           & (distance < mapper.max_range_m-.5*mapper.range_resolution_m))
    world = transform_points(points[use], pose, mapper.sensor_height_m)
    cells = np.floor(world[:, :2]/RESOLUTION+.5).astype(np.int64)
    inside = ((cells >= 0) & (cells < mapper.prior.shape)).all(axis=1)
    world, cells = world[inside], cells[inside]
    with mapper._update_lock:
        with mapper._lock:
            elev, seen = mapper.elev.copy(), mapper.seen.copy()
        mapper._last_local_high = np.zeros(len(world), bool)
        if len(cells):
            flat = np.ravel_multi_index(cells.T, elev.shape)
            order = np.argsort(flat, kind='stable')
            touched, starts = np.unique(flat[order], return_index=True)
            for key, incoming in zip(touched, np.split(world[order], starts[1:])):
                old = mapper._local_points.get(int(key))
                history = incoming if old is None else np.concatenate((old, incoming))
                mapper._local_points[int(key)] = history[-mapper.samples_per_cell:].copy()

            # Off-centre queries can reach two neighbouring coarse bins.
            coarse = np.column_stack(np.unravel_index(touched, elev.shape))
            touched_mask = np.zeros(elev.shape, bool)
            touched_mask.flat[touched] = True
            support_keys = np.flatnonzero(maximum_filter(touched_mask, size=5, mode='constant'))
            support = np.concatenate([mapper._local_points[k] for k in support_keys if k in mapper._local_points])
            histories = [mapper._local_points[int(key)] for key in touched]
            centres = coarse*RESOLUTION
            queries = np.vstack([world, *histories, np.column_stack((centres, np.zeros(len(centres))))])
            reference_all = local_planes(support, queries)
            # Classify the incoming returns for sensor counters, using exactly
            # the same retained support as detection (not the stale DEM).
            mapper._last_local_high = world[:, 2]-reference_all[:len(world)] >= mapper.obstacle_height_m
            starts = np.r_[0, np.cumsum([len(history) for history in histories])]
            history_xyz = queries[len(world):-len(touched)]
            reference = reference_all[len(world):-len(touched)]
            values = np.column_stack((history_xyz[:, 2], history_xyz[:, 2]-reference))
            fine_ids = np.ravel_multi_index(fine_cells(history_xyz).T, mapper.fine_shape)
            mapper.samples.update(zip(map(int, touched), np.split(values, starts[1:-1])))
            mapper._fine_ids.update(zip(map(int, touched), np.split(fine_ids, starts[1:-1])))

            # Group sorted ground heights once, then select the middle return(s)
            # in each coarse cell. Unknown references leave the prior context.
            history_groups = np.repeat(np.arange(len(touched)), np.diff(starts))
            ground = np.isfinite(reference) & (values[:, 1] < mapper.obstacle_height_m)
            ground_z, ground_groups = values[ground, 0], history_groups[ground]
            ground_order = np.lexsort((ground_z, ground_groups))
            groups, offsets, counts = np.unique(ground_groups[ground_order],
                                                return_index=True, return_counts=True)
            height = reference_all[-len(touched):].copy()
            low = ground_z[ground_order[offsets+(counts-1)//2]]
            high = ground_z[ground_order[offsets+counts//2]]
            height[groups] = (low+high)/2
            known = np.isfinite(height)
            elev.flat[touched[known]] = height[known]
            seen.flat[touched] = True

            high_ids = fine_ids[values[:, 1] >= mapper.obstacle_height_m]
            unique, counts = np.unique(high_ids, return_counts=True)
            new = unique[(counts >= mapper.min_obstacle_points) & ~mapper.fine_obstacle.flat[unique]]
            mapper._add_obstacles(new.tolist())
            tm = TraversabilityMap(elev, mapper.raw_obstacle, mapper.robot, mapper.weights)
            tm.rock |= mapper._inflated_coarse
            tm.lethal = tm.rock | tm.steep
            lethal = inflate_steep(tm, mapper.robot.footprint_radius)
            with mapper._lock:
                mapper.elev, mapper.seen, mapper.tm, mapper.lethal = elev, seen, tm, lethal
                mapper.version += 1
        with mapper._lock:
            result = dict(version=mapper.version, input_points=len(points), accepted_points=len(cells),
                          observed_cells=int(mapper.seen.sum()))
    result['update_s'] = time.perf_counter()-began
    return result
