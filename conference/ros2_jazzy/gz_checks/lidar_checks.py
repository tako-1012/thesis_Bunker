"""Experimental 3-then-10 LiDAR trials using task021's exact saved scenario cohort."""

import argparse
from dataclasses import asdict
import hashlib
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
sys.path.insert(0, str(ROOT/'ros2_jazzy/src/thesis_bunker_gz'))
from thesis_bunker_gz.lidar import LidarSpec
from tapp.sensor_geometry import SENSOR_MODES, sensor_configuration
from tapp.config import RESOLUTION
from tapp.pointcloud_map_fine import GROUND_ESTIMATES
from tapp.endpoint_policy import ENDPOINT_POLICIES
from tapp.real_beach import build_real, list_patches
from tapp.mapfile import scenario_to_mapfile
from tapp.run_log import FIELDS
from data_prep.export_maps import LAS_ATTRIBUTION
from data_prep.export_gazebo import export_gazebo
from ros2_jazzy.gz_checks.terrain_mesh import write_terrain_obj, use_mesh_visual
from ros2_jazzy.gz_checks.online_batch_runtime import CsvChunks, map_signature, split_follower_logs
from ros2_jazzy.gz_checks.online_batch_checks import TERMINAL, save_manifest
from ros2_jazzy.gz_checks.lidar_map import fine_protocol, matched_task022_maps, sensor_bridge_config

BASELINE = ROOT/'results/gazebo_online/physical_run'


