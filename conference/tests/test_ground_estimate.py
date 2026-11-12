"""Task029: ground-only medians, immutable obstacle evidence and legacy bytes."""

import ast
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np

from tapp.config import RESOLUTION
from tapp.footprint import inflate_steep
from tapp.pointcloud_map_fine import PointCloudMapFine
from tapp.pointcloud_map_multi import PointCloudMapMulti
from tapp.sensor_geometry import REAL_MOUNTS
from tapp.traversability import TraversabilityMap
from ros2_jazzy.gz_checks.lidar_map import make_pointcloud_map
from tests.test_real_sensors import local_cloud

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT/'results/ground_estimate/verification/legacy_bytes.json'
BOX_CELL = (10, 10)
NEIGHBOURS = [(9, 10), (11, 10), (10, 9), (10, 11)]


def box_world(top_points=3):
    ground = [[x*RESOLUTION, y*RESOLUTION, 0.]
              for x in range(9, 12) for y in range(9, 12) if (x, y) != BOX_CELL]
    return np.asarray(ground+[[5., 5., .55]]*top_points)


def update_world(mapper, world):
    pose = np.array([2., 2., 0., 0., 0., 0.])
    return mapper.update(np.asarray(world)-pose[:3]-[0., 0., .8], pose)


def checksum(data):
    return hashlib.sha256(data).hexdigest()


def legacy_output_bytes(folder, ground_estimate=None):
    """Run the same deterministic updates before/after the implementation."""
    folder = Path(folder)
    result = {}
    options = {} if ground_estimate is None else dict(ground_estimate=ground_estimate)
    for mode in ('fine', 'lidar_real', 'lidar_real+depth2'):
        mapper = (PointCloudMapFine(np.zeros((32, 32)), **options) if mode == 'fine' else
                  PointCloudMapMulti(np.zeros((32, 32)), sensors=mode, **options))
        updates = []
        with patch('time.perf_counter', return_value=1.):
            if mode == 'fine':
                clouds = [box_world(), np.array([[5., 5., .1]]*7+[[5., 5., .55]]*70),
                          np.array([[5., 5., .2]]*4), np.empty((0, 3))]
                updates = [update_world(mapper, cloud) for cloud in clouds]
            else:
                pose = np.array([2., 5., 0., 0., 0., 0.])
                for i, (name, mount) in enumerate(mapper.mounts.items()):
                    updates.append(mapper.update(local_cloud(box_world(), pose, mount), pose,
                                                 sensor=name, stamp=float(i+1)))
        path = folder/(mode+'.npz')
        mapper.save(path)
        result[mode] = dict(updates=json.dumps(updates, sort_keys=True),
                            npz_sha256=checksum(path.read_bytes()),
                            snapshot_sha256=[checksum(a.tobytes()) for a in mapper.snapshot()],
                            history={str(k): checksum(v.tobytes()) for k, v in mapper.samples.items()},
                            fine_ids={str(k): checksum(v.tobytes()) for k, v in mapper._fine_ids.items()})
        if mode != 'fine':
            result[mode]['sensor_sidecar_sha256'] = checksum(Path(str(path)+'.sensors.json').read_bytes())
    return result


def test_legacy_bytes():
    expected = json.loads(REFERENCE.read_text())
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for policy in (None, 'all_returns'):
            assert legacy_output_bytes(root, policy) == expected['mapping'], policy
    print('1 PASS: implicit/explicit all_returns match pre-change update JSON, snapshots, histories, NPZ and multi-sensor sidecar bytes')


