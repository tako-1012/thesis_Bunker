"""Stamped multi-sensor registration, sharing fine-map fusion and inflation.

Each cloud is range-filtered in its sensor frame, then registered with the
full mount and stamped model pose. Attribution follows the fine mapper's
last-64-return history;
counts describe supporting returns, not ground-truth obstacle identities.
"""

from dataclasses import asdict
import json
from pathlib import Path
import threading
import time
import numpy as np
from scipy.ndimage import map_coordinates
from .config import RESOLUTION
from .pointcloud_map_fine import PointCloudMapFine, FINE_RESOLUTION, RATIO, _ranges
from .sensor_geometry import REAL_MOUNTS, DepthCameraSpec, transform_sensor_points


class PointCloudMapMulti(PointCloudMapFine):
    def __init__(self, *args, sensors='lidar_real+depth2', ground_estimate='all_returns', **kwargs):
        if sensors not in ('lidar_real', 'lidar_real+depth2'):
            raise ValueError('multi mapper needs an explicit real sensor combination')
        # Range rejection belongs to the actual sensor, not the virtual world
        # sensor used by the compatibility path.
        kwargs.update(sensor_height_m=.8, min_range_m=0., max_range_m=1e12, range_resolution_m=.01)
        super().__init__(*args, ground_estimate=ground_estimate, **kwargs)
        self.sensor_mode = sensors
        names = ('lidar', 'camera1', 'camera2') if sensors.endswith('+depth2') else ('lidar',)
        self.mounts = {name: REAL_MOUNTS[name] for name in names}
        self.depth_spec = DepthCameraSpec()
        self.sensor_counts = {name: dict(clouds=0, input_points=0, accepted_points=0,
                                        high_returns=0, first_detected_cells=0) for name in names}
        self._source_history = {}
        self._same_source = {name: np.full(min(self.samples_per_cell, 64), name, dtype='U7') for name in names}
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
        distance = _ranges(points)
        if sensor == 'lidar':
            use = (distance >= .9) & (distance < 30.-.5*.01)
        else:
            # Gazebo near clipping is axial x; the ogre2 depth shader applies far clipping to radial distance.
            spec = self.depth_spec
            x = points[:, 0]
            use = ((x >= spec.min_range_m) & (distance < spec.max_range_m)
                   & (np.abs(points[:, 1]) <= x*np.tan(np.deg2rad(spec.horizontal_fov_deg/2)))
                   & (np.abs(points[:, 2]) <= x*np.tan(np.deg2rad(spec.vertical_fov_deg/2))))
        world = transform_sensor_points(points if use.all() else points[use], pose, self.mounts[sensor])
        cells = np.floor(world[:, :2]/RESOLUTION+.5).astype(np.int64)
        inside = ((cells >= 0) & (cells < np.asarray(self.prior.shape))).all(axis=1)
        if not inside.all():
            world, cells = world[inside], cells[inside]
        flat = np.ravel_multi_index(cells.T, self.prior.shape) if len(cells) else np.empty(0, np.int64)
        with self._fusion_lock:
            keys, counts = np.unique(flat, return_counts=True)
            # All incoming returns have one source. Concatenate only the
            # part of the previous history that can survive this update.
            sources = self._same_source[sensor]
            needed = min(int(counts.max(initial=0)), self.samples_per_cell)
            if needed > len(sources):
                sources = np.full(needed, sensor, dtype='U7')
            for key, count in zip(keys.tolist(), counts.tolist()):
                n = min(count, self.samples_per_cell)
                old = self._source_history.get(key)
                if old is None or n == self.samples_per_cell:
                    current = sources[:n]
                elif old.base is sources and len(old)+n <= len(sources):
                    current = sources[:len(old)+n]
                else:
                    current = np.concatenate((old[n-self.samples_per_cell:], sources[:n]))
                self._source_history[key] = current
            prior = None
            if (self.obstacle_reference == 'prior' and self.sensor_height_m == .8
                    and self.min_range_m == 0 and self.max_range_m == 1e12
                    and self.range_resolution_m == .01 and np.abs(world).max(initial=0.) < 1e11):
                # The virtual sensor's range filter is inactive in this region.
                # Keep its exact z round trip for the history. The prior lookup
                # depends only on x/y and can also serve the original z counter.
                prior = map_coordinates(self.prior, world[:, :2].T/RESOLUTION, order=1, mode='nearest')
                fusion_world = world.copy()
                fusion_world[:, 2] = (world[:, 2]-.8)+.8+0.
                result = self._update_prior(fusion_world, cells, len(points), prior)
            else:
                result = super().update(world-[0., 0., .8], [0., 0., 0., 0., 0., 0.])
            stats = self.sensor_counts[sensor]
            stats['clouds'] += 1
            stats['input_points'] += len(points)
            stats['accepted_points'] += len(world)
            # np.argwhere in the original mapper ordered detections by flat ID.
            new_ids = np.sort(np.asarray(self._last_new_obstacles, dtype=np.intp))
            newly = np.column_stack(np.unravel_index(new_ids, self.fine_shape))
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
                if self.obstacle_reference == 'local':
                    stats['high_returns'] += int(np.count_nonzero(self._last_local_high))
                else:
                    if prior is None:
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
