"""Task027 fixed mounts (model origin, x forward/y left/z up) and D455 assumptions."""

from dataclasses import asdict, dataclass
import math
import numpy as np
from scipy.spatial.transform import Rotation

SENSOR_MODES = ('legacy', 'lidar_real', 'lidar_real+depth2')


@dataclass(frozen=True)
class SensorMount:
    xyz: tuple
    rpy: tuple = (0., 0., 0.)

    def __post_init__(self):
        if len(self.xyz) != 3 or len(self.rpy) != 3 or not np.isfinite((*self.xyz, *self.rpy)).all():
            raise ValueError('mount requires finite xyz and roll/pitch/yaw triples')

    @property
    def base_link_xyz(self):
        return (self.xyz[0], self.xyz[1], self.xyz[2]-.35)


@dataclass(frozen=True)
class DepthCameraSpec:
    horizontal_fov_deg: float = 87.
    vertical_fov_deg: float = 58.
    width: int = 212
    height: int = 120
    min_range_m: float = .6
    max_range_m: float = 6.
    update_hz: float = 10.
    noise_stddev_m: float = .01

    def validate(self):
        if not all(math.isfinite(v) for v in asdict(self).values()):
            raise ValueError('camera values must be finite')
        if not all(isinstance(v, int) and v > 0 for v in (self.width, self.height)):
            raise ValueError('camera dimensions must be positive integers')
        if not (0 < self.horizontal_fov_deg < 180 and 0 < self.vertical_fov_deg < 180
                and 0 < self.min_range_m < self.max_range_m and self.update_hz > 0 and self.noise_stddev_m >= 0):
            raise ValueError('invalid depth camera specification')


REAL_MOUNTS = {
    'lidar': SensorMount((-.24, 0., 1.40)),
    'camera1': SensorMount((.40, .27, .76), (0., 0., .345)),
    'camera2': SensorMount((.40, -.27, .76), (0., 0., -.345)),
}


def sensor_configuration(mode):
    if mode not in SENSOR_MODES:
        raise ValueError('unknown sensor combination: '+str(mode))
    if mode == 'legacy':
        return None
    names = ('lidar', 'camera1', 'camera2') if mode.endswith('+depth2') else ('lidar',)
    return dict(preset='real_bunker', combination=mode,
                mounts={name: dict(asdict(REAL_MOUNTS[name]), base_link_xyz=REAL_MOUNTS[name].base_link_xyz,
                                  frame=name, point_axes='x_forward_y_left_z_up') for name in names},
                depth_camera_spec=asdict(DepthCameraSpec()) if len(names) > 1 else None,
                assumptions='D455 FOV/range/rate/noise/downsampled resolution are assumptions, not calibrated; no occlusion in coverage table')


def transform_sensor_points(points, pose, mount):
    points, pose = np.asarray(points, float), np.asarray(pose, float)
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError('points must be N x 3')
    if pose.shape != (6,) or not np.isfinite(pose).all():
        raise ValueError('pose requires finite model-origin xyz/roll/pitch/yaw')
    local = points @ Rotation.from_euler('xyz', mount.rpy).as_matrix().T + mount.xyz
    return local @ Rotation.from_euler('xyz', pose[3:]).as_matrix().T + pose[:3]
