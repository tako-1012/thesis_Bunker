"""Thin ROS adapter: world poses in, shared follower commands and run logs out."""

import json
import time
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import PoseArray, Twist
from sensor_msgs.msg import Imu
from std_msgs.msg import String, Empty
from tapp.follower import MissionFollower
from tapp.run_log import RunLog
from .transport import pose3d, rpy


class PathFollower(Node):
    def __init__(self):
        super().__init__("path_follower")
        self.declare_parameter("map_id", "file/flat_test_100m.npz")
        self.declare_parameter("run_root", "")
        self.declare_parameter("stall_timeout_s", 10.0)
        self.map_id = self.get_parameter("map_id").value
        self.pose = None
        self.imu = None
        self.follower = None
        self.log = None
        self.mission_id = 0
        self.pose_received = 0.0
        self.started = None
        self.last_status = "idle"
        self.cmd = self.create_publisher(Twist, "/cmd_vel", 10)
        self.state = self.create_publisher(String, "/mission/state", 10)
        self.create_subscription(
            PoseArray, "/ground_truth", self.on_pose, qos_profile_sensor_data
        )
        self.create_subscription(Imu, "/imu", self.on_imu, qos_profile_sensor_data)
        self.create_subscription(String, "/mission/command", self.on_mission, 10)
        self.create_subscription(Empty, "/mission/stop", lambda _: self.stop(), 10)
        self.create_timer(0.05, self.tick)

    def on_pose(self, msg):
        if msg.poses:
            self.pose = pose3d(msg.poses[0])
            self.pose_received = time.monotonic()

    def on_imu(self, msg):
        self.imu = rpy(msg.orientation)

    def on_mission(self, msg):
        try:
            mission = json.loads(msg.data)
            if mission["map_id"] != self.map_id:
                self.publish_state("map_mismatch")
                return
            settings = dict(
                lookahead_m=mission.get("lookahead_m", 1.0),
                v_max=1.0,
                w_max=1.0,
                goal_tol_m=0.3,
                stall_timeout_s=float(self.get_parameter("stall_timeout_s").value),
            )
            follower = MissionFollower(mission["path"], **settings)
            self.stop("replaced")
            self.follower = follower
            self.mission_id = int(mission.get("id", 0))
            self.started = None
            self.last_status = "running"
            self.log = RunLog(
                dict(mission, controller=settings),
                self.get_parameter("run_root").value or None,
            )
            self.get_logger().info("run log: " + str(self.log.folder))
        except (ValueError, KeyError, TypeError) as exc:
            self.get_logger().error(str(exc))
            self.stop("invalid_mission")

    def publish_state(self, status, t=0.0):
        message = String()
        message.data = json.dumps(
            dict(
                map_id=self.map_id,
                mission_id=self.mission_id,
                status=status,
                pose=self.pose,
                sim_time=t,
            )
        )
        self.state.publish(message)

    def tick(self):
        now = self.get_clock().now().nanoseconds / 1e9
        if self.follower is None:
            self.publish_state(self.last_status, now)
            return
        if self.pose is None or time.monotonic() - self.pose_received > 1.0:
            self.stop("pose_timeout")
            return
        if self.started is None:
            self.started = now
        try:
            v, w, done = self.follower.step(
                now, (self.pose[0], self.pose[1], self.pose[5])
            )
        except ValueError as exc:
            self.get_logger().error(str(exc))
            self.stop("time_reset")
            return
        command = Twist()
        command.linear.x = v
        command.angular.z = w
        self.cmd.publish(command)
        self.log.write(self.follower.log_row(now, self.pose, self.imu, v, w))
        status = self.follower.status
        self.last_status = status
        if done:
            self.log.close(status)
            self.log = None
            self.follower = None
        self.publish_state(status, now)

    def stop(self, status="stopped"):
        self.last_status = status
        if self.log:
            self.log.close(status)
            self.log = None
        self.follower = None
        if rclpy.ok():
            self.cmd.publish(Twist())
            self.publish_state(status, self.get_clock().now().nanoseconds / 1e9)


def main(args=None):
    rclpy.init(args=args)
    node = PathFollower()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.stop()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
