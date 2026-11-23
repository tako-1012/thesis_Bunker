"""Capture and compare the first stamped ROS clouds in a CPU/GPU smoke pair."""

import argparse
import csv
import json
from pathlib import Path
import time
from zipfile import BadZipFile

import numpy as np

SENSORS = ('lidar', 'camera1', 'camera2')
N_FRAMES = 8
POSE_SPAN_NS = 30_000_000  # ground-truth poses are published at 20 Hz
POSITION_TOL_M = .001
ANGLE_TOL_DEG = .1
RECORD_ERRORS = (OSError, ValueError, KeyError, TypeError, EOFError, BadZipFile)


def stamp_ns(msg):
    stamp = msg.header.stamp
    return 1_000_000_000*stamp.sec + stamp.nanosec


def capture(output):
    from geometry_msgs.msg import PoseArray
    import rclpy
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import PointCloud2
    from tapp.pointcloud_map import decode_xyz

    output.mkdir()
    frames = {sensor: {} for sensor in SENSORS}
    poses = {}

    def on_pose(msg):
        stamp = stamp_ns(msg)
        if stamp > 0 and msg.poses:
            p, q = msg.poses[0].position, msg.poses[0].orientation
            poses[stamp] = [p.x, p.y, p.z, q.x, q.y, q.z, q.w]

    def on_cloud(msg, sensor):
        stamp = stamp_ns(msg)
        if stamp <= 0 or min(msg.width, msg.height) <= 0:
            return
        if len(frames[sensor]) >= N_FRAMES or stamp in frames[sensor]:
            return
        fields = [dict(name=f.name, offset=f.offset, datatype=f.datatype, count=f.count) for f in msg.fields]
        xyz = decode_xyz(bytes(msg.data), fields, point_step=msg.point_step, row_step=msg.row_step,
                         width=msg.width, height=msg.height, is_bigendian=msg.is_bigendian)
        frames[sensor][stamp] = xyz.reshape(msg.height, msg.width, 3), msg.header.frame_id

    rclpy.init()
    node = rclpy.create_node('task045_cloud_probe')
    try:
        node.create_subscription(PoseArray, '/ground_truth', on_pose, qos_profile_sensor_data)
        for sensor in SENSORS:
            node.create_subscription(PointCloud2, f'/{sensor}/points',
                                     lambda msg, name=sensor: on_cloud(msg, name), qos_profile_sensor_data)
        deadline = time.monotonic()+180.
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=.1)
            if poses and all(len(clouds) == N_FRAMES for clouds in frames.values()):
                latest = max(max(clouds) for clouds in frames.values())
                if max(poses) >= latest+POSE_SPAN_NS:
                    break
    finally:
        node.destroy_node()
        rclpy.shutdown()

    np.savez(output/'poses.npz', stamps=np.asarray(list(poses), dtype=np.int64),
             pose=np.asarray(list(poses.values()), dtype=float).reshape(-1, 7))
    for sensor, clouds in frames.items():
        for stamp, (xyz, frame) in clouds.items():
            np.savez(output/f'{sensor}-{stamp}.npz', xyz=xyz, frame=frame)
        print(f'{sensor}: captured {len(clouds)} frames', flush=True)
    return 0 if poses and all(len(clouds) == N_FRAMES for clouds in frames.values()) else 2


def load_poses(path, stop_ns):
    file = path/'poses.npz'
    if not file.is_file():
        return {}
    with np.load(file, allow_pickle=False) as data:
        return {int(t): pose for t, pose in zip(data['stamps'], data['pose'], strict=True) if 0 < t < stop_ns}


def load_frames(path, sensor, stop_ns):
    return {int(p.stem.split('-')[1]): p for p in path.glob(f'{sensor}-*.npz')
            if 0 < int(p.stem.split('-')[1]) < stop_ns}


def pose_difference(a, b):
    translation = float(np.linalg.norm(a[:3]-b[:3]))
    q1, q2 = a[3:], b[3:]
    norm = np.linalg.norm(q1)*np.linalg.norm(q2)
    if not np.isfinite(translation+norm) or norm <= 0.:
        return float('inf'), float('inf')
    cosine = np.clip(abs(q1 @ q2)/norm, 0., 1.)
    return translation, float(np.degrees(2*np.arccos(cosine)))


