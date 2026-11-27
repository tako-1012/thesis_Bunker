"""Replay stamped LiDAR scans with KISS-ICP and scan-to-map GICP."""

import argparse
from collections.abc import Iterable
import csv
from dataclasses import dataclass
from importlib.metadata import version
from itertools import islice
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation, Slerp

CORRECTION_INTERVAL_M = 5.
INITIAL_ALONGSHORE_M = .5
INITIAL_YAW_DEG = 2.
# For the coupled Hessian, measure δθ by the arc travelled at a 1 m lever arm.
ROTATION_LEVER_M = 1.
MIN_INFORMATION = 1.
VOXEL_M = .25
GICP_MAX_CORRESPONDENCE_M = 1.5
GICP_ITERATIONS = 40
NORMAL_NEIGHBORS = 20
MIN_RANGE_M = .1
MAX_RANGE_M = 30.
METHODS = ('odometry', 'map_only', 'combined')


class MissingLocalizationPackages(RuntimeError):
    pass


def load_backends():
    try:
        from kiss_icp.config import KISSConfig
        from kiss_icp.kiss_icp import KissICP
        import small_gicp
    except ImportError as exc:
        raise MissingLocalizationPackages(
            'KISS-ICP と small_gicp が必要です。'
            'python -m pip install -r requirements_localization.txt を実行してください。'
            f' ({exc})'
        ) from exc
    return KISSConfig, KissICP, small_gicp


def initial_pose(truth):
    biased = np.array(truth, dtype=float, copy=True)
    biased[0, 3] += INITIAL_ALONGSHORE_M
    biased[:3, :3] = Rotation.from_euler('z', INITIAL_YAW_DEG, degrees=True).as_matrix() @ biased[:3, :3]
    return biased


@dataclass
class Recording:
    stamps_ns: np.ndarray
    truth: np.ndarray
    scans: Iterable[np.ndarray]
    base_from_lidar: np.ndarray
    imu_samples: int = 0
    discarded_scans: int = 0
    imu_stamp_ns: np.ndarray | None = None
    imu_values: np.ndarray | None = None


@dataclass
class Replay:
    poses: dict
    odometry_distance_m: np.ndarray
    alignments: list


@dataclass
class Information:
    translation: np.ndarray
    rotation: np.ndarray
    weakest: float
    weak_direction_world: np.ndarray
    weak_axis: str


def information(hessian, inliers, world_from_lidar_rotation):
    """GICP uses right increments in LiDAR coordinates, ordered (ω, v)."""
    h = np.asarray(hessian, dtype=float)
    if inliers <= 0 or h.shape != (6, 6) or not np.isfinite(h).all():
        return None
    h = (h+h.T)/(2*inliers)
    scale = np.array([1/ROTATION_LEVER_M]*3+[1.]*3)
    eigenvalues, vectors = np.linalg.eigh(h*scale[:, None]*scale)
    direction = vectors[:, 0].reshape(2, 3) @ world_from_lidar_rotation.T
    flat = direction.ravel()
    flat *= np.sign(flat[np.argmax(np.abs(flat))])
    if np.linalg.norm(direction[0]) > np.linalg.norm(direction[1]):
        axis = 'rotation'
    else:
        axis = ('alongshore', 'cross_shore', 'vertical')[np.argmax(np.abs(direction[1]))]
    return Information(np.linalg.eigvalsh(h[3:, 3:]), np.linalg.eigvalsh(h[:3, :3]),
                       float(eigenvalues[0]), flat, axis)


