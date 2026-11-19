"""Task041 footprint geometry, incremental projection and compatibility checks."""

import csv
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from ros2_jazzy.gz_checks import lidar_checks
from ros2_jazzy.gz_checks.lidar_map import make_pointcloud_map
from ros2_jazzy.gz_checks.safety_runtime import make_safety_lidar_runtime
from tapp.traversability import TraversabilityMap
from tests.test_map_speed import digest
from tests.test_online_safety import Immediate, ROOT, handle_safety_state
from tests.test_prior_free import cloud
from tests.test_real_sensors import local_cloud
from tests.test_review_fixes import drive, follower_node, SCENARIO

FIXTURE = ROOT/'tests/reference/obstacle_clearance_legacy.json'


def make_mapper(sensors, reference, **options):
    return make_pointcloud_map(np.zeros((24, 24)), map_method='fine', sensors=sensors,
                               obstacle_reference=reference, ground_estimate='non_obstacle', **options)


def fuse(mapper, xyz, *, source=None):
    if source is None:
        return mapper.update(xyz-[0., 0., .8], np.zeros(6))
    pose = np.array([2., 5., 0., 0., 0., 0.])
    return mapper.update(local_cloud(xyz, pose, mapper.mounts[source]), pose, sensor=source, stamp=1.)


def collect_map_bytes(root, **options):
    data = {}
    for sensors in ('legacy', 'lidar_real+depth2'):
        for reference in ('prior', 'local'):
            mapper = make_mapper(sensors, reference, **options)
            source = None if sensors == 'legacy' else 'lidar'
            key = sensors, reference
            for i, xyz in enumerate((cloud(), cloud(box=True), cloud(20., box=True))):
                fuse(mapper, xyz, source=source)
                data['/'.join((*key, str(i)))] = digest(mapper)
            path = root/('_'.join(key)+'.npz')
            mapper.save(path)
            for file in root.glob(path.name+'*'):
                data[file.name] = hashlib.sha256(file.read_bytes()).hexdigest()
    return data


def capture_defaults(*, record_clearance=False, **options):
    result = {}
    with tempfile.TemporaryDirectory() as tmp, patch('time.perf_counter', return_value=1.), \
            patch('time.monotonic', return_value=0.):
        root = Path(tmp)
        result['maps'] = collect_map_bytes(root, **options)
        for mode in ('none', 'v1', 'v2'):
            folder = root/mode
            folder.mkdir()
            mapper = make_mapper('legacy', 'prior', **options)
            tm = TraversabilityMap(mapper.prior, mapper.raw_obstacle)
            runtime = make_safety_lidar_runtime(dict(tmap=tm), mapper, online_fixes=mode,
                                                diagnostics=True, plan_log=folder/'plans.csv', executor=Immediate(),
                                                **(dict(record_clearance=True) if record_clearance else {}))
            node = follower_node(mode, folder/'follower')
            commands = []

            def tick(t, xy):
                command = runtime.tick(xy, t)
                commands.append(json.dumps(command))
                if command is not None:
                    node.on_mission(SimpleNamespace(data=commands[-1]))

            try:
                fuse(mapper, cloud())
                runtime.start(SCENARIO.copy())
                tick(0., [2., 2.])
                tick(.1, [2., 2.])
                drive(node, .1, 2., 2.)
                if mode != 'none':
                    stop = drive(node, 1., 2., 2., tilt=26.)
                    assert handle_safety_state(runtime, stop)
                    tick(1., [2., 2.])
                    tick(1.1, [2., 2.])
                    assert drive(node, 1.1, 2., 2.)['safety_revision'] == 2
                drive(node, 2., 3., 2.25)
                tick(2., [3., 2.25])
                tick(11., [3., 2.25])
                node.stop()
            finally:
                runtime.close()
            if record_clearance:
                assert (folder/'clearance.csv').is_file()
            result[mode] = dict(commands=commands, state=node.states, velocities=node.commands,
                                files={(file.name if 'follower' in file.parts else str(file.relative_to(folder))):
                                       hashlib.sha256(file.read_bytes()).hexdigest()
                                       for file in sorted(folder.rglob('*')) if file.is_file()
                                       and file.name != 'clearance.csv'})
            manifest = lidar_checks.prepare_cases(folder, map_method='fine', diagnostics=True,
                                                 online_fixes=mode, **options)
            encoded = (folder/'manifest.json').read_bytes()
            result[mode]['manifest_sha256'] = hashlib.sha256(encoded).hexdigest()
            result[mode]['environment'] = manifest.pop('input_environment')
            result[mode]['manifest_without_environment_sha256'] = hashlib.sha256(
                (json.dumps(manifest, ensure_ascii=False, indent=2)+'\n').encode()).hexdigest()
    return json.loads(json.dumps(result))


