"""Reproducible LiDAR replay fixtures with a flat or landmark-rich scene."""

import numpy as np
from scipy.spatial.transform import Rotation

from experiments.offline_localization import Recording
from tapp.sensor_geometry import REAL_MOUNTS

SYNTHETIC_SEED = 101
SCENES = ('landmarks', 'plane')
BOXES = (
    (1., -3.5, 1.4, 2.0, 1.8), (2.5, 4.5, 1.5, 1.1, 1.4),
    (5.5, -4.5, 1.3, 1.4, 2.1), (6., 4., 2., 1.3, 2.0),
    (9., -2.8, 1.4, 1.6, 1.6), (11.5, 3.8, 1.3, 1.1, 2.4),
    (14., -3., 1.7, 1.8, 1.9), (16., 4., 1.7, 1.2, 2.4),
    (19., -4., 1.5, 1.4, 2.0),
)


def height(x, y, landmarks):
    if not landmarks:
        return np.zeros_like(x)
    return .38*np.sin(.51*x+.33*y)+.25*np.cos(.62*y-.28*x)+.18*np.sin(.81*x-.82*y)


def surfaces(landmarks, step, phase):
    x, y = np.meshgrid(np.arange(-12.+phase, 29., step),
                       np.arange(-12.+phase, 12., step), indexing='ij')
    parts = [np.column_stack((x.ravel(), y.ravel(), height(x, y, landmarks).ravel()))]
    if landmarks:
        for cx, cy, width, depth, rise in BOXES:
            floor = height(cx, cy, True)-.25
            axes = [np.linspace(-width/2, width/2, int(np.ceil(width/step))+1)+cx,
                    np.linspace(-depth/2, depth/2, int(np.ceil(depth/step))+1)+cy,
                    np.linspace(floor, floor+rise, int(np.ceil(rise/step))+1)]
            # Four walls and the top. No hidden underside.
            for axis, side in ((0, 0), (0, -1), (1, 0), (1, -1), (2, -1)):
                grid_axes = list(axes)
                grid_axes[axis] = [axes[axis][side]]
                if phase:
                    for dim in set(range(3))-{axis}:
                        samples = axes[dim]
                        grid_axes[dim] = samples[:-1]+phase*np.diff(samples)/step
                vertices = np.meshgrid(*grid_axes, indexing='ij')
                parts.append(np.column_stack([a.ravel() for a in vertices]))
    return np.concatenate(parts)


def scan_at(surface, world_from_lidar, rng):
    local = (surface-world_from_lidar[:3, 3]) @ world_from_lidar[:3, :3]
    radius = np.linalg.norm(local, axis=1)
    elevation = np.arctan2(local[:, 2], np.hypot(local[:, 0], local[:, 1]))
    valid = (radius >= .1) & (radius <= 11.) & (abs(elevation) < np.pi/4)
    local, radius, elevation = local[valid], radius[valid], elevation[valid]
    heading = np.arctan2(local[:, 1], local[:, 0])
    # Keep the nearest visible sample in each 0.5° azimuth × 1.875° elevation bin.
    bins = np.floor((heading+np.pi)*720/(2*np.pi)).astype(int)
    bins = bins % 720 + 720*np.floor((elevation+np.pi/4)*48/(np.pi/2)).astype(int)
    order = np.lexsort((radius, bins))
    _, first = np.unique(bins[order], return_index=True)
    indices = order[first]
    indices = indices[rng.random(len(indices)) >= .05]
    scale = 1+rng.normal(0., .01, len(indices))/radius[indices]
    return local[indices]*scale[:, None]


def synthetic_recording(scene='landmarks', seed=SYNTHETIC_SEED):
    if scene not in SCENES:
        raise ValueError(f'unknown synthetic scene: {scene}')
    landmarks = scene == 'landmarks'
    rng = np.random.default_rng(seed)
    base_from_lidar = np.eye(4)
    base_from_lidar[:3, 3] = REAL_MOUNTS['lidar'].base_link_xyz
    x = np.linspace(0, 16, 65)
    t = x/2.5
    y = .6*np.sin(.45*x)
    truth = np.repeat(np.eye(4)[None, :, :], len(x), axis=0)
    truth[:, :3, 3] = np.column_stack((x, y, .35+height(x, y, landmarks)))
    truth[:, :3, :3] = Rotation.from_euler('z', np.arctan(.27*np.cos(.45*x))[:, None]).as_matrix()
    scene_surface = surfaces(landmarks, step=.14, phase=.05)
    scans = [scan_at(scene_surface, pose @ base_from_lidar, rng) for pose in truth]
    stamps_ns = np.rint(t*1e9).astype(np.int64)
    return Recording(stamps_ns, truth, scans, base_from_lidar), surfaces(landmarks, step=.12, phase=0.)