def verify_inputs(patch, meta, truth, prior):
    """Require identical LAS bytes and masks; disclose historical floating hashes.

    Task021 used NumPy1.26.4; newer NumPy can change debris height bits. Never
    relabel cached control values or claim bitwise historical height equality.
    """
    protocol = json.loads((BASELINE.parent/'verification/protocol.json').read_text())
    for name in ['tapp/config.py', 'tapp/real_beach.py', 'tapp/traversability.py', 'tapp/online_mission.py', 'tapp/footprint.py']:
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != protocol['source_sha256'][name]:
            raise ValueError('task021 map/planner parameters changed: '+name)
    expected = protocol['data_sha256'][patch]
    actual = hashlib.sha256((ROOT/'data/shizuoka_beach_las'/(patch+'.npz')).read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError('LAS source changed: '+patch)
    signatures = dict(truth=map_signature(truth), prior=map_signature(prior))
    for name, signature in signatures.items():
        reference = meta['truth_signature' if name == 'truth' else 'prior_signature']
        if any(signature[key] != reference[key] for key in ['lethal', 'rock']):
            raise ValueError('task021 obstacle/lethal masks changed: '+patch+' '+name)
        if name == 'prior' and signature['elev'] != reference['elev']:
            raise ValueError('stale prior height changed: '+patch)
    return dict(patch=patch, las_sha256=actual, signatures=signatures,
                historical_truth_elevation_equal=signatures['truth']['elev'] == meta['truth_signature']['elev'],
                note='If historical elevation SHA differs, its magnitude is unknown without the old transient grid; masks/LAS match.')


def prepare_cases(output, *, patch_count=3, sensor_height_m=.8, obstacle_height_m=.3,
                  noise_stddev_m=.02, max_range_m=30., map_method='coarse', sensors='legacy', endpoint_policy='none', diagnostics=False,
                  ground_estimate='all_returns'):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output/'manifest.json').exists():
        raise FileExistsError('choose a new output; no existing recordings will be overwritten')
    if patch_count not in (3, 10):
        raise ValueError('run the first three beaches before extending to ten')
    if ground_estimate not in GROUND_ESTIMATES:
        raise ValueError('unknown ground estimate')
    if ground_estimate != 'all_returns' and map_method != 'fine':
        raise ValueError('non_obstacle ground estimate requires --map fine')
    if endpoint_policy not in ENDPOINT_POLICIES:
        raise ValueError('unknown endpoint policy')
    if (endpoint_policy != 'none' or diagnostics) and map_method != 'fine':
        raise ValueError('task028 requires --map fine')
    configuration = sensor_configuration(sensors)
    if configuration is not None:
        if map_method != 'fine':
            raise ValueError('real sensors require --map fine')
        if noise_stddev_m != .02 or max_range_m != 30. or sensor_height_m not in (.8, 1.4) or obstacle_height_m != .3:
            raise ValueError('task027 fixes the real sensor specification and threshold')
        sensor_height_m = 1.4
    spec = LidarSpec(noise_stddev_m=noise_stddev_m, max_range_m=max_range_m,
                     **({'min_range_m': .9} if configuration is not None else {}))
    spec.validate()
    if not np.isfinite([sensor_height_m, obstacle_height_m]).all() or min(sensor_height_m, obstacle_height_m) <= 0:
        raise ValueError('height assumptions must be positive')
    if map_method not in ('coarse', 'fine'):
        raise ValueError('map method must be coarse or fine')
    fine_settings = fine_protocol() if map_method == 'fine' else None
    if fine_settings is not None and configuration is None:
        reference = json.loads((ROOT/'results/gazebo_lidar/physical_10/manifest.json').read_text())
        if (asdict(spec) != reference['lidar_spec'] or sensor_height_m != reference['sensor_height_m']
                or obstacle_height_m != .3 or obstacle_height_m != reference['obstacle_height_m']):
            raise ValueError('fine comparison keeps the task022 sensor and threshold unchanged')
    baseline = json.loads((BASELINE/'manifest.json').read_text())
    scenarios = baseline['scenarios']
    expected = [r['name'] for r in list_patches('test', dataset='shizuoka_beach_las')[:10]]
    if [s['patch'] for s in scenarios] != expected:
        raise ValueError('baseline must contain the same first ten LAS test beaches')
    only_patch = os.environ.get('THESIS_ONLY_PATCH') if os.environ.get('THESIS_FINE_PROTOCOL') == 'rtf_check' else None
    manifest = dict(dataset='shizuoka_beach_las', split='test', side_m=200, seed=0,
                    planner='TA*-S+inflate', sensor='lidar', patch_count=patch_count,
                    execution='not_started', world_max_pixels=4097,
                    lidar_spec=asdict(spec), sensor_height_m=sensor_height_m,
                    obstacle_height_m=obstacle_height_m,
                    obstacle_reference='stale prior DEM, bilinear; three high returns in a cell; uncalibrated assumption',
                    height_definition='median of last 64 returns per hit cell, including obstacle tops',
                    baseline='results/gazebo_online/physical_run', scenarios=scenarios,
                    input_environment=dict(python=sys.version, numpy=np.__version__),
                    cases=[dict(patch=s['patch'], mode='lidar', selected=(s['patch'] == only_patch if only_patch else i < patch_count),
                                planning_status=s['planning_status'], run_folder=None, error='', termination=None)
                           for i, s in enumerate(scenarios)])
    if fine_settings is not None:
        manifest.update(fine_settings)
    if configuration is not None:
        manifest.update(sensor=sensors, sensors=sensors, sensor_configuration=configuration,
                        experiment='task027 real sensors; not a matched task022/023 sensor comparison')
    if os.environ.get('THESIS_FINE_PROTOCOL'):
        manifest.update(protocol=os.environ['THESIS_FINE_PROTOCOL'], only_patch=only_patch,
                        software_rendering=os.environ.get('LIBGL_ALWAYS_SOFTWARE'))
    if endpoint_policy != 'none' or diagnostics:
        manifest.update(endpoint_policy=endpoint_policy, diagnostics=bool(diagnostics),
                        endpoint_protocol='task028; separate evaluation from task023')
    if ground_estimate != 'all_returns':
        # An absent field still means all_returns in historical/default runs.
        manifest.update(ground_estimate=ground_estimate,
                        height_definition='median of last 64 ALL returns with height minus bilinear stale-prior height < 0.3m; '
                                          'if none remain, retain stale-prior cell height; seen unchanged')
    save_manifest(output, manifest)
    return manifest


