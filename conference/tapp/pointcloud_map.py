"""ROS-free LiDAR registration and observed-cell maps, without truth-map access.

Cell heights are rolling medians of returns. A cluster above the stale DEM is
an assumed obstacle; that prior-relative rule is not ground segmentation.
Unhit cells retain prior context for derivatives but never become observed.
"""

from collections import deque
import math
import threading
import time
import numpy as np
from scipy.ndimage import map_coordinates
from scipy.spatial.transform import Rotation, Slerp

from .config import RESOLUTION, Robot, CostWeights
from .traversability import TraversabilityMap
from .footprint import inflate_steep


def transform_points(points, pose, sensor_height_m=.8):
    """Sensor xyz -> world xyz using model-origin xyz/rpy, including roll/pitch.

    Height is along model z. On level ground, the model origin is at ground
    level; model.py places the sensor at height-0.35 inside base_link.
    """
    points, pose = np.asarray(points, float), np.asarray(pose, float)
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError('points must be N x 3')
    if pose.shape != (6,) or not np.isfinite(pose).all():
        raise ValueError('pose must contain finite xyz/roll/pitch/yaw')
    if not math.isfinite(sensor_height_m) or sensor_height_m <= 0:
        raise ValueError('sensor height must be positive')
    rotation = Rotation.from_euler('xyz', pose[3:]).as_matrix()
    return (points + [0., 0., sensor_height_m]) @ rotation.T + pose[:3]


class PoseBuffer:
    """Interpolate stamped model poses; never silently use a latest-pose fallback."""
    def __init__(self, maxlen=200):
        self.items = deque(maxlen=maxlen)

    def add(self, stamp, pose):
        pose = np.asarray(pose, float)
        if not math.isfinite(stamp) or pose.shape != (6,) or not np.isfinite(pose).all():
            raise ValueError('invalid stamped pose')
        if self.items and stamp < self.items[-1][0]:
            raise ValueError('ground-truth clock moved backwards')
        if self.items and stamp == self.items[-1][0]:
            self.items.pop()
        self.items.append((float(stamp), pose.copy()))

    def at(self, stamp, max_gap_s=.1):
        if not math.isfinite(stamp) or not math.isfinite(max_gap_s) or max_gap_s <= 0:
            raise ValueError('invalid interpolation time/gap')
        for t, pose in self.items:
            if t == stamp:
                return pose.copy()
        for (a, p), (b, q) in zip(self.items, list(self.items)[1:]):
            if a < stamp < b and b-a <= max_gap_s:
                f = (stamp-a)/(b-a)
                orientation = Slerp([a, b], Rotation.from_euler('xyz', np.array([p[3:], q[3:]])))([stamp]).as_euler('xyz')[0]
                return np.r_[p[:3]+f*(q[:3]-p[:3]), orientation]
        return None


def decode_xyz(data, fields, *, point_step, row_step, width, height, is_bigendian=False):
    """Decode PointCloud2-compatible bytes, including row padding and endian tags.

    fields is a sequence of dicts with name/offset/datatype/count. ROS datatype
    7 is float32 and 8 float64; no ROS package is imported here.
    """
    if min(width, height) < 0 or point_step <= 0 or row_step < width*point_step:
        raise ValueError('invalid point cloud layout')
    if len(data) < row_step*height:
        raise ValueError('truncated point cloud')
    lookup = {f['name']: f for f in fields}
    formats, offsets = [], []
    endian = '>' if is_bigendian else '<'
    for name in ['x', 'y', 'z']:
        f = lookup.get(name)
        if f is None or f.get('count', 1) != 1 or f['datatype'] not in (7, 8):
            raise ValueError('xyz must be scalar float32/float64 fields')
        size = 4 if f['datatype'] == 7 else 8
        if f['offset'] < 0 or f['offset']+size > point_step:
            raise ValueError('xyz field outside point stride')
        formats.append(endian+('f4' if size == 4 else 'f8'))
        offsets.append(f['offset'])
    if not width or not height:
        return np.empty((0, 3))
    dtype = np.dtype(dict(names=['x', 'y', 'z'], formats=formats, offsets=offsets, itemsize=point_step))
    cloud = np.ndarray((height, width), dtype=dtype, buffer=data, strides=(row_step, point_step))
    return np.column_stack([cloud[name].ravel().astype(float) for name in ['x', 'y', 'z']])


