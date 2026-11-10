"""VLP-16-like Gazebo scan geometry; sampling/noise/range are declared assumptions."""

from dataclasses import asdict, dataclass
import math
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class LidarSpec:
    vertical_samples: int = 16
    vertical_min_deg: float = -15.
    vertical_max_deg: float = 15.
    horizontal_samples: int = 1800
    update_hz: float = 10.
    min_range_m: float = .1
    max_range_m: float = 30.
    noise_stddev_m: float = .02
    range_resolution_m: float = .01

    def validate(self):
        if not isinstance(self.vertical_samples, int) or self.vertical_samples < 2:
            raise ValueError('at least two vertical channels required')
        if not isinstance(self.horizontal_samples, int) or self.horizontal_samples < 2:
            raise ValueError('at least two horizontal samples required')
        if not all(math.isfinite(v) for v in asdict(self).values()):
            raise ValueError('LiDAR values must be finite')
        if not -90 <= self.vertical_min_deg < self.vertical_max_deg <= 90:
            raise ValueError('invalid vertical field of view')
        if (self.update_hz <= 0 or not 0 <= self.min_range_m < self.max_range_m or self.noise_stddev_m < 0
                or not 0 < self.range_resolution_m < self.max_range_m-self.min_range_m):
            raise ValueError('invalid rate/range/noise')


def add_lidar(body, *, sensor_height_m=.8, spec=LidarSpec(), sensor_xyz=None, sensor_rpy=(0., 0., 0.)):
    spec.validate()
    if not math.isfinite(sensor_height_m) or sensor_height_m <= 0:
        raise ValueError('sensor height must be positive')
    def node(parent, tag, text=None, **attrs):
        result = ET.SubElement(parent, tag, attrs)
        if text is not None:
            result.text = str(text)
        return result
    sensor = node(body, 'sensor', name='lidar', type='gpu_lidar')
    if sensor_xyz is None and sensor_rpy == (0., 0., 0.):
        pose = f'0 0 {sensor_height_m-.35:.17g} 0 0 0'
    else:
        from tapp.sensor_geometry import SensorMount
        mount = SensorMount((0., 0., sensor_height_m) if sensor_xyz is None else tuple(sensor_xyz), tuple(sensor_rpy))
        pose = ' '.join(f'{v:.17g}' for v in (*mount.base_link_xyz, *mount.rpy))
    node(sensor, 'pose', pose)
    node(sensor, 'always_on', 'true')
    node(sensor, 'update_rate', spec.update_hz)
    node(sensor, 'topic', '/lidar')
    node(sensor, 'gz_frame_id', 'lidar')
    lidar = node(sensor, 'lidar')
    scan = node(lidar, 'scan')
    horizontal = node(scan, 'horizontal')
    for name, value in [('samples', spec.horizontal_samples), ('resolution', 1),
                        ('min_angle', -math.pi), ('max_angle', math.pi)]:
        node(horizontal, name, value)
    vertical = node(scan, 'vertical')
    for name, value in [('samples', spec.vertical_samples), ('resolution', 1),
                        ('min_angle', math.radians(spec.vertical_min_deg)),
                        ('max_angle', math.radians(spec.vertical_max_deg))]:
        node(vertical, name, value)
    ranges = node(lidar, 'range')
    for name, value in [('min', spec.min_range_m), ('max', spec.max_range_m), ('resolution', spec.range_resolution_m)]:
        node(ranges, name, value)
    noise = node(lidar, 'noise', type='gaussian')
    node(noise, 'mean', 0.)
    node(noise, 'stddev', spec.noise_stddev_m)
    return sensor
