"""Offline checks for deterministic worlds, reference points and sensor capture."""

from dataclasses import asdict
import json
import math
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace as S
from unittest.mock import patch
import xml.etree.ElementTree as ET

import numpy as np

from experiments.eval_runs import cell_metrics, reference_data
from ros2_jazzy.gz_checks import lidar_checks, sensor_recorder
from ros2_jazzy.gz_checks.clearance_log import save_debris_footprints
from ros2_jazzy.gz_checks.landmark_sdf import add_landmark_models
from ros2_jazzy.gz_checks.terrain_mesh import write_terrain_obj
from tapp.mapfile import load_map_file, scenario_to_mapfile
from tapp.landmark_world import Landmark, landmark_mask, place_landmarks, save_reference_cloud, with_landmarks
from tapp.sensor_recording import IMU_COLUMNS, SensorArchive, iter_lidar, pack_lidar, unpack_lidar
from tapp.traversability import TraversabilityMap
from tests import test_overlap_goal as baseline
from tests import test_waypoint_feasibility as launcher
from tests.test_pose_error import header, truth

BASE = 'fee31da7'
SURFACE_TOL_M = .00005


def scenario(elevation, *, rock=None, water=None, nodata=None):
    z = np.asarray(elevation, dtype=float)
    rock, water, nodata = (np.zeros(z.shape, bool) if mask is None else mask for mask in (rock, water, nodata))
    return dict(tmap=TraversabilityMap(z, rock | water | nodata), start=(5, 5),
                terrain=dict(rock=rock, water=water, nodata=nodata))


def test_default(root):
    with patch.object(baseline, 'BASE', BASE):
        before, = baseline.load_before(lidar_checks)

    def run(module, name, **options):
        out = root/name
        dispatch = launcher.capture_launch(module, out, **options)
        files = {p.relative_to(out): p.read_bytes() for p in out.rglob('*') if p.is_file()}
        return dispatch, files

    for mode in ('coarse', 'fine'):
        options = dict(map_method=mode, pose_trace=True, pose_error='bias', pose_error_bias=(.2, .4, 0.))
        expected = run(before, f'{mode}-old', **options)
        assert run(lidar_checks, f'{mode}-default', **options) == expected
        assert run(lidar_checks, f'{mode}-explicit', landmarks=0, record_sensors=False, **options) == expected
    assert run(before, 'old-bare') == run(lidar_checks, 'new-bare')
    print('1 PASS: same-host previous/default bytes for full mocked output trees, launch and dispatch')


def test_placement():
    z = np.zeros((220, 204))
    z[70:95] = np.arange(25)[:, None] * .3
    water = np.indices(z.shape)[0] < 15
    nodata = np.indices(z.shape)[1] < 8
    debris = np.zeros(z.shape, bool)
    debris[101:108, 26:34] = True
    model = scenario(z, water=water, nodata=nodata, rock=debris)
    endpoints = [(15, 90), (101, 149), (155, 175)]
    area, objects = place_landmarks(model, 'beach', 160, 42, endpoints)
    assert area == (220-15)*(204-8)*.25
    assert len(objects) == math.floor(160*area/10_000+.5)
    assert abs(2*sum(obj.shape == 'box' for obj in objects) - len(objects)) <= 1
    assert place_landmarks(model, 'beach', 160, 42, endpoints) == (area, objects)
    assert place_landmarks(model, 'beach', 40, 42, endpoints)[1] == objects[:40]
    assert place_landmarks(model, 'beach', 160, 43, endpoints)[1] != objects
    assert place_landmarks(model, 'other', 160, 42, endpoints)[1] != objects
    assert place_landmarks(model, 'beach', 0, 42, endpoints) == (area, [])
    for index, item in enumerate(objects):
        assert .4 <= item.width_m <= 1.5 and .4 <= item.depth_m <= 1.5
        assert .3 <= item.height_m <= 1.2 and -math.pi <= item.yaw_rad <= math.pi
        xy = (item.x_m, item.y_m)
        for endpoint in endpoints:
            assert math.dist(xy, np.asarray(endpoint)*.5)-item.radius_m >= 2.
        for other in objects[:index]:
            assert math.dist(xy, (other.x_m, other.y_m))-item.radius_m-other.radius_m >= 1.
    mask = landmark_mask(z.shape, objects)
    assert mask.any() and not (mask & (water | nodata | model['tmap'].steep | debris)).any()
    print(f'2 PASS: {len(objects)} landmarks over {area:.0f} m², density, seed, nested positions and gaps')


