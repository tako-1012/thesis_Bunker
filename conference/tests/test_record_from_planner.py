"""Verify task083 using the actual callback, local sockets and the 075/077 archive."""

from concurrent.futures import Future
import json
from pathlib import Path
from shutil import copytree
import socket
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Event, Thread
from types import ModuleType, SimpleNamespace as S
from unittest.mock import patch

import numpy as np

from experiments.recording_bridge import open_archive
from ros2_jazzy.gz_checks import lidar_checks, sensor_recorder
from tapp.sensor_geometry import sensor_configuration
from tapp.sensor_recording import SensorArchive, iter_lidar
from tapp.traversability import TraversabilityMap
from tests import test_overlap_goal as baseline
from tests import test_waypoint_feasibility as launcher
from tests.test_landmark_world import scenario
from tests.test_pose_error import header, load_source, truth

BASE = 'b0dd82ea2420b56ce48305854422d6a2c96c97f3'
PLANNER = lidar_checks.ROOT/'ros2_jazzy/gz_checks/lidar_planner.py'
XYZ = np.array([[2.001, .105, -.103], [3.341, .303, .022]])
FIELDS = [S(name=name, offset=i*4, datatype=7, count=1) for i, name in enumerate('xyz')]


def cloud(ns, *, frame='lidar', xyz=XYZ):
    h = header(ns/1e9)
    h.frame_id = frame
    data = np.asarray(xyz, dtype='>f4').tobytes()+b'padding!'
    return S(header=h, width=2, height=1, point_step=12, row_step=32,
             is_bigendian=True, data=data, fields=FIELDS)


def serialize(message):
    stamp, frame = sensor_recorder.header(message)
    encoded = frame.encode()
    return struct.pack('!qH', stamp, len(encoded))+encoded+message.data


def deserialize(payload, message_type):
    stamp, length = struct.unpack('!qH', payload[:10])
    start = 10+length
    message = cloud(stamp, frame=payload[10:start].decode())
    message.data = payload[start:start+32]
    return message


class ImmediatePool:
    def __init__(self, max_workers):
        pass

    def submit(self, function, *args):
        future = Future()
        try:
            future.set_result(function(*args))
        except Exception as exc:
            future.set_exception(exc)
        return future

    def shutdown(self, wait):
        pass


