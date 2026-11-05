"""Stamped PointCloud2 -> stale-prior map -> task021 async ROS mission adapter."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'ros2_jazzy/src/thesis_bunker_mission'))
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import PoseArray
from nav_msgs.msg import Path as ROSPath
from sensor_msgs.msg import PointCloud2
from std_msgs.msg import String, Empty
from thesis_bunker_mission.online_planner import OnlinePlannerNode
from tapp.mapfile import load_map_file
from tapp.pointcloud_map import PointCloudMap, PoseBuffer, decode_xyz
from ros2_jazzy.gz_checks.lidar_runtime import LidarOnlineMission
from ros2_jazzy.gz_checks.online_batch_runtime import CsvChunks
from ros2_jazzy.gz_checks.lidar_map import make_pointcloud_map

UPDATE_FIELDS = ['stamp', 'status', 'error', 'version', 'input_points', 'accepted_points',
                 'observed_cells', 'update_s', 'decode_s', 'queue_drops', 'cloud_sha256']


class LidarPlannerNode(OnlinePlannerNode):
    def __init__(self):
        # Deliberately do not load truth_map or construct a perfect-sensor runtime.
        Node.__init__(self, 'lidar_planner')
        for name, default in [('prior_map', ''), ('map_id', 'file/truth.npz'), ('run_folder', ''),
                              ('sensor_height_m', .8), ('max_range_m', 30.), ('obstacle_height_m', .3), ('range_resolution_m', .01),
                              ('stale_timeout_s', .5), ('map_method', 'coarse')]:
            self.declare_parameter(name, default)
        # Cloud age that stops the mission; 0.5s by default, raised only for slow CPU rendering.
        self.stale_timeout_s = float(self.get_parameter('stale_timeout_s').value)
        prior = load_map_file(self.get_parameter('prior_map').value)
        self.folder = Path(self.get_parameter('run_folder').value)
        if not self.get_parameter('run_folder').value:
            raise ValueError('run_folder is required')
        self.folder.mkdir(parents=True, exist_ok=True)
        self.map_id = self.get_parameter('map_id').value
        raw_obstacle = prior['obstacle'] | prior['water'] | prior['nodata']
        self.mapper = make_pointcloud_map(prior['tmap'].elev, raw_obstacle,
                                    map_method=self.get_parameter('map_method').value,
                                    robot=prior['tmap'].robot, weights=prior['tmap'].weights,
                                    sensor_height_m=self.get_parameter('sensor_height_m').value,
                                    max_range_m=self.get_parameter('max_range_m').value,
                                    range_resolution_m=self.get_parameter('range_resolution_m').value,
                                    obstacle_height_m=self.get_parameter('obstacle_height_m').value)
        self.runtime = LidarOnlineMission(prior, self.mapper, plan_log=self.folder / 'plans.csv')
        self.poses = PoseBuffer()
        self.map_pool = ThreadPoolExecutor(max_workers=1)
        self.pending = self.future = None
        self.last_cloud_stamp = self.mission_started = None
        self.dropped = self.received_clouds = 0
        self.observed_cells = 0
        self.last_error = ''
        self.terminal_sensor_error = ''
        self.mapping_finished = self.watchdog_sent = False
        self.log = CsvChunks(self.folder / 'map_updates.csv', UPDATE_FIELDS)
        self.pose = self.received = None
        self.command = self.create_publisher(String, '/mission/online_command', 10)
        self.path = self.create_publisher(ROSPath, '/mission/path', 10)
        self.sensor_state = self.create_publisher(String, '/lidar/state', 10)
        self.create_subscription(PoseArray, '/ground_truth', self.on_pose, qos_profile_sensor_data)
        self.create_subscription(PointCloud2, '/lidar/points', self.on_cloud, qos_profile_sensor_data)
        self.create_subscription(String, '/mission/command', self.on_mission, 10)
        self.create_subscription(String, '/mission/state', self.on_state, 10)
        self.create_subscription(Empty, '/mission/stop', self.on_stop, 10)
        self.create_timer(.02, self.map_tick)
        self.create_timer(.05, self.tick)

    @staticmethod
    def stamp(message):
        return message.header.stamp.sec + message.header.stamp.nanosec/1e9

    def on_pose(self, message):
        super().on_pose(message)
        stamp = self.stamp(message)
        now = self.get_clock().now().nanoseconds/1e9
        try:
            if stamp == 0 and now > .1:
                raise ValueError('ground-truth timestamp is absent')
            self.poses.add(stamp, self.pose)
        except ValueError as exc:
            self.last_error = str(exc)

    def on_cloud(self, message):
        if self.mapping_finished:
            return
        self.received_clouds += 1
        if self.pending is not None:
            self.dropped += 1
        self.pending = message  # Bounded backlog: keep only the latest unprocessed scan.

    def on_mission(self, message):
        version = self.runtime.version
        super().on_mission(message)
        if self.runtime.version != version:
            self.mission_started = self.get_clock().now().nanoseconds/1e9

    def on_state(self, message):
        super().on_state(message)
        if self.runtime.state is not None and self.runtime.finished:
            self.mapping_finished = True

    def on_stop(self, _):
        self.mapping_finished = True
        self.runtime.stop()

    def _update(self, message, pose):
        began = time.perf_counter()
        frame = message.header.frame_id
        if frame != 'lidar' and not frame.endswith('/lidar'):
            raise ValueError('unexpected sensor frame: ' + frame)
        if self.stamp(message) == 0 and self.get_clock().now().nanoseconds/1e9 > .1:
            raise ValueError('LiDAR timestamp is absent')
        fields = [dict(name=f.name, offset=f.offset, datatype=f.datatype, count=f.count) for f in message.fields]
        points = decode_xyz(message.data, fields, point_step=message.point_step, row_step=message.row_step,
                            width=message.width, height=message.height, is_bigendian=message.is_bigendian)
        decoded = time.perf_counter()
        result = self.mapper.update(points, pose)
        result.update(decode_s=decoded-began, update_s=time.perf_counter()-began,
                      cloud_sha256=hashlib.sha256(message.data).hexdigest())
        if not (self.folder / 'first_cloud.npz').exists():
            np.savez_compressed(self.folder / 'first_cloud.npz', points=points, pose=pose, stamp=self.stamp(message))
        return result

    def _collect(self):
        if self.future is None or not self.future.done():
            return
        row = dict.fromkeys(UPDATE_FIELDS)
        row.update(stamp=self.future_stamp, status='ok', error='', queue_drops=self.dropped)
        try:
            result = self.future.result()
            row.update(result)
            self.observed_cells = result['observed_cells']
            if result['accepted_points']:
                self.last_cloud_stamp = self.future_stamp
            self.last_error = ''
        except Exception as exc:
            row.update(status='error', error=type(exc).__name__ + ': ' + str(exc))
            self.last_error = row['error']
        self.log.write(row)
        self.future = None

    def map_tick(self):
        self._collect()
        now = self.get_clock().now().nanoseconds/1e9
        if self.future is None and self.pending is not None and not self.mapping_finished:
            message = self.pending
            stamp = self.stamp(message)
            pose = self.poses.at(stamp)
            if pose is not None:
                self.pending = None
                self.future_stamp = stamp
                self.future = self.map_pool.submit(self._update, message, pose)
            elif now-stamp > self.stale_timeout_s:
                self.pending = None
                self.dropped += 1
                self.last_error = 'no bracketing stamped pose for LiDAR cloud'
        state = dict(ready=self.last_cloud_stamp is not None and now-self.last_cloud_stamp <= self.stale_timeout_s,
                     observed_cells=self.observed_cells, received_clouds=self.received_clouds,
                     queue_drops=self.dropped, last_cloud_stamp=self.last_cloud_stamp,
                     error=self.terminal_sensor_error or self.last_error)
        message = String()
        message.data = json.dumps(state)
        self.sensor_state.publish(message)

    def tick(self):
        now = self.get_clock().now().nanoseconds/1e9
        if self.runtime.state is not None and not self.runtime.finished:
            if self.last_cloud_stamp is None or now-self.last_cloud_stamp > self.stale_timeout_s:
                if self.mission_started is not None and now-self.mission_started > .5 and not self.watchdog_sent:
                    self.terminal_sensor_error = 'lidar_unavailable_or_stale'
                    message = String()
                    message.data = json.dumps(dict(self.runtime.state['mission'], online_generated=True,
                                                   online_error='lidar_unavailable_or_stale'))
                    self.command.publish(message)
                    self.watchdog_sent = True
                    self.runtime.stop()
                return
        super().tick()

    def close(self):
        self.mapping_finished = True
        self.map_pool.shutdown(wait=True)
        self._collect()
        self.runtime.close()
        self.mapper.save(self.folder / 'pointcloud_map.npz')
        (self.folder / 'sensor_status.json').write_text(json.dumps(dict(
            received_clouds=self.received_clouds, queue_drops=self.dropped,
            last_cloud_stamp=self.last_cloud_stamp, error=self.terminal_sensor_error or self.last_error,
            sensor_height_m=self.mapper.sensor_height_m, obstacle_height_m=self.mapper.obstacle_height_m,
            scan_storage='first cloud plus SHA-256 per processed scan; complete cloud stream not stored'), indent=2)+'\n')
        self.log.close()


def main(args=None):
    rclpy.init(args=args)
    node = LidarPlannerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
