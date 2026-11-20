"""Byte-for-byte replay of the task038 baseline without ROS or git history."""

import hashlib
import json
from pathlib import Path

import numpy as np

from tapp.pointcloud_map_fine import PointCloudMapFine
from tapp.pointcloud_map_multi import PointCloudMapMulti
from tapp.sensor_geometry import REAL_MOUNTS, transform_sensor_points
from scipy.spatial.transform import Rotation


ROOT = Path(__file__).resolve().parents[1]
SAVED = ROOT / 'results/real_sensors/b0b/lidar_real_depth2/physical_1/raw/08OB86_-0205'
SENSORS = ('lidar', 'camera1', 'camera2')


def local_cloud(world, pose, mount):
    body = (world-pose[:3]) @ Rotation.from_euler('xyz', pose[3:]).as_matrix()
    return (body-mount.xyz) @ Rotation.from_euler('xyz', mount.rpy).as_matrix()


def synthetic_cloud(sensor):
    # Same sensor sizes and geometry as the task036 synthetic timing fixture.
    rng = np.random.default_rng(36)
    pose = np.array([100., 100., 0., 0., 0., 0.])
    mount = REAL_MOUNTS[sensor]
    if sensor == 'lidar':
        angle = np.tile(np.linspace(-np.pi, np.pi, 1800, endpoint=False), 16)
        distance = np.repeat(np.linspace(4.2, 22., 16), 1800) + rng.normal(0., .08, len(angle))
        x, y = distance*np.cos(angle), distance*np.sin(angle)
        z = .02*x + .01*y
        z[(x > 8.) & (x < 9.) & (abs(y) < .5)] += .4
        world = np.column_stack((x+pose[0], y+pose[1], z))
        return local_cloud(world, pose, mount), pose
    x, slope = np.meshgrid(np.linspace(1.5, 4.1, 125), np.linspace(-.8, .8, 214))
    y = x*slope
    z = np.full(x.shape, -mount.xyz[2])
    z[(x > 2.) & (x < 2.5) & (abs(y) < .25)] += .4
    return np.column_stack((x.ravel(), y.ravel(), z.ravel())), pose


def replay(Fine=PointCloudMapFine, Multi=PointCloudMapMulti):
    rng = np.random.default_rng(103)
    x, y = np.indices((96, 102)) * .5
    terrain = .02*x + .02*np.sin(y) + .02*np.cos(x+y)
    rock = (x == 7) & (y < 8)
    for cls in (Fine, Multi):
        for ground in ('all_returns', 'non_obstacle'):
            for reference in ('prior', 'local'):
                mapper = cls(terrain, rock, ground_estimate=ground, obstacle_reference=reference)
                name = f'{cls.__name__}/{ground}/{reference}'
                for i, (px, py) in enumerate(((0, 0), (6, 6), (6, 6), (9, 6),
                                               (25, 25), (47, 50), (47, 50), (30, 10))):
                    pose = [px, py, 0., 0., 0., .12*i]
                    xy = rng.uniform(-3, 3, (1500, 2)) + [px, py]
                    z = .02*xy[:, 0] + .02*np.sin(xy[:, 1])
                    if i == 0:
                        z.fill(0.)
                    if i >= 3:
                        z[(abs(xy[:, 0]-px) < 1) & (abs(xy[:, 1]-py) < 1)] += .55
                    if i >= 5:
                        z += .45*(xy[:, 0]-px)
                    world = np.column_stack((xy, z))
                    if cls is Multi:
                        sensor = SENSORS[i % 3]
                        if sensor != 'lidar':
                            # Generate camera returns inside the actual frustum.
                            cloud = np.column_stack((rng.uniform(1.8, 4., 1500),
                                                     rng.uniform(-.6, .6, 1500),
                                                     rng.uniform(-.5, .5, 1500)))
                        else:
                            cloud = local_cloud(world, pose, REAL_MOUNTS[sensor])
                        mapper.update(cloud, pose, sensor=sensor, stamp=i*.1)
                    else:
                        cloud = world.copy()
                        cloud[:, :2] = (world[:, :2]-[px, py]) @ np.array(
                            [[np.cos(pose[5]), -np.sin(pose[5])],
                             [np.sin(pose[5]), np.cos(pose[5])]])
                        cloud[:, 2] -= .8
                        mapper.update(cloud, pose)
                    yield f'{name}/{i}', mapper
                mapper.update(np.empty((0, 3)), pose)
                yield f'{name}/empty', mapper

    for cls in (Fine, Multi):
        for ground in ('all_returns', 'non_obstacle'):
            for reference in ('prior', 'local'):
                mapper = cls(np.zeros((401, 401)), ground_estimate=ground,
                             obstacle_reference=reference)
                for i, (sensor, suffix) in enumerate(zip(SENSORS, ('', '_camera1', '_camera2'))):
                    if cls is Fine and i:
                        break
                    with np.load(SAVED / f'first_cloud{suffix}.npz') as scan:
                        points, pose = scan['points'], scan['pose']
                    if cls is Multi:
                        mapper.update(points, pose, sensor=sensor, stamp=i*.1)
                    else:
                        finite = np.isfinite(points).all(axis=1)
                        world = transform_sensor_points(points[finite], pose, REAL_MOUNTS[sensor])
                        mapper.update(world-[*pose[:2], .8], [*pose[:2], 0., 0., 0., 0.])
                    yield f'saved/{cls.__name__}/{ground}/{reference}/{sensor}', mapper


