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
from .online_runtime import replace_running_path, record_plan_history


class PathFollower(Node):
    def __init__(self, *, online_fixes='none'):
        super().__init__("path_follower")
        self.declare_parameter("map_id", "file/flat_test_100m.npz")
        self.declare_parameter("run_root", "")
        self.declare_parameter("stall_timeout_s", 10.0)
        self.declare_parameter("online", False)
        self.declare_parameter('online_fixes', online_fixes)
        from tapp.online_safety import validate_fixes
        self.online_fixes = validate_fixes(self.get_parameter('online_fixes').value)
        self.online = self.get_parameter("online").value
        self.current_mission = None
        self.n_replans = 0
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
        self.create_subscription(
            String,
            "/mission/online_command" if self.online else "/mission/command",
            self.on_mission,
            10,
        )
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
            if self.online and (mission.get("endpoint_hold") or mission.get("endpoint_finished")):
                # Keep the same trajectory log during a timed stop/retry.
                self.follower = None
                self.mission_id = int(mission.get("id", 0))
                self.cmd.publish(Twist())
                if mission.get("endpoint_finished"):
                    if self.log is not None:
                        self.log.mission['endpoint_outcomes'] = mission['endpoint_outcomes']
                    self.stop("completed")
                else:
                    self.last_status = "waiting_for_plan"
                return
            if self.online and mission.get("online_error"):
                if self.log is not None and mission.get("id") == self.mission_id:
                    if getattr(self, 'online_fixes', 'none') == 'v1':
                        self.log.mission['online_error'] = mission['online_error']
                    record_plan_history(self.log, mission)
                if int(mission.get("id", 0)) != self.mission_id:
                    self.current_mission = None
                self.n_replans = sum(
                    e["reason"] != "start_leg" for e in mission.get("plan_history", [])
                )
                self.mission_id = int(mission.get("id", 0))
                self.stop("no_path")
                return
            settings = dict(
                lookahead_m=mission.get("lookahead_m", 1.0),
                v_max=1.0,
                w_max=1.0,
                goal_tol_m=0.3,
                stall_timeout_s=float(self.get_parameter("stall_timeout_s").value),
            )
            if (
                self.online
                and mission.get("replace_path")
                and self.log is not None
                and int(mission.get("id", 0)) == self.mission_id
            ):
                self.follower = replace_running_path(
                    self.log,
                    mission,
                    settings,
                    self.get_clock().now().nanoseconds / 1e9,
                    previous=self.follower,
                    **(dict(online_fixes='v1') if getattr(self, 'online_fixes', 'none') == 'v1' else {}),
                )
                self.current_mission = mission
                self.n_replans = mission["n_replans"]
                self.last_status = "running"
                return
            if getattr(self, 'online_fixes', 'none') == 'v1':
                from tapp.online_safety import make_follower
                follower = make_follower(mission['path'], online_fixes='v1', **settings)
            else:
                follower = MissionFollower(mission["path"], **settings)
            self.stop("replaced")
            self.follower = follower
            self.mission_id = int(mission.get("id", 0))
            self.started = None
            self.last_status = "running"
            self.current_mission = mission
            self.n_replans = mission.get("n_replans", 0)
            self.log = RunLog(
                dict(mission, controller=settings),
                self.get_parameter("run_root").value or None,
            )
            if self.online:
                record_plan_history(self.log, mission)
            self.get_logger().info("run log: " + str(self.log.folder))
        except (ValueError, KeyError, TypeError) as exc:
            self.get_logger().error(str(exc))
            self.stop("invalid_mission")

    def publish_state(self, status, t=0.0):
        message = String()
        payload = dict(
            map_id=self.map_id,
            mission_id=self.mission_id,
            status=status,
            pose=self.pose,
            sim_time=t,
        )
        if self.online and self.current_mission:
            payload.update(
                current_path=self.current_mission["path"], n_replans=self.n_replans
            )
            if getattr(self, 'online_fixes', 'none') == 'v1':
                payload['safety_revision'] = self.current_mission.get('revision', 0)
        message.data = json.dumps(payload)
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
            if getattr(self, 'online_fixes', 'none') == 'v1':
                v, w, done = self.follower.step(now, self.pose, imu_rpy=self.imu)
            else:
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
        if getattr(self, 'online_fixes', 'none') == 'v1' and status in ('unsafe_tilt', 'off_path'):
            if self.last_status != status:
                from .online_safety import append_event
                append_event(self.log.folder/'safety_stops.csv', now, status,
                             dict(pose=list(self.pose), revision=self.current_mission.get('revision', 0)))
            done = False  # Retain this run/log while waiting for a new path.
        if (
            done
            and status == "completed"
            and self.online
            and not self.current_mission.get("final_leg", True)
        ):
            # Keep the same run/CSV open while the next leg is planned.
            status = "waiting_for_plan"
            done = False
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
    import argparse
    import sys
    from tapp.online_safety import ONLINE_FIXES
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--online-fixes', choices=ONLINE_FIXES, default=None)
    options, remaining = parser.parse_known_args(sys.argv[1:] if args is None else args)
    rclpy.init(args=remaining if options.online_fixes is not None else args)
    node = PathFollower(**(dict(online_fixes=options.online_fixes) if options.online_fixes is not None else {}))
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.stop()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