class MapRegistration:
    def __init__(self, reference, small_gicp):
        self.backend = small_gicp
        self.target, self.tree = self.preprocess(reference)
        if len(self.target) < NORMAL_NEIGHBORS:
            raise ValueError('reference point cloud has too few occupied voxels')

    def preprocess(self, xyz):
        return self.backend.preprocess_points(
            np.asarray(xyz, dtype=float), downsampling_resolution=VOXEL_M,
            num_neighbors=NORMAL_NEIGHBORS, num_threads=1,
        )

    def match(self, source, initial, *, gated):
        if source is None or len(source) < NORMAL_NEIGHBORS:
            return initial, dict(converged=False, inliers=0, accepted=False,
                                 status='insufficient_scan', information=None)
        result = self.backend.align(
            self.target, source, self.tree, init_T_target_source=initial,
            registration_type='GICP', max_correspondence_distance=GICP_MAX_CORRESPONDENCE_M,
            max_iterations=GICP_ITERATIONS, num_threads=1,
        )
        candidate = np.asarray(result.T_target_source)
        finite = np.isfinite(candidate).all()
        info = information(result.H, result.num_inliers, candidate[:3, :3]) if finite else None
        if not result.converged:
            status = 'not_converged'
        elif result.num_inliers < NORMAL_NEIGHBORS:
            status = 'insufficient_inliers'
        elif info is None:
            status = 'invalid_information'
        elif gated and info.weakest <= MIN_INFORMATION:
            status = 'weak_information'
        else:
            status = 'accepted'
        accepted = status == 'accepted'
        return (candidate if accepted else initial,
                dict(converged=result.converged, inliers=result.num_inliers,
                     accepted=accepted, status=status, information=info))


def path_distance(poses):
    return np.r_[0., np.cumsum(np.linalg.norm(np.diff(poses[:, :3, 3], axis=0), axis=1))]