def test_box():
    mappers = {name: PointCloudMapFine(np.zeros((32, 32)), ground_estimate=name)
               for name in ('all_returns', 'non_obstacle')}
    rows = []
    for name, mapper in mappers.items():
        update_world(mapper, box_world())
        assert mapper.detected_obstacle[BOX_CELL] and mapper.lethal[BOX_CELL]
        terrain = TraversabilityMap(mapper.elev, mapper.raw_obstacle, mapper.robot, mapper.weights)
        assert np.array_equal(mapper.tm.cost, terrain.cost)
        assert np.array_equal(mapper.lethal, inflate_steep(terrain) | mapper._inflated_coarse)
        for cell in NEIGHBOURS:
            slope = float(mapper.tm.slope[cell])
            assert (slope > mapper.robot.max_slope_deg if name == 'all_returns' else slope < 5.), (name, cell, slope)
            rows.append(dict(ground_estimate=name, x=cell[0], y=cell[1], slope_deg=slope,
                             steep=bool(mapper.tm.steep[cell]), box_lethal=bool(mapper.lethal[BOX_CELL])))
    old, new = mappers.values()
    assert np.isclose(old.elev[BOX_CELL], .55) and new.elev[BOX_CELL] == new.prior[BOX_CELL]
    for attribute in ('fine_obstacle', 'fine_inflated', 'detected_obstacle', '_inflated_coarse', 'seen'):
        assert np.array_equal(getattr(old, attribute), getattr(new, attribute)), attribute
    for key in old.samples:
        assert np.array_equal(old.samples[key], new.samples[key])
        assert np.array_equal(old._fine_ids[key], new._fine_ids[key])
    print('2 PASS: 0.55m box creates false steep neighbours only with all_returns; box detection/inflation and all evidence unchanged')
    print('ground_estimate x y slope_deg steep box_lethal')
    for row in rows:
        print(row['ground_estimate'], row['x'], row['y'], repr(row['slope_deg']), row['steep'], row['box_lethal'])
    return rows


def test_top_only_and_history():
    prior = np.full((32, 32), 1.25)
    mapper = PointCloudMapFine(prior, ground_estimate='non_obstacle')
    update_world(mapper, [[5., 5., 1.45]]*64)
    assert np.isclose(mapper.elev[BOX_CELL], 1.45)
    update_world(mapper, [[5., 5., 1.8]]*64)
    assert mapper.elev[BOX_CELL] == prior[BOX_CELL]  # Not the previous 1.45m estimate.
    assert mapper.seen[BOX_CELL] and mapper.detected_obstacle[BOX_CELL]
    key = np.ravel_multi_index(BOX_CELL, prior.shape)
    assert len(mapper.samples[key]) == 64 and np.all(mapper.samples[key][:, 1] >= .3)
    update_world(mapper, [[5., 5., 1.35]]*3)
    assert np.isclose(mapper.elev[BOX_CELL], 1.35)
    assert len(mapper.samples[key]) == 64
    assert np.count_nonzero(mapper.samples[key][:, 1] < .3) == 3
    update_world(mapper, [[5., 5., 1.8]]*64)
    assert mapper.elev[BOX_CELL] == prior[BOX_CELL]
    assert mapper.detected_obstacle[BOX_CELL]  # Persistent detection is unchanged.
    assert np.array_equal(mapper.prior, prior)
    print('3 PASS: all-excluded cells retain prior height and seen status; last-64 ALL returns displace older ground, then ground observations resume')


def test_low_changes_bilinear_and_threshold():
    mapper = PointCloudMapFine(np.zeros((32, 32)), ground_estimate='non_obstacle')
    update_world(mapper, [[x*.5, y*.5, .2] for x in range(8, 13) for y in range(8, 13)])
    assert np.allclose(mapper.elev[8:13, 8:13], .2) and not mapper.detected_obstacle.any()
    # Off-centre point: 0.35m above the cell-centre prior, but only 0.27m
    # above its bilinear prior. The latter is the existing obstacle rule.
    prior = np.indices((32, 32))[0]*RESOLUTION*.4
    mapper = PointCloudMapFine(prior, ground_estimate='non_obstacle')
    update_world(mapper, [[5.2, 5., 2.35]]*3+[[5.2, 5., 2.39]]*3)
    assert np.isclose(mapper.elev[BOX_CELL], 2.35)
    assert mapper.detected_obstacle[BOX_CELL]
    flat = PointCloudMapFine(np.zeros((32, 32)), ground_estimate='non_obstacle')
    update_world(flat, [[5., 5., .299]]*3+[[5., 5., .3]]*3)
    values = flat.samples[np.ravel_multi_index(BOX_CELL, flat.prior.shape)]
    assert np.count_nonzero(values[:, 1] < .3) == 3
    assert np.count_nonzero(values[:, 1] >= .3) == 3
    assert np.isclose(flat.elev[BOX_CELL], .299) and flat.detected_obstacle[BOX_CELL]
    print('4 PASS: sub-0.3m terrain changes retained; bilinear prior and the unchanged >=0.3m obstacle boundary used')