def test_default_bytes():
    expected = json.loads(FIXTURE.read_text())
    actual = capture_defaults()
    assert capture_defaults(obstacle_clearance='centre', record_clearance=True) == actual
    for mode in ('none', 'v1', 'v2'):
        if actual[mode]['environment'] != expected[mode]['environment']:
            for result in (actual, expected):
                result[mode].pop('manifest_sha256')
                result[mode].pop('environment')
    assert actual == expected
    print('1 PASS: centre default/explicit, prior/local, fine/multi; map, manifest, ROS-mocked commands and existing none/v1/v2 files match baseline')


def obstacle_cloud():
    return np.vstack((cloud(), np.repeat([[4.81, 4.81, .4]], 3, axis=0)))


def test_path():
    from tapp.collision import path_lethal_cells
    from tapp.config import RESOLUTION
    from tapp.exact_planners import run_planner_exact
    from tapp.obstacle_clearance import cell_boxes, path_clearance

    centre, overlap = [make_mapper('legacy', 'prior', obstacle_clearance=mode)
                       for mode in ('centre', 'overlap')]
    for mapper in (centre, overlap):
        fuse(mapper, obstacle_cloud())
    assert not centre.lethal[9, 11] and overlap.lethal[9, 11]
    assert np.array_equal(centre.fine_obstacle, overlap.fine_obstacle)
    assert np.count_nonzero(overlap.fine_obstacle) == 1
    boxes = cell_boxes(centre.fine_obstacle, .1, -.25)
    paths, distances = [], []
    for mapper in (centre, overlap):
        result = run_planner_exact('TA*-S', dict(tmap=mapper.tm, start=(10, 15), goal=(11, 7)))
        assert result['success'] and not len(path_lethal_cells(result['path'], mapper.lethal))
        paths.append(result['path'])
        distances.append(path_clearance(np.array(result['path'])*RESOLUTION, *boxes))
    assert distances[0] < .5 <= distances[1]
    print('2 mode min_path_clearance_m lethal_cells path_grid')
    for mapper, distance, path in zip((centre, overlap), distances, paths):
        print(mapper.obstacle_clearance, f'{distance:.9f}', int(mapper.lethal.sum()), path)

    # Exact counterexample: an old centre-sampled fine halo can miss a
    # coarse corner whose distance to the true square is below 0.5m.
    corner = [make_mapper('legacy', 'prior', obstacle_clearance=mode) for mode in ('centre', 'overlap')]
    for mapper in corner:
        mapper._add_obstacles([np.ravel_multi_index((15, 17), mapper.fine_shape)])
    from tapp.pointcloud_map_fine import coarse_overlap
    assert not coarse_overlap(corner[0].fine_inflated)[4, 2]
    assert corner[1]._inflated_coarse[4, 2]


def test_incremental():
    from scipy.ndimage import binary_dilation
    from tapp.pointcloud_map_fine import coarse_overlap
    from tapp.traversability import inflate

    x, y = np.mgrid[-6:7, -6:7]
    disk = np.maximum(abs(x)-1, 0)**2 + np.maximum(abs(y)-1, 0)**2 <= 25
    xyz = obstacle_cloud()
    scans = (cloud(), xyz, xyz+[2., 0., 0.], np.empty((0, 3)), xyz+[-1., 2., 0.])
    updates = 0
    for sensors in ('legacy', 'lidar_real+depth2'):
        for reference in ('prior', 'local'):
            mapper = make_mapper(sensors, reference, obstacle_clearance='overlap')
            for index, scan in enumerate(scans):
                fuse(mapper, scan, source=None if sensors == 'legacy' else ('lidar', 'camera1')[index % 2])
                expected = binary_dilation(mapper.fine_obstacle, structure=disk)
                pooled = coarse_overlap(expected)
                assert np.array_equal(mapper.fine_inflated, expected)
                assert np.array_equal(mapper._inflated_coarse, pooled)
                assert np.array_equal(mapper.lethal, mapper._prior_rock | pooled | inflate(mapper.tm.steep, .5))
                updates += 1
            assert mapper.fine_obstacle.any(), (sensors, reference)

    # A single nearby seed takes the dense path. Opposite corner seeds
    # take the sparse path with a clipped halo against the map boundaries.
    mapper = make_mapper('legacy', 'prior', obstacle_clearance='overlap')
    for cells in (((5, 6),), ((0, 0), (119, 119))):
        keys = [np.ravel_multi_index(cell, mapper.fine_shape) for cell in cells]
        mapper._add_obstacles(keys)
        expected = binary_dilation(mapper.fine_obstacle, structure=disk)
        assert np.array_equal(mapper.fine_inflated, expected)
        assert np.array_equal(mapper._inflated_coarse, coarse_overlap(expected))
    print(f'3 PASS: full recompute after {updates} updates across prior/local and fine/multi, plus dense/sparse edge cases')


