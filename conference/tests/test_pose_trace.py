"""Check pose diagnostics and the original ROS control path without ROS or Gazebo."""

import csv
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from experiments import pose_trace_inspect as inspect
from ros2_jazzy.gz_checks import lidar_checks
from tapp import pose_trace as trace
from tests import test_overlap_goal as baseline
from tests.test_review_fixes import FOLLOWER, SCENARIO
from tests.test_rtf_option import LAUNCHER, clean_env
from tests.test_waypoint_feasibility import capture_launch

BASE = '150c27a6ed18b28e3c826b0fbc0941cdea28a57f'
NS = trace.NS


def make_follower(source, folder, fixes, trace_dir):
    class Twist:
        def __init__(self):
            self.linear, self.angular = SimpleNamespace(x=0.), SimpleNamespace(z=0.)

    class Node:
        def __init__(self, name):
            self.params = dict(online=True, map_id='fixture', run_root=str(folder))
            if trace_dir is not None:
                self.params['pose_trace_dir'] = str(trace_dir)
            self.subscriptions, self.states, self.commands = {}, [], []
            self.clock = 0

        def declare_parameter(self, key, default):
            self.params.setdefault(key, default)

        def get_parameter(self, key):
            return SimpleNamespace(value=self.params[key])

        def create_publisher(self, kind, topic, depth):
            if kind is Twist:
                return SimpleNamespace(publish=lambda msg: self.commands.append((msg.linear.x, msg.angular.z)))
            return SimpleNamespace(publish=lambda msg: self.states.append(msg.data))

        def create_subscription(self, kind, topic, callback, qos):
            self.subscriptions[topic] = callback

        def create_timer(self, period, callback):
            assert period == .05
            self.timer = callback

        def get_clock(self):
            return SimpleNamespace(now=lambda: SimpleNamespace(nanoseconds=self.clock))

        def get_logger(self):
            return SimpleNamespace(info=lambda _: None, error=lambda _: None)

    stubs = {'rclpy': SimpleNamespace(ok=lambda: True), 'rclpy.node': SimpleNamespace(Node=Node),
             'rclpy.qos': SimpleNamespace(qos_profile_sensor_data=None),
             'geometry_msgs.msg': SimpleNamespace(PoseArray=object, Twist=Twist),
             'sensor_msgs.msg': SimpleNamespace(Imu=object),
             'std_msgs.msg': SimpleNamespace(String=SimpleNamespace, Empty=object)}
    with patch.dict(sys.modules, stubs):
        spec = importlib.util.spec_from_file_location('thesis_bunker_mission._pose_trace_fixture', source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.PathFollower(online_fixes=fixes)


def pose_message(header=True, *, empty=False):
    pose = SimpleNamespace(position=SimpleNamespace(x=2., y=2., z=0.),
                           orientation=SimpleNamespace(x=0., y=0., z=0., w=1.))
    message = SimpleNamespace(poses=[] if empty else [pose])
    if header:
        message.header = SimpleNamespace(stamp=SimpleNamespace(sec=4, nanosec=500))
    return message


def run_follower(source, folder, fixes, trace_dir=None):
    node = make_follower(source, folder, fixes, trace_dir)
    wall = 10*NS
    with patch('time.monotonic', side_effect=lambda: wall/NS), patch('time.monotonic_ns', side_effect=lambda: wall):
        node.clock = 5*NS
        node.subscriptions['/ground_truth'](pose_message())
        node.subscriptions['/mission/online_command'](SimpleNamespace(data=json.dumps(SCENARIO)))
        node.timer()
        node.clock += NS//20
        node.subscriptions['/ground_truth'](pose_message(False))
        wall += NS
        node.timer()
        assert node.last_status == 'running'  # The control uses >1.0, including under tracing.
        node.clock += NS//20
        wall += NS//20
        node.subscriptions['/ground_truth'](pose_message(empty=True))
        node.timer()
        assert node.last_status == 'pose_timeout' and node.commands[-1] == (0., 0.)
    if trace_dir is not None:
        for writer in node.pose_trace_logs:
            writer.close()
    files = {path.name: path.read_bytes() for path in folder.glob('*/*') if path.is_file()}
    return json.dumps((node.commands, node.states)).encode(), files


def test_default_bytes(root):
    with patch.object(baseline, 'BASE', BASE):
        previous, = baseline.load_before(lidar_checks)
    before_path = root/'before.py'
    before_path.write_bytes(subprocess.check_output(
        ['git', 'show', f'{BASE}:{FOLLOWER.relative_to(lidar_checks.ROOT.parent)}'],
        cwd=lidar_checks.ROOT.parent))
    for fixes in ('none', 'v1', 'v2'):
        options = dict(map_method='fine', online_fixes=fixes, diagnostics=True)
        old, new = root/f'{fixes}-old', root/f'{fixes}-new'
        assert capture_launch(previous, old, **options) == capture_launch(lidar_checks, new, **options)
        def saved(folder):
            return {path.relative_to(folder): path.read_bytes() for path in folder.rglob('*') if path.is_file()}
        assert saved(old) == saved(new)
        expected = run_follower(before_path, root/f'{fixes}-follower-before', fixes)
        assert expected == run_follower(FOLLOWER, root/f'{fixes}-follower-after', fixes)
        traced = root/f'{fixes}-trace'
        assert expected == run_follower(FOLLOWER, root/f'{fixes}-follower-traced', fixes, traced)
        poses = inspect.read_trace(traced, 'follower_pose', trace.POSE_FIELDS, strings=('stamp_source',))
        assert [row['stamp_source'] for row in poses] == ['header', 'ros', 'header']
        assert [row['has_pose'] for row in poses] == [1, 1, 0]
        assert poses[0]['stamp_ns'] == 4*NS+500 and poses[1]['stamp_ns'] == poses[1]['ros_ns']
        ticks = inspect.read_trace(traced, 'follower_tick', trace.TICK_FIELDS)
        assert [row['pose_timeout'] for row in ticks] == [0, 0, 1]
        assert [row['interval_ns'] for row in ticks] == [None, NS, NS//20]
        assert ticks[-1]['last_pose_received_ns'] == 10*NS
    print('1 PASS: same-host default manifest, run files, ROS arguments, commands, timeout boundary and control bytes for none/v1/v2')


def write_csv(base, name, fields, rows):
    with (base/f'{name}.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(fields)
        writer.writerows(rows)


def fake_run(raw, *, peers_advance, ticks_stall, fallback=False):
    folder = raw/'pose_trace'
    folder.mkdir(parents=True)
    raw.joinpath('mission.json').write_text('{"status":"pose_timeout","finished_t":14}')
    before_gap = [18*NS, 19*NS, 20*NS]
    during_gap = [20*NS+NS//4, 20*NS+NS//2, 21*NS]
    for key in inspect.SUBSCRIBERS:
        timestamps = before_gap + (during_gap if key != 'follower' and peers_advance else [])
        rows = [(value, value//3, value//3, 'ros' if fallback else 'header', 1) for value in timestamps]
        write_csv(folder, key+'_pose', trace.POSE_FIELDS, rows)
    stop = 21*NS+NS//10
    tick_times = list(range(19*NS, 20*NS+1, NS//10))+(during_gap + [stop] if not ticks_stall else [stop])
    ticks = [(t, t-tick_times[i-1] if i else None, 2_000_000, int(t == stop), 20*NS if t == stop else None)
             for i, t in enumerate(tick_times)]
    write_csv(folder, 'follower_tick', trace.TICK_FIELDS, ticks)
    write_csv(folder, 'cpu', trace.CPU_FIELDS, [(20*NS, 12., 2.0, 1.6, 1.2), (21*NS, 88., 3.0, 2.5, 1.8)])


def test_inspector(root):
    cases = dict(upstream=(False, False, 'shared_upstream_gap'),
                 transfer=(True, False, 'follower_receive_gap'),
                 processing=(True, True, 'follower_processing_gap'))
    raw_root = root/'runs'
    for name, (peers_advance, ticks_stall, expected) in cases.items():
        raw = raw_root/name
        fake_run(raw, peers_advance=peers_advance, ticks_stall=ticks_stall)
        row = inspect.inspect(raw)
        assert row['diagnosis'] == expected and not row['trace_issues']
        assert row['follower_pose_gap_s'] == 1.1 and row['follower_usable_in_gap'] == 0
        for who in ('planner', 'observer'):
            assert row[who+'_usable_in_gap'] == (3 if peers_advance else 0)
            assert row[who+'_header_advanced_in_gap'] is peers_advance
        assert row['tick_gap_overlaps_pose_gap'] is ticks_stall
        assert row['max_tick_interval_s'] == (1.1 if ticks_stall else .5)
        assert row['max_tick_duration_s'] == .002 and row['cpu_samples_in_window'] == 2
        assert row['cpu_pct_last'] == row['cpu_pct_max'] == 88. and row['load1_last'] == 3.
    missing = raw_root/'old'
    missing.mkdir()
    missing.joinpath('mission.json').write_text('{"status":"pose_timeout","finished_t":14}')
    assert inspect.inspect(missing)['diagnosis'] == 'missing_timeout_marker'
    fallback = raw_root/'no-header'
    fake_run(fallback, peers_advance=True, ticks_stall=False, fallback=True)
    row = inspect.inspect(fallback)
    assert row['diagnosis'] == 'follower_receive_gap' and row['observer_header_advanced_in_gap'] is None
    (fallback/'pose_trace'/'planner_pose.csv').unlink()
    (fallback/'pose_trace'/'observer_pose.csv').unlink()
    assert inspect.inspect(fallback)['diagnosis'] == 'insufficient_data'
    output = root/'summary.csv'
    assert inspect.main([str(raw_root), '--out', str(output)]) == 0
    with output.open() as stream:
        summaries = {Path(row['run']).name: row['diagnosis'] for row in csv.DictReader(stream)}
    assert len(summaries) == 5 and all(summaries[name] == expected for name, (_, _, expected) in cases.items())
    print('2 PASS: shared upstream, follower receipt, follower processing, missing data, stamp fallback and CPU evidence')


def test_wiring_and_limits(root):
    prepared = root/'prepared'
    argv = ['lidar_checks.py', '--map', 'fine', '--pose-trace', '--prepare-only', '--output', str(prepared)]
    with patch.object(sys, 'argv', argv), patch.dict(os.environ, clean_env(), clear=True):
        lidar_checks.main()
    assert json.loads((prepared/'manifest.json').read_bytes())['pose_trace'] is True
    live = root/'mock-run'
    manifest, _, _, commands = capture_launch(lidar_checks, live, map_method='fine', pose_trace=True)
    record = json.loads(manifest)
    assert record['pose_trace'] is True and record['pose_trace_limit_bytes'] == trace.TRACE_LIMIT_BYTES < 20_000_000
    case, = [row for row in record['cases'] if row['selected']]
    trace_dir = live/case['run_folder']/'pose_trace'
    for args in commands[-2:]:
        assert 'pose_trace_dir:=<output>/'+case['run_folder']+'/pose_trace' in args
    assert {p.name for p in trace_dir.iterdir()} == {'observer_pose.csv', 'cpu.csv'}

    docker = root/'docker'
    docker.write_text('#!/bin/bash\nprintf "%s\\0" "$@" > "$TASK058_ARGV"\n')
    docker.chmod(0o755)
    signature = root/'argv'
    env = dict(clean_env(), PATH=f'{root}:{os.environ["PATH"]}', THESIS_RENDER='cpu', TASK058_ARGV=str(signature))
    subprocess.run(['bash', str(LAUNCHER), str(root/'wrapped'), '--map', 'fine', '--pose-trace'], check=True, env=env)
    assert signature.read_bytes().split(b'\0')[-2:] == [b'--pose-trace', b'']

    folder = root/'bounded'
    file = folder/'follower_tick.csv'
    writer = trace.TraceCsv(file, trace.TICK_FIELDS, 180)
    for index in range(60):
        writer.write(index*NS, NS, 120, int(index == 59), None)
    writer.close()
    recent = inspect.read_trace(folder, 'follower_tick', trace.TICK_FIELDS)
    assert recent[-1]['pose_timeout'] == 1 and recent[-1]['mono_ns'] == 59*NS
    assert len(recent) < 60 and len(list(folder.iterdir())) == 2
    assert all(path.stat().st_size <= 180 for path in folder.iterdir())

    node = SimpleNamespace(last_status='running')
    node.tick = lambda: None
    measured, tick_log = trace.trace_tick(root/'duration', node, None)
    with patch('time.monotonic_ns', side_effect=(NS, NS+2_000_000, 2*NS, 2*NS+3_000_000)):
        measured()
        measured()
    tick_log.close()
    data = inspect.read_trace(root/'duration', 'follower_tick', trace.TICK_FIELDS)
    assert [row['duration_ns'] for row in data] == [2_000_000, 3_000_000]
    assert data[1]['interval_ns'] == NS

    sampler = trace.CpuSampler.__new__(trace.CpuSampler)
    sampler.stop = SimpleNamespace(wait=lambda _: next(samples))
    sampler.trace = trace.TraceCsv(folder/'cpu.csv', trace.CPU_FIELDS, trace.CPU_FILE_BYTES)
    samples = iter((False, True))
    with patch.object(trace, 'cpu_ticks', side_effect=((100, 70), (200, 100))), \
            patch('os.getloadavg', return_value=(2.5, 2.3, 2.1)):
        sampler._sample()
    sampler.trace.close()
    row, = inspect.read_trace(folder, 'cpu', trace.CPU_FIELDS, floats=trace.CPU_FIELDS[1:])
    assert row['cpu_pct'] == 70. and row['load1'] == 2.5
    print('3 PASS: CLI/manifest, ROS trace destinations, fake Docker, bounded CSV rollover and CPU sample')


if __name__ == '__main__':
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        test_default_bytes(root)
        test_inspector(root)
        test_wiring_and_limits(root)
    print('all task058 pose trace tests passed')