def localize(recording, reference):
    KISSConfig, KissICP, small_gicp = load_backends()
    config = KISSConfig()
    config.data.min_range = MIN_RANGE_M
    config.data.max_range = MAX_RANGE_M
    config.data.deskew = False  # The recorded scan has one timestamp, not per-return offsets.
    config.mapping.voxel_size = VOXEL_M
    config.registration.max_num_threads = 1
    odometry = KissICP(config)
    matcher = MapRegistration(reference, small_gicp)
    base_from_lidar = recording.base_from_lidar
    lidar_from_base = np.linalg.inv(base_from_lidar)
    initial = initial_pose(recording.truth[0]) @ base_from_lidar
    map_pose = initial.copy()
    correction = np.eye(4)
    poses = {method: [] for method in METHODS}
    events, distances = [], []
    distance, next_correction = 0., CORRECTION_INTERVAL_M

    for k, (stamp, scan) in enumerate(zip(recording.stamps_ns, recording.scans, strict=True)):
        scan = np.asarray(scan, dtype=float)
        r = np.linalg.norm(scan, axis=1)
        scan = scan[(r > MIN_RANGE_M) & (r < MAX_RANGE_M)]
        source = None
        if len(scan) >= NORMAL_NEIGHBORS:
            odometry.register_frame(scan, np.empty(0))
            if not np.isfinite(odometry.last_pose).all():
                raise ValueError(f'KISS-ICP returned a non-finite pose at scan {k}')
            source, _ = matcher.preprocess(scan)

        lidar_odom = initial @ odometry.last_pose
        base_odom = lidar_odom @ lidar_from_base
        if k:
            distance += np.linalg.norm(base_odom[:3, 3]-poses['odometry'][-1][:3, 3])
        distances.append(distance)
        poses['odometry'].append(base_odom)
        event = dict(scan=k, stamp_ns=int(stamp), odometry_distance_m=float(distance))
        map_pose, diagnostics = matcher.match(source, map_pose, gated=False)
        poses['map_only'].append(map_pose @ lidar_from_base)
        events.append(dict(event, method='map_only', **diagnostics))
        if distance >= next_correction:
            corrected, diagnostics = matcher.match(source, correction @ lidar_odom, gated=True)
            if diagnostics['accepted']:
                correction = corrected @ np.linalg.inv(lidar_odom)
            events.append(dict(event, method='combined', scheduled_distance_m=next_correction, **diagnostics))
            # At most one correction per scan even when it crosses multiple multiples.
            next_correction = (int(distance//CORRECTION_INTERVAL_M)+1)*CORRECTION_INTERVAL_M
        poses['combined'].append(correction @ base_odom)
    return Replay({key: np.stack(track) for key, track in poses.items()}, np.asarray(distances), events)


def poses_from_xyz_quat(xyz_quat):
    values = np.asarray(xyz_quat, dtype=float)
    if values.ndim != 2 or values.shape[1] != 7 or not len(values) or not np.isfinite(values).all():
        raise ValueError('ground truth must contain finite [x, y, z, qx, qy, qz, qw] rows')
    matrices = np.repeat(np.eye(4)[None, :, :], len(values), axis=0)
    matrices[:, :3, 3] = values[:, :3]
    matrices[:, :3, :3] = Rotation.from_quat(values[:, 3:]).as_matrix()
    return matrices


def synchronized_truth(lidar_ns, truth_ns, truth):
    """Trim outside the truth coverage and interpolate without extrapolation."""
    if lidar_ns.ndim != 1 or truth_ns.ndim != 1 or len(truth) != len(truth_ns):
        raise ValueError('one timestamp per input frame and ground truth pose is required')
    if len(lidar_ns) == 0 or len(truth_ns) < 2:
        raise ValueError('at least one LiDAR scan and two ground truth poses are required')
    if np.any(lidar_ns[1:] <= lidar_ns[:-1]) or np.any(truth_ns[1:] <= truth_ns[:-1]):
        raise ValueError('LiDAR and ground truth timestamps must be strictly increasing')
    selected = np.flatnonzero((lidar_ns >= truth_ns[0]) & (lidar_ns <= truth_ns[-1]))
    if not len(selected):
        raise ValueError('LiDAR and ground truth timestamps do not overlap')
    t = (truth_ns-truth_ns[0])*1e-9
    query = (lidar_ns[selected]-truth_ns[0])*1e-9
    values = np.repeat(np.eye(4)[None, :, :], len(query), axis=0)
    values[:, :3, 3] = np.column_stack([np.interp(query, t, truth[:, i, 3]) for i in range(3)])
    values[:, :3, :3] = Slerp(t, Rotation.from_matrix(truth[:, :3, :3]))(query).as_matrix()
    return selected, values


def timestamps(values, name):
    values = np.asarray(values)
    if values.ndim != 1 or values.dtype.kind not in 'iu' or np.any(values < 0):
        raise ValueError(f'{name} must be one-dimensional nonnegative integer nanoseconds')
    if np.any(values > np.iinfo(np.int64).max):
        raise ValueError(f'{name} exceeds the signed 64-bit limit')
    return values.astype(np.int64)


def lidar_directions(azimuth, elevation):
    azimuth, elevation = np.asarray(azimuth), np.asarray(elevation)
    if (azimuth.ndim != 1 or elevation.ndim != 1 or not np.isfinite(azimuth).all()
            or not np.isfinite(elevation).all() or np.any(np.abs(elevation) > np.pi/2)):
        raise ValueError('LiDAR beam angles must be finite 1-D radian vectors')
    x = np.cos(elevation[:, None])*np.cos(azimuth)
    y = np.cos(elevation[:, None])*np.sin(azimuth)
    z = np.broadcast_to(np.sin(elevation[:, None]), x.shape)
    return np.stack((x, y, z), axis=-1)


def range_scan(ranges_mm, directions):
    valid = (ranges_mm > MIN_RANGE_M*1000) & (ranges_mm < MAX_RANGE_M*1000)
    return directions[valid]*(ranges_mm[valid, None]*.001)


def load_run_directory(path, reference=None):
    from experiments.recording_bridge import open_archive
    from tapp.sensor_recording import iter_lidar

    archive = open_archive(path)
    reference_path = archive.folder/'reference_cloud.npz'
    if reference is not None and Path(reference).resolve() != reference_path.resolve():
        raise ValueError('075の入力には同じ走行フォルダの reference_cloud.npz を使ってください')
    if not reference_path.is_file():
        raise FileNotFoundError(f'{reference_path}: 同じ走行の参照点群が見つかりません')

    lidar_ns = timestamps(archive.lidar_stamp_ns, 'lidar_stamp_ns')
    truth_ns = timestamps(archive.truth_stamp_ns, 'ground_truth_stamp_ns')
    imu_ns = timestamps(archive.imu_stamp_ns, 'imu_stamp_ns')
    selected, truth = synchronized_truth(lidar_ns, truth_ns, poses_from_xyz_quat(archive.truth_values))
    selected_ns = lidar_ns[selected]

    def scans():
        decoded = islice(iter_lidar(archive.folder/'sensors'), int(selected[0]), int(selected[-1])+1)
        for scan, expected in zip(decoded, selected_ns, strict=True):
            if scan.stamp_ns != expected:
                raise ValueError('075の復元スキャンとチャンクの時刻が一致しません')
            yield scan.xyz.reshape(-1, 3)

    recording = Recording(selected_ns, truth, scans(), archive.base_from_lidar, len(imu_ns),
                          len(lidar_ns)-len(selected), imu_stamp_ns=imu_ns, imu_values=archive.imu_values)
    source = dict(recording=str(archive.folder), reference=str(reference_path),
                  recording_format='sensor_archive_v1', archive_status=archive.status,
                  extrinsic_source=archive.extrinsic_source)
    return recording, reference_path, source


def load_recording(path):
    """Read task075 run directories or the standalone packed NPZ format."""
    if Path(path).is_dir():
        return load_run_directory(path)[0]
    with np.load(path, allow_pickle=False) as data:
        lidar_ns = timestamps(data['lidar_stamp_ns'], 'lidar_stamp_ns')
        truth_ns = timestamps(data['truth_stamp_ns'], 'truth_stamp_ns')
        truth = poses_from_xyz_quat(data['truth_xyz_quat_xyzw'])
        extrinsic = np.asarray(data['base_from_lidar'], dtype=float)
        directions = lidar_directions(data['azimuth_rad'], data['elevation_rad'])
        ranges = data['ranges_mm']
        if ranges.dtype != np.uint16 or ranges.shape != (len(lidar_ns), *directions.shape[:2]):
            raise ValueError('ranges_mm must be uint16 with shape (scans, elevation, azimuth)')
        imu_count = 0
        if 'imu_stamp_ns' in data:
            imu_count = len(timestamps(data['imu_stamp_ns'], 'imu_stamp_ns'))
            for key in ('imu_angular_velocity', 'imu_linear_acceleration'):
                if data[key].shape != (imu_count, 3) or not np.isfinite(data[key]).all():
                    raise ValueError(f'{key} must have one finite xyz row per IMU stamp')
    if (extrinsic.shape != (4, 4) or not np.isfinite(extrinsic).all()
            or not np.allclose(extrinsic[3], [0, 0, 0, 1])
            or not np.allclose(extrinsic[:3, :3].T @ extrinsic[:3, :3], np.eye(3), atol=1e-7)
            or not np.isclose(np.linalg.det(extrinsic[:3, :3]), 1.)):
        raise ValueError('base_from_lidar must be a proper rigid 4x4 transform')
    selected, truth = synchronized_truth(lidar_ns, truth_ns, truth)
    scans = (range_scan(ranges[i], directions) for i in selected)
    return Recording(lidar_ns[selected], truth, scans, extrinsic, imu_count, len(lidar_ns)-len(selected))


def load_reference(path):
    with np.load(path, allow_pickle=False) as data:
        xyz = data['xyz']
    if xyz.ndim != 2 or xyz.shape[1] != 3 or len(xyz) < NORMAL_NEIGHBORS or not np.isfinite(xyz).all():
        raise ValueError('reference_cloud.npz must contain finite Nx3 xyz points in world coordinates')
    return xyz


def pose_values(poses):
    return np.column_stack((poses[:, :3, 3], Rotation.from_matrix(poses[:, :3, :3]).as_quat()))


def trajectory_metrics(recording, replay):
    truth = recording.truth
    travelled = path_distance(truth)
    errors = {}
    rows = []
    for name in METHODS:
        displacement_error = replay.poses[name][:, :3, 3]-truth[:, :3, 3]
        norms = np.linalg.norm(displacement_error, axis=1)
        errors[name] = norms
        drift = np.linalg.norm(displacement_error[-1]-displacement_error[0])
        rows.append(dict(method=name, frames=len(truth), mean_error_m=float(norms.mean()),
                         p95_error_m=float(np.quantile(norms, .95)), max_error_m=float(norms.max()),
                         final_error_m=float(norms[-1]), travelled_m=float(travelled[-1]),
                         relative_drift_m_per_m=float(drift/travelled[-1]) if travelled[-1] > 0 else None))
    return errors, rows


def write_csv(path, rows):
    with path.open('x', newline='') as stream:
        writer = csv.DictWriter(stream, list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def alignment_rows(events, start_stamp):
    for event in events:
        info = event['information']
        row = {key: event.get(key) for key in ('scan', 'stamp_ns', 'method', 'odometry_distance_m',
                                               'scheduled_distance_m', 'converged', 'inliers',
                                               'accepted', 'status')}
        row['time_s'] = (event['stamp_ns']-start_stamp)*1e-9
        row['minimum_scaled_eigenvalue'] = info.weakest if info is not None else None
        for kind in ('translation', 'rotation'):
            values = getattr(info, kind) if info is not None else [None]*3
            row.update({f'{kind}_eig{i+1}': value for i, value in enumerate(values)})
        row['weak_axis'] = info.weak_axis if info is not None else 'unavailable'
        names = ('weak_rx', 'weak_ry', 'weak_rz', 'weak_tx', 'weak_ty', 'weak_tz')
        row.update(zip(names, info.weak_direction_world if info is not None else [None]*6))
        yield row


def plot_diagnostics(path, times, errors, alignments):
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt

    colors = dict(odometry='#456376', map_only='#008075', combined='#bd6224')
    labels = dict(odometry='KISS-ICP', map_only='Scan to map', combined='Combined')
    fig, axes = plt.subplots(3, 1, figsize=(9, 7.3), sharex=True, layout='constrained')
    for name, error in errors.items():
        axes[0].plot(times, error, label=labels[name], color=colors[name], lw=1.8)
    axes[0].set_ylabel('Absolute position error (m)')
    axes[0].legend(loc='lower left', bbox_to_anchor=(0, 1), ncols=3, frameon=False)
    full = [r for r in alignments if r['method'] == 'map_only']
    for key, label, color in (('translation_eig1', 'Translation', '#15857e'),
                              ('rotation_eig1', 'Rotation', '#6c5b97')):
        axes[1].plot([r['time_s'] for r in full],
                     [np.nan if r[key] is None else r[key] for r in full],
                     label=label, color=color, lw=1.6)
    axes[1].set_yscale('symlog', linthresh=.1)
    axes[1].set_ylabel('Minimum block eigenvalue')
    axes[1].legend(loc='lower left', bbox_to_anchor=(0, 1), ncols=2, frameon=False)
    minimum = 'minimum_scaled_eigenvalue'
    axes[2].plot([r['time_s'] for r in full], [np.nan if r[minimum] is None else r[minimum] for r in full],
                 color='#799486', label='Scan to map')
    axes[2].axhline(MIN_INFORMATION, color='#626970', lw=1, ls='--', label='Correction threshold')
    for accepted, marker, color, label in ((True, 'o', '#bd6224', 'Combined: accepted'),
                                           (False, 'x', '#982d44', 'Combined: rejected')):
        group = [r for r in alignments if r['method'] == 'combined' and r['accepted'] == accepted
                 and r[minimum] is not None]
        if group:
            axes[2].scatter([r['time_s'] for r in group], [r[minimum] for r in group],
                            color=color, marker=marker, label=label, zorder=4)
    axes[2].set_yscale('symlog', linthresh=.1)
    axes[2].set(ylabel='Minimum coupled eigenvalue', xlabel='Time since first LiDAR scan (s)')
    axes[2].legend(loc='lower left', bbox_to_anchor=(0, 1), frameon=False, ncols=3)
    for axis in axes:
        axis.grid(color='#d8dfe2', alpha=.65, linewidth=.6)
        axis.spines[['right', 'top']].set_visible(False)
    fig.savefig(path, dpi=155, facecolor='white')
    plt.close(fig)


def save_results(out, recording, replay, source):
    out.mkdir(parents=True, exist_ok=False)
    errors, summary = trajectory_metrics(recording, replay)
    aligned = list(alignment_rows(replay.alignments, int(recording.stamps_ns[0])))
    times = (recording.stamps_ns-recording.stamps_ns[0])*1e-9
    tracks = {name: pose_values(values) for name, values in dict(truth=recording.truth, **replay.poses).items()}
    travelled = path_distance(recording.truth)
    rows = []
    for i, time_s in enumerate(times):
        row = dict(stamp_ns=int(recording.stamps_ns[i]), time_s=time_s,
                   truth_distance_m=travelled[i], odometry_distance_m=replay.odometry_distance_m[i])
        for name, track in tracks.items():
            row.update({f'{name}_{key}': value for key, value in
                        zip(('x', 'y', 'z', 'qx', 'qy', 'qz', 'qw'), track[i])})
        row.update({f'{name}_error_m': error[i] for name, error in errors.items()})
        rows.append(row)
    write_csv(out/'trajectory.csv', rows)
    write_csv(out/'alignments.csv', aligned)
    write_csv(out/'summary.csv', summary)
    metadata = dict(
        source=source, correction_interval_m=CORRECTION_INTERVAL_M, minimum_information=MIN_INFORMATION,
        rotation_lever_m=ROTATION_LEVER_M, initial_alongshore_m=INITIAL_ALONGSHORE_M,
        initial_yaw_deg=INITIAL_YAW_DEG, base_from_lidar=recording.base_from_lidar.tolist(),
        voxel_m=VOXEL_M, gicp_max_correspondence_m=GICP_MAX_CORRESPONDENCE_M,
        gicp_iterations=GICP_ITERATIONS, normal_neighbors=NORMAL_NEIGHBORS,
        imu_samples=recording.imu_samples, discarded_scans=recording.discarded_scans,
        packages={name: version(name) for name in ('numpy', 'scipy', 'matplotlib', 'kiss-icp', 'small_gicp')},
    )
    (out/'metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
    plot_diagnostics(out/'diagnostics.png', times, errors, aligned)
    print((out/'summary.csv').read_text(), end='')
    for name in ('map_only', 'combined'):
        attempts = [event for event in aligned if event['method'] == name]
        print(f"{name}: {sum(event['accepted'] for event in attempts)}/{len(attempts)} accepted")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--recording', type=Path, help='packed LiDAR, IMU and ground truth NPZ')
    inputs.add_argument('--synthetic', choices=('landmarks', 'plane'))
    parser.add_argument('--reference', type=Path, help='reference map NPZ (default: beside recording)')
    parser.add_argument('--out', required=True, type=Path, help='new output directory')
    args = parser.parse_args(argv)
    if args.synthetic is not None and args.reference is not None:
        parser.error('--reference requires --recording')
    try:
        load_backends()
        if args.synthetic is not None:
            from experiments.offline_localization_synthetic import SYNTHETIC_SEED, synthetic_recording

            recording, reference = synthetic_recording(args.synthetic)
            source = dict(scene=args.synthetic, seed=SYNTHETIC_SEED)
        elif args.recording.is_dir():
            recording, reference_path, source = load_run_directory(args.recording, args.reference)
            reference = load_reference(reference_path)
        else:
            reference_path = args.reference or args.recording.with_name('reference_cloud.npz')
            recording, reference = load_recording(args.recording), load_reference(reference_path)
            source = dict(recording=str(args.recording), reference=str(reference_path))
        replay = localize(recording, reference)
        save_results(args.out, recording, replay, source)
    except (MissingLocalizationPackages, OSError, ValueError, KeyError) as exc:
        parser.exit(2, f'自己位置推定: {exc}\n')


if __name__ == '__main__':
    main()