def test_multi():
    pose = np.array([2., 5., 0., 0., 0., 0.])
    mappers = {name: PointCloudMapMulti(np.zeros((32, 32)), ground_estimate=name)
               for name in ('all_returns', 'non_obstacle')}
    for mapper in mappers.values():
        for i, sensor in enumerate(('lidar', 'camera1', 'camera2')):
            world = box_world(2 if sensor == 'lidar' else 1)
            result = mapper.update(local_cloud(world, pose, REAL_MOUNTS[sensor]), pose, sensor=sensor, stamp=float(i+1))
            assert result['accepted_points'] == len(world)
        assert mapper.detected_obstacle[BOX_CELL] and mapper.lethal[BOX_CELL]
        first = mapper.first_detections[0]
        assert first['triggering_sensor'] == 'camera1'
        assert first['supporting_returns'] == dict(lidar=2, camera1=1, camera2=0)
    old, new = mappers.values()
    assert old.sensor_counts == new.sensor_counts and old.first_detections == new.first_detections
    assert np.array_equal(old.fine_obstacle, new.fine_obstacle)
    for cell in NEIGHBOURS:
        assert old.tm.slope[cell] > old.robot.max_slope_deg
        assert new.tm.slope[cell] < 5.
    for key in old.samples:
        assert np.array_equal(old.samples[key], new.samples[key])
        assert np.array_equal(old._source_history[key], new._source_history[key])
    print('5 PASS: LiDAR+two cameras share unchanged 2+1 detection evidence, source attribution and filtering; ground-only median removes false steep cells')


