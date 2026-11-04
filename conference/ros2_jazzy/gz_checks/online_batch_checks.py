"""Twenty paired Gazebo trials; transient maps/worlds, durable measured telemetry."""

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tapp.config import RESOLUTION
from tapp.mapfile import scenario_to_mapfile
from tapp.run_log import FIELDS
from data_prep.export_gazebo import export_gazebo
from data_prep.export_maps import LAS_ATTRIBUTION
from ros2_jazzy.gz_checks.online_batch_runtime import (
    PLANNERS, MODES, scenario_cases, case_metadata, CsvChunks, split_follower_logs,
)

OUT = ROOT / 'results/gazebo_online'
TERMINAL = {'completed', 'stuck', 'no_path', 'pose_timeout', 'invalid_mission', 'time_reset', 'map_mismatch'}


def save_manifest(output, manifest):
    (Path(output) / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')


def prepare_cases(output, planner=PLANNERS[0], *, scenarios=None):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'manifest.json').exists():
        raise FileExistsError('choose a new output; existing recordings are never overwritten')
    cases = scenario_cases(planner) if scenarios is None else scenarios
    manifest = dict(dataset='shizuoka_beach_las', split='test', side_m=200, seed=0,
                    planner=planner, sense_radius_m=10, world_max_pixels=4097,
                    execution='not_started',
                    sensing='perfect radius visibility of traversability labels; no LiDAR, occlusion or error',
                    scenarios=[case_metadata(sc) for sc in cases],
                    cases=[dict(patch=sc['patch'], mode=mode, planning_status=sc['planning_status'],
                                run_folder=None, termination=None, error='') for sc in cases for mode in MODES])
    save_manifest(output, manifest)
    return manifest, cases


