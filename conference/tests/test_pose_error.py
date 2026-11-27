"""Verify the pose relay, real ROS callback paths and the truth-only evaluator."""

import csv
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace as S
from unittest.mock import patch

import numpy as np
from scipy.spatial.transform import Rotation

from experiments import eval_runs
from ros2_jazzy.gz_checks import lidar_checks, pose_error_relay
from tapp.pose_error import ESTIMATED_POSE_TOPIC, PoseError, PoseErrorSettings
from tapp.pose_trace import NS, TraceCsv
from tapp.traversability import TraversabilityMap
from tests import test_overlap_goal as baseline
from tests.test_endpoint_policy import Immediate
from tests.test_pose_trace import run_follower
from tests.test_review_fixes import FOLLOWER
from tests.test_rtf_option import LAUNCHER, clean_env
from tests.test_waypoint_feasibility import capture_launch
from thesis_bunker_mission.transport import pose3d

BASE = 'e288f783b95adc76ea9d2470e888906dfc93bb01'
ROOT = lidar_checks.ROOT
TANGENT, NORMAL = (.6, .8), (-.8, .6)
PATCH = '08OB88_-0167'
DRIFT_STD_REL_TOL = .10


def load_source(name, source):
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default(root):
    with patch.object(baseline, 'BASE', BASE):
        old, = baseline.load_before(lidar_checks)
    before = root/'path_follower_before.py'
    before.write_bytes(subprocess.check_output(
        ['git', 'show', f'{BASE}:{FOLLOWER.relative_to(ROOT.parent)}'], cwd=ROOT.parent))
    for enabled in (False, True):
        options = dict(map_method='fine', pose_trace=enabled, online_fixes='v2')
        expected = capture_launch(old, root/f'old-{enabled}', **options)
        assert expected == capture_launch(lidar_checks, root/f'implicit-{enabled}', **options)
        assert expected == capture_launch(lidar_checks, root/f'explicit-{enabled}', pose_error='none', **options)
    for fixes in ('none', 'v2'):
        assert run_follower(before, root/f'{fixes}-before', fixes) == run_follower(
            FOLLOWER, root/f'{fixes}-after', fixes)
    print('1 PASS: same-host old/default/none manifest, commands, run files and follower bytes')


def header(stamp):
    sec, nanosec = divmod(round(stamp*NS), NS)
    return S(stamp=S(sec=sec, nanosec=nanosec), frame_id='map')


def truth(stamp, x, y, *, z=0., angles=(0., 0., 0.)):
    pos = S(x=x, y=y, z=z)
    q = S(**dict(zip('xyzw', Rotation.from_euler('xyz', angles).as_quat())))
    return S(header=header(stamp), poses=[S(position=pos, orientation=q)])


def cloud(stamp, sensor):
    h = header(stamp)
    h.frame_id = sensor
    return S(header=h, width=1, height=1, point_step=12, row_step=12, is_bigendian=False,
             data=struct.pack('<fff', 2., 0., 0.),
             fields=[S(name=name, offset=i*4, datatype=7, count=1) for i, name in enumerate('xyz')])


class ImmediatePool(Immediate):
    def __init__(self, **kwargs):
        pass

    def shutdown(self, **kwargs):
        pass