def cloud_difference(a, b, frame_a, frame_b):
    finite_a = np.isfinite(a).all(axis=-1)
    finite_b = np.isfinite(b).all(axis=-1)
    result = dict(cpu_shape=list(a.shape[:2]), gpu_shape=list(b.shape[:2]), cpu_frame=frame_a, gpu_frame=frame_b,
                  cpu_slots=finite_a.size, gpu_slots=finite_b.size,
                  cpu_finite=int(finite_a.sum()), gpu_finite=int(finite_b.sum()))
    if a.shape != b.shape or frame_a != frame_b or not frame_a or a.shape[0] <= 1:
        return dict(result, status='unpaired_layout')
    valid = finite_a & finite_b
    result.update(paired_finite=int(valid.sum()), cpu_only=int((finite_a & ~finite_b).sum()),
                  gpu_only=int((finite_b & ~finite_a).sum()),
                  both_invalid=int((~finite_a & ~finite_b).sum()), xyz_array_equal=bool(np.array_equal(a, b, equal_nan=True)))
    if not valid.any():
        return dict(result, status='no_finite_pair')
    signed = np.linalg.norm(b[valid], axis=1)-np.linalg.norm(a[valid], axis=1)
    return dict(result, status='compared', range_gpu_minus_cpu_m=dict(zip(
        ('min', 'p05', 'median', 'p95', 'max'), np.percentile(signed, [0, 5, 50, 95, 100]).tolist(), strict=True)),
        abs_range_difference_m=dict(zip(('median', 'p95', 'max'),
                                        np.percentile(np.abs(signed), [50, 95, 100]).tolist(), strict=True)))


def compare_sensor(sensor, folders, stops, poses):
    a, b = (load_frames(path, sensor, stop) for path, stop in zip(folders, stops, strict=True))
    common_poses = poses[0].keys() & poses[1].keys()
    for stamp in sorted(a.keys() & b.keys()):
        if not common_poses:
            break
        pose_stamp = min(common_poses, key=lambda t: (abs(t-stamp), t))
        if abs(pose_stamp-stamp) > POSE_SPAN_NS:
            continue
        translation, angle = pose_difference(poses[0][pose_stamp], poses[1][pose_stamp])
        if translation <= POSITION_TOL_M and angle <= ANGLE_TOL_DEG:
            with np.load(a[stamp], allow_pickle=False) as cpu, np.load(b[stamp], allow_pickle=False) as gpu:
                return dict(stamp_ns=stamp, pose_stamp_ns=pose_stamp,
                            position_difference_m=translation, orientation_difference_deg=angle,
                            **cloud_difference(cpu['xyz'], gpu['xyz'], cpu['frame'].item(), gpu['frame'].item()))
    return dict(status='no_common_pre_mission_stamp_and_pose', cpu_frames=len(a), gpu_frames=len(b))


def gpu_utilization(path):
    samples = {}
    with path.open(newline='') as stream:
        for row in csv.reader(stream):
            if len(row) != 5:
                continue
            _, index, name, util, _ = (x.strip() for x in row)
            try:
                percent = float(util)
            except ValueError:
                continue
            if 0. <= percent <= 100.:
                samples.setdefault(f'{index} {name}', []).append(percent)
    return {name: dict(samples=len(values), median_pct=float(np.median(values)), max_pct=max(values))
            for name, values in samples.items()}