def run_checks(output, planner=PLANNERS[0]):
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from geometry_msgs.msg import PoseArray, Twist
    from rosgraph_msgs.msg import Clock
    from std_msgs.msg import String, Empty
    from thesis_bunker_gz.model import make_model
    from thesis_bunker_mission.transport import pose3d

    output = Path(output).resolve()
    manifest, scenarios = prepare_cases(output, planner)
    manifest.update(execution='started', environment=dict(
        image=os.environ.get('THESIS_ROS_IMAGE', 'thesis/jazzy-gz:1'),
        gazebo=subprocess.check_output(['gz', 'sim', '--versions'], text=True).strip(), python=sys.version,
        numpy=np.__version__))
    save_manifest(output, manifest)

    class Observer(Node):
        def __init__(self, folder, online):
            super().__init__('online_batch_observer')
            self.t = self.pose = self.state = None
            self.v = self.w = 0.
            self.recording = False
            self.collecting_plans = False
            self.previous_path = None
            self.logged_plans = set()
            self.trace = CsvChunks(folder / 'trajectory.csv', FIELDS)
            self.plans = CsvChunks(folder / ('plans_observed.csv' if online else 'plans.csv'),
                                   ['n_plans', 'reason', 'success', 'plan_time_s'])
            self.replans = CsvChunks(folder / 'replans.csv', ['t', 'reason', 'revision', 'leg_index', 'n_replans', 'plan_time_s'])
            self.paths = CsvChunks(folder / 'path_revisions.csv', ['t', 'path'])
            self.create_subscription(Clock, '/clock', self.clock, qos_profile_sensor_data)
            self.create_subscription(PoseArray, '/ground_truth', self.ground, qos_profile_sensor_data)
            self.create_subscription(String, '/mission/state', self.status, 10)
            self.create_subscription(String, '/mission/online_command', self.plan, 10)
            self.create_subscription(Twist, '/cmd_vel', self.velocity, 10)
            self.command = self.create_publisher(String, '/mission/command', 10)
            self.stop = self.create_publisher(Empty, '/mission/stop', 10)

        def clock(self, msg):
            self.t = msg.clock.sec + msg.clock.nanosec / 1e9

        def ground(self, msg):
            if msg.poses:
                self.pose = pose3d(msg.poses[0])
                if self.recording and self.t is not None:
                    self.trace.write(dict(zip(FIELDS, [self.t, *self.pose, self.v, self.w])))

        def velocity(self, msg):
            self.v, self.w = msg.linear.x, msg.angular.z

        def status(self, msg):
            self.state = json.loads(msg.data)
            path = self.state.get('current_path')
            if self.recording and path and path != self.previous_path:
                self.paths.write(dict(t=self.state['sim_time'], path=json.dumps(path)))
                self.previous_path = path

        def plan(self, msg):
            if not self.collecting_plans:
                return
            command = json.loads(msg.data)
            for event in command.get('plan_history', []):
                if event['n_plans'] not in self.logged_plans:
                    self.plans.write(event)
                    self.logged_plans.add(event['n_plans'])
            if command.get('replace_path'):
                self.replans.write(dict(t=command.get('planned_at', self.t),
                                       **{k: command[k] for k in ['reason', 'revision', 'leg_index', 'n_replans', 'plan_time_s']}))

        def wait_until(self, predicate, processes, wall_limit=120):
            deadline = time.monotonic() + wall_limit
            while not predicate():
                if any(p.poll() is not None for p in processes):
                    raise RuntimeError('a Gazebo/ROS process exited; inspect process logs')
                if time.monotonic() > deadline:
                    raise TimeoutError('missing or stalled ROS/Gazebo telemetry')
                rclpy.spin_once(self, timeout_sec=.05)

        def close(self):
            for writer in [self.trace, self.plans, self.replans, self.paths]:
                writer.close()
            self.destroy_node()

    rclpy.init()
    try:
        with tempfile.TemporaryDirectory(prefix='thesis-gz-online-batch-') as temporary:
            transient = Path(temporary)
            for sc, metadata in zip(scenarios, manifest['scenarios']):
                paired = [c for c in manifest['cases'] if c['patch'] == sc['patch']]
                if sc['planning_status'] != 'planned':
                    continue
                folder = transient / sc['patch']
                folder.mkdir()
                truth_file, prior_file = folder / 'truth.npz', folder / 'prior.npz'
                try:
                    # Debris changes elevations after the nodata fill: store that surface (as task014's export_stale_map).
                    scenario_to_mapfile(dict(sc['truth'], raw_elev=sc['truth']['tmap'].elev), truth_file, sc['patch'] + '_debris', sc['patch'], 'task021 LAS Ground, test, seed=0, debris (truth)', LAS_ATTRIBUTION)
                    scenario_to_mapfile(sc['clean'], prior_file, sc['patch'], sc['patch'], 'task021 LAS Ground, test, seed=0, clean (stale prior)', LAS_ATTRIBUTION)
                    export_gazebo(truth_file, folder / 'world', max_pixels=4097)
                except Exception as exc:
                    for case in paired:
                        case['error'] = 'world export: ' + type(exc).__name__ + ': ' + str(exc)
                    save_manifest(output, manifest)
                    continue
                for case in paired:
                    raw = output / 'raw' / (sc['patch'] + '_' + case['mode'])
                    raw.mkdir(parents=True)
                    case['run_folder'] = str(raw.relative_to(output))
                    observer = Observer(raw, case['mode'] == 'online')
                    processes, streams = [], []
                    mission = dict(id=1, map_id='file/' + truth_file.name, data_source='gazebo',
                                   patch=sc['patch'], mode=case['mode'], planner=planner, path=metadata['initial_path'],
                                   points=(np.asarray(sc['points']) * RESOLUTION).tolist(), order=metadata['order'],
                                   stops_cells=metadata['stops'], start_cells=sc['start'], lookahead_m=1., status='not_started')
                    def save_run():
                        (raw / 'mission.json').write_text(json.dumps(mission, ensure_ascii=False, indent=2) + '\n')
                    save_run()
                    try:
                        with tempfile.TemporaryDirectory(prefix='thesis-gz-online-run-') as run_tmp:
                            runtime = Path(run_tmp)
                            world = folder / 'world/world.sdf'
                            tree = ET.parse(world)
                            w = tree.find('world')
                            w.find('physics/real_time_factor').text = '1'
                            for uri in tree.findall('.//heightmap/uri'):
                                uri.text = (world.parent / 'heightmap.png').as_uri()
                            model = ET.parse(make_model(runtime / 'bunker.sdf', mass_kg=sc['truth']['tmap'].robot.mass_kg)).find('model')
                            x, y = np.asarray(sc['start']) * RESOLUTION
                            z = float(sc['truth']['tmap'].elev[tuple(sc['start'])]) + .1
                            ET.SubElement(model, 'pose').text = f'{x} {y} {z} 0 0 0'
                            w.append(model)
                            tree.write(runtime / 'world.sdf', encoding='utf-8', xml_declaration=True)
                            commands = [
                                ['gz', 'sim', '-s', '-r', '--seed', '0', str(runtime / 'world.sdf')],
                                ['ros2', 'run', 'ros_gz_bridge', 'parameter_bridge', '--ros-args', '-p',
                                 'config_file:=' + str(ROOT / 'ros2_jazzy/src/thesis_bunker_gz/config/bridge.yaml')],
                                ['ros2', 'run', 'thesis_bunker_mission', 'path_follower', '--ros-args', '-p',
                                 'use_sim_time:=true', '-p', 'online:=' + str(case['mode'] == 'online').lower(), '-p',
                                 'map_id:=' + mission['map_id'], '-p', 'run_root:=' + str(raw / 'follower')]]
                            if case['mode'] == 'online':
                                commands.append([sys.executable, str(ROOT / 'ros2_jazzy/gz_checks/online_batch_planner.py'),
                                                 '--ros-args', '-p', 'use_sim_time:=true', '-p', 'truth_map:=' + str(truth_file),
                                                 '-p', 'prior_map:=' + str(prior_file), '-p', 'planner:=' + planner,
                                                 '-p', 'plan_log:=' + str(raw / 'plans.csv')])
                            for i, command in enumerate(commands):
                                stream = (raw / f'process_{i}.txt').open('w')
                                streams.append(stream)
                                processes.append(subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True))
                            observer.wait_until(lambda: observer.t is not None and observer.pose is not None and
                                                observer.state is not None and observer.command.get_subscription_count() > 0,
                                                processes)
                            settled = observer.t + 5
                            observer.wait_until(lambda: observer.t >= settled, processes)
                            mission.update(started_t=observer.t, start_pose=observer.pose, status='running')
                            save_run()
                            observer.recording = True
                            observer.collecting_plans = True
                            if case['mode'] == 'fixed':
                                observer.paths.write(dict(t=observer.t, path=json.dumps(mission['path'])))
                                for i, seconds in enumerate(metadata['fixed_plan_times'], 1):
                                    observer.plans.write(dict(n_plans=i, reason='start_leg', success=True, plan_time_s=seconds))
                            message = String()
                            message.data = json.dumps(mission)
                            observer.command.publish(message)
                            distance = float(np.linalg.norm(np.diff(np.asarray(mission['path']), axis=0), axis=1).sum())
                            limit = max(120, 6 * distance + 60)
                            def done():
                                return ((observer.state.get('mission_id') == 1 and observer.state['status'] in TERMINAL)
                                        or observer.t - mission['started_t'] > limit)
                            observer.wait_until(done, processes, wall_limit=max(180, limit * 3))
                            case['termination'] = ('simulation_timeout' if observer.t - mission['started_t'] > limit
                                                   else observer.state['status'])
                            mission.update(status=case['termination'], finished_t=observer.t, final_state=observer.state)
                            save_run()
                            observer.recording = False
                            observer.stop.publish(Empty())
                            ended = observer.t + .2
                            observer.wait_until(lambda: observer.t >= ended, processes, wall_limit=10)
                            print(sc['patch'], case['mode'], case['termination'], flush=True)
                    except Exception as exc:
                        case['error'] = type(exc).__name__ + ': ' + str(exc)
                        if mission['status'] in TERMINAL | {'simulation_timeout'}:
                            mission['cleanup_error'] = case['error']
                        else:
                            mission.update(status='runtime_error', finished_t=observer.t, error=case['error'])
                        save_run()
                    finally:
                        for process in reversed(processes):
                            if process.poll() is None:
                                os.killpg(process.pid, signal.SIGINT)
                                try:
                                    process.wait(timeout=10)
                                except subprocess.TimeoutExpired:
                                    os.killpg(process.pid, signal.SIGKILL)
                                    process.wait()
                        for stream in streams:
                            stream.close()
                        observer.close()
                        split_follower_logs(raw)
                        save_manifest(output, manifest)
        manifest['execution'] = 'finished_with_errors' if any(c['error'] for c in manifest['cases']) else 'finished'
        save_manifest(output, manifest)
        from experiments.gz_online_batch_report import summarize
        summarize(output)
        if manifest['execution'] == 'finished_with_errors':
            raise RuntimeError('some trials failed to run; inspect manifest and process logs')
    finally:
        rclpy.shutdown()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUT)
    parser.add_argument('--planner', choices=PLANNERS, default=PLANNERS[0])
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    if args.prepare_only:
        prepare_cases(args.output, args.planner)
        from experiments.gz_online_batch_report import summarize
        summarize(args.output)
    else:
        run_checks(args.output, args.planner)


if __name__ == '__main__':
    main()