def digest(mapper):
    result = {}
    for name in ('elev', 'seen', 'lethal', 'fine_obstacle', 'fine_inflated',
                 'detected_obstacle', '_inflated_coarse'):
        result[name] = hashlib.sha256(getattr(mapper, name).tobytes()).hexdigest()
    for name, value in vars(mapper.tm).items():
        if isinstance(value, np.ndarray):
            result[f'tm.{name}'] = hashlib.sha256(value.tobytes()).hexdigest()
    for name in ('samples', '_fine_ids', '_source_history'):
        if hasattr(mapper, name):
            checksum = hashlib.sha256()
            for key, value in sorted(getattr(mapper, name).items()):
                checksum.update(int(key).to_bytes(8, 'little'))
                checksum.update(len(value).to_bytes(8, 'little'))
                checksum.update(value.tobytes())
            result[name] = checksum.hexdigest()
    result['version'] = mapper.version
    if hasattr(mapper, 'sensor_counts'):
        result['attribution'] = hashlib.sha256(json.dumps(
            [mapper.sensor_counts, mapper.first_detections], sort_keys=True).encode()).hexdigest()
    return result


def reference_classes():
    """Load the pre-038 implementation (copied byte for byte from 9b3b1ef) as a runtime reference.

    Stored hashes of float arrays (slope, cost, ...) depend on the platform's math library and
    CPU, so the same code can produce different bits on another machine. Comparing against the
    reference implementation run on the same machine keeps the byte-for-byte check strict and
    portable. The relative imports are redirected so the copies use each other, not the 038 code.
    """
    import importlib.util
    import sys
    loaded = {}
    for name in ('pointcloud_map_fine', 'local_ground', 'pointcloud_map_multi'):
        source = (ROOT/'tests/reference'/f'{name}_038base.py').read_text()
        for other in ('local_ground', 'pointcloud_map_fine'):
            source = source.replace(f'from .{other} import', f'from .{other}_038base import')
        full = f'tapp.{name}_038base'
        spec = importlib.util.spec_from_loader(full, loader=None)
        module = importlib.util.module_from_spec(spec)
        module.__package__ = 'tapp'
        sys.modules[full] = module
        exec(compile(source, f'{name}_038base.py', 'exec'), vars(module))
        loaded[name] = module
    return loaded['pointcloud_map_fine'].PointCloudMapFine, loaded['pointcloud_map_multi'].PointCloudMapMulti


def test_replay():
    expected = json.loads((ROOT / 'results/map_speed/expected.json').read_text())
    Fine, Multi = reference_classes()
    seen, stored_mismatch = set(), 0
    for (name, mapper), (reference_name, reference) in zip(replay(), replay(Fine, Multi)):
        assert name == reference_name
        actual, wanted = digest(mapper), digest(reference)
        assert actual == wanted, (name, [key for key in actual if actual[key] != wanted.get(key)])
        stored_mismatch += actual != expected[name]
        seen.add(name)
    assert seen == set(expected)
    print(f'byte-identical replay against the pre-038 implementation: {len(seen)} update states; '
          f'states differing from the hashes stored on the recording machine: {stored_mismatch}')


def benchmark_cases():
    x, y = np.indices((401, 401)) * .5
    terrain = .02*(x-100) + .01*(y-100) + .02*np.sin(x+y)
    for cls in (PointCloudMapFine, PointCloudMapMulti):
        for ground in ('all_returns', 'non_obstacle'):
            for sensor in (SENSORS if cls is PointCloudMapMulti else ('lidar',)):
                cloud, pose = synthetic_cloud(sensor)
                if cls is PointCloudMapFine:
                    world = transform_sensor_points(cloud, pose, REAL_MOUNTS[sensor])
                    cloud = world-[*pose[:2], .8]
                yield cls, ground, sensor, cloud, pose, terrain


if __name__ == '__main__':
    test_replay()