def test_unseen_halo():
    from ros2_jazzy.gz_checks.endpoint_runtime import capture
    from ros2_jazzy.gz_checks.lidar_runtime import LidarOnlineMission
    from tapp.online_mission import OnlinePlanner

    mapper = make_mapper('legacy', 'prior', obstacle_clearance='overlap')
    fuse(mapper, np.repeat([[4.81, 4.81, .4]], 3, axis=0))
    fringe = mapper.lethal & ~mapper.seen
    assert fringe.any()
    tm = TraversabilityMap(mapper.prior, mapper.raw_obstacle)
    runtime = LidarOnlineMission(dict(tmap=tm), mapper, executor=Immediate())
    try:
        planner = OnlinePlanner(tm.cost, tm.lethal, tm.weights)
        runtime._observe(planner)
        assert planner.planning_maps()[0][fringe].all()
        diag = capture(mapper, OnlinePlanner(tm.cost, tm.lethal, tm.weights), [2., 2.], [2., 2.], 0., [4, 4])
        assert diag['lethal'][fringe].all() and not diag['seen'][fringe].any()
        assert not mapper.seen[fringe].any()
    finally:
        runtime.close()
    print('3 planning PASS: inferred overlap halo blocks unseen cells in normal and diagnostic planner snapshots')



def test_diagnostics():
    from contextlib import redirect_stdout
    import io
    import xml.etree.ElementTree as ET

    from experiments.obstacle_clearance_report import summarize
    from ros2_jazzy.gz_checks.clearance_log import save_debris_footprints
    from tapp.mapfile import save_map

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        mapper = make_mapper('legacy', 'prior')
        tm = TraversabilityMap(mapper.prior, mapper.raw_obstacle)
        runtime = make_safety_lidar_runtime(dict(tmap=tm), mapper, online_fixes='v2',
                                            diagnostics=True, record_clearance=True,
                                            plan_log=root/'plans.csv', executor=Immediate())
        try:
            fuse(mapper, cloud())
            runtime.start(SCENARIO.copy())
            for t in (0., .1, 1.):
                runtime.tick([2., 2.], t)
            fuse(mapper, obstacle_cloud())
            runtime.tick([4.8, 4.3], 10.1)
            runtime.tick([4.8, 4.3], 10.2)
        finally:
            runtime.close()
        with (root/'clearance.csv').open() as stream:
            rows = list(csv.DictReader(stream))
        assert len(rows) == 2 and rows[0]['clearance_m'] == ''
        assert [float(row['sim_time']) for row in rows] == [0., 10.1]
        assert [int(row['map_version']) for row in rows] == [1, 2]
        assert np.isclose(float(rows[1]['clearance_m']), .45)

        world = ET.fromstring('<world><model name="obstacle_1"><pose>1 1 0 0 0 0</pose>'
                              '<link><collision><geometry><box><size>0.5 0.5 1</size></box>'
                              '</geometry></collision></link></model></world>')
        save_debris_footprints(root/'debris_footprints.csv', world)
        (root/'trajectory.csv').write_text('x,y\n0,0.5\n2,0.5\n')
        result = summarize(root)
        assert result['min_truth_clearance_m'] == .25
        assert np.isclose(result['min_observed_clearance_m'], .45)
        (root/'trajectory_part001.csv').write_text('x,y\n2,1\n0,1\n')
        assert summarize(root)['min_truth_clearance_m'] == 0.
        obstacle = np.zeros((4, 4), bool)
        obstacle[2, 2] = True
        save_map(root/'truth.npz', np.zeros((4, 4)), obstacle=obstacle)
        assert summarize(root, root/'truth.npz')['min_truth_clearance_m'] == 0.
    print('4 B PASS: periodic observed data incl. empty map, exact trajectory-to-box distance, CSV parts and truth-mask fallback')


