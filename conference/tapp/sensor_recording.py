"""Bounded, ROS-independent storage and reconstruction of simulator sensor data."""

from dataclasses import dataclass
import io
import json
from pathlib import Path
import numpy as np

LIMIT_BYTES = 100_000_000
META_BYTES = 2048
SCANS_PER_CHUNK = 20
ROWS_PER_CHUNK = 500
MISSING = np.iinfo(np.uint16).max
NONFINITE_START = MISSING - 26
IMU_COLUMNS = ('qx', 'qy', 'qz', 'qw', 'wx_rad_s', 'wy_rad_s', 'wz_rad_s',
               'ax_m_s2', 'ay_m_s2', 'az_m_s2',
               *(f'{name}_cov_{i}{j}' for name in ('orientation', 'gyro', 'accel')
                 for i in range(3) for j in range(3)))
TRUTH_COLUMNS = ('x_m', 'y_m', 'z_m', 'qx', 'qy', 'qz', 'qw')


def pack_lidar(scans):
    """Encode (scan, row, column, XYZ) using uint16 radial millimetres.

    A ray is inferred from the first usable return at each pixel. Preserve
    off-ray, out-of-range and partly nonfinite samples verbatim in a sparse
    side array. Use 27 reserved values for the NaN/+inf/-inf triples.
    """
    scans = np.asarray(scans)
    if scans.ndim != 4 or scans.shape[-1] != 3 or not scans.shape[0]:
        raise ValueError('LiDAR requires XYZ and at least one scan')
    xyz = scans.astype(np.float64, copy=False)
    components_finite = np.isfinite(xyz)
    finite = components_finite.all(axis=-1)
    no_return = ~components_finite.any(axis=-1)
    with np.errstate(invalid='ignore', over='ignore'):
        metres = np.linalg.norm(xyz, axis=-1)
        mm = np.rint(metres * 1000)
        valid = finite & (mm < NONFINITE_START)
        usable = valid & (metres > 0)
        first = np.argmax(usable, axis=0)[None, ..., None]
        ray_xyz = np.take_along_axis(xyz, first, axis=0)[0]
        ray_length = np.take_along_axis(metres, first[..., 0], axis=0)[0, ..., None]
        rays = np.divide(ray_xyz, ray_length, out=np.zeros_like(ray_xyz),
                         where=usable.any(axis=0)[..., None]).astype(np.float32)
        reconstructed = (mm[..., None] * .001) * rays
        radial = valid & (np.linalg.norm(reconstructed - xyz, axis=-1) <= .0009)
    ranges = np.full(xyz.shape[:-1], MISSING, dtype=np.uint16)
    ranges[radial] = mm[radial].astype(np.uint16)
    missing_xyz = xyz[no_return]
    digits = np.where(np.isneginf(missing_xyz), 0, np.where(np.isposinf(missing_xyz), 1, 2))
    ranges[no_return] = NONFINITE_START + digits @ np.array([1, 3, 9])
    fallback = ~radial & ~no_return
    return dict(ranges_mm=ranges, rays=rays,
                exception_indices=np.flatnonzero(fallback).astype(np.uint32),
                exception_xyz=scans[fallback])


def unpack_lidar(chunk):
    """Return the organized XYZ in metres, in its original sensor frame."""
    ranges = chunk['ranges_mm']
    xyz = (ranges[..., None] * .001) * chunk['rays']
    no_return = ranges >= NONFINITE_START
    digits = (ranges[no_return, None] - NONFINITE_START) // np.array([1, 3, 9]) % 3
    xyz[no_return] = np.array([-np.inf, np.inf, np.nan])[digits]
    xyz.reshape(-1, 3)[chunk['exception_indices']] = chunk['exception_xyz']
    return xyz


@dataclass(frozen=True)
class LidarScan:
    stamp_ns: int
    frame_id: str
    xyz: np.ndarray


def iter_lidar(folder):
    """Read the recorded scans one archive at a time in capture order."""
    for path in sorted(Path(folder).glob('chunk_*.npz')):
        with np.load(path, allow_pickle=False) as chunk:
            if 'ranges_mm' in chunk:
                for stamp, frame, points in zip(chunk['lidar_stamp_ns'], chunk['lidar_frame_id'], unpack_lidar(chunk)):
                    yield LidarScan(int(stamp), str(frame), points)


def record_columns(stamps, frames, values, sensor):
    return {f'{sensor}_stamp_ns': np.asarray(stamps, dtype=np.int64),
            f'{sensor}_frame_id': np.asarray(frames, dtype=str),
            f'{sensor}_values': np.asarray(values, dtype=np.float64)}