class FakeRos:
    def __init__(self, folder):
        self.folder = folder
        self.nodes = {}
        self.ready, self.stop = Event(), Event()
        self.errors = []

    def stubs(self):
        harness = self

        class Node:
            def __init__(self, name):
                self.timers, self.subscriptions, self.published = [], {}, {}
                self.params = (dict(run_folder=str(harness.folder), map_method='fine', sensors='lidar_real+depth2')
                               if name == 'lidar_planner' else {})
                self.clock_ns = 1_400_000_000
                self.pose_callbacks = []
                harness.nodes[name] = self

            def declare_parameter(self, name, default):
                self.params.setdefault(name, default)

            def get_parameter(self, name):
                return S(value=self.params[name])

            def create_subscription(self, kind, topic, callback, qos):
                assert topic not in self.subscriptions
                self.subscriptions[topic] = callback

            def create_publisher(self, kind, topic, depth):
                self.published[topic] = []
                return S(publish=lambda msg: self.published[topic].append(msg.data))

            def create_timer(self, interval, callback):
                self.timers.append(callback)

            def get_clock(self):
                return S(now=lambda: S(nanoseconds=self.clock_ns))

            def destroy_node(self):
                pass

            def on_pose(self, message):
                self.pose_callbacks.append(message)

        class ExternalShutdownException(Exception):
            pass

        return {'rclpy': S(init=lambda **kw: None, spin=self.spin, try_shutdown=lambda: None),
                'rclpy.node': S(Node=Node),
                'rclpy.qos': S(QoSProfile=S, ReliabilityPolicy=S(BEST_EFFORT=1), qos_profile_sensor_data=object()),
                'rclpy.serialization': S(serialize_message=serialize, deserialize_message=deserialize),
                'rclpy.executors': S(ExternalShutdownException=ExternalShutdownException),
                'geometry_msgs.msg': S(PoseArray=object), 'sensor_msgs.msg': S(Imu=object, PointCloud2=object),
                'std_msgs.msg': S(String=S, Empty=object), 'nav_msgs.msg': S(Path=object),
                'thesis_bunker_mission.online_planner': S(OnlinePlannerNode=Node)}

    def load_planner(self, *, before=None, **options):
        if before is None:
            module = load_source('lidar_planner_083_fixture', PLANNER)
        else:
            module = ModuleType('lidar_planner_083_base')
            module.__file__ = str(PLANNER)
            exec(compile(before, str(PLANNER), 'exec'), vars(module))
        blank = np.zeros((20, 20), bool)
        prior = dict(tmap=TraversabilityMap(np.zeros(blank.shape), blank), obstacle=blank, nodata=blank, water=blank)
        runtime = S(close=lambda: None, version=0)
        with patch.object(module, 'load_map_file', return_value=prior), patch.object(
                module, 'make_lidar_runtime', return_value=runtime), patch.object(
                module, 'ThreadPoolExecutor', ImmediatePool), patch.object(module, 'time', S(perf_counter=lambda: 5.)):
            node = module.LidarPlannerNode(**options)
        module.time = S(perf_counter=lambda: 5.)
        node.poses.add(1., np.zeros(6))
        return node

    def spin(self, node):
        covariance = [0.]*9
        vector = S(x=0., y=0., z=0., w=1.)
        node.subscriptions['/imu'](S(header=header(1.), orientation=vector, angular_velocity=vector,
                                     linear_acceleration=vector, orientation_covariance=covariance,
                                     angular_velocity_covariance=covariance, linear_acceleration_covariance=covariance))
        node.subscriptions['/ground_truth'](truth(1., 0., 0.))
        self.ready.set()
        while not self.stop.is_set():
            for timer in node.timers:
                timer()
            self.stop.wait(.002)

    def start_recorder(self, fd, *options):
        def run():
            argv = ['sensor_recorder', str(self.folder/'sensors'), '--lidar-fd', str(fd), *options]
            try:
                with patch.object(sys, 'argv', argv):
                    sensor_recorder.main()
            except Exception as exc:
                self.errors.append(exc)

        worker = Thread(target=run, daemon=True)
        worker.start()
        assert self.ready.wait(5.), self.errors
        return worker

    def finish_recorder(self, worker):
        self.stop.set()
        worker.join(timeout=7.)
        assert not worker.is_alive() and not self.errors, self.errors


def update(node, stamp, **options):
    message = cloud(stamp, **options)
    stamp_seconds = node.stamp(message)
    node.poses.add(stamp_seconds, np.zeros(6))
    node.subscriptions['/lidar/points'](message)
    for _ in range(3):
        node.map_tick()
    assert node.source_state['lidar']['last_stamp'] == stamp_seconds


def test_default(root):
    with patch.object(baseline, 'BASE', BASE):
        old, = baseline.load_before(lidar_checks)
    source = subprocess.check_output(
        ['git', 'show', f'{BASE}:{PLANNER.relative_to(lidar_checks.ROOT.parent)}'], cwd=lidar_checks.ROOT.parent)

    def run(folder, **options):
        stub = FakeRos(folder)
        with patch.dict(sys.modules, stub.stubs()):
            node = stub.load_planner(**options)
            update(node, 1_100_000_000)
            node.close()
        return node.published, {p.name: p.read_bytes() for p in folder.iterdir()}

    assert run(root/'node-old', before=source) == run(root/'node-new')
    for options in ({}, dict(map_method='fine', sensors='lidar_real+depth2', pose_trace=True)):
        run_name = 'fine' if options else 'coarse'
        a, b = [root/f'launch-{run_name}-{suffix}' for suffix in ('old', 'new')]
        assert launcher.capture_launch(old, a, **options) == launcher.capture_launch(lidar_checks, b, **options)
        files = lambda path: {p.relative_to(path): p.read_bytes() for p in path.rglob('*') if p.is_file()}
        assert files(a) == files(b)
    print('1 PASS: same-host previous/default planner products, messages, launch and manifest bytes')