def test_review_fixes():
    from tapp.online_safety import make_follower, OFF_PATH_M
    from tapp.pure_pursuit import path_distance
    from thesis_bunker_mission.online_safety import SafetyRuntimeMixin

    class Base:
        finished = False

        def tick(self, position, sim_time):
            return {'revision': 1}

    class Runtime(SafetyRuntimeMixin, Base):
        pass

    runtime = Runtime(online_fixes='v2')
    runtime._last_plan_history = [{'revision': 0}]
    assert runtime.tick([0., 0.], 0.) == {'revision': 1}
    assert runtime._last_plan_history == [{'revision': 0}]
    before_different = 0
    rng = np.random.default_rng(104)
    for _ in range(100):
        line = rng.uniform(5., 195., (2, 2))
        axis = line[1]-line[0]
        normal = np.array((-axis[1], axis[0]))/np.linalg.norm(axis)
        for distance in (.7, .75, .8):
            pos = line.mean(axis=0) + distance*normal
            t = np.clip(np.sum((pos-line[0])*axis)/np.sum(axis**2), 0., 1.)
            before = np.linalg.norm(pos-line[0]-t*axis)
            follower = make_follower(line, online_fixes='v2')
            actual = follower._path_distance(pos)
            assert np.isclose(actual, before, atol=1e-12, rtol=0.)
            assert (actual > OFF_PATH_M) == (before > OFF_PATH_M)
            before_different += (path_distance(pos, line) > OFF_PATH_M) != (before > OFF_PATH_M)
    assert before_different
    with tempfile.TemporaryDirectory() as tmp:
        assert type(follower_node('none', Path(tmp))).safety_enabled is False
    print(f'4 C1-C3 PASS: missing plan_history, shared path_distance (300 decisions, {before_different} rounding cases), class default')


def test_cli():
    import ast
    from contextlib import redirect_stdout
    import io

    from tests.test_rtf_option import clean_env, LAUNCHER
    import subprocess

    with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, clean_env(), clear=True):
        root = Path(tmp)
        overlap = root/'overlap'
        args = ['lidar_checks.py', '--map', 'fine', '--output', str(overlap),
                '--obstacle-clearance', 'overlap', '--online-fixes', 'v2', '--diagnostics', '--prepare-only']
        with patch.object(sys, 'argv', args), redirect_stdout(io.StringIO()):
            lidar_checks.main()
        manifest = json.loads((overlap/'manifest.json').read_text())
        assert manifest['obstacle_clearance'] == 'overlap' and manifest['obstacle_inflation_radius_m'] == .5
        source = ast.parse(Path(lidar_checks.__file__).read_text())
        branch = next(node for node in ast.walk(source) if isinstance(node, ast.If)
                      and 'obstacle_clearance' in ast.unparse(node.test)
                      and any('commands' in ast.unparse(statement) for statement in node.body))
        commands = [[]]
        exec(compile(ast.Module(body=[branch], type_ignores=[]), '<lidar command>', 'exec'),
             dict(commands=commands, manifest=manifest))
        assert commands == [['-p', 'obstacle_clearance:=overlap']]

        docker = root/'docker'
        docker.write_text('#!/bin/bash\nprintf "%s\\0" "$@" >"$TASK041_ARGV"\n')
        docker.chmod(0o755)
        argv = root/'argv'
        env = dict(os.environ, PATH=f'{root}:{os.environ["PATH"]}', TASK041_ARGV=str(argv))
        subprocess.run(['bash', str(LAUNCHER), str(root/'wrapper'), '--map', 'fine',
                        '--obstacle-clearance', 'overlap'], check=True, env=env)
        assert argv.read_bytes().split(b'\0')[-3:] == [b'--obstacle-clearance', b'overlap', b'']

        rtf = root/'rtf'
        with patch.dict(os.environ, {'THESIS_FINE_PROTOCOL': 'rtf_check', 'THESIS_REAL_TIME_FACTOR': '1'}), \
                patch.object(sys, 'argv', ['lidar_checks.py', '--map', 'fine', '--prepare-only', '--output', str(rtf)]), \
                redirect_stdout(io.StringIO()) as output:
            lidar_checks.main()
        assert json.loads((rtf/'manifest.json').read_text())['real_time_factor'] == 1.
        assert 'aggregation requires 0.3x' in output.getvalue()
        assert sorted(f.name for f in rtf.iterdir()) == ['manifest.json']
        stubs = {'rclpy': SimpleNamespace(init=lambda: None, shutdown=lambda: None),
                 'rclpy.node': SimpleNamespace(Node=object),
                 'rclpy.qos': SimpleNamespace(qos_profile_sensor_data=None),
                 'geometry_msgs.msg': SimpleNamespace(PoseArray=object, Twist=object),
                 'rosgraph_msgs.msg': SimpleNamespace(Clock=object),
                 'std_msgs.msg': SimpleNamespace(String=object, Empty=object)}
        live = root/'rtf-live'
        with patch.dict(sys.modules, stubs), patch.dict(
                os.environ, {'THESIS_FINE_PROTOCOL': 'rtf_check', 'THESIS_REAL_TIME_FACTOR': '1'}), patch.object(
                lidar_checks.subprocess, 'check_output', return_value='fixture'), redirect_stdout(io.StringIO()) as output:
            lidar_checks.run_checks(live, map_method='fine', selected_patches=[])
        assert json.loads((live/'manifest.json').read_text())['execution'] == 'finished'
        assert 'aggregation requires 0.3x' in output.getvalue()
    print('4 C4 and routing PASS: env-selected 1.0 honoured, overlap manifest, ROS command and wrapper')


