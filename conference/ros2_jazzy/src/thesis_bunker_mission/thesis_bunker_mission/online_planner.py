"""ROS adapter for perfect-radius sensing and nonblocking incremental mission plans."""

import json
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import PoseArray, PoseStamped
from nav_msgs.msg import Path as ROSPath
from std_msgs.msg import String, Empty
from .transport import pose3d
from .online_runtime import AsyncOnlineMission, load_online_maps


class OnlinePlannerNode(Node):
    def __init__(self):
        super().__init__("online_planner")
        self.declare_parameter("truth_map", "")
        self.declare_parameter("prior_map", "")
        self.declare_parameter("sense_radius_m", 10.0)
        truth_file = self.get_parameter("truth_map").value
        truth, prior_tm, prior, mode = load_online_maps(
            truth_file, self.get_parameter("prior_map").value
        )
        self.map_id = "file/" + Path(truth_file).name
        self.runtime = AsyncOnlineMission(
            truth["tmap"],
            prior_tm,
            prior,
            radius_m=self.get_parameter("sense_radius_m").value,
            prior_lethal_mode=mode,
        )
        self.pose = None
        self.received = None
        self.command = self.create_publisher(String, "/mission/online_command", 10)
        self.path = self.create_publisher(ROSPath, "/mission/path", 10)
        self.create_subscription(
            PoseArray, "/ground_truth", self.on_pose, qos_profile_sensor_data
        )
        self.create_subscription(String, "/mission/command", self.on_mission, 10)
        self.create_subscription(String, "/mission/state", self.on_state, 10)
        self.create_subscription(
            Empty, "/mission/stop", lambda _: self.runtime.stop(), 10
        )
        self.create_timer(0.05, self.tick)

    def on_pose(self, msg):
        if msg.poses:
            self.pose = pose3d(msg.poses[0])
            self.received = self.get_clock().now().nanoseconds / 1e9

    def on_mission(self, msg):
        try:
            mission = json.loads(msg.data)
            if mission["map_id"] != self.map_id:
                self.get_logger().error("truth_mapと指示の地図が一致しません")
                return
            self.runtime.start(mission)
        except (ValueError, KeyError, TypeError) as exc:
            self.get_logger().error(str(exc))

    def on_state(self, msg):
        state = json.loads(msg.data)
        if (
            self.runtime.state
            and state.get("mission_id") == self.runtime.state["mission"].get("id")
            and state.get("status")
            in {
                "completed",
                "stuck",
                "no_path",
                "pose_timeout",
                "invalid_mission",
                "time_reset",
                "stopped",
            }
        ):
            self.runtime.stop()

    def tick(self):
        now = self.get_clock().now().nanoseconds / 1e9
        if self.pose is None or self.received is None or now - self.received > 1.0:
            return
        command = self.runtime.tick(self.pose[:2], now)
        if command is None:
            return
        message = String()
        message.data = json.dumps(command)
        self.command.publish(message)
        if command.get("online_error"):
            self.get_logger().error(command["online_error"])
            return
        path = ROSPath()
        path.header.frame_id = "map"
        path.header.stamp = self.get_clock().now().to_msg()
        for x, y in command["path"]:
            point = PoseStamped()
            point.header = path.header
            point.pose.position.x = x
            point.pose.position.y = y
            point.pose.orientation.w = 1.0
            path.poses.append(point)
        self.path.publish(path)


def main(args=None):
    rclpy.init(args=args)
    node = OnlinePlannerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.runtime.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