def test_known_masks(root):
    z = np.zeros((40, 40))
    debris = np.zeros(z.shape, bool)
    debris[29, 26] = True
    bare, full = scenario(z), scenario(z, rock=debris)
    rock = Landmark('landmark_1', 'box', 6., 7., 0., .6, .9, .5, .83)
    mask = landmark_mask(z.shape, [rock])
    known, current = with_landmarks(bare, mask), with_landmarks(full, mask)
    output = root/'prior.npz'
    scenario_to_mapfile(known, output, 'prior', 'test', 'test', '')
    prior = load_map_file(output)
    np.testing.assert_array_equal(prior['obstacle'], mask)
    assert prior['tmap'].lethal[12, 14] and not bare['tmap'].lethal[12, 14]
    assert not full['terrain']['rock'][12, 14]
    np.savez_compressed(root/'evaluation_reference.npz', truth_elev=z,
                        truth_rock=current['tmap'].rock, truth_lethal=current['tmap'].lethal,
                        prior_rock=prior['tmap'].rock)
    _, ref = reference_data(root, None, '')
    np.testing.assert_array_equal(ref['truth_rock'] & ~ref['prior_rock'], full['tmap'].rock)
    through_landmark = cell_metrics(np.array([[4., 7.], [8., 7.]]), ref)
    through_debris = cell_metrics(np.array([[13., 13.], [14.5, 13.], [16., 13.]]), ref)
    assert through_landmark['debris_entries'] == through_landmark['debris_len_m'] == 0
    assert through_landmark['lethal_cells'] and through_debris['debris_entries'] == 1
    print('3 PASS: serialized prior blocks landmarks, evaluation counts debris but excludes known landmarks')


def test_reference(root):
    z = np.array([[.12467, .01, .12], [.1, .46, .34], [.25, .67, .8]])
    box = Landmark('landmark_1', 'box', .25, .6, .17, .4, .53, .43, .83)
    tube = Landmark('landmark_2', 'cylinder', .7, .2, .32, .6, .6, .68, -1.3)
    objects = [box, tube]
    world = ET.Element('world')
    add_landmark_models(world, objects)
    assert world.findall('model/static')[0].text == 'true'
    assert world.find('model[@name="landmark_1"]/link/collision/geometry/box/size').text == '0.4 0.53 0.43'
    assert world.find('model[@name="landmark_2"]/link/visual/geometry/cylinder/radius').text == '0.3'
    footprints = root/'footprints.csv'
    save_debris_footprints(footprints, world)
    assert len(footprints.read_text().splitlines()) == 1

    obj_file = write_terrain_obj(z, root/'terrain.obj')
    rows = [line.split() for line in obj_file.read_text().splitlines()]
    vertices = np.array([row[1:] for row in rows if row[0] == 'v'], dtype=float)
    triangles = np.array([row[1:] for row in rows if row[0] == 'f'], dtype=int)-1
    path = root/'reference_cloud.npz'
    n_ground, n_objects = save_reference_cloud(path, z, objects)
    with np.load(path, allow_pickle=False) as cloud:
        xyz, kind = cloud['xyz'], cloud['kind']
        assert n_ground == 121 and len(xyz) == n_ground+n_objects
        np.testing.assert_allclose(xyz[kind == 0, :2]*10, np.rint(xyz[kind == 0, :2]*10), atol=1e-6)
        for x, y, h in xyz[kind == 0]:
            face_heights = []
            for triangle in vertices[triangles]:
                weights = np.linalg.solve(np.c_[triangle[:, :2], np.ones(3)].T, [x, y, 1])
                if np.min(weights) >= -1e-7:
                    face_heights.append(weights @ triangle[:, 2])
            assert face_heights and min(abs(h-v) for v in face_heights) < SURFACE_TOL_M
        distances = []
        for item in objects:
            local = xyz[kind == 1]-[item.x_m, item.y_m, item.bottom_z_m]
            cap = np.minimum(np.abs(local[:, 2]), np.abs(local[:, 2]-item.height_m))
            if item.shape == 'box':
                c, s = np.cos(item.yaw_rad), np.sin(item.yaw_rad)
                xy = np.abs(local[:, :2] @ [[c, -s], [s, c]])
                side = xy - [item.width_m/2, item.depth_m/2]
            else:
                side = (np.linalg.norm(local[:, :2], axis=1)-item.radius_m)[:, None]
            h_ok = (local[:, 2] >= -SURFACE_TOL_M) & (local[:, 2] <= item.height_m+SURFACE_TOL_M)
            within = h_ok & (side.max(axis=1) <= SURFACE_TOL_M)
            hits = within & (np.minimum(cap, np.abs(side).min(axis=1)) < SURFACE_TOL_M)
            distances.append(hits)
        assert all(hits.any() for hits in distances) and np.logical_or.reduce(distances).all()
    print(f'4 PASS: terrain triangles and both static surfaces agree with XYZ within {SURFACE_TOL_M} m')


