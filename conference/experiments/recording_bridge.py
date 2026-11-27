"""Read the task075 archive and the sensor extrinsic of the same recorded run."""

from dataclasses import dataclass
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from scipy.spatial.transform import Rotation

from tapp.sensor_recording import IMU_COLUMNS, TRUTH_COLUMNS


@dataclass(frozen=True)
class SensorRun:
    folder: Path
    lidar_stamp_ns: np.ndarray
    truth_stamp_ns: np.ndarray
    truth_values: np.ndarray
    imu_stamp_ns: np.ndarray
    imu_values: np.ndarray
    base_from_lidar: np.ndarray
    extrinsic_source: str
    status: str


def run_folder(path):
    if (path/'sensors').is_dir():
        return path
    if path.name == 'raw':
        candidates = sorted(p for p in path.iterdir() if (p/'sensors').is_dir())
        if len(candidates) == 1:
            return candidates[0]
        if candidates:
            raise ValueError(f'{path}: 複数の記録があります。raw/<砂浜> を指定してください: '
                             + ', '.join(p.name for p in candidates))
    raise FileNotFoundError(f'{path}: 075の sensors/ が見つかりません')


def transform(xyz, rpy, *, degrees=False):
    xyz, rpy = np.asarray(xyz, dtype=float), np.asarray(rpy, dtype=float)
    if xyz.shape != (3,) or rpy.shape != (3,) or not np.isfinite([xyz, rpy]).all():
        raise ValueError('LiDARの取り付け位置には有限な xyz と rpy が必要です')
    matrix = np.eye(4)
    matrix[:3, 3] = xyz
    matrix[:3, :3] = Rotation.from_euler('xyz', rpy, degrees=degrees).as_matrix()
    return matrix


def manifest_extrinsic(manifest):
    explicit = manifest.get('base_from_lidar')
    if explicit is not None:
        matrix = np.asarray(explicit, dtype=float)
        if (matrix.shape != (4, 4) or not np.isfinite(matrix).all()
                or not np.allclose(matrix[3], [0, 0, 0, 1])
                or not np.allclose(matrix[:3, :3].T @ matrix[:3, :3], np.eye(3), atol=1e-7)
                or not np.isclose(np.linalg.det(matrix[:3, :3]), 1.)):
            raise ValueError('manifest の base_from_lidar は4×4の剛体変換にしてください')
        return matrix, 'base_from_lidar'
    configuration = manifest.get('sensor_configuration') or {}
    mount = (configuration.get('mounts') or {}).get('lidar') or {}
    if 'xyz' in mount and 'rpy' in mount:
        # The PosePublisher records the bunker model, not its offset base_link.
        return transform(mount['xyz'], mount['rpy']), 'sensor_configuration.mounts.lidar.xyz/rpy'
    return None


def sdf_pose(pose, expected_frames):
    if pose.get('relative_to', '') not in expected_frames:
        raise ValueError('world.sdf の LiDAR 取り付け位置が未対応の相対フレームを参照しています')
    if pose.get('rotation_format', 'euler_rpy') != 'euler_rpy':
        raise ValueError('world.sdf の LiDAR 取り付け位置には xyz/rpy を指定してください')
    values = [float(item) for item in (pose.text or '').split()]
    return transform(values[:3], values[3:], degrees=pose.get('degrees') in ('1', 'true'))


def sdf_extrinsic(path):
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ValueError(f'{path}: world.sdf を読めません: {exc}') from exc
    models = root.findall('world/model[@name="bunker"]') + root.findall('model[@name="bunker"]')
    mounts = [(link, sensor) for model in models for link in model.findall('link')
              for sensor in link.findall('sensor[@name="lidar"]')]
    if not mounts:
        return None
    if len(mounts) != 1:
        raise ValueError(f'{path}: bunker に複数の LiDAR センサーがあります')
    link, lidar = mounts[0]
    lidar_pose = lidar.find('pose')
    if lidar_pose is None:
        return None
    if lidar_pose.get('relative_to') == '__model__':
        return sdf_pose(lidar_pose, ('__model__',))
    link_from_lidar = sdf_pose(lidar_pose, ('', link.get('name'), f'bunker::{link.get("name")}'))
    link_pose = link.find('pose')
    return link_from_lidar if link_pose is None else sdf_pose(link_pose, ('', '__model__')) @ link_from_lidar


