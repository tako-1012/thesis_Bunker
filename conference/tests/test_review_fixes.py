"""Task040 compatibility snapshots and ROS-free checks of the review fixes."""

from contextlib import redirect_stdout
from hashlib import sha256
import importlib.util
import io
import json
from pathlib import Path
import runpy
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from ros2_jazzy.gz_checks import lidar_checks
from ros2_jazzy.gz_checks.safety_runtime import make_safety_lidar_runtime
from tapp.traversability import TraversabilityMap
from tests.test_online_safety import Immediate, Mapper, ROOT, handle_safety_state

BASELINE_BYTES = ROOT/'tests/reference/review_fixes_legacy.json'
FOLLOWER = ROOT/'ros2_jazzy/src/thesis_bunker_mission/thesis_bunker_mission/path_follower.py'
SCENARIO = dict(id=1, map_id='fixture', order=[0, 1], start_cells=[4, 4], stops_cells=[[18, 4]],
                points=[[9., 2.]], path=[[2., 2.], [9., 2.]])


def follower_node(mode, folder):
    """Instantiate the production follower with inert ROS interfaces."""
    class Twist:
        def __init__(self):
            self.linear, self.angular = SimpleNamespace(x=0.), SimpleNamespace(z=0.)

    class Node:
        def __init__(self, name):
            self.params = dict(online=True, run_root=str(folder))
            self.clock, self.states, self.commands = 0., [], []
            self.logger = SimpleNamespace(info=lambda _: None, error=lambda _: None)

        def declare_parameter(self, key, default):
            self.params.setdefault(key, default)

        def get_parameter(self, key):
            return SimpleNamespace(value=self.params[key])

        def create_publisher(self, kind, topic, depth):
            if kind is Twist:
                return SimpleNamespace(publish=lambda msg: self.commands.append((msg.linear.x, msg.angular.z)))
            return SimpleNamespace(publish=lambda msg: self.states.append(msg.data))

        def create_subscription(self, *args):
            pass

        def create_timer(self, *args):
            pass

        def get_clock(self):
            return SimpleNamespace(now=lambda: SimpleNamespace(nanoseconds=round(self.clock*1e9)))

        def get_logger(self):
            return self.logger

    stubs = {'rclpy': SimpleNamespace(ok=lambda: True), 'rclpy.node': SimpleNamespace(Node=Node),
             'rclpy.qos': SimpleNamespace(qos_profile_sensor_data=None),
             'geometry_msgs.msg': SimpleNamespace(PoseArray=object, Twist=Twist),
             'sensor_msgs.msg': SimpleNamespace(Imu=object),
             'std_msgs.msg': SimpleNamespace(String=SimpleNamespace, Empty=object)}
    with patch.dict(sys.modules, stubs):
        spec = importlib.util.spec_from_file_location('thesis_bunker_mission._review_follower', FOLLOWER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        node = module.PathFollower(online_fixes=mode)
    node.map_id = 'fixture'
    return node


def drive(node, t, x, y, tilt=0.):
    node.clock = t
    node.pose = [x, y, 0., np.deg2rad(tilt), 0., 0.]
    node.pose_received = 0.
    node.tick()
    return json.loads(node.states[-1])


def make_runtime(mode, folder=None):
    z = np.zeros((24, 24))
    mapper = Mapper(z, np.zeros(z.shape, bool))
    options = dict(executor=Immediate(), plan_log=folder/'plans.csv' if folder else None)
    if mode is not None:
        options['online_fixes'] = mode
    runtime = make_safety_lidar_runtime(dict(tmap=TraversabilityMap(z, np.zeros(z.shape, bool))),
                                        mapper, **options)
    runtime.start(SCENARIO.copy())
    return runtime, mapper


def capture_compatibility():
    legacy = runpy.run_path(str(ROOT/'results/online_safety/verification/capture_defaults.py'))
    result = {'implicit_none': legacy['capture'](), 'explicit_none': legacy['capture'](explicit=True)}
    with tempfile.TemporaryDirectory() as tmp, patch('time.perf_counter', return_value=1.), \
            patch('time.monotonic', return_value=0.):
        root = Path(tmp)
        for mode in ('none', 'v1'):
            folder = root/mode
            folder.mkdir()
            runtime, mapper = make_runtime(mode, folder)
            node = follower_node(mode, folder/'follower')
            commands = []

            def tick(t, position):
                command = runtime.tick(position, t)
                commands.append(json.dumps(command))
                if command:
                    node.on_mission(SimpleNamespace(data=commands[-1]))

            try:
                tick(0., [2., 2.])
                tick(.1, [2., 2.])
                drive(node, .1, 2., 2.)
                if mode == 'v1':
                    state = drive(node, 1., 2., 2., tilt=26.)
                    assert handle_safety_state(runtime, state)
                    tick(1., [2., 2.])
                    tick(1.1, [2., 2.])
                    assert drive(node, 1.1, 2., 2.)['safety_revision'] == 2
                # Exercise known free-to-lethal tracking on the current route.
                mapper.lethal[10, 4] = True
                tick(2., [2.5, 2.])
                tick(2.1, [2.5, 2.])
                node.stop()
            finally:
                runtime.close()
            result[mode] = dict(commands=commands, state=node.states, velocities=node.commands,
                                files={(file.name if 'follower' in file.parts else str(file.relative_to(folder))):
                                       sha256(file.read_bytes()).hexdigest()
                                       for file in sorted(folder.rglob('*')) if file.is_file()})
            manifest_path = folder/'manifest.json'
            manifest = lidar_checks.prepare_cases(folder, map_method='fine', online_fixes=mode)
            result[mode]['manifest'] = dict(full_sha256=sha256(manifest_path.read_bytes()).hexdigest(),
                                            environment=manifest.pop('input_environment'),
                                            without_environment_sha256=sha256(
                                                (json.dumps(manifest, ensure_ascii=False, indent=2)+'\n').encode()).hexdigest())
    # Both fixture capture and comparison use JSON's list and scalar types.
    return json.loads(json.dumps(result))


def test_legacy_bytes():
    expected = json.loads(BASELINE_BYTES.read_text())
    current = capture_compatibility()
    exact_manifests = 0
    for key, manifests in [('implicit_none', ('coarse', 'fine', 'real')),
                           ('explicit_none', ('coarse', 'fine', 'real')),
                           ('none', ('manifest',)), ('v1', ('manifest',))]:
        for name in manifests:
            before, after = expected[key].pop(name), current[key].pop(name)
            assert after['without_environment_sha256'] == before['without_environment_sha256']
            if before['environment'] == after['environment']:
                assert before['full_sha256'] == after['full_sha256']
                exact_manifests += 1
    assert current == expected
    print(f'1 PASS: none/v1 commands, ROS follower state and log bytes unchanged; full manifest hashes {exact_manifests}/8')


def test_repeat_tilt():
    with tempfile.TemporaryDirectory() as tmp, patch('time.monotonic', return_value=0.):
        for mode, delay, terminal in [('v1', 9., False), ('v2', 9., True),
                                      ('v2', 10., True), ('v2', 10.1, False)]:
            folder = Path(tmp)/f'{mode}-{delay}'
            runtime, _ = make_runtime(mode, folder)
            node = follower_node(mode, folder/'follower')

            def tick(t):
                command = runtime.tick([2., 2.], t)
                if command is not None:
                    node.on_mission(SimpleNamespace(data=json.dumps(command)))
                return command

            try:
                tick(0.)
                assert tick(.1)['revision'] == 1
                first = drive(node, 1., 2., 2., 26.)
                assert first['status'] == 'unsafe_tilt' and node.commands[-1] == (0., 0.)
                assert handle_safety_state(runtime, first)
                assert handle_safety_state(runtime, first)  # Duplicate of the same revision.
                tick(1.)
                replacement = tick(1.1)
                assert replacement['reason'] == 'unsafe_tilt' and replacement['revision'] == 2
                assert handle_safety_state(runtime, first)  # Stale after replacement.
                assert not runtime._safety_hold
                second = drive(node, 1.+delay, 2., 2., 26.)
                assert second['status'] == 'unsafe_tilt' and node.commands[-1] == (0., 0.)
                assert handle_safety_state(runtime, second)
                command = tick(1.+delay)
                if terminal:
                    assert command['online_error'] == 'unsafe_tilt' and runtime.finished
                    assert node.last_status == 'no_path' and node.follower is None
                    mission_log = next((folder/'follower').glob('*/mission.json'))
                    assert json.loads(mission_log.read_text())['online_error'] == 'unsafe_tilt'
                    assert runtime.safety_events[-1]['event'] == 'unsafe_tilt_repeat'
                    assert runtime.safety_events[-1]['detail']['duration_s'] == delay
                    assert 'unsafe_tilt_repeat' in (folder/'safety_events.csv').read_text()
                    assert tick(1.1+delay) is None
                else:
                    assert command is None and not runtime.finished
                    assert tick(1.1+delay)['revision'] == 3
                    assert not runtime.finished
                print(f'A1 {mode} second tilt after {delay:g}s: '
                      f'{"terminal unsafe_tilt" if terminal else "replanned"}')
            finally:
                node.stop()
                runtime.close()


def test_duplicate_segments():
    from tapp.online_safety import make_follower

    for mode in ('v1', 'v2'):
        follower = make_follower([[0., 0.], [10., 0.], [10., 0.]], online_fixes=mode)
        # Pure Pursuit normally deduplicates at construction. Put the zero
        # segment back outside its projection window to exercise the guard.
        controller = follower.controller
        controller.path = np.vstack((controller.path, controller.path[-1]))
        controller.arc = np.r_[controller.arc, controller.arc[-1]]
        controller.lengths = np.r_[controller.lengths, 0.]
        with np.errstate(invalid='ignore'):
            command = follower.step(0., [1., .8, 0.])
        assert follower.status == ('running' if mode == 'v1' else 'off_path')
        if mode == 'v2':
            assert command == (0., 0., True)
        print(f'A2 {mode} duplicate segment, 0.8m: {follower.status}')
    single = make_follower([[0., 0.], [0., 0.]], online_fixes='v2')
    assert single.step(0., [0., .8, 0.]) == (0., 0., True)
    assert single.status == 'off_path'


def test_remaining_path():
    from tapp.online_safety import make_follower

    for mode in ('v1', 'v2'):
        follower = make_follower([[0., 0.], [6., 0.], [6., 1.], [0., 1.]], online_fixes=mode)
        positions = [(0., 0.), (2., 0.), (4., 0.), (6., 0.), (6., 1.), (5., 1.)]
        for t, (x, y) in enumerate(positions):
            assert not follower.step(t, [x, y, 0.])[2]
        assert follower.controller.progress > 7.
        command = follower.step(6., [5., .2, 0.])
        assert follower.status == ('running' if mode == 'v1' else 'off_path')
        if mode == 'v2':
            assert command == (0., 0., True)
        print(f'A3 {mode} near passed segment and 0.8m from remaining route: {follower.status}')


def test_window():
    from tests.test_prior_free import BOX, mapper_for, update

    # The only low support is 0.70m away along each axis. A 1.1m window
    # contains just the elevated centre cell, so its fit is undefined.
    ground = np.array([[4.3, 5., 0.], [5.7, 5., 0.], [5., 4.3, 0.], [5., 5.7, 0.]])
    box = np.repeat([[5., 5., .4]], 3, axis=0)
    mapper = mapper_for()
    update(mapper, np.vstack((ground, box)))
    assert mapper.detected_obstacle[BOX], '1.5m window must include ground 0.70m from the box'
    assert mapper.detected_obstacle.sum() == 1
    print('B6 PASS: the box is detected with support 0.70m from its centre')


def compare_scans(label, shape, scans, *, check_lethal=None):
    from tapp import local_ground
    from tapp.pointcloud_map_multi import PointCloudMapMulti
    from tapp.sensor_geometry import REAL_MOUNTS
    from tests.test_local_speed import baseline_module, mask_differences
    from tests.test_real_sensors import local_cloud

    old_update = baseline_module('local_ground').update_local
    old_mapper = baseline_module('pointcloud_map_multi').PointCloudMapMulti
    prior = np.zeros(shape)
    maps = [cls(prior, obstacle_reference='local') for cls in (old_mapper, PointCloudMapMulti)]
    print(f'B7 {label} scan fine_diff coarse_diff lethal_diff', flush=True)
    for scan, (xyz, pose) in enumerate(scans):
        points = local_cloud(xyz, pose, REAL_MOUNTS['lidar'])
        with patch.object(local_ground, 'update_local', old_update):
            maps[0].update(points, pose, sensor='lidar')
        maps[1].update(points, pose, sensor='lidar')
        lethal = int(np.count_nonzero(maps[0].lethal != maps[1].lethal))
        print(scan, *mask_differences(*maps), lethal, flush=True)
        if check_lethal is not None:
            assert lethal == 0
            check_lethal(scan, maps)


def test_multiscan():
    # One return per fine cell per scan. Three scans are needed to
    # accumulate the three high returns required for obstacle detection.
    coordinates = 3.01 + .1*np.arange(41)
    x, y = np.meshgrid(coordinates, coordinates, indexing='ij')
    box = (abs(x-5.) < .25) & (abs(y-5.) < .25)
    xyz = np.column_stack((x.ravel(), y.ravel(), np.where(box, .4, 0.).ravel()))

    def scans():
        for scan in range(12):
            yield xyz, np.array([2.+.05*scan, 5., 0., 0., 0., 0.])

    def check_history(scan, maps):
        for mapper in maps:
            assert bool(mapper.detected_obstacle[10, 10]) == (scan >= 2)
            assert bool(mapper.lethal[10, 10]) == (scan >= 2)

    compare_scans('controlled', (24, 24), scans(), check_lethal=check_history)


def audit_review_multiscan():
    """Record every scan from the review fixture, including transient differences."""
    angle = np.tile(np.linspace(-np.pi, np.pi, 1800, endpoint=False), 16)
    radii = np.repeat(np.linspace(4.2, 22., 16), 1800)
    boxes = [(110, 100), (118, 103), (126, 97), (134, 101), (142, 99), (150, 104)]
    rng = np.random.default_rng(7)

    def scans():
        for scan in range(12):
            pose = np.array([100.+4*scan, 100., 0., 0., 0., 0.])
            distance = radii+rng.normal(0., .08, len(angle))
            x, y = pose[0]+distance*np.cos(angle), pose[1]+distance*np.sin(angle)
            z = .03*x+.02*y+.15*np.sin(x/3)*np.cos(y/4)
            for bx, by in boxes:
                z[(abs(x-bx) < .5) & (abs(y-by) < .5)] += .4
            yield np.column_stack((x, y, z)), pose

    compare_scans('review', (401, 401), scans())


def test_sparse_planes():
    from tapp import local_ground
    from tests.test_prior_free import cloud

    support = cloud(20., box=True)
    queries = np.vstack((support[::17], [25., 25., 0.]))
    dense = local_ground.local_planes(support, queries)
    with patch.object(local_ground, 'cKDTree', wraps=local_ground.cKDTree) as tree:
        sparse = local_ground.local_planes(support, queries, max_grid_cells=1)
        tree.assert_called_once()
    assert np.isnan(dense[-1]) and np.isfinite(dense[:-1]).all()
    np.testing.assert_allclose(sparse, dense, atol=1e-12, rtol=0, equal_nan=True)
    print(f'B9 PASS: dense/cKDTree agree on {len(queries)} heights, including unknown support')


def test_reference_hashes():
    for module, expected in (
        ('local_ground', '5a57c07f09d31e0fcf7508de6ddc28e05253cca13939eeda767ffca2ef7491f5'),
        ('pointcloud_map_multi', '710d81185c5a945e9c89d1d679414c6846832f779edbc6a9e9065823ba67dc96'),
    ):
        data = (ROOT/'tests/reference'/f'{module}_032.py').read_bytes()
        assert sha256(data).hexdigest() == expected
        print(f'B8 5f36770 {module}_032.py SHA-256 {expected}')



def test_world_and_summary():
    from data_prep.export_gazebo import export_gazebo
    from experiments import lidar_fine_report
    from tapp.mapfile import scenario_to_mapfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        fine = lidar_checks.prepare_cases(root/'fine', map_method='fine')
        edge = lidar_checks.prepare_cases(root/'edge', map_method='fine', edge_margin_m=10)
        # Compare the same beach and start with different selected waypoints.
        assert fine['scenarios'][0]['points'] != edge['scenarios'][0]['points']
        products = []
        for i, manifest in enumerate((fine, edge)):
            case, meta = manifest['cases'][0], manifest['scenarios'][0]
            truth, prior = lidar_checks.case_world_inputs(case, meta, manifest)
            terrain_file = root/f'terrain{i}.npz'
            scenario_to_mapfile(dict(truth, raw_elev=truth['tmap'].elev),
                                terrain_file, 'fixture', case['patch'], 'task022 truth', lidar_checks.LAS_ATTRIBUTION)
            world = root/f'world{i}'
            export_gazebo(terrain_file, world, max_pixels=4097)
            products.append((case['world_reference'], case['input_audit']['signatures'],
                             terrain_file.read_bytes(), (world/'world.sdf').read_bytes(),
                             (world/'heightmap.png').read_bytes()))
        assert products[0] == products[1]
        coarse_case = dict(patch=edge['cases'][0]['patch'])
        lidar_checks.case_world_inputs(coarse_case, edge['scenarios'][0], {'edge_margin_m': 10})
        assert 'world_reference' not in coarse_case
        lidar_checks.case_world_inputs(coarse_case, edge['scenarios'][0], {'edge_margin_m': 10},
                                       matched_world=True)
        assert coarse_case['world_reference'] == products[0][0]
        # Check run_checks itself with no cases, inert ROS and a fake version
        # command. Reintroducing the edge-specific override would set world_input.
        stubs = {'rclpy': SimpleNamespace(init=lambda: None, shutdown=lambda: None),
                 'rclpy.node': SimpleNamespace(Node=object),
                 'rclpy.qos': SimpleNamespace(qos_profile_sensor_data=None),
                 'geometry_msgs.msg': SimpleNamespace(PoseArray=object, Twist=object),
                 'rosgraph_msgs.msg': SimpleNamespace(Clock=object),
                 'std_msgs.msg': SimpleNamespace(String=object, Empty=object)}
        coarse_output = root/'coarse-run'
        coarse_output.mkdir()
        with patch.dict(sys.modules, stubs), patch.object(
                lidar_checks, 'prepare_cases', return_value=dict(edge_margin_m=10, cases=[], scenarios=[])), patch.object(
                lidar_checks.subprocess, 'check_output', return_value='fixture'):
            lidar_checks.run_checks(coarse_output, edge_margin_m=10, finalize_report=False)
        assert 'world_input' not in json.loads((coarse_output/'manifest.json').read_text())
        print('B10 PASS: fine world input NPZ, world SDF and heightmap match byte for byte; coarse matching remains explicit')

        with patch.object(lidar_fine_report, 'summarize') as summarize, redirect_stdout(io.StringIO()) as log:
            lidar_checks.summarize_edge_margin(root/'edge', edge)
            summarize.assert_not_called()
            assert 'the waypoint cohort differs from the cached task022 controls' in log.getvalue()
            lidar_checks.summarize_edge_margin(root/'coarse', {'edge_margin_m': 10})
            assert 'requires --map fine' in log.getvalue()
            lidar_checks.summarize_edge_margin(root/'opt-in', dict(edge, online_fixes='v2'))
            assert 'opt-in conditions require separate evaluation' in log.getvalue()
            lidar_checks.summarize_edge_margin(root/'fine', dict(fine, edge_margin_m=10))
            summarize.assert_called_once_with(root/'fine')
        print(log.getvalue(), end='')
        print('B11 PASS: standard aggregation selected only for a comparable fine cohort')


def test_v2_configuration():
    import ast

    from thesis_bunker_mission.online_safety import make_async_runtime

    with tempfile.TemporaryDirectory() as tmp:
        manifest = lidar_checks.prepare_cases(Path(tmp), map_method='fine', online_fixes='v2')
        assert manifest['online_fixes'] == 'v2'
        assert manifest['online_safety']['unsafe_tilt_repeat_sim_s'] == 10.
        assert manifest['online_safety']['off_path_m'] == .75
        assert manifest['online_safety']['max_tilt_deg'] == 25.
        with patch.object(sys, 'argv', ['lidar_checks.py', '--online-fixes', 'v2']), \
                patch.object(lidar_checks, 'run_checks') as run:
            lidar_checks.main()
            assert run.call_args.kwargs['online_fixes'] == 'v2'
    tree = ast.parse(Path(lidar_checks.__file__).read_text())
    extension = next(n for n in ast.walk(tree) if isinstance(n, ast.If) and 'online_fixes' in ast.unparse(n.test)
                     and any(isinstance(k, ast.Name) and k.id == 'commands'
                             for statement in n.body for k in ast.walk(statement)))
    commands = [['gz'], ['bridge'], ['follower'], ['planner']]
    exec(compile(ast.Module(body=[extension], type_ignores=[]), '<commands>', 'exec'),
         dict(commands=commands, manifest=manifest))
    assert commands[-1][-2:] == commands[-2][-2:] == ['-p', 'online_fixes:=v2']
    tm = TraversabilityMap(np.zeros((24, 24)), np.zeros((24, 24), bool))
    from tapp.prior import PriorMap
    runtime = make_async_runtime(tm, tm, PriorMap(tm.cost, tm.lethal, .5),
                                 executor=Immediate(), online_fixes='v2')
    try:
        assert runtime.online_fixes == 'v2'
    finally:
        runtime.close()
    print('v2 configuration PASS: manifest, CLI, both ROS parameters and async factory')


if __name__ == '__main__':
    for test in (test_legacy_bytes, test_repeat_tilt, test_duplicate_segments, test_remaining_path,
                 test_window, test_sparse_planes, test_reference_hashes, test_v2_configuration, test_world_and_summary, test_multiscan,
                 audit_review_multiscan):
        test()
    print('all task040 review-fix tests passed')
