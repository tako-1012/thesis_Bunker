"""Robot-initiated urllib polling; network work never blocks the ROS executor."""

from concurrent.futures import ThreadPoolExecutor
import json
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path
from std_msgs.msg import String
from .transport import RobotHTTP


class WebUIBridge(Node):
    def __init__(self):
        super().__init__("webui_bridge")
        self.declare_parameter("webui", "http://localhost:8080")
        self.declare_parameter("map_id", "file/flat_test_100m.npz")
        self.client = RobotHTTP(
            self.get_parameter("webui").value, self.get_parameter("map_id").value
        )
        self.command = self.create_publisher(String, "/mission/command", 10)
        self.path = self.create_publisher(Path, "/mission/path", 10)
        self.latest = dict(map_id=self.client.map_id, status="idle")
        self.create_subscription(String, "/mission/state", self.on_state, 10)
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.pending = None
        self.rejection = None
        self.create_timer(0.25, self.tick)

    def on_state(self, msg):
        self.latest = json.loads(msg.data)

    def exchange(self, state):
        self.client.state(state)
        return self.client.poll()

    def tick(self):
        if self.pending is not None:
            if not self.pending.done():
                return
            try:
                mission, error = self.pending.result()
                if error:
                    self.rejection = error
                if mission:
                    self.rejection = None
                    # One JSON command carries the path and metadata atomically;
                    # a typed Path is also published for ROS visualization/tools.
                    command = String()
                    command.data = json.dumps(mission)
                    self.command.publish(command)
                    path = Path()
                    path.header.frame_id = "map"
                    path.header.stamp = self.get_clock().now().to_msg()
                    for x, y in mission["path"]:
                        point = PoseStamped()
                        point.header = path.header
                        point.pose.position.x = x
                        point.pose.position.y = y
                        point.pose.orientation.w = 1.0
                        path.poses.append(point)
                    self.path.publish(path)
            except Exception as exc:
                self.get_logger().warning("Web接続: " + str(exc))
        self.pending = self.pool.submit(
            self.exchange, dict(self.rejection or self.latest)
        )


def main(args=None):
    rclpy.init(args=args)
    node = WebUIBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.pool.shutdown(wait=True)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
