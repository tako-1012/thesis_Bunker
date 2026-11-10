"""Opt-in depth sensors; let horizontal FOV and image aspect set projection."""

import math
import xml.etree.ElementTree as ET
from tapp.sensor_geometry import DepthCameraSpec, SensorMount


def add_depth_camera(body, *, name, mount, spec=DepthCameraSpec()):
    spec.validate()
    if name not in ('camera1', 'camera2'):
        raise ValueError('camera must have a unique camera1/camera2 name')
    def node(parent, tag, text=None, **attrs):
        result = ET.SubElement(parent, tag, attrs)
        if text is not None:
            result.text = str(text)
        return result
    sensor = node(body, 'sensor', name=name, type='depth_camera')
    node(sensor, 'pose', ' '.join(f'{v:.17g}' for v in (*mount.base_link_xyz, *mount.rpy)))
    node(sensor, 'always_on', 'true')
    node(sensor, 'update_rate', spec.update_hz)
    node(sensor, 'topic', '/'+name)
    node(sensor, 'gz_frame_id', name)
    camera = node(sensor, 'camera')
    node(camera, 'horizontal_fov', math.radians(spec.horizontal_fov_deg))
    image = node(camera, 'image')
    node(image, 'width', spec.width)
    node(image, 'height', spec.height)
    node(image, 'format', 'R_FLOAT32')
    clip = node(camera, 'clip')
    node(clip, 'near', spec.min_range_m)
    node(clip, 'far', spec.max_range_m)
    noise = node(camera, 'noise', type='gaussian')
    node(noise, 'mean', 0.)
    node(noise, 'stddev', spec.noise_stddev_m)
    return sensor