def test_configuration():
    from ros2_jazzy.gz_checks import lidar_checks
    expected = json.loads(REFERENCE.read_text())
    configurations = [('coarse', {}), ('fine', dict(map_method='fine')),
                      ('lidar_real', dict(map_method='fine', sensors='lidar_real')),
                      ('lidar_real+depth2', dict(map_method='fine', sensors='lidar_real+depth2'))]
    with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ):
        for key in ('THESIS_FINE_PROTOCOL', 'THESIS_ONLY_PATCH', 'THESIS_REAL_TIME_FACTOR', 'THESIS_STALE_TIMEOUT_S'):
            os.environ.pop(key, None)
        root = Path(temporary)
        for name, options in configurations:
            for explicit in (False, True):
                folder = root/(name+str(explicit))
                kwargs = dict(options, **(dict(ground_estimate='all_returns') if explicit else {}))
                manifest = lidar_checks.prepare_cases(folder, **kwargs)
                recorded = expected['manifests'][name]
                if manifest['input_environment'] == expected['environment']:
                    assert checksum((folder/'manifest.json').read_bytes()) == recorded['full_sha256']
                manifest['input_environment'] = {}
                assert checksum((json.dumps(manifest, ensure_ascii=False, indent=2)+'\n').encode()) == recorded['without_environment_sha256']
            if name != 'coarse':
                selected = lidar_checks.prepare_cases(root/(name+'ground'), ground_estimate='non_obstacle', **options)
                assert selected['ground_estimate'] == 'non_obstacle'
                assert 'bilinear' in selected['height_definition'] and '0.3' in selected['height_definition']
                mapper = make_pointcloud_map(np.zeros((12, 12)), ground_estimate='non_obstacle', **options)
                assert mapper.ground_estimate == 'non_obstacle'
        for kwargs in (dict(map_method='coarse', ground_estimate='non_obstacle'), dict(ground_estimate='invalid')):
            for create in (lambda: make_pointcloud_map(np.zeros((12, 12)), **kwargs),
                           lambda: lidar_checks.prepare_cases(root/'invalid', **kwargs)):
                try:
                    create()
                except ValueError:
                    pass
                else:
                    raise AssertionError('invalid ground estimate accepted')
    with patch.object(sys, 'argv', ['lidar_checks.py', '--map', 'fine', '--ground-estimate', 'non_obstacle']), \
         patch.object(lidar_checks, 'run_checks') as run:
        lidar_checks.main()
        assert run.call_args.kwargs['ground_estimate'] == 'non_obstacle'
    # Execute the real node constructor/main with transport mocked, without
    # importing ROS or starting a sensor/mission.
    import argparse
    from concurrent.futures import ThreadPoolExecutor
    from tapp.pointcloud_map import PoseBuffer
    from tapp.sensor_geometry import sensor_configuration
    from ros2_jazzy.gz_checks.online_batch_runtime import CsvChunks
    source = ROOT/'ros2_jazzy/gz_checks/lidar_planner.py'
    tree = ast.parse(source.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'LidarPlannerNode')
    cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '__init__']
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    class Node:
        def __init__(self, name): self.parameters = {}
        def declare_parameter(self, name, default): self.parameters[name] = default
        def get_parameter(self, name): return SimpleNamespace(value=self.parameters[name])
        def create_publisher(self, *args): return None
        def create_subscription(self, *args): return None
        def create_timer(self, *args): return None
    with tempfile.TemporaryDirectory() as temporary:
        prior = dict(tmap=TraversabilityMap(np.zeros((12, 12)), np.zeros((12, 12), bool)),
                     obstacle=np.zeros((12, 12), bool), water=np.zeros((12, 12), bool), nodata=np.zeros((12, 12), bool))
        original_declare = Node.declare_parameter
        def declare(node, name, default):
            return original_declare(node, name, {'run_folder': temporary, 'map_method': 'fine'}.get(name, default))
        Node.declare_parameter = declare
        scope = dict(Node=Node, OnlinePlannerNode=Node, Path=Path, np=np, load_map_file=lambda path: prior,
                     make_pointcloud_map=make_pointcloud_map, make_lidar_runtime=lambda *args, **kwargs: None,
                     PoseBuffer=PoseBuffer, ThreadPoolExecutor=ThreadPoolExecutor, CsvChunks=CsvChunks,
                     String=object, ROSPath=object, PoseArray=object, PointCloud2=object, Empty=object,
                     qos_profile_sensor_data=None, UPDATE_FIELDS=[], sensor_configuration=sensor_configuration)
        # Constructor subscriptions refer to existing methods; inert callbacks
        # suffice here, because their bodies are tested in test_real_sensors.
        exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), str(source), 'exec'), scope)
        selected_class = scope['LidarPlannerNode']
        for name in ('on_pose', 'on_cloud', 'on_mission', 'on_state', 'on_stop', 'map_tick', 'tick'):
            setattr(selected_class, name, lambda *args: None)
        node = selected_class(ground_estimate='non_obstacle')
        try:
            assert node.mapper.ground_estimate == 'non_obstacle'
        finally:
            node.map_pool.shutdown()
            node.log.close()
    calls = []
    dummy = SimpleNamespace(close=lambda: None, destroy_node=lambda: None)
    ros = SimpleNamespace(init=lambda **kwargs: calls.append(kwargs), spin=lambda node: None, ok=lambda: False)
    scope = dict(argparse=argparse, sys=sys, rclpy=ros, GROUND_ESTIMATES=('all_returns', 'non_obstacle'),
                 LidarPlannerNode=lambda **kwargs: (calls.append(kwargs) or dummy))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[main], type_ignores=[])), str(source), 'exec'), scope)
    scope['main'](['--ground-estimate', 'non_obstacle', '--ros-args', '-p', 'use_sim_time:=true'])
    assert calls == [dict(args=['--ros-args', '-p', 'use_sim_time:=true']), dict(ground_estimate='non_obstacle')]
    calls.clear()
    with patch.object(sys, 'argv', ['lidar_planner.py']): scope['main']()
    assert calls == [dict(args=None), {}]
    # Execute the command extension used by run_checks, without ROS/Gazebo.
    checks_tree = ast.parse(Path(lidar_checks.__file__).read_text())
    command_choice = next(n for n in ast.walk(checks_tree) if isinstance(n, ast.If)
                          and 'ground_estimate' in ast.unparse(n.test)
                          and any(isinstance(child, ast.Name) and child.id == 'commands'
                                  for statement in n.body for child in ast.walk(statement)))
    for mode in ('all_returns', 'non_obstacle'):
        commands = [['python3', 'lidar_planner.py', '--ros-args']]
        context = dict(commands=commands, manifest=dict(ground_estimate=mode))
        exec(compile(ast.fix_missing_locations(ast.Module(body=[command_choice], type_ignores=[])),
                     lidar_checks.__file__, 'exec'), context)
        expected_args = ['-p', 'ground_estimate:=non_obstacle'] if mode == 'non_obstacle' else []
        assert commands == [['python3', 'lidar_planner.py', '--ros-args']+expected_args]
    print('configuration PASS: byte-identical default manifests; opt-in factory, CLI, ROS parameter and actual node constructor propagation; invalid/coarse combinations rejected')


if __name__ == '__main__':
    for test in (test_legacy_bytes, test_box, test_top_only_and_history,
                 test_low_changes_bilinear_and_threshold, test_multi, test_configuration):
        test()
    print('all ground-estimate tests passed; requirement 6 is verified by running every conference/tests module separately (Python only)')