def run_checks(output, **kwargs):
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from geometry_msgs.msg import PoseArray, Twist
    from rosgraph_msgs.msg import Clock
    from std_msgs.msg import String, Empty
    from thesis_bunker_gz.model import make_model
    from thesis_bunker_mission.transport import pose3d

    output = Path(output).resolve()
    manifest = prepare_cases(output, **kwargs)
    # Slower simulation gives CPU-only GPU-LiDAR rendering time to keep up; physics is unchanged.
    if manifest.get('map_method') != 'fine':
        manifest['real_time_factor'] = float(os.environ.get('THESIS_REAL_TIME_FACTOR', '1'))
        manifest['stale_timeout_s'] = float(os.environ.get('THESIS_STALE_TIMEOUT_S', '0.5'))
    manifest.update(execution='started', environment=dict(
        image=os.environ.get('THESIS_ROS_IMAGE', 'thesis/jazzy-gz:1'),
        gazebo=subprocess.check_output(['gz', 'sim', '--versions'], text=True).strip(), python=sys.version))
    save_manifest(output, manifest)

    class Observer(Node):
        def __init__(self, folder):
            super().__init__('lidar_checks_observer')
            self.t = self.pose = self.state = self.perception = None
            self.v = self.w = 0.
            self.recording = False
            self.previous_path = None
            self.trace = CsvChunks(folder/'trajectory.csv', FIELDS)
            self.paths = CsvChunks(folder/'path_revisions.csv', ['t', 'path'])
            self.replans = CsvChunks(folder/'replans.csv', ['t', 'reason', 'revision', 'leg_index', 'n_replans', 'plan_time_s'])
            self.create_subscription(Clock, '/clock', self.clock, qos_profile_sensor_data)
            self.create_subscription(PoseArray, '/ground_truth', self.ground, qos_profile_sensor_data)
            self.create_subscription(Twist, '/cmd_vel', self.velocity, 10)
            self.create_subscription(String, '/mission/state', self.status, 10)
            self.create_subscription(String, '/mission/online_command', self.plan, 10)
            self.create_subscription(String, '/lidar/state', self.sensor, 10)
            self.command = self.create_publisher(String, '/mission/command', 10)
            self.stop = self.create_publisher(Empty, '/mission/stop', 10)

        def clock(self, msg):
            self.t = msg.clock.sec+msg.clock.nanosec/1e9

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

        def sensor(self, msg):
            self.perception = json.loads(msg.data)

        def plan(self, msg):
            command = json.loads(msg.data)
            if self.recording and command.get('replace_path'):
                self.replans.write(dict(t=command.get('planned_at', self.t),
                                       **{k: command[k] for k in ['reason', 'revision', 'leg_index', 'n_replans', 'plan_time_s']}))

        def wait_until(self, predicate, processes, wall_limit=120):
            deadline = time.monotonic()+wall_limit
            while not predicate():
                if any(p.poll() is not None for p in processes):
                    raise RuntimeError('a Gazebo/ROS process exited; inspect process logs')
                if time.monotonic() > deadline:
                    raise TimeoutError('no/stalled ROS, Gazebo, or LiDAR telemetry')
                rclpy.spin_once(self, timeout_sec=.05)

        def close(self):
            for writer in [self.trace, self.paths, self.replans]:
                writer.close()
            self.destroy_node()

    rclpy.init()
    try:
        with tempfile.TemporaryDirectory(prefix='thesis-lidar-worlds-') as temporary:
            for case, meta in zip(manifest['cases'], manifest['scenarios']):
                if not case['selected'] or case['planning_status'] != 'planned':
                    continue
                raw = output/'raw'/case['patch']
                raw.mkdir(parents=True)
                case['run_folder'] = str(raw.relative_to(output))
                observer = Observer(raw)
                processes, streams = [], []
                mission = dict(id=1, patch=case['patch'], mode='lidar', planner='TA*-S+inflate', data_source='gazebo',
                               map_id='file/truth.npz', path=meta['initial_path'], points=(np.asarray(meta['points'])*RESOLUTION).tolist(),
                               start_cells=meta['start'], stops_cells=meta['stops'], order=meta['order'], lookahead_m=1., status='not_started')
                def save_run():
                    (raw/'mission.json').write_text(json.dumps(mission, ensure_ascii=False, indent=2)+'\n')
                if manifest.get('sensors', 'legacy') != 'legacy':
                    mission['sensors'] = manifest['sensors']
                save_run()
                try:
                    folder = Path(temporary)/case['patch']
                    folder.mkdir()
                    truth = build_real(case['patch'], 200, 0, debris=True, dataset='shizuoka_beach_las')
                    prior = build_real(case['patch'], 200, 0, dataset='shizuoka_beach_las')
                    if manifest.get('map_method') == 'fine':
                        truth, prior, case['world_reference'] = matched_task022_maps(case['patch'], truth, prior)
                    case['input_audit'] = verify_inputs(case['patch'], meta, truth, prior)
                    # Evaluation arrays, not a deployable map/world: preserve the
                    # actual-run float bits for offline analysis on other CPUs.
                    np.savez_compressed(raw/'evaluation_reference.npz',
                                        truth_elev=truth['tmap'].elev, truth_lethal=truth['tmap'].lethal,
                                        truth_rock=truth['tmap'].rock, prior_elev=prior['tmap'].elev,
                                        prior_lethal=prior['tmap'].lethal, prior_rock=prior['tmap'].rock)
                    truth_file, prior_file = folder/'truth.npz', folder/'prior.npz'
                    scenario_to_mapfile(dict(truth, raw_elev=truth['tmap'].elev), truth_file, case['patch']+'_debris', case['patch'], 'task022 truth; no planner access', LAS_ATTRIBUTION)
                    scenario_to_mapfile(prior, prior_file, case['patch'], case['patch'], 'task022 stale prior', LAS_ATTRIBUTION)
                    export_gazebo(truth_file, folder/'world', max_pixels=4097)
                    world = folder/'world/world.sdf'
                    tree = ET.parse(world)
                    w = tree.find('world')
                    w.find('physics/real_time_factor').text = (str(manifest['real_time_factor']) if manifest.get('map_method') == 'fine'
                                                             else os.environ.get('THESIS_REAL_TIME_FACTOR', '1'))
                    for uri in tree.findall('.//heightmap/uri'):
                        uri.text = (world.parent/'heightmap.png').as_uri()
                    # GPU LiDAR sees visuals only; the heightmap visual crashes ogre2 without a GPU.
                    use_mesh_visual(tree, write_terrain_obj(truth['tmap'].elev, folder/'terrain.obj').resolve().as_uri())
                    model_kwargs = dict(lidar=True, lidar_height_m=manifest['sensor_height_m'],
                                        lidar_spec=LidarSpec(**manifest['lidar_spec']))
                    if manifest.get('sensors', 'legacy') != 'legacy':
                        model_kwargs = dict(sensor_preset='real_bunker', depth_cameras=manifest['sensors'].endswith('+depth2'))
                    model = ET.parse(make_model(folder/'bunker.sdf', mass_kg=truth['tmap'].robot.mass_kg,
                                                **model_kwargs)).find('model')
                    x, y = np.asarray(meta['start'])*RESOLUTION
                    z = float(truth['tmap'].elev[tuple(meta['start'])])+.1
                    ET.SubElement(model, 'pose').text = f'{x} {y} {z} 0 0 0'
                    w.append(model)
                    tree.write(folder/'world.sdf', encoding='utf-8', xml_declaration=True)
                    bridge = ROOT/'ros2_jazzy/gz_checks/lidar_bridge.yaml'
                    if manifest.get('sensors') == 'lidar_real+depth2':
                        bridge_text = sensor_bridge_config(bridge.read_text(), manifest['sensors'])
                        bridge = folder/'real_sensors_bridge.yaml'
                        bridge.write_text(bridge_text)
                        (raw/'real_sensors_bridge.yaml').write_text(bridge_text)
                    commands = [
                        ['gz', 'sim', '-s', '-r', '--headless-rendering', '--seed', '0', str(folder/'world.sdf')],
                        ['ros2', 'run', 'ros_gz_bridge', 'parameter_bridge', '--ros-args', '-p',
                         'config_file:='+str(bridge)],
                        ['ros2', 'run', 'thesis_bunker_mission', 'path_follower', '--ros-args', '-p', 'use_sim_time:=true',
                         '-p', 'online:=true', '-p', 'map_id:='+mission['map_id'], '-p', 'run_root:='+str(raw/'follower')],
                        [sys.executable, str(ROOT/'ros2_jazzy/gz_checks/lidar_planner.py'), '--ros-args', '-p', 'use_sim_time:=true',
                         '-p', 'prior_map:='+str(prior_file), '-p', 'map_id:='+mission['map_id'], '-p', 'run_folder:='+str(raw),
                         '-p', 'sensor_height_m:='+str(manifest['sensor_height_m']), '-p', 'obstacle_height_m:='+str(manifest['obstacle_height_m']),
                         '-p', 'max_range_m:='+str(manifest['lidar_spec']['max_range_m']),
                         '-p', 'range_resolution_m:='+str(manifest['lidar_spec']['range_resolution_m']),
                         '-p', 'stale_timeout_s:='+str(manifest['stale_timeout_s'])]]
                    if manifest.get('map_method') == 'fine':
                        commands[-1].extend(['-p', 'map_method:=fine'])
                    if manifest.get('endpoint_protocol'):
                        commands[-1].extend(['-p', 'endpoint_policy:='+manifest['endpoint_policy'],
                                             '-p', 'diagnostics:='+str(manifest['diagnostics']).lower()])
                    if manifest.get('sensors', 'legacy') != 'legacy':
                        commands[-1].extend(['-p', 'sensors:='+manifest['sensors']])
                    if manifest.get('ground_estimate', 'all_returns') != 'all_returns':
                        commands[-1].extend(['-p', 'ground_estimate:='+manifest['ground_estimate']])
                    for i, command in enumerate(commands):
                        stream = (raw/f'process_{i}.txt').open('w')
                        streams.append(stream)
                        processes.append(subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True))
                    observer.wait_until(lambda: observer.t is not None and observer.pose is not None and observer.state is not None
                                        and observer.command.get_subscription_count() > 0 and observer.perception is not None
                                        and observer.perception['ready'], processes)
                    settled = observer.t+5
                    observer.wait_until(lambda: observer.t >= settled, processes)
                    mission.update(started_t=observer.t, start_pose=observer.pose, wall_started=time.perf_counter(), status='running')
                    save_run()
                    observer.recording = True
                    message = String()
                    message.data = json.dumps(mission)
                    observer.command.publish(message)
                    distance = float(np.linalg.norm(np.diff(np.asarray(meta['initial_path']), axis=0), axis=1).sum())
                    limit = max(120, 6*distance+60)
                    # Wall-clock guard scales with the slowed simulation (real_time_factor 0.3 -> 10x the sim limit).
                    observer.wait_until(lambda: (observer.state.get('mission_id') == 1 and observer.state['status'] in TERMINAL)
                                        or observer.t-mission['started_t'] > limit, processes, wall_limit=max(180, limit*3/min(1., manifest['real_time_factor'])))
                    case['termination'] = 'simulation_timeout' if observer.t-mission['started_t'] > limit else observer.state['status']
                    mission.update(status=case['termination'], finished_t=observer.t, final_state=observer.state,
                                   perception=observer.perception, wall_elapsed_s=time.perf_counter()-mission['wall_started'])
                    save_run()
                    observer.recording = False
                    observer.stop.publish(Empty())
                    ended = observer.t+.2
                    observer.wait_until(lambda: observer.t >= ended, processes, wall_limit=10)
                    print(case['patch'], case['termination'], flush=True)
                except Exception as exc:
                    case['error'] = type(exc).__name__+': '+str(exc)
                    if mission['status'] not in TERMINAL | {'simulation_timeout'}:
                        mission.update(status='runtime_error', finished_t=observer.t, error=case['error'])
                    else:
                        mission['cleanup_error'] = case['error']
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
        if manifest.get('ground_estimate', 'all_returns') != 'all_returns':
            if manifest['execution'] == 'finished_with_errors':
                raise RuntimeError('task029 trial errors; inspect manifest')
            print('Task029 raw results saved; evaluate ground estimates separately:', output)
            return
        if manifest.get('endpoint_protocol'):
            if manifest['execution'] == 'finished_with_errors':
                raise RuntimeError('task028 trial errors; inspect manifest')
            print('Task028 raw results saved; evaluate stop outcomes separately:', output)
            return
        if manifest.get('sensors', 'legacy') != 'legacy':
            if manifest['execution'] == 'finished_with_errors':
                raise RuntimeError('some real sensor trials could not run; inspect manifest')
            print('Task027 raw results saved; legacy task023 aggregation is not applicable:', output)
            return
        if manifest.get('map_method') == 'fine':
            from experiments.lidar_fine_report import summarize
        else:
            from experiments.gz_lidar_report import summarize
        summarize(output)
        if manifest['execution'] == 'finished_with_errors':
            raise RuntimeError('some LiDAR trials could not run; inspect manifest')
    finally:
        rclpy.shutdown()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'results/gazebo_lidar/physical_3')
    parser.add_argument('--patch-count', type=int, choices=[3, 10], default=3)
    parser.add_argument('--sensor-height-m', type=float, default=.8)
    parser.add_argument('--obstacle-height-m', type=float, default=.3)
    parser.add_argument('--noise-stddev-m', type=float, default=.02)
    parser.add_argument('--max-range-m', type=float, default=30.)
    parser.add_argument('--map', choices=['coarse', 'fine'], default='coarse', dest='map_method')
    parser.add_argument('--sensors', choices=SENSOR_MODES, default='legacy')
    parser.add_argument('--ground-estimate', choices=GROUND_ESTIMATES, default='all_returns')
    parser.add_argument('--endpoint-policy', choices=ENDPOINT_POLICIES, default='none')
    parser.add_argument('--diagnostics', action='store_true')
    parser.add_argument('--prepare-only', action='store_true')
    args = vars(parser.parse_args())
    output, prepare = args.pop('output'), args.pop('prepare_only')
    if prepare:
        manifest = prepare_cases(output, **args)
        if manifest.get('ground_estimate', 'all_returns') != 'all_returns':
            print('Task029 preparation only; Gazebo not executed:', output)
            return
        if manifest.get('endpoint_protocol'):
            print('Task028 preparation only; Gazebo not executed:', output)
            return
        if manifest.get('sensors', 'legacy') != 'legacy':
            print('Task027 preparation only; Gazebo not executed:', output)
            return
        if manifest.get('map_method') == 'fine':
            from experiments.lidar_fine_report import summarize
        else:
            from experiments.gz_lidar_report import summarize
        summarize(output)
    else:
        run_checks(output, **args)


if __name__ == '__main__':
    main()
