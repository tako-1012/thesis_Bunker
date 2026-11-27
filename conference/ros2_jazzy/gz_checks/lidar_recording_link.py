"""Bounded local transfer of the planner's ROS-serialized LiDAR messages."""

from collections import deque
import select
import socket
import struct
from threading import Condition, Thread

QUEUE_CAPACITY = 4
HEADER = struct.Struct('!q')


class CloudForwarder:
    """Keep a few original messages; the worker alone serializes and writes."""

    def __init__(self, stream, serialize, *, capacity=QUEUE_CAPACITY):
        self.stream, self.serialize, self.capacity = stream, serialize, capacity
        self.condition = Condition()
        self.pending = deque()
        self.closing = self.finished = False
        self.dropped = 0
        self.thread = Thread(target=self._send, name='record-lidar', daemon=True)
        self.thread.start()

    def offer(self, message):
        with self.condition:
            if self.closing or self.finished:
                return
            if len(self.pending) >= self.capacity:
                self.dropped += 1
            else:
                self.pending.append(message)
                self.condition.notify()

    def _send(self):
        try:
            while True:
                with self.condition:
                    self.condition.wait_for(lambda: self.closing or self.pending, timeout=.05)
                    if self.closing and not self.pending:
                        break
                    message = self.pending.popleft() if self.pending else None
                # The recorder closes its write half at the byte/time limit.
                if select.select([self.stream], [], [], 0)[0]:
                    break
                if message is not None:
                    payload = self.serialize(message)
                    self.stream.sendall(HEADER.pack(len(payload)))
                    self.stream.sendall(payload)
            with self.condition:
                self.finished = True
                self.pending.clear()
                dropped = self.dropped
            # One negative header terminates the stream and carries the counter.
            self.stream.sendall(HEADER.pack(-1-dropped))
        except Exception as exc:
            print(f'LiDAR recording transfer failed: {exc}', flush=True)
        finally:
            with self.condition:
                self.finished = True
                self.pending.clear()
            self.stream.close()

    def close(self):
        with self.condition:
            self.closing = True
            self.condition.notify()
        self.thread.join(timeout=5.)
        if self.thread.is_alive():
            # A stalled recorder must not prevent the planner from shutting down.
            try:
                self.stream.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.thread.join(timeout=1.)


class CloudReceiver:
    """Read frames on the recorder's executor without waiting for socket data."""

    def __init__(self, stream, record, stopped, set_drops):
        self.stream, self.record, self.stopped, self.set_drops = stream, record, stopped, set_drops
        self.stream.setblocking(False)
        self.partial = bytearray()
        self.size = None
        self.finished = self.stop_sent = False

    def poll(self, *, max_frames=4):
        if self.finished:
            return
        frames = 0
        while max_frames is None or frames < max_frames:
            if self.stopped() and not self.stop_sent:
                try:
                    self.stream.shutdown(socket.SHUT_WR)
                except OSError:
                    # The producer may already have sent its trailer and closed.
                    pass
                self.stop_sent = True
            wanted = (HEADER.size if self.size is None else self.size) - len(self.partial)
            try:
                data = self.stream.recv(wanted)
            except BlockingIOError:
                return
            if not data:
                raise EOFError('planner LiDAR stream ended before its drop counter')
            self.partial.extend(data)
            if len(data) < wanted:
                continue
            if self.size is None:
                size, = HEADER.unpack(self.partial)
                self.partial.clear()
                if size < 0:
                    self.set_drops(-1-size)
                    self.finished = True
                    return
                if size == 0:
                    raise ValueError('empty serialized planner LiDAR frame')
                self.size = size
            else:
                if not self.stopped():
                    self.record(bytes(self.partial))
                self.partial.clear()
                self.size = None
                frames += 1