class PointCloudMap:
    """Median surface-height map with prior context and persistent observed cells.

    The 0.3m threshold, three-return cluster and 64-return history are fixed
    assumptions, not selected on test beaches. The reference for obstacle
    height is bilinear interpolation of the stale prior, not a truth surface.
    """
    def __init__(self, prior_elev, prior_obstacle=None, *, robot=Robot(), weights=CostWeights(),
                 sensor_height_m=.8, obstacle_height_m=.3, min_obstacle_points=3,
                 samples_per_cell=64, min_range_m=.1, max_range_m=30., range_resolution_m=.01):
        z = np.asarray(prior_elev, float)
        if z.ndim != 2 or min(z.shape) < 2 or not np.isfinite(z).all():
            raise ValueError('prior elevation must be a finite 2D grid')
        if not all(math.isfinite(v) and v > 0 for v in [sensor_height_m, obstacle_height_m, max_range_m]):
            raise ValueError('heights and maximum range must be positive')
        if not math.isfinite(min_range_m) or not 0 <= min_range_m < max_range_m:
            raise ValueError('invalid minimum range')
        if not math.isfinite(range_resolution_m) or not 0 < range_resolution_m < max_range_m-min_range_m:
            raise ValueError('invalid range resolution')
        if not isinstance(min_obstacle_points, int) or min_obstacle_points < 1:
            raise ValueError('invalid cluster size')
        if not isinstance(samples_per_cell, int) or samples_per_cell < min_obstacle_points:
            raise ValueError('invalid sample history size')
        raw = np.zeros(z.shape, bool) if prior_obstacle is None else np.asarray(prior_obstacle, bool)
        if raw.shape != z.shape:
            raise ValueError('prior obstacle shape differs')
        self.prior, self.raw_obstacle = z.copy(), raw.copy()
        self.robot, self.weights = robot, weights
        self.sensor_height_m, self.obstacle_height_m = sensor_height_m, obstacle_height_m
        self.min_obstacle_points, self.samples_per_cell = min_obstacle_points, samples_per_cell
        self.min_range_m, self.max_range_m = min_range_m, max_range_m
        self.range_resolution_m = range_resolution_m
        self.elev, self.seen = z.copy(), np.zeros(z.shape, bool)
        self.detected_obstacle = np.zeros(z.shape, bool)
        self.samples, self.version = {}, 0
        self.tm = TraversabilityMap(self.elev, self.raw_obstacle, robot, weights)
        self.lethal = inflate_steep(self.tm, robot.footprint_radius)
        self._lock, self._update_lock = threading.Lock(), threading.Lock()

    def update(self, sensor_points, pose):
        began = time.perf_counter()
        points = np.asarray(sensor_points, float)
        if points.ndim != 2 or points.shape[1] != 3:
            raise ValueError('points must be N x 3')
        finite = np.isfinite(points).all(axis=1)
        distance = np.linalg.norm(points, axis=1)
        # Saturated/no-return ranges must not turn the sky into occupied cells.
        use = finite & (distance >= self.min_range_m) & (distance < self.max_range_m-.5*self.range_resolution_m)
        world = transform_points(points[use], pose, self.sensor_height_m)
        cells = np.floor(world[:, :2]/RESOLUTION+.5).astype(np.int64)
        inside = ((cells >= 0) & (cells < np.asarray(self.prior.shape))).all(axis=1)
        world, cells = world[inside], cells[inside]
        with self._update_lock:
            with self._lock:
                elev, seen, obstacle = self.elev.copy(), self.seen.copy(), self.detected_obstacle.copy()
            if len(cells):
                flat = np.ravel_multi_index(cells.T, elev.shape)
                reference = map_coordinates(self.prior, world[:, :2].T/RESOLUTION, order=1, mode='nearest')
                order = np.argsort(flat, kind='stable')
                boundaries = np.r_[0, np.flatnonzero(np.diff(flat[order]))+1, len(order)]
                for a, b in zip(boundaries[:-1], boundaries[1:]):
                    indices = order[a:b]
                    key = int(flat[indices[0]])
                    values = np.column_stack((world[indices, 2], world[indices, 2]-reference[indices]))
                    old = self.samples.get(key, np.empty((0, 2)))
                    values = np.vstack((old, values))[-self.samples_per_cell:]
                    self.samples[key] = values
                    cell = np.unravel_index(key, elev.shape)
                    elev[cell] = float(np.median(values[:, 0]))
                    seen[cell] = True
                    if np.count_nonzero(values[:, 1] >= self.obstacle_height_m) >= self.min_obstacle_points:
                        obstacle[cell] = True
                tm = TraversabilityMap(elev, self.raw_obstacle | obstacle, self.robot, self.weights)
                lethal = inflate_steep(tm, self.robot.footprint_radius)
                with self._lock:
                    self.elev, self.seen, self.detected_obstacle = elev, seen, obstacle
                    self.tm, self.lethal = tm, lethal
                    self.version += 1
            with self._lock:
                result = dict(version=self.version, input_points=len(points), accepted_points=len(cells),
                              observed_cells=int(self.seen.sum()))
        result['update_s'] = time.perf_counter()-began
        return result

    def snapshot(self):
        with self._lock:
            return self.seen.copy(), self.tm.cost.copy(), self.lethal.copy()

    def save(self, path):
        with self._lock:
            np.savez_compressed(path, elev=self.elev, seen=self.seen, obstacle=self.detected_obstacle,
                                cost=self.tm.cost, lethal=self.lethal, version=self.version)