def full_scans(seed, scans=4):
    rng = np.random.default_rng(seed)
    azimuth = np.linspace(-np.pi, np.pi, 1800)[None, :]
    pitch = np.deg2rad(np.linspace(-15, 15, 16))[:, None]
    rays = np.stack(np.broadcast_arrays(np.cos(pitch)*np.cos(azimuth), np.cos(pitch)*np.sin(azimuth),
                                        np.sin(pitch)), axis=-1)
    ranges = rng.uniform(.9, 30, size=(scans, 16, 1800))
    return (rays * ranges[..., None]).astype(np.float32)


def test_codec():
    scan = full_scans(75)
    scan[0, 1, 4] = np.nan
    scan[1, 2, 7] = [0., np.nan, np.inf]
    scan[2, 3, 6] = [100., 0., 0.]
    scan[2, 4, 6] = np.roll(scan[2, 4, 6], 1)
    scan[3, 9, 17] = 0.
    scan[3, 8, 4] = [np.inf, -np.inf, np.nan]
    data = pack_lidar(scan)
    decoded = unpack_lidar(data)
    assert data['ranges_mm'].dtype == np.uint16
    assert data['ranges_mm'].shape == (4, 16, 1800)
    assert len(data['exception_indices']) == 3
    nonfinite = ~np.isfinite(scan).all(axis=-1)
    np.testing.assert_array_equal(scan[nonfinite], decoded[nonfinite])
    error = np.linalg.norm(scan[~nonfinite]-decoded[~nonfinite], axis=-1).max()
    assert error <= .001
    assert unpack_lidar(pack_lidar(np.empty((1, 1, 0, 3)))).shape == (1, 1, 0, 3)
    print(f'5 PASS: {error*1000:.6f} mm maximum Euclidean error, exceptions and empty scan preserved')


def stub_recording(name):
    positions = {}

    class Node:
        def __init__(self, name):
            pass

        def create_subscription(self, _, topic, callback, qos):
            positions[topic] = callback

        def destroy_node(self):
            pass

    class Shutdown(Exception):
        pass

    def spin(node):
        q = S(x=.1, y=.2, z=.3, w=.9)
        v = S(x=1., y=2., z=3.)
        cov = [float(i) for i in range(9)]
        positions['/imu'](S(header=header(.105), orientation=q, angular_velocity=v, linear_acceleration=v,
                            orientation_covariance=cov, angular_velocity_covariance=cov, linear_acceleration_covariance=cov))
        positions['/ground_truth'](S(poses=[]))
        positions['/ground_truth'](truth(.11, 4., 5.))
        assert set(positions) == {'/imu', '/ground_truth', '/lidar/points'}
        data = np.asarray([[[.0, 3.001, 0., 5.], [.0, 4.443, .0, 5.]]], dtype='>f4')
        positions['/lidar/points'](S(header=header(.12), width=2, height=1, point_step=16,
                                     row_step=40, is_bigendian=True, data=data.tobytes()+b'padding!',
                                     fields=[S(name=a, offset=4*i, datatype=7, count=1) for i, a in enumerate('xyz')]))
        positions['/ground_truth'](truth(1.11, 9., 10.))
        raise Shutdown

    stubs = {'rclpy': S(init=lambda **kw: None, spin=spin, try_shutdown=lambda: None),
             'rclpy.node': S(Node=Node), 'rclpy.executors': S(ExternalShutdownException=Shutdown),
             'rclpy.qos': S(QoSProfile=S, ReliabilityPolicy=S(BEST_EFFORT=1)),
             'geometry_msgs.msg': S(PoseArray=object), 'sensor_msgs.msg': S(Imu=object, PointCloud2=object)}
    with patch.dict(sys.modules, stubs), patch.object(sys, 'argv', ['sensor_recorder', str(name), '--seconds', '1']):
        sensor_recorder.main()