class SensorArchive:
    """Commit whole compressed chunks and stop before their total exceeds the cap."""

    def __init__(self, folder, *, duration_s=None, limit_bytes=LIMIT_BYTES):
        if duration_s is not None and (not np.isfinite(duration_s) or duration_s <= 0):
            raise ValueError('--record-sensors-seconds must be positive and finite')
        if limit_bytes <= META_BYTES:
            raise ValueError('sensor archive limit must leave room for data')
        self.folder = Path(folder)
        self.folder.mkdir()
        self.duration_s = duration_s
        self.limit_bytes = limit_bytes
        self.begin_ns = self.end_ns = None
        self.bytes = self.chunks = 0
        self.kept = dict(lidar=0, imu=0, ground_truth=0)
        self.received = dict(self.kept)
        self.skipped_empty = 0
        self.lidar_queue_drops = None
        self.stopped = None
        self.pending = {key: [] for key in self.kept}
        self._write_metadata()

    def _write_metadata(self):
        data = dict(format_version=1, status=self.stopped or 'recording',
                    received=self.received, saved=self.kept, empty_ground_truth=self.skipped_empty,
                    begin_ns=self.begin_ns, end_ns=self.end_ns, duration_limit_s=self.duration_s,
                    limit_bytes=self.limit_bytes, chunk_bytes=self.bytes, chunks=self.chunks,
                    timestamp='ROS message header stamp in simulator nanoseconds',
                    lidar='/lidar/points', imu='/imu', ground_truth='/ground_truth (pose index 0)',
                    imu_columns=IMU_COLUMNS, ground_truth_columns=TRUTH_COLUMNS)
        if self.lidar_queue_drops is not None:
            data['lidar_queue_drops'] = self.lidar_queue_drops
        encoded = (json.dumps(data, indent=2) + '\n').encode()
        if len(encoded) > META_BYTES:
            raise ValueError('sensor archive metadata exceeds the reserved space')
        (self.folder / 'metadata.json').write_bytes(encoded)

    def set_lidar_queue_drops(self, count):
        self.lidar_queue_drops = count
        self._write_metadata()

    def accepting(self, stamp_ns):
        if self.stopped:
            return False
        if self.begin_ns is None:
            self.begin_ns = stamp_ns
        if self.duration_s is not None and stamp_ns - self.begin_ns >= self.duration_s * 1e9:
            self.close('duration_limit')
            return False
        return True

    def add(self, sensor, stamp_ns, frame, values):
        if self.stopped:
            return
        self.received[sensor] += 1
        if not self.accepting(stamp_ns):
            return
        rows = self.pending[sensor]
        if sensor == 'lidar' and rows and rows[0][2].shape != values.shape:
            self.flush()
            if self.stopped:
                return
        rows.append((stamp_ns, frame, values))
        if len(rows) >= (SCANS_PER_CHUNK if sensor == 'lidar' else ROWS_PER_CHUNK):
            self.flush()

    def flush(self):
        arrays = {}
        end_ns = self.end_ns
        counts = {}
        for sensor, rows in self.pending.items():
            if not rows:
                continue
            stamps, frames, values = zip(*rows)
            end_ns = max(stamps) if end_ns is None else max(end_ns, *stamps)
            if sensor == 'lidar':
                arrays.update(pack_lidar(np.stack(values)))
                arrays.update(lidar_stamp_ns=np.asarray(stamps, dtype=np.int64),
                              lidar_frame_id=np.asarray(frames, dtype=str))
            else:
                arrays.update(record_columns(stamps, frames, values, sensor))
            counts[sensor] = len(rows)
            rows.clear()
        if not arrays:
            return
        encoded = io.BytesIO()
        np.savez_compressed(encoded, **arrays)
        size = encoded.tell()
        if self.bytes + size + META_BYTES > self.limit_bytes:
            self.stopped = 'byte_limit'
            self._write_metadata()
            return
        (self.folder / f'chunk_{self.chunks:05d}.npz').write_bytes(encoded.getbuffer())
        self.bytes += size
        self.chunks += 1
        self.end_ns = end_ns
        for key, count in counts.items():
            self.kept[key] += count
        self._write_metadata()

    def close(self, reason='finished'):
        if not self.stopped:
            self.flush()
            if not self.stopped:
                self.stopped = reason
            self._write_metadata()
        elif reason == 'error' and self.stopped != 'error':
            self.stopped = reason
            self._write_metadata()
