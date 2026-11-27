"""Publish one stamped localization stream for the LiDAR trial's robot nodes."""

from copy import deepcopy
import json
import math
from pathlib import Path
import sys
import time

from tapp.pose_error import ESTIMATED_POSE_TOPIC, PoseError, PoseErrorSettings
from tapp.pose_trace import NS, TraceCsv

POSE_PAIR_FIELDS = ('mono_ns', 'stamp_ns', 'travel_m', 'drift_steps', *(
    f'{kind}_{axis}' for kind in ('truth', 'estimated') for axis in ('x', 'y', 'z', 'roll', 'pitch', 'yaw')
))
POSE_PAIR_FILE_BYTES = 2_000_000


class PoseErrorRelay:
    """Translate a copy of each model pose and keep the bridge stamp intact."""

    def __init__(self, model, publish, *, pose3d, trace=None):
        self.model, self.publish, self.pose3d, self.trace = model, publish, pose3d, trace
        self.last_stamp = None
        self.start_ns = None
        self.sin = math.sin(model.yaw_rad/2)
        self.cos = math.cos(model.yaw_rad/2)

    def start(self, message):
        if self.start_ns is None:
            self.start_ns = round(json.loads(message.data)['started_t']*NS)

    def receive(self, message):
        if not message.poses:
            self.publish(message)
            return
        stamp = message.header.stamp
        stamp_ns = stamp.sec*NS+stamp.nanosec
        if self.last_stamp is not None and stamp_ns < self.last_stamp:
            return
        original = message.poses[0]
        p, q = original.position, original.orientation
        if not all(map(math.isfinite, (p.x, p.y, p.z, q.x, q.y, q.z, q.w))):
            return
        # The pre-mission scan stream is available for map initialization, but
        # settling after spawn does not count toward travel for the random walk.
        if self.model.rng is not None and (self.start_ns is None or stamp_ns < self.start_ns):
            dx = dy = 0.
        else:
            dx, dy = self.model.offset(p.x, p.y)
        estimated = deepcopy(message)
        pose = estimated.poses[0]
        pose.position.x += float(dx)
        pose.position.y += float(dy)
        if self.model.yaw_rad:
            c, s = self.cos, self.sin
            pose.orientation.x, pose.orientation.y = c*q.x-s*q.y, c*q.y+s*q.x
            pose.orientation.z, pose.orientation.w = c*q.z+s*q.w, c*q.w-s*q.z
        self.last_stamp = stamp_ns
        self.publish(estimated)
        if self.trace is not None:
            self.trace.write(time.monotonic_ns(), stamp_ns, self.model.travel_m, self.model.steps,
                             *self.pose3d(original), *self.pose3d(pose))


def main(config_file):
    import rclpy
    from rclpy.executors import ExternalShutdownException
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from geometry_msgs.msg import PoseArray
    from std_msgs.msg import String
    from thesis_bunker_mission.transport import pose3d

    config = json.loads(Path(config_file).read_text())
    model = PoseError(PoseErrorSettings(**config['settings']), config['tangent'], config['normal'],
                      config['run_seed'])
    rclpy.init(args=[])
    node = Node('pose_error_relay')
    trace = None
    try:
        if config['trace_dir'] is not None:
            trace = TraceCsv(Path(config['trace_dir'])/'pose_error.csv', POSE_PAIR_FIELDS, POSE_PAIR_FILE_BYTES)
        publisher = node.create_publisher(PoseArray, ESTIMATED_POSE_TOPIC, qos_profile_sensor_data)
        relay = PoseErrorRelay(model, publisher.publish, pose3d=pose3d, trace=trace)
        node.create_subscription(PoseArray, '/ground_truth', relay.receive, qos_profile_sensor_data)
        if model.rng is not None:
            node.create_subscription(String, '/mission/command', relay.start, 10)
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if trace is not None:
            trace.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main(sys.argv[1])