def test_ros_constructor():
    """Exercise the real LiDAR initializer with inert ROS subscriptions."""
    import ast

    from concurrent.futures import ThreadPoolExecutor
    from ros2_jazzy.gz_checks.endpoint_runtime import make_lidar_runtime
    from ros2_jazzy.gz_checks.online_batch_runtime import CsvChunks
    from tapp.pointcloud_map import PoseBuffer

    class Node:
        def __init__(self, name):
            self.params = dict(map_method='fine', online_fixes='v2', diagnostics=True, run_folder=str(folder))

        def declare_parameter(self, key, default):
            self.params.setdefault(key, default)

        def get_parameter(self, key):
            return SimpleNamespace(value=self.params[key])

        def create_publisher(self, *args):
            pass

        create_subscription = create_timer = create_publisher

    path = ROOT/'ros2_jazzy/gz_checks/lidar_planner.py'
    tree = ast.parse(path.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'LidarPlannerNode')
    cls.bases = [ast.Name(id='Node', ctx=ast.Load())]
    cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '__init__']
    mask = np.zeros((24, 24), bool)
    tm = TraversabilityMap(np.zeros(mask.shape), mask)
    prior = dict(tmap=tm, obstacle=mask, water=mask, nodata=mask)
    scope = dict(Node=Node, ThreadPoolExecutor=ThreadPoolExecutor, Path=Path, PoseBuffer=PoseBuffer,
                 load_map_file=lambda _: prior, make_pointcloud_map=make_pointcloud_map,
                 make_lidar_runtime=make_lidar_runtime, CsvChunks=CsvChunks, UPDATE_FIELDS=[])
    for name in ('String', 'ROSPath', 'PoseArray', 'PointCloud2', 'Empty', 'qos_profile_sensor_data'):
        scope[name] = object
    for name in ('on_pose', 'on_cloud', 'on_mission', 'on_state', 'on_stop', 'map_tick', 'tick'):
        setattr(Node, name, lambda *args: None)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), str(path), 'exec'), scope)
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        node = scope['LidarPlannerNode'](obstacle_clearance='overlap')
        try:
            assert node.runtime.online_fixes == 'v2' and node.mapper.obstacle_clearance == 'overlap'
            assert node.runtime.clearance_log.path == folder/'clearance.csv'
        finally:
            node.runtime.close()
            node.map_pool.shutdown()
            node.log.close()
    print('4 ROS constructor PASS: v2 runtime, overlap mapper and diagnostics selected together')


if __name__ == '__main__':
    test_default_bytes()
    test_path()
    test_incremental()
    test_unseen_halo()
    test_diagnostics()
    test_review_fixes()
    test_cli()
    test_ros_constructor()
    print('all task041 obstacle clearance tests passed')