def test_archive(root):
    folder = root/'sensors'
    stub_recording(folder)
    metadata = json.loads((folder/'metadata.json').read_text())
    assert metadata['status'] == 'duration_limit'
    assert metadata['begin_ns'] == 105_000_000 and metadata['end_ns'] == 120_000_000
    assert metadata['saved'] == dict(imu=1, ground_truth=1, lidar=1)
    assert metadata['empty_ground_truth'] == 1
    scan, = iter_lidar(folder)
    assert scan.stamp_ns == 120_000_000 and scan.frame_id == 'map'
    np.testing.assert_allclose(scan.xyz, [[[0, 3.001, 0], [0, 4.443, 0]]], atol=.001)
    with np.load(folder/'chunk_00000.npz', allow_pickle=False) as saved:
        assert saved['imu_values'].shape == (1, len(IMU_COLUMNS))
        np.testing.assert_array_equal(saved['imu_values'][0, :4], [.1, .2, .3, .9])
        np.testing.assert_array_equal(saved['imu_values'][0, -9:], np.arange(9))
        np.testing.assert_array_equal(saved['ground_truth_values'], [[4., 5., 0., 0., 0., 0., 1.]])
    cap = 5_000
    limited = SensorArchive(root/'capped', limit_bytes=cap)
    limited.add('imu', 0, 'imu', (0.,)*len(IMU_COLUMNS))
    limited.flush()
    limited.add('lidar', 10, 'lidar', full_scans(75, 1)[0])
    limited.close()
    status = json.loads((limited.folder/'metadata.json').read_text())
    assert status['status'] == 'byte_limit' and status['saved']['lidar'] == 0
    assert sum(p.stat().st_size for p in limited.folder.iterdir()) <= cap
    assert list(limited.folder.glob('*.npz')) == [limited.folder/'chunk_00000.npz']
    print('capture PASS: original ROS topics/stamps, endian/row padding, cutoff and strict byte cap')


def test_opt_in_dispatch(root):
    sc = scenario(np.zeros((100, 100)))
    objects = [Landmark('landmark_1', 'cylinder', 24., 24., 0., 1., 1., .5, .3)]
    first = launcher.archive_scenarios()[0]
    first.update(start=[5, 5], points=[[8, 8]], stops=[[8, 8], [5, 5]],
                 initial_path=[[2.5, 2.5], [4., 4.], [2.5, 2.5]], order=[0, 1], fixed_plan_times=[])
    cases = launcher.archive_scenarios()
    cases[0] = first
    actual_place = lidar_checks.add_landmark_world

    def world(raw, case, meta, settings, actual, prior):
        result = actual_place(raw, case, meta, settings, actual, prior)
        stub_recording(raw/'sensors')  # Substitute the optional recorder child.
        return result

    with patch.object(launcher, 'fixture', return_value=sc), patch.object(launcher, 'trial_scenarios', return_value=cases), \
            patch('tapp.landmark_world.place_landmarks', return_value=(2500., objects)), \
            patch.object(lidar_checks, 'add_landmark_world', side_effect=world):
        raw_manifest, _, _, commands = launcher.capture_launch(
            lidar_checks, root, map_method='fine', landmarks=160, landmark_seed=75,
            record_sensors=True, record_sensors_seconds=1., pose_error='bias', pose_error_bias=(.2, .4, 0.))
    manifest = json.loads(raw_manifest)
    case = manifest['cases'][0]
    assert case['landmarks'] == [asdict(objects[0])]
    assert case['reference_cloud']['landmark_points'] > 0
    assert case['sensor_recording']['status'] == 'duration_limit' and not case['error']
    assert commands[-2][1].endswith('/pose_error_relay.py')
    assert commands[-1][1].endswith('/sensor_recorder.py') and commands[-1][-2:] == ['--seconds', '1.0']
    assert commands[-1][2].endswith('/sensors')
    print('dispatch PASS: world, reference, manifest and separate truth-only recorder alongside pose error')


def main():
    with TemporaryDirectory() as temp:
        root = Path(temp)
        test_default(root)
        test_placement()
        test_known_masks(root)
        test_reference(root)
        test_codec()
        test_archive(root)
        test_opt_in_dispatch(root/'dispatch')
    print('all landmark world tests passed')


if __name__ == '__main__':
    main()