def write_extrinsic(folder):
    (folder/'manifest.json').write_text(json.dumps(
        dict(sensor_configuration=sensor_configuration('lidar_real+depth2'))))


def test_roundtrip(root):
    harness = FakeRos(root)
    send, receive = socket.socketpair()
    with patch.dict(sys.modules, harness.stubs()):
        node = harness.load_planner(record_lidar_fd=send.detach())
        worker = harness.start_recorder(receive.detach())
        try:
            update(node, 1_100_000_000)
            node.on_cloud(cloud(1_150_000_000, frame='camera1'), 'camera1')
            update(node, 1_200_000_000, frame='bunker/lidar', xyz=XYZ+1)
        finally:
            node.close()
            harness.finish_recorder(worker)
    write_extrinsic(root)
    record = open_archive(root)
    np.testing.assert_array_equal(record.lidar_stamp_ns, [1_100_000_000, 1_200_000_000])
    np.testing.assert_array_equal(record.imu_stamp_ns, [1_000_000_000])
    np.testing.assert_array_equal(record.truth_stamp_ns, [1_000_000_000])
    metadata = json.loads((root/'sensors/metadata.json').read_text())
    assert metadata['lidar_queue_drops'] == 0 and metadata['status'] == 'finished'
    scans = list(iter_lidar(root/'sensors'))
    assert [scan.frame_id for scan in scans] == ['lidar', 'bunker/lidar']
    assert all(scan.xyz.shape == (1, 2, 3) for scan in scans)
    errors_mm = np.linalg.norm(np.concatenate([scans[0].xyz-XYZ, scans[1].xyz-(XYZ+1)]), axis=-1)*1000
    assert errors_mm.max() <= 1.
    assert set(harness.nodes['thesis_sensor_recorder'].subscriptions) == {'/imu', '/ground_truth'}
    print(f'2 PASS: 077 opens three streams, exact nanosecond stamps and max XYZ error {errors_mm.max():.3f} mm')


def test_backpressure(root):
    entered, release, mapped = Event(), Event(), Event()
    harness = FakeRos(root)
    send, receive = socket.socketpair()
    send.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
    frames = 30
    real_flush = SensorArchive.flush
    real_serialize = serialize

    def slow_flush(archive):
        entered.set()
        assert release.wait(8.)
        real_flush(archive)

    def fat_payload(message):
        return real_serialize(message)+bytes(450_000)

    errors = []
    with patch.dict(sys.modules, harness.stubs()), patch.object(
            sys.modules['rclpy.serialization'], 'serialize_message', fat_payload), patch.object(
            SensorArchive, 'flush', slow_flush), patch('tapp.sensor_recording.SCANS_PER_CHUNK', 1):
        node = harness.load_planner(record_lidar_fd=send.detach())
        worker = harness.start_recorder(receive.detach())

        def map_while_blocked():
            try:
                for i in range(1, frames+1):
                    update(node, 1_100_000_000+i*1_000_000)
                mapped.set()
            except Exception as exc:
                errors.append(exc)

        try:
            update(node, 1_100_000_000)
            assert entered.wait(5.)
            mapper = Thread(target=map_while_blocked, daemon=True)
            mapper.start()
            assert mapped.wait(5.), errors
            assert not release.is_set()
            assert node.source_state['lidar']['processed'] == frames+1
        finally:
            release.set()
            node.close()
            harness.finish_recorder(worker)
    meta = json.loads((root/'sensors/metadata.json').read_text())
    assert meta['status'] == 'finished'
    assert meta['lidar_queue_drops'] > 0
    assert meta['received']['lidar'] == meta['saved']['lidar'] == frames+1-meta['lidar_queue_drops']
    print(f'3 PASS: {frames+1} map updates while recording was blocked, '
          f'{meta["lidar_queue_drops"]} recording-only drops counted exactly')