def resolve_extrinsic(run):
    local_manifest = run/'manifest.json'
    manifests = [local_manifest]
    if run.parent.name == 'raw':
        manifests.append(run.parent.parent/'manifest.json')
    for path in manifests:
        if path.is_file():
            manifest = json.loads(path.read_text())
            if path != local_manifest and 'cases' in manifest:
                raw_path = run.relative_to(path.parent).as_posix()
                if not any(case.get('run_folder') == raw_path for case in manifest['cases']):
                    continue
            result = manifest_extrinsic(manifest)
            if result is not None:
                matrix, key = result
                return matrix, f'{path}#{key}'
    for path in (run/'world.sdf', run/'world'/'world.sdf'):
        if path.is_file():
            matrix = sdf_extrinsic(path)
            if matrix is not None:
                return matrix, str(path)
    raise ValueError(f'{run}: LiDARの取り付け位置がありません。'
                     '走行の manifest.json または world.sdf に完全な取り付け位置が必要です')


def append_rows(chunks, stamps, values, width):
    if stamps.ndim != 1 or values.shape != (len(stamps), width):
        raise ValueError('075のセンサー時刻と値の行数または列数が一致しません')
    chunks.append((stamps, values))


def join_rows(chunks, width):
    if not chunks:
        return np.empty(0, dtype=np.int64), np.empty((0, width))
    stamps, values = zip(*chunks)
    return np.concatenate(stamps), np.concatenate(values)


def open_archive(path):
    """Collect stream headers only. XYZ is reconstructed lazily by iter_lidar."""
    run = run_folder(Path(path).resolve())
    sensor_dir = run/'sensors'
    metadata = json.loads((sensor_dir/'metadata.json').read_text())
    if metadata.get('format_version') != 1:
        raise ValueError(f'{sensor_dir}: 未対応の075記録形式です')
    files = sorted(sensor_dir.glob('chunk_*.npz'))
    if len(files) != metadata.get('chunks'):
        raise ValueError(f'{sensor_dir}: metadata.json とチャンク数が一致しません')
    lidar, truth, imu = [], [], []
    for path in files:
        with np.load(path, allow_pickle=False) as archive:
            if 'lidar_stamp_ns' in archive:
                stamps = archive['lidar_stamp_ns']
                if stamps.ndim != 1 or archive['lidar_frame_id'].shape != stamps.shape:
                    raise ValueError(f'{path}: LiDARの時刻とフレーム数が一致しません')
                lidar.append(stamps)
            truth_prefix = 'ground_truth' if 'ground_truth_values' in archive else 'truth'
            if f'{truth_prefix}_values' in archive:
                append_rows(truth, archive[f'{truth_prefix}_stamp_ns'],
                            archive[f'{truth_prefix}_values'], len(TRUTH_COLUMNS))
            if 'imu_values' in archive:
                append_rows(imu, archive['imu_stamp_ns'], archive['imu_values'], len(IMU_COLUMNS))
    if not lidar:
        raise ValueError(f'{sensor_dir}: LiDARスキャンがありません')
    lidar_ns = np.concatenate(lidar)
    truth_ns, truth_values = join_rows(truth, len(TRUTH_COLUMNS))
    imu_ns, imu_values = join_rows(imu, len(IMU_COLUMNS))
    saved = metadata.get('saved', {})
    for name, count in (('lidar', len(lidar_ns)), ('ground_truth', len(truth_ns)), ('imu', len(imu_ns))):
        if name in saved and saved[name] != count:
            raise ValueError(f'{sensor_dir}: metadata.json と {name} の保存数が一致しません')
    matrix, source = resolve_extrinsic(run)
    return SensorRun(run, lidar_ns, truth_ns, truth_values, imu_ns, imu_values, matrix,
                     source, metadata.get('status', 'unknown'))
