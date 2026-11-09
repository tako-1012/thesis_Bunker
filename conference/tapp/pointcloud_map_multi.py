"""Stamped multi-sensor registration, reusing task023 fusion/inflation unchanged.

Each cloud is range-filtered in its sensor frame, then registered with the
full mount and stamped model pose. A virtual world-aligned sensor feeds the
unchanged fine mapper. Attribution follows its SAME last-64-return history;
counts describe supporting returns, not ground-truth obstacle identities.
"""

from dataclasses import asdict
import json
from pathlib import Path
import threading
import time
import numpy as np
from .config import RESOLUTION
from .pointcloud_map_fine import PointCloudMapFine, FINE_RESOLUTION, RATIO
from .sensor_geometry import REAL_MOUNTS, DepthCameraSpec, transform_sensor_points


class PointCloudMapMulti(PointCloudMapFine):
    def __init__(self, *args, sensors='lidar_real+depth2', **kwargs):
        if sensors not in ('lidar_real', 'lidar_real+depth2'):
            raise ValueError('multi mapper needs an explicit real sensor combination')
        # Range rejection belongs to the actual sensor, not the virtual world
        # sensor used to invoke the unmodified task023 registration/fusion.
        kwargs.update(sensor_height_m=.8, min_range_m=0., max_range_m=1e12, range_resolution_m=.01)
        super().__init__(*args, **kwargs)
        self.sensor_mode = sensors
        names = ('lidar', 'camera1', 'camera2') if sensors.endswith('+depth2') else ('lidar',)
        self.mounts = {name: REAL_MOUNTS[name] for name in names}
        self.depth_spec = DepthCameraSpec()
        self.sensor_counts = {name: dict(clouds=0, input_points=0, accepted_points=0,
                                        high_returns=0, first_detected_cells=0) for name in names}
        self._source_history = {}
        self.first_detections = []
        self._fusion_lock = threading.RLock()

    def update(self, sensor_points, pose, *, sensor='lidar', stamp=None):
        if sensor not in self.mounts:
            raise ValueError('unknown or disabled sensor: '+sensor)
        if stamp is not None and not np.isfinite(stamp):
            raise ValueError('stamp must be finite simulation time')
        began = time.perf_counter()
        points = np.asarray(sensor_points, float)
        if points.ndim != 2 or points.shape[1] != 3:
            raise ValueError('points must be N x 3')
        finite = np.isfinite(points).all(axis=1)
        if sensor == 'lidar':
            distance = np.linalg.norm(points, axis=1)
            use = finite & (distance >= .9) & (distance < 30.-.5*.01)
        else:
            # Gazebo near clipping is axial x; the ogre2 depth shader applies far clipping to radial distance.
            spec = self.depth_spec
            x = points[:, 0]
            use = (finite & (x >= spec.min_range_m) & (np.linalg.norm(points, axis=1) < spec.max_range_m)
                   & (np.abs(points[:, 1]) <= x*np.tan(np.deg2rad(spec.horizontal_fov_deg/2)))
                   & (np.abs(points[:, 2]) <= x*np.tan(np.deg2rad(spec.vertical_fov_deg/2))))
        world = transform_sensor_points(points[use], pose, self.mounts[sensor])
        cells = np.floor(world[:, :2]/RESOLUTION+.5).astype(np.int64)
        inside = ((cells >= 0) & (cells < np.asarray(self.prior.shape))).all(axis=1)
        world, cells = world[inside], cells[inside]
        flat = np.ravel_multi_index(cells.T, self.prior.shape) if len(cells) else np.empty(0, np.int64)
        with self._fusion_lock:
            for key, count in zip(*np.unique(flat, return_counts=True)):
                n = int(count)
                old = self._source_history.get(int(key), np.empty(0, dtype='U7'))
                self._source_history[int(key)] = np.r_[old, np.full(n, sensor)][-self.samples_per_cell:]
            before = self.fine_obstacle.copy()
            # The virtual sensor at (0,0,.8) plus a zero model pose reconstructs
            # exactly the already-registered world points. No filter is applied
            # based on distance from the model or from the world origin.
            result = super().update(world-[0., 0., .8], [0., 0., 0., 0., 0., 0.])
            stats = self.sensor_counts[sensor]
            stats['clouds'] += 1
            stats['input_points'] += len(points)
            stats['accepted_points'] += len(world)
            newly = np.argwhere(self.fine_obstacle & ~before)
            pose_xyz = np.asarray(pose, float)[:3]
            for fine_cell in newly:
                fine_key = int(np.ravel_multi_index(fine_cell, self.fine_shape))
                coarse_cell = tuple(fine_cell//RATIO)
                coarse_key = int(np.ravel_multi_index(coarse_cell, self.prior.shape))
                history = self.samples[coarse_key]
                ids = self._fine_ids[coarse_key]
                sources = self._source_history[coarse_key]
                supporting = sources[(ids == fine_key) & (history[:, 1] >= self.obstacle_height_m)]
                contributions = {name: int(np.count_nonzero(supporting == name)) for name in self.mounts}
                centre = -RESOLUTION/2+(fine_cell+.5)*FINE_RESOLUTION
                self.first_detections.append(dict(fine_cell=fine_cell.tolist(), stamp_sim_s=stamp,
                    triggering_sensor=sensor, supporting_returns=contributions,
                    robot_distance_xy_m=float(np.linalg.norm(centre-pose_xyz[:2]))))
            stats['first_detected_cells'] += len(newly)
            # Bilinear reference matches task023 (counts are accepted high returns).
            if len(world):
                from scipy.ndimage import map_coordinates
                prior = map_coordinates(self.prior, world[:, :2].T/RESOLUTION, order=1, mode='nearest')
                stats['high_returns'] += int(np.count_nonzero(world[:, 2]-prior >= self.obstacle_height_m))
        result.update(input_points=len(points), sensor=sensor, new_obstacle_cells=len(newly),
                      update_s=time.perf_counter()-began)
        return result

    def save(self, path):
        with self._fusion_lock:
            super().save(path)
            metadata = dict(sensor_mode=self.sensor_mode,
                            mounts={k: asdict(v) for k, v in self.mounts.items()},
                            depth_camera_spec=asdict(self.depth_spec) if len(self.mounts) > 1 else None,
                            counters=self.sensor_counts, first_detections=self.first_detections,
                            attribution='first detection at a fine cell; supporting high returns in shared last-64 history; not unique physical objects')
            # Separate JSON keeps the legacy map NPZ schema readable by task023 tools.
            Path(str(path)+'.sensors.json').write_text(json.dumps(metadata, indent=2, allow_nan=False)+'\n')