def test_record_enabled_launch(root, sensor_fixture):
    baseline_cases = launcher.archive_scenarios()
    baseline_cases[0].update(start=[5, 5], points=[[8, 8]], stops=[[8, 8], [5, 5]],
                             initial_path=[[2.5, 2.5], [4., 4.], [2.5, 2.5]], order=[0, 1])
    sc = scenario(np.zeros((30, 30)))

    def fake_world(raw, *_):
        # Substitute the recorder child with the archive from the socket test.
        copytree(sensor_fixture, raw/'sensors')
        return sc, sc, []

    with patch.object(launcher, 'fixture', return_value=sc), patch.object(
            launcher, 'trial_scenarios', return_value=baseline_cases), patch.object(
            lidar_checks, 'add_landmark_world', side_effect=fake_world):
        manifest, _, _, commands = launcher.capture_launch(
            lidar_checks, root, map_method='fine', record_sensors=True, record_sensors_seconds=120.,
            pose_error='bias', pose_error_bias=(.2, .4, 0.))
    assert json.loads(manifest)['sensor_recording']['lidar_source'] == 'lidar_planner.on_cloud'
    planner, relay, recorder = commands[-3:]
    assert planner[1].endswith('lidar_planner.py') and relay[1].endswith('pose_error_relay.py')
    assert recorder[1].endswith('sensor_recorder.py') and recorder[-2:] == ['--seconds', '120.0']
    send_fd = int(planner[planner.index('--record-lidar-fd')+1])
    recv_fd = int(recorder[recorder.index('--lidar-fd')+1])
    assert send_fd != recv_fd
    print('4 PASS: launch selects the planner feed, with a separate recorder subscribing only to IMU and ground truth')


def test_limits(root, byte_limit):
    harness = FakeRos(root)
    send, receive = socket.socketpair()
    options = [] if byte_limit else ['--seconds', '.15']
    archive_arguments = {'limit_bytes': 5_000} if byte_limit else {}
    with patch.dict(sys.modules, harness.stubs()), patch.object(
            sensor_recorder, 'SensorArchive', side_effect=lambda *args, **kwargs:
            SensorArchive(*args, **kwargs, **archive_arguments)), patch('tapp.sensor_recording.SCANS_PER_CHUNK', 1):
        node = harness.load_planner(record_lidar_fd=send.detach())
        worker = harness.start_recorder(receive.detach(), *options)
        try:
            update(node, 1_100_000_000)
            update(node, 1_200_000_000)
            recording = node.lidar_recording
            # Wait for the limit to close the producer before stopping the mission.
            recording.thread.join(timeout=5.)
            assert not recording.thread.is_alive()
            update(node, 1_300_000_000)
            assert node.source_state['lidar']['processed'] == 3
        finally:
            node.close()
            harness.finish_recorder(worker)
    folder = root/'sensors'
    metadata = json.loads((folder/'metadata.json').read_text())
    assert metadata['status'] == ('byte_limit' if byte_limit else 'duration_limit')
    assert metadata['saved']['lidar'] == 1 and metadata['lidar_queue_drops'] == 0
    assert sum(p.stat().st_size for p in folder.iterdir()) <= metadata['limit_bytes']
    assert metadata['end_ns'] == 1_100_000_000
    print(f'limit PASS: {metadata["status"]}, exactly one scan retained and later planner update still succeeds')


def main():
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        test_default(root)
        test_roundtrip(root/'roundtrip')
        test_backpressure(root/'blocked')
        test_record_enabled_launch(root/'launch', root/'roundtrip'/'sensors')
        test_limits(root/'time-limit', byte_limit=False)
        test_limits(root/'byte-limit', byte_limit=True)
    print('all record-from-planner tests passed')


if __name__ == '__main__':
    main()
