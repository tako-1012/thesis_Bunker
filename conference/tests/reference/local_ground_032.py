"""Task032: two-pass local ground planes from retained sensor returns only.

Windows are closed 1.5m squares centred on the query point, in world x/y.
One actual lowest return per 0.1m cell enters the fit (ties keep the first).
Insufficient or collinear support is unknown, never a prior-based decision.
"""

import time
import numpy as np
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
    """Return ground height at each query, NaN when either fit is undefined."""
    result = np.full(len(queries), np.nan)
    if not len(support) or not len(queries):
        return result
    ids = fine_cells(support)
    tree = cKDTree(support[:, :2])
    query_xy, inverse = np.unique(queries[:, :2], axis=0, return_inverse=True)
    heights = np.full(len(query_xy), np.nan)
    for i, neighbours in enumerate(tree.query_ball_point(query_xy, WINDOW_M/2, p=np.inf)):
        if len(neighbours) < 3:
            continue
        neighbours = np.sort(neighbours)
        candidate_ids = ids[neighbours]
        # Clip the square FIRST. A lower return outside the window must not
        # hide a valid in-window return from the same fine cell.
        order = np.lexsort((neighbours, support[neighbours, 2], candidate_ids[:, 1], candidate_ids[:, 0]))
        sorted_ids = candidate_ids[order]
        first = np.r_[True, np.any(np.diff(sorted_ids, axis=0), axis=1)]
        points = support[neighbours[order[first]]]
        if len(points) < 3:
            continue
        # Centre coordinates improve conditioning; the intercept is query z.
        design = np.column_stack((points[:, :2]-query_xy[i], np.ones(len(points))))
        coefficients, _, rank, _ = np.linalg.lstsq(design, points[:, 2], rcond=None)
        if rank < 3:
            continue
        keep = points[:, 2]-design@coefficients < TRIM_M
        if np.count_nonzero(keep) < 3:
            continue
        coefficients, _, rank, _ = np.linalg.lstsq(design[keep], points[keep, 2], rcond=None)
        if rank == 3:
            heights[i] = coefficients[2]
    return heights[inverse]


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
            touched = np.unique(flat)
            for key in touched:
                old = mapper._local_points.get(int(key), np.empty((0, 3)))
                mapper._local_points[int(key)] = np.vstack((old, world[flat == key]))[-mapper.samples_per_cell:]
            # A query can be 0.25m off its coarse centre. The 0.75m
            # half-window can therefore reach two neighbouring coarse bins.
            support_keys = set()
            for cell in np.array(np.unravel_index(touched, elev.shape)).T:
                for dx in range(-2, 3):
                    for dy in range(-2, 3):
                        neighbour = cell+[dx, dy]
                        if ((neighbour >= 0) & (neighbour < elev.shape)).all():
                            support_keys.add(int(np.ravel_multi_index(neighbour, elev.shape)))
            support = np.vstack([mapper._local_points[k] for k in sorted(support_keys) if k in mapper._local_points])
            histories = [mapper._local_points[int(key)] for key in touched]
            centres = np.array(np.unravel_index(touched, elev.shape)).T*RESOLUTION
            queries = np.vstack([world, *histories, np.column_stack((centres, np.zeros(len(centres))))])
            # Build the support tree once per update, rather than once per
            # coarse cell. Identical query x/y positions share the same fit.
            reference_all = local_planes(support, queries)
            # Classify the incoming returns for sensor counters, using exactly
            # the same retained support as detection (not the stale DEM).
            mapper._last_local_high = world[:, 2]-reference_all[:len(world)] >= mapper.obstacle_height_m
            new = []
            cursor = len(world)
            for index, key in enumerate(touched):
                key = int(key)
                history = mapper._local_points[key]
                reference = reference_all[cursor:cursor+len(history)]
                cursor += len(history)
                values = np.column_stack((history[:, 2], history[:, 2]-reference))
                ids = np.ravel_multi_index(fine_cells(history).T, mapper.fine_shape)
                mapper.samples[key], mapper._fine_ids[key] = values, ids
                cell = np.unravel_index(key, elev.shape)
                ground = values[np.isfinite(reference) & (values[:, 1] < mapper.obstacle_height_m), 0]
                if len(ground):
                    elev[cell] = float(np.median(ground))
                else:
                    height = reference_all[-len(touched)+index]
                    if np.isfinite(height):
                        elev[cell] = height
                    # With no defined local plane, retain the planning context;
                    # it is never used to decide obstacle/ground membership.
                seen[cell] = True
                unique, counts = np.unique(ids[values[:, 1] >= mapper.obstacle_height_m], return_counts=True)
                new.extend(int(k) for k in unique[counts >= mapper.min_obstacle_points]
                           if not mapper.fine_obstacle.flat[int(k)])
            mapper._add_obstacles(new)
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
