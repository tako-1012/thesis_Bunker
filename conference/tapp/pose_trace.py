"""Bounded wall-clock pose diagnostics shared by the three ROS subscribers."""

import os
from pathlib import Path
import sys
from threading import Event, Thread
import time

NS = 1_000_000_000
POSE_FIELDS = ('mono_ns', 'ros_ns', 'stamp_ns', 'stamp_source', 'has_pose')
TICK_FIELDS = ('mono_ns', 'interval_ns', 'duration_ns', 'pose_timeout', 'last_pose_received_ns')
CPU_FIELDS = ('mono_ns', 'cpu_pct', 'load1', 'load5', 'load15')
POSE_FILE_BYTES = 2_000_000
TICK_FILE_BYTES = 3_500_000
CPU_FILE_BYTES = 400_000
TRACE_LIMIT_BYTES = 2 * (3 * POSE_FILE_BYTES + TICK_FILE_BYTES + CPU_FILE_BYTES)


class TraceCsv:
    """Keep current and previous segments, with no sampling of individual rows."""

    def __init__(self, path, fields, limit):
        self.path = path
        self.previous = path.with_name(path.stem+'_previous.csv')
        self.header = self.encode(fields)
        self.limit = limit
        self.file = None
        self.last_flush = 0
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._open()
        except OSError as error:
            self._failed(error)

    @staticmethod
    def encode(values):
        # Fields contain only numeric values, fixed ASCII labels or nulls.
        return (','.join('' if value is None else str(value) for value in values)+'\n').encode('ascii')

    def _open(self):
        self.file = self.path.open('xb')
        self.file.write(self.header)
        self.size = len(self.header)

    def _failed(self, error):
        self.close()
        print(f'pose trace disabled for {self.path.name}: {error}', file=sys.stderr)

    def write(self, *values, flush=False):
        if self.file is None:
            return
        data = self.encode(values)
        try:
            if self.size + len(data) > self.limit:
                self.close()
                self.path.replace(self.previous)
                self._open()
            self.file.write(data)
            self.size += len(data)
            if flush or values[0] - self.last_flush >= NS:
                self.file.flush()
                self.last_flush = values[0]
        except OSError as error:
            self._failed(error)

    def close(self):
        if self.file is not None:
            file, self.file = self.file, None
            try:
                file.close()
            except OSError as error:
                print(f'pose trace close failed for {self.path.name}: {error}', file=sys.stderr)

    def flush(self):
        if self.file is not None:
            try:
                self.file.flush()
            except OSError as error:
                self._failed(error)


def pose_sample(message, mono_ns, ros_ns):
    stamp = getattr(getattr(message, 'header', None), 'stamp', None)
    header_ns = stamp.sec*NS + stamp.nanosec if stamp is not None else 0
    source = 'header' if header_ns > 0 else ('ros' if ros_ns is not None else 'none')
    return mono_ns, ros_ns, header_ns if source == 'header' else ros_ns, source, int(bool(message.poses))


def trace_pose(folder, subscriber, on_pose, ros_time_ns):
    trace = TraceCsv(Path(folder)/f'{subscriber}_pose.csv', POSE_FIELDS, POSE_FILE_BYTES)

    def traced(message):
        received = time.monotonic_ns()
        ros_ns = ros_time_ns()
        try:
            on_pose(message)
        finally:
            trace.write(*pose_sample(message, received, ros_ns))

    return traced, trace


def trace_tick(folder, node, pose_log):
    trace = TraceCsv(Path(folder)/'follower_tick.csv', TICK_FIELDS, TICK_FILE_BYTES)
    previous = None

    def traced():
        nonlocal previous
        before = node.last_status
        began = time.monotonic_ns()
        interval = None if previous is None else began-previous
        previous = began
        try:
            node.tick()
        finally:
            duration = time.monotonic_ns()-began
            timeout = before != 'pose_timeout' and node.last_status == 'pose_timeout'
            last_pose = round(node.pose_received*NS) if timeout and node.pose is not None else None
            trace.write(began, interval, duration, int(timeout), last_pose, flush=timeout)
            if timeout:
                pose_log.flush()

    return traced, trace


def cpu_ticks():
    try:
        with open('/proc/stat', encoding='ascii') as stream:
            counters = [int(value) for value in stream.readline().split()[1:9]]
        return sum(counters), counters[3]+counters[4]
    except (OSError, ValueError, IndexError):
        return None


def cpu_percent(before, after):
    if before is None or after is None:
        return None
    total, idle = after[0]-before[0], after[1]-before[1]
    return round(100*(total-idle)/total, 2) if total > 0 and 0 <= idle <= total else None


class CpuSampler:
    def __init__(self, folder):
        self.trace = TraceCsv(Path(folder)/'cpu.csv', CPU_FIELDS, CPU_FILE_BYTES)
        self.stop = Event()
        self.thread = Thread(target=self._sample, name='pose-trace-cpu', daemon=True)
        self.thread.start()

    def _sample(self):
        before = cpu_ticks()
        while not self.stop.wait(1.):
            now = time.monotonic_ns()
            after = cpu_ticks()
            try:
                loads = os.getloadavg()
            except OSError:
                loads = (None, None, None)
            self.trace.write(now, cpu_percent(before, after), *loads)
            before = after

    def close(self):
        self.stop.set()
        self.thread.join()
        self.trace.close()