def trial(folder, mode):
    physical = folder/'physical_1'
    result = dict(patch=None, execution=None, termination=None, renderer=None, sim_s=None, wall_s=None,
                  measured_rtf=None, wall_run_gpu_usage=None)
    try:
        result['wall_run_gpu_usage'] = gpu_utilization(folder/'gpu_usage.csv')
    except FileNotFoundError:
        pass
    except RECORD_ERRORS as error:
        result['gpu_usage_error'] = str(error)

    try:
        manifest = json.loads((physical/'manifest.json').read_text())
        result['execution'] = manifest.get('execution')
        case, = [row for row in manifest['cases'] if row['selected']]
        result.update(patch=case['patch'], termination=case.get('termination'))
        render = case.get('rendering', {})
        for key in ('renderer', 'gl_vendor', 'gl_renderer', 'gpu_rendered'):
            if key in render:
                result[key] = render[key]
        if manifest['real_time_factor'] != 1. or manifest.get('sensors') != 'lidar_real+depth2':
            raise ValueError(f'{mode}: unexpected experiment settings')
        if mode == 'cpu' and (manifest.get('software_rendering') != '1' or 'rendering' in manifest):
            raise ValueError('the CPU trial did not request software rendering')
        if mode == 'gpu' and manifest.get('rendering', {}).get('mode') != 'gpu':
            raise ValueError('GPU rendering was not requested in manifest')

        if case.get('error'):
            raise ValueError(case['error'])
        exit_file = folder/'exit.txt'
        if exit_file.is_file():
            exit_code = int(exit_file.read_text())
            if exit_code != 0:
                raise ValueError(f'trial stopped with exit code {exit_code}; see console.txt')
        run_folder = case.get('run_folder')
        if not isinstance(run_folder, str) or not run_folder:
            raise ValueError(f"run_folder was not recorded (execution={result['execution']}); see console.txt")
        mission = json.loads((physical/run_folder/'mission.json').read_text())
        timing = [mission.get(key) for key in ('started_t', 'finished_t', 'wall_elapsed_s')]
        if any(value is None for value in timing):
            raise ValueError(f"mission timing is incomplete (status={mission.get('status')}); see console.txt")
        start, end, wall = map(float, timing)
        sim = end-start
        if not np.isfinite(start+sim+wall) or min(sim, wall) <= 0.:
            raise ValueError('invalid mission timing')
    except RECORD_ERRORS as error:
        result['error'] = str(error)
        try:
            result['stop_reason'] = (folder/'stopped.txt').read_text(errors='replace').strip()
        except OSError:
            pass
        return result, None
    return dict(result, sim_s=sim, wall_s=wall, measured_rtf=sim/wall), round(start*1e9)


def compare(root):
    modes = ('cpu', 'gpu')
    trials, stops = {}, {}
    for mode in modes:
        trials[mode], stop = trial(root/mode, mode)
        if stop is not None:
            stops[mode] = stop
    clouds = {sensor: dict(status='no_paired_trial') for sensor in SENSORS}
    ratio = None
    if len(stops) == 2 and trials['cpu']['patch'] == trials['gpu']['patch']:
        ratio = trials['gpu']['measured_rtf']/trials['cpu']['measured_rtf']
        folders = tuple(root/mode/'physical_1/clouds' for mode in modes)
        endings = tuple(stops[mode] for mode in modes)
        try:
            poses = [load_poses(path, stop) for path, stop in zip(folders, endings, strict=True)]
        except RECORD_ERRORS as error:
            clouds = {sensor: dict(status='pose_record_error', error=str(error)) for sensor in SENSORS}
        else:
            for sensor in SENSORS:
                try:
                    clouds[sensor] = compare_sensor(sensor, folders, endings, poses)
                except RECORD_ERRORS as error:
                    clouds[sensor] = dict(status='cloud_record_error', error=str(error))
    gpu = trials['gpu']
    nvidia = (gpu['gpu_rendered'] is True if 'gpu_rendered' in gpu else
              'nvidia' in (gpu['renderer'] or '').lower())
    result = dict(trials=trials, nvidia_renderer_confirmed=nvidia,
                  gpu_over_cpu_rtf=ratio, clouds=clouds)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    complete = all(t.get('execution') == 'finished' and t.get('wall_run_gpu_usage') for t in trials.values())
    return 0 if complete and nvidia and all(c['status'] == 'compared' for c in clouds.values()) else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('capture', 'compare'))
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    return (capture if args.action == 'capture' else compare)(args.directory)


if __name__ == '__main__':
    raise SystemExit(main())