def test_robot_callbacks(root, sensors):
    params = {
        'lidar_planner': dict(prior_map='fixture', map_id='fixture', run_folder=str(root/'planner'),
                              map_method='fine', sensors=sensors, pose_topic=ESTIMATED_POSE_TOPIC),
        'path_follower': dict(online=True, map_id='fixture', run_root=str(root/'follower'),
                               pose_topic=ESTIMATED_POSE_TOPIC),
    }
    nodes = {}

    class Twist:
        def __init__(self):
            self.linear, self.angular = S(x=0.), S(z=0.)

    class Node:
        def __init__(self, name):
            self.params = params[name].copy()
            self.clock = 1.05
            self.subscriptions, self.published = {}, {}
            nodes[name] = self

        def declare_parameter(self, key, value):
            self.params.setdefault(key, value)

        def get_parameter(self, key):
            return S(value=self.params[key])

        def create_subscription(self, kind, topic, callback, qos):
            self.subscriptions[topic] = callback

        def create_publisher(self, kind, topic, qos):
            self.published[topic] = []
            return S(publish=self.published[topic].append)

        def create_timer(self, period, callback):
            pass

        def get_clock(self):
            return S(now=lambda: S(nanoseconds=round(self.clock*NS), to_msg=lambda: header(self.clock).stamp))

        def get_logger(self):
            return S(info=lambda _: None, error=lambda _: None)

    stubs = {'rclpy': S(ok=lambda: True), 'rclpy.node': S(Node=Node),
             'rclpy.qos': S(qos_profile_sensor_data=object()),
             'geometry_msgs.msg': S(PoseArray=object, Twist=Twist,
                                    PoseStamped=lambda: S(header=header(0), pose=truth(0, 0., 0.).poses[0])),
             'nav_msgs.msg': S(Path=lambda: S(header=header(0), poses=[])),
             'sensor_msgs.msg': S(Imu=object, PointCloud2=object),
             'std_msgs.msg': S(String=S, Empty=object)}
    with patch.dict(sys.modules, stubs):
        # Load the inherited adapter as production sees it, with inert ROS modules.
        planner_key = 'thesis_bunker_mission.online_planner'
        sys.modules.pop(planner_key, None)
        importlib.import_module(planner_key)
        lidar = load_source('test_lidar_planner_072', ROOT/'ros2_jazzy/gz_checks/lidar_planner.py')
        follower = load_source('thesis_bunker_mission._follower_072', FOLLOWER).PathFollower()
        z = np.zeros((24, 24))
        mask = np.zeros_like(z, dtype=bool)
        prior = dict(tmap=TraversabilityMap(z, mask), obstacle=mask, water=mask, nodata=mask)
        make_runtime = lidar.make_lidar_runtime

        with patch.object(lidar, 'load_map_file', return_value=prior), patch.object(
            lidar, 'ThreadPoolExecutor', ImmediatePool
        ), patch.object(lidar, 'make_lidar_runtime', side_effect=lambda *a, **kw: make_runtime(
            *a, **kw, executor=Immediate())):
            planner = lidar.LidarPlannerNode()

    files = root/'trace'
    pair = TraceCsv(files/'pose_error.csv', pose_error_relay.POSE_PAIR_FIELDS, pose_error_relay.POSE_PAIR_FILE_BYTES)
    try:
        assert all('/ground_truth' not in node.subscriptions for node in nodes.values())
        received = []
        def publish(message):
            received.append(message)
            for node in (planner, follower):
                node.subscriptions[ESTIMATED_POSE_TOPIC](message)

        settings = PoseErrorSettings('bias', bias=(.6, .4, 2.))
        relay = pose_error_relay.PoseErrorRelay(PoseError(settings, TANGENT, NORMAL, settings.run_seed(PATCH)),
                                               publish, pose3d=pose3d, trace=pair)
        first = truth(1., 2., 2., z=.1, angles=(.1, -.15, .3))
        last = truth(1.05, 2., 2., z=.1, angles=(.1, -.15, .3))
        relay.receive(first)
        relay.receive(last)
        assert first.poses[0].position.x == 2. and first.poses[0].position.y == 2.
        assert received[0].header.stamp == first.header.stamp
        relay.receive(truth(.95, 9., 9.))  # A late packet cannot overwrite the shared pose.
        assert len(received) == 2
        expected = np.array([2.6, 1.6, .1, .1, -.15, .3+math.radians(2)])
        np.testing.assert_allclose(planner.pose, expected, atol=1e-12, rtol=0)
        np.testing.assert_array_equal(planner.pose, follower.pose)
        np.testing.assert_allclose(
            (np.asarray(planner.pose[:2])-2.) @ np.array([TANGENT, NORMAL]),
            .6*np.array(TANGENT)-.4*np.array(NORMAL), atol=1e-12, rtol=0)

        source_names = tuple(planner.mapper.mounts) if planner.multi else ('lidar',)
        for name in source_names:
            planner.on_cloud(cloud(1.025, name), name)
        for _ in range(len(source_names)+1):
            planner.map_tick()
        for name in source_names:
            filename = 'first_cloud.npz' if name == 'lidar' else f'first_cloud_{name}.npz'
            with np.load(planner.folder/filename) as saved:
                assert float(saved['stamp']) == 1.025
                np.testing.assert_allclose(saved['pose'], expected, atol=1e-12, rtol=0)
        assert planner.observed_cells > 0

        goal = (6., 2.)
        mission = dict(map_id='fixture', id=1, order=[0, 1], start_cells=[4, 4], stops_cells=[[12, 4]],
                       path=[[2., 2.], list(goal)], points=[list(goal)])
        planner.on_mission(S(data=json.dumps(mission)))
        planner.tick()
        planner.tick()
        [command] = planner.published['/mission/online_command']
        np.testing.assert_array_equal(json.loads(command.data)['path'][0], planner.pose[:2])
        follower.on_mission(command)
        with patch.object(follower.follower, 'step', wraps=follower.follower.step) as step:
            follower.tick()
            np.testing.assert_allclose(step.call_args.args[1], expected[[0, 1, 5]])
        # Advance through the follower's existing forward projection window.
        relay.receive(truth(1.10, 3.7, 2.2))
        follower.clock = 1.10
        follower.tick()
        # The estimate arrives, while ground truth remains >0.3 m from the waypoint.
        final = truth(1.15, 5.4, 2.4)
        assert math.dist((final.poses[0].position.x, final.poses[0].position.y), goal) > .3
        relay.receive(final)
        planner.clock = follower.clock = 1.15
        follower.tick()
        planner.tick()
        planner.tick()
        assert follower.last_status == 'completed' and planner.runtime.finished
    finally:
        follower.stop()
        planner.close()
        pair.close()
    with (files/'pose_error.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    assert [int(row['stamp_ns']) for row in rows] == [NS, 105*NS//100, 110*NS//100, 115*NS//100]
    np.testing.assert_allclose([float(rows[0][key]) for key in ('truth_y', 'estimated_y')], [2., 1.6])
    print(f'2 PASS ({sensors}): oblique coast, yaw, same stamped pose for cloud registration, planning, control and arrival')


def test_drift():
    def run(seed, rep=1, patch=PATCH):
        settings = PoseErrorSettings('drift', seed=seed, rep=rep, drift_pct=1.)
        return PoseError(settings, TANGENT, NORMAL, settings.run_seed(patch))

    samples = np.arange(0., 100.25, .25)
    col = lambda model: np.asarray([model.offset(x, 0.) for x in samples])
    a = col(run(0))
    np.testing.assert_array_equal(a, col(run(0)))
    assert not np.array_equal(a, col(run(1)))
    assert not np.array_equal(a, col(run(0, rep=2)))
    assert not np.array_equal(a, col(run(0, patch='08OB88_-1417')))
    np.testing.assert_array_equal(a[:4], np.zeros((4, 2)))
    np.testing.assert_array_equal(a[4], a[7])
    coarse = run(0)
    coarse.offset(0., 0.)
    np.testing.assert_array_equal(a[-1], coarse.offset(100., 0.))

    lengths = (1, 10, 100)
    columns = []
    for rep in range(1, 1001):
        model = run(0, rep)
        model.offset(0., 0.)
        columns.append([model.offset(x, 0.) for x in lengths])
    deviations = np.std(columns, axis=0, ddof=1)
    expected = np.repeat((.01*np.sqrt(lengths))[:, None], 2, axis=1)
    np.testing.assert_allclose(deviations, expected, atol=0., rtol=DRIFT_STD_REL_TOL)
    for length, sigma, (dx, dy) in zip(lengths, expected[:, 0], deviations):
        print(f'drift L={length:3d} m theory={sigma:.6f} sample_xy={dx:.6f},{dy:.6f}')
    model = run(4)
    seen = []
    relay = pose_error_relay.PoseErrorRelay(model, seen.append, pose3d=pose3d)
    relay.receive(truth(1., 1., 0.))
    relay.receive(truth(2., 5., 0.))
    assert model.steps == 0 and seen[-1].poses[0].position.x == 5.
    relay.start(S(data='{"started_t":3}'))
    relay.receive(truth(2.5, 100., 0.))
    relay.receive(truth(3., 5., 0.))
    relay.receive(truth(4., 6., 0., angles=(.1, .2, .3)))
    assert model.steps == 1 and model.travel_m == 1.
    np.testing.assert_allclose(pose3d(seen[-1].poses[0])[3:], [.1, .2, .3])
    print('3 PASS: 1,000 drift walks, ±10% sample standard-deviation limit, mission start and no yaw drift')


def write_csv(path, fields, rows):
    with path.open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(fields)
        writer.writerows(rows)


def test_evaluator(root):
    physical = root/'physical_1'
    raw = physical/'raw'/PATCH
    raw.mkdir(parents=True)
    manifest = physical/'manifest.json'
    manifest.write_text('{}\n')
    (raw/'mission.json').write_text('{"status":"completed","start_pose":[1,1,0,0,0,0],'
                                  '"final_state":{"pose":[8,1,0,0,0,0]}}\n')
    positions = ('t', 'x', 'y', 'roll', 'pitch')
    write_csv(raw/'trajectory.csv', positions, [(0, 1, 1, 0, 0), (1, 1.8, 1, 1.7, 0)])
    write_csv(raw/'endpoint_trajectory.csv', ('sim_time', 'x', 'y'), [(0, 7, 1), (1, 7.8, 1)])
    write_csv(raw/'debris_footprints.csv', ('xmin', 'xmax', 'ymin', 'ymax'), [(1.4, 1.6, .8, 1.2)])
    inside = np.zeros((24, 24), bool)
    inside[3, 2] = True
    np.savez(raw/'evaluation_reference.npz', truth_elev=np.zeros(inside.shape), truth_lethal=inside,
             truth_rock=inside, prior_rock=np.zeros_like(inside))
    (raw/'endpoint_masks').mkdir()
    np.savez(raw/'endpoint_masks'/'a.npz', applied=True, relaxed_shape=inside.shape,
             relaxed_bits=np.packbits(inside), sim_time=0.)

    with patch.object(baseline, 'BASE', BASE):
        old, = baseline.load_before(eval_runs)
    for name, module in (('before', old), ('after', eval_runs)):
        result = module.evaluate_run(raw, 'fixture')
        module.write_csv(root/f'{name}.csv', [*module.SCHEMA, 'missing_reasons'], [result])
    assert (root/'before.csv').read_bytes() == (root/'after.csv').read_bytes()
    assert result['relaxed_truth_lethal_len_m'] == 0.

    manifest.write_text('{"pose_error":"bias"}\n')
    (raw/'pose_trace').mkdir()
    write_csv(raw/'pose_trace'/'pose_error.csv', ('truth_x', 'estimated_x'), [(1, 7), (1.8, 7.8)])
    result = eval_runs.evaluate_run(raw, 'fixture')
    assert result['min_truth_clearance_m'] == 0. and result['truth_below_radius_entries'] == 1
    assert result['rolled_over'] and result['rollover_x_m'] == 1.8
    assert result['truth_lethal_len_m'] == .5 and result['relaxed_truth_lethal_len_m'] == .5
    (raw/'trajectory.csv').unlink()
    result = eval_runs.evaluate_run(raw, 'fixture')
    missing = json.loads(result['missing_reasons'])
    for key in ('min_truth_clearance_m', 'relaxed_truth_lethal_len_m'):
        assert result.get(key) is None and 'trajectory.csv' in missing[key]
    print('4 PASS: eval_runs measures truth clearance, rollover and endpoint-mask travel without estimated fallback')


def test_wiring(root):
    folder = root/'mock-run'
    result, sent, saved, commands = capture_launch(
        lidar_checks, folder, map_method='fine', pose_error='drift', pose_error_seed=-5,
        pose_error_rep=3, pose_error_drift_pct=2., pose_trace=True)
    manifest = json.loads(result)
    assert manifest['pose_error'] == 'drift' and manifest['pose_error_settings']['drift_pct'] == 2.
    assert manifest['pose_error_settings']['seed'] == -5 and manifest['pose_error_settings']['rep'] == 3
    case, = [row for row in manifest['cases'] if row['selected']]
    settings = PoseErrorSettings('drift', -5, 3, drift_pct=2.)
    assert case['pose_error']['run_seed'] == settings.run_seed(case['patch'])
    with np.load(ROOT/'data/shizuoka_beach_las'/(case['patch']+'.npz')) as data:
        for axis in ('tangent', 'normal'):
            np.testing.assert_array_equal(case['pose_error'][axis], data[axis])
    assert all('pose_topic:='+ESTIMATED_POSE_TOPIC in cmd for cmd in commands[2:4])
    assert commands[-1][1].endswith('/pose_error_relay.py')
    assert 'start_pose' not in json.loads(sent) and 'start_pose' in json.loads(saved)

    # Execute the relay's real entry point with an inert ROS transport.
    config = root/'relay.json'
    config.write_text(json.dumps(dict(case['pose_error'], settings=manifest['pose_error_settings'],
                                      trace_dir=str(root/'relay_trace'))))
    offered, subscriptions, output = [], {}, []
    node = S(create_publisher=lambda _, topic, qos: (offered.append(topic) or S(publish=output.append)),
             create_subscription=lambda _, topic, callback, qos: subscriptions.update({topic: callback}),
             destroy_node=lambda: None)

    def spin(_):
        subscriptions['/ground_truth'](truth(1., 1., 0.))
        subscriptions['/mission/command'](S(data='{"started_t":2}'))
        subscriptions['/ground_truth'](truth(2., 1., 0.))
        subscriptions['/ground_truth'](truth(3., 2., 0.))

    shutdown = type('ExternalShutdownException', (Exception,), {})
    stubs = {'rclpy': S(init=lambda args: None, spin=spin, ok=lambda: True, shutdown=lambda: None),
             'rclpy.executors': S(ExternalShutdownException=shutdown), 'rclpy.node': S(Node=lambda _: node),
             'rclpy.qos': S(qos_profile_sensor_data=None), 'geometry_msgs.msg': S(PoseArray=object),
             'std_msgs.msg': S(String=S)}
    with patch.dict(sys.modules, stubs):
        pose_error_relay.main(config)
    assert offered == [ESTIMATED_POSE_TOPIC] and len(output) == 3
    assert output[-1].poses[0].position.x != 2.
    assert (root/'relay_trace'/'pose_error.csv').is_file()

    prepared = root/'prepared'
    argv = ['lidar_checks', '--pose-error', 'bias', '--pose-error-bias=.25,.1,2',
            '--prepare-only', '--output', str(prepared)]
    with patch.object(sys, 'argv', argv), patch.dict(os.environ, clean_env(), clear=True):
        lidar_checks.main()
    assert json.loads((prepared/'manifest.json').read_text())['pose_error_settings']['bias'] == [.25, .1, 2.]

    fake = root/'docker'
    fake.write_text('#!/bin/bash\nprintf "%s\\0" "$@"\n')
    fake.chmod(0o755)
    flags = ['--pose-error', 'drift', '--pose-error-drift-pct', '2', '--pose-error-seed', '9', '--pose-error-rep', '3']
    env = dict(clean_env(), PATH=f'{root}:{os.environ["PATH"]}', THESIS_RENDER='cpu')
    output = subprocess.check_output(['bash', str(LAUNCHER), str(root/'wrapped'), *flags], env=env)
    assert output.split(b'\0')[-len(flags)-1:-1] == list(map(os.fsencode, flags))
    for invalid in (dict(pose_error='drift'), dict(pose_error='bias', pose_error_bias=(1., float('inf'), 0.)),
                    dict(pose_error='drift', pose_error_drift_pct=-1), dict(pose_error_rep=0)):
        try:
            lidar_checks.prepare_cases(root/'invalid', **invalid)
        except ValueError:
            assert not (root/'invalid').exists()
        else:
            raise AssertionError('invalid pose-error settings accepted')
    print('wiring PASS: selected patch axes and seed, shared topic, CLI parameters and shell forwarding')


if __name__ == '__main__':
    with TemporaryDirectory() as temporary:
        folder = Path(temporary)
        test_default(folder)
        test_robot_callbacks(folder/'legacy', 'legacy')
        test_robot_callbacks(folder/'multi', 'lidar_real+depth2')
        test_drift()
        test_evaluator(folder/'evaluation')
        test_wiring(folder)
    print('all task072 pose-error tests passed')
